"""Tests for the registry-build CLI (build_registry.py).

Under test: a promoted D4 batch (protocol §3 names, exactly what the
booth's PROMOTION.md emits) becomes a schema-v1 registry with every
FR-22 plan §4 acceptance gate applied, the split policy the registry
actually enforces, and zero silent fixes — failures are loud skips,
and an all-fail batch writes nothing.
"""

from __future__ import annotations

import io
import json
import struct
import wave

import numpy as np
import pytest

from samskrita_dhvani import build_registry as br
from samskrita_dhvani.registry import GvrRegistry


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


def _speech_wav_bytes(seconds: float = 1.2, f0: float = 135.0) -> bytes:
    sr = 16000
    t = np.arange(int(sr * seconds)) / sr
    y = np.zeros_like(t)
    for k in (1, 2, 3, 4, 5):
        y += np.sin(2 * np.pi * f0 * k * t) / k
    env = 0.5 * (1 - np.cos(np.pi * np.minimum(1.0, t / seconds)))
    return _wav_bytes(0.35 * y * env)


ITEMS = {
    "schema_version": 1,
    "kind": "gvr_itemlist",
    "program": "D4",
    "chapter": 2,
    "text_source": {"url": "https://example/bg.itx",
                    "file_sha256": "0" * 64, "edition_note": "fixture"},
    "items": [
        {"verse_id": f"2.{v:02d}", "chapter": 2, "verse": v,
         "devanagari": f"परीक्षा-{v:02d}", "fname_key": f"c2v{v}"}
        for v in range(1, 21)
    ],
}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """Recordings dir + item list + out path, all in tmp."""
    rec = tmp_path / "gvr_recordings"
    rec.mkdir()
    il = tmp_path / "ch2_itemlist.json"
    il.write_text(json.dumps(ITEMS, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "gvr_registry.json"
    monkeypatch.setattr(br, "DEFAULT_OUT", out)
    return {"rec": rec, "il": il, "out": out}


def _add_clip(rec_dir, name, seconds=1.2, f0=135.0, garbage=False):
    data = (b"not audio at all" * 64) if garbage else _speech_wav_bytes(seconds, f0)
    (rec_dir / name).write_bytes(data)


def _run(env, *extra):
    argv = [
        "--recordings", str(env["rec"]),
        "--out", str(env["out"]),
        "--itemlist", str(env["il"]),
        "--source-id", "GVR-D4-SELF",
        "--acquired-on", "2026-10-01",
        "--recitation-tradition", "classical paatha, no Vedic accents",
        *extra,
    ]
    return br.main(argv)


# ---------------------------------------------------------- name parse

def test_parse_promoted_name_right_to_left():
    from pathlib import Path as _P
    p = br.parse_promoted_name(
        _P("gvr_c2v13_asha_rao_GVR-REC-20261001-ab12cd_t1.wav")
    )
    assert p and p["chapter"] == 2 and p["verse"] == 13
    assert p["reciter"] == "asha_rao"          # underscore survives
    assert p["session_id"] == "GVR-REC-20261001-ab12cd"
    assert p["take"] == 1
    assert br.parse_promoted_name(
        _P("gvr_c2v13_wrong_name.wav")
    ) is None


# ---------------------------------------------------------- happy path

def test_happy_path_two_reciters_per_reciter_split(env):
    _add_clip(env["rec"], "gvr_c2v01_asha_rao_GVR-REC-20261001-ab12cd_t0.wav")
    _add_clip(env["rec"], "gvr_c2v13_asha_rao_GVR-REC-20261001-ab12cd_t1.wav")
    _add_clip(env["rec"], "gvr_c2v01_ravi_k_GVR-REC-20261001-cd34ef_t0.wav")
    _add_clip(env["rec"], "gvr_c2v13_ravi_k_GVR-REC-20261001-cd34ef_t0.wav")

    rc = _run(env, "--reciter-splits", "asha_rao=train,ravi_k=test")
    assert rc == 0
    reg = GvrRegistry.from_json(env["out"])   # full load-time gates
    assert len(reg) == 4
    assert reg.split_policy == "per-reciter"
    by = {(e.verse_id, e.reciter): e.split for e in reg.entries}
    assert by[("2.01", "asha_rao")] == "train"
    assert by[("2.13", "asha_rao")] == "train"
    assert by[("2.01", "ravi_k")] == "test"
    # mūla text attached from the item list, never typed by the tool
    assert all(e.devanagari_text.startswith("परीक्षा-") for e in reg.entries)
    # provenance on every row (Rule 2)
    assert all(e.provenance["source_id"] == "GVR-D4-SELF" for e in reg.entries)


def test_single_reciter_auto_per_recording_policy(env):
    _add_clip(env["rec"], "gvr_c2v01_solo_GVR-REC-20261001-aa11bb_t0.wav")
    _add_clip(env["rec"], "gvr_c2v02_solo_GVR-REC-20261001-aa11bb_t1.wav")
    rc = _run(env)
    assert rc == 0
    reg = GvrRegistry.from_json(env["out"])
    assert reg.split_policy == "per-recording"
    assert all(e.split == "train" for e in reg.entries)


def test_two_reciters_without_complete_assignment_is_error(env):
    _add_clip(env["rec"], "gvr_c2v01_a_GVR-REC-20261001-aa11bb_t0.wav")
    _add_clip(env["rec"], "gvr_c2v01_b_GVR-REC-20261001-cc22dd_t0.wav")
    rc = _run(env, "--reciter-splits", "a=train")   # b unassigned
    assert rc == 2
    assert not env["out"].exists()

    rc = _run(env)                                   # spec absent entirely
    assert rc == 2
    assert not env["out"].exists()


# --------------------------------------------------------------- gates

def test_gates_skip_loudly_and_count(env, capsys):
    _add_clip(env["rec"], "gvr_c2v01_asha_GVR-REC-20261001-ab12cd_t0.wav")
    _add_clip(env["rec"], "gvr_c2v02_asha_GVR-REC-20261001-ab12cd_t0.wav",
              garbage=True)                          # decode fail
    _add_clip(env["rec"], "gvr_c2v03_asha_GVR-REC-20261001-ab12cd_t0.wav",
              seconds=0.1)                           # too short
    (env["rec"] / "gvr_c2v04_asha_GVR-REC-20261001-ab12cd_t0.wav").write_bytes(
        _wav_bytes(np.zeros(16000, dtype=np.float32)))   # near-silence
    (env["rec"] / "junk_name.wav").write_bytes(_speech_wav_bytes())
    rc = _run(env)
    out = capsys.readouterr().err
    assert rc == 0                                   # one good row survives
    assert "does not match" in out
    assert "failed to decode" in out
    assert "too short" in out
    assert "near-silence" in out
    reg = GvrRegistry.from_json(env["out"])
    assert [e.verse_id for e in reg.entries] == ["2.01"]


def test_unknown_verse_skipped(env, capsys):
    _add_clip(env["rec"], "gvr_c2v99_asha_GVR-REC-20261001-ab12cd_t0.wav")
    rc = _run(env)
    assert "not in the item list" in capsys.readouterr().err
    assert rc == 2                                   # nothing survived
    assert not env["out"].exists()


def test_missing_itemlist_is_error(env):
    rc = _run(env, "--itemlist", str(env["il"].parent / "absent.json"))
    assert rc == 2


# ------------------------------------------------------- file handling

def test_overwrite_protection_and_force(env):
    _add_clip(env["rec"], "gvr_c2v01_asha_GVR-REC-20261001-ab12cd_t0.wav")
    assert _run(env) == 0
    first = env["out"].read_text()
    assert _run(env) == 2                            # refuses without --force
    assert _run(env, "--force") == 0
    assert env["out"].read_text() == first           # deterministic rebuild


def test_empty_recordings_dir_is_error(env, capsys):
    rc = _run(env)
    assert rc == 2
    assert not env["out"].exists()
    assert "no eligible clips" in capsys.readouterr().err


def test_train_outside_warning_lists_verses(env, capsys):
    # Only reciter b (test split): all verses end up outside train.
    _add_clip(env["rec"], "gvr_c2v01_b_GVR-REC-20261001-cc22dd_t0.wav")
    rc = _run(env, "--reciter-splits", "b=test")
    assert rc == 0
    assert "cannot be learned" in capsys.readouterr().err
