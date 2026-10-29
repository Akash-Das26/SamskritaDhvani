"""Copy the demo's three reference words out of Dhvani-Yantra-main.

Demo-only. The source tree is treated as read-only: this script only
reads ``Dhvani-Yantra-main/data/audio`` and writes under ``demo/data/``.
It never touches ``data/`` or ``corpus/``.

Every candidate is decoded with the project's own loader
(``samskrita_dhvani.frontend.load_audio_16k``) and gated on the
DataIntegrity §1.1 near-silence rule (WebRTC VAD speech fraction must
clear 10%). A file that fails either check is listed and skipped, never
repaired.

Usage::

    python -m demo.prepare_demo_data

The copied audio is gitignored (``demo/.gitignore``); the provenance
record for it is ``demo/DEMO_DATA.md``.
"""

from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

from samskrita_dhvani.frontend import load_audio_16k, vad_speech_fraction

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_AUDIO = PROJECT_ROOT / "Dhvani-Yantra-main" / "data" / "audio"
DEMO_DATA = PROJECT_ROOT / "demo" / "data"
REFERENCE_DIR = DEMO_DATA / "reference_words"
RECITATION_DIR = DEMO_DATA / "recitations"

# Word list IDs from the FR-12 seed list, mapped to the Dhvani-Yantra
# file stems. Every file below is synthetic Edge-TTS output.
WORDS: dict[str, dict] = {
    "kRSNa": {
        "reference": "ref_krishna.wav",
        "recitations": [
            "ref_krishna_alt.wav",
            "stud_krishna.wav",
            "stud_krishna_0_krisna.wav",
            "stud_krishna_1_kishna.wav",
        ],
    },
    "yoga": {
        "reference": "ref_yoga.wav",
        "recitations": [
            "ref_yoga_alt.wav",
            "stud_yoga.wav",
            "stud_yoga_0_yog.wav",
            "stud_yoga_1_yuga.wav",
        ],
    },
    "zAnti": {
        "reference": "ref_shanti.wav",
        "recitations": [
            "ref_shanti_alt.wav",
            "stud_shanti.wav",
            "stud_shanti_0_shant.wav",
            "stud_shanti_1_shanti.wav",
        ],
    },
    # Added: dharma and om complete the 5-word P1 evaluation set.
    # Both have validated reference + student clips in Dhvani-Yantra-main.
    "dharma": {
        "reference": "ref_dharma.wav",
        "recitations": [
            "ref_dharma_alt.wav",
            "stud_dharma.wav",
            "stud_dharma_0_dhram.wav",
            "stud_dharma_1_dharm.wav",
        ],
    },
    "om": {
        "reference": "ref_om.wav",
        "recitations": [
            "ref_om_alt.wav",
            "stud_om.wav",
            "stud_om_0_aum.wav",
            "stud_om_1_om.wav",
        ],
    },
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    if not SOURCE_AUDIO.is_dir():
        print(f"error: source audio dir not found: {SOURCE_AUDIO}", file=sys.stderr)
        return 2

    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    RECITATION_DIR.mkdir(parents=True, exist_ok=True)

    rows: list[tuple[str, str, int, str, float]] = []
    skipped: list[tuple[str, str]] = []

    for word_id, spec in WORDS.items():
        plan = [(SOURCE_AUDIO / spec["reference"],
                 REFERENCE_DIR / f"{word_id}.wav")]
        for rec in spec["recitations"]:
            plan.append((SOURCE_AUDIO / rec,
                         RECITATION_DIR / f"{word_id}__{Path(rec).stem}.wav"))
        for src, dst in plan:
            if not src.is_file():
                skipped.append((src.name, "source file missing"))
                continue
            try:
                y = load_audio_16k(str(src))
                frac = vad_speech_fraction(y)
            except Exception as exc:  # noqa: BLE001 — skip loudly, never repair
                skipped.append((src.name, f"loader failed: {exc}"))
                continue
            if frac <= 0.10:
                skipped.append(
                    (src.name, f"VAD speech fraction {frac:.2f} <= 0.10"))
                continue
            shutil.copyfile(src, dst)
            rows.append((str(src.relative_to(PROJECT_ROOT)),
                         str(dst.relative_to(PROJECT_ROOT)),
                         dst.stat().st_size, sha256(dst), frac))

    print(f"copied {len(rows)} file(s) into {DEMO_DATA}")
    print(f"{'source':<56} {'dest':<40} {'bytes':>7} {'vad':>5}  sha256")
    for src_rel, dest_rel, size, digest, frac in rows:
        print(f"{src_rel:<56} {dest_rel:<40} {size:>7} {frac:>5.2f}  {digest}")

    if skipped:
        print("skipped:", file=sys.stderr)
        for name, reason in skipped:
            print(f"  ! {name}: {reason}", file=sys.stderr)
        return 1 if not rows else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
