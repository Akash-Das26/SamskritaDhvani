"""CLI: one command from a finished D4 session to the published
evaluation (Phase 5).

Run: ``python -m samskrita_dhvani.d4_chain --help``.

Chains the four machine steps of the FR-22 plan (§5) for a finished,
promote-staged D4 booth session — and deliberately delegates each
step to the tool that already owns it:

1. **promote (consumed, not performed):** the operator stages the
   promotion in the booth (label ear check, then the promote panel),
   which writes ``data/_incoming/<session>/PROMOTION.md``. This
   script parses ONLY its ``- [ ]`` mapping lines (a source capture
   name → a ``data/gvr_recordings/<promoted-name>`` target); source
   names resolve against the session dir (where the booth writes the
   mapping), and every target is re-validated through
   ``build_registry.parse_promoted_name`` so a malformed line is a
   loud error, never a blind copy. All source files must exist and
   all targets must be free (or ``--force``) BEFORE the first byte
   moves — the copy phase is all-or-nothing.
2. **build_registry:** delegated verbatim to
   ``build_registry.main()`` — the nine per-row acceptance gates,
   the split policy (``--reciter-splits`` required for ≥2 reciters),
   and the ``from_json`` self-check live there.
3. **train:** ``GvrRecognizer.train`` on the registry's train rows →
   ``data/gvr/model.pkl`` (plan §5 step 4).
4. **evaluate:** delegated to the unit-8 ``evaluate.main()`` with
   ``--json data/gvr/eval_report.json`` (optionally ``--curve-png``)
   so the status page's ``gvr_eval`` section lights up (unit 9).

``--session`` is repeatable: the per-reciter held-out split case is
two sessions from two reciters. A single-reciter chain completes
through training and then ends at evaluate with the FR-23
"NOT speaker-independent" refusal as the run's final word — that is
the honest outcome, printed loudly (rc=2), not hidden.

Nothing is overwritten without ``--force`` (promoted files,
registry, model). The evaluation report is republished by the same
run that (re)trained the model, so it always describes the current
model. PROVENANCE.md registration is reminded at the end — it is
never auto-written.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

from samskrita_dhvani import build_registry as build_registry_mod
from samskrita_dhvani import evaluate as evaluate_mod
from samskrita_dhvani.frontend import load_audio_16k
from samskrita_dhvani.gvr_classifier import MODEL_DEFAULT_PATH, GvrRecognizer
from samskrita_dhvani.record import INCOMING_ROOT
from samskrita_dhvani.registry import GvrRegistry

DEFAULT_ITEMLIST = build_registry_mod.DEFAULT_ITEMLIST

# The booth's mapping lines (record.py promote, D4 branch):
#   - [ ] `gvr_c2v13_recitation_t0.wav`
#         → `data/gvr_recordings/gvr_c2v13_<reciter>_<sid>_t0.wav`  (verse_id 2.13)
PROMOTION_LINE_RE = re.compile(
    r"^-\s\[\s\]\s`(?P<src>[^`]+\.wav)`\s→\s`(?P<dst>[^`]+\.wav)`"
)


def parse_promotion_md(path: Path) -> list[tuple[str, str]]:
    """Extract (source-name, promoted-target-path) pairs from the
    booth's PROMOTION.md. Non-mapping lines are ignored; the targets
    are re-validated downstream, never trusted blindly."""
    pairs: list[tuple[str, str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line.startswith("- [ ]"):
            continue
        m = PROMOTION_LINE_RE.match(line)
        if not m:
            raise ValueError(
                f"{path}: unrecognized promotion line (expected "
                "`- [ ] `src.wav` → `dst.wav` …`): {line!r}"
            )
        pairs.append((m.group("src"), m.group("dst")))
    return pairs


def _validate_targets(
    pairs: list[tuple[str, str]],
) -> tuple[list[tuple[Path, Path]], Path]:
    """Resolve pairs to (absolute source, absolute target) and validate
    every target against the registry-prep grammar. Returns the moves
    and the single recordings dir every target must share (the
    mapping is the protocol — the directory is derived from it, so it
    can never diverge from ``--recordings``-style flags)."""
    checked: list[tuple[Path, Path]] = []
    for src, dst in pairs:
        dst_path = Path(dst)
        if dst_path.is_absolute():
            raise ValueError(
                f"promotion target is not repo-relative: {dst!r}"
            )
        dst_abs = Path.cwd() / dst_path
        parts = dst_path.parts
        if len(parts) != 3 or parts[:2] != ("data", "gvr_recordings"):
            raise ValueError(
                f"promotion target must be data/gvr_recordings/<name>: {dst!r}"
            )
        parsed = build_registry_mod.parse_promoted_name(dst_abs)
        if parsed is None:
            raise ValueError(
                f"promotion target does not match the protocol §3 grammar: "
                f"{dst!r}"
            )
        checked.append((Path(src), dst_abs))
    dirs = {dst.parent for _, dst in checked}
    if len(dirs) != 1:
        raise ValueError(
            "promotion targets span multiple directories: "
            + ", ".join(sorted(str(d) for d in dirs))
        )
    return checked, dirs.pop()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m samskrita_dhvani.d4_chain",
        description="Chain a finished D4 booth session: promote mapping → "
                    "copy → build_registry → train → evaluate --json.",
    )
    parser.add_argument(
        "--session", action="append", required=True,
        help="GVR-REC-… session id under data/_incoming/ (repeatable; "
             "two reciters = two sessions)",
    )
    parser.add_argument("--registry", type=Path,
                        default=build_registry_mod.DEFAULT_OUT)
    parser.add_argument("--model", type=Path,
                        default=MODEL_DEFAULT_PATH)
    parser.add_argument("--itemlist", type=Path, default=DEFAULT_ITEMLIST)
    parser.add_argument("--reciter-splits", default=None,
                        help="e.g. --reciter-splits sage=train,friend=test "
                             "(required with ≥2 reciters)")
    parser.add_argument("--source-id", required=True,
                        help="PROVENANCE.md entry for these recordings")
    parser.add_argument("--acquired-on", required=True,
                        help="acquisition date (YYYY-MM-DD)")
    parser.add_argument("--recitation-tradition", required=True,
                        help="tradition stated per protocol §3.6")
    parser.add_argument("--json-report", type=Path,
                        default=evaluate_mod.DEFAULT_REGISTRY.parent
                        / "gvr" / "eval_report.json",
                        help="where to publish the evaluation report "
                             "(the status page reads this)")
    parser.add_argument("--curve-png", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true",
                        help="print the plan, write nothing")
    parser.add_argument("--force", action="store_true",
                        help="allow overwriting existing targets/artifacts")
    args = parser.parse_args(argv)

    # ---- step 0: read every session's promotion mapping
    pairs: list[tuple[str, str]] = []
    for sid in args.session:
        p = INCOMING_ROOT / sid / "PROMOTION.md"
        if not p.is_file():
            print(
                f"error: {p} not found — stage the promotion in the booth "
                "first (label ear check → promote panel writes PROMOTION.md)",
                file=sys.stderr,
            )
            return 2
        try:
            got = parse_promotion_md(p)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if not got:
            print(f"error: {p} contains no promotion mapping lines",
                  file=sys.stderr)
            return 2
        print(f"session {sid}: {len(got)} mapped take(s)")
        # Source names in PROMOTION.md are relative to the session dir
        # (the booth writes the mapping INTO the session); resolve them
        # there. Targets stay repo-relative (validated below).
        session_dir = p.parent
        pairs.extend(
            (str(session_dir / src), dst) for src, dst in got
        )

    # ---- step 1: validate BEFORE anything moves
    try:
        moves, recordings_dir = _validate_targets(pairs)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    for src, dst in moves:
        if not src.is_file():
            print(f"error: promotion source missing: {src} (the session "
                  "dir must still hold every mapped take)", file=sys.stderr)
            return 2
        if dst.exists() and not args.force:
            print(f"error: target already exists: {dst} (use --force to "
                  "overwrite deliberately)", file=sys.stderr)
            return 2
    for artifact in (args.registry, args.model):
        if artifact.exists() and not args.force:
            print(f"error: {artifact} already exists (use --force to "
                  "overwrite deliberately)", file=sys.stderr)
            return 2
    print(f"plan: {len(moves)} take(s) → {recordings_dir}")

    if args.dry_run:
        for src, dst in moves:
            print(f"  would copy {src} → {dst}")
        print("dry-run: nothing written (registry/model/report untouched)")
        return 0

    # ---- step 1b: the copy phase (all-or-nothing per run)
    recordings_dir.mkdir(parents=True, exist_ok=True)
    for src, dst in moves:
        shutil.copy2(src, dst)
    print(f"copied {len(moves)} take(s) into {recordings_dir}")
    print(f"reminder: register source-id '{args.source_id}' in "
          "files/PROVENANCE.md (DataIntegrity Rule 2) — the chain never "
          "writes provenance entries itself", file=sys.stderr)

    # ---- step 2: build_registry (delegated — gates + split policy +
    #      from_json self-check live there)
    cmd = [
        "--recordings", str(recordings_dir),
        "--out", str(args.registry),
        "--itemlist", str(args.itemlist),
        "--source-id", args.source_id,
        "--acquired-on", args.acquired_on,
        "--recitation-tradition", args.recitation_tradition,
    ]
    if args.reciter_splits is not None:
        cmd += ["--reciter-splits", args.reciter_splits]
    if args.force:
        cmd += ["--force"]
    rc = build_registry_mod.main(cmd)
    if rc != 0:
        print(f"error: build_registry failed (rc={rc}) — nothing trained",
              file=sys.stderr)
        return rc

    # ---- step 3: train (plan §5 step 4)
    registry = GvrRegistry.from_json(args.registry)
    print(f"training {len(registry)}-row registry "
          f"(policy {registry.split_policy}) …")
    recognizer = GvrRecognizer.train(registry, load_audio_16k)
    recognizer.save(args.model)
    print(f"model saved: {args.model} "
          f"({len(recognizer)} verse(s), per-verse training clips: "
          f"{ {v: recognizer.verses[v].n_training_clips for v in recognizer.verse_ids} })")

    # ---- step 4: evaluate (delegated; publishes the report the
    #      status page mirrors)
    ev = [
        "--registry", str(args.registry),
        "--model", str(args.model),
        "--json", str(args.json_report),
    ]
    if args.curve_png is not None:
        ev += ["--curve-png", str(args.curve_png)]

    print(f"evaluating: python -m samskrita_dhvani.evaluate "
          f"{' '.join(ev)} (Ground Rule 1: this exact command is the "
          "one to record)")
    return evaluate_mod.main(ev)


if __name__ == "__main__":
    sys.exit(main())
