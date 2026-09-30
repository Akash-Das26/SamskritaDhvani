"""Phase 5 E2E: drive the WIRED UI end-to-end in headless Chrome with a
fake microphone device.

Covers, through the real page code paths (no direct API calls):
  1. SPD upload fallback  -> submit -> explicit 503 model_unavailable card
  2. SPD mic recording    -> submit -> explicit 503 model_unavailable card
  3. GVR  mic recording   -> submit -> explicit 503 fallback panel
  4. GVR  garbage upload  -> explicit client-side decode failure state

Ground Rule 1 assertion on every test: no numeric score or recognized
verse is ever displayed without a real 200 response.
"""
import asyncio
import base64
import io
import json
import math
import random
import struct
import time
import urllib.request
import wave

from websockets.client import connect

PORT = 9333
BASE = "http://127.0.0.1:8000"
SHOTS = "files/e2e-screens"


def page_target_ws_url():
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list") as r:
        targets = json.load(r)
    pages = [t for t in targets if t.get("type") == "page"]
    return pages[0]["webSocketDebuggerUrl"]


def speech_like_wav_b64(dur=1.5, sr=16000):
    """A real decodable WAV: voiced harmonic stack, pitch contour,
    amplitude envelope — the kind of clip the pipeline expects."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        frames = []
        for i in range(int(sr * dur)):
            t = i / sr
            env = max(0.0, math.sin(math.pi * min(1.0, t / dur)))
            f0 = 120 + 30 * math.sin(2 * math.pi * 0.7 * t)
            v = sum(math.sin(2 * math.pi * f0 * h * t) / h for h in (1, 2, 3, 4, 5))
            v = v * 0.4 * env + 0.01 * random.uniform(-1, 1)
            frames.append(struct.pack("<h", int(v * 32767)))
        w.writeframes(b"".join(frames))
    return base64.b64encode(buf.getvalue()).decode()


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
            f.write(base64.b64decode(r["data"]))
        print(f"    screenshot -> {path}")


def ok(label, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    return bool(cond)


DROP_FILE_JS = """
(async (b64, name) => {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  const dt = new DataTransfer();
  dt.items.add(new File([bytes], name, { type: 'audio/wav' }));
  const inp = document.getElementById('audioFileInput');
  inp.files = dt.files;
  inp.dispatchEvent(new Event('change', { bubbles: true }));
  return 'dropped';
})
"""


async def main():
    results = []
    async with connect(page_target_ws_url()) as ws:
        await rpc(ws, 1, "Runtime.enable")
        await rpc(ws, 2, "Page.enable")
        await rpc(ws, 4, "Emulation.setDeviceMetricsOverride",
                  {"width": 1280, "height": 900, "deviceScaleFactor": 1, "mobile": False})
        d = Driver(ws)

        # ---------------- Test 1: SPD upload fallback -> 503 card
        print("\n[1] SPD — upload fallback through the wired UI")
        await d.goto("/spd.html",
                     "document.querySelectorAll('#wordList button[data-wid]').length > 0")
        await d.ev(f"({DROP_FILE_JS})('{speech_like_wav_b64()}', 'attempt.wav')",
                   await_promise=True)
        await d.wait("!document.getElementById('submitBtn').disabled",
                     desc="upload decoded, submit enabled")
        clip_meta = await d.ev("document.getElementById('uploadFileName').textContent")
        print(f"    clip meta: {clip_meta}")
        await d.ev("document.getElementById('submitBtn').click()")
        await d.wait(
            "document.getElementById('resultBadge').textContent.indexOf('model_unavailable') !== -1",
            desc="explicit 503 model_unavailable card",
        )
        score = await d.ev("document.getElementById('resultScore').textContent")
        note = await d.ev("document.getElementById('resultNote').textContent")
        badge = await d.ev("document.getElementById('resultBadge').textContent")
        results.append(ok("submit rendered the explicit 503 state", "model_unavailable" in badge, badge.strip()))
        results.append(ok("no numeric score displayed without a 200", score.strip() == "—", f"score shows {score!r}"))
        results.append(ok("note names the missing D2 scorer", "D2" in note, note[:90]))
        await d.shot(f"{SHOTS}/spd-upload-503.png")

        # ---------------- Test 2: SPD fake-mic recording -> 503 card
        print("\n[2] SPD — real getUserMedia/MediaRecorder recording path")
        await d.goto("/spd.html",
                     "document.querySelectorAll('#wordList button[data-wid]').length > 0")
        await d.ev("document.getElementById('recordBtn').click()")
        await d.wait("document.getElementById('micStatusText').textContent.indexOf('Capturing') !== -1",
                     desc="recording started")
        await asyncio.sleep(1.6)
        timer_mid = await d.ev("document.getElementById('timerText').textContent")
        print(f"    live timer mid-recording: {timer_mid!r}")
        await d.ev("document.getElementById('recordBtn').click()")
        await d.wait("document.getElementById('micStatusText').textContent.indexOf('captured') !== -1",
                     desc="recording stopped and transcoded")
        await d.wait("!document.getElementById('submitBtn').disabled", desc="submit enabled")
        await d.ev("document.getElementById('submitBtn').click()")
        await d.wait(
            "document.getElementById('resultBadge').textContent.indexOf('model_unavailable') !== -1",
            desc="explicit 503 card",
        )
        score2 = await d.ev("document.getElementById('resultScore').textContent")
        badge2 = await d.ev("document.getElementById('resultBadge').textContent")
        results.append(ok("mic recording reached the backend", "model_unavailable" in badge2, badge2.strip()))
        results.append(ok("timer advanced as a real clock", "00:00.0" not in timer_mid, timer_mid.strip()))
        results.append(ok("no score fabricated on 503", score2.strip() == "—", f"score shows {score2!r}"))
        await d.shot(f"{SHOTS}/spd-mic-503.png")

        # ---------------- Test 3: GVR fake-mic recording -> 503 fallback panel
        print("\n[3] GVR — recording path, honest not-recognized fallback")
        await d.goto("/gvr.html",
                     "window.SD && document.getElementById('gvrStatusLine').textContent.indexOf('no submission') !== -1")
        await d.ev("document.getElementById('recordToggleBtn').click()")
        await d.wait("document.getElementById('micIcon').textContent === 'stop'",
                     desc="recording started")
        await asyncio.sleep(2.0)
        clock_mid = await d.ev("document.getElementById('timeCounter').textContent")
        print(f"    live clock mid-recording: {clock_mid!r}")
        await d.ev("document.getElementById('recordToggleBtn').click()")
        await d.wait("document.getElementById('gvrClipMeta').textContent.indexOf('clip ready') !== -1",
                     desc="clip ready")
        await d.ev("document.getElementById('submitBtn').click()")
        await d.wait(
            "document.getElementById('gvrFallback').classList.contains('hidden') === false && "
            "document.getElementById('fallbackFlag').textContent.indexOf('model_unavailable') !== -1",
            desc="explicit 503 fallback panel",
        )
        fallback_head = await d.ev("document.getElementById('fallbackHead').textContent")
        body_has_verse = await d.ev("document.body.textContent.indexOf('patraṁ puṣpaṁ') !== -1")
        match_hidden = await d.ev("document.getElementById('gvrResult').classList.contains('hidden')")
        results.append(ok("fallback panel shows model_unavailable", True))
        results.append(ok("fallback copy is the honest no-model state",
                          "not scored" in fallback_head and "not available" in fallback_head,
                          fallback_head.strip()))
        results.append(ok("match card stays hidden (no verse shown)", match_hidden is True))
        results.append(ok("no verse text fabricated", body_has_verse is False))
        await d.shot(f"{SHOTS}/gvr-mic-503.png")

        # ---------------- Test 4: GVR garbage upload -> explicit decode failure
        print("\n[4] GVR — undecodable upload shows an explicit failure state")
        junk = base64.b64encode(b"this is definitely not audio" * 64).decode()
        await d.ev(f"({DROP_FILE_JS})('{junk}', 'garbage.wav')", await_promise=True)
        await d.wait(
            "document.getElementById('gvrStatusLine').textContent.indexOf('Could not decode') !== -1",
            desc="explicit decode-failure message",
        )
        status4 = await d.ev("document.getElementById('gvrStatusLine').textContent")
        submit_disabled = await d.ev("document.getElementById('submitBtn').disabled")
        results.append(ok("decode failure is explicit, not silent", "Could not decode" in status4, status4.strip()))
        results.append(ok("submit stays disabled for a bad clip", submit_disabled is True))
        await d.shot(f"{SHOTS}/gvr-decode-fail.png")

    print("\n===== E2E RESULT:", "ALL PASS" if all(results) else "FAILURES", "=====")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
