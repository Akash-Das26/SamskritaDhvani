"""Job bookkeeping for the demo video add-on (DEMO ONLY, not an SRS feature).

A job is a directory under ``demo/tmp/video/`` holding the uploaded source,
a ``status.json`` the worker rewrites as it progresses, and — when the
worker finishes — ``result.json`` plus its artifacts. The demo server only
ever reads those files; it never imports OpenCV itself, because the video
dependencies live in the separate ``demo/.venv-video`` environment.

Nothing here deletes anything, and nothing is written outside
``demo/tmp/video/``.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
JOBS_DIR = PROJECT_ROOT / "demo" / "tmp" / "video"

JOB_ID_RE = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{6}$")
WORKER_MODULE = "demo.video.pipeline"

_runtime_cache: dict[str, object] = {}
_procs: dict[str, subprocess.Popen] = {}


def video_python() -> Path:
    """Interpreter of the separate video environment (override with env)."""
    raw = os.environ.get("DEMO_VIDEO_PYTHON")
    if raw:
        return Path(raw).expanduser()
    venv = PROJECT_ROOT / "demo" / ".venv-video"
    if sys.platform.startswith("win"):
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def runtime_status() -> dict:
    """``{"available": bool, "python": str, "error": str|None, "versions"}``.

    Cached: the answer only changes when the environment is (re)installed.
    """
    if "status" in _runtime_cache:
        return _runtime_cache["status"]  # type: ignore[return-value]

    py = video_python()
    result: dict = {"available": False, "python": str(py), "error": None,
                    "versions": {}}
    if not py.exists():
        result["error"] = (f"video environment not found at {py} — create it "
                           "with demo/requirements-video.txt")
    else:
        code = ("import json, cv2, scenedetect, imageio_ffmpeg;"
                "print(json.dumps({'opencv': cv2.__version__,"
                "'scenedetect': scenedetect.__version__,"
                "'imageio_ffmpeg': imageio_ffmpeg.__version__}))")
        try:
            proc = subprocess.run([str(py), "-c", code],
                                  capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired) as exc:
            result["error"] = f"video environment did not start: {exc}"
        else:
            if proc.returncode == 0:
                try:
                    result["versions"] = json.loads(proc.stdout.strip() or "{}")
                except json.JSONDecodeError:
                    result["versions"] = {}
                result["available"] = True
            else:
                tail = (proc.stderr or "").strip().splitlines()[-1:]
                result["error"] = ("video environment cannot import its "
                                   "packages" + (f": {tail[0]}" if tail else ""))

    _runtime_cache["status"] = result
    return result


# ------------------------------------------------------------- job storage

def new_job_id() -> str:
    return time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]


def job_dir(job_id: str) -> Path:
    if not JOB_ID_RE.match(job_id):
        raise ValueError("malformed job id")
    return JOBS_DIR / job_id


def status_path(job: Path) -> Path:
    return job / "status.json"


def result_path(job: Path) -> Path:
    return job / "result.json"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def write_json(path: Path, data: dict) -> None:
    """Atomic write: a reader never sees a half-written status file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=False))
    os.replace(tmp, path)


def read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def initial_status(job_id: str, filename: str, size_bytes: int) -> dict:
    return {
        "job_id": job_id,
        "status": "queued",
        "progress": {
            "stage": "queued",
            "stage_index": -1,
            "stages": ["probe", "scenes", "frames", "motion", "track",
                       "summary"],
            "pct": 0,
            "detail": "waiting for the worker",
            "elapsed_s": 0.0,
        },
        "source": {"filename": filename, "bytes": size_bytes},
        "error": None,
        "created_at": _now(),
        "updated_at": _now(),
    }


def launch(job: Path) -> subprocess.Popen:
    """Start the worker in the video environment; progress goes to status.json."""
    py = video_python()
    log = open(job / "worker.log", "w", encoding="utf-8")  # noqa: SIM115
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PROJECT_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONUNBUFFERED"] = "1"
    proc = subprocess.Popen(
        [str(py), "-m", WORKER_MODULE, "--job", str(job)],
        cwd=str(PROJECT_ROOT), env=env, stdout=log, stderr=subprocess.STDOUT,
    )
    log.close()
    _procs[job.name] = proc
    (job / "worker.pid").write_text(str(proc.pid))
    return proc


def worker_alive(job: Path) -> bool:
    """Whether the worker is still running.

    The live ``Popen`` handle is authoritative (it reaps the child and
    knows its exit status); the pid file only covers a server restart.
    """
    proc = _procs.get(job.name)
    if proc is not None:
        return proc.poll() is None
    try:
        pid = int((job / "worker.pid").read_text().strip())
    except (OSError, ValueError):
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def log_tail(job: Path, limit: int = 1200) -> str:
    try:
        text = (job / "worker.log").read_text(errors="replace")
    except OSError:
        return ""
    return text[-limit:].strip()
