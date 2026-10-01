"""Tests for the D5 recording-booth capture server (record.py).

The discipline under test (DataIntegrity §2/§5, RecordingProtocol):
uploads land only in ``data/_incoming/<session>/``; every take is
decoded with the real D1 loader and VAD-gated; rejected takes never
touch disk; take numbers are server-computed; nothing is ever written
into the corpus tree (``data/spd/``) — promotion is a separate,
deliberate step that only emits a mapping.
"""

from __future__ import annotations

import io
import json
import struct
import wave

import numpy as np
import pytest
from fastapi.testclient import TestClient

from samskrita_dhvani import record as record_mod
from samskrita_dhvani.frontend import load_audio_16k


# ------------------------------------------------------------ fixtures

def _wav_bytes(y: np.ndarray, sr: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"".join(
            struct.pack("<h", int(np.clip(s, -1, 1) * 32767)) for s in y
        ))
    return buf.getvalue()


def _speech_wav_bytes(seconds: float = 1.0, f0: float = 130.0) -> bytes:
    """Harmonic-stack voiced WAV (the same VAD-detectable shape the API
    tests use)."""
    sr = 16000
    t = np.arange(int(sr * seconds)) / sr
    y = np.zeros_like(t)
    for k in (1, 2, 3, 4, 5):
        y += np.sin(2 * np.pi * f0 * k * t) / k
    env = 0.5 * (1 - np.cos(np.pi * np.minimum(1.0, t / seconds)))
    return _wav_bytes(0.35 * y * env)


def _silence_wav_bytes(seconds: float = 1.0) -> bytes:
    return _wav_bytes(np.zeros(int(16000 * seconds), dtype=np.float32))


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """TestClient with the incoming tree redirected to tmp_path."""
    monkeypatch.setattr(record_mod, "INCOMING_ROOT", tmp_path / "_incoming")
    return TestClient(record_mod.app)


@pytest.fixture()
def session_id(client):
    r = client.post(
        "/api/record/session",
        data={
            "reciter": "test_reciter",
            "location": "quiet room, curtains closed",
            "device": "test mic, 20 cm",
            "consent": "true",
            "source_id": "SPD-D5-SELF",
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["session_id"]


# --------------------------------------------------------------- words

def test_words_endpoint_lists_seed_wordlist(client):
    r = client.get("/api/record/words")
    assert r.status_code == 200
    body = r.json()
    ids = [w["word_id"] for w in body["words"]]
    assert "kRSNa" in ids and "tAla" in ids          # HK slugs, case-significant
    assert len(ids) == 27                             # seed list size
    assert all({"word_id", "devanagari", "iast", "difficulty_axis"} <= set(w)
               for w in body["words"])


# ------------------------------------------------------------- session

def test_session_refuses_missing_consent_or_fields(client):
    r = client.post("/api/record/session", data={
        "reciter": "x", "location": "y", "device": "z", "consent": "false",
    })
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "consent_required"

    r = client.post("/api/record/session", data={
        "reciter": "x", "location": "", "device": "z", "consent": "true",
    })
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "bad_session_fields"


def test_session_sheet_records_provenance_fields(client):
    r = client.post("/api/record/session", data={
        "reciter": "Asha Rao", "location": "study", "device": "usb mic",
        "consent": "true", "source_id": "SPD-D5-SELF",
    })
    assert r.status_code == 200
    meta = r.json()["meta"]
    assert meta["reciter"] == "Asha Rao"
    assert meta["reciter_slug"] == "asha_rao"
    assert meta["consent_confirmed"] is True
    assert meta["source_id"] == "SPD-D5-SELF"
    assert meta["protocol"].endswith("RecordingProtocol.md")


# -------------------------------------------------------------- upload

def test_upload_happy_path_lands_in_incoming_with_sidecar(client, session_id, tmp_path):
    r = client.post(
        "/api/record/upload",
        data={"session_id": session_id, "word_id": "kRSNa", "role": "canonical"},
        files={"audio": ("take.wav", _speech_wav_bytes(1.0), "audio/wav")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["file"] == "spd_kRSNa_canonical_t0.wav"
    assert 0.9 < body["duration_s"] <= 1.2
    assert body["vad_speech_fraction"] > 0.10

    sess = record_mod.INCOMING_ROOT / session_id
    wav = sess / body["file"]
    assert wav.is_file()

    # The stored clip decodes with the real D1 loader at 16 kHz mono.
    y = load_audio_16k(str(wav))
    assert y.dtype == np.float32 and len(y) == int(16000 * body["duration_s"])

    # Per-clip checklist sidecar (RecordingProtocol §2 row).
    cl = json.loads((sess / "spd_kRSNa_canonical_t0.checklist.json").read_text())
    assert cl["item"] == "kRSNa" and cl["take"] == 0 and cl["role"] == "canonical"
    assert cl["session_id"] == session_id
    assert cl["vad_speech_fraction"] == pytest.approx(
        body["vad_speech_fraction"], abs=1e-6
    )

    # Session sheet carries reciter/device/consent (Rule 2).
    meta = json.loads((sess / "session_meta.json").read_text())
    assert meta["reciter"] == "test_reciter"
    assert meta["takes"]["kRSNa"]["canonical"][0]["file"] == body["file"]

    # Nothing outside the session dir was created.
    assert list(record_mod.INCOMING_ROOT.iterdir()) == [sess]


def test_upload_rejects_invalid_audio_without_storing(client, session_id):
    r = client.post(
        "/api/record/upload",
        data={"session_id": session_id, "word_id": "kRSNa", "role": "recitation"},
        files={"audio": ("take.wav", b"this is not audio" * 100, "audio/wav")},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "invalid_audio"
    sess = record_mod.INCOMING_ROOT / session_id
    assert not any(sess.glob("*.wav"))  # loud rejection, nothing stored


def test_upload_rejects_near_silence_per_dataintegrity(client, session_id):
    r = client.post(
        "/api/record/upload",
        data={"session_id": session_id, "word_id": "kRSNa", "role": "recitation"},
        files={"audio": ("take.wav", _silence_wav_bytes(1.0), "audio/wav")},
    )
    assert r.status_code == 422
    body = r.json()["detail"]
    assert body["error"] == "near_silence"
    assert "DataIntegrity" in body["detail"]
    assert not any((record_mod.INCOMING_ROOT / session_id).glob("*.wav"))


def test_upload_rejects_unknown_word_and_bad_role(client, session_id):
    r = client.post(
        "/api/record/upload",
        data={"session_id": session_id, "word_id": "notAWord", "role": "canonical"},
        files={"audio": ("t.wav", _speech_wav_bytes(), "audio/wav")},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "unknown_word"

    r = client.post(
        "/api/record/upload",
        data={"session_id": session_id, "word_id": "kRSNa", "role": "verse"},
        files={"audio": ("t.wav", _speech_wav_bytes(), "audio/wav")},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "bad_role"


def test_take_numbers_are_server_computed_and_append_only(client, session_id):
    """Three uploads → t0, t1, t2; roles number independently; a lie
    about the take number from the client cannot influence anything
    (the field does not even exist)."""
    for expected in (0, 1, 2):
        r = client.post(
            "/api/record/upload",
            data={"session_id": session_id, "word_id": "kRSNa",
                  "role": "recitation"},
            files={"audio": ("t.wav", _speech_wav_bytes(0.8, f0=140 + 10 * expected),
                             "audio/wav")},
        )
        assert r.status_code == 200
        assert r.json()["take"] == expected

    r = client.post(
        "/api/record/upload",
        data={"session_id": session_id, "word_id": "kRSNa", "role": "canonical"},
        files={"audio": ("t.wav", _speech_wav_bytes(0.9), "audio/wav")},
    )
    assert r.json()["file"] == "spd_kRSNa_canonical_t0.wav"

    files = sorted(p.name for p in
                   (record_mod.INCOMING_ROOT / session_id).glob("*.wav"))
    assert files == [
        "spd_kRSNa_canonical_t0.wav",
        "spd_kRSNa_recitation_t0.wav",
        "spd_kRSNa_recitation_t1.wav",
        "spd_kRSNa_recitation_t2.wav",
    ]


def test_vowel_length_pairs_do_not_collide_in_filenames(client, session_id):
    """HK case is significant: tala and tAla are a minimal pair. Filenames
    keep the registry word_id verbatim so their takes never interleave
    (a lowercase-folding bug here would corrupt the D0 corpus)."""
    for wid in ("tala", "tAla"):
        r = client.post(
            "/api/record/upload",
            data={"session_id": session_id, "word_id": wid, "role": "recitation"},
            files={"audio": ("t.wav", _speech_wav_bytes(0.8), "audio/wav")},
        )
        assert r.status_code == 200
        assert r.json()["file"] == f"spd_{wid}_recitation_t0.wav"


def test_upload_to_unknown_session_404(client):
    r = client.post(
        "/api/record/upload",
        data={"session_id": "SPD-REC-20260101-deadbe", "word_id": "kRSNa",
              "role": "canonical"},
        files={"audio": ("t.wav", _speech_wav_bytes(), "audio/wav")},
    )
    assert r.status_code == 404


# ------------------------------------------------------------- promote

def test_promote_writes_mapping_without_touching_corpus_tree(client, session_id):
    client.post("/api/record/upload",
                data={"session_id": session_id, "word_id": "kRSNa", "role": "canonical"},
                files={"audio": ("t.wav", _speech_wav_bytes(0.9), "audio/wav")})
    client.post("/api/record/upload",
                data={"session_id": session_id, "word_id": "kRSNa", "role": "recitation"},
                files={"audio": ("t.wav", _speech_wav_bytes(0.8), "audio/wav")})
    client.post("/api/record/upload",
                data={"session_id": session_id, "word_id": "tAla", "role": "recitation"},
                files={"audio": ("t.wav", _speech_wav_bytes(0.7, f0=150), "audio/wav")})

    r = client.post("/api/record/promote", data={"session_id": session_id})
    assert r.status_code == 200
    body = r.json()
    assert body["canonical_candidates"] == 1
    assert body["recitation_takes"] == 2
    assert body["promoted"] is False  # force flag not passed

    block = body["promotion_block"]
    text = (record_mod.INCOMING_ROOT / session_id / "PROMOTION.md").read_text()
    assert block.endswith("PROMOTION.md")
    assert "`spd_kRSNa_canonical_t0.wav` → `reference_words/kRSNa.wav`" in text
    assert "`spd_kRSNa_recitation_t0.wav` → `recitations/kRSNa__t0.wav`" in text
    assert "samskrita_dhvani.calibrate" in text

    # The boundary this module exists to enforce: capture never writes
    # into the corpus tree.
    corpus = record_mod.PROJECT_ROOT / "data" / "spd"
    assert not (corpus / "reference_words").exists()
    assert not (corpus / "recitations").exists()


def test_promote_empty_session_is_409(client, session_id):
    r = client.post("/api/record/promote", data={"session_id": session_id})
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "empty_session"


def test_get_session_reports_takes(client, session_id):
    client.post("/api/record/upload",
                data={"session_id": session_id, "word_id": "tAla", "role": "recitation"},
                files={"audio": ("t.wav", _speech_wav_bytes(0.7, f0=150), "audio/wav")})
    r = client.get(f"/api/record/session/{session_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["meta"]["source_id"] == "SPD-D5-SELF"
    assert {"word_id": "tAla", "role": "recitation", "take": 0} in body["takes"]


def test_booth_page_served_with_shared_app_js(client):
    """The booth page loads with the shared SD helpers, so the capture
    path (Recorder/toWav16k) is exactly the one the demo screens use."""
    r = client.get("/")
    assert r.status_code == 200
    assert 'src="/app.js"' in r.text
    r2 = client.get("/app.js")
    assert r2.status_code == 200
    assert "toWav16k" in r2.text
