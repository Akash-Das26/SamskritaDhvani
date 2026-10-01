"""CLI: rebuild the D2 per-word D₀ calibration from audio on disk
(Run: ``python -m samskrita_dhvani.calibrate --help``).

Inputs, by convention:

- ``--references DIR``  canonical reference clips, one per word,
  named ``<word_id>.wav`` (``.flac``/``.mp3`` also accepted). These
  are the ear-verified clips cut after the Hall/Loyola check passes.
- ``--recitations DIR`` known-correct recitations, grouped per word
  either as ``<word_id>__<anything>.<ext>`` siblings or as
  ``<word_id>/`` subdirectories. These are the recordings the D₂
  scale is measured against (design D5 / DataIntegrity Rule 2).

Behaviour worth knowing:

- Provenance is mandatory (``--source-id``, ``--acquired-on``): an
  anonymous calibration file is invalid by Rule 2.
- A word missing either side (no canonical clip, or no known-correct
  recitations) is skipped with a printed notice — never silently
  dropped, never given a guessed scale.
- Refuses to overwrite an existing calibration file without
  ``--force`` (regeneration must be deliberate; Ground Rule 4).
- Prints the measured per-word D₀ values so the numbers can be
  recorded in Review.md as-run.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from samskrita_dhvani.frontend import load_audio_16k
from samskrita_dhvani.spd_scorer import CalibrationBuilder

AUDIO_EXTS = (".wav", ".flac", ".mp3")
DEFAULT_OUT = Path("data") / "spd" / "calibration.json"


def _audio_files(directory: Path) -> list[Path]:
    return sorted(p for p in directory.iterdir()
                  if p.is_file() and p.suffix.lower() in AUDIO_EXTS)


def find_canonical(ref_dir: Path) -> dict[str, Path]:
    """word_id → canonical clip, from ``<word_id>.<ext>`` files."""
    found: dict[str, Path] = {}
    for p in _audio_files(ref_dir):
        word_id = p.stem
        if word_id in found:
            print(f"  ! duplicate canonical clip for '{word_id}': "
                  f"{p.name} shadows {found[word_id].name} — keeping the first",
                  file=sys.stderr)
            continue
        found[word_id] = p
    return found


def find_recitations(rec_dir: Path) -> dict[str, list[Path]]:
    """word_id → known-correct recitations, from ``<word_id>__*.ext``
    siblings and/or ``<word_id>/`` subdirectories."""
    found: dict[str, list[Path]] = {}
    for p in _audio_files(rec_dir):
        if "__" in p.stem:
            word_id = p.stem.split("__", 1)[0]
            found.setdefault(word_id, []).append(p)
    for sub in sorted(rec_dir.iterdir()):
        if sub.is_dir():
            clips = _audio_files(sub)
            if clips:
                found.setdefault(sub.name, []).extend(clips)
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m samskrita_dhvani.calibrate",
        description="Rebuild the D2 per-word D0 calibration "
                    "(calibration.json) from canonical reference clips "
                    "and known-correct recitations.",
    )
    parser.add_argument("--references", type=Path, required=True,
                        help="dir of canonical clips named <word_id>.wav")
    parser.add_argument("--recitations", type=Path, required=True,
                        help="dir of known-correct recitations, grouped as "
                             "<word_id>__*.wav siblings or <word_id>/ subdirs")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help=f"output path (default: {DEFAULT_OUT})")
    parser.add_argument("--source-id", required=True,
                        help="PROVENANCE.md source entry for the input audio")
    parser.add_argument("--acquired-on", required=True,
                        help="acquisition date of the input audio (YYYY-MM-DD)")
    parser.add_argument("--force", action="store_true",
                        help="overwrite an existing calibration file")
    args = parser.parse_args(argv)

    if not args.references.is_dir():
        print(f"error: --references dir not found: {args.references}",
              file=sys.stderr)
        return 2
    if not args.recitations.is_dir():
        print(f"error: --recitations dir not found: {args.recitations}",
              file=sys.stderr)
        return 2
    if args.out.exists() and not args.force:
        print(f"error: {args.out} already exists (use --force to regenerate "
              "deliberately)", file=sys.stderr)
        return 2

    canonical = find_canonical(args.references)
    recitations = find_recitations(args.recitations)
    word_ids = sorted(set(canonical) & set(recitations))
    for w in sorted((set(canonical) | set(recitations))
                    - (set(canonical) & set(recitations))):
        side = "canonical clip" if w in canonical else "known-correct recitations"
        print(f"  ! skipping '{w}': no {side}", file=sys.stderr)

    if not word_ids:
        print("error: no word has both a canonical clip and known-correct "
              "recitations — nothing to calibrate", file=sys.stderr)
        return 2

    builder = CalibrationBuilder()
    n_failed_words = 0
    for word_id in word_ids:
        try:
            builder.set_canonical(word_id,
                                  load_audio_16k(str(canonical[word_id])))
        except Exception as exc:  # noqa: BLE001 — skip loudly, keep going
            print(f"  ! skipping '{word_id}': canonical clip failed to "
                  f"load/decode: {exc}", file=sys.stderr)
            n_failed_words += 1
            continue
        loaded = 0
        for clip in recitations[word_id]:
            try:
                builder.add_reference(word_id, load_audio_16k(str(clip)))
                loaded += 1
            except Exception as exc:  # noqa: BLE001 — one bad take must not
                # kill the word; the surviving takes still calibrate it.
                print(f"  ! skipping recitation '{clip.name}' for "
                      f"'{word_id}': {exc}", file=sys.stderr)
        if loaded == 0:
            print(f"  ! skipping '{word_id}': no known-correct recitation "
                  "loaded", file=sys.stderr)
            builder.drop(word_id)
            n_failed_words += 1

    data = builder.build(
        provenance={"source_id": args.source_id, "acquired_on": args.acquired_on},
        out_path=args.out,
    )

    print(f"wrote {args.out} "
          f"(schema_version {data['schema_version']}, "
          f"provenance {args.source_id} / {args.acquired_on})")
    print(f"{'word_id':<16} {'D0':>10} {'D0_formant':>11} "
          f"{'D0_duration':>12} {'refs':>5}")
    for word_id, entry in data["words"].items():
        print(f"{word_id:<16} {entry['d0']:>10.4f} "
              f"{entry['d0_formant']:>11.4f} "
              f"{entry['d0_duration']:>12.4f} "
              f"{entry['n_references']:>5}")
    if n_failed_words:
        print(f"warning: {n_failed_words} word(s) skipped on audio errors",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
