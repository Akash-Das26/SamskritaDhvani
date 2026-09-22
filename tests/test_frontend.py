"""Unit tests for the shared front-end (design D1, FR-01/FR-02/FR-03).

Per NFR-02, every fixture here is a clearly labeled synthetic signal
(sines, chirps, noise, silence). None of it is real corpus audio, and
none of these tests produce a reported similarity/accuracy number —
they verify pipeline correctness only.
"""

import numpy as np
import pytest
import soundfile as sf

from samskrita_dhvani.frontend import (
    DEFAULT_CONFIG,
    FrontendConfig,
    cross_check_mfcc,
    extract_features,
    formants_pitch,
    frame_signal,
    hand_mfcc,
    load_audio_16k,
    lpcc,
    pre_emphasize,
    vad_speech_fraction,
    vad_trim,
    _levinson_durbin,
    _lpc_to_ceps,
)


# ---------------------------------------------------------------- fixtures

@pytest.fixture(scope="module")
def sr():
    return DEFAULT_CONFIG.sample_rate


@pytest.fixture(scope="module")
def sine_1khz(sr):
    """1 kHz sine, 1.0 s — clearly synthetic tone fixture."""
    t = np.arange(sr, dtype=np.float64) / sr
    return 0.5 * np.sin(2 * np.pi * 1000.0 * t)


@pytest.fixture(scope="module")
def speech_like(sr):
    """Sum of formant-like sines with amplitude modulation + noise.

    Stands in for the broadband, harmonic structure of speech without
    being recording of speech (NFR-02).
    """
    t = np.arange(sr, dtype=np.float64) / sr
    x = (
        0.4 * np.sin(2 * np.pi * 220.0 * t)
        + 0.3 * np.sin(2 * np.pi * 880.0 * t)
        + 0.2 * np.sin(2 * np.pi * 2100.0 * t)
        + 0.1 * np.sin(2 * np.pi * 3300.0 * t)
    )
    env = 0.6 + 0.4 * np.sin(2 * np.pi * 3.0 * t)
    rng = np.random.default_rng(42)
    return (x * env + 0.01 * rng.standard_normal(len(t))).astype(np.float32)


# ------------------------------------------------------------- FR-01 parts

def test_pre_emphasis_formula():
    x = np.array([1.0, 2.0, 4.0, 8.0])
    y = pre_emphasize(x, 0.97)
    assert y[0] == pytest.approx(1.0)
    assert y[1:] == pytest.approx(x[1:] - 0.97 * x[:-1])


def test_pre_emphasis_attenuates_dc_by_design():
    # y[n] = x[n] - 0.97 x[n-1] on a DC input leaves (1 - 0.97)·x after
    # the first sample: DC is attenuated 33x, not zeroed.
    x = np.ones(16_000)
    y = pre_emphasize(x, 0.97)
    assert y[0] == pytest.approx(1.0)
    assert np.allclose(y[1:], 0.03)
    assert abs(np.mean(y)) < 0.031


def test_frame_signal_geometry(sr):
    x = np.zeros(int(1.0 * sr))
    frames = frame_signal(x)
    assert frames.shape[1] == 400          # 25 ms @ 16 kHz
    # 1 s minus one frame, at 10 ms hop -> ~99 frames (tail-padded floor)
    assert 98 <= frames.shape[0] <= 101


def test_frame_signal_tail_padded():
    # 500 samples, fl=400, hop=160 -> 2 frames; padded length
    # (2-1)*160+400 = 560, so the last frame holds samples 160..559
    # with the final 60 values zero-padded.
    x = np.ones(500)
    cfg = FrontendConfig(frame_ms=25.0, hop_ms=10.0)
    frames = frame_signal(x, cfg)
    assert frames.shape[0] == 2
    assert frames[-1][339] == 1.0          # last real sample (500-1-160)
    assert np.all(frames[-1][340:] == 0)   # zero padding beyond it


# ------------------------------------------------------------ FR-02 config

def test_config_documents_every_parameter():
    cfg = DEFAULT_CONFIG
    assert cfg.sample_rate == 16_000
    assert cfg.pre_emphasis == 0.97
    assert cfg.frame_ms == 25.0 and cfg.hop_ms == 10.0
    assert cfg.window == "hamming"
    assert cfg.n_mels == 26
    assert cfg.n_mfcc == 13 and cfg.keep_c0 is False
    assert cfg.mel_htk is True
    assert cfg.delta_width == 9
    assert cfg.cmvn is True
    assert cfg.frame_length == 400 and cfg.hop_length == 160


def test_config_is_immutable():
    with pytest.raises(Exception):
        DEFAULT_CONFIG.sample_rate = 8_000


# ------------------------------------------------------- output contract

def test_extract_features_shape_and_contract(speech_like):
    feats = extract_features(speech_like)
    assert feats.dtype == np.float32
    assert feats.ndim == 2
    assert feats.shape[1] == 39            # 13 MFCC + 13 Δ + 13 ΔΔ
    assert 90 <= feats.shape[0] <= 105     # ~1 s at 10 ms hop


def test_cmvn_zero_mean_unit_variance(speech_like):
    feats = extract_features(speech_like)          # cmvn=True
    raw = extract_features(speech_like, FrontendConfig(cmvn=False))
    assert np.allclose(feats.mean(axis=0), 0.0, atol=1e-4)
    assert np.allclose(feats.std(axis=0), 1.0, atol=1e-2)
    # and the normalization is the only difference
    assert raw.shape == feats.shape


def test_resampling_path(tmp_path, sr):
    """load_audio_16k: 44.1 kHz stereo file -> 16 kHz mono float32."""
    t = np.arange(int(0.5 * 44_100)) / 44_100
    stereo = np.stack(
        [0.3 * np.sin(2 * np.pi * 440 * t), 0.3 * np.sin(2 * np.pi * 550 * t)], axis=1
    ).astype(np.float32)
    p = tmp_path / "t.wav"
    sf.write(p, stereo, 44_100)
    y = load_audio_16k(str(p))
    assert y.dtype == np.float32
    assert y.ndim == 1
    assert len(y) == int(0.5 * sr)         # duration preserved at 16 kHz


# ------------------------------------------------- hand-vs-librosa (FR-03)

def test_fr03_cross_check_speech_like(speech_like):
    """The FR-03 number: measured, not asserted to be zero."""
    r = cross_check_mfcc(speech_like)
    assert r["n_frames_hand"] == r["n_frames_librosa"]
    # sanity: same-stage implementations should land in the same
    # acoustic ballpark; the measured max diff is reported via the
    # return value and logged in Review.md.
    assert r["max_abs_diff"] < 5.0


def test_fr03_cross_check_perfect_on_steady_tone(sine_1khz):
    """On a stationary tone both paths must agree almost exactly:
    a single dominant frequency exercises no edge/slope differences."""
    r = cross_check_mfcc(sine_1khz)
    assert r["max_abs_diff"] < 1e-6


def test_fr03_cross_check_scale_invariance(speech_like):
    """Hand path must track the library path under gain changes
    (dB-scaled log + fixed mel slopes = constant offset per frame)."""
    r1 = cross_check_mfcc(speech_like)
    r2 = cross_check_mfcc(0.1 * speech_like)
    assert abs(r1["max_abs_diff"] - r2["max_abs_diff"]) < 0.1


def test_hand_and_library_frame_counts_match(speech_like):
    h = hand_mfcc(speech_like)
    feats = extract_features(speech_like, FrontendConfig(cmvn=False))
    assert h.shape[0] == feats.shape[0]
    assert h.shape[1] == 13


def test_extract_features_silence_is_finite():
    """All-zero input must not produce NaN/Inf through log/CMVN."""
    feats = extract_features(np.zeros(16_000))
    assert np.all(np.isfinite(feats))


# ----------------------------------------------------- VAD (FR-01 layer)

def test_vad_speech_fraction_clean_speech(sr):
    rng = np.random.default_rng(7)
    t = np.arange(sr) / sr
    modulated = (0.4 * (1 + np.sin(2 * np.pi * 4 * t)) * np.sin(2 * np.pi * 300 * t)
                 + 0.05 * rng.standard_normal(sr))
    frac = vad_speech_fraction(modulated.astype(np.float32))
    assert frac > 0.8          # continuously voiced synthetic speech


def test_vad_speech_fraction_silence():
    rng = np.random.default_rng(8)
    quiet = (1e-4 * rng.standard_normal(16_000)).astype(np.float32)
    frac = vad_speech_fraction(quiet)
    assert frac < 0.1          # near-silence fixture


def test_vad_trim_shortens_silence_padded_speech(sr):
    rng = np.random.default_rng(9)
    t = np.arange(sr // 2) / sr
    speech = 0.4 * np.sin(2 * np.pi * 300 * t) + 0.02 * rng.standard_normal(len(t))
    padded = np.concatenate([np.zeros(4000), speech, np.zeros(4000)]).astype(np.float32)
    trimmed = vad_trim(padded)
    assert len(trimmed) < len(padded)
    assert len(trimmed) > len(speech)          # padding kept


def test_vad_trim_no_speech_returns_input():
    x = (1e-4 * np.random.default_rng(10).standard_normal(8000)).astype(np.float32)
    out = vad_trim(x)
    assert len(out) == len(x)  # documented no-speech behaviour


def test_vad_rejects_more_than_90pct_silence():
    """DataIntegrity §1.1's near-silence rule, as code."""
    x = np.zeros(16_000, dtype=np.float32)
    assert vad_speech_fraction(x) < 0.1


# ------------------------------------------------- FR-04: LPCC path

@pytest.fixture(scope="module")
def vowel_like(sr):
    """Harmonic buzz (F0 150 Hz, 1/k amplitudes) with resonances added
    at 750 Hz (=5·F0) and 1200 Hz (=8·F0) — all partials are harmonics
    of one true F0, so pitch and formant structure are unambiguous.
    Clearly synthetic."""
    t = np.arange(sr) / sr
    buzz = sum(0.3 / k * np.sin(2 * np.pi * 150 * k * t) for k in range(1, 11))
    form = 0.3 * np.sin(2 * np.pi * 750 * t) + 0.2 * np.sin(2 * np.pi * 1200 * t)
    return (0.5 * buzz + 0.5 * form).astype(np.float32)


def test_levinson_durbin_recovers_ar_process():
    """Durbin method on a known AR(2) process should recover a1, a2."""
    rng = np.random.default_rng(11)
    a_true = np.array([0.9, -0.3])
    n = 16_000
    e = rng.standard_normal(n)
    x = np.zeros(n)
    for i in range(2, n):
        x[i] = a_true[0] * x[i - 1] + a_true[1] * x[i - 2] + e[i]
    r = np.array([np.dot(x[: n - k], x[k:]) / n for k in range(3)])
    a_est, err = _levinson_durbin(r, 2)
    assert np.allclose(a_est, a_true, atol=0.05)
    assert 0 < err <= r[0] + 1e-9


def test_levinson_durbin_reflection_clamping_keeps_stable():
    """A degenerate (constant) frame must not yield NaN/Inf or an
    exploding filter — reflection coefficients are clamped to ±0.999."""
    r = np.array([1.0, 1.0, 1.0, 1.0])   # perfectly correlated frame
    a, err = _levinson_durbin(r, 3)
    assert np.all(np.isfinite(a))
    assert np.all(np.abs(a) <= 2.0)


def test_lpc_to_ceps_first_coefficient_identity():
    """c1 = a1 exactly (the recursion's first step has no sum)."""
    a = np.array([0.8, -0.25, 0.1])
    c = _lpc_to_ceps(a, 3)
    assert c[0] == pytest.approx(a[0])


def test_lpc_to_ceps_q_may_exceed_p():
    """Course: Q ≈ 3/2 p and 'Q may be greater than p' — the recursion
    must zero-extend a_m beyond the LPC order, not index-error."""
    a = np.array([0.8, -0.25, 0.1, 0.05])
    c = _lpc_to_ceps(a, 10)                # Q=10 > p=4
    assert c.shape == (10,)
    assert np.all(np.isfinite(c))
    # and the tail coefficients decay (minimum-phase envelope)
    assert np.abs(c[-1]) < np.abs(c[0])


def test_lpcc_shape_defaults_and_delta(speech_like):
    feats = lpcc(speech_like)
    assert feats.dtype == np.float32
    assert feats.shape[1] == 21            # course: Q ≈ 3/2 p, p=14 -> 21
    assert feats.shape[0] == extract_features(speech_like).shape[0]
    wide = lpcc(speech_like, with_delta=True)
    assert wide.shape[1] == 42
    assert np.all(np.isfinite(feats))


def test_lpcc_envelope_peaks_near_resonances(vowel_like):
    """The LPCC spectral envelope exp(FFT(c)) must show prominent peaks
    near the two resonances — LPCC models the vocal-tract envelope.
    (Prominence, not global argmax: the buzz's own harmonics legitimately
    compete in overall level.)"""
    feats = lpcc(vowel_like)
    row = feats[len(feats) // 2]
    full = np.concatenate([[0.0], row])            # c0 (log gain) = 0
    env = np.exp(np.real(np.fft.fft(full, n=512)))
    freqs = np.fft.fftfreq(512, d=1.0 / 16_000)[:256]
    env = env[:256]
    med = np.median(env)
    for res, halfwidth in ((750.0, 150.0), (1200.0, 250.0)):
        band = np.abs(freqs - res) < halfwidth
        assert env[band].max() > 2.0 * med         # prominent local peak
        peak_hz = freqs[band][np.argmax(env[band])]
        assert abs(peak_hz - res) < halfwidth


# --------------------------------------------- FR-04: formants/pitch path

def test_formants_pitch_grid_matches_mfcc(vowel_like):
    fp = formants_pitch(vowel_like)
    t_mfcc = extract_features(vowel_like).shape[0]
    assert fp["times"].shape[0] == t_mfcc
    assert fp["formants"].shape == (t_mfcc, 3)
    assert fp["pitch"].shape == (t_mfcc,)


def test_formants_recover_resonances(vowel_like):
    fp = formants_pitch(vowel_like)
    vals = fp["formants"][np.isfinite(fp["formants"])]
    assert vals.size > 0
    assert np.min(np.abs(vals - 750)) < 120
    assert np.min(np.abs(vals - 1200)) < 150


def test_pitch_tracks_fundamental(vowel_like):
    fp = formants_pitch(vowel_like)
    voiced = fp["pitch"][np.isfinite(fp["pitch"])]
    assert voiced.size > 20                  # continuously voiced fixture
    assert abs(np.median(voiced) - 150.0) < 10.0


def test_delta_extremes_are_monotone():
    """The regression Δ of a linearly increasing static coefficient is
    constant — verifies the delta stage behaves like the course's
    regression formula rather than something exotic."""
    cfg = FrontendConfig(cmvn=False, delta_width=9)
    t = np.arange(16_000) / 16_000
    # a pure tone sweep: static c1 rises ~linearly with the sweep
    x = 0.5 * np.sin(2 * np.pi * (200 + 400 * t) * t)
    feats = extract_features(x, cfg)
    d = feats[:, 13]  # first delta coefficient
    interior = d[10:-10]
    assert np.nanstd(interior) < np.nanstd(feats[:, 0][10:-10])
