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


def test_spd_score_valid_request_honest_503_until_scorer_lands():
    """Ground Rule 1 in the UI: a valid attempt must NOT get a fake
    score — it gets an explicit model_unavailable until D2 exists."""
    from samskrita_dhvani.registry import harvard_kyoto_slug, iast_to_devanagari

    word_id = harvard_kyoto_slug(iast_to_devanagari("kṛṣṇa"))
    r = client.post(
        "/api/spd/score",
        files={"audio": ("a.wav", GOOD_WAV, "audio/wav")},
        data={"word_id": word_id},
    )
    assert r.status_code == 503
    body = r.json()["detail"]
    assert body["error"] == "model_unavailable"
    assert "D2" in body["detail"]


# ----------------------------------------------------- /api/gvr/recognize

def test_gvr_recognize_garbage_audio_is_422():
    r = client.post(
        "/api/gvr/recognize",
        files={"audio": ("a.wav", NOT_AUDIO, "audio/wav")},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "invalid_audio"


def test_gvr_recognize_valid_request_honest_503_until_model_lands():
    r = client.post(
        "/api/gvr/recognize",
        files={"audio": ("a.wav", GOOD_WAV, "audio/wav")},
    )
    assert r.status_code == 503
    body = r.json()["detail"]
    assert body["error"] == "model_unavailable"


# ------------------------------------------------------------ static UI

def test_web_mount_serves_index_when_present():
    """If web/ exists it must serve; if not, this is skipped — the
    mount is conditional by design (API-only runs stay valid)."""
    from samskrita_dhvani.api import PROJECT_ROOT

    if not (PROJECT_ROOT / "web").is_dir():
        pytest.skip("web/ not created yet (Stitch exports pending)")
    r = client.get("/")
    assert r.status_code == 200
