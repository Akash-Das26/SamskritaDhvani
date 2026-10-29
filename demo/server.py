"""Demo server: the real API, with demo-only reference data and calibration.

The demo needs two things ``samskrita_dhvani.api`` does not have on this
machine: reference clips (``data/spd/reference_words/`` is empty) and a
measured D₀ (``data/spd/calibration.json`` does not exist). Neither may
be created under ``data/`` for a demo, so this module points the *same*
API at ``demo/data/`` and adds the missing reference-audio route.

What it changes, and nothing else:

- ``api.SPD_REFERENCE_ROOT`` → ``demo/data/reference_words``
- the score route's calibration lookup → ``demo/data/calibration.json``
  (still ``spd_scorer.load_calibration``; still the real D2 scorer)
- one route, ``GET /api/reference-audio/<file>``, which the API
  advertises but does not define
- the static ``/`` mount is re-registered last so that route resolves

The UI is the existing ``web/`` tree, unchanged in layout; the demo
overlay (comparison strip + banner) is ``web/demo/comparison.js``.

Run::

    python -m demo.server            # http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse

from demo.video.router import router as video_router
from samskrita_dhvani import api
from samskrita_dhvani.spd_scorer import load_calibration as _load_calibration

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def demo_data_root() -> Path:
    """The active demo corpus: ``DEMO_DATA_ROOT`` or ``demo/data``.

    The demo keeps two corpora side by side — the copied TTS references
    in ``demo/data/`` and the owner's own recordings in ``demo/data_own/``.
    One variable switches between them; nothing here can point at
    ``data/`` or ``corpus/`` unless the caller asks for it explicitly.
    """
    raw = os.environ.get("DEMO_DATA_ROOT")
    root = Path(raw).expanduser() if raw else PROJECT_ROOT / "demo" / "data"
    if not root.is_absolute():
        root = PROJECT_ROOT / root
    return root.resolve()


DEMO_DATA = demo_data_root()
REFERENCE_ROOT = DEMO_DATA / "reference_words"
CALIBRATION_PATH = DEMO_DATA / "calibration.json"

BANNER = ("DEMO — references not ear-verified, calibration provisional; "
          "not a result.")


# ------------------------------------------------------------------ wiring

api.SPD_REFERENCE_ROOT = REFERENCE_ROOT
api.load_calibration = lambda word_id: _load_calibration(  # type: ignore[assignment]
    word_id, CALIBRATION_PATH
)

# The API registers its static mount at import time; anything added
# afterwards would sit behind it and 404. Move the mount to the end.
_routes = api.app.router.routes
_web_mount = next((r for r in _routes if getattr(r, "name", None) == "web"), None)
if _web_mount is not None:
    _routes.remove(_web_mount)


@api.app.get("/api/reference-audio/{name}")
def demo_reference_audio(name: str) -> FileResponse:
    """Serve a demo reference clip (the route the API's URLs point at)."""
    safe = Path(name).name
    p = REFERENCE_ROOT / safe
    if not p.is_file() or p.stat().st_size == 0:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "reference_unavailable",
                "detail": (
                    f"No demo reference clip for '{safe}'. The demo covers "
                    "kRSNa, yoga and zAnti only; the rest of the 27-word "
                    "list has no ear-verified reference."
                ),
            },
        )
    return FileResponse(p, media_type="audio/wav")


# DEMO add-on, outside the SRS: the video tab's API (demo/video/).
api.app.include_router(video_router)


if _web_mount is not None:
    _routes.append(_web_mount)


# ------------------------------------------------------------- entrypoint

def main(argv: list[str] | None = None) -> int:
    import uvicorn

    parser = argparse.ArgumentParser(
        prog="python -m demo.server",
        description="Run the SamskritaDhvani demo API (real D2 scorer, "
                    "provisional demo data).",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)

    refs = sorted(p.stem for p in REFERENCE_ROOT.glob("*.wav")) \
        if REFERENCE_ROOT.is_dir() else []
    calib_words: list[str] = []
    if CALIBRATION_PATH.is_file():
        calib_words = sorted(
            json.loads(CALIBRATION_PATH.read_text(encoding="utf-8"))
            .get("words", {})
        )
    print(f"demo server → http://{args.host}:{args.port}", flush=True)
    print(f"  data root: {DEMO_DATA}", flush=True)
    print(f"  reference words: {', '.join(refs) or '(none — run python -m demo.prepare_demo_data)'}",
          flush=True)
    print(f"  provisional calibration: {', '.join(calib_words) or '(none — run python -m demo.build_demo_calibration)'}",
          flush=True)
    print(f"  {BANNER}", flush=True)
    uvicorn.run(api.app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
