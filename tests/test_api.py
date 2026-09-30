"""Tests for the demo API (Frontend.md §4 data contract).

All requests use synthetic in-memory audio — no corpus audio and no
network. The contract under test: real registry data out, honest
error states (never placeholder scores), Ground Rule 1 in the UI.
"""

import io
import struct
import wave

import numpy as np
import pytest
from fastapi.testclient import TestClient

from samskrita_dhvani.api import app

client = TestClient(app)


def _wav_bytes(freq_hz: int = 220, seconds: float = 1.0, sr: int = 16000) -> bytes:
    """Synthetic 16-bit mono PCM WAV (NFR-02 fixture, not corpus audio)."""
    n = int(sr * seconds)
    t = np.arange(n) / sr
    y = 0.4 * np.sin(2 * np.pi * freq_hz * t).astype(np.float32)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        frames = b"".join(
            struct.pack("<h", int(np.clip(s, -1, 1) * 32767)) for s in y
        )
        w.writeframes(frames)
    return buf.getvalue()


GOOD_WAV = _wav_bytes()
SHORT_WAV = _wav_bytes(seconds=0.05)
NOT_AUDIO = b"this is definitely not an audio file" * 40


# ------------------------------------------------------------- /api/words

def test_words_endpoint_returns_real_registry():
    r = client.get("/api/words")
    assert r.status_code == 200
    body = r.json()
    assert body["reference_audio_available"] is False  # ear check pending
    assert len(body["words"]) >= 20                    # FR-12 minimum
    w = body["words"][0]
    assert set(w) == {
        "word_id", "devanagari", "iast", "difficulty_axis", "pair_id",
        "reference_audio_url",
    }
    assert w["reference_audio_url"] is None            # honest empty state


def test_words_rows_are_transliteration_consistent():
    from samskrita_dhvani.registry import (
        devanagari_to_iast,
        transliteration_round_trip_ok,
    )
    r = client.get("/api/words")
    for w in r.json()["words"]:
        assert devanagari_to_iast(w["devanagari"]) == w["iast"]
        assert transliteration_round_trip_ok(w["devanagari"], w["iast"])


# ------------------------------------------------------------ /api/status

def test_status_reports_real_counts_and_honest_gaps():
    r = client.get("/api/status")
    assert r.status_code == 200
    body = r.json()
    assert body["word_count"] >= 20                    # real FR-12 count
    assert body["spd_reference_audio_available"] is False
    assert body["gvr_scorer_available"] is False       # D3 not built yet
    vc = body["verse_coverage"]
    assert vc["available"] is False                    # registry empty
    assert "blocked" in vc["detail"].lower() or "no gvr registry" in vc["detail"].lower()
    assert body["generated_at"]                        # real timestamp


def test_status_sweep_summary_depends_on_corpus_presence():
    r = client.get("/api/status")
    sweep = r.json()["last_sweep"]
    # Either real numbers (corpus on this machine) or an explicit
    # honest-missing detail — never invented values.
    if sweep["available"]:
        assert sweep["files_swept"] > 0
        assert sweep["total_hours"] > 0
        assert sweep["last_sweep_date"]
    else:
        assert "MANIFEST" in sweep["detail"] or "PROVENANCE" in sweep["detail"]


# -------------------------------------------------------- /api/spd/score

def test_spd_score_unknown_word_is_404():
    r = client.post(
        "/api/spd/score",
        files={"audio": ("a.wav", GOOD_WAV, "audio/wav")},
        data={"word_id": "notAWord"},
    )
    assert r.status_code == 404
    assert r.json()["detail"]["error"] == "unknown_word"


def test_spd_score_garbage_audio_is_422():
    from samskrita_dhvani.registry import harvard_kyoto_slug, iast_to_devanagari

    word_id = harvard_kyoto_slug(iast_to_devanagari("kṛṣṇa"))
    r = client.post(
        "/api/spd/score",
        files={"audio": ("a.wav", NOT_AUDIO, "audio/wav")},
        data={"word_id": word_id},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "invalid_audio"


def test_spd_score_too_short_audio_is_422():
    from samskrita_dhvani.registry import harvard_kyoto_slug, iast_to_devanagari

    word_id = harvard_kyoto_slug(iast_to_devanagari("kṛṣṇa"))
    r = client.post(
        "/api/spd/score",
        files={"audio": ("a.wav", SHORT_WAV, "audio/wav")},
        data={"word_id": word_id},
    )
    assert r.status_code == 422
    assert "short" in r.json()["detail"]["detail"].lower()


def test_spd_score_tone_fixture_is_near_silence_422():
    """DataIntegrity §1.1 at the API boundary: a pure sine is not
    speech — WebRTC VAD measures ~9% speech frames on the 220 Hz tone
    fixture, below the 10% gate, so the honest answer is invalid input,
    not a score or a model error."""
    from samskrita_dhvani.registry import harvard_kyoto_slug, iast_to_devanagari

    word_id = harvard_kyoto_slug(iast_to_devanagari("kṛṣṇa"))
    r = client.post(
        "/api/spd/score",
        files={"audio": ("a.wav", GOOD_WAV, "audio/wav")},
        data={"word_id": word_id},
    )
    assert r.status_code == 422
    body = r.json()["detail"]
    assert body["error"] == "near_silence"
    assert "DataIntegrity" in body["detail"]


def _speech_wav_bytes(seconds=1.0, seed=0):
    """Harmonic-stack speech-like WAV (voiced, VAD-detectable)."""
    sr = 16000
    t = np.arange(int(sr * seconds)) / sr
    y = np.zeros_like(t)
    for k in (1, 2, 3, 4, 5):
        y += np.sin(2 * np.pi * 130 * k * t) / k
    env = 0.5 * (1 - np.cos(np.pi * np.minimum(1.0, t / seconds)))
    y = 0.35 * y * env
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"".join(
            struct.pack("<h", int(np.clip(s, -1, 1) * 32767)) for s in y
        ))
    return buf.getvalue()


def test_spd_score_speech_audio_honest_503_reference_unavailable():
    """D2 is implemented, but its first data prerequisite is missing:
    no ear-verified reference clip exists yet (Hall/Loyola ear check
    pending), so the endpoint says exactly that — never a guess."""
    from samskrita_dhvani.registry import harvard_kyoto_slug, iast_to_devanagari

    word_id = harvard_kyoto_slug(iast_to_devanagari("kṛṣṇa"))
    r = client.post(
        "/api/spd/score",
        files={"audio": ("a.wav", _speech_wav_bytes(), "audio/wav")},
        data={"word_id": word_id},
    )
    assert r.status_code == 503
    body = r.json()["detail"]
    assert body["error"] == "reference_unavailable"
    assert "ear check" in body["detail"]


def test_spd_score_503_calibration_unavailable_when_reference_exists(
    tmp_path, monkeypatch
):
    """With a reference clip on disk but no measured D0, the seam must
    still refuse to invent the scale (D2 forbids guessed D0)."""
    from samskrita_dhvani import api as api_mod
    from samskrita_dhvani.registry import harvard_kyoto_slug, iast_to_devanagari

    ref_root = tmp_path / "refs"
    ref_root.mkdir()
    (ref_root / "kRSNa.wav").write_bytes(_speech_wav_bytes())
    monkeypatch.setattr(api_mod, "SPD_REFERENCE_ROOT", ref_root)

    word_id = harvard_kyoto_slug(iast_to_devanagari("kṛṣṇa"))
    r = client.post(
        "/api/spd/score",
        files={"audio": ("a.wav", _speech_wav_bytes(seed=1), "audio/wav")},
        data={"word_id": word_id},
    )
    assert r.status_code == 503
    body = r.json()["detail"]
    assert body["error"] == "calibration_unavailable"
    assert "D0" in body["detail"]


def test_spd_score_200_full_contract_when_reference_and_calibration_exist(
    tmp_path, monkeypatch
):
    """The FR-11 200 path end-to-end: real D1 features, real D2 DTW
    scoring; only the data prerequisites (reference file + measured
    scale) are provided as test doubles."""
    from samskrita_dhvani import api as api_mod
    from samskrita_dhvani.registry import harvard_kyoto_slug, iast_to_devanagari
    from samskrita_dhvani.spd_scorer import Calibration

    # Reference clip on disk: a fixed-formant synthetic vowel.
    sr = 16000
    t = np.arange(sr) / sr
    ref = sum(np.sin(2 * np.pi * 140 * k * t) / k for k in (1, 2, 3, 4, 5))
    ref = (0.3 * ref / np.max(np.abs(ref))).astype(np.float32)
    ref_root = tmp_path / "refs"
    ref_root.mkdir()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"".join(
            struct.pack("<h", int(np.clip(s, -1, 1) * 32767)) for s in ref
        ))
    (ref_root / "kRSNa.wav").write_bytes(buf.getvalue())
    monkeypatch.setattr(api_mod, "SPD_REFERENCE_ROOT", ref_root)

    cal = Calibration(
        word_id="kRSNa", d0=3.0, d0_formant=0.08, d0_duration=0.15,
        n_references=3, schema_version=1,
    )
    monkeypatch.setattr(api_mod, "load_calibration", lambda wid: cal)

    word_id = harvard_kyoto_slug(iast_to_devanagari("kṛṣṇa"))
    r = client.post(
        "/api/spd/score",
        files={"audio": ("a.wav", _speech_wav_bytes(), "audio/wav")},
        data={"word_id": word_id},
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert set(body) == {
        "similarity_pct", "vowel_score", "consonant_score",
        "duration_score", "mfcc_dtw_score", "reference_word",
    }
    for key in ("similarity_pct", "vowel_score", "consonant_score",
                "duration_score", "mfcc_dtw_score"):
        assert 0.0 < body[key] <= 100.0, (key, body[key])
    assert body["reference_word"] == {
        "word_id": word_id, "devanagari": "कृष्ण", "iast": "kṛṣṇa",
    }


# ----------------------------------------------------- /api/gvr/recognize

def _make_synthetic_gvr_registry(tmp_path):
    """Small synthetic GVR registry (2 train rows per verse) for the
    200-path test; verses are temporally structured so they survive
    D1's CMVN (see tests/test_gvr_classifier.py for the reasoning)."""
    from tests.test_gvr_classifier import (
        VERSE_IDS,
        render_verse,
        _wav_bytes as _verse_wav_bytes,
    )
    from samskrita_dhvani.registry import VerseEntry, GvrRegistry
    import zlib

    entries = []
    for vid in VERSE_IDS:
        for r in range(2):
            y = render_verse(vid, seed=zlib.crc32(f"api:{vid}:{r}".encode()))
            p = tmp_path / f"gvr_{vid.replace('.', '_')}_{r}.wav"
            p.write_bytes(_verse_wav_bytes(y))
            entries.append(
                VerseEntry(
                    verse_id=vid,
                    audio_file=str(p),
                    reciter=f"reciter-{r}",
                    split="train",
                    devanagari_text=f"॥ {vid} ॥" if r == 0 else None,
                    provenance={"source_id": "SYNTHETIC",
                                "acquired_on": "2026-10-01"},
                )
            )
    return GvrRegistry(entries)


def _train_synthetic_gvr(registry):
    from tests.test_gvr_classifier import _load_wav
    from samskrita_dhvani.gvr_classifier import GvrRecognizer

    return GvrRecognizer.train(registry, _load_wav)


def test_gvr_recognize_tone_fixture_is_near_silence_422():
    """Same DataIntegrity §1.1 gate as SPD, now first in the chain: the
    220 Hz sine is not speech (VAD ≈ 9%), so invalid input — not a
    model error — is the honest response."""
    r = client.post(
        "/api/gvr/recognize",
        files={"audio": ("a.wav", GOOD_WAV, "audio/wav")},
    )
    assert r.status_code == 422
    body = r.json()["detail"]
    assert body["error"] == "near_silence"


def test_gvr_recognize_speech_honest_503_while_model_missing():
    """D3 is implemented; with no trained artifact on disk the endpoint
    names exactly that (plus the registry state), never a guess."""
    from tests.test_api import _speech_wav_bytes

    r = client.post(
        "/api/gvr/recognize",
        files={"audio": ("a.wav", _speech_wav_bytes(), "audio/wav")},
    )
    assert r.status_code == 503
    body = r.json()["detail"]
    assert body["error"] == "model_unavailable"
    assert "data/gvr/model.pkl" in body["detail"]
    assert "FR-22" in body["detail"]


def test_gvr_recognize_200_full_contract_with_trained_model(
    tmp_path, monkeypatch
):
    """The FR-21 200 path end-to-end: train the real D3 recognizer on
    synthetic verses, point GVR_MODEL_PATH at it, submit a held-out
    recitation, and verify the exact response contract."""
    from samskrita_dhvani import api as api_mod
    from tests.test_gvr_classifier import render_verse, _wav_bytes

    reg = _make_synthetic_gvr_registry(tmp_path)
    rec = _train_synthetic_gvr(reg)
    model_path = tmp_path / "model.pkl"
    rec.save(model_path)
    monkeypatch.setattr(api_mod, "GVR_MODEL_PATH", model_path)

    y = render_verse("2.13", f0_jitter=0.03,
                     seed=12345)  # held-out rendition
    r = client.post(
        "/api/gvr/recognize",
        files={"audio": ("a.wav", _wav_bytes(y), "audio/wav")},
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert set(body) == {"top_match", "candidates"}
    tm = body["top_match"]
    assert set(tm) == {"verse_id", "devanagari", "gloss", "confidence"}
    assert tm["verse_id"] == "2.13"
    assert 0 < tm["confidence"] <= 1.0
    assert tm["devanagari"] == "॥ 2.13 ॥"  # recorded at training time
    assert {c["verse_id"] for c in body["candidates"]} == {
        "4.07", "9.26", "18.66"
    }
    for c in body["candidates"]:
        assert set(c) == {"verse_id", "confidence"}
        # Runner-up shares may underflow to exact 0.0 in float64 when a
        # verse is thousands of nats behind the top match — exp(-2000)
        # IS 0.0 to the machine. Zero here means 'vanishingly unlikely',
        # which is the honest value, so the bound is inclusive.
        assert 0.0 <= c["confidence"] < tm["confidence"]


# ------------------------------------------------------------ static UI

def test_web_mount_serves_index_when_present():
    """If web/ exists it must serve; if not, this is skipped — the
    mount is conditional by design (API-only runs stay valid)."""
    from samskrita_dhvani.api import PROJECT_ROOT

    if not (PROJECT_ROOT / "web").is_dir():
        pytest.skip("web/ not created yet (Stitch exports pending)")
    r = client.get("/")
    assert r.status_code == 200
