"""Worker for the demo video add-on (DEMO ONLY, runs in demo/.venv-video).

Invoked by the demo server as ``python -m demo.video.pipeline --job DIR``,
or by hand as ``python -m demo.video.pipeline --input clip.mp4 --out DIR``.
Progress is written to ``DIR/status.json`` as each stage advances; the
finished payload goes to ``DIR/result.json``. All five outputs live beside
those files, inside ``demo/tmp/video/``.

Stages: probe -> scenes -> frames -> motion -> track -> summary.
"""

from __future__ import annotations

import argparse
import sys
import time
import traceback
from pathlib import Path

from demo.video import (
    BANNER,
    MAX_DURATION_S,
    MAX_SAMPLED_FRAMES,
    SAMPLE_FPS,
    STAGES,
    TRACK_FPS_MAX,
    TRACK_MAX_DETECTIONS,
)
from demo.video import frames, jobs, motion, scenes, summary, track
WEIGHTS = {"probe": 3, "scenes": 15, "frames": 27, "motion": 10,
           "track": 30, "summary": 15}


class PipelineError(Exception):
    """A refusal the API can explain: ``{"code": ..., "detail": ...}``."""

    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


class Status:
    """Rewrites status.json at stage boundaries and on a light throttle."""

    def __init__(self, job: Path):
        self.job = job
        doc = jobs.read_json(jobs.status_path(job)) or {}
        doc.setdefault("job_id", job.name)
        doc.setdefault("created_at", _now())
        doc["status"] = "running"
        doc["error"] = None
        doc["progress"] = {
            "stage": "probe", "stage_index": 0, "stages": STAGES,
            "pct": 0, "detail": "starting", "elapsed_s": 0.0,
        }
        self.doc = doc
        self.started = time.perf_counter()
        self.last_write = 0.0
        self.write(force=True)

    def stage(self, name: str, fraction: float = 0.0, detail: str = "",
              force: bool = False) -> None:
        index = STAGES.index(name)
        base = sum(WEIGHTS[s] for s in STAGES[:index])
        pct = base + WEIGHTS[name] * max(0.0, min(1.0, fraction))
        self.doc["progress"] = {
            "stage": name,
            "stage_index": index,
            "stages": STAGES,
            "pct": int(round(min(99.0, pct))),
            "detail": detail,
            "elapsed_s": round(time.perf_counter() - self.started, 2),
        }
        self.write(force=force)

    def write(self, force: bool = False) -> None:
        now = time.perf_counter()
        if not force and now - self.last_write < 0.4:
            return
        self.doc["updated_at"] = _now()
        self.doc["progress"]["elapsed_s"] = round(now - self.started, 2)
        jobs.write_json(jobs.status_path(self.job), self.doc)
        self.last_write = now

    def fail(self, code: str, detail: str) -> None:
        self.doc["status"] = "failed"
        self.doc["error"] = {"code": code, "detail": detail}
        self.doc["updated_at"] = _now()
        self.doc["progress"]["elapsed_s"] = round(
            time.perf_counter() - self.started, 2)
        jobs.write_json(jobs.status_path(self.job), self.doc)

    def done(self, result: dict) -> None:
        self.doc["status"] = "done"
        self.doc["progress"].update({"stage": "done", "pct": 100,
                                     "detail": "complete",
                                     "stage_index": len(STAGES)})
        self.doc["result"] = {
            "frames": len(result["frames"]),
            "scenes": len(result["scenes"]),
            "tracks": result["tracks"]["count"],
            "summary_seconds": result["summary"]["seconds"],
        }
        self.doc["updated_at"] = _now()
        self.doc["progress"]["elapsed_s"] = round(
            time.perf_counter() - self.started, 2)
        jobs.write_json(jobs.status_path(self.job), self.doc)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def run(job: Path, source: Path, *, status: Status | None = None) -> dict:
    """Run every stage and return the result payload (also written to disk)."""
    status = status or Status(job)
    timings: dict[str, float] = {}

    # ------------------------------------------------------------- probe
    started = time.perf_counter()
    status.stage("probe", 0.1, "reading container metadata")
    try:
        meta = frames.probe(source)
    except RuntimeError as exc:
        raise PipelineError("not_video",
                            f"Not a decodable video: {exc}") from exc

    duration = float(meta["duration_s"])
    if duration <= 0.1:
        raise PipelineError("not_video", "No decodable frames in the file.")
    if duration > MAX_DURATION_S + 0.5:
        raise PipelineError(
            "too_long",
            f"Video is {duration / 60:.1f} min; the demo caps at 30.")
    status.doc["source"] = {
        **status.doc.get("source", {}),
        **meta,
        "sampled_fps": SAMPLE_FPS,
    }
    status.stage("probe", 1.0, f"{meta['width']}x{meta['height']} · "
                               f"{duration:.1f}s", force=True)
    timings["probe"] = round(time.perf_counter() - started, 2)

    # ------------------------------------------------------------ scenes
    started = time.perf_counter()
    scene_list = scenes.detect(
        source, duration_s=duration,
        progress=lambda frac, detail: status.stage("scenes", frac, detail),
    )
    timings["scenes"] = round(time.perf_counter() - started, 2)
    status.stage("scenes", 1.0, f"{len(scene_list)} scene(s)", force=True)

    # ------------------------------------------- frames (one decode pass)
    started = time.perf_counter()
    accumulator = motion.Accumulator()
    records: list[dict] = []
    for record in frames.scan(
            source, sample_fps=SAMPLE_FPS, max_frames=MAX_SAMPLED_FRAMES,
            progress=lambda frac, detail: status.stage("frames", frac, detail),
            on_frame=accumulator.feed):
        records.append(record)

    selections = frames.select(records, scene_list)
    saved = frames.save(source, selections, job / "frames")
    timings["frames"] = round(time.perf_counter() - started, 2)
    status.stage("frames", 1.0, f"{len(saved)} important frame(s)",
                 force=True)

    # ------------------------------------------------------------ motion
    started = time.perf_counter()
    status.stage("motion", 0.2, "rendering motion map")
    motion_info = accumulator.finish(job / "motion_map.png", duration)
    timings["motion"] = round(time.perf_counter() - started, 2)
    status.stage("motion", 1.0, f"{motion_info['samples']} diff pairs",
                 force=True)

    # ------------------------------------------------------------- track
    started = time.perf_counter()
    track_info = track.detect_and_track(
        source, duration_s=duration, max_detect_s=TRACK_FPS_MAX,
        max_detections=TRACK_MAX_DETECTIONS, job_dir=job,
        progress=lambda frac, detail: status.stage("track", frac, detail),
    )
    timings["track"] = round(time.perf_counter() - started, 2)
    status.stage("track", 1.0, f"{track_info['count']} track(s)", force=True)

    # ----------------------------------------------------------- summary
    started = time.perf_counter()
    summary_info = summary.build(
        job, source, scene_list, duration,
        progress=lambda frac, detail: status.stage("summary", frac, detail),
    )
    timings["summary"] = round(time.perf_counter() - started, 2)
    status.stage("summary", 1.0, f"{summary_info['seconds']:.1f}s summary",
                 force=True)

    # ----------------------------------------------- key frame per scene
    by_scene: dict[int, dict] = {}
    for frame in saved:
        by_scene.setdefault(int(frame.get("scene", 0)), frame)
    for scene in scene_list:
        key = by_scene.get(scene["index"])
        scene["key_frame"] = key["file"] if key else None
        scene["key_thumb"] = key["thumb"] if key else None
        scene["key_t_s"] = key["t_s"] if key else None

    result = {
        "job_id": job.name,
        "status": "done",
        "banner": BANNER,
        "source": {
            "filename": status.doc.get("source", {}).get("filename"),
            "bytes": status.doc.get("source", {}).get("bytes"),
            "duration_s": round(duration, 3),
            "width": meta["width"],
            "height": meta["height"],
            "fps": meta["fps"],
            "sampled_fps": SAMPLE_FPS,
            "frames_decoded": meta["frame_count"],
        },
        "frames": [{
            "number": f["number"],
            "t_s": f["t_s"],
            "scene": f["scene"],
            "score": f["score"],
            "sharpness": f["sharpness"],
            "change": f["change"],
            "file": f["file"],
            "thumb": f["thumb"],
            "width": f["width"],
            "height": f["height"],
        } for f in saved],
        "scenes": scene_list,
        "motion": motion_info,
        "tracks": track_info,
        "summary": summary_info,
        "timings": timings,
        "generated_at": _now(),
    }
    jobs.write_json(jobs.result_path(job), result)
    status.done(result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m demo.video.pipeline",
        description="DEMO video analysis worker (add-on, not an SRS feature).")
    parser.add_argument("--job", type=Path,
                        help="job directory created by demo.video.jobs")
    parser.add_argument("--input", type=Path, help="source video (manual runs)")
    parser.add_argument("--out", type=Path, help="output dir (manual runs)")
    parser.add_argument("--name", default=None, help="display filename")
    args = parser.parse_args(argv)

    if args.job:
        job = args.job.resolve()
        sources = sorted(job.glob("source.*"))
        if not sources:
            print(f"error: no source.* in {job}", file=sys.stderr)
            return 2
        source = sources[0]
        status = Status(job)
    elif args.input and args.out:
        job = args.out.resolve()
        job.mkdir(parents=True, exist_ok=True)
        source = args.input.resolve()
        status = Status(job)
        status.doc["source"] = {
            "filename": args.name or source.name,
            "bytes": source.stat().st_size,
        }
    else:
        parser.error("use --job DIR, or --input FILE --out DIR")
        return 2

    try:
        result = run(job, source, status=status)
    except PipelineError as exc:
        status.fail(exc.code, exc.detail)
        print(f"failed: {exc.code} — {exc.detail}", file=sys.stderr)
        return 3
    except Exception as exc:  # noqa: BLE001 — the job must end in a state
        traceback.print_exc()
        status.fail("pipeline_error", f"{type(exc).__name__}: {exc}")
        return 4

    print(f"done: {len(result['frames'])} frame(s), "
          f"{len(result['scenes'])} scene(s), "
          f"{result['tracks']['count']} track(s), "
          f"summary {result['summary']['seconds']:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
