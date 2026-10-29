"""Scene boundaries for the demo video add-on (DEMO ONLY).

Uses PySceneDetect's ``ContentDetector``: each frame is converted to HSV,
the mean absolute difference of hue/saturation/value against the previous
frame is computed, and a cut is declared where that content value crosses
a threshold. No model and no training data — a classic shot-cut detector.

Output per scene: index, start/end seconds, length, and the peak content
value inside the scene (its cut strength).
"""

from __future__ import annotations

from typing import Callable

ProgressFn = Callable[[float, str], None]


def _metric_value(metric) -> float:
    """PySceneDetect's metric is a float in some versions, an object in others."""
    if isinstance(metric, (int, float)):
        return float(metric)
    for attr in ("content_val", "value"):
        value = getattr(metric, attr, None)
        if isinstance(value, (int, float)):
            return float(value)
    return 0.0


def _cut_strength(manager, start_frame: int) -> float:
    """The content value at a scene's first frame — i.e. its cut strength."""
    stats = getattr(manager, "stats_manager", None)
    if stats is None:
        return 0.0
    try:
        values = stats.get_metrics(start_frame, ["content_val"])
    except Exception:  # noqa: BLE001 — metrics are a nicety, never a failure
        return 0.0
    return round(_metric_value(values[0]), 3) if values else 0.0


def detect(path, *, duration_s: float, threshold: float = 27.0,
           min_scene_len_s: float = 0.7,
           progress: ProgressFn | None = None) -> list[dict]:
    """Return the shot list. Falls back to one scene when no cut is found."""
    from scenedetect import (
        ContentDetector,
        SceneManager,
        StatsManager,
        open_video,
    )

    if progress:
        progress(0.05, "opening video")
    video = open_video(str(path))
    fps = float(video.frame_rate or 25.0)
    min_len_frames = max(1, int(round(min_scene_len_s * fps)))

    # A StatsManager is what keeps the per-frame content value around after
    # detection; without it the cut strengths would all read 0.
    try:
        manager = SceneManager(StatsManager())
    except TypeError:  # older PySceneDetect without the constructor argument
        manager = SceneManager()
    detector = ContentDetector(threshold=threshold,
                               min_scene_len=min_len_frames)
    manager.add_detector(detector)
    if progress:
        progress(0.10, "scanning frames")
    manager.detect_scenes(video, show_progress=False)
    pairs = manager.get_scene_list()

    scenes: list[dict] = []
    for index, (start, end) in enumerate(pairs):
        start_s = float(start.get_seconds())
        end_s = float(end.get_seconds())
        if end_s <= start_s:
            continue
        scenes.append({
            "index": index,
            "start_s": round(start_s, 3),
            "end_s": round(end_s, 3),
            "len_s": round(end_s - start_s, 3),
            "score": _cut_strength(manager, int(start.get_frames())),
        })

    if not scenes:
        scenes = [{
            "index": 0,
            "start_s": 0.0,
            "end_s": round(duration_s, 3),
            "len_s": round(duration_s, 3),
            "score": 0.0,
        }]

    if progress:
        progress(1.0, f"{len(scenes)} scene(s)")
    return scenes
