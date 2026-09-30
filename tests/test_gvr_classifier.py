"""Tests for the D3 GVR recognizer (Phase 4 unit 4).

All fixtures are synthetic (NFR-02): each "verse" is a fixed sequence
of four pseudo-vowel phones with distinct formant targets plus short
gaps — temporal structure that survives D1's per-utterance CMVN (a
stationary tone would be normalized into near-nothing, which is a
property of the pipeline, not a bug). No corpus audio. The properties
mirror the Phase 3 test plan: L-R transmat row-stochasticity +
no-backward-transitions, and a Viterbi decode smoke on synthetic
sequences.
"""

import io
import json
import wave
import zlib

import numpy as np
import pytest

from samskrita_dhvani.gvr_classifier import (
    COVARIANCE_TYPE,
    N_STATES,
    VERSE_HMM_SCHEMA_VERSION,
    GvrRecognizer,
    _hand_init_lrhmm,
    _segment_init_emissions,
)
from samskrita_dhvani.registry import GvrRegistry, VerseEntry

SR = 16000
VERSE_IDS = ("2.13", "4.07", "9.26", "18.66")


def _stable_seed(text: str) -> int:
    """Deterministic across processes (hash() is salted per run)."""
    return zlib.crc32(text.encode("utf-8"))


def verse_plan(verse_id: str):
    """A verse's fixed phone plan: base F0 + four formant-target
    triples. Same for every recitation of the verse (up to jitter)."""
    rng = np.random.default_rng(_stable_seed("plan:" + verse_id))
    f0 = float(rng.uniform(100, 180))
    phones = [
        (
            float(rng.uniform(300, 800)),
            float(rng.uniform(900, 2200)),
            float(rng.uniform(2400, 3000)),
        )
        for _ in range(4)
    ]
    return f0, phones


def pseudo_vowel(dur=0.3, f0=150, formants=(700.0, 1200.0, 2600.0), seed=0,
                 sr=SR):
    """Harmonic stack shaped by three formant gaussians, raised-cosine
    envelope — a voiced phone with a defined spectral signature."""
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
    return 0.3 * y * env / (np.max(np.abs(y)) + 1e-12)


def render_verse(verse_id: str, f0_jitter=0.02, seed=0, sr=SR):
    """Render a recitation: the verse's phone plan with per-recitation
    F0 jitter, timing jitter, and noise (same plan, new rendition)."""
    f0_base, phones = verse_plan(verse_id)
    rng = np.random.default_rng(seed)
    parts = []
    for i, formants in enumerate(phones):
        f0 = f0_base * (1 + rng.uniform(-f0_jitter, f0_jitter))
        dur = 0.30 * (1 + rng.uniform(-0.1, 0.1))
        parts.append(
            pseudo_vowel(dur=dur, f0=f0, formants=formants,
                         seed=int(rng.integers(2**31)), sr=sr)
        )
        if i < len(phones) - 1:
            parts.append(np.zeros(int(sr * 0.05)))
    return np.concatenate(parts)


def _wav_bytes(y):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(y, -1, 1) * 32767).astype("<i2").tobytes())
    return buf.getvalue()


def make_registry(tmp_path):
    """A 4-verse synthetic registry: 2 train + 1 test recitation per
    verse, written as real WAV files so the loader path is exercised."""
    entries = []
    for vid in VERSE_IDS:
        for r in range(3):
            y = render_verse(vid, seed=_stable_seed(f"{vid}:{r}"))
            p = tmp_path / f"v{vid.replace('.', '_')}_{r}.wav"
            p.write_bytes(_wav_bytes(y))
            entries.append(
                VerseEntry(
                    verse_id=vid,
                    audio_file=str(p),
                    reciter=f"reciter-{r}",
                    split="train" if r < 2 else "test",
                    devanagari_text=f"॥ {vid} ॥" if r == 0 else None,
                    provenance={"source_id": "SYNTHETIC",
                                "acquired_on": "2026-10-01"},
                )
            )
    return GvrRegistry(entries)


def _load_wav(path):
    with wave.open(str(path), "rb") as w:
        y = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
    return (y / 32767.0).astype(np.float32)


# ------------------------------------------------------- topology (D3)

def test_hand_init_is_left_right_no_skip():
    m = _hand_init_lrhmm(39)
    assert m.n_components == N_STATES == 6
    assert m.covariance_type == COVARIANCE_TYPE == "diag"
    assert m.startprob_[0] == 1.0 and m.startprob_.sum() == 1.0
    for i in range(N_STATES):
        for j in range(N_STATES):
            expected = 0.0
            if j == i:
                expected = 0.5 if i < N_STATES - 1 else 1.0
            elif j == i + 1:
                expected = 0.5
            assert m.transmat_[i, j] == expected, (i, j)
            if j < i:
                assert m.transmat_[i, j] == 0.0  # no backward transitions


def test_fit_preserves_hand_topology():
    rng = np.random.default_rng(3)
    m = _hand_init_lrhmm(39, n_iter=10, random_state=0)
    X = rng.normal(size=(300, 39))
    m.means_, m.covars_ = _segment_init_emissions(X)
    m.fit(X)
    assert np.allclose(m.transmat_.sum(axis=1), 1.0)  # row-stochastic
    assert all(m.transmat_[i, j] == 0.0 for i in range(N_STATES)
               for j in range(i))  # still no backward after EM
    assert m.startprob_[0] == 1.0


# ------------------------------------------------------------- training

def test_train_one_model_per_verse_from_train_split_only(tmp_path):
    reg = make_registry(tmp_path)
    rec = GvrRecognizer.train(reg, _load_wav)
    assert set(rec.verse_ids) == set(VERSE_IDS)
    assert len(rec) == 4
    for vid in rec.verse_ids:
        assert rec.verses[vid].n_training_clips == 2  # train split only


def test_train_too_short_clip_raises(tmp_path):
    reg = make_registry(tmp_path)
    short = tmp_path / "short.wav"
    short.write_bytes(
        _wav_bytes(np.zeros(int(SR * 0.02), dtype="<i2").astype(np.float32) / 32767)
    )
    entries = list(reg.entries)
    entries.append(
        VerseEntry(
            verse_id="2.13",
            audio_file=str(short),
            reciter="tiny",
            split="train",
            provenance={"source_id": "SYNTHETIC", "acquired_on": "2026-10-01"},
        )
    )
    with pytest.raises(ValueError, match="at least that many"):
        GvrRecognizer.train(GvrRegistry(entries), _load_wav)


# --------------------------------------------------------- recognition

def test_predict_identifies_the_correct_synthetic_verse(tmp_path):
    reg = make_registry(tmp_path)
    rec = GvrRecognizer.train(reg, _load_wav)
    for vid in VERSE_IDS:
        # Held-out rendition: same plan, unseen jitter/noise seed.
        y = render_verse(vid, f0_jitter=0.03, seed=_stable_seed("held:" + vid))
        pred = rec.predict(y)
        assert pred.verse_id == vid, (vid, pred.verse_id, pred.confidence)
        assert 0 < pred.confidence <= 1.0
        ranked = [c["verse_id"] for c in pred.candidates]
        assert set(ranked) == set(VERSE_IDS) - {vid}
        confs = [pred.confidence] + [c["confidence"] for c in pred.candidates]
        assert all(a >= b for a, b in zip(confs, confs[1:]))  # rank-monotone
        assert abs(sum(confs) - 1.0) < 1e-9   # softmax shares, closed set


def test_predict_survives_heavy_recitation_jitter(tmp_path):
    reg = make_registry(tmp_path)
    rec = GvrRecognizer.train(reg, _load_wav)
    y = render_verse("4.07", f0_jitter=0.06, seed=_stable_seed("jitter"))
    assert rec.predict(y).verse_id == "4.07"


def test_predict_no_spurious_verse_ids(tmp_path):
    reg = make_registry(tmp_path)
    rec = GvrRecognizer.train(reg, _load_wav)
    y = render_verse("2.13", seed=_stable_seed("probe"))
    pred = rec.predict(y)
    assert pred.verse_id in VERSE_IDS
    assert all(c["verse_id"] in VERSE_IDS for c in pred.candidates)


# ----------------------------------------------------------------- text

def test_text_for_returns_recorded_training_text(tmp_path):
    reg = make_registry(tmp_path)
    rec = GvrRecognizer.train(reg, _load_wav)
    assert rec.text_for("9.26")["devanagari"] == "॥ 9.26 ॥"
    assert rec.text_for("4.07").get("devanagari") is None or \
        "4.07" in rec.verse_text  # only rows that carried text


# -------------------------------------------------------------------- io

def test_save_load_round_trip_preserves_predictions(tmp_path):
    reg = make_registry(tmp_path)
    rec = GvrRecognizer.train(reg, _load_wav)
    p = rec.save(tmp_path / "model.pkl")
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["schema_version"] == VERSE_HMM_SCHEMA_VERSION == 1
    assert data["kind"] == "gvr_verse_hmms"
    rec2 = GvrRecognizer.load(p)
    y = render_verse("9.26", seed=_stable_seed("roundtrip"))
    a, b = rec.predict(y), rec2.predict(y)
    assert a.verse_id == b.verse_id
    assert a.confidence == pytest.approx(b.confidence)
    assert [c["verse_id"] for c in a.candidates] == [
        c["verse_id"] for c in b.candidates
    ]


def test_load_absent_model_is_none(tmp_path):
    assert GvrRecognizer.load(tmp_path / "missing.pkl") is None


def test_load_wrong_schema_raises(tmp_path):
    p = tmp_path / "bad.pkl"
    p.write_text(json.dumps({"schema_version": 99, "kind": "gvr_verse_hmms",
                             "verses": {}}), encoding="utf-8")
    with pytest.raises(ValueError, match="schema_version"):
        GvrRecognizer.load(p)
