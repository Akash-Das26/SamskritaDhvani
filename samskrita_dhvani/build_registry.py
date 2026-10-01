"""CLI: build ``data/gvr_registry.json`` from a promoted D4 recording
batch (Run: ``python -m samskrita_dhvani.build_registry --help``).

Input convention — exactly what the recording booth's PROMOTION.md
emits (RecordingProtocol §3 registry-prep names)::

    data/gvr_recordings/gvr_c<ch>v<vv>_<reciter>_<session-id>_t<take>.wav

    e.g. gvr_c2v01_asha_rao_S Glück-GVR-REC-20261001-ab12cd_t1.wav
         (reciter slugs and session ids may contain underscores —
         the parser splits from the RIGHT: t<take> ← session ← reciter
         ← c<ch>v<vv>)

What it does, per file:

- parses the protocol name (loud skip on a grammar mismatch);
- resolves the verse against ``data/gvr/ch2_itemlist.json`` (the
  checked GVR-TXT-01 text source) for the canonical verse id and
  mūla ``devanagari_text`` — the tool never types verse text;
- decodes with the real D1 loader and applies the DataIntegrity §1.1
  gates (duration ≥ 0.2 s, VAD speech fraction > 10%);
- assigns a split under the registry's actual leak policy
  (``assert_no_split_leak``): ≥2 reciters → per-reciter with an
  explicit ``--reciter-splits R=train,R=test`` assignment (unassigned
  reciters are an error, so no row guesses its split); exactly one
  reciter → all rows train with ``split_policy: per-recording``
  recorded in the file (NFR-04) — reporting must then state that
  accuracy is not speaker-independent;
- attaches the mandatory provenance (``--source-id`` /
  ``--acquired-on``) and ``--recitation-tradition`` (protocol §3.6).

A row failing any gate is skipped with a printed reason and counted —
never fixed silently (DataIntegrity Rule 1). If zero rows survive,
nothing is written and the exit code is 2. Before reporting success
the tool loads its own output through ``GvrRegistry.from_json`` (the
same load-time gates training will apply) and prints the split
summary + verse coverage as-run.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from samskrita_dhvani.frontend import load_audio_16k, vad_speech_fraction
from samskrita_dhvani.registry import GvrRegistry, VerseEntry

AUDIO_EXTS = (".wav", ".flac", ".mp3")
DEFAULT_OUT = Path("data") / "gvr_registry.json"
DEFAULT_ITEMLIST = Path("data") / "gvr" / "ch2_itemlist.json"
VAD_MIN_SPEECH_FRACTION = 0.10  # DataIntegrity §1.1
MIN_DURATION_S = 0.2

# Registry-prep grammar (booth PROMOTION.md output):
#   gvr_c<ch>v<vv>_<reciter>_<session-id>_t<take>.<ext>
# Parsed from the RIGHT so reciter slugs / session ids that contain
# underscores stay intact.
STEM_RE = re.compile(
    r"^gvr_c(?P<ch>\d{1,3})v(?P<vv>\d{1,3})_"
    r"(?P<reciter>[A-Za-z0-9_]+?)_"
    r"(?P<sid>(?:SPD|GVR)-REC-\d{8}-[0-9a-f]{6})_"
    r"t(?P<take>\d+)$"
)


def parse_promoted_name(path: Path) -> dict | None:
    """Parse one promoted filename; None if it doesn't match the grammar."""
    if path.suffix.lower() not in AUDIO_EXTS:
        return None
    m = STEM_RE.fullmatch(path.stem)
    if not m:
        return None
    return {
        "path": path,
        "chapter": int(m.group("ch")),
        "verse": int(m.group("vv")),
        "reciter": m.group("reciter"),
        "session_id": m.group("sid"),
        "take": int(m.group("take")),
    }


def _audio_files(directory: Path) -> list[Path]:
    return sorted(
        p for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() in AUDIO_EXTS
    )


def _load_itemlist(path: Path) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("kind") != "gvr_itemlist" or data.get("schema_version") != 1:
        raise SystemExit(
            f"error: {path} is not a schema-v1 gvr_itemlist (run "
            "tools/build_gvr_itemlist.py first)"
        )
    return {it["verse_id"]: it for it in data["items"]}


def _assign_splits(
    reciters: list[str], spec: str | None
) -> dict[str, str] | None:
    """Parse ``--reciter-splits a=train,b=test``; None if not given."""
    if spec is None:
        return None
    out: dict[str, str] = {}
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part or part.rsplit("=", 1)[1] not in (
            "train", "validation", "test"
        ):
            return None
        name, split = part.rsplit("=", 1)
        if not name.strip():
            return None
        out[name.strip()] = split
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m samskrita_dhvani.build_registry",
        description="Build the FR-22 GVR verse registry from a promoted "
                    "recording batch (protocol §3 names).",
    )
    parser.add_argument("--recordings", type=Path, required=True,
                        help="dir of promoted clips: "
                             "gvr_c<ch>v<vv>_<reciter>_<sid>_t<take>.wav")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--itemlist", type=Path, default=DEFAULT_ITEMLIST,
                        help="chapter item list for verse ids + mūla text "
                             "(GVR-TXT-01 source)")
    parser.add_argument("--source-id", required=True,
                        help="PROVENANCE.md entry for these recordings")
    parser.add_argument("--acquired-on", required=True,
                        help="acquisition date (YYYY-MM-DD)")
    parser.add_argument("--recitation-tradition", required=True,
                        help="tradition stated per protocol §3.6")
    parser.add_argument("--reciter-splits", default=None,
                        help="per-reciter split assignment, e.g. "
                             "asha_rao=train,ravi=test (required when ≥2 "
                             "reciters are present)")
    parser.add_argument("--force", action="store_true",
                        help="overwrite an existing registry file")
    args = parser.parse_args(argv)

    if not args.recordings.is_dir():
        print(f"error: --recordings dir not found: {args.recordings}",
              file=sys.stderr)
        return 2
    if args.out.exists() and not args.force:
        print(f"error: {args.out} already exists (use --force to "
              "regenerate deliberately)", file=sys.stderr)
        return 2
    try:
        itemlist = _load_itemlist(args.itemlist)
    except FileNotFoundError:
        print(f"error: item list not found: {args.itemlist} (run "
              "tools/build_gvr_itemlist.py first)", file=sys.stderr)
        return 2

    rows = []
    n_skipped = 0
    for p in _audio_files(args.recordings):
        parsed = parse_promoted_name(p)
        if parsed is None:
            print(f"  ! skipping '{p.name}': does not match the "
                  "gvr_c<ch>v<vv>_<reciter>_<sid>_t<take> grammar",
                  file=sys.stderr)
            n_skipped += 1
            continue

        verse_id = f"{parsed['chapter']}.{parsed['verse']:02d}"
        item = itemlist.get(verse_id)
        if item is None:
            print(f"  ! skipping '{p.name}': verse {verse_id} is not in "
                  f"the item list ({args.itemlist})", file=sys.stderr)
            n_skipped += 1
            continue

        try:
            y = load_audio_16k(str(p))
        except Exception as exc:  # noqa: BLE001 — loud per-file skip
            print(f"  ! skipping '{p.name}': failed to decode: {exc}",
                  file=sys.stderr)
            n_skipped += 1
            continue
        duration = len(y) / 16000.0
        if duration < MIN_DURATION_S:
            print(f"  ! skipping '{p.name}': too short ({duration:.2f}s "
                  f"< {MIN_DURATION_S:.2f}s)", file=sys.stderr)
            n_skipped += 1
            continue
        frac = vad_speech_fraction(y)
        if frac <= VAD_MIN_SPEECH_FRACTION:
            print(f"  ! skipping '{p.name}': near-silence (VAD speech "
                  f"fraction {frac:.3f} ≤ {VAD_MIN_SPEECH_FRACTION:.2f}, "
                  "DataIntegrity §1.1)", file=sys.stderr)
            n_skipped += 1
            continue

        rows.append({**parsed, "verse_id": verse_id, "duration_s": duration,
                     "vad": frac})

    if not rows:
        print("error: no eligible clips survived the acceptance gates — "
              "nothing to register", file=sys.stderr)
        return 2

    reciters = sorted({r["reciter"] for r in rows})
    assignment = _assign_splits(reciters, args.reciter_splits)
    if assignment is not None:
        # An explicit assignment always wins — including a deliberate
        # single-reciter test/validation assignment (the operator owns
        # the consequence: those verses cannot be learned from).
        missing = [r for r in reciters if r not in assignment]
        if missing:
            print(
                "error: --reciter-splits does not cover: "
                + ", ".join(missing)
                + " (unassigned rows would guess their split)",
                file=sys.stderr,
            )
            return 2
        policy = "per-reciter"
        splits = {r: assignment[r] for r in reciters}
    elif len(reciters) >= 2:
        print(
            "error: with ≥2 reciters the per-reciter policy needs an "
            "explicit, complete --reciter-splits assignment "
            "(unassigned would guess splits): "
            + ", ".join(reciters),
            file=sys.stderr,
        )
        return 2
    else:
        # Single reciter, no explicit assignment: reciter-disjoint
        # splits are impossible. All rows train, policy recorded
        # honestly in the file (NFR-04); reporting must carry the
        # FR-23 sentence.
        policy = "per-recording"
        splits = {reciters[0]: "train"}

    provenance = {
        "source_id": args.source_id,
        "acquired_on": args.acquired_on,
    }
    entries = []
    for r in rows:
        item = itemlist[r["verse_id"]]
        entries.append(
            VerseEntry(
                verse_id=r["verse_id"],
                audio_file=str(r["path"]).replace("\\", "/"),
                reciter=r["reciter"],
                split=splits[r["reciter"]],
                devanagari_text=item["devanagari"],
                provenance=dict(provenance),
            )
        )

    registry = GvrRegistry(entries, split_policy=policy)

    # Self-check: the file must pass the same load-time gates that
    # training will apply (leak + provenance + schema).
    import tempfile

    tmp = tempfile.NamedTemporaryFile(
        suffix=".json", delete=False, mode="w", encoding="utf-8"
    )
    registry.to_json(tmp.name)
    tmp.close()
    try:
        GvrRegistry.from_json(tmp.name)
    except Exception as exc:  # noqa: BLE001 — never write a bad registry
        Path(tmp.name).unlink(missing_ok=True)
        print(f"error: generated registry fails its load-time gates: {exc}",
              file=sys.stderr)
        return 2
    Path(tmp.name).unlink(missing_ok=True)

    registry.to_json(args.out)

    # -------- as-run summary
    by_split: dict[str, set] = defaultdict(set)
    for e in registry.entries:
        by_split[e.split].add(e.reciter)
    verses_by_split: dict[str, set] = defaultdict(set)
    for e in registry.entries:
        verses_by_split[e.split].add(e.verse_id)

    print(f"wrote {args.out} (schema_version 1, split_policy {policy}, "
          f"{len(registry.entries)} rows, {n_skipped} skipped)")
    print(f"provenance: {args.source_id} / {args.acquired_on} · "
          f"tradition: {args.recitation_tradition}")
    for split in ("train", "validation", "test"):
        if by_split.get(split):
            print(f"  {split}: reciters {sorted(by_split[split])} · "
                  f"{len(verses_by_split[split])} verse(s)")
    train_verses = verses_by_split.get("train", set())
    all_verses = {e.verse_id for e in registry.entries}
    outside = sorted(all_verses - train_verses)
    if outside:
        print(f"warning: {len(outside)} verse(s) have NO train rows and "
              "cannot be learned by GvrRecognizer.train: "
              + ", ".join(outside), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
