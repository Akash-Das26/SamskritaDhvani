"""DEMO ONLY — video analysis add-on (outside the project's requirements).

Nothing here implements an SRS requirement, and nothing it produces is a
result. The page and every API response carry the banner in :data:`BANNER`.

The module is split so the heavy work happens in ``demo/.venv-video`` (a
separate environment with OpenCV, PySceneDetect and imageio-ffmpeg) while
the demo server itself keeps running in the project venv:

- :mod:`demo.video.jobs`      job directories, status files, the worker process
- :mod:`demo.video.pipeline`  the worker entry point (probe → … → summary)
- :mod:`demo.video.scenes`    scene boundaries (PySceneDetect ContentDetector)
- :mod:`demo.video.frames`    sampling pass + important-frame scoring
- :mod:`demo.video.motion`    motion map and per-second motion series
- :mod:`demo.video.track`     object tracking (OpenCV HOG + centroid fallback)
- :mod:`demo.video.summary`   short summary video (ffmpeg)
- :mod:`demo.video.router`    the HTTP surface mounted by ``demo/server.py``
"""

BANNER = ("DEMO — video analysis is an add-on outside the project's "
          "requirements; outputs are not results.")

# Hard limits, checked before any analysis starts.
MAX_DURATION_S = 30 * 60          # 30 minutes, as agreed
MAX_UPLOAD_BYTES = 512 * 1024 * 1024   # 512 MiB
MAX_SAMPLED_FRAMES = 7200         # 4 fps × 30 min
SAMPLE_FPS = 4.0                  # frames/motion analysis rate
TRACK_FPS_MAX = 2.0               # tracking detection rate cap
TRACK_MAX_DETECTIONS = 900        # HOG is ~0.1-0.4 s/frame; keep it bounded
MAX_SUMMARY_S = 90.0              # summary length cap

ALLOWED_EXTENSIONS = (".mp4", ".m4v", ".mov", ".mkv", ".webm", ".avi")

# Names reported by /config and by every progress payload.
STAGES = ["probe", "scenes", "frames", "motion", "track", "summary"]

BACKEND_NOTE = ("tracking: OpenCV HOG person detector + centroid association "
                "(no model download, no deep-learning tracker)")
