"""Short summary video for the demo add-on (DEMO ONLY).

Takes one short slice from scenes spread across the clip, encodes each
slice to a small MP4 with ffmpeg (the binary bundled with imageio-ffmpeg,
falling back to ``ffmpeg`` on PATH) and joins them with the concat demuxer.
Audio is dropped: the summary exists to show *what happened where*, not to
be a faithful excerpt.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

MAX_SUMMARY_S = 90.0
SHOT_S = 2.5


def ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg

        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and Path(exe).exists():
            return exe
    except Exception:  # noqa: BLE001 — fall through to PATH
        pass
    found = shutil.which("ffmpeg")
    if not found:
        raise RuntimeError("ffmpeg not found (imageio-ffmpeg or PATH)")
    return found


def _pick_shots(scenes: list[dict], duration_s: float) -> list[dict]:
    target = min(MAX_SUMMARY_S, max(10.0, 0.25 * duration_s))
    usable = [s for s in scenes if s["end_s"] - s["start_s"] >= 0.5]
    if not usable:
        usable = scenes
    count = max(1, int(round(target / SHOT_S)))
    count = min(count, len(usable))
    if count <= 0:
        return []

    # Spread picks evenly, always including the first and last scene.
    if count == 1:
        picks = [usable[0]]
    else:
        picks = [usable[round(i * (len(usable) - 1) / (count - 1))]
                 for i in range(count)]

    length = target / len(picks)
    shots = []
    for scene in picks:
        start = scene["start_s"]
        room = scene["end_s"] - start
        shots.append({
            "start_s": round(start, 3),
            "len_s": round(min(length, room), 3),
            "scene": scene["index"],
            "score": scene.get("score", 0.0),
        })
    return shots


def build(job_dir: Path, source_path: Path, scenes: list[dict],
          duration_s: float, *, progress=None) -> dict:
    ffmpeg = ffmpeg_exe()
    shots = _pick_shots(scenes, duration_s)
    parts_dir = job_dir / "parts"
    parts_dir.mkdir(parents=True, exist_ok=True)

    parts: list[Path] = []
    for number, shot in enumerate(shots):
        part = parts_dir / f"shot_{number:02d}.mp4"
        command = [
            ffmpeg, "-v", "error", "-y",
            "-ss", f"{shot['start_s']:.3f}",
            "-t", f"{shot['len_s']:.3f}",
            "-i", str(source_path),
            "-an",
            "-vf", "scale=640:360:force_original_aspect_ratio=decrease,"
                   "pad=640:360:(ow-iw)/2:(oh-ih)/2:color=black,fps=25",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "30",
            "-pix_fmt", "yuv420p",
            str(part),
        ]
        proc = subprocess.run(command, capture_output=True, text=True)
        if proc.returncode != 0 or not part.exists() or part.stat().st_size == 0:
            raise RuntimeError(
                f"ffmpeg failed on shot {number}: "
                f"{(proc.stderr or '').strip()[-300:] or 'no output'}")
        parts.append(part)
        if progress:
            progress((number + 1) / max(1, len(shots)),
                     f"shot {number + 1}/{len(shots)}")

    if not parts:
        raise RuntimeError("no shots could be built")

    listing = parts_dir / "concat.txt"
    listing.write_text("".join(f"file '{p.name}'\n" for p in parts))
    out = job_dir / "summary.mp4"
    proc = subprocess.run(
        [ffmpeg, "-v", "error", "-y", "-f", "concat", "-safe", "0",
         "-i", str(listing), "-c", "copy", str(out)],
        capture_output=True, text=True)
    if proc.returncode != 0 or not out.exists() or out.stat().st_size == 0:
        raise RuntimeError(f"ffmpeg concat failed: "
                           f"{(proc.stderr or '').strip()[-300:] or 'no output'}")

    seconds = round(sum(s["len_s"] for s in shots), 3)
    return {
        "video": out.name,
        "bytes": out.stat().st_size,
        "seconds": seconds,
        "source_seconds": round(duration_s, 3),
        "compression_ratio": round(seconds / duration_s, 4) if duration_s else 0.0,
        "shot_s": SHOT_S,
        "shots": shots,
    }
