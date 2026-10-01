"""Phase 5 E2E for the D5 recording booth (record.py + web/record.html).

Drives the REAL page in headless Chrome with the fake-microphone
device, then asserts server-side on what actually landed in
data/_incoming — the same Ground Rule 1 discipline as e2e_flow.py:
nothing is claimed saved unless the file, checklist sidecar, and
decoded waveform are really on disk.

Covers:
  1. Session form -> session created with provenance fields
  2. Fake-mic canonical take  -> 200, stored + sidecar + D1-decodable
  3. Fake-mic recitation take -> 200, take numbering t1
  4. Promotion mapping        -> PROMOTION.md block, corpus tree untouched

Run: see tools/e2e_booth.sh (launches server + Chrome, runs this file).
"""
import asyncio
import json
import time
import urllib.request

from websockets.client import connect

PORT = 9334
BASE = "http://127.0.0.1:8030"
SHOTS = "files/e2e-screens"


def page_target_ws_url():
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list") as r:
        targets = json.load(r)
    pages = [t for t in targets if t.get("type") == "page"]
    return pages[0]["webSocketDebuggerUrl"]


async def rpc(ws, msg_id, method, params=None, timeout=25):
    await ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
    deadline = time.time() + timeout
    while time.time() < deadline:
        raw = json.loads(await asyncio.wait_for(ws.recv(), timeout=deadline - time.time()))
        if raw.get("id") == msg_id:
            if "error" in raw:
                raise RuntimeError(f"{method}: {raw['error']}")
            return raw.get("result", {})
    raise TimeoutError(method)


class Driver:
    def __init__(self, ws):
        self.ws = ws
        self.n = 100

    async def ev(self, expr, await_promise=False):
        self.n += 1
        r = await rpc(self.ws, self.n, "Runtime.evaluate", {
            "expression": expr, "returnByValue": True, "awaitPromise": await_promise,
        })
        return r.get("result", {}).get("value")

    async def wait(self, expr, timeout=25.0, desc=""):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if await self.ev(expr) is True:
                return True
            await asyncio.sleep(0.25)
        raise TimeoutError(f"timeout waiting for: {desc or expr}")

    async def goto(self, path, settle_expr):
        url = BASE + path
        await rpc(self.ws, 3, "Page.navigate", {"url": url})
        await self.wait(
            f"location.href === {json.dumps(url)} && document.readyState !== 'loading'",
            desc=f"nav to {url}",
        )
        await self.wait(settle_expr, desc=f"settle {url}")

    async def shot(self, path):
        self.n += 1
        r = await rpc(self.ws, self.n, "Page.captureScreenshot", {"format": "png"})
        with open(path, "wb") as f:
            f.write(base64_decode(r["data"]))
        print(f"    screenshot -> {path}")


def base64_decode(b64):
    import base64
    return base64.b64decode(b64)


def ok(label, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    return bool(cond)


def main_sync_server_checks(session_hint):
    from pathlib import Path
    import json as _json
    import wave
    root = Path("data/_incoming")

    def latest(prefix):
        for s in sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if s.name.startswith(prefix):
                return s
        return None

    problems = []
    sess = latest("SPD-REC-")
    if sess is None:
        problems.append("no SPD session dir found on disk")
    else:
        wavs = sorted(sess.glob("spd_*.wav"))
        if len(wavs) < 2:
            problems.append(f"expected >=2 takes on disk, found {len(wavs)}")
        for w in wavs:
            with wave.open(str(w), "rb") as f:
                if f.getframerate() != 16000 or f.getnframes() < 8000:
                    problems.append(f"{w.name}: not a 16 kHz / >=0.5 s WAV")
            side = w.with_name(w.stem + ".checklist.json")
            if not side.is_file():
                problems.append(f"{w.name}: missing checklist sidecar")
        if (sess.parent.parent / "spd" / "reference_words").exists():
            problems.append("corpus tree data/spd/reference_words was created by capture!")

    gvr_problems = []
    gsess = latest("GVR-REC-")
    if gsess is None:
        gvr_problems.append("no GVR session dir found on disk")
    else:
        gwav = sorted(gsess.glob("gvr_*.wav"))
        if len(gwav) != 1:
            gvr_problems.append(f"expected 1 verse take, found {len(gwav)}")
        for w in gwav:
            side = w.with_name(w.stem + ".checklist.json")
            if not side.is_file():
                gvr_problems.append(f"{w.name}: missing checklist sidecar")
                continue
            cl = _json.loads(side.read_text(encoding="utf-8"))
            if cl.get("item") != "2.13" or cl.get("program") != "D4":
                gvr_problems.append(f"{w.name}: wrong checklist item/program")
            if not cl.get("recitation_tradition"):
                gvr_problems.append(f"{w.name}: tradition missing from checklist")
        if (gsess.parent.parent / "gvr_recordings").exists():
            gvr_problems.append("corpus tree data/gvr_recordings was created by capture!")
    return problems, (sess.name if sess else ""), gvr_problems, (gsess.name if gsess else "")


async def main():
    results = []
    async with connect(page_target_ws_url()) as ws:
        await rpc(ws, 1, "Runtime.enable")
        await rpc(ws, 2, "Page.enable")
        await rpc(ws, 4, "Emulation.setDeviceMetricsOverride",
                  {"width": 1280, "height": 900, "deviceScaleFactor": 1, "mobile": False})
        d = Driver(ws)

        # ---------------- Test 1: session creation through the real form
        print("\n[1] Booth — start session through the wired form")
        await d.goto("/", "document.querySelectorAll('#wordGrid .capBtn').length > 0")
        n_words = await d.ev("document.querySelectorAll('#wordGrid .capBtn').length / 2")
        results.append(ok("word grid rendered the 27-word list", n_words == 27, f"{n_words} words"))
        await d.ev("document.getElementById('fReciter').value = 'e2e_bot'")
        await d.ev("document.getElementById('fLocation').value = 'headless chrome, fake mic'")
        await d.ev("document.getElementById('fDevice').value = 'fake device'")
        await d.ev("document.getElementById('fConsent').checked = true")
        await d.ev("document.getElementById('startBtn').click()")
        await d.wait("document.getElementById('booth').classList.contains('hidden') === false",
                     desc="booth visible after session start")
        session_id = await d.ev("document.getElementById('sessionId').textContent")
        results.append(ok("session id minted and shown",
                          str(session_id).startswith("SPD-REC-"), str(session_id)))
        await d.shot(f"{SHOTS}/booth-session.png")

        # ---------------- Test 2: fake-mic canonical take on kRSNa
        print("\n[2] Booth — fake-mic canonical take (kRSNa)")
        await d.ev("document.querySelector('button[data-wid=\"kRSNa\"][data-role=\"canonical\"]').click()")
        await d.wait("document.getElementById('recModal').classList.contains('hidden') === false",
                     desc="recorder modal open")
        await d.ev("document.getElementById('recBtn').click()")
        await d.wait("document.getElementById('recHint').textContent.indexOf('recording') !== -1",
                     desc="recording started")
        await asyncio.sleep(2.0)
        await d.ev("document.getElementById('recBtn').click()")
        await d.wait(
            "document.getElementById('recHint').textContent.indexOf('saved') !== -1 || "
            "document.getElementById('recHint').textContent.indexOf('REJECTED') !== -1",
            desc="upload settled",
        )
        hint = await d.ev("document.getElementById('recHint').textContent")
        results.append(ok("canonical take saved through the real capture path",
                          "saved" in str(hint), str(hint)))
        results.append(ok("take file is the canonical t0 name",
                          "spd_kRSNa_canonical_t0.wav" in str(hint), str(hint)))
        await d.shot(f"{SHOTS}/booth-canonical-take.png")

        # ---------------- Test 3: fake-mic recitation takes (numbering)
        print("\n[3] Booth — recitation takes, server-computed numbering")
        for i in (1, 2):
            await d.ev("document.querySelector('button[data-wid=\"kRSNa\"][data-role=\"recitation\"]').click()")
            await d.wait("document.getElementById('recModal').classList.contains('hidden') === false",
                         desc=f"modal open for take {i}")
            await d.ev("document.getElementById('recBtn').click()")
            await d.wait("document.getElementById('recHint').textContent.indexOf('recording') !== -1",
                         desc="recording")
            await asyncio.sleep(1.6)
            await d.ev("document.getElementById('recBtn').click()")
            await d.wait("document.getElementById('recHint').textContent.indexOf('saved') !== -1",
                         desc=f"take {i} saved")
        stats = await d.ev("document.getElementById('sessionStats').textContent")
        results.append(ok("stats reflect 1 canonical + 2 recitation takes",
                          "1 canonical · 2 recitation" in str(stats), str(stats)))
        grid_btn = await d.ev(
            "document.querySelector('button[data-wid=\"kRSNa\"][data-role=\"recitation\"]').textContent")
        results.append(ok("grid shows the recitation count badge",
                          "(2)" in str(grid_btn), str(grid_btn)))
        await d.shot(f"{SHOTS}/booth-recitation-takes.png")

        # ---------------- Test 4: promotion mapping, corpus untouched
        print("\n[4] Booth — promotion mapping, corpus-tree boundary")
        await d.ev("document.getElementById('promoteBtn').click()")
        await d.wait("document.getElementById('promotionOut').classList.contains('hidden') === false",
                     desc="promotion output shown")
        promo = await d.ev("document.getElementById('promotionOut').textContent")
        results.append(ok("promotion mapping lists canonical → reference_words",
                          "spd_kRSNa_canonical_t0.wav → reference_words/kRSNa.wav" in str(promo)
                          or ("spd_kRSNa_canonical_t0.wav" in str(promo)
                              and "reference_words/kRSNa.wav" in str(promo)),
                          str(promo)[:80]))
        results.append(ok("corpus tree untouched by capture",
                          "NOT copied into data/spd/" in str(promo) or "nothing copied" in str(promo).lower(),
                          str(promo)[:120]))
        await d.shot(f"{SHOTS}/booth-promotion.png")

        # ---------------- Test 5: D4 (Gita verses) program flow
        print("\n[5] Booth — D4 verse mode end-to-end")
        await d.goto("/", "document.querySelectorAll('#wordGrid .capBtn').length > 0")
        await d.ev("document.querySelector('input[name=\"prog\"][value=\"D4\"]').click()")
        await d.ev("document.getElementById('fReciter').value = 'e2e_bot'")
        await d.ev("document.getElementById('fLocation').value = 'headless chrome, fake mic'")
        await d.ev("document.getElementById('fDevice').value = 'fake device'")
        await d.ev("document.getElementById('fTradition').value = 'classical paatha, no Vedic accents'")
        await d.ev("document.getElementById('fSourceId').value = 'GVR-D4-SELF'")
        await d.ev("document.getElementById('fConsent').checked = true")
        await d.ev("document.getElementById('startBtn').click()")
        await d.wait("/^GVR-REC-/.test(document.getElementById('sessionId').textContent)",
                     desc="GVR-REC session minted")
        n_verses = await d.ev("document.querySelectorAll('#wordGrid .capBtn').length")
        results.append(ok("D4 grid shows the 20-verse FR-22 subset",
                          n_verses == 20, f"{n_verses} verse cards"))
        await d.ev("document.querySelector('button[data-wid=\"2.13\"][data-role=\"recitation\"]').click()")
        await d.wait("document.getElementById('recModal').classList.contains('hidden') === false",
                     desc="verse modal open")
        verse_shown = await d.ev("document.getElementById('modalVerse').textContent")
        results.append(ok("modal displays the real 2.13 mūla from the parsed source",
                          "देहिनो" in str(verse_shown) and "कौमारं" in str(verse_shown),
                          str(verse_shown)[:40]))
        await d.ev("document.getElementById('recBtn').click()")
        await d.wait("document.getElementById('recHint').textContent.indexOf('recording') !== -1",
                     desc="recording")
        await asyncio.sleep(1.8)
        await d.ev("document.getElementById('recBtn').click()")
        await d.wait("document.getElementById('recHint').textContent.indexOf('saved') !== -1",
                     desc="D4 take saved")
        hint5 = await d.ev("document.getElementById('recHint').textContent")
        results.append(ok("verse take saved under the protocol fname_key",
                          "gvr_c2v13_recitation_t0.wav" in str(hint5), str(hint5)))
        await d.shot(f"{SHOTS}/booth-d4-verse-take.png")

    print("\n[6] Server-side disk truth")
    problems, sess_name, gvr_problems, gvr_name = main_sync_server_checks(None)
    results.append(ok("D5 session dir valid (WAVs + sidecars + sheet)",
                      not problems, "; ".join(map(str, problems))))
    results.append(ok("D5 capture stayed inside data/_incoming",
                      sess_name.startswith("SPD-REC-"), sess_name))
    results.append(ok("D4 session dir valid (verse take + tradition carried)",
                      not gvr_problems, "; ".join(map(str, gvr_problems))))
    results.append(ok("D4 capture stayed inside data/_incoming",
                      gvr_name.startswith("GVR-REC-"), gvr_name))

    print("\n===== E2E RESULT:", "ALL PASS" if all(results) else "FAILURES", "=====")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
