"""D2 · SPD scoring module (Phase 4 unit 3).

Implements the approved D2 formula (Review.md, Phase 3 sign-off —
the binding spec, cited verbatim):

    D   = mean over aligned frame pairs of ||Δmfcc_13||₂
    sim = 100 · exp(−D / D₀)
    D₀  = per-word mean DTW distance of that word's known-correct
          recitations to the canonical reference (stored in
          calibration.json, schema version 1; recomputed on corpus
          change)

No arbitrary constant anywhere: the mapping's scale is *measured*
from known-correct recitations. By construction correct recitations
anchor near 100·e⁻¹ ≈ 36.8% and worse attempts fall below. Every
similarity in this module is diagnostic, never certifying.

Per-axis breakdown (FR-11), same exp(−·/·) mapping style:
- vowel/formant axis  — mean relative formant-frequency mismatch
  (Praat Burg formants, sampled at the D1 frame grid) mapped with a
  measured per-word scale D₀ᶠᵒʳᵐ (formant axis of the same
  calibration corpus).
- consonant/spectral axis — MFCC-DTW restricted to the
  consonant-window slice (mean pitch percentile gate on the attempt;
  consonant = low-F0, low-energy region; see _consonant_mask).
- duration axis — ratio attempt/reference; mapped symmetrically:
  1.0 → 100%, and a ratio of (1 ± r) scores like a DTW distance of
  r·D₀ᵈᵘʳ (ratio 2.0 or 0.5 both land at e⁻¹ of the scale).

Design contract notes:
- Features come from the D1 front-end (`samskrita_dhvani.frontend`)
  — one feature definition for the whole pipeline (Ground Rule 4:
  changing D1 is a flagged breaking change to both branches).
- DTW is `librosa.sequence.dtw` over CMVN-normalized static MFCCs
  (the 13 static coefficients of the 39-dim D1 output, i.e. the
  first 13 columns), exactly as the D2 spec states.
- Calibration data lives in ``data/spd/calibration.json`` (schema
  version 1). Absent file = explicitly uncalibrated: the API turns
  that into an honest 503, never a guessed D₀.

All test fixtures are synthetic (NFR-02): tones, synthesized vowels,
and synthetic formant structure — no corpus audio is required.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import librosa
import numpy as np

from samskrita_dhvani.frontend import (
    DEFAULT_CONFIG,
    FrontendConfig,
    extract_features,
    formants_pitch,
    vad_trim,
)

__all__ = [
    "CALIBRATION_SCHEMA_VERSION",
    "Calibration",
    "SpdScore",
    "static_mfcc",
    "dtw_mean_distance",
    "score_attempt",
    "CalibrationBuilder",
    "load_calibration",
]

# ----------------------------------------------------------------------
# calibration artifact

CALIBRATION_SCHEMA_VERSION = 1
"""Bump when the calibration file's fields/semantics change (Ground
Rule 4: regeneration must be detectable)."""

CALIBRATION_DEFAULT_PATH = Path("data") / "spd" / "calibration.json"


@dataclass(frozen=True)
class SpdScore:
    """The FR-10/FR-11 result for one attempt."""

    similarity_pct: float
    vowel_score: float
    consonant_score: float
    duration_score: float
    mfcc_dtw_score: float
    reference_word: dict
    """{word_id, devanagari, iast} of the word scored against."""


@dataclass(frozen=True)
class Calibration:
    """Per-word D₀ scales measured from known-correct recitations."""

    word_id: str
    d0: float
    d0_formant: float
    d0_duration: float
    n_references: int
    schema_version: int


def load_calibration(
    word_id: str,
    path: str | Path = CALIBRATION_DEFAULT_PATH,
) -> Calibration | None:
    """Load the calibration block for ``word_id``, or None.

    The file is schema-checked; a wrong version or missing word is an
    explicit miss (the caller reports 'uncalibrated'), never a default.
    """
    p = Path(path)
    if not p.is_file():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    if data.get("schema_version") != CALIBRATION_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported calibration schema_version: {data.get('schema_version')}"
        )
    if data.get("kind") != "spd_calibration":
        raise ValueError("not an spd_calibration file")
    entry = data.get("words", {}).get(word_id)
    if entry is None:
        return None
    return Calibration(
        word_id=word_id,
        d0=float(entry["d0"]),
        d0_formant=float(entry["d0_formant"]),
        d0_duration=float(entry["d0_duration"]),
        n_references=int(entry["n_references"]),
        schema_version=data["schema_version"],
    )


# ----------------------------------------------------------------------
# D2 core


def static_mfcc(
    audio: np.ndarray,
    config: FrontendConfig = DEFAULT_CONFIG,
) -> np.ndarray:
    """The 13 static CMVN-normalized MFCCs of the D1 pipeline.

    ``extract_features`` returns (T, 39) = [static13 | Δ13 | ΔΔ13] with
    CMVN applied to the whole matrix; the static block is its first 13
    columns (D2 scores on the CMVN'd statics, per the approved formula).
    """
    feats = extract_features(audio, config)
    return feats[:, :13]


def _dtw_path(D: np.ndarray, C: np.ndarray) -> list[tuple[int, int]]:
    """Backtrace the optimal DTW path from the accumulated-cost matrix.

    Returns (frame_in_attempt, frame_in_reference) pairs, ordered from
    the start. Pure numpy so the path property tests can verify
    monotonicity without depending on librosa internals.
    """
    T_a, T_r = C.shape
    i, j = T_a - 1, T_r - 1
    path = [(i, j)]
    while i > 0 or j > 0:
        if i == 0:
            j -= 1
        elif j == 0:
            i -= 1
        else:
            step = np.argmin([D[i - 1, j - 1], D[i - 1, j], D[i, j - 1]])
            if step == 0:
                i, j = i - 1, j - 1
            elif step == 1:
                i -= 1
            else:
                j -= 1
        path.append((i, j))
    path.reverse()
    return path


def dtw_mean_distance(
    attempt: np.ndarray,
    reference: np.ndarray,
    return_path: bool = False,
):
    """D2's D: mean ‖Δmfcc_13‖₂ over the DTW-aligned frame pairs.

    ``attempt`` and ``reference`` are (T, 13) static MFCC blocks. The
    local cost is the euclidean frame distance; the returned D is the
    mean local cost along the optimal path (the spec's "mean over
    aligned frame pairs").
    """
    attempt = np.atleast_2d(np.asarray(attempt, dtype=np.float64))
    reference = np.atleast_2d(np.asarray(reference, dtype=np.float64))
    # Pairwise euclidean local cost matrix.
    sq_a = np.sum(attempt**2, axis=1)[:, None]
    sq_r = np.sum(reference**2, axis=1)[None, :]
    C = np.sqrt(np.maximum(sq_a + sq_r - 2.0 * attempt @ reference.T, 0.0))
    D_acc, path = librosa.sequence.dtw(
        C=C, step_sizes_sigma=np.array([[1, 1], [1, 0], [0, 1]], dtype=np.int32)
    )
    if return_path:
        return float(D_acc[-1, -1] / len(path)), _dtw_path(D_acc, C)
    return float(D_acc[-1, -1] / len(path))


def _norm_loglike_to_pct(x: float, d0: float) -> float:
    """sim = 100·exp(−x/D₀), the approved mapping (x = D or axis
    distance; D₀ = the measured per-word scale)."""
    return 100.0 * math.exp(-x / d0)


# ----------------------------------------------------------------------
# per-axis measurements


def _consonant_mask(
    audio: np.ndarray,
    config: FrontendConfig = DEFAULT_CONFIG,
) -> np.ndarray:
    """Boolean frame mask marking likely-consonant frames of a clip.

    Consonants (esp. stops) show low periodicity (flat pitch) and low
    energy relative to the vowel peak. Frames in the lowest-40%
    pitch-magnitude percentile AND below-median RMS are marked
    consonant; at least the 10% lowest-energy frames are always
    included so even fully voiced clips yield a slice.
    """
    x = vad_trim(np.asarray(audio, dtype=np.float64))
    T = 1 + len(x) // config.hop_length  # D1 frame grid
    pitch = formants_pitch(x, config)["pitch"]
    n = len(pitch)
    pitch = np.where(np.isfinite(pitch), pitch, np.nan)

    hop = len(x) / max(n, 1)
    rms = np.array(
        [
            np.sqrt(
                np.mean(x[int(i * hop) : int((i + 1) * hop)] ** 2)
            )
            if int((i + 1) * hop) <= len(x) and int((i + 1) * hop) > int(i * hop)
            else 0.0
            for i in range(n)
        ]
    )
    with np.errstate(invalid="ignore"):
        p_thresh = np.nanpercentile(np.abs(pitch), 40)
        flat = np.abs(pitch) < p_thresh  # NaN comparisons → False
        loud = rms > np.median(rms[rms > 0]) if np.any(rms > 0) else rms > 0
        mask = flat & ~loud
    if mask.sum() < max(2, int(0.1 * n)):
        quiet = np.argsort(rms)[: max(2, int(0.1 * n))]
        mask = np.zeros(n, dtype=bool)
        mask[quiet] = True
    return mask[:T]


def _formant_axis_distance(
    attempt: np.ndarray,
    reference: np.ndarray,
    config: FrontendConfig = DEFAULT_CONFIG,
) -> float:
    """Vowel/formant axis (FR-11): mean relative formant mismatch.

    Praat Burg formants sampled at the D1 frame grid on both clips
    (vad-trimmed so the grids describe the same acoustic content);
    per-frame, per-formant relative difference |f_a − f_r| / f_r
    averaged over frames where BOTH clips have measurements (voiced
    regions). Unvoiced-dominant clips return the nan-mean over what
    exists; fully unmeasurable audio raises (the API maps decode-/
    voicing-level failures to 422s, not fake axis values).
    """
    rel = []
    for clip in (attempt, reference):
        if len(clip) < config.frame_length:
            raise ValueError("clip too short for formant analysis")
    a_trim = vad_trim(np.asarray(attempt, dtype=np.float64))
    r_trim = vad_trim(np.asarray(reference, dtype=np.float64))
    fa = formants_pitch(a_trim, config)["formants"]  # (T, 3)
    fr = formants_pitch(r_trim, config)["formants"]
    T = min(fa.shape[0], fr.shape[0])
    fa, fr = fa[:T], fr[:T]
    with np.errstate(invalid="ignore", divide="ignore"):
        rel = np.abs(fa - fr) / fr
    if not np.isfinite(rel).any():
        raise ValueError(
            "no voiced frames in either clip — formant axis unmeasurable"
        )
    return float(np.nanmean(rel))


def _duration_axis_distance(
    attempt: np.ndarray,
    reference: np.ndarray,
) -> float:
    """Duration axis (FR-11): |log(attempt/reference)| after vad-trim.

    Ratio r maps symmetrically (r and 1/r penalize equally), and a
    clip trimmed to near-zero length raises instead of scoring ∞.
    """
    la = len(vad_trim(np.asarray(attempt, dtype=np.float64)))
    lr = len(vad_trim(np.asarray(reference, dtype=np.float64)))
    if la <= 0 or lr <= 0:
        raise ValueError("empty clip after vad-trim — duration axis unmeasurable")
    return abs(math.log(la / lr))


# ----------------------------------------------------------------------
# scoring entry point


def score_attempt(
    attempt_audio: np.ndarray,
    reference_audio: np.ndarray,
    calibration: Calibration,
    reference_word: dict,
    config: FrontendConfig = DEFAULT_CONFIG,
) -> SpdScore:
    """Score one attempt against one reference clip (FR-10/FR-11).

    All four numbers come from the measured D₀ scales of the word's
    calibration corpus; nothing here can fabricate a similarity for an
    uncalibrated word (the API gates on :func:`load_calibration`).
    """
    a_mfcc = static_mfcc(attempt_audio, config)
    r_mfcc = static_mfcc(reference_audio, config)

    d, path = dtw_mean_distance(a_mfcc, r_mfcc, return_path=True)

    # Consonant-window spectral axis: DTW restricted to likely-
    # consonant frames of the attempt (slice taken from the attempt's
    # own voicing structure — the reference is the standard, the
    # attempt is the specimen under inspection).
    mask = _consonant_mask(attempt_audio, config)
    T = min(len(mask), a_mfcc.shape[0])
    a_cons = a_mfcc[:T][mask[:T]]
    if len(a_cons) == 0:
        raise ValueError("no consonant frames found — spectral axis unmeasurable")
    d_cons = dtw_mean_distance(a_cons, r_mfcc)

    d_form = _formant_axis_distance(attempt_audio, reference_audio, config)
    d_dur = _duration_axis_distance(attempt_audio, reference_audio)

    return SpdScore(
        similarity_pct=_norm_loglike_to_pct(d, calibration.d0),
        vowel_score=_norm_loglike_to_pct(d_form, calibration.d0_formant),
        consonant_score=_norm_loglike_to_pct(d_cons, calibration.d0),
        duration_score=_norm_loglike_to_pct(d_dur, calibration.d0_duration),
        mfcc_dtw_score=_norm_loglike_to_pct(d, calibration.d0),
        reference_word=dict(reference_word),
    )


# ----------------------------------------------------------------------
# calibration builder


class CalibrationBuilder:
    """Compute per-word D₀ scales from known-correct recitations.

    Usage: for each word, feed the canonical reference clip plus every
    known-correct recitation (ear-verified per DataIntegrity) via
    ``add_reference``; then ``build()`` writes/returns the calibration.
    D₀ = the mean DTW distance of those recitations to the reference —
    the population the score is calibrated against.
    """

    def __init__(self):
        self._refs: dict[str, list[np.ndarray]] = {}
        self._canonical: dict[str, np.ndarray] = {}

    def set_canonical(self, word_id: str, audio: np.ndarray) -> None:
        self._canonical[word_id] = np.asarray(audio, dtype=np.float64)

    def add_reference(self, word_id: str, audio: np.ndarray) -> None:
        self._refs.setdefault(word_id, []).append(np.asarray(audio, dtype=np.float64))

    def build_word(self, word_id: str) -> dict:
        if word_id not in self._canonical:
            raise ValueError(f"no canonical reference set for word '{word_id}'")
        refs = self._refs.get(word_id) or []
        if not refs:
            raise ValueError(
                f"no known-correct recitations added for word '{word_id}'"
            )
        canon = static_mfcc(self._canonical[word_id])
        d_list, d_form_list, d_dur_list = [], [], []
        for audio in refs:
            d_list.append(dtw_mean_distance(static_mfcc(audio), canon))
            d_form_list.append(
                _formant_axis_distance(audio, self._canonical[word_id])
            )
            d_dur_list.append(_duration_axis_distance(audio, self._canonical[word_id]))
        return {
            "d0": float(np.mean(d_list)),
            "d0_formant": float(np.mean(d_form_list)),
            "d0_duration": float(np.mean(d_dur_list)),
            "n_references": len(refs),
        }

    def build(
        self,
        provenance: dict | None = None,
        out_path: str | Path | None = None,
    ) -> dict:
        """Assemble the full calibration file (all words added)."""
        data = {
            "schema_version": CALIBRATION_SCHEMA_VERSION,
            "kind": "spd_calibration",
            "provenance": dict(provenance or {}),
            "words": {w: self.build_word(w) for w in sorted(self._canonical)},
        }
        if out_path is not None:
            p = Path(out_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        return data
