"""D3 · GVR verse recognizer (Phase 4 unit 4).

Implements the approved D3 topology (Review.md, Phase 3 sign-off —
the binding spec, cited verbatim):

    One GaussianHMM per verse: 6 states, left-to-right no-skip
    (self + advance-by-one only), diagonal Gaussians, hand-initialized
    startprob/transmat before fit() (hmmlearn has no L-R constructor —
    verified in Phase 2), Viterbi decode() across all verse HMMs →
    verse ID + log-likelihood gap as confidence.

Design contract notes:
- Features come from the D1 front-end (``extract_features``, the
  (T, 39) MFCC+Δ+ΔΔ CMVN matrix) — one feature definition for the
  whole pipeline (Ground Rule 4).
- Confidence is the softmax share of the closed-set log-likelihoods
  (a monotone function of the log-likelihood gaps: a verse that beats
  every other verse by a wide margin scores near 1, a near-tie scores
  near 1/n_verses). Shares are honest relative beliefs over the
  closed set — they say nothing about out-of-set audio, which is why
  the UI's "not confidently recognized" state is driven by explicit
  API responses, not by a threshold invented here.
- Persistence: ``data/gvr/model.pkl`` (a JSON envelope with a schema
  version and pickled GaussianHMM per verse). Missing file = no
  trained model: the API reports that explicitly, never guesses.
- Split policy is enforced upstream (``GvrRegistry.assert_no_split_leak``
  at registry load); training consumes only rows the registry allows.

All test fixtures are synthetic (NFR-02): pseudo-vowels with distinct
formant/pitch signatures, no corpus audio.
"""

from __future__ import annotations

import base64
import json
import pickle
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from hmmlearn.hmm import GaussianHMM

from samskrita_dhvani.frontend import (
    DEFAULT_CONFIG,
    FrontendConfig,
    extract_features,
)

__all__ = [
    "VERSE_HMM_SCHEMA_VERSION",
    "N_STATES",
    "GvrRecognizer",
    "VersePrediction",
]

VERSE_HMM_SCHEMA_VERSION = 1
"""Bump when the model envelope's fields/semantics change (Ground
Rule 4: regeneration must be detectable)."""

N_STATES = 6
"""D3: six states per verse HMM (documented, not a library default)."""

COVARIANCE_TYPE = "diag"
"""D3: diagonal Gaussians (documented, not a library default)."""

MODEL_DEFAULT_PATH = Path("data") / "gvr" / "model.pkl"


@dataclass(frozen=True)
class VersePrediction:
    """The FR-21 result for one recitation."""

    verse_id: str
    confidence: float
    """Softmax share of the top verse's log-likelihood, in (0, 1]."""
    candidates: list[dict]
    """Runner-up verses, ranked: [{verse_id, confidence}, ...]."""


def _hand_init_lrhmm(
    n_features: int,
    n_states: int = N_STATES,
    n_iter: int = 100,
    random_state: int | None = None,
) -> GaussianHMM:
    """A left-to-right no-skip GaussianHMM with hand-initialized
    startprob/transmat (D3) and NO auto-initialized emissions
    (``init_params=""``): the caller sets means/covars explicitly.
    """
    startprob = np.zeros(n_states)
    startprob[0] = 1.0
    transmat = np.zeros((n_states, n_states))
    for i in range(n_states - 1):
        transmat[i, i] = 0.5
        transmat[i, i + 1] = 0.5
    transmat[n_states - 1, n_states - 1] = 1.0

    model = GaussianHMM(
        n_components=n_states,
        covariance_type=COVARIANCE_TYPE,
        n_iter=n_iter,
        init_params="",
        params="stmc",
        random_state=random_state,
    )
    model.startprob_ = startprob
    model.transmat_ = transmat
    return model


def _segment_init_emissions(
    X: np.ndarray, n_states: int = N_STATES
) -> tuple[np.ndarray, np.ndarray]:
    """HTK-style equal-segmentation emission init.

    The concatenated training sequence is cut into ``n_states`` equal
    parts; each state's diagonal Gaussian starts at its part's mean and
    variance. This guarantees every state owns a region of the feature
    space at EM start — k-means init on near-stationary speech
    features can collapse states together, after which the L-R
    topology never visits them (zero transition rows → NaN at decode),
    which the synthetic-fixture tests caught on the first run.
    """
    bounds = np.linspace(0, len(X), n_states + 1).astype(int)
    means = np.zeros((n_states, X.shape[1]))
    covars = np.zeros((n_states, X.shape[1]))
    for s in range(n_states):
        seg = X[bounds[s] : bounds[s + 1]]
        if len(seg) == 0:
            means[s] = X.mean(axis=0)
            covars[s] = 1.0
        else:
            means[s] = seg.mean(axis=0)
            var = seg.var(axis=0) if len(seg) > 1 else np.ones(X.shape[1])
            covars[s] = np.maximum(var, 1e-3)  # floor: flat segments stay invertible
    return means, covars


def _assert_fitted_lrhmm(model: GaussianHMM, context: str) -> None:
    """Fail loudly if EM left the model degenerate (NaN parameters or
    states that were never observed). Such a model must not be stored —
    the verse needs more/better recitations, not a silent repair."""
    if not np.isfinite(model.startprob_).all() or not np.isfinite(model.transmat_).all():
        raise ValueError(
            f"{context}: EM produced NaN parameters (degenerate L-R "
            "training); more distinct training audio is needed"
        )
    dead = np.where(model.transmat_.sum(axis=1) == 0)[0]
    if dead.size:
        raise ValueError(
            f"{context}: states {dead.tolist()} were never visited during "
            "training (zero transition rows); more distinct training "
            "audio is needed"
        )


@dataclass
class _VerseModel:
    verse_id: str
    model: GaussianHMM
    n_training_clips: int


class GvrRecognizer:
    """One trained GaussianHMM per verse + Viterbi decoding (D3)."""

    def __init__(self, verses: dict[str, _VerseModel], verse_text: dict | None = None):
        if not verses:
            raise ValueError("a recognizer needs at least one trained verse")
        self.verses = verses
        self.verse_text = verse_text or {}

    # ------------------------------------------------------------ train

    @classmethod
    def train(
        cls,
        registry,
        audio_loader,
        config: FrontendConfig = DEFAULT_CONFIG,
        n_iter: int = 100,
        random_state: int | None = 0,
    ) -> "GvrRecognizer":
        """Fit one L-R HMM per verse from the registry's recitations.

        ``registry`` is a ``GvrRegistry`` (split-leak enforcement lives
        there). ``audio_loader`` maps an entry's ``audio_file`` path to
        a 1-D waveform at the D1 analysis rate — dependency-injected so
        tests can feed synthetic verses without touching disk.
        """
        by_verse: dict[str, list] = {}
        for entry in registry.entries:
            if entry.split != "train":
                continue  # held-out rows (validation/test) never train
            by_verse.setdefault(entry.verse_id, []).append(entry)

        verses: dict[str, _VerseModel] = {}
        verse_text: dict[str, dict] = {}
        for verse_id in sorted(by_verse):
            sequences = []
            text: dict = {}
            for e in by_verse[verse_id]:
                y = audio_loader(e.audio_file)
                feats = extract_features(y, config)
                if feats.shape[0] < N_STATES:
                    raise ValueError(
                        f"verse {verse_id}: clip '{e.audio_file}' yields only "
                        f"{feats.shape[0]} frames; the {N_STATES}-state L-R "
                        "topology needs at least that many"
                    )
                sequences.append(feats)
                if e.devanagari_text and "devanagari" not in text:
                    text["devanagari"] = e.devanagari_text
            X = np.concatenate(sequences, axis=0).astype(np.float64)
            lengths = [s.shape[0] for s in sequences]
            hmm = _hand_init_lrhmm(X.shape[1], n_iter=n_iter,
                                   random_state=random_state)
            hmm.means_, hmm.covars_ = _segment_init_emissions(X)
            hmm.fit(X, lengths)
            _assert_fitted_lrhmm(hmm, f"verse {verse_id}")
            verses[verse_id] = _VerseModel(
                verse_id=verse_id, model=hmm, n_training_clips=len(sequences)
            )
            if text:
                verse_text[verse_id] = text
        return cls(verses, verse_text)

    # ---------------------------------------------------------- decode

    @property
    def verse_ids(self) -> list[str]:
        return sorted(self.verses)

    def __len__(self) -> int:
        return len(self.verses)

    def predict(
        self,
        audio: np.ndarray,
        config: FrontendConfig = DEFAULT_CONFIG,
    ) -> VersePrediction:
        """Viterbi-decode the clip against every verse HMM (FR-21)."""
        feats = extract_features(np.asarray(audio), config)
        loglikes = np.array(
            [
                self.verses[vid].model.decode(feats, algorithm="viterbi")[0]
                for vid in self.verse_ids
            ]
        )
        ranks = np.argsort(-loglikes)
        # Softmax over the closed set = monotone map of the pairwise
        # log-likelihood gaps (D3's "log-likelihood gap as confidence").
        shifted = loglikes - loglikes.max()
        p = np.exp(shifted)
        p /= p.sum()
        order = list(self.verse_ids)
        top = order[int(ranks[0])]
        candidates = [
            {"verse_id": order[i], "confidence": float(p[i])}
            for i in ranks[1:]
        ]
        return VersePrediction(
            verse_id=top,
            confidence=float(p[int(ranks[0])]),
            candidates=candidates,
        )

    def text_for(self, verse_id: str) -> dict:
        """Verse presentation text recorded at training time, if any."""
        t = self.verse_text.get(verse_id, {})
        return {"devanagari": t.get("devanagari"), "gloss": t.get("gloss")}

    # ------------------------------------------------------------ io

    def save(self, path: str | Path = MODEL_DEFAULT_PATH) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": VERSE_HMM_SCHEMA_VERSION,
            "kind": "gvr_verse_hmms",
            "n_states": N_STATES,
            "covariance_type": COVARIANCE_TYPE,
            "verse_text": self.verse_text,
            "verses": {
                vid: {
                    "n_training_clips": vm.n_training_clips,
                    "model_pickle": base64.b64encode(
                        pickle.dumps(vm.model)
                    ).decode("ascii"),
                }
                for vid, vm in sorted(self.verses.items())
            },
        }
        p.write_text(json.dumps(payload), encoding="utf-8")
        return p

    @classmethod
    def load(
        cls, path: str | Path = MODEL_DEFAULT_PATH
    ) -> "GvrRecognizer | None":
        """Load a trained recognizer, or None if none exists.

        A wrong schema/kind raises (regeneration must be detectable);
        an absent file is an honest miss the API surfaces as 503.
        """
        p = Path(path)
        if not p.is_file():
            return None
        data = json.loads(p.read_text(encoding="utf-8"))
        if data.get("schema_version") != VERSE_HMM_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported gvr model schema_version: {data.get('schema_version')}"
            )
        if data.get("kind") != "gvr_verse_hmms":
            raise ValueError("not a gvr_verse_hmms file")
        verses = {}
        for vid, entry in data["verses"].items():
            model = pickle.loads(base64.b64decode(entry["model_pickle"]))
            verses[vid] = _VerseModel(
                verse_id=vid,
                model=model,
                n_training_clips=int(entry["n_training_clips"]),
            )
        return cls(verses, data.get("verse_text", {}))
