"""Frame sampling and important-frame selection (DEMO ONLY).

One sequential pass decodes the video at a fixed analysis rate (default
4 fps) and computes, per sampled frame, a cheap quality pair:

- **sharpness** — variance of the Laplacian on a 192x108 grey copy
  (higher means crisper, less motion-blurred),
- **change** — mean absolute difference against the previous sampled frame
  (higher means something moved or the shot changed).

Important frames are then the highest-scoring samples per scene, spaced out
so a scene does not yield ten near-identical frames. Selected frames are
re-read by index only after selection, so memory stays flat on long videos.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

SMALL = (192, 108)
THUMB_WIDTH = 240


def probe(path) -> dict:
    """Container metadata via OpenCV. Raises RuntimeError if undecodable."""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        cap.release()
        raise RuntimeError("OpenCV could not open the file")
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        if fps <= 0 or width <= 0 or height <= 0:
            raise RuntimeError("no decodable video stream")
        duration = count / fps if count > 0 else 0.0
        return {
            "fps": round(fps, 3),
            "frame_count": count,
            "width": width,
            "height": height,
            "duration_s": round(duration, 3),
        }
    finally:
        cap.release()


def scan(path, *, sample_fps: float, max_frames: int,
         progress=None, on_frame=None):
    """Yield one record per sampled frame; ``on_frame(frame, t_s)`` sees each.

    Records carry ``index`` (native frame number), ``t_s``, ``sharpness``,
    ``change`` and ``score``. The frame array itself is only handed to
    ``on_frame`` and is not retained here.
    """
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        cap.release()
        raise RuntimeError("OpenCV could not open the file")
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        step = max(1, int(round(fps / max(sample_fps, 0.1))))
        prev_small = None
        index = 0
        taken = 0
        while taken < max_frames:
            if not cap.grab():
                break
            if index % step == 0:
                ok, frame = cap.retrieve()
                if ok and frame is not None:
                    small = cv2.resize(frame, SMALL,
                                       interpolation=cv2.INTER_AREA)
                    grey = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
                    sharpness = float(
                        cv2.Laplacian(grey, cv2.CV_64F).var())
                    change = (0.0 if prev_small is None else
                              float(np.mean(cv2.absdiff(small, prev_small))))
                    record = {
                        "index": index,
                        "t_s": round(index / fps, 3),
                        "sharpness": round(sharpness, 3),
                        "change": round(change, 3),
                        # Sharpness is heavy-tailed; log keeps one crisp
                        # frame from dominating every scene.
                        "score": round(float(np.log1p(sharpness))
                                       * (1.0 + change / 32.0), 5),
                    }
                    if on_frame is not None:
                        on_frame(frame, record["t_s"])
                    yield record
                    prev_small = small
                    taken += 1
                    if progress and total > 0:
                        progress(min(1.0, index / total),
                                 f"{record['t_s']:.1f}s / "
                                 f"{total / fps:.1f}s")
            index += 1
    finally:
        cap.release()


def select(records: list[dict], scenes: list[dict], *,
           max_frames: int = 32, per_scene: int = 3,
           min_gap_s: float = 0.6) -> list[dict]:
    """Pick important frames: strongest per scene, then best overall."""
    if not records:
        return []

    def scene_of(t: float) -> int:
        for scene in scenes:
            if scene["start_s"] <= t < scene["end_s"]:
                return scene["index"]
        return scenes[-1]["index"] if scenes else 0

    by_scene: dict[int, list[dict]] = {}
    for record in records:
        by_scene.setdefault(scene_of(record["t_s"]), []).append(record)

    chosen: list[dict] = []
    for scene_index in sorted(by_scene):
        picked: list[dict] = []
        for record in sorted(by_scene[scene_index],
                             key=lambda r: r["score"], reverse=True):
            if len(picked) >= per_scene:
                break
            if any(abs(record["t_s"] - p["t_s"]) < min_gap_s for p in picked):
                continue
            picked.append(record)
        for record in picked:
            chosen.append(dict(record, scene=scene_index))

    if len(chosen) > max_frames:
        chosen.sort(key=lambda r: r["score"], reverse=True)
        chosen = chosen[:max_frames]

    chosen.sort(key=lambda r: r["t_s"])
    for i, record in enumerate(chosen, start=1):
        record["number"] = i
        record["label"] = f"frame_{i:04d}"
    return chosen


def save(path, selections: list[dict], out_dir: Path,
         *, max_width: int = 960) -> list[dict]:
    """Write the selected frames (and thumbnails) as JPEGs, re-reading by index."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[dict] = []
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        cap.release()
        raise RuntimeError("OpenCV could not open the file")
    try:
        for record in selections:
            cap.set(cv2.CAP_PROP_POS_FRAMES, record["index"])
            ok, frame = cap.retrieve() if cap.grab() else (False, None)
            if not ok or frame is None:
                continue
            height, width = frame.shape[:2]
            if width > max_width:
                scale = max_width / width
                frame = cv2.resize(frame, (max_width, int(height * scale)),
                                   interpolation=cv2.INTER_AREA)
            full = out_dir / f"{record['label']}.jpg"
            thumb = out_dir / f"{record['label']}_thumb.jpg"
            cv2.imwrite(str(full), frame, [cv2.IMWRITE_JPEG_QUALITY, 88])
            th, tw = frame.shape[:2]
            tscale = min(1.0, THUMB_WIDTH / tw)
            small = cv2.resize(frame, (int(tw * tscale), int(th * tscale)),
                               interpolation=cv2.INTER_AREA)
            cv2.imwrite(str(thumb), small, [cv2.IMWRITE_JPEG_QUALITY, 82])
            written.append(dict(record, file=full.name, thumb=thumb.name,
                                width=int(tw), height=int(th)))
    finally:
        cap.release()
    return written
