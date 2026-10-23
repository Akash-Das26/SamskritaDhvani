"""REC-skeleton tests — synthetic fixtures only (NFR-02).

Every WAV, session_meta.json, provenance note, and completed sheet here
is generated in tmp_path. No real recording session exists, and these
tests make no claim about real audio.
"""

import json
import re
import wave
from pathlib import Path

import numpy as np
import pytest

from samskrita_dhvani import exclusions
from samskrita_dhvani import promote as pr
from samskrita_dhvani import rec_skeleton as rs

SESSION = "SPD-REC-20261023-01"
STARTED = "2026-10-23T10:15:30+00:00"
VERSION = "spd-seed-27@2026-09-23"


# --------------------------------------------------------------- fixtures


def _speech_wav(path: Path, *, seconds: float = 1.0, f0: float = 130.0,
                scale: float = 0.35) -> Path:
    sr = 16_000
    t = np.arange(int(sr * seconds)) / sr
    y = np.zeros_like(t)
    for k in (1, 2, 3, 4, 5):
        y += np.sin(2 * np.pi * f0 * k * t) / k
    env = 0.5 * (1 - np.cos(np.pi * np.minimum(1.0, t / seconds)))
    pcm = (np.clip(scale * y * env, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return path


@pytest.fixture()
def env(tmp_path, monkeypatch):
    incoming = tmp_path / "_incoming"
    prov_dir = tmp_path / "provenance"
    spd = tmp_path / "spd"
    gvr = tmp_path / "gvr_recordings"
    prov_md = tmp_path / "PROVENANCE.md"
    for d in (incoming, prov_dir):
        d.mkdir()
    prov_md.write_text(
        "# PROVENANCE (synthetic fixture)\n\n"
        "### SPD-SYNTHETIC · fixture source\n\n"
        f"| Field | Value |\n|---|---|\n"
        f"| **Session** | `{SESSION}` (synthetic fixture) |\n",
        encoding="utf-8",
    )
    register = tmp_path / "EXCLUDED.csv"
    register.write_text(
        "path,reason,date\n"
        f"{tmp_path / 'never-used.mp3'},synthetic fixture,2026-10-23\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(exclusions.REGISTER_ENV_VAR, str(register))
    monkeypatch.setattr(exclusions, "_CACHE", {})

    for mod in (rs, pr):
        monkeypatch.setattr(mod, "INCOMING_ROOT", incoming)
        monkeypatch.setattr(mod, "PROVENANCE_DIR", prov_dir)
    monkeypatch.setattr(pr, "PROVENANCE_MD", prov_md)
    monkeypatch.setattr(pr, "SPD_ROOT", spd)
    monkeypatch.setattr(pr, "GVR_RECORDINGS_ROOT", gvr)
    return {"incoming": incoming, "prov": prov_dir, "prov_md": prov_md,
            "spd": spd, "gvr": gvr, "tmp": tmp_path}


def _session(env, *, clips, meta_extra=None, program="D5") -> Path:
    d = env["incoming"] / SESSION
    d.mkdir(parents=True, exist_ok=True)
    meta = {
        "session_id": SESSION,
        "program": program,
        "reciter": "fixture-reciter",
        "reciter_slug": "fixture",
        "location": "synthetic fixture room",
        "device": "synthetic fixture mic",
        "consent_confirmed": True,
        "source_id": "SPD-SYNTHETIC",
        "recitation_tradition": "synthetic fixture tradition",
        "wordlist_version": VERSION,
        "started_utc": STARTED,
        "protocol": "files/RecordingProtocol.md",
    }
    meta.update(meta_extra or {})
    (d / "session_meta.json").write_text(json.dumps(meta), encoding="utf-8")
    for make in clips:
        make(d)
    return d


def _canonical(d: Path):
    return _speech_wav(d / "spd_kRSNa_canonical_t0.wav")


def _recitation(d: Path):
    return _speech_wav(d / "spd_kRSNa_recitation_t0.wav", f0=150.0)


def _sheet(env) -> Path:
    return env["prov"] / f"REC_{SESSION}.md"


def _gen(env) -> int:
    return rs.main(["--session", SESSION])


# ------------------------------------------------------------ pre-filling


def test_synthetic_skeleton_prefills_only_machine_known_fields(env, capsys):
    _session(env, clips=(_canonical, _recitation))
    assert _gen(env) == 0
    text = _sheet(env).read_text(encoding="utf-8")

    assert "**Program:** D5" in text
    assert f"| **Session ID** | {SESSION} |" in text
    assert f"| **Date / time** | {STARTED} |" in text
    assert f"| **Recording format** | {rs.RECORDING_FORMAT} |" in text
    assert f"| **Materials & version** | {VERSION} |" in text

    rows = [ln for ln in text.splitlines() if ln.startswith("| spd_")]
    assert len(rows) == 2
    canonical = next(r for r in rows if "canonical" in r)
    cells = [c.strip() for c in canonical.strip("|").split("|")]
    assert cells[0] == "spd_kRSNa_canonical_t0.wav"
    assert cells[1] == SESSION
    assert cells[2] == "kRSNa"
    assert cells[3] == "0"
    assert cells[4] == "1.000"
    assert re.fullmatch(r"-?\d+\.\d", cells[5])   # peak dBFS, 1 decimal
    assert cells[6] == "no"


def test_synthetic_clipping_is_measured_not_guessed(env, capsys):
    _session(env, clips=(lambda d: _speech_wav(
        d / "spd_kRSNa_canonical_t0.wav", scale=1.0),))
    assert _gen(env) == 0
    row = next(ln for ln in _sheet(env).read_text(encoding="utf-8").splitlines()
               if ln.startswith("| spd_"))
    cells = [c.strip() for c in row.strip("|").split("|")]
    assert cells[6] == "yes"


def test_synthetic_skeleton_leaves_human_fields_blank(env, capsys):
    _session(env, clips=(_canonical,))
    assert _gen(env) == 0
    text = _sheet(env).read_text(encoding="utf-8")

    for field in rs.HUMAN_ONLY_FIELDS:
        assert re.search(
            rf"^\| \*\*{re.escape(field)}\*\* \|\s*\|$", text, re.MULTILINE
        ), field
    # And the four human §2 columns stay empty on every row.
    for line in text.splitlines():
        if line.startswith("| spd_"):
            assert line.endswith("|  |  |  |  |")


def test_synthetic_unparsed_clip_gets_blank_item_and_take(env, capsys):
    _session(env, clips=(_canonical,
                         lambda d: _speech_wav(d / "stray_take.wav")))
    assert _gen(env) == 0
    row = next(ln for ln in _sheet(env).read_text(encoding="utf-8").splitlines()
               if ln.startswith("| stray_take.wav"))
    cells = [c.strip() for c in row.strip("|").split("|")]
    assert cells[2] == "" and cells[3] == ""  # item/take never guessed


# -------------------------------------------------- promote integration


def _fill_human_fields(text: str) -> str:
    values = {field: f"synthetic {field.lower()}" for field in rs.HUMAN_ONLY_FIELDS}
    values["Recitation tradition"] = "synthetic fixture tradition"
    values["Consent"] = "CONSENT-SYNTHETIC-01 (fixture form)"
    out = []
    for line in text.splitlines():
        m = re.match(r"^\| \*\*(.+?)\*\* \|\s*\|$", line)
        if m and m.group(1) in values:
            line = f"| **{m.group(1)}** | {values[m.group(1)]} |"
        elif line.startswith("| spd_") or line.startswith("| gvr_"):
            assert line.endswith("|  |  |  |  |")
            line = line[: -len("|  |  |  |  |")] + (
                "| no | yes | 2026-10-23 | SPD-SYNTHETIC |"
            )
        out.append(line)
    return "\n".join(out)


def test_synthetic_fresh_skeleton_is_refused_by_promote(env, capsys):
    _session(env, clips=(_canonical,))
    assert _gen(env) == 0
    capsys.readouterr()

    rc = pr.main(["--session", SESSION, "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0  # dry run reports, never blocks
    assert "HOLD spd_kRSNa_canonical_t0.wav" in out
    assert "§1 field 'Reciter ID' is empty" in out
    assert "§2 row for 'spd_kRSNa_canonical_t0.wav' has empty field(s)" in out
    assert "Silence trimmed?" in out
    assert "Provenance entry" in out
    assert "PASS spd_" not in out


def test_synthetic_completed_skeleton_passes_sheet_and_checklist(env, capsys):
    _session(env, clips=(_canonical, _recitation))
    assert _gen(env) == 0
    sheet = _sheet(env)
    sheet.write_text(_fill_human_fields(sheet.read_text(encoding="utf-8")),
                     encoding="utf-8")
    capsys.readouterr()

    rc = pr.main(["--session", SESSION, "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "session sheet:" in out and "— PASS" in out
    assert "provenance:" in out and "— PASS" in out
    assert out.count("PASS spd_") == 2
    assert "session_sheet" not in out
    assert "checklist_row" not in out


# ------------------------------------------------------------- refusals


def _refusal(capsys, rc, needle):
    assert rc == 2
    err = capsys.readouterr().err.strip()
    assert needle in err
    assert len(err.splitlines()) == 1
    return err


def test_synthetic_malformed_and_unknown_sessions_are_refused(env, capsys):
    rc = rs.main(["--session", "bad id!"])
    _refusal(capsys, rc, "malformed session id")

    rc = rs.main(["--session", "SPD-REC-20990101-01"])
    _refusal(capsys, rc, "unknown session")


def test_synthetic_missing_meta_and_no_clips_are_refused(env, capsys):
    d = env["incoming"] / SESSION
    d.mkdir()
    _speech_wav(d / "spd_kRSNa_canonical_t0.wav")
    rc = rs.main(["--session", SESSION])
    _refusal(capsys, rc, "session_meta.json missing")

    for p in d.glob("*.wav"):
        p.unlink()
    _session(env, clips=())  # meta only, no wavs
    rc = rs.main(["--session", SESSION])
    _refusal(capsys, rc, "session has no clips")


def test_synthetic_existing_sheet_is_not_clobbered(env, capsys):
    _session(env, clips=(_canonical,))
    sheet = _sheet(env)
    sheet.write_text("hand-filled synthetic sheet\n", encoding="utf-8")

    rc = rs.main(["--session", SESSION])
    _refusal(capsys, rc, "sheet already exists")
    assert sheet.read_text(encoding="utf-8") == "hand-filled synthetic sheet\n"


def test_synthetic_force_backs_up_then_rewrites(env, capsys):
    _session(env, clips=(_canonical,))
    sheet = _sheet(env)
    sheet.write_text("hand-filled synthetic sheet\n", encoding="utf-8")

    rc = rs.main(["--session", SESSION, "--force"])
    captured = capsys.readouterr()
    assert rc == 0, captured.err
    assert "backup:" in captured.out

    backups = sorted(env["prov"].glob(f"REC_{SESSION}.md.bak-*"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "hand-filled synthetic sheet\n"
    assert _sheet(env).read_text(encoding="utf-8").startswith(f"# REC {SESSION}")
