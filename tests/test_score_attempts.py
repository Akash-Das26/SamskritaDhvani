"""Batch SPD scoring CLI tests — synthetic fixtures only (NFR-02).

Every WAV, reference clip, calibration value, and rating sheet here is
generated in tmp_path. None of it is corpus audio, and no number
produced by these tests is evidence or is written into any doc.
"""

import json
import wave
from pathlib import Path

import numpy as np
import pytest

from samskrita_dhvani import exclusions
from samskrita_dhvani import score_attempts as sa
from samskrita_dhvani.spd_scorer import Calibration

HEADER = "path,reason,date\n"


# --------------------------------------------------------------- fixtures


def _speech_wav_bytes(seconds: float = 1.0, f0: float = 130.0) -> bytes:
    """Harmonic-stack voiced WAV — synthetic (NFR-02), VAD-detectable."""
    sr = 16_000
    t = np.arange(int(sr * seconds)) / sr
    y = np.zeros_like(t)
    for k in (1, 2, 3, 4, 5):
        y += np.sin(2 * np.pi * f0 * k * t) / k
    env = 0.5 * (1 - np.cos(np.pi * np.minimum(1.0, t / seconds)))
    pcm = (np.clip(0.35 * y * env, -1, 1) * 32767).astype("<i2")
    import io

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


def _silence_wav_bytes(seconds: float = 1.0) -> bytes:
    import io

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16_000)
        w.writeframes(np.zeros(int(16_000 * seconds), dtype="<i2").tobytes())
    return buf.getvalue()


def _write(path: Path, data: bytes) -> Path:
    path.write_bytes(data)
    return path


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """Reference root + calibration doubles; no real corpus artifacts."""
    refs = tmp_path / "refs"
    refs.mkdir()
    for f0, word in ((130.0, "kRSNa"), (150.0, "yoga")):
        _write(refs / f"{word}.wav", _speech_wav_bytes(f0=f0))
    monkeypatch.setattr(sa.api, "SPD_REFERENCE_ROOT", refs)

    cal_path = tmp_path / "calibration.json"
    cal_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(sa, "CALIBRATION_DEFAULT_PATH", cal_path)
    cal = Calibration(
        word_id="fixture", d0=3.0, d0_formant=0.08, d0_duration=0.15,
        n_references=3, schema_version=1,
    )
    monkeypatch.setattr(sa, "load_calibration", lambda word_id: cal)

    register = tmp_path / "EXCLUDED.csv"
    register.write_text(
        HEADER + f"{tmp_path / 'never-used.mp3'},synthetic fixture,2026-10-23\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(exclusions.REGISTER_ENV_VAR, str(register))
    monkeypatch.setattr(exclusions, "_CACHE", {})

    attempts = tmp_path / "attempts"
    attempts.mkdir()
    return {"attempts": attempts, "refs": refs, "cal": cal_path,
            "register": register, "tmp": tmp_path}


# ------------------------------------------------------------ name parsing


def test_synthetic_protocol_name_parsing_and_variant_tags():
    parsed = sa.parse_attempt_name(
        "spd_krsna_asha-rao_spd-rec-20261023-01_t2"
    )
    assert parsed is not None
    assert parsed.attempt_id == "spd_krsna_asha-rao_spd-rec-20261023-01_t2"
    assert parsed.item == "krsna"
    assert parsed.take == 2
    assert parsed.variant is None
    assert parsed.rest == "asha-rao_spd-rec-20261023-01"

    var = sa.parse_attempt_name(
        "spd_kRSNa_asha_spd-rec-01_t3_var-sub"
    )
    assert var is not None and var.variant == "_var-sub"
    assert var.attempt_id.endswith("_var-sub")


@pytest.mark.parametrize(
    "stem",
    [
        "not_protocol.wav",
        "spd_krsna_t1",
        "gvr_c2v01_a_b_t1",
        "spd_krsna_asha_spd-rec-01",          # no take
        "spd_krsna__spd-rec-01_t1",           # empty reciter token
        "spd_krsna_asha_spd-rec-01_t1_var",   # malformed variant tag
    ],
)
def test_synthetic_malformed_names_are_rejected(stem):
    assert sa.parse_attempt_name(stem) is None


def test_synthetic_booth_style_name_needs_the_flag():
    assert sa.parse_attempt_name("spd_krsna_canonical_t1") is None
    parsed = sa.parse_attempt_name("spd_krsna_canonical_t1", booth_style=True)
    assert parsed is not None and parsed.item == "krsna"


# -------------------------------------------------------------- scoring


def test_synthetic_batch_scores_two_attempts(env, capsys):
    attempts, out = env["attempts"], env["tmp"] / "scores.jsonl"
    _write(attempts / "spd_krsna_asha_spd-rec-01_t1.wav",
           _speech_wav_bytes())
    _write(attempts / "spd_kRSNa_asha_spd-rec-01_t1_var-len.wav",
           _speech_wav_bytes(f0=150.0))

    rc = sa.main(["--attempts", str(attempts), "--out", str(out)])
    captured = capsys.readouterr()
    assert rc == 0, captured.err

    lines = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 2
    for rec in lines:
        assert set(rec) == {
            "attempt_id", "reference_word", "similarity_pct",
            "vowel_score", "consonant_score", "duration_score",
            "mfcc_dtw_score",
        }
        assert rec["reference_word"]["word_id"] == "kRSNa"
        assert 0.0 <= rec["similarity_pct"] <= 100.0
    assert lines[0]["attempt_id"] == "spd_kRSNa_asha_spd-rec-01_t1_var-len"
    assert "scored 2/2 attempt(s)" in captured.out
    assert "as-run: python -m samskrita_dhvani.score_attempts" in captured.out


def test_synthetic_booth_style_scores_only_with_flag(env, capsys):
    attempts, out = env["attempts"], env["tmp"] / "scores.jsonl"
    _write(attempts / "spd_krsna_canonical_t1.wav", _speech_wav_bytes())

    rc = sa.main(["--attempts", str(attempts), "--out", str(out)])
    assert rc == 2  # nothing scoreable → loud refusal, no file
    assert not out.exists()

    rc = sa.main(["--attempts", str(attempts), "--out", str(out),
                  "--word-from-name"])
    assert rc == 0, capsys.readouterr().err
    rec = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
    assert rec["attempt_id"] == "spd_krsna_canonical_t1"


def test_synthetic_round_trip_into_nfr10(env, capsys):
    """The CLI's output is consumed by nfr10 --scores without edits."""
    attempts = env["attempts"]
    out = env["tmp"] / "scores.jsonl"
    stems = []
    for take in range(1, 9):
        stem = f"spd_krsna_asha_spd-rec-01_t{take}"
        _write(attempts / f"{stem}.wav",
               _speech_wav_bytes(f0=120.0 + take * 6))
        stems.append(stem)

    assert sa.main(["--attempts", str(attempts), "--out", str(out)]) == 0

    sheet_rows = "\n".join(
        f"| {stem} | kRSNa | क | k | {1 + i % 5} | synthetic |"
        for i, stem in enumerate(sorted(stems))
    )
    sheet = env["tmp"] / "rater_a.md"
    body = f"""
# NFR-10 Rater Sheet — synthetic fixture

**SYNTHETIC-FIXTURE** — generated by tests/test_score_attempts.py.

| Field | Value |
|---|---|
| Rater ID (name or pseudonym) | fixture-A |
| Role | instructor |
| Native language(s) | none |
| Script familiarity (Devanagari / IAST / neither) | IAST |
| Recitation tradition practiced or studied | synthetic |
| Years of Sanskrit study / teaching | 0 |
| Date of rating | 2026-01-01 |

| Attempt ID | Word ID | Devanagari | IAST | Rating (1–5) | Notes (optional) |
|---|---|---|---|---|---|
{sheet_rows}
"""
    sheet.write_text(body, encoding="utf-8")
    sheet_b = env["tmp"] / "rater_b.md"
    sheet_b.write_text(body.replace("fixture-A", "fixture-B"),
                       encoding="utf-8")

    from samskrita_dhvani.nfr10 import main as nfr10_main

    report_path = env["tmp"] / "nfr10.json"
    rc = nfr10_main([
        "--ratings", str(sheet), str(sheet_b),
        "--scores", str(out), "--json", str(report_path),
        "--min-n", "8", "--fixtures",
    ])
    captured = capsys.readouterr()
    assert rc == 0, captured.err
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["n"] == 8
    assert report["synthetic_fixture"] is True


# ---------------------------------------------------- skip paths, counted


def test_synthetic_skip_reasons_are_counted(env, capsys, monkeypatch):
    attempts, tmp = env["attempts"], env["tmp"]
    _write(attempts / "spd_krsna_asha_spd-rec-01_t1.wav",
           _speech_wav_bytes())                                      # scored
    _write(attempts / "not_protocol.wav", _speech_wav_bytes())       # unparsed
    _write(attempts / "spd_zzz_asha_spd-rec-01_t1.wav",
           _speech_wav_bytes())                                      # unknown
    _write(attempts / "spd_pata_asha_spd-rec-01_t1.wav",
           _speech_wav_bytes())                                      # ambiguous
    _write(attempts / "spd_krsna_asha_spd-rec-01_t2.wav",
           _silence_wav_bytes())                                     # near-silence
    _write(attempts / "spd_krsna_asha_spd-rec-01_t3.wav", b"junk")   # decode
    _write(attempts / "spd_rAma_asha_spd-rec-01_t1.wav",
           _speech_wav_bytes())                                      # no reference
    _write(attempts / "spd_yoga_asha_spd-rec-01_t1.wav",
           _speech_wav_bytes())                                      # no calibration

    excluded = attempts / "spd_krsna_asha_spd-rec-01_t4.wav"
    _write(excluded, _speech_wav_bytes())
    env["register"].write_text(
        HEADER + f"{excluded},synthetic fixture: clipped,2026-10-23\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(exclusions, "_CACHE", {})

    real_load = sa.load_calibration
    monkeypatch.setattr(
        sa, "load_calibration",
        lambda word_id: None if word_id == "yoga" else real_load(word_id),
    )

    out = tmp / "scores.jsonl"
    rc = sa.main(["--attempts", str(attempts), "--out", str(out)])
    captured = capsys.readouterr()
    assert rc == 0, captured.err
    summary = captured.out
    for reason in ("unparsed_name", "unknown_word", "ambiguous_word",
                   "near_silence", "decode_failed", "reference_missing",
                   "calibration_missing", "excluded"):
        assert reason in summary, reason
    assert "scored 1/" in summary
    assert "! skipped 'not_protocol.wav':" in captured.err
    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1


# ------------------------------------------------------------- refusals


def _refusal(capsys, rc, needle):
    assert rc == 2
    err = capsys.readouterr().err
    assert needle in err
    assert len(err.strip().splitlines()) == 1  # one loud line
    return err


def test_synthetic_missing_attempts_dir_is_refused(env, capsys):
    rc = sa.main(["--attempts", str(env["tmp"] / "absent"),
                  "--out", str(env["tmp"] / "s.jsonl")])
    _refusal(capsys, rc, "attempts directory not found")


def test_synthetic_empty_attempts_dir_is_refused(env, capsys):
    rc = sa.main(["--attempts", str(env["attempts"]),
                  "--out", str(env["tmp"] / "s.jsonl")])
    _refusal(capsys, rc, "no audio files")


def test_synthetic_wordlist_unavailable_is_refused(env, capsys, monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("synthetic fixture: word list unavailable")

    monkeypatch.setattr(sa, "build_seed_wordlist", boom)
    _write(env["attempts"] / "spd_krsna_asha_spd-rec-01_t1.wav",
           _speech_wav_bytes())
    rc = sa.main(["--attempts", str(env["attempts"]),
                  "--out", str(env["tmp"] / "s.jsonl")])
    _refusal(capsys, rc, "SPD word list unavailable")


def test_synthetic_calibration_unavailable_is_refused(
    env, capsys, monkeypatch
):
    monkeypatch.setattr(sa, "CALIBRATION_DEFAULT_PATH",
                        env["tmp"] / "absent_calibration.json")
    _write(env["attempts"] / "spd_krsna_asha_spd-rec-01_t1.wav",
           _speech_wav_bytes())
    rc = sa.main(["--attempts", str(env["attempts"]),
                  "--out", str(env["tmp"] / "s.jsonl")])
    _refusal(capsys, rc, "SPD calibration unavailable")


def test_synthetic_exclusion_register_missing_is_refused(
    env, capsys, monkeypatch
):
    monkeypatch.setenv(exclusions.REGISTER_ENV_VAR,
                       str(env["tmp"] / "absent_register.csv"))
    monkeypatch.setattr(exclusions, "_CACHE", {})
    _write(env["attempts"] / "spd_krsna_asha_spd-rec-01_t1.wav",
           _speech_wav_bytes())
    rc = sa.main(["--attempts", str(env["attempts"]),
                  "--out", str(env["tmp"] / "s.jsonl")])
    _refusal(capsys, rc, "exclusion register not found")


def test_synthetic_out_is_not_clobbered_without_force(env, capsys):
    attempts, out = env["attempts"], env["tmp"] / "scores.jsonl"
    _write(attempts / "spd_krsna_asha_spd-rec-01_t1.wav",
           _speech_wav_bytes())
    out.write_text('{"attempt_id": "old", "similarity_pct": 1.0}\n',
                   encoding="utf-8")

    rc = sa.main(["--attempts", str(attempts), "--out", str(out)])
    _refusal(capsys, rc, "already exists")
    assert '"old"' in out.read_text(encoding="utf-8")

    rc = sa.main(["--attempts", str(attempts), "--out", str(out), "--force"])
    assert rc == 0, capsys.readouterr().err
    assert '"old"' not in out.read_text(encoding="utf-8")
