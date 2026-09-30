"""Phase 5 render check: drive headless Chrome over the DevTools
protocol and verify each wired screen renders its live API binding.

Requires: google-chrome, websockets (already in the venv via
uvicorn[standard]). Usage: .venv/bin/python /tmp/e2e_render_check.py
"""
import asyncio
import base64
import json
import subprocess
import time
import urllib.request

from websockets.client import connect

BASE = "http://127.0.0.1:8000"
PORT = 9333


async def rpc(ws, msg_id, method, params=None, timeout=30):
    await ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
    deadline = time.time() + timeout
    while time.time() < deadline:
        raw = json.loads(await asyncio.wait_for(ws.recv(), timeout=deadline - time.time()))
        if raw.get("id") == msg_id:
            if "error" in raw:
                raise RuntimeError(f"{method}: {raw['error']}")
            return raw.get("result", {})
    raise TimeoutError(method)


async def wait_console_idle(ws, seconds=4.0):
    """Collect console/errors for a wall-clock window after load."""
    events = []
    try:
        while True:
            raw = json.loads(await asyncio.wait_for(ws.recv(), timeout=seconds))
            if raw.get("method") in ("Runtime.consoleAPICalled", "Runtime.exceptionThrown", "Log.entryAdded"):
                events.append(raw)
    except asyncio.TimeoutError:
        pass
    return events


def page_target_ws_url():
    """Resolve the first page target's webSocketDebuggerUrl via /json/list."""
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list") as r:
        targets = json.load(r)
    pages = [t for t in targets if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]
    if not pages:
        raise RuntimeError(f"no page targets on :{PORT}: {targets}")
    return pages[0]["webSocketDebuggerUrl"]


async def wait_until(ws, expr, timeout=25.0):
    """Poll an evaluate expression until it returns true."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = await rpc(ws, 77, "Runtime.evaluate",
                          {"expression": expr, "returnByValue": True}, timeout=5)
            if r.get("result", {}).get("value") is True:
                return True
        except (TimeoutError, RuntimeError):
            pass
        await asyncio.sleep(0.3)
    return False


SETTLE = {
    "index": "!!document.querySelector('header nav a[href=\"/spd.html\"]')",
    "": "!!document.querySelector('header nav a[href=\"/spd.html\"]')",
    "spd.html": "document.querySelectorAll('#wordList button[data-wid]').length > 0",
    "gvr.html": "window.SD && document.getElementById('gvrStatusLine').textContent.indexOf('no submission') !== -1",
    "status.html": "document.getElementById('statWordCount').textContent !== '—' || document.getElementById('statWordMeta').textContent.indexOf('unavailable') !== -1",
}


async def render(page_path):
    url = BASE + "/" + page_path if page_path else BASE + "/"
    key = page_path.replace(".html", "") if page_path.endswith(".html") else page_path or "index"
    async with connect(page_target_ws_url()) as ws:
        await rpc(ws, 1, "Runtime.enable")
        await rpc(ws, 2, "Page.enable")
        await rpc(ws, 3, "Page.navigate", {"url": url})
        # Wait until THIS tab has committed the navigation and finished
        # parsing — do not trust readyState before the URL matches.
        committed = await wait_until(
            ws,
            f"location.href === {json.dumps(url)} && document.readyState !== 'loading'",
            timeout=30,
        )
        if not committed:
            raise TimeoutError(f"navigation never committed for {url}")
        # Wait until the page's async bindings actually rendered.
        await wait_until(ws, SETTLE.get(key, "true"), timeout=25)
        errors = await wait_console_idle(ws, 3.0)
        result = await rpc(ws, 4, "Runtime.evaluate", {
            "expression": "document.documentElement.outerHTML",
            "returnByValue": True,
        })
        dom = result["result"]["value"]
        return dom, errors


def check(name, dom, errors, assertions):
    print(f"\n===== {name} =====")
    hard = [
        e for e in errors
        if e.get("method") == "Runtime.exceptionThrown"
        or (e.get("method") == "Log.entryAdded" and e["params"]["entry"].get("level") == "error")
    ]
    print(f"JS errors: {len(hard)}")
    for e in hard:
        entry = e["params"].get("exceptionDetails") or e["params"]["entry"]
        print("  !", json.dumps(entry, default=str)[:300])
    ok = True
    for label, predicate in assertions:
        passed = predicate(dom)
        ok = ok and passed
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}")
    return ok and not hard


async def main():
    checks = [
        ("", [
            ("nav rewired to /spd.html", lambda d: 'href="/spd.html"' in d),
            ("nav rewired to /gvr.html", lambda d: 'href="/gvr.html"' in d),
            ("nav rewired to /status.html", lambda d: 'href="/status.html"' in d),
            ("no fabricated 'Kaldi/PyTorch' telemetry",
             lambda d: "Kaldi" not in d and "PyTorch" not in d),
            ("no fabricated model name", lambda d: "SD-PhonoNet" not in d),
            ("no fabricated 48.0 kHz card", lambda d: "48.0 kHz" not in d),
            ("no fabricated p-values", lambda d: "p = 0.94" not in d),
        ]),
        ("spd.html", [
            ("word list rendered from /api/words", lambda d: d.count("data-wid=") >= 27),
            ("meta shows live source", lambda d: "live from /api/words" in d),
            ("kṛṣṇa offered in the picker", lambda d: "kṛṣṇa" in d),
            ("selected axis shown", lambda d: "difficulty axis: consonant-cluster" in d),
            ("reference playback disabled honestly",
             lambda d: "not yet ear-verified" in d),
            ("no pre-filled fake scores (78%/84%/71%/91%)",
             lambda d: ">78%<" not in d and ">84%<" not in d and ">71%<" not in d and ">91%<" not in d),
            ("no fabricated phoneme tic labels",
             lambda d: ">/k/<" not in d and ">/ṣ/<" not in d),
            ("submit starts disabled", lambda d: 'id="submitBtn" disabled' in d),
        ]),
        ("gvr.html", [
            ("match card hidden until a real result",
             lambda d: 'id="gvrResult"' in d and 'hidden' in
             d.split('id="gvrResult"')[1][:250]),
            ("fallback card hidden until a real response",
             lambda d: 'id="gvrFallback"' in d and 'hidden' in
             d.split('id="gvrFallback"')[1][:250]),
            ("no fabricated 94.2% confidence", lambda d: "94.2%" not in d),
            ("no fabricated verse text", lambda d: "patraṁ puṣpaṁ" not in d),
            ("no fabricated Viterbi count", lambda d: "1,420" not in d),
            ("no fabricated timer value", lambda d: "00:18.4" not in d),
            ("honest 'not yet populated' scope line",
             lambda d: "not yet populated" in d),
        ]),
        ("status.html", [
            ("live word count bound", lambda d: 'id="statWordCount">27<' in d),
            ("axis breakdown listed", lambda d: "retroflex-dental" in d),
            ("honest empty verse registry", lambda d: "no entries" in d),
            ("honest sweep-unavailable state",
             lambda d: "NOT ON THIS MACHINE" in d),
            ("honest pending reference audio", lambda d: "PENDING" in d),
            ("audit rows built live", lambda d: "Reading /api/status" not in d),
            ("no fabricated 142-file sweep", lambda d: "142" not in
             d.split('id="sweepFiles"')[1][:120]),
            ("no fabricated SHA commit", lambda d: "rev-2025.04" not in d),
            ("no fabricated checksums",
             lambda d: "e3b0c44298fc1c149afbf4c8996fb924" not in d),
        ]),
    ]

    all_ok = True
    for name, assertions in checks:
        dom, errors = await render(name)
        all_ok = check(name, dom, errors, assertions) and all_ok
    print("\n===== RESULT:", "ALL SCREENS PASS" if all_ok else "FAILURES PRESENT", "=====")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
