"""Phase 5 E2E (negative cases): every backend-failure path must render
an explicit failure state — never stale data or a fabricated value.

Case A: SPD page loaded, then the API process is killed; the user
        uploads a clip and submits — expect an explicit network card.
Case B: status page loaded with /api/* blocked via CDP (the server
        itself stays up, since it serves the static page too) — expect
        explicit 'unavailable' states, no stale numbers.
"""
import asyncio
import json
import os
import signal
import time
import urllib.request

from websockets.client import connect

PORT = int(os.environ.get("SD_CDP_PORT", "9333"))
BASE = os.environ.get("SD_BASE", "http://127.0.0.1:8000")


def page_target():
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

    async def ev(self, expr):
        self.n += 1
        try:
            r = await rpc(self.ws, self.n, "Runtime.evaluate",
                          {"expression": expr, "returnByValue": True})
            return r.get("result", {}).get("value")
        except RuntimeError:
            return None  # context can be unavailable mid-navigation

    async def wait(self, expr, timeout=30.0, desc=""):
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
            desc=f"nav {url}")
        await self.wait(settle_expr, desc=f"settle {url}")


def ok(label, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    return bool(cond)


BUILD_WAV_JS = """
(async () => {
  const sr = 16000, n = Math.round(sr * 0.3);
  const buf = new ArrayBuffer(44 + n * 2);
  const v = new DataView(buf);
  const w = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
  w(0, 'RIFF'); v.setUint32(4, 36 + n * 2, true); w(8, 'WAVE');
  w(12, 'fmt '); v.setUint32(16, 16, true); v.setUint16(20, 1, true);
  v.setUint16(22, 1, true); v.setUint32(24, 16000, true);
  v.setUint32(28, 32000, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
  w(36, 'data'); v.setUint32(40, n * 2, true);
  for (let i = 0; i < n; i++) v.setInt16(44 + i * 2, Math.round(8000 * Math.sin(i / 10)), true);
  const dt = new DataTransfer();
  dt.items.add(new File([buf], 'offline.wav', { type: 'audio/wav' }));
  const inp = document.getElementById('audioFileInput');
  inp.files = dt.files;
  inp.dispatchEvent(new Event('change', { bubbles: true }));
  return 'dropped';
})()
"""


async def main():
    results = []
    async with connect(page_target()) as ws:
        await rpc(ws, 1, "Runtime.enable")
        await rpc(ws, 2, "Page.enable")
        d = Driver(ws)

        # ---------- Load SPD while the API is up (used by both cases)
        await d.goto("/spd.html",
                     "document.querySelectorAll('#wordList button[data-wid]').length > 0")
        words_rendered = await d.ev(
            "document.querySelectorAll('#wordList button[data-wid]').length")
        results.append(ok("word list rendered while API was up",
                          (words_rendered or 0) >= 27, f"{words_rendered} buttons"))

        # ---------- Case B FIRST: status page with /api/* blocked via CDP
        # (server stays up — it serves the static page too; only the API
        # calls are blocked, simulating an unreachable backend).
        print("\n[case B] status page with /api/* requests blocked via CDP")
        await rpc(ws, 5, "Network.enable")
        await rpc(ws, 6, "Network.setBlockedURLs", {"urls": ["*://127.0.0.1:*/api/*"]})
        await d.goto("/status.html",
                     "document.getElementById('statWordMeta').textContent.indexOf('unavailable') !== -1")
        meta = await d.ev("document.getElementById('statWordMeta').textContent")
        audit = await d.ev("document.querySelector('#auditBody tr td').textContent")
        count = await d.ev("document.getElementById('statWordCount').textContent")
        results.append(ok("status page shows explicit unavailable state",
                          "unavailable" in meta, meta.strip()[:90]))
        results.append(ok("audit table renders the failure, not stale rows",
                          "unavailable" in audit, audit.strip()[:80]))
        results.append(ok("no fabricated word count while API unreachable",
                          count.strip() == "—", f"shows {count!r}"))
        await rpc(ws, 7, "Network.setBlockedURLs", {"urls": []})

        # ---------- Case A: kill the API, submit from the live SPD page
        print("\n[case A] back to SPD (server still up), then killing the API")
        await d.goto("/spd.html",
                     "document.querySelectorAll('#wordList button[data-wid]').length > 0")
        os.kill(int(os.environ["SD_SERVER_PID"]), signal.SIGTERM)
        time.sleep(1.0)

        await d.ev(BUILD_WAV_JS)
        await d.wait("!document.getElementById('submitBtn').disabled",
                     desc="offline clip prepared (decode is local)")
        await d.ev("document.getElementById('submitBtn').click()")
        await d.wait(
            "document.getElementById('resultBadge').textContent.indexOf('network') !== -1",
            desc="explicit network-failure card")
        badge = await d.ev("document.getElementById('resultBadge').textContent")
        note = await d.ev("document.getElementById('resultNote').textContent")
        score = await d.ev("document.getElementById('resultScore').textContent")
        results.append(ok("offline submit renders explicit network state",
                          "network" in badge, badge.strip()))
        results.append(ok("note tells the user how to recover",
                          "uvicorn" in note or "server" in note.lower(), note[:80]))
        results.append(ok("no score fabricated while offline", score.strip() == "—"))

    print("\n===== NEGATIVE E2E RESULT:", "ALL PASS" if all(results) else "FAILURES", "=====")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
