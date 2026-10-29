"""Motion map for the demo video add-on (DEMO ONLY).

Plain frame differencing: each sampled frame is reduced to a 192x108 grey
image, the absolute difference against the previous sample is averaged
into a 48x27 grid cell by cell, and the accumulated grid is rendered as a
heatmap. No optical flow and no model — this shows *where* pixels changed,
not what moved or which way.

The same pass also records one mean-difference value per second, which is
what the page's motion series is drawn from.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

GRID = (48, 27)
SMALL = (192, 108)
HEATMAP_SIZE = (640, 360)


class Accumulator:
    """Fed one frame per sample; keeps only the grid and per-second sums."""

    def __init__(self, grid: tuple[int, int] = GRID):
        self.grid = grid
        self.accumulated = np.zeros((grid[1], grid[0]), dtype=np.float64)
        self.samples = 0
        self.prev = None
        self.per_second: dict[int, list[float]] = {}

    def feed(self, frame, t_s: float) -> None:
        small = cv2.resize(frame, SMALL, interpolation=cv2.INTER_AREA)
        grey = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        if self.prev is not None:
            diff = cv2.absdiff(grey, self.prev)
            cell = cv2.resize(diff, self.grid, interpolation=cv2.INTER_AREA)
            self.accumulated += cell.astype(np.float64)
            self.per_second.setdefault(int(t_s), []).append(float(diff.mean()))
            self.samples += 1
        self.prev = grey

    def finish(self, out_path: Path, duration_s: float) -> dict:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if self.samples == 0 or self.accumulated.max() <= 0:
            heat = np.zeros((HEATMAP_SIZE[1], HEATMAP_SIZE[0], 3), np.uint8)
            cv2.imwrite(str(out_path), heat)
            return {
                "map": out_path.name, "grid": list(self.grid),
                "mean": 0.0, "peak": 0.0,
                "per_second": [0.0] * max(1, int(round(duration_s))),
                "hotspots": [], "samples": 0,
            }

        # Average per sample, then scale relative to the busiest cell, so the
        # map reads as "share of peak motion" rather than absolute luma.
        average = self.accumulated / float(self.samples)
        peak = float(average.max())
        relative = average / peak
        heat_small = np.clip(relative * 255.0, 0, 255).astype(np.uint8)
        heat = cv2.applyColorMap(
            cv2.resize(heat_small, HEATMAP_SIZE, interpolation=cv2.INTER_CUBIC),
            cv2.COLORMAP_TURBO,
        )
        cv2.imwrite(str(out_path), heat)

        seconds = int(round(duration_s))
        series = []
        for second in range(max(1, seconds)):
            values = self.per_second.get(second, [])
            series.append(round(float(np.mean(values)), 3) if values else 0.0)

        return {
            "map": out_path.name,
            "grid": list(self.grid),
            # Both on the same 0-255 luma-difference scale: mean of the
            # per-cell averages, and the busiest cell's average.
            "mean": round(float(average.mean()), 3),
            "peak": round(peak, 3),
            "per_second": series[:seconds or 1],
            "hotspots": _hotspots(relative),
            "samples": self.samples,
        }


def _hotspots(relative: np.ndarray, count: int = 4) -> list[dict]:
    """Peaks of a 5x5 smoothed grid, at least 6 cells apart."""
    import numpy as _np

    height, width = relative.shape
    smoothed = cv2.blur(relative.astype(np.float32), (5, 5))
    order = _np.dstack(_np.unravel_index(
        _np.argsort(smoothed, axis=None)[::-1], smoothed.shape))[0]
    picked: list[tuple[int, int]] = []
    for y, x in order:
        if smoothed[y, x] <= 0:
            break
        if any(abs(x - px) < 6 and abs(y - py) < 6 for px, py in picked):
            continue
        picked.append((int(x), int(y)))
        if len(picked) >= count:
            break
    return [{
        "x": round((x + 0.5) / width, 4),
        "y": round((y + 0.5) / height, 4),
        "weight": round(float(smoothed[y, x]), 4),
    } for x, y in picked]
