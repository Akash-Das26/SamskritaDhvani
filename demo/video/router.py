"""HTTP surface of the demo video add-on (DEMO ONLY, not an SRS feature).

Mounted by ``demo/server.py``. This module deliberately imports nothing
from OpenCV or PySceneDetect: the server keeps running in the project
venv, and the analysis happens in the separate ``demo/.venv-video``
environment as a background worker. Every response carries the demo
banner; every failure uses the same JSON shape::

    {"status": "failed", "banner": "...", "error": {"code": ..., "detail": ...}}

Error codes: ``video_unavailable`` (503), ``unsupported_type`` (400),
``empty_upload`` (400), ``too_large`` (413), ``too_long`` (422, reported by
the worker), ``not_video`` (422), ``job_not_found`` (404), ``not_ready``
(409), ``worker_exited`` (500), ``pipeline_error`` (500).
"""

from __future__ import annotations

import re

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from demo.video import (
    ALLOWED_EXTENSIONS,
    BANNER,
    MAX_DURATION_S,
    MAX_SUMMARY_S,
    MAX_UPLOAD_BYTES,
    SAMPLE_FPS,
    STAGES,
)
from demo.video import jobs

router = APIRouter(prefix="/demo/video", tags=["demo-video"])

_CHUNK = 1024 * 1024
_ARTIFACT_PATTERNS = (
    re.compile(r"^frames/frame_\d{4}(_thumb)?\.jpg$"),
    re.compile(r"^motion_map\.png$"),
    re.compile(r"^summary\.mp4$"),
    re.compile(r"^tracked\.mp4$"),
)


def _error(status_code: int, code: str, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"status": "failed", "banner": BANNER,
                 "error": {"code": code, "detail": detail}},
    )


def _public(doc: dict) -> dict:
    """Status document plus the URLs the page needs."""
    job_id = doc["job_id"]
    doc = dict(doc)
    doc["banner"] = BANNER
    doc["status_url"] = f"/demo/video/jobs/{job_id}"
    doc["result_url"] = (f"/demo/video/jobs/{job_id}/result"
                         if doc.get("status") == "done" else None)
    return doc


def _job_status(job_id: str):
    """(job, status doc) or an error response."""
    try:
        job = jobs.job_dir(job_id)
    except ValueError:
        return None, _error(404, "job_not_found", "Malformed job id.")
    doc = jobs.read_json(jobs.status_path(job))
    if doc is None:
        return None, _error(404, "job_not_found",
                            f"No demo video job '{job_id}'.")
    if doc.get("status") in ("queued", "running") and \
            doc.get("progress", {}).get("elapsed_s", 0) >= 2 and \
            not jobs.worker_alive(job):
        doc["status"] = "failed"
        doc["error"] = {
            "code": "worker_exited",
            "detail": ("The analysis worker stopped without reporting. "
                       "Check demo/tmp/video/" + job_id + "/worker.log. "
                       f"{(jobs.log_tail(job) or '')[-400:]}"),
        }
    return job, doc


# --------------------------------------------------------------- endpoints

@router.get("/config")
def video_config() -> dict:
    runtime = jobs.runtime_status()
    return {
        "available": bool(runtime["available"]),
        "banner": BANNER,
        "tracking": "hog" if runtime["available"] else "unavailable",
        "backend": ("OpenCV HOG person detector + centroid association; "
                    "no model download, no deep-learning tracker"),
        "limits": {
            "max_duration_s": MAX_DURATION_S,
            "max_upload_bytes": MAX_UPLOAD_BYTES,
            "max_upload_mb": MAX_UPLOAD_BYTES // (1024 * 1024),
            "sample_fps": SAMPLE_FPS,
            "summary_max_s": MAX_SUMMARY_S,
            "extensions": list(ALLOWED_EXTENSIONS),
        },
        "stages": STAGES,
        "runtime": {
            "python": runtime["python"],
            "versions": runtime["versions"],
            "error": runtime["error"],
        },
    }


@router.post("/upload", status_code=202)
async def upload(file: UploadFile = File(...)):
    runtime = jobs.runtime_status()
    if not runtime["available"]:
        return _error(503, "video_unavailable",
                      "Video analysis is not installed. Create "
                      "demo/.venv-video from demo/requirements-video.txt "
                      f"({runtime['error']}).")

    name = (file.filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not name:
        return _error(400, "empty_upload", "No file was sent.")
    suffix = ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""
    if suffix not in ALLOWED_EXTENSIONS:
        return _error(400, "unsupported_type",
                      f"'{suffix or name}' is not one of "
                      f"{', '.join(ALLOWED_EXTENSIONS)}.")

    job_id = jobs.new_job_id()
    job = jobs.job_dir(job_id)
    job.mkdir(parents=True, exist_ok=True)
    target = job / f"source{suffix}"

    written = 0
    try:
        with target.open("wb") as handle:
            while True:
                chunk = await file.read(_CHUNK)
                if not chunk:
                    break
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    raise OverflowError
                handle.write(chunk)
    except OverflowError:
        target.unlink(missing_ok=True)
        return _error(413, "too_large",
                      f"Upload exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    except Exception as exc:  # noqa: BLE001 — surface a clean JSON failure
        target.unlink(missing_ok=True)
        return _error(500, "upload_failed", f"Could not store the upload: {exc}")
    finally:
        await file.close()

    if written == 0:
        target.unlink(missing_ok=True)
        return _error(400, "empty_upload", "The uploaded file was empty.")

    status = jobs.initial_status(job_id, name, written)
    jobs.write_json(jobs.status_path(job), status)
    try:
        jobs.launch(job)
    except Exception as exc:  # noqa: BLE001 — the job must not hang in queued
        status["status"] = "failed"
        status["error"] = {"code": "worker_start_failed",
                           "detail": f"Could not start the worker: {exc}"}
        jobs.write_json(jobs.status_path(job), status)
        return _error(500, "worker_start_failed", status["error"]["detail"])

    return {
        "job_id": job_id,
        "status": "queued",
        "banner": BANNER,
        **{k: status[k] for k in ("progress", "source")},
        "status_url": f"/demo/video/jobs/{job_id}",
        "result_url": f"/demo/video/jobs/{job_id}/result",
    }


@router.get("/jobs/{job_id}")
def job_status(job_id: str):
    job, doc = _job_status(job_id)
    if job is None:
        return doc
    return _public(doc)


@router.get("/jobs/{job_id}/result")
def job_result(job_id: str):
    job, doc = _job_status(job_id)
    if job is None:
        return doc
    status = doc.get("status")
    if status != "done":
        if status == "failed":
            return _error(422, doc["error"]["code"], doc["error"]["detail"])
        return _error(409, "not_ready",
                      f"Job is {status}; progress "
                      f"{doc.get('progress', {}).get('pct', 0)}%.")
    result = jobs.read_json(jobs.result_path(job))
    if result is None:
        return _error(500, "pipeline_error",
                      "The worker reported done but result.json is missing.")

    base = f"/demo/video/jobs/{job_id}/files/"
    for frame in result.get("frames", []):
        frame["url"] = base + "frames/" + frame["file"]
        frame["thumb_url"] = base + "frames/" + frame["thumb"]
    for scene in result.get("scenes", []):
        scene["key_frame_url"] = (base + "frames/" + scene["key_frame"]
                                  if scene.get("key_frame") else None)
        scene["key_thumb_url"] = (base + "frames/" + scene["key_thumb"]
                                  if scene.get("key_thumb") else None)
    result.setdefault("motion", {})["map_url"] = base + "motion_map.png"
    result.setdefault("summary", {})["video_url"] = base + "summary.mp4"
    if result.get("tracks", {}).get("video"):
        result["tracks"]["video_url"] = base + "tracked.mp4"
    result["banner"] = BANNER
    return result


@router.get("/jobs/{job_id}/files/{name:path}")
def job_file(job_id: str, name: str):
    job, doc = _job_status(job_id)
    if job is None:
        return doc
    if doc.get("status") != "done":
        return _error(409, "not_ready", "Artifacts appear when the job is done.")
    if not any(pattern.match(name) for pattern in _ARTIFACT_PATTERNS):
        return _error(404, "job_not_found", f"No artifact '{name}'.")
    path = (job / name).resolve()
    try:
        path.relative_to(job.resolve())
    except ValueError:
        return _error(404, "job_not_found", f"No artifact '{name}'.")
    if not path.is_file():
        return _error(404, "job_not_found", f"No artifact '{name}'.")
    media = {".jpg": "image/jpeg", ".png": "image/png",
             ".mp4": "video/mp4"}.get(path.suffix, "application/octet-stream")
    return FileResponse(path, media_type=media)
