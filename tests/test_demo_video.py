"""Tests for the demo video add-on (DEMO ONLY — outside the SRS).

Two layers:

- the HTTP surface in ``demo/video/router.py``, exercised with a bare
  FastAPI app and a temporary jobs directory (no OpenCV, no worker);
- page guards for ``web/video.html``: no mockup strings, one <main>, the
  five result sections, and the demo banner.
"""

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from demo.video import jobs
from demo.video import router as video_router

PAGE = Path(__file__).resolve().parent.parent / "web" / "video.html"

MOCKUP_STRINGS = [
    "Inspect:", "SD-VideoNet", "WEBGPU", "WebGPU", "YOLOv9-PHONO",
    "COCO-ARCHIVAL", "Kalman", "NLP-SEMANTIC-V3", "Kaldi/PyTorch",
    "Open Philological License", "MOD-VID-702", "Mudrā", "Speaker",
    "Palm Leaf", "Auditor", "Correlate", "Re-encode", "42%",
    "lh3.googleusercontent", "FARNEBACK", "RIG_VEDA", "Saliency",
    "KF-01", "confidence",
]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "JOBS_DIR", tmp_path / "jobs")
    app = FastAPI()
    app.include_router(video_router.router)
    return TestClient(app)


@pytest.fixture()
def runtime_ok(monkeypatch):
    monkeypatch.setattr(jobs, "runtime_status", lambda: {
        "available": True, "python": "/tmp/python", "error": None,
        "versions": {"opencv": "4.14.0", "scenedetect": "0.6.7.1",
                     "imageio_ffmpeg": "0.6.0"},
    })


def _status(job_id, **overrides):
    doc = jobs.initial_status(job_id, "clip.mp4", 1024)
    doc.update(overrides)
    return doc


# --------------------------------------------------------------- config

def test_config_reports_hog_and_limits(client, runtime_ok):
    body = client.get("/demo/video/config").json()
    assert body["tracking"] == "hog"
    assert body["available"] is True
    assert body["limits"]["max_duration_s"] == 1800
    assert body["limits"]["max_upload_bytes"] == 512 * 1024 * 1024
    assert body["stages"] == ["probe", "scenes", "frames", "motion",
                              "track", "summary"]
    assert "outputs are not results" in body["banner"]


def test_config_reports_unavailable_honestly(client, monkeypatch):
    monkeypatch.setattr(jobs, "runtime_status", lambda: {
        "available": False, "python": "/tmp/python",
        "error": "not installed", "versions": {},
    })
    body = client.get("/demo/video/config").json()
    assert body["available"] is False
    assert body["tracking"] == "unavailable"
    assert "not installed" in body["runtime"]["error"]


# --------------------------------------------------------------- upload

def test_upload_rejects_wrong_extension(client, runtime_ok):
    response = client.post("/demo/video/upload",
                           files={"file": ("notes.txt", b"hello", "text/plain")})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsupported_type"


def test_upload_rejects_empty_file(client, runtime_ok):
    response = client.post("/demo/video/upload",
                           files={"file": ("clip.mp4", b"", "video/mp4")})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "empty_upload"


def test_upload_rejects_oversized(client, runtime_ok, monkeypatch):
    monkeypatch.setattr(video_router, "MAX_UPLOAD_BYTES", 1024)
    response = client.post("/demo/video/upload",
                           files={"file": ("clip.mp4", b"x" * 2048,
                                           "video/mp4")})
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "too_large"


def test_upload_queues_a_job(client, runtime_ok, monkeypatch, tmp_path):
    launched = []
    monkeypatch.setattr(jobs, "launch", lambda job: launched.append(job))

    response = client.post("/demo/video/upload",
                           files={"file": ("clip.mp4", b"\x00" * 4096,
                                           "video/mp4")})
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["result_url"].endswith("/result")

    job = jobs.job_dir(body["job_id"])
    assert (job / "source.mp4").stat().st_size == 4096
    status = json.loads((job / "status.json").read_text())
    assert status["status"] == "queued"
    assert status["source"]["filename"] == "clip.mp4"
    assert launched == [job]


# --------------------------------------------------------------- status

def test_unknown_job_is_404(client):
    response = client.get("/demo/video/jobs/20260101-000000-abcdef")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "job_not_found"


def test_malformed_job_id_is_404(client):
    response = client.get("/demo/video/jobs/not-a-job")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "job_not_found"


def test_result_before_done_is_409(client, tmp_path):
    job = jobs.job_dir("20260101-000000-abcdef")
    job.mkdir(parents=True)
    jobs.write_json(jobs.status_path(job),
                    _status("20260101-000000-abcdef"))
    response = client.get("/demo/video/jobs/20260101-000000-abcdef/result")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "not_ready"


def test_dead_worker_is_reported(client):
    job_id = "20260101-000000-abcdef"
    job = jobs.job_dir(job_id)
    job.mkdir(parents=True)
    doc = _status(job_id, status="running")
    doc["progress"]["elapsed_s"] = 12.0
    jobs.write_json(jobs.status_path(job), doc)

    body = client.get(f"/demo/video/jobs/{job_id}").json()
    assert body["status"] == "failed"
    assert body["error"]["code"] == "worker_exited"


# ------------------------------------------------------------ page guard

def test_page_has_no_mockup_strings():
    html = PAGE.read_text()
    found = [s for s in MOCKUP_STRINGS if s in html]
    assert found == []


def test_page_structure_and_banner():
    html = PAGE.read_text()
    assert html.count("<main") == 1
    for label in ("IMPORTANT FRAMES", "SCENE BOUNDARIES", "MOTION MAP",
                  "TRACKED OBJECTS", "SUMMARY"):
        assert label in html
    assert "DEMO — video analysis is an add-on outside the project's" in html
    assert "fixed bottom-0 left-0 right-0" in html
    assert 'id="fileInput"' in html and 'type="file"' in html
    assert "HOG + centroid fallback" in html


def test_page_binds_every_artifact_to_the_api():
    html = PAGE.read_text()
    for element in ("framesList", "scenesList", "motionImg", "trackVideo",
                    "tracksTable", "summaryVideo", "summaryLine"):
        assert f'id="{element}"' in html
    assert "tracks.video_url" in html
    assert "motion.map_url" in html
    assert "summary.video_url" in html


def test_index_page_wires_mod03_video():
    index_html = (PAGE.parent / "index.html").read_text()
    assert "MOD-03" in index_html
    assert "/video.html" in index_html
    assert "Video Analysis" in index_html


def test_sample_video_endpoint():
    import subprocess
    import sys

    code = (
        "from demo.server import api\n"
        "from fastapi.testclient import TestClient\n"
        "client = TestClient(api.app)\n"
        "res = client.get('/api/sample-video')\n"
        "assert res.status_code == 200\n"
        "assert res.headers['content-type'] == 'video/mp4'\n"
        "assert len(res.content) > 1000\n"
    )
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr


