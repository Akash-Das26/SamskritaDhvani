"""Tests for the DataIntegrity.md §4 exclusion-register enforcement.

Every register and every audio clip here is a **synthetic fixture**
(NFR-02): generated in ``tmp_path``, never corpus audio. The paths in
the fixtures deliberately mimic the real corpus layout
(``corpus/vaksancayah/...``) so the normalisation logic is exercised
the way production uses it.

Covered:

- register parsing/validation (header, column count, blank path/reason,
  date format, empty file, duplicate rows);
- loud failure on a missing/malformed register, including the CLIs'
  rc=2 contract;
- the shared loader (:func:`load_audio_16k`) refusing a registered path
  and still loading an unregistered one;
- the sweep walkers' skip-and-count behaviour.
"""

import json

import numpy as np
import pytest

from samskrita_dhvani import exclusions as ex
from samskrita_dhvani.build_registry import main as build_registry_main
from samskrita_dhvani.calibrate import main as calibrate_main
from samskrita_dhvani.frontend import load_audio_16k

HEADER = "path,reason,date\n"


def _write_synth_wav(path):
    """A 0.3 s 220 Hz synthetic tone — a fixture, not speech (NFR-02)."""
    import wave

    sr = 16_000
    t = np.arange(int(0.3 * sr)) / sr
    y = (0.2 * np.sin(2 * np.pi * 220.0 * t) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(y.tobytes())


def _register(path, rows, header=HEADER):
    path.write_text(header + "".join(rows), encoding="utf-8")
    return path


def _use(monkeypatch, register):
    monkeypatch.setenv(ex.REGISTER_ENV_VAR, str(register))


# ---------------------------------------------------------------- parsing


def test_register_rows_are_normalised_deduped_and_carry_reasons(tmp_path):
    audio = tmp_path / "corpus" / "vaksancayah" / "sp001" / "a.mp3"
    audio.parent.mkdir(parents=True)
    audio.write_bytes(b"synthetic fixture placeholder")
    reg = _register(
        tmp_path / "EXCLUDED.csv",
        [
            f"{audio},synthetic-fixture: clipped,2026-10-22\n",
            f"{audio},synthetic-fixture: duplicate row,2026-10-23\n",
        ],
    )
    rows = ex.load_excluded_rows(reg)
    assert len(rows) == 1
    row = next(iter(rows.values()))
    assert row.reason == "synthetic-fixture: clipped"  # first row wins
    assert row.date == "2026-10-22"
    assert str(audio.resolve()) in ex.load_excluded_paths(reg)


@pytest.mark.parametrize(
    "content, needle",
    [
        ("path,reason\nx,y\n", "header"),
        ("path,reason,date\nonly,two\n", "line 2"),
        ("path,reason,date\n,no path,2026-10-22\n", "empty path"),
        ("path,reason,date\nx.mp3,,2026-10-22\n", "no reason"),
        ("path,reason,date\nx.mp3,damaged,22-10-2026\n", "YYYY-MM-DD"),
    ],
)
def test_malformed_register_fails_loudly(tmp_path, content, needle):
    reg = tmp_path / "EXCLUDED.csv"
    reg.write_text(content, encoding="utf-8")
    with pytest.raises(ex.ExclusionRegisterError) as excinfo:
        ex.load_excluded_rows(reg)
    assert needle in str(excinfo.value)


def test_repo_relative_rows_resolve_against_project_root(tmp_path, monkeypatch):
    reg = _register(
        tmp_path / "EXCLUDED.csv",
        ["corpus/vaksancayah/sp001/x.mp3,synthetic-fixture: clipped,2026-10-22\n"],
    )
    monkeypatch.chdir(tmp_path)  # cwd must not change the register's meaning
    rows = ex.load_excluded_rows(reg)
    expected = str((ex.PROJECT_ROOT / "corpus/vaksancayah/sp001/x.mp3").resolve())
    assert expected in rows


def test_empty_register_fails_loudly(tmp_path):
    reg = tmp_path / "EXCLUDED.csv"
    reg.write_text("", encoding="utf-8")
    with pytest.raises(ex.ExclusionRegisterError, match="empty"):
        ex.load_excluded_rows(reg)


def test_missing_register_fails_loudly(tmp_path):
    with pytest.raises(ex.ExclusionRegisterError, match="not found"):
        ex.load_excluded_rows(tmp_path / "absent.csv")
    with pytest.raises(ex.ExclusionRegisterError, match="not found"):
        ex.load_excluded_paths(tmp_path / "absent.csv")


# ----------------------------------------------------------------- loader


def test_loader_refuses_a_registered_path(tmp_path, monkeypatch):
    clip = tmp_path / "corpus" / "vaksancayah" / "sp001" / "clip.mp3"
    clip.parent.mkdir(parents=True)
    _write_synth_wav(clip)
    reg = _register(
        tmp_path / "EXCLUDED.csv",
        [f"{clip},synthetic-fixture: sustained clipping,2026-10-22\n"],
    )
    _use(monkeypatch, reg)

    with pytest.raises(ex.ExcludedAudioError) as excinfo:
        load_audio_16k(str(clip))
    message = str(excinfo.value)
    assert "sustained clipping" in message
    assert "EXCLUDED.csv" in message


def test_loader_still_loads_an_unregistered_path(tmp_path, monkeypatch):
    allowed = tmp_path / "corpus" / "vaksancayah" / "sp001" / "ok.mp3"
    blocked = tmp_path / "corpus" / "vaksancayah" / "sp001" / "bad.mp3"
    allowed.parent.mkdir(parents=True)
    _write_synth_wav(allowed)
    _write_synth_wav(blocked)
    reg = _register(
        tmp_path / "EXCLUDED.csv",
        [f"{blocked},synthetic-fixture: decoder-damaged,2026-10-22\n"],
    )
    _use(monkeypatch, reg)

    y = load_audio_16k(str(allowed))
    assert y.dtype == np.float32 and y.size == int(0.3 * 16_000)


# ------------------------------------------------------ sweep skip + count


def test_filter_excluded_counts_skips_loudly(tmp_path, monkeypatch, capsys):
    a = tmp_path / "a.mp3"
    b = tmp_path / "b.mp3"
    a.write_bytes(b"synthetic fixture placeholder")
    b.write_bytes(b"synthetic fixture placeholder")
    reg = _register(
        tmp_path / "EXCLUDED.csv",
        [f"{a},synthetic-fixture: clipped,2026-10-22\n"],
    )
    _use(monkeypatch, reg)

    kept, skipped = ex.filter_excluded([a, b], label="unit-test sweep")
    assert kept == [b]
    assert skipped == [a]
    err = capsys.readouterr().err
    assert "EXCLUDED register" in err
    assert "skipped 1 file(s)" in err
    assert "unit-test sweep" in err


def test_filter_excluded_is_silent_when_nothing_is_registered(
    tmp_path, monkeypatch, capsys
):
    a = tmp_path / "a.mp3"
    a.write_bytes(b"synthetic fixture placeholder")
    reg = _register(
        tmp_path / "EXCLUDED.csv",
        [f"{tmp_path / 'other.mp3'},synthetic-fixture: clipped,2026-10-22\n"],
    )
    _use(monkeypatch, reg)

    kept, skipped = ex.filter_excluded([a], label="unit-test sweep")
    assert kept == [a] and skipped == []
    assert capsys.readouterr().err == ""


# ------------------------------------------------------------ CLI rc = 2


def _calibrate_args(tmp_path):
    refs = tmp_path / "refs"
    recs = tmp_path / "recs"
    refs.mkdir()
    recs.mkdir()
    return [
        "--references", str(refs),
        "--recitations", str(recs),
        "--out", str(tmp_path / "calibration.json"),
        "--source-id", "SYNTHETIC-FIXTURE",
        "--acquired-on", "2026-01-01",
    ]


def test_calibrate_returns_2_when_register_is_missing(
    tmp_path, monkeypatch, capsys
):
    _use(monkeypatch, tmp_path / "absent.csv")
    rc = calibrate_main(_calibrate_args(tmp_path))
    assert rc == 2
    assert "exclusion register not found" in capsys.readouterr().err


def test_calibrate_returns_2_when_register_is_malformed(
    tmp_path, monkeypatch, capsys
):
    reg = tmp_path / "EXCLUDED.csv"
    reg.write_text("path,reason\nx.mp3,broken\n", encoding="utf-8")
    _use(monkeypatch, reg)
    rc = calibrate_main(_calibrate_args(tmp_path))
    assert rc == 2
    assert "malformed exclusion register" in capsys.readouterr().err


def test_build_registry_returns_2_when_register_is_missing(
    tmp_path, monkeypatch, capsys
):
    recordings = tmp_path / "recordings"
    recordings.mkdir()
    _write_synth_wav(recordings / "gvr_c2v01_asha_SYNTHETIC_t1.wav")
    itemlist = tmp_path / "itemlist.json"
    itemlist.write_text(
        json.dumps({"kind": "gvr_itemlist", "schema_version": 1, "items": []}),
        encoding="utf-8",
    )
    _use(monkeypatch, tmp_path / "absent.csv")

    rc = build_registry_main([
        "--recordings", str(recordings),
        "--out", str(tmp_path / "registry.json"),
        "--itemlist", str(itemlist),
        "--source-id", "SYNTHETIC-FIXTURE",
        "--acquired-on", "2026-01-01",
        "--recitation-tradition", "synthetic fixture",
    ])
    assert rc == 2
    assert "exclusion register not found" in capsys.readouterr().err


# --------------------------------------------------- shipped register gate


def test_shipped_register_parses_and_every_row_has_a_reason():
    """The tracked register must be loadable — a broken one would turn
    every corpus-facing loader into an rc=2 stop, which is the point."""
    rows = ex.load_excluded_rows(ex.DEFAULT_REGISTER)
    assert rows
    assert all(row.reason.strip() for row in rows.values())
    assert all(row.date for row in rows.values())
