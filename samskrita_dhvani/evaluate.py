"""CLI: held-out evaluation of the trained GVR recognizer (Phase 5).

Run: ``python -m samskrita_dhvani.evaluate --help``.

FR-22 plan §5 step 5 — the NFR-20/FR-23 reporting infrastructure:

- **FR-23 is structural, not optional:** only rows whose registry
  split is ``test`` are ever scored. Train/validation rows are counted
  for transparency and skipped for scoring. The split policy is stated
  in the output, and a ``per-recording`` policy (single-reciter
  corpora) carries the mandatory "NOT speaker-independent" sentence.
  An evaluator that could also train could silently evaluate its own
  training — so this script has NO training mode by design; training
  is plan §5 step 4's boundary.
- **NFR-20:** alongside the headline accuracy (always the exact
  fraction ``n_correct/n_test`` — a lone percent is never the
  headline) it reports the confusion matrix (rows = true verse,
  cols = predicted verse), per-verse recall + support, and the
  accuracy-vs-training-examples-per-verse curve. ``x`` comes from the
  model envelope's ``n_training_clips`` — the ground truth for what
  actually trained — and ``y`` is that verse's held-out recall.
- **Honest absence (Ground Rule 1):** a missing registry, missing
  model, zero test rows, or a test clip that no longer decodes stops
  the run loudly with the exact artifact path — no number is
  fabricated, nothing is skipped silently (the 503 honesty pattern,
  on disk). A test verse with no trained model is counted INCORRECT
  (it cannot be recognized), named in the output, and excluded from
  the curve; if no test row has a trained model, the registry and the
  model do not describe the same experiment and the run refuses to
  report accuracy at all.
- **Scope (Ground Rule 2):** read-only over the existing artifacts —
  no change to the recognizer, scorer, booth, registry, or API.

Single-recitation support is marked ``*`` in the per-verse table: one
test clip is the weakest possible evidence, and NFR-20 exists exactly
so data-starved verses are visible instead of dissolved into the
headline.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from samskrita_dhvani.frontend import load_audio_16k
from samskrita_dhvani.gvr_classifier import MODEL_DEFAULT_PATH, GvrRecognizer
from samskrita_dhvani.registry import GvrRegistry

DEFAULT_REGISTRY = Path("data") / "gvr_registry.json"
DEFAULT_MODEL = MODEL_DEFAULT_PATH

EVAL_REPORT_SCHEMA_VERSION = 1
"""Bump when the report's fields/semantics change (Ground Rule 4)."""

EVAL_REPORT_KIND = "gvr_eval_report"

PER_RECITER_SENTENCE = (
    "split policy: per-reciter — each (verse, reciter) pair sits in "
    "exactly one split (GvrRegistry.assert_no_split_leak passed at "
    "registry load)."
)
PER_RECORDING_SENTENCE = (
    "split policy: per-recording (single-reciter corpus) — the "
    "accuracy below is NOT speaker-independent (FR-23)."
)
PER_RECORDING_REFUSAL_SUFFIX = (
    "The split policy is per-recording (single-reciter corpus): any "
    "accuracy from it would NOT be speaker-independent (FR-23), and "
    "one reciter's (verse, reciter) pairs cannot be split across "
    "train/test without a leak — record a second reciter for a "
    "per-reciter held-out split."
)


class EvalDataError(Exception):
    """A loud, named refusal to produce a number (rc=2)."""


def _percent(fraction: float) -> float:
    return round(fraction * 100.0, 2)


def _confusion_matrix(
    true_ids: list[str], pred_ids: list[str], labels: list[str]
) -> list[list[int]]:
    """Rows = true verse, cols = predicted verse."""
    index = {vid: i for i, vid in enumerate(labels)}
    m = [[0] * len(labels) for _ in labels]
    for t, p in zip(true_ids, pred_ids):
        m[index[t]][index[p]] += 1
    return m


def evaluate(
    recognizer: GvrRecognizer,
    registry: GvrRegistry,
    audio_loader=load_audio_16k,
) -> dict:
    """Score the registry's held-out test rows (FR-23) and build the
    full NFR-20 report dict. Raises :class:`EvalDataError` on the
    honest-absence conditions — never returns a fabricated number."""
    policy = registry.split_policy
    if policy == "per-recording":
        policy_sentence = PER_RECORDING_SENTENCE
    else:
        policy_sentence = PER_RECITER_SENTENCE

    train_rows = [e for e in registry.entries if e.split == "train"]
    validation_rows = [e for e in registry.entries if e.split == "validation"]
    test_rows = [e for e in registry.entries if e.split == "test"]
    if not test_rows:
        msg = (
            f"registry has 0 test rows (train {len(train_rows)} / "
            f"validation {len(validation_rows)}): FR-23 forbids scoring "
            "train rows — assign a held-out test split (build_registry "
            "--reciter-splits) and re-run"
        )
        if policy == "per-recording":
            msg += " " + PER_RECORDING_REFUSAL_SUFFIX
        raise EvalDataError(msg)

    # Speaker overlap is a computed fact either policy can produce.
    train_reciters = {e.reciter for e in train_rows}
    overlap = sorted(
        {e.reciter for e in test_rows} & train_reciters
    )
    if overlap:
        overlap_note = (
            "speaker overlap: test reciter(s) " + ", ".join(overlap) +
            " also hold train rows; recall on their test verses is not "
            "fully speaker-independent."
        )
    else:
        overlap_note = None

    true_ids: list[str] = []
    pred_ids: list[str] = []
    unmodelled: list[dict] = []
    modelled_test_rows = 0
    for e in test_rows:
        try:
            y = audio_loader(e.audio_file)
        except Exception as exc:  # noqa: BLE001 — loud stop, no silent skip
            raise EvalDataError(
                f"test row failed to decode: '{e.audio_file}' (verse "
                f"{e.verse_id}, reciter '{e.reciter}'): {exc} — fix or "
                "re-split the registry; a test row is never silently "
                "dropped"
        ) from exc
        if e.verse_id not in recognizer.verses:
            # Unmodelled test verse (e.g. an explicit split assignment
            # that left a verse without train rows): it cannot be
            # recognized, so it is counted incorrect — never skipped.
            unmodelled.append(
                {"verse_id": e.verse_id, "reciter": e.reciter,
                 "audio_file": e.audio_file}
            )
            true_ids.append(e.verse_id)
            pred_ids.append(e.verse_id + " (unmodelled)")
            continue
        modelled_test_rows += 1
        prediction = recognizer.predict(y)
        true_ids.append(e.verse_id)
        pred_ids.append(prediction.verse_id)

    if modelled_test_rows == 0:
        msg = (
            "no test row has a trained model: the registry and the "
            "model do not describe the same experiment — (re)train per "
            "plan §5 step 4 or rebuild the registry (FR-23: refusing "
            "to report a number)"
        )
        if policy == "per-recording":
            msg += " " + PER_RECORDING_REFUSAL_SUFFIX
        raise EvalDataError(msg)

    n_test = len(test_rows)
    n_correct = sum(
        1 for t, p in zip(true_ids, pred_ids) if t == p
    )
    fraction = n_correct / n_test

    # Verses present on either side of the evaluation — including
    # zero-support modelled verses (train-only data, no test rows) so
    # the curve shows the full training distribution (NFR-20).
    labels = sorted(set(true_ids) | set(pred_ids) | set(recognizer.verses))
    matrix = _confusion_matrix(true_ids, pred_ids, labels)

    n_train_clips = {
        vid: recognizer.verses[vid].n_training_clips
        for vid in recognizer.verses
    }
    test_support = Counter(true_ids)
    test_correct = Counter(
        t for t, p in zip(true_ids, pred_ids) if t == p
    )

    verses: dict[str, dict] = {}
    for vid in labels:
        support = test_support.get(vid, 0)
        modelled = vid in recognizer.verses
        if not modelled:
            verses[vid] = {
                "recall": None, "n_correct": test_correct.get(vid, 0),
                "support": support, "n_training_clips": None,
                "modelled": False,
                "single_row_support": support == 1,
            }
        else:
            recall = (
                test_correct.get(vid, 0) / support if support else None
            )
            verses[vid] = {
                "recall": recall, "n_correct": test_correct.get(vid, 0),
                "support": support,
                "n_training_clips": n_train_clips[vid],
                "modelled": True,
                "single_row_support": support == 1,
            }

    # NFR-20 curve: one point per modelled verse WITH test rows, at
    # x = its training-clip count, y = its held-out recall. Unmodelled
    # verses have no x and are excluded. Single-point honesty: if every
    # trained verse saw exactly one clip, no trend is displayable and
    # the report says so.
    curve_points = [
        {"verse_id": vid, "n_training_clips": n_train_clips[vid],
         "recall": verses[vid]["recall"]}
        for vid in labels
        if verses[vid]["modelled"] and verses[vid]["support"] > 0
    ]
    curve_points.sort(
        key=lambda pt: (pt["n_training_clips"], pt["verse_id"])
    )
    if curve_points and len({pt["n_training_clips"] for pt in curve_points}) == 1:
        curve_note = (
            "every trained verse saw exactly "
            f"{curve_points[0]['n_training_clips']} training clip(s): "
            "the curve is a single x value — no data-quantity trend is "
            "displayable yet"
        )
    elif not curve_points:
        curve_note = "no modelled verse has test rows: no curve"
    else:
        curve_note = None

    return {
        "schema_version": EVAL_REPORT_SCHEMA_VERSION,
        "kind": EVAL_REPORT_KIND,
        "split_policy": policy,
        "fr23_statement": policy_sentence,
        "speaker_overlap_note": overlap_note,
        "rows_by_split": {
            "train": len(train_rows),
            "validation": len(validation_rows),
            "test": n_test,
        },
        "overall": {
            "n_test": n_test,
            "n_correct": n_correct,
            "accuracy_fraction": fraction,
            "accuracy_percent": _percent(fraction),
        },
        "confusion": {
            "labels": labels,
            "matrix": matrix,
            "note": "rows = true verse, cols = predicted verse; "
                    "each row sums to that verse's test support",
        },
        "verses": verses,
        "curve": {
            "x_field": "n_training_clips (from the model envelope)",
            "y_field": "held-out recall on that verse's test rows",
            "points": curve_points,
            "note": curve_note,
        },
        "unmodelled_test_verses": unmodelled,
    }


def _render_confusion(report: dict) -> list[str]:
    labels = report["confusion"]["labels"]
    matrix = report["confusion"]["matrix"]
    lines = [
        "Confusion matrix (NFR-20) — " + report["confusion"]["note"] + ":"
    ]
    if not labels:
        lines.append("  (empty)")
        return lines
    width = max(6, max(len(v) for v in labels))
    lines.append("  " + " " * (width + 3)
                 + "  ".join(v.rjust(width) for v in labels))
    for vid, row in zip(labels, matrix):
        cells = "  ".join(str(n).rjust(width) for n in row)
        lines.append(f"  {(vid + ' →').ljust(width + 2)} {cells}")
    return lines


def _render_report(report: dict) -> str:
    out: list[str] = []
    overall = report["overall"]
    rows = report["rows_by_split"]
    out.append("GVR held-out evaluation (FR-23/NFR-20)")
    out.append(f"  rows: train {rows['train']} · validation "
               f"{rows['validation']} · test {rows['test']}")
    out.append(f"  {report['fr23_statement']}")
    if report["speaker_overlap_note"]:
        out.append(f"  {report['speaker_overlap_note']}")

    out.append("")
    out.append(
        f"Headline accuracy (held-out TEST rows only, FR-23): "
        f"{overall['n_correct']}/{overall['n_test']} = "
        f"{overall['accuracy_fraction']:.4f} "
        f"({overall['accuracy_percent']}%)"
    )

    out.append("")
    out.append("Per-verse recall (NFR-20; * = single-recitation "
               "support — data-starved):")
    out.append(f"  {'verse':<8}{'recall':>7}{'support':>9}"
               f"{'train_clips':>13}")
    for vid, v in report["verses"].items():
        star = "*" if v["single_row_support"] else " "
        if not v["modelled"]:
            recall = "—"
        elif v["recall"] is None:
            recall = "n/a"
        else:
            recall = f"{v['recall']:.2f}"
        clips = ("—" if v["n_training_clips"] is None
                 else str(v["n_training_clips"]))
        out.append(f"  {vid:<8}{recall:>7}{star}{v['support']:>8}"
                   f"{clips:>13}")

    out.extend(_render_confusion(report))

    out.append("")
    out.append("Accuracy vs training examples per verse (NFR-20):")
    for pt in report["curve"]["points"]:
        recall = pt["recall"]
        recall_s = "n/a" if recall is None else f"{recall:.2f}"
        out.append(f"  {pt['n_training_clips']} clip(s): {pt['verse_id']} "
                   f"recall {recall_s}")
    if report["curve"]["note"]:
        out.append(f"  note: {report['curve']['note']}")

    if report["unmodelled_test_verses"]:
        out.append("")
        out.append("Counted INCORRECT (not skipped — FR-23 honesty):")
        for u in report["unmodelled_test_verses"]:
            out.append(
                f"  '{u['audio_file']}' (verse {u['verse_id']}, reciter "
                f"'{u['reciter']}'): NO trained model for verse "
                f"{u['verse_id']} → counted incorrect (train the verse "
                "to fix)"
            )
    return "\n".join(out)


def _write_curve_png(report: dict, path: Path) -> None:
    """The NFR-20 scatter: x = training clips per verse, y = that
    verse's held-out recall, annotated with the verse id."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    pts = report["curve"]["points"]
    xs = [pt["n_training_clips"] for pt in pts]
    ys = [pt["recall"] for pt in pts]
    fig, ax = plt.subplots(figsize=(7.0, 4.5))
    ax.scatter(xs, ys, s=42, zorder=3)
    for pt in pts:
        ax.annotate(
            pt["verse_id"], (pt["n_training_clips"], pt["recall"]),
            textcoords="offset points", xytext=(5, 4), fontsize=9,
        )
    ax.set_xticks(sorted(set(xs)))
    ax.set_ylim(-0.02, 1.1)
    ax.set_xlabel("training clips per verse (n_training_clips)")
    ax.set_ylabel("held-out recall (test split)")
    ax.set_title(
        "GVR accuracy vs training examples per verse (NFR-20)\n"
        "held-out test split only (FR-23)"
    )
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m samskrita_dhvani.evaluate",
        description="Held-out GVR evaluation (FR-23/NFR-20): test-split "
                    "accuracy, confusion matrix, per-verse recall, and "
                    "the accuracy-vs-training-examples curve.",
    )
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY,
                        help=f"registry JSON (default: {DEFAULT_REGISTRY})")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL,
                        help=f"trained model envelope "
                             f"(default: {DEFAULT_MODEL})")
    parser.add_argument("--json", type=Path, default=None,
                        help="write the full report as schema-v1 JSON "
                             "(kind gvr_eval_report)")
    parser.add_argument("--curve-png", type=Path, default=None,
                        help="render the NFR-20 curve as a PNG "
                             "(matplotlib)")
    args = parser.parse_args(argv)

    # ---- honest-absence gates (loud, named, rc=2; nothing fabricated)
    if not args.registry.is_file():
        print(f"error: registry not found: {args.registry} (run "
              "python -m samskrita_dhvani.build_registry first — FR-23: "
              "no registry, no number)", file=sys.stderr)
        return 2
    if not args.model.is_file():
        print(f"error: trained model not found: {args.model} (train per "
              "plan §5 step 4 — FR-23: no model, no number)",
              file=sys.stderr)
        return 2

    try:
        registry = GvrRegistry.from_json(args.registry)
    except Exception as exc:  # noqa: BLE001 — the load gates ARE the point
        print(f"error: registry failed its load-time gates "
              f"({args.registry}): {exc}", file=sys.stderr)
        return 2
    try:
        recognizer = GvrRecognizer.load(args.model)
    except Exception as exc:  # noqa: BLE001
        print(f"error: model failed to load ({args.model}): {exc}",
              file=sys.stderr)
        return 2

    try:
        report = evaluate(recognizer, registry)
    except EvalDataError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(_render_report(report))

    if args.json:
        args.json.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"report JSON: {args.json} (schema "
              f"{EVAL_REPORT_SCHEMA_VERSION}, kind {EVAL_REPORT_KIND})")
    if args.curve_png:
        try:
            _write_curve_png(report, args.curve_png)
        except Exception as exc:  # noqa: BLE001 — loud, after the numbers
            print(f"error: curve PNG failed ({args.curve_png}): {exc}",
                  file=sys.stderr)
            return 2
        print(f"curve PNG: {args.curve_png}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
