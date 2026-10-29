"""Record the demo owner's own takes with ``arecord`` (demo-only, no new deps).

This is the recorder half of the "own recordings" demo corpus. It never
edits audio: every accepted take is copied byte-for-byte from the file
``arecord`` wrote. A take that is clipped, silent, too quiet, or too
short is deleted and re-recorded — a bad take is never kept.

Layout (same names ``prepare_demo_data.py`` uses, so the calibration
builder and the demo server need no changes)::

    demo/data_own/reference_words/<word_id>.wav
    demo/data_own/recitations/<word_id>__own_t0.wav … t3
    demo/data_own/variants/<word_id>__var-<label>.wav

Only ``reference_words/`` and ``recitations/`` are read by
``demo.build_demo_calibration``; variants are demonstration material and
must never enter a calibration.

Every take is measured with the project's own loader
(``load_audio_16k``) and the DataIntegrity §1.1 VAD gate. Nothing here
touches ``data/`` or ``corpus/``; the root refuses to point at them.

Usage::

    python -m demo.record_own --word kRSNa
    python -m demo.record_own --word yoga --no-variants
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

import numpy as np

from samskrita_dhvani.frontend import (
    load_audio_16k,
    vad_speech_fraction,
    vad_trim,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROOT = PROJECT_ROOT / "demo" / "data_own"

RATE = 16_000
CHANNELS = 1
SAMPLES = 40_000            # 2.5 s at 16 kHz
DEVICE_NOTE = "Realtek ALC245 internal mic (card 1, HD-Audio Generic)"

# Gate thresholds. Clipping uses the RecordingProtocol §4 criterion
# (peak >= 0.99 or >= 0.1 % of samples at |x| >= 0.999); the quiet and
# length floors are the recorder's own, stated here so they are visible.
MIN_DURATION_S = 0.30
MIN_SPEECH_S = 0.15
MIN_PEAK = 0.02
MIN_RMS = 0.004
MAX_PEAK = 0.90
MAX_CLIPPED_FRAC = 0.001
MIN_SPEECH_FRACTION = 0.10

# word_id -> devanagari/IAST plus the two demonstration variants.
# ``error_type`` uses the RecordingProtocol §3 filename tags: var-sub
# (a sound is substituted) and var-del (a sound is deleted).
WORDS: dict[str, dict] = {
    "kRSNa": {
        "devanagari": "कृष्ण",
        "iast": "kṛṣṇa",
        "variants": [
            ("krisna", "var-sub", "say “krisna” — the vowel ṛ becomes ri"),
            ("kishna", "var-del", "say “kishna” — the r is dropped"),
        ],
    },
    "yoga": {
        "devanagari": "योग",
        "iast": "yoga",
        "variants": [
            ("yog", "var-del", "say “yog” — the final a is dropped"),
            ("yogo", "var-sub", "say “yogo” — the final a becomes o"),
        ],
    },
    "zAnti": {
        "devanagari": "शान्ति",
        "iast": "śānti",
        "variants": [
            ("santi", "var-sub", "say “santi” — ś becomes a dental s"),
            ("shaati", "var-del", "say “shaati” — the n is dropped"),
        ],
    },
}


# ----------------------------------------------------------------- helpers

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def capture_level() -> str:
    """The Mixer 'Capture' setting in force, for the provenance record."""
    try:
        r = subprocess.run(
            ["amixer", "-c", "1", "sget", "Capture"],
            capture_output=True, text=True, timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "unknown (amixer unavailable)"
    for line in r.stdout.splitlines():
        if "Front Left: Capture" in line:
            parts = line.split()
            try:
                raw = parts[3]
                return (f"{raw}/63 ({parts[4].strip('[]')}, "
                        f"{parts[5].strip('[]')}, switch {parts[6].strip('[]')})")
            except IndexError:
                return line.split(":", 1)[1].strip()
    return "unknown"


def measure(path: Path) -> dict:
    with wave.open(str(path), "rb") as w:
        frames = w.getnframes()
        rate = w.getframerate()
        channels = w.getnchannels()
    y = load_audio_16k(str(path))
    peak = float(np.max(np.abs(y))) if y.size else 0.0
    rms = float(np.sqrt(np.mean(np.square(y, dtype=np.float64)))) if y.size else 0.0
    clipped = float(np.mean(np.abs(y) >= 0.999)) if y.size else 0.0
    speech_frac = vad_speech_fraction(y)
    speech_s = len(vad_trim(y)) / rate
    return {
        "raw_duration_s": round(frames / rate, 3),
        "rate": rate,
        "channels": channels,
        "duration_s": round(len(y) / RATE, 3),
        "peak": round(peak, 4),
        "rms": round(rms, 4),
        "clipped_frac": round(clipped, 5),
        "speech_fraction": round(speech_frac, 3),
        "speech_duration_s": round(speech_s, 3),
    }


def problems(m: dict) -> list[str]:
    errs: list[str] = []
    if m["peak"] > MAX_PEAK or m["clipped_frac"] >= MAX_CLIPPED_FRAC:
        errs.append(
            f"clipped — peak {m['peak']:.3f}, {m['clipped_frac'] * 100:.2f} % of "
            "samples at full scale. Move back from the mic; if it persists, "
            "lower Capture: amixer -c 1 sset 'Capture' 40%"
        )
    if m["peak"] < MIN_PEAK or m["rms"] < MIN_RMS:
        errs.append(
            f"too quiet — peak {m['peak']:.3f}, rms {m['rms']:.4f}. Speak up, "
            "or raise Capture one step: amixer -c 1 sset 'Capture' 60%"
        )
    if m["raw_duration_s"] < MIN_DURATION_S or m["speech_duration_s"] < MIN_SPEECH_S:
        errs.append(
            f"too short — {m['raw_duration_s']:.2f} s recorded, "
            f"{m['speech_duration_s']:.2f} s of speech. Say the whole word."
        )
    if m["speech_fraction"] <= MIN_SPEECH_FRACTION:
        errs.append(
            f"no speech detected — VAD {m['speech_fraction']:.0%} "
            f"(needs > {MIN_SPEECH_FRACTION:.0%})."
        )
    return errs


def record(tmpdir: Path, label: str) -> Path:
    """One 2.5 s take through arecord; returns the raw WAV path."""
    safe = label.replace(" ", "_").replace("/", "-")
    out = tmpdir / f"{safe}.wav"
    cmd = [
        "arecord", "-q", "-t", "wav", "-f", "S16_LE", "-r", str(RATE),
        "-c", str(CHANNELS), "-s", str(SAMPLES), str(out),
    ]
    print(f"  Get ready for {label} …", flush=True)
    for n in (3, 2, 1):
        print(f"  {n}…", flush=True)
        time.sleep(1)
    print("  ● RECORDING — speak now", flush=True)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=12)
    except FileNotFoundError:
        print("error: arecord not found", file=sys.stderr)
        raise SystemExit(2)
    except subprocess.TimeoutExpired:
        print("error: arecord did not stop within 12 s", file=sys.stderr)
        raise SystemExit(2)
    if r.returncode != 0 or not out.is_file():
        print(f"error: arecord failed (rc={r.returncode}): "
              f"{r.stderr.strip()[:300]}", file=sys.stderr)
        raise SystemExit(2)
    return out


def take(tmpdir: Path, label: str, prompt: str) -> tuple[Path, dict]:
    """Record until one take passes every gate and the owner accepts it."""
    while True:
        print(f"\n{label}")
        print(f"  {prompt}")
        input("  Press Enter to record this take: ")
        path = record(tmpdir, label)
        m = measure(path)
        print(f"  measured: {m['duration_s']:.2f} s · peak {m['peak']:.3f} · "
              f"rms {m['rms']:.4f} · clipped {m['clipped_frac'] * 100:.2f} % · "
              f"VAD speech {m['speech_fraction']:.0%} "
              f"({m['speech_duration_s']:.2f} s)")
        errs = problems(m)
        if errs:
            for e in errs:
                print(f"  REJECTED — {e}")
            path.unlink(missing_ok=True)
            print("  Nothing kept. Let's redo it.")
            continue
        answer = input("  Save this take? [Y/n] ").strip().lower()
        if answer in ("", "y", "yes"):
            return path, m
        path.unlink(missing_ok=True)
        print("  Discarded. Recording again.")


def store(src: Path, dest: Path) -> str:
    """Copy the raw take unchanged (no editing, no normalisation)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    return sha256(dest)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m demo.record_own",
        description="Record the demo owner's own takes with arecord.",
    )
    parser.add_argument("--word", required=True, choices=sorted(WORDS),
                        help="which word to record (one word per run)")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT,
                        help=f"demo corpus root (default: {DEFAULT_ROOT})")
    parser.add_argument("--no-variants", action="store_true",
                        help="skip the two demonstration variants")
    parser.add_argument("--force", action="store_true",
                        help="overwrite existing takes for this word")
    args = parser.parse_args(argv)

    root = args.root.expanduser().resolve()
    forbidden = {
        (PROJECT_ROOT / "demo" / "data").resolve(),
        (PROJECT_ROOT / "data").resolve(),
        (PROJECT_ROOT / "corpus").resolve(),
    }
    if root in forbidden:
        print(f"error: refusing to write into {root} — own takes go to "
              "demo/data_own, never demo/data or data/", file=sys.stderr)
        return 2

    spec = WORDS[args.word]
    ref_dest = root / "reference_words" / f"{args.word}.wav"
    rec_dests = [root / "recitations" / f"{args.word}__own_t{i}.wav"
                 for i in range(4)]
    var_dests = [root / "variants" / f"{args.word}__var-{label}.wav"
                 for label, _tag, _hint in spec["variants"]]

    existing = [p for p in [ref_dest, *rec_dests] if p.exists()]
    if existing and not args.force:
        print("error: takes already exist for this word (use --force to "
              "replace them):", file=sys.stderr)
        for p in existing:
            print(f"  {p.relative_to(PROJECT_ROOT)}", file=sys.stderr)
        return 2

    level = capture_level()
    print(f"demo root : {root}")
    print(f"device    : {DEVICE_NOTE}")
    print(f"capture   : {level}")
    print(f"word      : {args.word} — {spec['devanagari']} ({spec['iast']})")
    print(f"takes     : 1 reference + 4 correct, 2.5 s each, 16 kHz mono")
    print("Nothing is kept unless it passes the gates and you accept it.\n")

    manifest_path = root / "recordings.json"
    manifest: dict = {"recordings": {}}
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest.setdefault("recordings", {})
        except json.JSONDecodeError:
            pass

    saved: list[tuple[Path, str, dict, str]] = []   # dest, sha, metrics, role

    def save(src: Path, dest: Path, role: str, take_no, variant,
             error_type) -> None:
        digest = store(src, dest)
        m = measure(dest)
        rel = str(dest.relative_to(PROJECT_ROOT))
        manifest["recordings"][rel] = {
            "path": rel,
            "word_id": args.word,
            "role": role,
            "take": take_no,
            "variant": variant,
            "error_type": error_type,
            "sha256": digest,
            "recorded_utc": _dt.datetime.now(_dt.timezone.utc)
            .replace(microsecond=0).isoformat(),
            "device": DEVICE_NOTE,
            "capture_level": level,
            **m,
        }
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        saved.append((dest, digest, m, role))
        print(f"  saved {rel}  sha256 {digest[:16]}…")

    tmpdir = Path(tempfile.mkdtemp(prefix="sd_own_"))
    try:
        src, _m = take(
            tmpdir, "REFERENCE",
            f"Say {spec['devanagari']} ({spec['iast']}) once, clearly.")
        save(src, ref_dest, "reference", None, None, None)

        for i in range(4):
            src, _m = take(
                tmpdir, f"CORRECT {i + 1}/4",
                f"Say {spec['devanagari']} ({spec['iast']}) again — a normal, "
                "correct recitation.")
            save(src, rec_dests[i], "correct", i, None, None)

        if not args.no_variants:
            print("\nDemonstration variants (never used for calibration).")
            answer = input("Record the two variants for this word? [y/N] ").strip().lower()
            if answer in ("y", "yes"):
                for (label, tag, hint), dest in zip(spec["variants"], var_dests):
                    src, _m = take(tmpdir, f"VARIANT {label}",
                                   f"{hint}  [{tag}]")
                    save(src, dest, "variant", None, label, tag)
    except (KeyboardInterrupt, EOFError):
        print("\nStopped. Takes already accepted are saved; this run is "
              "incomplete.", file=sys.stderr)
        return 130
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    print("\nAccepted in this run:")
    for dest, digest, m, role in saved:
        print(f"  {dest.relative_to(PROJECT_ROOT)}  {role:<9} "
              f"{m['duration_s']:.2f} s peak {m['peak']:.3f}  {digest}")
    print("\nNext: DEMO_DATA_ROOT=demo/data_own "
          ".venv/bin/python -m demo.build_demo_calibration")
    return 0


if __name__ == "__main__":
    sys.exit(main())
