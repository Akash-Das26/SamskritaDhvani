"""Object tracking for the demo video add-on (DEMO ONLY).

Backend: OpenCV's built-in HOG + linear-SVM person detector
(``HOGDescriptor_getDefaultPeopleDetector``), one detection pass every
``1 / track_fps`` seconds, with a simple centroid association tracker
between passes. No model file is downloaded and no deep-learning tracker
is used — this is the fallback agreed for the demo, and ``/config``
reports ``tracking: "hog"`` accordingly.

What that means for quality, stated plainly: HOG only fires on upright
human silhouettes at a reasonable size; it misses seated, small, occluded
or unusual poses, produces false positives on some textures, and the
centroid tracker has no appearance model, so two people crossing can swap
identities. The track list is indicative motion, not an identification.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import cv2
import numpy as np

from demo.video.summary import ffmpeg_exe


def _hog() -> "cv2.HOGDescriptor":
    hog = cv2.HOGDescriptor()
    hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    return hog


def detect_and_track(path, *, duration_s: float, max_detect_s: float = 2.0,
                     max_detections: int = 900, job_dir: Path | None = None,
                     progress=None) -> dict:
    """Run detection over the clip and associate boxes into tracks.

    With ``job_dir`` set, also renders ``tracked.mp4``: the source at 12 fps
    with each detection drawn as a box labelled "person".
    """
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        cap.release()
        raise RuntimeError("OpenCV could not open the file")

    try:
        native_fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
        track_fps = max_detect_s
        if duration_s > 0:
            track_fps = min(max_detect_s, max(0.5, max_detections / duration_s))
        step = max(1, int(np.ceil(native_fps / max(track_fps, 0.1))))

        detector = _hog()
        tracks: list[dict] = []
        active: list[dict] = []
        detection_log: list[tuple[float, list[tuple]]] = []
        index = 0
        detections = 0
        processed = 0
        last_t = 0.0

        while True:
            if not cap.grab():
                break
            if index % step == 0:
                ok, frame = cap.retrieve()
                if ok and frame is not None:
                    t_s = index / native_fps
                    last_t = t_s
                    height, width = frame.shape[:2]
                    if width > 640:
                        scale = 640 / width
                        frame = cv2.resize(frame, (640, int(height * scale)),
                                           interpolation=cv2.INTER_AREA)
                        height, width = frame.shape[:2]
                    grey = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    rects, weights = detector.detectMultiScale(
                        grey, winStride=(8, 8), padding=(8, 8), scale=1.05)
                    boxes = []
                    for (x, y, w, h), weight in zip(rects, weights):
                        if float(weight) < 0.5:
                            continue
                        boxes.append((float(x), float(y), float(w), float(h),
                                      float(weight)))
                    detections += len(boxes)
                    processed += 1
                    if boxes:
                        detection_log.append((t_s, [
                            (x / width, y / height, w / width, h / height)
                            for x, y, w, h, _weight in boxes]))
                    _associate(active, tracks, boxes, t_s, width, height)
                    if progress and duration_s > 0:
                        progress(min(1.0, t_s / duration_s),
                                 f"{t_s:.1f}s / {duration_s:.1f}s · "
                                 f"{len(tracks)} track(s)")
            index += 1
    finally:
        cap.release()

    kept = [t for t in tracks if t["frames"] >= 2]
    for number, track in enumerate(sorted(kept, key=lambda t: t["first_s"]),
                                   start=1):
        track["id"] = number

    info: dict = {
        "backend": "hog",
        "detector": "OpenCV HOG default people detector",
        "tracker": "centroid association (no appearance model)",
        "track_fps": round(1.0 / (step / native_fps), 3),
        "detections": detections,
        "sampled_frames": processed,
        "count": len(kept),
        "tracks": kept,
        "note": ("HOG fires on upright human silhouettes only; no identity, "
                 "and centroids can swap when people cross."),
    }

    if job_dir is not None:
        info.update(_render_tracked(job_dir, path, detection_log))
        if progress:
            progress(1.0, f"{len(kept)} track(s) · tracked.mp4")
    elif progress:
        progress(1.0, f"{len(kept)} track(s)")
    return info


def _render_tracked(job_dir: Path, source, detection_log: list[tuple],
                    out_fps: float = 12.0) -> dict:
    """Draw the detections onto a 12 fps copy of the source (tracked.mp4)."""
    cap = cv2.VideoCapture(str(source))
    if not cap.isOpened():
        cap.release()
        raise RuntimeError("OpenCV could not open the file")
    try:
        native_fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        step = max(1, int(round(native_fps / out_fps)))
        raw = job_dir / "parts" / "tracked_raw.mp4"
        raw.parent.mkdir(parents=True, exist_ok=True)
        writer = cv2.VideoWriter(str(raw), cv2.VideoWriter_fourcc(*"mp4v"),
                                 native_fps / step, (width, height))
        index = 0
        cursor = 0
        current: list[tuple] = []
        last_seen = -99.0
        while True:
            if not cap.grab():
                break
            if index % step == 0:
                ok, frame = cap.retrieve()
                if ok and frame is not None:
                    t_s = index / native_fps
                    while (cursor < len(detection_log)
                           and detection_log[cursor][0] <= t_s):
                        current = detection_log[cursor][1]
                        last_seen = detection_log[cursor][0]
                        cursor += 1
                    if current and t_s - last_seen <= 1.0:
                        _draw(frame, current, width, height)
                    writer.write(frame)
            index += 1
        writer.release()
    finally:
        cap.release()

    out = job_dir / "tracked.mp4"
    proc = subprocess.run(
        [ffmpeg_exe(), "-v", "error", "-y", "-i", str(raw), "-an",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)],
        capture_output=True, text=True)
    if proc.returncode != 0 or not out.exists() or out.stat().st_size == 0:
        raise RuntimeError("ffmpeg could not encode tracked.mp4: "
                           f"{(proc.stderr or '').strip()[-300:] or 'no output'}")
    return {
        "video": out.name,
        "video_bytes": out.stat().st_size,
        "video_fps": round(native_fps / step, 3),
        "video_label": "HOG + centroid fallback",
    }


def _draw(frame, boxes: list[tuple], width: int, height: int) -> None:
    for (x, y, w, h) in boxes:
        x0, y0 = int(x * width), int(y * height)
        x1, y1 = x0 + int(w * width), y0 + int(h * height)
        cv2.rectangle(frame, (x0, y0), (x1, y1), (32, 32, 214), 2)
        cv2.putText(frame, "person", (x0 + 3, max(12, y0 - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (32, 32, 214), 1,
                    cv2.LINE_AA)


def _associate(active: list[dict], tracks: list[dict], boxes: list[tuple],
               t_s: float, width: int, height: int) -> None:
    """Greedy nearest-centroid matching; unmatched boxes start new tracks."""
    max_distance = 0.18 * float(np.hypot(width, height))
    taken_boxes: set[int] = set()

    for track in sorted(active, key=lambda tr: tr["last_t"], reverse=True):
        cx, cy = track["centroid"]
        best = None
        best_distance = max_distance
        for i, (x, y, w, h, _weight) in enumerate(boxes):
            if i in taken_boxes:
                continue
            bx, by = x + w / 2.0, y + h / 2.0
            distance = float(np.hypot(bx - cx, by - cy))
            if distance < best_distance:
                best, best_distance = i, distance
        if best is None:
            continue
        taken_boxes.add(best)
        x, y, w, h, weight = boxes[best]
        track["centroid"] = (x + w / 2.0, y + h / 2.0)
        track["last_t"] = t_s
        track["last_s"] = round(t_s, 3)
        track["frames"] += 1
        track["points"].append([
            round(t_s, 3),
            round((x + w / 2.0) / width, 4),
            round((y + h / 2.0) / height, 4),
        ])
        track["boxes"].append([
            round(x / width, 4), round(y / height, 4),
            round(w / width, 4), round(h / height, 4),
        ])
        track["confidence"] = round(
            float(np.mean([track["confidence"], weight])), 3)

    for i, (x, y, w, h, weight) in enumerate(boxes):
        if i in taken_boxes:
            continue
        track = {
            "id": 0,
            "first_s": round(t_s, 3),
            "last_s": round(t_s, 3),
            "frames": 1,
            "confidence": round(weight, 3),
            "centroid": (x + w / 2.0, y + h / 2.0),
            "last_t": t_s,
            "points": [[round(t_s, 3), round((x + w / 2.0) / width, 4),
                        round((y + h / 2.0) / height, 4)]],
            "boxes": [[round(x / width, 4), round(y / height, 4),
                       round(w / width, 4), round(h / height, 4)]],
        }
        tracks.append(track)
        active.append(track)

    # Retire tracks that have not been seen for two seconds.
    active[:] = [tr for tr in active if t_s - tr["last_t"] <= 2.0]
