"""Tests for the calibration CLI (python -m samskrita_dhvani.calibrate).

All fixtures are synthetic vowel clips on disk (NFR-02) laid out the
way the D5 recordings will be: canonical ``<word_id>.wav`` references
plus ``<word_id>__take<N>.wav`` known-correct recitations.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from samskrita_dhvani.calibrate import main


def vowel_clip(dur=0.6, f0=150, formants=(700.0, 1200.0, 2600.0), seed=0):
    rng = np.random.default_rng(seed)
    sr = 16000
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


def write_wav(path: Path, y):
    import io
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes((np.clip(y, -1, 1) * 32767).astype("<i2").tobytes())
    path.write_bytes(buf.getvalue())


@pytest.fixture
def word_dirs(tmp_path):
    refs = tmp_path / "reference_words"
    recs = tmp_path / "known_correct"
    refs.mkdir()
    recs.mkdir()
    for word_id, f0 in (("kRSNa", 150.0), ("tAla", 130.0)):
        write_wav(refs / f"{word_id}.wav", vowel_clip(f0=f0, seed=1))
        for take in range(2):
            # Real recitations vary in tempo too — identical durations
            # would measure a degenerate D0_duration of exactly 0 (now
            # rejected by Calibration validation).
            dur = 0.6 * (1 + 0.15 * (take - 0.5))
            write_wav(
                recs / f"{word_id}__take{take}.wav",
                vowel_clip(dur=dur, f0=f0 * (1 + 0.01 * (take - 0.5)),
                           seed=2 + take),
            )
    return refs, recs


def _run(word_dirs, tmp_path, extra=None):
    refs, recs = word_dirs
    out = tmp_path / "calibration.json"
    rc = main([
        "--references", str(refs),
        "--recitations", str(recs),
        "--out", str(out),
        "--source-id", "SPD-01",
        "--acquired-on", "2026-10-01",
        *(extra or []),
    ])
    return rc, out


def test_cli_writes_measured_calibration(word_dirs, tmp_path, capsys):
    rc, out = _run(word_dirs, tmp_path)
    assert rc == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["kind"] == "spd_calibration"
    assert data["provenance"] == {"source_id": "SPD-01",
                                  "acquired_on": "2026-10-01"}
    assert set(data["words"]) == {"kRSNa", "tAla"}
    for entry in data["words"].values():
        assert entry["d0"] > 0
        assert entry["d0_formant"] > 0
        assert entry["d0_duration"] > 0
        assert entry["n_references"] == 2
    printed = capsys.readouterr().out
    assert "kRSNa" in printed and "D0" in printed  # the measured table


def test_cli_skips_words_missing_one_side(word_dirs, tmp_path, capsys):
    refs, recs = word_dirs
    (refs / "orphanRef.wav").write_bytes(b"")
    (refs / "orphanRef.wav").unlink()
    write_wav(refs / "orphanRef.wav", vowel_clip(seed=9))
    write_wav(recs / "orphanRec__a.wav", vowel_clip(seed=10))
    # 'orphanRec' has recitations but no canonical clip -> skipped loudly
    (recs / "orphanRec__a.wav").unlink()
    write_wav(recs / "orphanRec__a.wav", vowel_clip(seed=11))
    rc, out = _run(word_dirs, tmp_path)
    assert rc == 0
    err = capsys.readouterr().err
    assert "orphanRec" in err and "canonical clip" in err
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "orphanRec" not in data["words"]


def test_cli_refuses_overwrite_without_force(word_dirs, tmp_path):
    rc, out = _run(word_dirs, tmp_path)
    assert rc == 0
    before = out.read_text(encoding="utf-8")
    rc2, _ = _run(word_dirs, tmp_path)
    assert rc2 == 2
    assert out.read_text(encoding="utf-8") == before  # untouched


def test_cli_force_regenerates(word_dirs, tmp_path):
    rc, out = _run(word_dirs, tmp_path)
    rc2, _ = _run(word_dirs, tmp_path, extra=["--force"])
    assert rc2 == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert set(data["words"]) == {"kRSNa", "tAla"}


def test_cli_requires_provenance_args(word_dirs, tmp_path):
    refs, recs = word_dirs
    out = tmp_path / "c.json"
    with pytest.raises(SystemExit):
        main([
            "--references", str(refs),
            "--recitations", str(recs),
            "--out", str(out),
            # no --source-id / --acquired-on
        ])
    assert not out.exists()


def test_cli_missing_dir_is_an_error(word_dirs, tmp_path):
    refs, recs = word_dirs
    rc = main([
        "--references", str(refs / "nope"),
        "--recitations", str(recs),
        "--out", str(tmp_path / "c.json"),
        "--source-id", "X",
        "--acquired-on", "2026-10-01",
    ])
    assert rc == 2


def test_cli_reports_undecodable_take_and_word_survives(
    word_dirs, tmp_path, capsys
):
    """One corrupt take must not kill the word: the surviving takes
    still calibrate it, and the bad take is named on stderr."""
    refs, recs = word_dirs
    (recs / "kRSNa__corrupt.wav").write_bytes(b"not audio at all" * 40)
    rc, out = _run(word_dirs, tmp_path)
    assert rc == 0
    err = capsys.readouterr().err
    assert "kRSNa__corrupt.wav" in err
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["words"]["kRSNa"]["n_references"] == 2  # corrupt take excluded
    assert "tAla" in data["words"]


def test_cli_drops_word_when_all_recitations_fail(word_dirs, tmp_path, capsys):
    refs, recs = word_dirs
    for p in recs.glob("kRSNa__*.wav"):
        p.write_bytes(b"not audio at all" * 40)
    rc, out = _run(word_dirs, tmp_path)
    assert rc == 0  # other words still calibrate
    err = capsys.readouterr().err
    assert "no known-correct recitation loaded" in err
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "kRSNa" not in data["words"]  # dropped loudly, not silently
    assert "tAla" in data["words"]
