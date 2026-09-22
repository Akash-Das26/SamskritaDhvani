"""Shared feature-extraction front-end for SPD and GVR (design D1).

Implements the pipeline fixed at Phase 3 sign-off:

    16 kHz mono -> pre-emphasis 0.97 -> framing 25 ms / 10 ms shift
    -> Hamming window -> power spectrum -> 26-triangle Mel filterbank
    (0-8 kHz, HTK mel) -> log -> DCT-II -> 13 MFCC kept (c0 discarded)
    -> Delta + Delta-Delta -> CMVN per utterance

Output contract: a (T, 39) float32 matrix per clip (the compatibility
surface for both branches). Every parameter is a named, documented
attribute of :class:`FrontendConfig` (FR-02) — no library default is
inherited anywhere (Phase 2 verified librosa's defaults differ from the
course spec: sr=22050, n_mfcc=20, n_mels=128, slaney mel).

Theory reference: the SVP course chapters (Ch-5 / UNIT II_MFCC / Ch-6),
which specify DFT power spectrum -> triangular Mel filterbank -> log ->
IDFT/DCT with the first ~12-13 cepstral values kept, and regression
(Delta/Delta-Delta) plus CMN/CMVN normalization (Ch-6).

A hand-derived MFCC path (:func:`hand_mfcc`) implements the same math
from first principles (FR-03); :func:`cross_check_mfcc` quantifies its
difference from the librosa path on any input.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import librosa
import soundfile as sf
import webrtcvad
import parselmouth
from parselmouth import praat

__all__ = [
    "FrontendConfig",
    "DEFAULT_CONFIG",
    "load_audio_16k",
    "pre_emphasize",
    "frame_signal",
    "vad_speech_fraction",
    "vad_trim",
    "extract_features",
    "hand_mfcc",
    "cross_check_mfcc",
    "lpcc",
    "formants_pitch",
]


@dataclass(frozen=True)
class FrontendConfig:
    """Exact configuration of the shared front-end (FR-02).

    All values are the D1 design decisions signed off at Phase 3;
    changing any of them is a flagged breaking change to both the SPD
    and GVR branches (Development.md Ground Rule 4).
    """

    sample_rate: int = 16_000
    """Analysis sample rate in Hz; all input audio is resampled to it."""

    pre_emphasis: float = 0.97
    """First-order high-pass coefficient (course Ch-5 range 0.95-0.97)."""

    frame_ms: float = 25.0
    """Frame length in milliseconds (course range 20-25 ms)."""

    hop_ms: float = 10.0
    """Frame shift in milliseconds (course: 10 ms)."""

    window: str = "hamming"
    """Window family (course Ch-3/Ch-4: Hamming to limit spectral leakage)."""

    n_mels: int = 26
    """Number of triangular Mel filters (course UNIT II_MFCC: 20-26)."""

    n_mfcc: int = 13
    """Cepstral coefficients kept per frame (course: first 12-13)."""

    keep_c0: bool = False
    """c0 is discarded per the course's 'first 12-13 values' convention."""

    fmin: float = 0.0
    """Mel filterbank lower edge in Hz."""

    fmax: float = 8000.0
    """Mel filterbank upper edge in Hz (= sample_rate / 2 at 16 kHz)."""

    mel_htk: bool = True
    """Use the HTK mel formula (2595 * log10(1 + f/700)), matching the
    course's Mel-scale definition rather than Slaney's."""

    delta_width: int = 9
    """Regression window for Delta/Delta-Delta (course Ch-6 convention)."""

    cmvn: bool = True
    """Apply per-utterance cepstral mean-and-variance normalization."""

    @property
    def frame_length(self) -> int:
        """Frame length in samples at :attr:`sample_rate`."""
        return int(round(self.sample_rate * self.frame_ms / 1000.0))

    @property
    def hop_length(self) -> int:
        """Frame shift in samples at :attr:`sample_rate`."""
        return int(round(self.sample_rate * self.hop_ms / 1000.0))


DEFAULT_CONFIG = FrontendConfig()
"""The signed-off D1 configuration. Both branches must use this object
(or an explicitly documented variant) so the report can state exact
values."""


def load_audio_16k(path: str, config: FrontendConfig = DEFAULT_CONFIG) -> np.ndarray:
    """Load an audio file and resample to mono ``config.sample_rate``.

    Accepts any format ``soundfile`` reads (WAV/FLAC/MP3/OGG). Mono is
    produced by averaging channels; resampling uses librosa's polyphase
    resampler. Returns float32 in [-1, 1].
    """
    audio, sr = sf.read(path, dtype="float32", always_2d=True)
    mono = audio.mean(axis=1)
    if sr != config.sample_rate:
        mono = librosa.resample(
            mono, orig_sr=sr, target_sr=config.sample_rate, res_type="polyphase"
        )
    return np.ascontiguousarray(mono, dtype=np.float32)


def pre_emphasize(x: np.ndarray, coeff: float = 0.97) -> np.ndarray:
    """First-order pre-emphasis ``y[n] = x[n] - coeff * x[n-1]``."""
    return np.append(x[0], x[1:] - coeff * x[:-1])


def frame_signal(x: np.ndarray, config: FrontendConfig = DEFAULT_CONFIG) -> np.ndarray:
    """Slice a 1-D signal into overlapping frames.

    Returns a ``(n_frames, frame_length)`` view-compatible array with
    10 ms hop and 25 ms length at 16 kHz by default. Frames are padded
    (zeros) at the tail so the whole signal is covered, matching the
    default centered behaviour of the library path.
    """
    fl, hop = config.frame_length, config.hop_length
    n_frames = 1 + max(0, int(np.ceil((len(x) - fl) / hop)))
    padded = np.pad(x, (0, max(0, (n_frames - 1) * hop + fl - len(x))))
    idx = np.arange(fl)[None, :] + hop * np.arange(n_frames)[:, None]
    return padded[idx]


def vad_speech_fraction(
    audio: np.ndarray,
    aggressiveness: int = 2,
    sample_rate: int = 16_000,
) -> float:
    """Fraction of 30 ms frames classified as speech by WebRTC VAD.

    DataIntegrity.md §1.1 treats clips that are more than ~90% silence
    as invalid; this function is the measurement used to apply that
    rule. Input must be a 1-D float waveform in [-1, 1] at 16 kHz.
    """
    vad = webrtcvad.Vad(aggressiveness)
    x = np.asarray(audio, dtype=np.float32)
    x16 = np.clip(x * 32767.0, -32768, 32767).astype(np.int16)
    fl = int(0.03 * sample_rate)
    frames = [x16[i : i + fl] for i in range(0, len(x16) - fl + 1, fl)]
    if not frames:
        return 0.0
    speech = sum(1 for fr in frames if vad.is_speech(fr.tobytes(), sample_rate))
    return speech / len(frames)


def vad_trim(
    audio: np.ndarray,
    aggressiveness: int = 2,
    pad_ms: float = 50.0,
    sample_rate: int = 16_000,
) -> np.ndarray:
    """Trim leading/trailing silence, keeping ``pad_ms`` of headroom.

    The trimming stage of the shared preprocessing layer
    (Implementation.md §3; FR-01). Returns the waveform cut to the
    first..last speech-containing 30 ms frame (plus padding). If no
    speech is detected at all, the input is returned unchanged — the
    caller must use :func:`vad_speech_fraction` to apply the
    DataIntegrity near-silence exclusion rule.
    """
    vad = webrtcvad.Vad(aggressiveness)
    x = np.asarray(audio, dtype=np.float32)
    x16 = np.clip(x * 32767.0, -32768, 32767).astype(np.int16)
    fl = int(0.03 * sample_rate)
    starts = list(range(0, len(x16) - fl + 1, fl))
    speech_idx = [i for i in starts if vad.is_speech(x16[i : i + fl].tobytes(), sample_rate)]
    if not speech_idx:
        return x
    pad = int(pad_ms / 1000.0 * sample_rate)
    a = max(0, speech_idx[0] - pad)
    b = min(len(x), speech_idx[-1] + fl + pad)
    return x[a:b]


def _frame_hamming(x: np.ndarray, config: FrontendConfig) -> np.ndarray:
    """Centered framing + periodic Hamming window (shared by the hand
    MFCC path and the LPCC path — one framing definition per front-end)."""
    fl, hop = config.frame_length, config.hop_length
    pad = fl // 2
    xp = np.pad(np.asarray(x, dtype=np.float64), (pad, pad))
    n_frames = 1 + (len(xp) - fl) // hop
    idx = np.arange(fl)[None, :] + hop * np.arange(n_frames)[:, None]
    w = _hamming(fl)
    return xp[idx] * w


def _levinson_durbin(r: np.ndarray, order: int) -> tuple[np.ndarray, float]:
    """Levinson-Durbin recursion (the course's 'Durbin method').

    ``r`` holds order+1 autocorrelation values (r[0] = frame energy).
    Returns ``(a, error)`` with ``a`` the LPC coefficients in the
    A(z) = 1 - a1 z^-1 - ... convention (a[k-1] is a_k), and the final
    residual error. Reflection coefficients are clamped to ±0.999 so a
    degenerate frame can never yield an unstable filter.
    """
    a = np.zeros(order)
    if r[0] <= 0:
        return a, 0.0
    E = float(r[0])
    for i in range(1, order + 1):
        acc = r[i] - np.dot(a[: i - 1], r[i - 1 : 0 : -1])
        k = acc / E
        if not np.isfinite(k):
            break
        k = float(np.clip(k, -0.999, 0.999))
        a_prev = a.copy()
        a[i - 1] = k
        if i > 1:
            a[: i - 1] = a_prev[: i - 1] - k * a_prev[i - 2 :: -1]
        E *= 1.0 - k * k
        if E <= 0:
            break
    return a, E


def _lpc_to_ceps(a: np.ndarray, n_ceps: int) -> np.ndarray:
    """LPC -> cepstral recursion (course UNIT II_LPCC step 5).

    c_m = a_m + (1/m) * sum_{k=1}^{m-1} k * c_k * a_{m-k}, with a_m = 0
    for m > LPC order. c0 (log gain) is not produced — the course's
    feature vector starts at c1. Q may exceed the LPC order (course:
    Q ≈ 3/2 p).
    """
    p = len(a)
    # a_m = 0 for m > LPC order: zero-pad so Q may exceed p (course:
    # Q ≈ 3/2 p) without index errors in the recursion.
    if n_ceps > p:
        a = np.concatenate([a, np.zeros(n_ceps - p)])
    c = np.zeros(n_ceps)
    for m in range(1, n_ceps + 1):
        am = a[m - 1] if m <= p else 0.0
        k = np.arange(1, m)
        s = np.dot(k * c[: m - 1], a[m - 1 - k]) if m > 1 else 0.0
        c[m - 1] = am + s / m
    return c


def lpcc(
    audio: np.ndarray,
    config: FrontendConfig = DEFAULT_CONFIG,
    n_lpc: int = 14,
    n_ceps: int | None = None,
    with_delta: bool = False,
) -> np.ndarray:
    """Linear-Prediction Cepstral Coefficients (FR-04 ablation path).

    Course UNIT II_LPCC steps, in order: pre-emphasis -> frame blocking
    -> Hamming windowing -> autocorrelation analysis (p+1 values) ->
    Durbin method (Levinson-Durbin) -> direct recursive conversion to
    cepstral coefficients c1..cQ. Defaults follow the course: LPC order
    in its 8–16 range (14 here), Q ≈ 3/2 p (21). The framing/window are
    the front-end's shared 25 ms/10 ms Hamming (one definition per
    module). c0/log-gain is excluded, matching the course's feature
    vector V(t) = [c1..cQ, Δc1..ΔcQ].

    Returns ``(T, n_ceps)`` float32 (or ``(T, 2*n_ceps)`` with
    ``with_delta=True``).
    """
    if n_ceps is None:
        n_ceps = int(round(1.5 * n_lpc))
    x = np.asarray(audio, dtype=np.float64)
    x = pre_emphasize(x, config.pre_emphasis)
    frames = _frame_hamming(x, config)

    # p+1 autocorrelation values per frame (FFT method, zero-padded to
    # 2L so lags <= p are exact linear autocorrelations).
    fl = config.frame_length
    F = np.fft.rfft(frames, n=2 * fl, axis=1)
    r = np.fft.irfft(np.abs(F) ** 2, n=2 * fl, axis=1)[:, : n_lpc + 1]

    T = frames.shape[0]
    c = np.zeros((T, n_ceps))
    for t in range(T):
        a, _ = _levinson_durbin(r[t], n_lpc)
        c[t] = _lpc_to_ceps(a, n_ceps)

    if with_delta:
        d = librosa.feature.delta(c.T, width=config.delta_width, axis=1, mode="nearest").T
        c = np.concatenate([c, d], axis=1)
    return c.astype(np.float32)


def formants_pitch(
    audio: np.ndarray,
    config: FrontendConfig = DEFAULT_CONFIG,
    n_formants: int = 3,
    f0_min: float = 75.0,
    f0_max: float = 300.0,
    formant_max_hz: float = 5000.0,
) -> dict:
    """Praat formant + pitch tracks on the D1 analysis grid (FR-04).

    Formants: Burg method, 25 ms windows (matching D1's frame length),
    10 ms steps sampled exactly at the MFCC frame centers t = k·hop/sr
    so the per-axis SPD breakdown can join formant and MFCC features
    frame-by-frame. Pitch: Praat cross-correlation-era defaults bounded
    to [f0_min, f0_max].

    Returns ``{'times': (T,), 'formants': (T, n_formants),
    'pitch': (T,)}`` — unvoiced/unmeasured points are NaN (a formant
    value of exactly 0 from Praat is treated as unmeasured).
    Intended for word-length clips (SPD), not hour-long files.
    """
    x = np.asarray(audio, dtype=np.float64)
    snd = parselmouth.Sound(x, sampling_frequency=config.sample_rate)

    pitch = praat.call(snd, "To Pitch", 0.0, f0_min, f0_max)
    formant = praat.call(
        snd, "To Formant (burg)", 0.01, 5.0, formant_max_hz, 0.025, 50.0
    )

    hop_s = config.hop_length / config.sample_rate
    # Frame count matching the MFCC grid exactly (librosa center=True
    # with fl even): n_frames = 1 + len(x) // hop_length.
    n_frames = 1 + len(x) // config.hop_length
    times = np.arange(n_frames) * hop_s

    f_vals = np.full((len(times), n_formants), np.nan)
    p_vals = np.full(len(times), np.nan)
    for i, t in enumerate(times):
        v = pitch.get_value_at_time(float(t))
        p_vals[i] = v if (v is not None and np.isfinite(v) and v > 0) else np.nan
        for j in range(1, n_formants + 1):
            fv = formant.get_value_at_time(j, float(t))
            if fv is not None and np.isfinite(fv) and fv > 0:
                f_vals[i, j - 1] = fv
    return {"times": times, "formants": f_vals, "pitch": p_vals}


def _htk_hz_to_mel(f: np.ndarray | float) -> np.ndarray | float:
    return 2595.0 * np.log10(1.0 + np.asarray(f, dtype=np.float64) / 700.0)


def _htk_mel_to_hz(m: np.ndarray | float) -> np.ndarray | float:
    return 700.0 * (10.0 ** (np.asarray(m, dtype=np.float64) / 2595.0) - 1.0)


def _hamming(length: int) -> np.ndarray:
    """Periodic Hamming window (matches librosa/scipy ``hamming``).

    w[k] = 0.54 - 0.46 cos(2 pi k / length)."""
    n = np.arange(length)
    return 0.54 - 0.46 * np.cos(2.0 * np.pi * n / length)


def _dct_ii(x: np.ndarray, keep: int) -> np.ndarray:
    """DCT-II along the last axis, orthonormal scaling, first ``keep``.

    Equivalent to ``scipy.fftpack.dct(x, type=2, norm='ortho')[:keep]``
    but written out so the hand path depends on nothing beyond numpy.
    """
    n_frames, n_bands = x.shape
    k = np.arange(keep)[:, None]
    r = np.arange(n_bands)[None, :]
    basis = np.cos(np.pi * k * (2 * r + 1) / (2 * n_bands))
    y = x @ basis.T
    y[:, 0] *= 1.0 / np.sqrt(2.0)
    y *= np.sqrt(2.0 / n_bands)
    return y


def _mel_filterbank(config: FrontendConfig, n_fft_bins: int) -> np.ndarray:
    """Triangular Mel filterbank (n_mels, n_fft_bins), HTK mel spacing.

    Edge points are evenly spaced in mel, mapped back to Hz; ramps are
    computed on the continuous FFT frequency grid with clipped
    min(up, down) slopes. Extracted as a function so the FR-03 test can
    compare it against the library's filterbank directly.
    """
    hz = np.linspace(0.0, config.sample_rate / 2.0, n_fft_bins)
    mel_lo = _htk_hz_to_mel(config.fmin)
    mel_hi = _htk_hz_to_mel(config.fmax)
    hz_pts = _htk_mel_to_hz(np.linspace(mel_lo, mel_hi, config.n_mels + 2))
    up = (hz[None, :] - hz_pts[:-2, None]) / (hz_pts[1:-1] - hz_pts[:-2])[:, None]
    down = (hz_pts[2:, None] - hz[None, :]) / (hz_pts[2:] - hz_pts[1:-1])[:, None]
    return np.maximum(0.0, np.minimum(up, down))


def hand_mfcc(
    audio: np.ndarray,
    config: FrontendConfig = DEFAULT_CONFIG,
    preemphasized: bool = False,
) -> np.ndarray:
    """Hand-derived MFCC (FR-03) implementing the course math directly.

    Pipeline: pre-emphasis -> centered framing -> periodic Hamming
    window -> raw power spectrum (rFFT) -> 26-triangle HTK-mel
    filterbank -> dB-scale log (10·log10, floor 1e-10) -> DCT-II
    (orthonormal) -> 14 coefficients computed, c0 discarded -> 13 kept.

    Returns the same (T, 13) static MFCC layout as the librosa path, so
    the two can be compared frame-by-frame. The c0 discard and the
    Delta/Delta-Delta/CMVN stages are shared with the library path and
    deliberately excluded from this comparison surface.
    """
    x = np.asarray(audio, dtype=np.float64)
    if not preemphasized:
        x = pre_emphasize(x, config.pre_emphasis)

    # Centered framing (mirror the library path's center=True: pad
    # frame_length // 2 on both sides, floor frame count) via the shared
    # helper — one framing definition per module.
    frames = _frame_hamming(x, config)
    fl = config.frame_length

    # Power spectrum: raw rFFT magnitude squared. librosa.stft applies
    # NO magnitude normalization; a global scale would only shift c0
    # (discarded) EXCEPT at the amin floor, where the clamp pattern
    # must match — so we keep the raw scale identical to the library.
    spectrum = np.abs(np.fft.rfft(frames, n=fl)) ** 2

    # Triangular Mel filterbank (HTK spacing) over 0..Nyquist. The
    # n_mels + 2 edge points are evenly spaced in MEL, then mapped back
    # to Hz (even spacing in Hz is the classic MFCC bug).
    fbank = _mel_filterbank(config, fl // 2 + 1)

    mel_energy = spectrum @ fbank.T
    # 10*log10 with the same floor as the library path's power_to_db.
    log_mel = 10.0 * np.log10(np.maximum(mel_energy, 1e-10))

    # n_mfcc + 1 coefficients computed, c0 discarded -> 13 kept (D1).
    coeffs = _dct_ii(log_mel, config.n_mfcc + 1)
    return coeffs[:, 1:]


def extract_features(
    audio: np.ndarray,
    config: FrontendConfig = DEFAULT_CONFIG,
    preemphasized: bool = False,
) -> np.ndarray:
    """Extract the full D1 feature matrix from a 16 kHz mono waveform.

    Library path: identical front-end stages realized with librosa
    (``melspectrogram`` + ``mfcc`` + ``librosa.feature.delta``), then the
    shared post-processing stages (c0 discard, Delta/Delta-Delta, CMVN).

    Returns a ``(T, 39)`` float32 matrix: 13 static MFCC + 13 Delta +
    13 Delta-Delta, optionally CMVN-normalized (mean 0, unit variance
    per coefficient over the utterance). This is the compatibility
    contract consumed by both the SPD and GVR branches.
    """
    x = np.asarray(audio, dtype=np.float64)
    if not preemphasized:
        x = pre_emphasize(x, config.pre_emphasis)

    hop, fl = config.hop_length, config.frame_length

    mel = librosa.feature.melspectrogram(
        y=x,
        sr=config.sample_rate,
        n_fft=fl,
        hop_length=hop,
        win_length=fl,
        window=config.window,
        center=True,
        power=2.0,
        n_mels=config.n_mels,
        fmin=config.fmin,
        fmax=config.fmax,
        htk=config.mel_htk,
        norm=None,
    )
    # n_mfcc + 1 DCT coefficients; c0 discarded unless keep_c0=True.
    n_dct = config.n_mfcc + 1 if not config.keep_c0 else config.n_mfcc
    mfcc = librosa.feature.mfcc(
        S=librosa.power_to_db(mel, amin=1e-10, top_db=None),
        sr=config.sample_rate,
        n_mfcc=n_dct,
        dct_type=2,
        norm="ortho",
        lifter=0,
    )
    static = mfcc.T
    if not config.keep_c0:
        static = static[:, 1:]  # discard c0 per course convention -> 13 kept

    delta = librosa.feature.delta(static.T, width=config.delta_width, axis=1, mode="nearest").T
    delta2 = librosa.feature.delta(delta.T, width=config.delta_width, axis=1, mode="nearest").T
    feats = np.concatenate([static, delta, delta2], axis=1)

    if config.cmvn:
        mean = feats.mean(axis=0, keepdims=True)
        std = feats.std(axis=0, keepdims=True)
        feats = (feats - mean) / np.maximum(std, 1e-8)

    return feats.astype(np.float32)


def cross_check_mfcc(
    audio: np.ndarray,
    config: FrontendConfig = DEFAULT_CONFIG,
    preemphasized: bool = False,
) -> dict:
    """FR-03 cross-check: hand-derived vs librosa MFCC on one input.

    Both paths compute static MFCC only (identical stage boundaries).
    The comparison is exact frame-alignment: the hand path is run with
    centered-padding-equivalent framing and the library path with the
    same hop/win/window/normalization, so frame t means the same
    25 ms analysis window in both.

    Returns a dict with ``max_abs_diff``, ``mean_abs_diff``,
    ``rms_diff``, and the per-path shapes. The measured numbers (not
    assertions) are what FR-03 requires to be reported.
    """
    hand = hand_mfcc(audio, config, preemphasized=preemphasized)
    x = np.asarray(audio, dtype=np.float64)
    if not preemphasized:
        x = pre_emphasize(x, config.pre_emphasis)
    n_dct = config.n_mfcc + 1 if not config.keep_c0 else config.n_mfcc

    hop, fl = config.hop_length, config.frame_length
    mel = librosa.feature.melspectrogram(
        y=x,
        sr=config.sample_rate,
        n_fft=fl,
        hop_length=hop,
        win_length=fl,
        window=config.window,
        center=True,
        power=2.0,
        n_mels=config.n_mels,
        fmin=config.fmin,
        fmax=config.fmax,
        htk=config.mel_htk,
        norm=None,
    )
    lib = librosa.feature.mfcc(
        S=librosa.power_to_db(mel, amin=1e-10, top_db=None),
        sr=config.sample_rate,
        n_mfcc=n_dct,
        dct_type=2,
        norm="ortho",
        lifter=0,
    ).T
    if not config.keep_c0:
        lib = lib[:, 1:]

    t = min(hand.shape[0], lib.shape[0])
    diff = np.abs(hand[:t] - lib[:t])
    return {
        "n_frames_hand": int(hand.shape[0]),
        "n_frames_librosa": int(lib.shape[0]),
        "max_abs_diff": float(diff.max()),
        "mean_abs_diff": float(diff.mean()),
        "rms_diff": float(np.sqrt((diff**2).mean())),
    }
