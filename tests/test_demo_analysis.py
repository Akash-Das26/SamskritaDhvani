"""Tests for the demo's measured attempt analysis (demo/analysis.py).

All fixtures are synthetic (NFR-02), as in the D2 scorer tests: two
harmonic-stack "vowels" with known formant structure, a concatenation of
them, and a resampled (time-stretched) copy of that concatenation. No
corpus audio is used, so the suite runs without demo data.
"""

from __future__ import annotations

import math

import numpy as np

from demo.analysis import N_BINS, analyze_attempt
from samskrita_dhvani.spd_scorer import Calibration, score_attempt


def vowel(dur=0.6, sr=16000, f0=150, formants=(700.0, 1200.0, 2600.0),
          seed=0, noise=1e-4):
    """Synthesized vowel: harmonic stack shaped by three formant gaussians."""
    rng = np.random.default_rng(seed)
    n = int(sr * dur)
    t = np.arange(n) / sr
    y = np.zeros(n)
    for k in range(1, 13):
        fk = f0 * k
        amp = (
            np.exp(-((fk - formants[0]) ** 2) / (2 * 300.0**2))
            + 0.7 * np.exp(-((fk - formants[1]) ** 2) / (2 * 400.0**2))
            + 0.3 * np.exp(-((fk - formants[2]) ** 2) / (2 * 500.0**2))
        )
        y += amp * np.sin(2 * np.pi * fk * t + rng.uniform(0, 2 * np.pi))
    env = 0.5 * (1 - np.cos(np.pi * np.minimum(1.0, t / dur)))
    y = 0.3 * y * env / (np.max(np.abs(y)) + 1e-12)
    return y + noise * rng.standard_normal(n)


def two_vowels():
    """A synthetic two-vowel utterance (synthetic fixture)."""
    return np.concatenate(
        [
            vowel(0.3, formants=(700, 1200, 2600), seed=2),
            vowel(0.3, formants=(400, 2000, 2600), seed=3),
        ]
    )


def stretched(y, factor=1.5):
    """Resample the fixture to ``factor``× its duration (synthetic)."""
    n = len(y)
    m = int(n * factor)
    return np.interp(np.linspace(0, n - 1, m), np.arange(n), y)


def calibration(d0=2.0):
    return Calibration(
        word_id="synthetic",
        d0=d0,
        d0_formant=1.0,
        d0_duration=1.0,
        n_references=1,
        schema_version=1,
    )


def test_self_comparison_is_diagonal_and_zero_cost():
    y = vowel(seed=1)  # synthetic
    out = analyze_attempt(y, y, d0=1.0, scorer_similarity_pct=100.0)

    assert out["d_mfcc"] == 0.0
    assert all(i == j for i, j in out["dtw_path"])
    assert out["duration_ratio"] == 1.0
    assert [b["mean_cost"] for b in out["cost_profile"]["bins"]] == [0.0] * N_BINS
    assert out["d_mfcc_check"]["within_1e-6"] is True
    assert out["d_mfcc_check"]["gap"] <= 1e-6


def test_time_stretch_gives_bent_path_and_ratio_near_stretch_factor():
    ref = two_vowels()  # synthetic
    attempt = stretched(ref, 1.5)
    score = score_attempt(attempt, ref, calibration(), {"word_id": "synthetic"})
    out = analyze_attempt(
        attempt, ref, d0=2.0, scorer_similarity_pct=score.similarity_pct
    )

    assert 1.4 <= out["duration_ratio"] <= 1.6
    assert out["d_mfcc"] > 0.5
    # The alignment must leave the identity diagonal for a 1.5× stretch.
    assert max(abs(i - j) for i, j in out["dtw_path"]) >= 10
    assert out["dtw_path"][0][0] <= 1 and out["dtw_path"][-1][1] == out["cost_profile"]["reference_frames"] - 1


def test_d_mfcc_matches_the_scorer():
    attempt = vowel(0.6, seed=5)  # synthetic, same "word", different take
    reference = vowel(0.55, seed=9)
    score = score_attempt(
        attempt, reference, calibration(), {"word_id": "synthetic"}
    )
    out = analyze_attempt(
        attempt, reference, d0=2.0, scorer_similarity_pct=score.similarity_pct
    )

    check = out["d_mfcc_check"]
    assert check["within_1e-6"] is True
    assert check["gap"] <= 1e-6
    assert abs(check["scorer_distance"] - out["d_mfcc"]) <= 1e-6
    # And the reported percentage is the scorer's, at its published precision.
    assert round(100.0 * math.exp(-out["d_mfcc"] / 2.0), 1) == round(score.similarity_pct, 1)


def test_cost_profile_has_seven_bins_over_the_reference_timeline():
    ref = two_vowels()  # synthetic
    attempt = stretched(ref, 1.3)
    out = analyze_attempt(attempt, ref, d0=2.0, scorer_similarity_pct=50.0)
    profile = out["cost_profile"]

    assert profile["n_bins"] == N_BINS
    assert len(profile["bins"]) == N_BINS
    assert profile["bins"][0]["ref_frame_start"] == 0
    assert profile["bins"][-1]["ref_frame_end"] == profile["reference_frames"]
    assert all(b["frames"] > 0 for b in profile["bins"])
    # The bins partition the path, so their weighted mean reproduces D.
    total = sum(b["mean_cost"] * b["frames"] for b in profile["bins"])
    frames = sum(b["frames"] for b in profile["bins"])
    assert abs(total / frames - out["d_mfcc"]) < 1e-6


def test_formants_are_measured_or_explicitly_unavailable():
    y = vowel(0.6, seed=7)  # synthetic
    out = analyze_attempt(y, y, d0=1.0, scorer_similarity_pct=100.0)
    for side in ("reference", "attempt"):
        track = out["formants"][side]
        assert track["available"] is True
        assert track["source"].startswith("Praat")
        assert track["median_hz"]["f1"] > 0
        assert len(track["f1"]) == len(track["f2"])

    tiny = analyze_attempt(
        np.zeros(100), np.zeros(100), d0=1.0, scorer_similarity_pct=100.0
    )
    track = tiny["formants"]["attempt"]
    assert track["available"] is False
    assert isinstance(track["reason"], str) and track["reason"]
