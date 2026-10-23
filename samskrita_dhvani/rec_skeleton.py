"""CLI: emit a RecordingProtocol session-sheet skeleton for a booth session.

    python -m samskrita_dhvani.rec_skeleton --session <session-id> [--force]

Writes ``data/provenance/REC_<session-id>.md`` from the booth's
``session_meta.json`` and the clips present in
``data/_incoming/<session-id>/``.

Only machine-known or measured values are filled:

- §1: Session ID, Date / time (``started_utc``), Program (D4/D5, printed
  above the table), the booth's recording-format target, and the
  materials version (``wordlist_version``) when the booth recorded it.
- §2, per clip: File, Session ID, Item, Take #, Duration, Peak dBFS, and
  Clipping? (yes/no from the same criterion the §4 sweep uses: peak
  ≥ 0.99 or ≥ 0.1% of samples at |x| ≥ 0.999).

Everything a human must assert is left **blank, never guessed**: room,
noise, reciter ID/background, recitation tradition, consent, device,
levels notes, procedure, transfer details, and the §2 columns "Silence
trimmed?", "Transcript verified?", "Sweep date", "Provenance entry".
The resulting sheet therefore fails ``python -m samskrita_dhvani.promote``
until a person fills it.

Refusals (rc=2, one loud line): malformed or unknown session, missing or
unreadable ``session_meta.json``, no clips, or an existing sheet without
``--force``. ``--force`` copies the old sheet to
``REC_<session-id>.md.bak-<UTC stamp>`` before writing and prints the
backup path — a hand-filled sheet is never silently discarded.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import soundfile as sf

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INCOMING_ROOT = PROJECT_ROOT / "data" / "_incoming"
PROVENANCE_DIR = PROJECT_ROOT / "data" / "provenance"

SESSION_FIELDS = (
    "Session ID",
    "Date / time",
    "Location / room",
    "Noise environment",
    "Reciter ID",
    "Reciter background",
    "Recitation tradition",
    "Consent",
    "Device",
    "Recording format",
    "Levels",
    "Materials & version",
    "Procedure",
    "Post-session transfer",
)

CHECKLIST_HEADER = (
    "File", "Session ID", "Item (word / ch.v)", "Take #", "Duration (s)",
    "Peak dBFS", "Clipping?", "Silence trimmed?", "Transcript verified?",
    "Sweep date", "Provenance entry",
)

HUMAN_ONLY_FIELDS = (
    "Location / room",
    "Noise environment",
    "Reciter ID",
    "Reciter background",
    "Recitation tradition",
    "Consent",
    "Device",
    "Levels",
    "Procedure",
    "Post-session transfer",
)

RECORDING_FORMAT = "WAV, 16 kHz mono, 16-bit PCM (booth target)"

CLIP_PEAK_LIMIT = 0.99
CLIP_SUSTAINED_LIMIT = 0.001

_SESSION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")
_D5_NAME = re.compile(
    r"^spd_(?P<item>.+)_(?P<role>canonical|recitation)_t(?P<take>\d+)\.wav$"
)
_D4_NAME = re.compile(
    r"^gvr_(?P<key>[a-z0-9]+)_recitation_t(?P<take>\d+)\.wav$"
)


class SkeletonRefusal(Exception):
    """An unusable session — printed loudly, exit 2."""


def _item_and_take(filename: str, program: str) -> tuple[str, str]:
    """(item, take) from the booth filename; blanks if unparseable."""
    pattern = _D5_NAME if program == "D5" else _D4_NAME
    m = pattern.match(filename)
    if m is None:
        return "", ""
    item = m.group("item") if program == "D5" else m.group("key")
    return item, m.group("take")


def _measure(path: Path) -> dict | None:
    """Duration / peak / clipping exactly as the §4 sweep defines them."""
    try:
        info = sf.info(str(path))
        audio, _ = sf.read(str(path), dtype="float32", always_2d=True)
    except Exception:  # noqa: BLE001 — reported per clip, never guessed
        return None
    if not info.samplerate or info.frames <= 0:
        return None
    mono = audio.mean(axis=1)
    peak = float(np.max(np.abs(mono))) if len(mono) else 0.0
    sustained = float(np.mean(np.abs(mono) >= 0.999)) if len(mono) else 0.0
    return {
        "duration": info.frames / info.samplerate,
        "peak": peak,
        "peak_dbfs": (20.0 * np.log10(peak)) if peak > 0 else None,
        "clipping": peak >= CLIP_PEAK_LIMIT or sustained >= CLIP_SUSTAINED_LIMIT,
    }


def _cell(value: str) -> str:
    return value.replace("|", "/").strip()


def build_sheet(
    session_id: str,
    meta: dict,
    clips: list[Path],
) -> tuple[str, list[str]]:
    """(markdown text, warnings) for a fresh skeleton."""
    program = meta.get("program", "D5")
    started = str(meta.get("started_utc") or "").strip()
    version = str(meta.get("wordlist_version") or "").strip()

    values = {
        "Session ID": session_id,
        "Date / time": started,
        "Recording format": RECORDING_FORMAT,
        "Materials & version": version,
    }
    field_rows = []
    for field in SESSION_FIELDS:
        field_rows.append(f"| **{field}** | {_cell(values.get(field, ''))} |")

    warnings: list[str] = []
    clip_rows = []
    for clip in clips:
        info = _measure(clip)
        item, take = _item_and_take(clip.name, program)
        if info is None:
            warnings.append(
                f"unreadable clip '{clip.name}': duration/peak/clipping left blank"
            )
            duration = peak = clipping = ""
        else:
            duration = f"{info['duration']:.3f}"
            peak = ("" if info["peak_dbfs"] is None
                    else f"{info['peak_dbfs']:.1f}")
            clipping = "yes" if info["clipping"] else "no"
        clip_rows.append(
            f"| {_cell(clip.name)} | {session_id} | {_cell(item)} | "
            f"{_cell(take)} | {duration} | {peak} | {clipping} |  |  |  |  |"
        )

    text = f"""# REC {session_id} — session sheet

**Program:** {program} (from session_meta.json)
*Generated by `python -m samskrita_dhvani.rec_skeleton`. Machine-known
and measured fields are filled; every blank is deliberate and must be
completed by the rater/operator before promotion (RecordingProtocol
§1–§2, §5).*

## 1. Session sheet (one per recording session)

| Field | Value (fill in) |
|---|---|
{chr(10).join(field_rows)}

## 2. Per-file checklist (one row per clip)

| {' | '.join(CHECKLIST_HEADER)} |
|{'---|' * len(CHECKLIST_HEADER)}
{chr(10).join(clip_rows)}
"""
    return text, warnings


def _backup_path(path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    candidate = path.with_name(f"{path.name}.bak-{stamp}")
    n = 2
    while candidate.exists():
        candidate = path.with_name(f"{path.name}.bak-{stamp}-{n}")
        n += 1
    return candidate


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m samskrita_dhvani.rec_skeleton",
        description="Emit data/provenance/REC_<session-id>.md from a booth "
                    "session: machine-known values filled, human-only "
                    "fields deliberately blank.",
    )
    parser.add_argument("--session", required=True,
                        help="session id under data/_incoming/")
    parser.add_argument("--force", action="store_true",
                        help="replace an existing sheet (the old file is "
                             "backed up first)")
    args = parser.parse_args(argv)

    session_id = args.session
    if not _SESSION_RE.fullmatch(session_id):
        print(f"error: malformed session id: '{session_id}'", file=sys.stderr)
        return 2
    session_dir = INCOMING_ROOT / session_id
    if not session_dir.is_dir():
        print(f"error: unknown session (not under data/_incoming): "
              f"{session_dir}", file=sys.stderr)
        return 2
    meta_path = session_dir / "session_meta.json"
    if not meta_path.is_file():
        print(f"error: session_meta.json missing: {meta_path}", file=sys.stderr)
        return 2
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: session_meta.json unreadable ({meta_path}): {exc}",
              file=sys.stderr)
        return 2

    clips = sorted(
        p for p in session_dir.iterdir()
        if p.is_file() and p.suffix.lower() == ".wav"
    )
    if not clips:
        print(f"error: session has no clips: {session_dir}", file=sys.stderr)
        return 2

    out = PROVENANCE_DIR / f"REC_{session_id}.md"
    if out.exists() and not args.force:
        print(f"error: sheet already exists: {out} (use --force to replace "
              "it; a hand-filled sheet is never clobbered silently)",
              file=sys.stderr)
        return 2

    text, warnings = build_sheet(session_id, meta, clips)
    if out.exists():
        backup = _backup_path(out)
        try:
            shutil.copy2(out, backup)
        except OSError as exc:
            print(f"error: could not back up {out}: {exc}", file=sys.stderr)
            return 2
        print(f"backup: {backup} (previous sheet preserved)")

    try:
        _write_atomic(out, text)
    except OSError as exc:
        print(f"error: could not write {out}: {exc}", file=sys.stderr)
        return 2

    for warning in warnings:
        print(f"  ! {warning}", file=sys.stderr)
    print(f"wrote {out} (program {meta.get('program', 'D5')}, "
          f"{len(clips)} clip row(s))")
    print("  machine-filled §1: Session ID, Date / time, Program, "
          "Recording format, Materials & version")
    print("  machine-filled §2: File, Session ID, Item, Take #, Duration, "
          "Peak dBFS, Clipping?")
    print("  left blank for the human: " + ", ".join(HUMAN_ONLY_FIELDS)
          + ", and §2 Silence trimmed? / Transcript verified? / Sweep date / "
          "Provenance entry")
    print("  this sheet fails `python -m samskrita_dhvani.promote` until "
          "those are filled")
    return 0


if __name__ == "__main__":
    sys.exit(main())
