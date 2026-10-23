"""CLI: gated promotion of a booth session out of ``data/_incoming/``.

    python -m samskrita_dhvani.promote --session <session-id> --dry-run
    python -m samskrita_dhvani.promote --session <session-id> --apply

Implements the RecordingProtocol.md §5 acceptance rule in code. A clip
enters the corpus only when **all** of these hold:

1. ``data/provenance/REC_<session-id>.md`` exists, its §1 session-sheet
   values are all filled (including a recitation tradition and a consent
   *reference*, not a bare "yes"), and its Session ID matches the sheet
   it claims to be;
2. the clip has a complete §2 checklist row (all eleven columns filled,
   for this filename and this session);
3. the clip passes the DataIntegrity §4 automated sweep — it decodes,
   is not near-silent (WebRTC VAD speech fraction > 10%), shows no
   clipping (peak < 0.99 and fewer than 0.1% of samples at |x| ≥ 0.999),
   and is not listed in ``data/EXCLUDED.csv``;
4. ``files/PROVENANCE.md`` references the session ID.

A clip failing any gate **stays in ``data/_incoming/<session-id>/``**
and is printed with the failing gate and reason; nothing is repaired,
substituted, or deleted. The §5 label ear-check stays a manual step —
no code here claims a label was verified.

Targets (the booth's existing mapping):
- D5 canonical → ``data/spd/reference_words/<word_id>.wav``
- D5 recitation → ``data/spd/recitations/<word_id>__t<take>.wav``
- D4 take → ``data/gvr_recordings/gvr_c<ch>v<vv>_<reciter>_<session>_t<take>.wav``

Exit codes: 2 for an unusable session (unknown/malformed session id,
missing session metadata, no clips, or neither/both of
``--dry-run``/``--apply``), and for an ``--apply`` run in which no clip
passed. A dry run always exits 0 once it has a table to print.

Scope note: ``POST /api/record/promote`` remains a *staging* helper (it
writes ``PROMOTION.md`` and never moves a file); this CLI is the entry
gate into the corpus.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from samskrita_dhvani.exclusions import ExclusionRegisterError, excluded_row
from samskrita_dhvani.frontend import load_audio_16k, vad_speech_fraction

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INCOMING_ROOT = PROJECT_ROOT / "data" / "_incoming"
PROVENANCE_DIR = PROJECT_ROOT / "data" / "provenance"
PROVENANCE_MD = PROJECT_ROOT / "files" / "PROVENANCE.md"
SPD_ROOT = PROJECT_ROOT / "data" / "spd"
GVR_RECORDINGS_ROOT = PROJECT_ROOT / "data" / "gvr_recordings"

VAD_MIN_SPEECH_FRACTION = 0.10   # DataIntegrity §1.1 (same as the API)
CLIP_PEAK_LIMIT = 0.99           # §4 sweep: peak ≥ 0.99 = clipped
CLIP_SUSTAINED_LIMIT = 0.001     # §4/EXCLUDED: ≥0.1% samples at |x| ≥ 0.999

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

CHECKLIST_FIELDS = (
    "File",
    "Session ID",
    "Item",
    "Take #",
    "Duration (s)",
    "Peak dBFS",
    "Clipping?",
    "Silence trimmed?",
    "Transcript verified?",
    "Sweep date",
    "Provenance entry",
)

_PLACEHOLDERS = {"", "-", "—", "–", "?", "tbd", "todo", "..."}
_BARE_CONSENT = {"yes", "y", "true", "obtained", "given", "done"}

_D5_NAME = re.compile(
    r"^spd_(?P<item>.+)_(?P<role>canonical|recitation)_t(?P<take>\d+)\.wav$"
)
_D4_NAME = re.compile(
    r"^gvr_(?P<key>[a-z0-9]+)_recitation_t(?P<take>\d+)\.wav$"
)


class PromoteRefusal(Exception):
    """An unusable session — printed loudly, exit 2."""


@dataclass
class GateFailure:
    gate: str
    reason: str


@dataclass
class ClipDecision:
    file: str
    src: Path
    target: Path | None
    failures: list[GateFailure] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures


@dataclass
class PromotionReport:
    session_id: str
    program: str
    dry_run: bool
    session_sheet_path: Path
    session_sheet_failures: list[GateFailure]
    provenance_path: Path
    provenance_failures: list[GateFailure]
    clips: list[ClipDecision]

    @property
    def promoted(self) -> list[ClipDecision]:
        return [c for c in self.clips if c.ok]

    @property
    def held(self) -> list[ClipDecision]:
        return [c for c in self.clips if not c.ok]

    def by_reason(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for clip in self.held:
            for f in clip.failures:
                counts[f.gate] = counts.get(f.gate, 0) + 1
        return dict(sorted(counts.items()))


# ----------------------------------------------------------------------
# markdown parsing


def _cells(line: str) -> list[str] | None:
    s = line.strip()
    if not (s.startswith("|") and s.endswith("|")):
        return None
    return [c.strip() for c in s.strip("|").split("|")]


def _clean(cell: str) -> str:
    return cell.strip().strip("*").strip("`").strip()


def _separator(cells: list[str]) -> bool:
    return bool(cells) and all(
        re.fullmatch(r":?-{2,}:?", c.replace(" ", "")) for c in cells
    )


def _filled(value: str) -> bool:
    return _clean(value).casefold() not in _PLACEHOLDERS


def _section(lines: list[str], heading: str) -> list[str]:
    """Lines of one ``## <n>.`` section, up to the next ``## ``."""
    out: list[str] = []
    inside = False
    for line in lines:
        if re.match(r"^##\s", line):
            if inside:
                break
            inside = heading in line
            continue
        if inside:
            out.append(line)
    return out


def _table_by_header(lines: list[str], required: str):
    """(header_cells, rows) of the first table whose header contains it."""
    for i, line in enumerate(lines):
        cells = _cells(line)
        if cells is None:
            continue
        lowered = [_clean(c).casefold() for c in cells]
        if any(required.casefold() in c for c in lowered):
            rows = []
            for line2 in lines[i + 1:]:
                row = _cells(line2)
                if row is None:
                    break
                if _separator(row):
                    continue
                rows.append(row)
            return [_clean(c) for c in cells], rows
    return None, []


def parse_session_sheet(text: str) -> tuple[dict[str, str], list[dict[str, str]]]:
    """(§1 fields, §2 rows as header→value dicts) from a REC sheet."""
    lines = text.splitlines()
    sec1 = _section(lines, "## 1.")
    sec2 = _section(lines, "## 2.")

    fields: dict[str, str] = {}
    for line in sec1:
        cells = _cells(line)
        if cells is None or len(cells) < 2:
            continue
        fields[_clean(cells[0]).casefold()] = " | ".join(
            c for c in (_clean(x) for x in cells[1:]) if c
        )

    header, rows = _table_by_header(sec2, "File")
    parsed_rows: list[dict[str, str]] = []
    if header is not None:
        index = {}
        for want in CHECKLIST_FIELDS:
            for j, name in enumerate(header):
                if _clean(name).casefold().startswith(want.casefold()):
                    index[want] = j
                    break
        for row in rows:
            parsed_rows.append({
                want: (row[j] if j < len(row) else "")
                for want, j in index.items()
            })
    return fields, parsed_rows


# ----------------------------------------------------------------------
# gates


def _session_sheet_gate(
    session_id: str,
) -> tuple[Path, list[GateFailure], list[dict[str, str]]]:
    path = PROVENANCE_DIR / f"REC_{session_id}.md"
    failures: list[GateFailure] = []
    if not path.is_file():
        return path, [GateFailure(
            "session_sheet", f"{path} does not exist (RecordingProtocol §1 sheet)",
        )], []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return path, [GateFailure("session_sheet", f"{path} unreadable: {exc}")], []

    fields, rows = parse_session_sheet(text)
    for want in SESSION_FIELDS:
        value = fields.get(want.casefold(), "")
        if not _filled(value):
            failures.append(GateFailure(
                "session_sheet",
                f"§1 field '{want}' is empty in {path.name}",
            ))
    session_cell = fields.get("session id", "")
    if _filled(session_cell) and _clean(session_cell) != session_id:
        failures.append(GateFailure(
            "session_sheet",
            f"§1 Session ID is '{_clean(session_cell)}', not '{session_id}' "
            f"({path.name})",
        ))
    consent = fields.get("consent", "")
    if _filled(consent) and _clean(consent).casefold() in _BARE_CONSENT:
        failures.append(GateFailure(
            "session_sheet",
            f"§1 Consent is only '{_clean(consent)}' — cite the consent "
            "form/reference (DataIntegrity §2)",
        ))
    if not rows:
        failures.append(GateFailure(
            "session_sheet",
            f"no §2 per-file checklist rows in {path.name}",
        ))
    return path, failures, rows


def _provenance_gate(session_id: str) -> tuple[Path, list[GateFailure]]:
    path = PROVENANCE_MD
    if not path.is_file():
        return path, [GateFailure(
            "provenance", f"{path} does not exist (DataIntegrity §2)",
        )]
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return path, [GateFailure("provenance", f"{path} unreadable: {exc}")]
    if session_id not in text:
        return path, [GateFailure(
            "provenance",
            f"'{session_id}' is not referenced anywhere in {path} — "
            "add the session to its source entry",
        )]
    return path, []


def _checklist_gate(
    session_id: str,
    filename: str,
    rows: list[dict[str, str]],
) -> list[GateFailure]:
    matches = [r for r in rows if _clean(r.get("File", "")) == filename]
    if not matches:
        return [GateFailure(
            "checklist_row",
            f"no §2 checklist row for '{filename}' in the session sheet",
        )]
    if len(matches) > 1:
        return [GateFailure(
            "checklist_row",
            f"{len(matches)} §2 checklist rows for '{filename}' — ambiguous",
        )]
    row = matches[0]
    failures: list[GateFailure] = []
    missing = [f for f in CHECKLIST_FIELDS if not _filled(row.get(f, ""))]
    if missing:
        failures.append(GateFailure(
            "checklist_row",
            f"§2 row for '{filename}' has empty field(s): "
            + ", ".join(missing),
        ))
    session_cell = row.get("Session ID", "")
    if _filled(session_cell) and _clean(session_cell) != session_id:
        failures.append(GateFailure(
            "checklist_row",
            f"§2 row for '{filename}' names session "
            f"'{_clean(session_cell)}', not '{session_id}'",
        ))
    return failures


def _sweep_gate(path: Path) -> list[GateFailure]:
    failures: list[GateFailure] = []
    row = excluded_row(path)
    if row is not None:
        failures.append(GateFailure(
            "sweep",
            f"listed in data/EXCLUDED.csv ({row.reason}; {row.date}) — "
            "DataIntegrity §4",
        ))
    try:
        y = load_audio_16k(str(path))
    except Exception as exc:  # noqa: BLE001 — per-file, loud hold
        failures.append(GateFailure("sweep", f"decode failed: {exc}"))
        return failures
    frac = vad_speech_fraction(y)
    if frac <= VAD_MIN_SPEECH_FRACTION:
        failures.append(GateFailure(
            "sweep",
            f"near-silence: VAD speech fraction {frac:.3f} ≤ "
            f"{VAD_MIN_SPEECH_FRACTION:.2f} (DataIntegrity §1.1)",
        ))
    peak = float(np.max(np.abs(y))) if len(y) else 0.0
    sustained = float(np.mean(np.abs(y) >= 0.999)) if len(y) else 0.0
    if peak >= CLIP_PEAK_LIMIT or sustained >= CLIP_SUSTAINED_LIMIT:
        failures.append(GateFailure(
            "sweep",
            f"clipping: peak {peak:.4f} (limit < {CLIP_PEAK_LIMIT}) and "
            f"{sustained:.4%} of samples at |x| ≥ 0.999 "
            f"(limit < {CLIP_SUSTAINED_LIMIT:.1%})",
        ))
    return failures


# ----------------------------------------------------------------------
# promotion targets


def _target_for(
    filename: str,
    program: str,
    session_id: str,
    reciter_slug: str | None,
) -> tuple[Path | None, GateFailure | None]:
    if program == "D5":
        m = _D5_NAME.match(filename)
        if m is None:
            return None, GateFailure(
                "name",
                f"'{filename}' does not match "
                "spd_<word_id>_<canonical|recitation>_t<take>.wav",
            )
        item, role, take = m.group("item"), m.group("role"), m.group("take")
        if role == "canonical":
            return SPD_ROOT / "reference_words" / f"{item}.wav", None
        return SPD_ROOT / "recitations" / f"{item}__t{take}.wav", None

    m = _D4_NAME.match(filename)
    if m is None:
        return None, GateFailure(
            "name",
            f"'{filename}' does not match "
            "gvr_<cNvNN>_recitation_t<take>.wav",
        )
    key, take = m.group("key"), m.group("take")
    vm = re.fullmatch(r"c(\d+)v(\d+)", key)
    if vm is None:
        return None, GateFailure(
            "name", f"'{filename}' verse key '{key}' is not c<ch>v<vv>",
        )
    if not reciter_slug:
        return None, GateFailure(
            "name",
            "session_meta.json has no reciter_slug — cannot build the "
            "protocol §3 promoted name",
        )
    chapter, verse = vm.group(1), int(vm.group(2))
    return (
        GVR_RECORDINGS_ROOT
        / f"gvr_c{chapter}v{verse:02d}_{reciter_slug}_{session_id}_t{take}.wav",
        None,
    )


# ----------------------------------------------------------------------
# planning / applying


def plan_promotion(session_id: str, *, dry_run: bool) -> PromotionReport:
    """Evaluate every gate; move nothing. Raises PromoteRefusal."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", session_id):
        raise PromoteRefusal(f"malformed session id: '{session_id}'")
    session_dir = INCOMING_ROOT / session_id
    if not session_dir.is_dir():
        raise PromoteRefusal(f"session not found in data/_incoming: {session_dir}")
    meta_path = session_dir / "session_meta.json"
    if not meta_path.is_file():
        raise PromoteRefusal(f"session metadata missing: {meta_path}")
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PromoteRefusal(f"session metadata unreadable ({meta_path}): {exc}")
    program = meta.get("program", "D5")
    if program not in ("D5", "D4"):
        raise PromoteRefusal(
            f"session_meta.json declares unknown program '{program}'"
        )

    clips = sorted(
        p for p in session_dir.iterdir()
        if p.is_file() and p.suffix.lower() == ".wav"
    )
    if not clips:
        raise PromoteRefusal(f"session has no .wav clips: {session_dir}")

    sheet_path, sheet_failures, rows = _session_sheet_gate(session_id)
    prov_path, prov_failures = _provenance_gate(session_id)

    decisions: list[ClipDecision] = []
    for p in clips:
        target, name_failure = _target_for(
            p.name, program, session_id, meta.get("reciter_slug")
        )
        decision = ClipDecision(file=p.name, src=p, target=target)
        decision.failures.extend(sheet_failures)
        decision.failures.extend(prov_failures)
        if name_failure is not None:
            decision.failures.append(name_failure)
        if rows:  # a missing sheet already failed; don't double-report
            decision.failures.extend(_checklist_gate(session_id, p.name, rows))
        decision.failures.extend(_sweep_gate(p))
        if target is not None and target.exists():
            decision.failures.append(GateFailure(
                "target_exists",
                f"refusing to overwrite existing {target}",
            ))
        decisions.append(decision)

    return PromotionReport(
        session_id=session_id,
        program=program,
        dry_run=dry_run,
        session_sheet_path=sheet_path,
        session_sheet_failures=sheet_failures,
        provenance_path=prov_path,
        provenance_failures=prov_failures,
        clips=decisions,
    )


def apply_promotion(report: PromotionReport) -> tuple[int, int]:
    """Move the passing clips; return (moved, failed_moves)."""
    moved = failed = 0
    for clip in report.promoted:
        assert clip.target is not None  # a passing clip always has one
        try:
            clip.target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(clip.src), str(clip.target))
            moved += 1
        except OSError as exc:
            failed += 1
            print(f"  ! move failed '{clip.file}': {exc}", file=sys.stderr)
            clip.failures.append(GateFailure("move_failed", str(exc)))
    return moved, failed


# ----------------------------------------------------------------------
# rendering / CLI


def render(report: PromotionReport) -> str:
    lines: list[str] = []
    lines.append(
        f"Promotion — session {report.session_id} ({report.program})"
        + (" [DRY RUN]" if report.dry_run else "")
    )
    lines.append(
        f"  session sheet: {report.session_sheet_path} — "
        + ("PASS" if not report.session_sheet_failures else "FAIL")
    )
    for f in report.session_sheet_failures:
        lines.append(f"    ! {f.gate}: {f.reason}")
    lines.append(
        f"  provenance: {report.provenance_path} — "
        + ("PASS" if not report.provenance_failures else "FAIL")
    )
    for f in report.provenance_failures:
        lines.append(f"    ! {f.gate}: {f.reason}")

    lines.append(f"  clips: {len(report.clips)}")
    for clip in report.clips:
        if clip.ok:
            lines.append(f"    PASS {clip.file} → {clip.target}")
        else:
            reasons = "; ".join(f"{f.gate}: {f.reason}" for f in clip.failures)
            lines.append(f"    HOLD {clip.file}: {reasons}")

    lines.append(
        f"  counts: promoted {len(report.promoted)} · "
        f"held {len(report.held)}"
    )
    if report.held:
        lines.append(
            "  held by reason: "
            + " · ".join(f"{k} {v}" for k, v in report.by_reason().items())
        )
    lines.append(
        "  dry run: nothing moved" if report.dry_run
        else "  promotion applied"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m samskrita_dhvani.promote",
        description="Gated promotion of a booth session per "
                    "RecordingProtocol.md §5.",
    )
    parser.add_argument("--session", required=True,
                        help="session id under data/_incoming/")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true",
                      help="print the per-clip gate table; move nothing")
    mode.add_argument("--apply", action="store_true",
                      help="move only the clips that pass every gate")
    args = parser.parse_args(argv)

    try:
        report = plan_promotion(args.session, dry_run=args.dry_run)
    except PromoteRefusal as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except ExclusionRegisterError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(render(report))
    if args.dry_run:
        return 0

    moved, failed = apply_promotion(report)
    if failed:
        print(f"  ! {failed} move(s) failed (see above)", file=sys.stderr)
    print(f"promoted {moved} clip(s); held {len(report.held)}")
    return 0 if moved and not failed else 2


if __name__ == "__main__":
    sys.exit(main())
