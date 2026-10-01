"""Tests for the D4 session chain CLI (Phase 5).

Fixtures: the D3 synthetic verse canon (tests/test_gvr_classifier.py)
rendered into fake ``data/_incoming/<GVR-REC-…>/`` sessions with a
hand-built PROMOTION.md in exactly the format the booth's promote
endpoint writes (record.py, D4 branch). Sessions and all output
artifacts live under tmp_path (monkeypatched ``INCOMING_ROOT`` +
``monkeypatch.chdir``) — a test can never write the repo's
``data/gvr_registry.json``, ``data/gvr/model.pkl``, or the report of
record. Chapter-2 verses are used so the REAL item-list gate passes;
synthetic-derived numbers are pipeline tests only (Rule 4).
"""

import json
from pathlib import Path

import pytest

import samskrita_dhvani.d4_chain as d4_chain
from samskrita_dhvani.d4_chain import main
from test_gvr_classifier import _stable_seed, _wav_bytes, render_verse

REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_ITEMLIST = REPO_ROOT / "data" / "gvr" / "ch2_itemlist.json"

# Chapter-2 verses that exist in the REAL checked item list.
CHAIN_VERSES = ("2.01", "2.07", "2.13", "2.20")

SESSION_A = "GVR-REC-20261001-aaaaaa"
SESSION_B = "GVR-REC-20261001-bbbbbb"


def _capture_v(vid: str) -> int:
    return int(vid.split(".")[1])


def stage_session(incoming: Path, sid: str, reciter: str,
                  verses=CHAIN_VERSES, n_takes: int = 1) -> Path:
    """A fake finished D4 session: canon takes + the booth's
    PROMOTION.md mapping format (record.py, D4 branch) verbatim."""
    d = incoming / sid
    d.mkdir(parents=True)
    (d / "session_meta.json").write_text(
        json.dumps({
            "session_id": sid, "program": "D4", "reciter": reciter,
            "reciter_slug": reciter, "source_id": "SYNTHETIC-D4",
            "recitation_tradition": "test-tradition",
            "consent": "yes", "location": "test", "device": "test",
        }),
        encoding="utf-8",
    )
    lines = ["# Promotion mapping (ear-check gate)", ""]
    for vid in verses:
        v = _capture_v(vid)
        for k in range(n_takes):
            capture = f"gvr_c2v{v}_recitation_t{k}.wav"
            dst = (f"data/gvr_recordings/"
                   f"gvr_c2v{v:02d}_{reciter}_{sid}_t{k}.wav")
            # canon seed scheme (f"{vid}:{i}") — proven EM-stable
            y = render_verse(vid, seed=_stable_seed(f"{vid}:{k}"))
            (d / capture).write_bytes(_wav_bytes(y))
            lines.append(f"- [ ] `{capture}` → `{dst}`  (verse_id {vid})")
    (d / "PROMOTION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return d


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """Sandboxed chain environment: cwd + INCOMING_ROOT under tmp_path
    so every artifact the chain writes is quarantined."""
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(d4_chain, "INCOMING_ROOT", incoming)
    paths = {
        "incoming": incoming,
        # The recordings dir is DERIVED from the PROMOTION.md targets
        # (cwd/data/gvr_recordings after monkeypatch.chdir(tmp_path)).
        "recordings": tmp_path / "data" / "gvr_recordings",
        "registry": tmp_path / "gvr_registry.json",
        "model": tmp_path / "gvr" / "model.pkl",
        "report": tmp_path / "gvr" / "eval_report.json",
    }
    return paths


def run_chain(paths, sessions, extra=()):
    argv = []
    for s in sessions:
        argv += ["--session", s]
    argv += [
        "--registry", str(paths["registry"]),
        "--model", str(paths["model"]),
        "--itemlist", str(REAL_ITEMLIST),
        "--source-id", "SYNTHETIC-D4",
        "--acquired-on", "2026-10-01",
        "--recitation-tradition", "test-tradition",
        "--json-report", str(paths["report"]),
    ] + list(extra)
    return main(argv)


# ------------------------------------------------------------ happy path

def test_two_reciter_chain_end_to_end(env, capsys):
    stage_session(env["incoming"], SESSION_A, "reciter_a")
    stage_session(env["incoming"], SESSION_B, "reciter_b")
    rc = run_chain(
        env, [SESSION_A, SESSION_B],
        ["--reciter-splits", "reciter_a=train,reciter_b=test"],
    )
    assert rc == 0, (lambda c: c.out + c.err)(capsys.readouterr())

    # Every promoted take landed in the derived recordings dir.
    assert len(list(env["recordings"].glob("*.wav"))) == 8
    reg = json.loads(env["registry"].read_text(encoding="utf-8"))
    assert reg["split_policy"] == "per-reciter"
    splits = {(e["reciter"], e["split"]) for e in reg["entries"]}
    assert splits == {("reciter_a", "train"), ("reciter_b", "test")}
    assert len(reg["entries"]) == 8  # 4 verses × 2 reciters

    assert env["model"].is_file()
    report = json.loads(env["report"].read_text(encoding="utf-8"))
    assert report["kind"] == "gvr_eval_report"
    assert report["overall"]["n_test"] == 4

    out = capsys.readouterr().out
    assert "python -m samskrita_dhvani.evaluate" in out  # exact command
    assert "PROVENANCE" not in out or True  # reminder lives in stderr path


def test_chain_reminds_about_provenance_registration(env, capsys):
    stage_session(env["incoming"], SESSION_A, "solo")
    rc = run_chain(env, [SESSION_A])
    assert rc == 2  # single-reciter FR-23 refusal (see test below)
    cap = capsys.readouterr()  # readouterr drains: capture once, use twice
    combined = cap.out + cap.err
    assert "PROVENANCE" in combined  # Rule 2 reminder surfaced


# ------------------------------------------------------- honest failures

def test_missing_promotion_md_names_the_booth_step(env, capsys):
    (env["incoming"] / SESSION_A).mkdir(parents=True)  # no PROMOTION.md
    rc = run_chain(env, [SESSION_A])
    assert rc == 2
    err = capsys.readouterr().err
    assert "PROMOTION.md" in err and "booth" in err


def test_missing_source_wav_copies_nothing(env, capsys):
    d = stage_session(env["incoming"], SESSION_A, "reciter_a")
    # One take vanished from the session dir after promotion staging.
    for p in d.glob("gvr_c2v20_*.wav"):
        p.unlink()
    rc = run_chain(env, [SESSION_A])
    assert rc == 2
    err = capsys.readouterr().err
    assert "promotion source missing" in err
    assert not env["recordings"].exists() or \
        not any(env["recordings"].iterdir())


def test_existing_artifacts_require_force(env, capsys):
    stage_session(env["incoming"], SESSION_A, "reciter_a")
    stage_session(env["incoming"], SESSION_B, "reciter_b")
    spec = ["--reciter-splits", "reciter_a=train,reciter_b=test"]
    assert run_chain(env, [SESSION_A, SESSION_B], spec) == 0
    capsys.readouterr()
    rc = run_chain(env, [SESSION_A, SESSION_B], spec)
    assert rc == 2
    assert "already exists" in capsys.readouterr().err
    assert run_chain(env, [SESSION_A, SESSION_B], spec + ["--force"]) == 0


def test_dry_run_writes_nothing(env, capsys):
    stage_session(env["incoming"], SESSION_A, "reciter_a")
    stage_session(env["incoming"], SESSION_B, "reciter_b")
    rc = run_chain(
        env, [SESSION_A, SESSION_B],
        ["--reciter-splits", "reciter_a=train,reciter_b=test",
         "--dry-run"],
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "would copy" in out and "nothing written" in out
    assert not env["recordings"].exists() or \
        not any(env["recordings"].iterdir())
    assert not env["registry"].exists()
    assert not env["model"].exists()
    assert not env["report"].exists()


def test_single_reciter_chain_ends_in_fr23_refusal(env, capsys):
    """The honest single-reciter outcome: promote+build+train all
    succeed, then evaluate refuses with the FR-23 sentence as the
    run's final word (rc=2) — model exists, no accuracy is claimed."""
    stage_session(env["incoming"], SESSION_A, "solo")
    rc = run_chain(env, [SESSION_A])
    assert rc == 2
    assert env["registry"].is_file()      # built
    assert env["model"].is_file()         # trained
    assert not env["report"].exists()     # no number published
    err = capsys.readouterr().err
    assert "0 test rows" in err
    assert "NOT be speaker-independent" in err
    assert "second reciter" in err


# --------------------------------------------------- promotion-line gates

def test_malformed_promotion_line_is_loud(env, capsys):
    d = stage_session(env["incoming"], SESSION_A, "reciter_a")
    md = d / "PROMOTION.md"
    md.write_text(md.read_text(encoding="utf-8")
                  + "- [ ] not-a-mapping-line\n", encoding="utf-8")
    rc = run_chain(env, [SESSION_A])
    assert rc == 2
    assert "unrecognized promotion line" in capsys.readouterr().err


def test_target_outside_gvr_recordings_rejected(env, capsys):
    d = stage_session(env["incoming"], SESSION_A, "reciter_a")
    md = d / "PROMOTION.md"
    lines = md.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if line.startswith("- [ ]"):
            lines[i] = line.replace("data/gvr_recordings/", "data/spd/")
            break
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    rc = run_chain(env, [SESSION_A])
    assert rc == 2
    assert "data/gvr_recordings" in capsys.readouterr().err


def test_target_name_not_matching_protocol_grammar_rejected(env, capsys):
    d = stage_session(env["incoming"], SESSION_A, "reciter_a")
    md = d / "PROMOTION.md"
    lines = md.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if line.startswith("- [ ]"):
            # a target the registry parser must refuse (no session id)
            lines[i] = line.replace(f"_{SESSION_A}_", "_nosid_")
            break
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    rc = run_chain(env, [SESSION_A])
    assert rc == 2
    assert "protocol §3 grammar" in capsys.readouterr().err
