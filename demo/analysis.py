"""Measured per-attempt diagnostics for the demo (demo-only).

Everything here is computed from the attempt and its reference with the
project's own front-end and scorer functions. Nothing is derived from
the returned sub-scores, and no phoneme name, timecode or voicing tag is
invented:

- ``dtw_path``      backtrace of the DTW that ``spd_scorer.dtw_mean_distance``
                    runs over the 13 static CMVN MFCCs
- ``d_mfcc``        that same distance, asserted against the scorer's
- ``duration_ratio`` VAD-trimmed attempt length ÷ trimmed reference length
- ``formants``      Praat Burg F1/F2 time series (or null + reason)
- ``cost_profile``  local DTW cost along the path in 7 equal bins of the
                    reference frame timeline

The module imports from ``samskrita_dhvani`` but does not modify it.
"""

from __future__ import annotations

import math
from typing import Any

import librosa
import numpy as np

from samskrita_dhvani.frontend import DEFAULT_CONFIG, FrontendConfig, formants_pitch, vad_trim
from samskrita_dhvani.spd_scorer import dtw_mean_distance, static_mfcc

N_BINS = 7
"""Reference-timeline bins for the local cost profile."""


def _local_cost(attempt: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """The exact pairwise local cost ``dtw_mean_distance`` uses.

    ``static_mfcc`` returns float32; the scorer casts to float64 before
    its expansion, so do the same here (float32 cancellation would leave
    a ~4e-3 phantom cost on a self-comparison's diagonal).
    """
    attempt = np.asarray(attempt, dtype=np.float64)
    reference = np.asarray(reference, dtype=np.float64)
    sq_a = np.sum(attempt**2, axis=1)[:, None]
    sq_r = np.sum(reference**2, axis=1)[None, :]
    return np.sqrt(np.maximum(sq_a + sq_r - 2.0 * attempt @ reference.T, 0.0))


def _series(values: np.ndarray, times: np.ndarray, digits: int = 1) -> list[dict]:
    """JSON-safe point list; NaN becomes null."""
    out = []
    for t, v in zip(times, values):
        out.append(
            {
                "t_s": round(float(t), 4),
                "hz": None if not np.isfinite(v) else round(float(v), digits),
            }
        )
    return out


def _formant_track(audio: np.ndarray, config: FrontendConfig) -> dict:
    """F1/F2 on the trimmed clip, or an explicit unavailable reason."""
    trimmed = np.asarray(vad_trim(audio), dtype=np.float64)
    if len(trimmed) < config.frame_length:
        return {"available": False, "reason": "clip shorter than one analysis frame"}
    try:
        fp = formants_pitch(trimmed, config)
    except Exception as exc:  # noqa: BLE001 - report, never substitute
        return {"available": False, "reason": f"formant tracking failed: {exc}"}
    f = fp["formants"]
    finite = np.isfinite(f[:, 0]) | np.isfinite(f[:, 1])
    if not finite.any():
        return {"available": False, "reason": "no voiced frames with measurable formants"}
    f1 = f[:, 0]
    f2 = f[:, 1]
    return {
        "available": True,
        "source": "Praat Burg via samskrita_dhvani.frontend.formants_pitch",
        "f1": _series(f1, fp["times"]) if finite.any() else [],
        "f2": _series(f2, fp["times"]) if finite.any() else [],
        "median_hz": {
            "f1": round(float(np.nanmedian(f1)), 1) if np.isfinite(f1).any() else None,
            "f2": round(float(np.nanmedian(f2)), 1) if np.isfinite(f2).any() else None,
        },
    }


def analyze_attempt(
    attempt_audio: np.ndarray,
    reference_audio: np.ndarray,
    *,
    d0: float,
    scorer_similarity_pct: float,
    config: FrontendConfig = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Compute the measured diagnostics for one scored attempt.

    ``scorer_similarity_pct`` is the unrounded value returned by
    ``spd_scorer.score_attempt``; ``d0`` is that word's calibration scale.
    The distance check is an assertion about *equality of computation*:
    inverting the scorer's own percentage must reproduce the distance
    computed here, because both use the same MFCCs and the same DTW.
    """
    attempt_mfcc = static_mfcc(attempt_audio, config)
    reference_mfcc = static_mfcc(reference_audio, config)

    # Call the scorer's own distance, then obtain the optimal warping path
    # from the identical DTW (same cost matrix, same step set). librosa
    # returns the path end→start; reverse it so index 0 is the first frame.
    d = dtw_mean_distance(attempt_mfcc, reference_mfcc)
    cost = _local_cost(attempt_mfcc, reference_mfcc)
    _acc, wp = librosa.sequence.dtw(
        C=cost,
        step_sizes_sigma=np.array([[1, 1], [1, 0], [0, 1]], dtype=np.int32),
    )
    path = [(int(i), int(j)) for i, j in wp[::-1]]
    local = np.array([cost[i, j] for i, j in path], dtype=np.float64)
    mean_local = float(local.mean()) if len(local) else float("nan")

    # The scorer computes sim = 100·exp(−D/D₀); invert it to recover the
    # distance it used. This is the check the demo reports, not a substitute.
    if 0.0 < scorer_similarity_pct <= 100.0:
        d_scorer = -d0 * math.log(scorer_similarity_pct / 100.0)
    else:  # pragma: no cover - the scorer never returns outside this range
        d_scorer = float("nan")
    gap = abs(d - d_scorer) if math.isfinite(d_scorer) else float("nan")

    # Trimmed durations (the same VAD trim the scorer's duration axis uses).
    a_trim = vad_trim(np.asarray(attempt_audio, dtype=np.float64))
    r_trim = vad_trim(np.asarray(reference_audio, dtype=np.float64))
    a_s = len(a_trim) / config.sample_rate
    r_s = len(r_trim) / config.sample_rate
    duration_ratio = (a_s / r_s) if r_s > 0 else None

    # Local cost in equal bins of the reference frame timeline.
    n_ref = reference_mfcc.shape[0]
    edges = np.linspace(0.0, float(n_ref), N_BINS + 1)
    bins = []
    for b in range(N_BINS):
        lo, hi = edges[b], edges[b + 1]
        vals = [c for (_, j), c in zip(path, local) if lo <= j < hi or (b == N_BINS - 1 and j == n_ref - 1)]
        bins.append(
            {
                "bin": b + 1,
                "ref_frame_start": int(math.floor(lo)),
                "ref_frame_end": int(math.ceil(hi)),
                "ref_time_start_s": round(lo * config.hop_length / config.sample_rate, 4),
                "ref_time_end_s": round(hi * config.hop_length / config.sample_rate, 4),
                "mean_cost": round(float(np.mean(vals)), 6) if vals else None,
                "frames": len(vals),
            }
        )

    return {
        "d_mfcc": round(float(d), 6),
        "dtw_path": [[int(i), int(j)] for i, j in path],
        "dtw_frames": {"attempt": int(attempt_mfcc.shape[0]), "reference": int(reference_mfcc.shape[0])},
        "d_mfcc_check": {
            "scorer_distance": round(float(d_scorer), 6) if math.isfinite(d_scorer) else None,
            "gap": round(float(gap), 9) if math.isfinite(gap) else None,
            "within_1e-6": bool(math.isfinite(gap) and gap <= 1e-6),
            "path_mean_cost": round(mean_local, 6) if math.isfinite(mean_local) else None,
            "path_mean_gap": round(abs(mean_local - d), 9) if math.isfinite(mean_local) else None,
        },
        "duration_ratio": round(float(duration_ratio), 4) if duration_ratio is not None else None,
        "duration_s": {
            "attempt_trimmed": round(a_s, 4),
            "reference_trimmed": round(r_s, 4),
            "attempt_raw": round(len(attempt_audio) / config.sample_rate, 4),
            "reference_raw": round(len(reference_audio) / config.sample_rate, 4),
        },
        "formants": {
            "reference": _formant_track(reference_audio, config),
            "attempt": _formant_track(attempt_audio, config),
        },
        "cost_profile": {
            "n_bins": N_BINS,
            "reference_frames": int(n_ref),
            "bins": bins,
            "note": "local ||ΔMFCC₁₃||₂ along the DTW path, averaged per bin",
        },
    }
