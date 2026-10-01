"""Tests for the held-out evaluation CLI (Phase 5, NFR-20/FR-23).

Fixtures reuse the D3 synthetic verse canon from
``tests/test_gvr_classifier.py`` (``verse_plan``/``render_verse``/
``_wav_bytes`` — four pseudo-vowel "verses" with distinct formant
plans). No new synthetic recipe, no corpus audio (NFR-02, Ground Rule
4). Synthetic-derived numbers here are pipeline tests ONLY
(DataIntegrity Rule 4) — they never enter any reported result.
"""

import json
import re
import wave
import zlib
from types import SimpleNamespace
from pathlib import Path

import numpy as np
import pytest

import samskrita_dhvani.evaluate as evaluate_mod
from samskrita_dhvani.evaluate import (
    EVAL_REPORT_KIND,
    PER_RECITER_SENTENCE,
    PER_RECORDING_SENTENCE,
    EvalDataError,
    evaluate,
    main,
)
from samskrita_dhvani.gvr_classifier import GvrRecognizer
from samskrita_dhvani.registry import GvrRegistry, VerseEntry

# D3 fixture canon (tests/test_gvr_classifier.py)
from test_gvr_classifier import (
    SR,
    VERSE_IDS,
    _stable_seed,
    _wav_bytes,
    render_verse,
)

PROVENANCE = {"source_id": "SYNTHETIC", "acquired_on": "2026-10-01"}


def _load_wav(path):
    with wave.open(str(path), "rb") as w:
        y = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
    return (y / 32767.0).astype(np.float32)


def _write_clip(tmp_path, vid, tag, i):
    # tag "v" = the canon seed scheme (proven EM-stable for training
    # in tests/test_gvr_classifier.py); other tags are test-only rows
    # and may use any deterministic seed.
    if tag == "v":
        seed = _stable_seed(f"{vid}:{i}")
    else:
        seed = _stable_seed(f"{tag}:{vid}:{i}")
    y = render_verse(vid, seed=seed)
    p = tmp_path / f"{tag}_{vid.replace('.', '_')}_{i}.wav"
    p.write_bytes(_wav_bytes(y))
    return p


def build_registry(tmp_path, per_reciter=True, n_train=2):
    """4-verse synthetic registry: ``n_train`` train takes + 1 test
    take per verse. ``per_reciter=False`` puts everything on one
    reciter (the per-recording single-reciter case)."""
    entries = []
    for vid in VERSE_IDS:
        if per_reciter:
            layout = [(f"reciter-{i}", "train") for i in range(n_train)]
            layout.append(("reciter-2", "test"))
        else:
            layout = [("solo", "train")] * n_train + [("solo", "test")]
        for i, (reciter, split) in enumerate(layout):
            p = _write_clip(tmp_path, vid, "v", i)
            entries.append(
                VerseEntry(
                    verse_id=vid,
                    audio_file=str(p),
                    reciter=reciter,
                    split=split,
                    devanagari_text=f"॥ {vid} ॥" if i == 0 else None,
                    provenance=dict(PROVENANCE),
                )
            )
    return GvrRegistry(entries)


def train_model(registry):
    # Default n_iter (100) — the configuration pinned by the unit-4
    # tests; the degeneracy guard is data-honest, not a test knob.
    return GvrRecognizer.train(registry, _load_wav)


def _write_artifacts(tmp_path, registry, recognizer):
    reg_path = tmp_path / "registry.json"
    model_path = tmp_path / "model.pkl"
    registry.to_json(reg_path)
    recognizer.save(model_path)
    return str(reg_path), str(model_path)


# ------------------------------------------------------- full wiring

def test_perfect_run_on_synthetic_verses(tmp_path):
    reg = build_registry(tmp_path)
    rec = train_model(reg)
    report = evaluate(rec, reg)
    assert report["kind"] == EVAL_REPORT_KIND == "gvr_eval_report"
    assert report["schema_version"] == 1
    assert report["overall"]["n_test"] == 4
    assert report["overall"]["n_correct"] == 4
    assert report["overall"]["accuracy_fraction"] == 1.0
    assert report["overall"]["accuracy_percent"] == 100.0
    assert report["rows_by_split"] == {"train": 8, "validation": 0,
                                       "test": 4}
    labels = report["confusion"]["labels"]
    assert labels == sorted(VERSE_IDS)
    matrix = report["confusion"]["matrix"]
    for i, row in enumerate(matrix):
        assert sum(row) == 1 and row[i] == 1  # diagonal, support 1 each
    assert report["fr23_statement"] == PER_RECITER_SENTENCE
    assert report["speaker_overlap_note"] is None
    # Curve: one point per verse at x = 2 training clips, recall 1.
    pts = report["curve"]["points"]
    assert len(pts) == 4
    assert all(pt["n_training_clips"] == 2 and pt["recall"] == 1.0
               for pt in pts)
    assert report["curve"]["note"] is not None  # single x → no trend yet


def test_forced_wrong_predictions_metric_math(tmp_path, monkeypatch):
    reg = build_registry(tmp_path)
    rec = train_model(reg)
    # Deterministic forced predictions (test rows arrive in registry
    # order): two swaps, one hit, one miss to a shared target.
    queue = iter(["4.07", "2.13", "9.26", "9.26"])

    def fake(audio, **kwargs):
        return SimpleNamespace(verse_id=next(queue), confidence=0.5,
                               candidates=[])

    monkeypatch.setattr(rec, "predict", fake)
    report = evaluate(rec, reg)
    assert report["overall"]["n_test"] == 4
    assert report["overall"]["n_correct"] == 1
    assert report["overall"]["accuracy_fraction"] == 0.25
    assert report["overall"]["accuracy_percent"] == 25.0
    labels = report["confusion"]["labels"]  # sorted: 18.66,2.13,4.07,9.26
    matrix = report["confusion"]["matrix"]
    assert matrix[labels.index("2.13")] == [0, 0, 1, 0]   # → 4.07
    assert matrix[labels.index("4.07")] == [0, 1, 0, 0]   # → 2.13
    assert matrix[labels.index("9.26")] == [0, 0, 0, 1]   # hit
    assert matrix[labels.index("18.66")] == [0, 0, 0, 1]  # → 9.26
    verses = report["verses"]
    assert verses["2.13"]["recall"] == 0.0
    assert verses["4.07"]["recall"] == 0.0
    assert verses["9.26"]["recall"] == 1.0
    assert verses["18.66"]["recall"] == 0.0
    assert verses["9.26"]["n_correct"] == 1
    assert all(v["support"] == 1 for v in verses.values())
    curve = {pt["verse_id"]: pt["recall"] for pt in report["curve"]["points"]}
    assert curve == {"2.13": 0.0, "4.07": 0.0, "9.26": 1.0, "18.66": 0.0}
    assert report["unmodelled_test_verses"] == []
    text = evaluate_mod._render_report(report)
    assert "1/4 = 0.2500 (25.0%)" in text


# --------------------------------------------------- FR-23 statements

def test_per_recording_all_train_refuses_with_fr23_sentence(tmp_path):
    # The truthful single-reciter state build_registry auto-emits:
    # every row train, policy per-recording. A (verse, reciter) pair
    # cannot span two splits, so no leak-free held-out split EXISTS
    # for one reciter — the refusal must carry the FR-23 sentence.
    reg = build_registry(tmp_path, per_reciter=False)
    assert reg.split_policy == "per-reciter"
    per_rec = GvrRegistry(
        [e for e in reg.entries if e.split == "train"],
        split_policy="per-recording",
    )
    rec = train_model(per_rec)
    with pytest.raises(EvalDataError, match="0 test rows") as ei:
        evaluate(rec, per_rec)
    assert "would NOT be speaker-independent" in str(ei.value)


def test_declared_per_recording_policy_prints_the_sentence(tmp_path):
    # An operator-declared per-recording policy over ≥2 reciters is
    # constructible (GvrRegistry allows it); the report must carry
    # the sentence verbatim.
    reg = build_registry(tmp_path)
    per_rec = GvrRegistry(list(reg.entries), split_policy="per-recording")
    rec = train_model(per_rec)
    report = evaluate(rec, per_rec)
    assert report["split_policy"] == "per-recording"
    assert report["fr23_statement"] == PER_RECORDING_SENTENCE
    assert "NOT speaker-independent" in report["fr23_statement"]
    assert report["speaker_overlap_note"] is None  # disjoint reciters


def test_speaker_overlap_computed_and_named(tmp_path):
    # Overlap WITHOUT changing any training inputs: rename one canon
    # train row's reciter to reciter-9 (same clip, same per-verse
    # train counts — training stays byte-identical to the base run),
    # and move 4.07's test slot to reciter-9 too. reciter-9 then sits
    # in BOTH splits (on different verses — no leak) and must be
    # named in the computed note.
    reg = build_registry(tmp_path)
    entries = []
    for e in reg.entries:
        if e.split == "train" and e.verse_id == "9.26" \
                and e.reciter == "reciter-0":
            e = VerseEntry(verse_id=e.verse_id, audio_file=e.audio_file,
                           reciter="reciter-9", split="train",
                           devanagari_text=e.devanagari_text,
                           provenance=dict(PROVENANCE))
        if e.split == "test" and e.verse_id == "4.07":
            e = VerseEntry(verse_id=e.verse_id, audio_file=e.audio_file,
                           reciter="reciter-9", split="test",
                           devanagari_text=e.devanagari_text,
                           provenance=dict(PROVENANCE))
        entries.append(e)
    reg2 = GvrRegistry(entries)
    assert reg2.split_policy == "per-reciter"
    rec = train_model(reg2)
    report = evaluate(rec, reg2)
    note = report["speaker_overlap_note"]
    assert note and "reciter-9" in note
    assert "not fully speaker-independent" in note


def test_zero_test_rows_refuses_fr23(tmp_path):
    reg = build_registry(tmp_path)
    rec = train_model(reg)
    reg_path, model_path = _write_artifacts(tmp_path, reg, rec)
    # Rewrite the registry with every test row demoted to validation.
    data = json.loads(Path(reg_path).read_text(encoding="utf-8"))
    for e in data["entries"]:
        if e["split"] == "test":
            e["split"] = "validation"
    Path(reg_path).write_text(json.dumps(data), encoding="utf-8")
    rc = main(["--registry", reg_path, "--model", model_path])
    assert rc == 2
    # Direct call raises the named error too.
    reg2 = GvrRegistry.from_json(reg_path)
    with pytest.raises(EvalDataError, match="0 test rows"):
        evaluate(rec, reg2)


def test_predict_called_once_per_test_row_only(tmp_path, monkeypatch):
    reg = build_registry(tmp_path)  # 12 train rows + 4 test rows
    rec = train_model(reg)
    calls = []

    def spy(audio, **kwargs):
        calls.append(audio)
        return GvrRecognizer.predict(rec, audio, **kwargs)

    monkeypatch.setattr(rec, "predict", spy)
    report = evaluate(rec, reg)
    # Exactly one call per test row: any train/validation row reaching
    # predict would push the count past n_test (FR-23, structurally).
    assert len(calls) == report["overall"]["n_test"] == 4


# -------------------------------------------------- honest absence

def test_absent_registry_and_model_are_loud(tmp_path, capsys):
    missing_reg = tmp_path / "nope.json"
    missing_model = tmp_path / "nope.pkl"
    rc = main(["--registry", str(missing_reg), "--model",
               str(missing_model)])
    assert rc == 2
    err = capsys.readouterr().err
    assert "registry not found" in err and str(missing_reg) in err

    reg = build_registry(tmp_path)
    rec = train_model(reg)
    reg_path, _ = _write_artifacts(tmp_path, reg, rec)
    rc = main(["--registry", reg_path, "--model", str(missing_model)])
    assert rc == 2
    err = capsys.readouterr().err
    assert "no model, no number" in err and str(missing_model) in err


def test_corrupt_test_row_audio_stops_loud(tmp_path):
    reg = build_registry(tmp_path)
    rec = train_model(reg)
    test_entry = next(e for e in reg.entries if e.split == "test")
    Path(test_entry.audio_file).write_bytes(b"definitely not a wav")
    with pytest.raises(EvalDataError, match="failed to decode"):
        evaluate(rec, reg)


def test_all_test_rows_unmodelled_refuses_to_report(tmp_path):
    reg = build_registry(tmp_path)
    rec = train_model(reg)
    # Same train rows, but the only test row is a verse the model has
    # never seen: registry and model do not describe one experiment.
    extra = _write_clip(tmp_path, "7.01", "extra", 0)
    reg2 = GvrRegistry(
        [e for e in reg.entries if e.split == "train"]
        + [VerseEntry(verse_id="7.01", audio_file=str(extra),
                      reciter="r-x", split="test",
                      provenance=dict(PROVENANCE))]
    )
    with pytest.raises(EvalDataError,
                       match="do not describe the same experiment"):
        evaluate(rec, reg2)


# ------------------------------------- unmodelled verses (NFR-20 case)

def test_unmodelled_test_verse_counted_incorrect_and_off_curve(tmp_path):
    reg = build_registry(tmp_path)
    rec = train_model(reg)
    del rec.verses["18.66"]  # verse without train rows (unit-7 case)
    report = evaluate(rec, reg)
    assert report["overall"]["n_test"] == 4
    assert report["overall"]["n_correct"] == 3
    assert report["overall"]["accuracy_fraction"] == 0.75
    assert [u["verse_id"] for u in report["unmodelled_test_verses"]] == [
        "18.66"
    ]
    labels = report["confusion"]["labels"]
    i = labels.index("18.66")
    row = report["confusion"]["matrix"][i]
    assert sum(row) == 1 and row[i] == 0  # in support, not correct
    assert "18.66" not in [pt["verse_id"] for pt in
                           report["curve"]["points"]]
    assert len(report["curve"]["points"]) == 3
    v = report["verses"]["18.66"]
    assert v["modelled"] is False and v["recall"] is None
    assert v["n_training_clips"] is None and v["support"] == 1
    text = evaluate_mod._render_report(report)
    assert "Counted INCORRECT" in text and "18.66" in text


# -------------------------------------------------- NFR-20 curve shape

def test_curve_note_when_every_verse_has_one_training_clip(tmp_path):
    reg = build_registry(tmp_path, n_train=1)
    rec = train_model(reg)
    report = evaluate(rec, reg)
    assert all(pt["n_training_clips"] == 1
               for pt in report["curve"]["points"])
    assert report["curve"]["note"] is not None
    assert "1 training clip(s)" in report["curve"]["note"]


def test_single_recitation_support_marked_and_extra_row_unmarked(
    tmp_path,
):
    reg = build_registry(tmp_path)
    rec = train_model(reg)
    extra = _write_clip(tmp_path, "2.13", "extra", 0)
    reg2 = GvrRegistry(
        list(reg.entries)
        + [VerseEntry(verse_id="2.13", audio_file=str(extra),
                      reciter="reciter-3", split="test",
                      provenance=dict(PROVENANCE))]
    )
    report = evaluate(rec, reg2)
    assert report["verses"]["2.13"]["support"] == 2
    assert report["verses"]["2.13"]["single_row_support"] is False
    assert report["verses"]["4.07"]["support"] == 1
    assert report["verses"]["4.07"]["single_row_support"] is True
    assert report["overall"]["n_test"] == 5
    text = evaluate_mod._render_report(report)
    assert "*" in text  # data-starved marker present


# ---------------------------------------------------------- artifacts

def test_json_report_written_and_deterministic(tmp_path, capsys):
    reg = build_registry(tmp_path)
    rec = train_model(reg)
    reg_path, model_path = _write_artifacts(tmp_path, reg, rec)
    out1, out2 = tmp_path / "r1.json", tmp_path / "r2.json"
    base = ["--registry", reg_path, "--model", model_path]
    assert main(base + ["--json", str(out1)]) == 0
    assert main(base + ["--json", str(out2)]) == 0
    assert out1.read_text(encoding="utf-8") == out2.read_text(
        encoding="utf-8"
    )
    data = json.loads(out1.read_text(encoding="utf-8"))
    assert data["kind"] == EVAL_REPORT_KIND and data["schema_version"] == 1
    # The printed headline comes from the same numbers as the JSON
    # (Ground Rule 1: one source for any recorded number).
    printed = capsys.readouterr().out
    m = re.search(r"(\d+)/(\d+) = ", printed)
    assert m and int(m.group(1)) == data["overall"]["n_correct"]
    assert int(m.group(2)) == data["overall"]["n_test"]


def test_curve_png_written(tmp_path):
    reg = build_registry(tmp_path)
    rec = train_model(reg)
    reg_path, model_path = _write_artifacts(tmp_path, reg, rec)
    png = tmp_path / "curve.png"
    assert main(["--registry", reg_path, "--model", model_path,
                 "--curve-png", str(png)]) == 0
    assert png.is_file()
    assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
