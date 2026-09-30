"""Tests for the D2 SPD scorer (Phase 4 unit 3).

All fixtures are synthetic (NFR-02): harmonic-stack vowels with known
formant structure, noise, and tones — no corpus audio required. The
property tests mirror the Phase 3 test plan: DTW alignment
monotonicity, sim-mapping monotonicity, and the D=0 → 100 boundary.
"""

import json
import math

import numpy as np
import pytest

from samskrita_dhvani.frontend import DEFAULT_CONFIG
from samskrita_dhvani.spd_scorer import (
    CALIBRATION_SCHEMA_VERSION,
    Calibration,
    CalibrationBuilder,
    _consonant_mask,
    _duration_axis_distance,
    _formant_axis_distance,
    _norm_loglike_to_pct,
    dtw_mean_distance,
    load_calibration,
    score_attempt,
    static_mfcc,
)


def vowel(dur=0.6, sr=16000, f0=150, formants=(700.0, 1200.0, 2600.0),
          seed=0, noise=1e-4):
    """Synthesized vowel: harmonic stack shaped by three formant
    gaussians, raised-cosine envelope, tiny noise floor."""
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


# ------------------------------------------------------------- features

def test_static_mfcc_shape_and_cmvn():
    mfcc = static_mfcc(vowel(seed=1))
    assert mfcc.shape[1] == 13
    assert mfcc.ndim == 2
    # CMVN'd statics are ~zero-mean per coefficient (FR-02 property).
    assert np.allclose(mfcc.mean(axis=0), 0.0, atol=1e-6)


def test_static_mfcc_is_first_13_columns_of_d1_output():
    from samskrita_dhvani.frontend import extract_features

    x = vowel(seed=2)
    full = extract_features(x)
    assert np.array_equal(static_mfcc(x), full[:, :13])


# ------------------------------------------------------------------ DTW

def test_dtw_identical_signals_give_zero_distance():
    mfcc = static_mfcc(vowel(seed=3))
    d = dtw_mean_distance(mfcc, mfcc)
    assert d < 1e-9


def test_dtw_distance_grows_with_distortion():
    ref = static_mfcc(vowel(formants=(700, 1200, 2600), seed=4))
    small = static_mfcc(vowel(formants=(900, 1300, 2600), seed=4))
    large = static_mfcc(vowel(formants=(1500, 2000, 2600), seed=4))
    d_small = dtw_mean_distance(small, ref)
    d_large = dtw_mean_distance(large, ref)
    assert 0 < d_small < d_large


def test_dtw_path_is_monotonic_and_spanning():
    a = static_mfcc(vowel(dur=0.6, seed=5))
    r = static_mfcc(vowel(dur=0.9, seed=5))  # same "utterance", stretched
    d, path = dtw_mean_distance(a, r, return_path=True)
    assert d >= 0
    assert path[0] == (0, 0)
    assert path[-1] == (a.shape[0] - 1, r.shape[0] - 1)
    for (i0, j0), (i1, j1) in zip(path, path[1:]):
        assert (i1 - i0, j1 - j0) in {(1, 0), (0, 1), (1, 1)}
    assert len(path) >= max(a.shape[0], r.shape[0])


# ------------------------------------------------------- sim mapping

def test_sim_mapping_zero_distance_is_exactly_100():
    assert _norm_loglike_to_pct(0.0, d0=1.7) == 100.0


def test_sim_mapping_matches_approved_formula():
    d0 = 2.4
    assert _norm_loglike_to_pct(d0, d0) == pytest.approx(100 * math.exp(-1.0))


def test_sim_mapping_is_monotone_decreasing_in_distance():
    sims = [_norm_loglike_to_pct(x, d0=1.0) for x in (0.0, 0.5, 1.0, 2.0, 4.0)]
    assert all(a > b for a, b in zip(sims, sims[1:]))


def test_larger_d0_is_a_gentler_scale():
    assert _norm_loglike_to_pct(1.0, d0=4.0) > _norm_loglike_to_pct(1.0, d0=1.0)


# ------------------------------------------------------------ axes

def test_formant_axis_near_zero_for_same_vowel():
    a = vowel(seed=6)
    r = vowel(seed=6)
    assert _formant_axis_distance(a, r) < 0.02


def test_formant_axis_grows_with_formant_shift():
    a = vowel(formants=(900, 1400, 2600), seed=6)
    r = vowel(formants=(700, 1200, 2600), seed=6)
    assert _formant_axis_distance(a, r) > 0.05


def test_formant_axis_raises_on_silence():
    silence = np.zeros(1600)
    with pytest.raises(ValueError, match="voiced"):
        _formant_axis_distance(silence, vowel(seed=7))


def test_duration_axis_symmetric_in_ratio():
    short = vowel(dur=0.6, seed=8)
    long = vowel(dur=1.2, seed=8)
    d_fast = _duration_axis_distance(short, long)
    d_slow = _duration_axis_distance(long, short)
    # The axis measures vad-trimmed (acoustic) duration, so a 2× raw
    # ratio need not map to exactly |log 2| — the trim cuts the quiet
    # tails of the two clips by slightly different amounts. Symmetry
    # and ballpark are the contract.
    assert d_fast == pytest.approx(d_slow)  # r and 1/r penalize equally
    assert 0.4 < d_fast < 1.0               # consistent with ~2× duration


def test_consonant_mask_avoids_the_loud_voiced_nucleus():
    x = vowel(dur=0.6, seed=9)
    mask = _consonant_mask(x)
    assert mask.dtype == bool
    assert mask.sum() >= 2
    rms_frames = np.array(
        [np.sqrt(np.mean(x[i * 160 : (i + 1) * 160] ** 2))
         for i in range(mask.shape[0])]
    )
    loud = rms_frames > np.percentile(rms_frames, 90)
    assert not (mask & loud).any()  # consonant frames are never the loudest


# ------------------------------------------------------- end-to-end

def _calibration_for(tmp_path, word_id="kRSNa"):
    ref = vowel(seed=10)
    builder = CalibrationBuilder()
    builder.set_canonical(word_id, ref)
    builder.add_reference(word_id, vowel(seed=11))
    builder.add_reference(word_id, np.roll(vowel(seed=12), 400))
    builder.add_reference(word_id, vowel(seed=13))
    data = builder.build(
        provenance={"source_id": "SYNTHETIC", "acquired_on": "2026-10-01"},
        out_path=tmp_path / "calibration.json",
    )
    assert data["words"][word_id]["d0"] > 0
    cal = load_calibration(word_id, tmp_path / "calibration.json")
    assert cal is not None and cal.n_references == 3
    return cal, ref


def test_score_attempt_ranks_good_over_bad(tmp_path):
    cal, ref = _calibration_for(tmp_path)
    good = ref + 2e-3 * np.random.default_rng(14).standard_normal(len(ref))
    bad = vowel(formants=(1500, 2100, 2900), seed=15)
    word = {"word_id": "kRSNa", "devanagari": "कृष्ण", "iast": "kṛṣṇa"}
    s_good = score_attempt(good, ref, cal, word)
    s_bad = score_attempt(bad, ref, cal, word)
    for s in (s_good, s_bad):
        assert 0 < s.similarity_pct <= 100
        assert 0 < s.vowel_score <= 100
        assert 0 < s.consonant_score <= 100
        assert 0 < s.duration_score <= 100
        assert s.reference_word == word
    assert s_good.similarity_pct > s_bad.similarity_pct
    assert s_good.vowel_score > s_bad.vowel_score
    # similarity_pct and mfcc_dtw_score share D and D₀ by construction.
    assert s_good.similarity_pct == s_good.mfcc_dtw_score


def test_score_attempt_perfect_copy_scores_100():
    """The D=0 boundary, end-to-end through the scoring entry point."""
    ref = vowel(seed=16)
    cal = Calibration(
        word_id="kRSNa", d0=1.0, d0_formant=0.05, d0_duration=0.05,
        n_references=1, schema_version=CALIBRATION_SCHEMA_VERSION,
    )
    s = score_attempt(
        ref.copy(), ref, cal,
        {"word_id": "kRSNa", "devanagari": "कृष्ण", "iast": "kṛṣṇa"},
    )
    assert s.similarity_pct == pytest.approx(100.0)


# ------------------------------------------------------ calibration IO

def test_calibration_builder_file_structure(tmp_path):
    _, ref = _calibration_for(tmp_path)
    data = json.loads((tmp_path / "calibration.json").read_text(encoding="utf-8"))
    assert data["schema_version"] == CALIBRATION_SCHEMA_VERSION == 1
    assert data["kind"] == "spd_calibration"
    entry = data["words"]["kRSNa"]
    assert {"d0", "d0_formant", "d0_duration", "n_references"} <= set(entry)
    assert data["provenance"]["source_id"] == "SYNTHETIC"


def test_load_calibration_missing_file_is_none(tmp_path):
    assert load_calibration("kRSNa", tmp_path / "absent.json") is None


def test_load_calibration_missing_word_is_none(tmp_path):
    _, ref = _calibration_for(tmp_path)
    assert load_calibration("notAWord", tmp_path / "calibration.json") is None


def test_load_calibration_rejects_wrong_schema(tmp_path):
    p = tmp_path / "calibration.json"
    p.write_text(json.dumps({"schema_version": 99, "kind": "spd_calibration",
                             "words": {}}), encoding="utf-8")
    with pytest.raises(ValueError, match="schema_version"):
        load_calibration("kRSNa", p)


def test_calibration_builder_requires_canonical_and_references():
    builder = CalibrationBuilder()
    with pytest.raises(ValueError, match="canonical"):
        builder.build_word("kRSNa")
    builder.set_canonical("kRSNa", vowel(seed=17))
    with pytest.raises(ValueError, match="known-correct"):
        builder.build_word("kRSNa")
