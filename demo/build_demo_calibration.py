"""Build the demo's provisional D₂ calibration (demo/data/calibration.json).

This is the real calibration path — ``CalibrationBuilder`` from
``samskrita_dhvani.spd_scorer``, the same class
``python -m samskrita_dhvani.calibrate`` drives — pointed at
``demo/data/`` instead of ``data/spd/``. Nothing here changes the D2
formula: D₀ is still the mean DTW distance of known-correct
recitations to the canonical clip. The only difference is the corpus:
synthetic Edge-TTS clips copied from Dhvani-Yantra-main, which are
**not ear-verified**. The result is a provisional scale for the demo
and must never be read as a measured calibration.

Usage::

    python -m demo.build_demo_calibration [--force]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from samskrita_dhvani.calibrate import find_canonical, find_recitations
from samskrita_dhvani.frontend import load_audio_16k
from samskrita_dhvani.spd_scorer import CalibrationBuilder

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEMO_DATA = PROJECT_ROOT / "demo" / "data"
REFERENCE_DIR = DEMO_DATA / "reference_words"
RECITATION_DIR = DEMO_DATA / "recitations"
OUT_PATH = DEMO_DATA / "calibration.json"

PROVENANCE = {
    "source_id": "DEMO-DHVANI-YANTRA-TTS",
    "acquired_on": "2026-10-29",
    "note": (
        "DEMO — synthetic Edge-TTS references, not ear-verified; "
        "provisional calibration, not a result."
    ),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m demo.build_demo_calibration",
        description="Build the provisional demo D2 calibration from "
                    "demo/data/ (never data/spd/).",
    )
    parser.add_argument("--force", action="store_true",
                        help="overwrite an existing demo calibration")
    args = parser.parse_args(argv)

    if not REFERENCE_DIR.is_dir() or not RECITATION_DIR.is_dir():
        print("error: demo data missing — run: python -m demo.prepare_demo_data",
              file=sys.stderr)
        return 2
    if OUT_PATH.exists() and not args.force:
        print(f"error: {OUT_PATH} already exists (use --force to rebuild)",
              file=sys.stderr)
        return 2

    canonical = find_canonical(REFERENCE_DIR)
    recitations = find_recitations(RECITATION_DIR)
    word_ids = sorted(set(canonical) & set(recitations))
    if not word_ids:
        print("error: no demo word has both a reference clip and recitations",
              file=sys.stderr)
        return 2
    for word_id in sorted((set(canonical) | set(recitations)) - set(word_ids)):
        print(f"  ! skipping '{word_id}': missing one side", file=sys.stderr)

    builder = CalibrationBuilder()
    for word_id in word_ids:
        builder.set_canonical(word_id, load_audio_16k(str(canonical[word_id])))
        for clip in recitations[word_id]:
            builder.add_reference(word_id, load_audio_16k(str(clip)))

    data = builder.build(provenance=PROVENANCE, out_path=OUT_PATH)

    print(f"wrote {OUT_PATH.relative_to(PROJECT_ROOT)} "
          f"(schema_version {data['schema_version']}, "
          f"provenance {PROVENANCE['source_id']} / {PROVENANCE['acquired_on']})")
    print("DEMO ONLY — synthetic TTS scale, not ear-verified, not a result.")
    print(f"{'word_id':<10} {'D0':>10} {'D0_formant':>12} {'D0_duration':>12} "
          f"{'refs':>5}")
    for word_id, entry in data["words"].items():
        print(f"{word_id:<10} {entry['d0']:>10.4f} {entry['d0_formant']:>12.4f} "
              f"{entry['d0_duration']:>12.4f} {entry['n_references']:>5}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
