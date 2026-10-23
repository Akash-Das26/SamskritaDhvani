"""DataIntegrity.md §4 exclusion register — enforcement.

``data/EXCLUDED.csv`` (columns ``path,reason,date``) is the
machine-readable list of files the project has swept and excluded.
Until this module existed the register was policy only; nothing read
it. It is now enforced in two places:

- :func:`samskrita_dhvani.frontend.load_audio_16k` — the single
  corpus-facing loader — refuses an excluded path with
  :class:`ExcludedAudioError`, so no training, calibration, sweep, or
  evaluation path can consume one accidentally.
- the corpus walkers of the sweep CLIs
  (:mod:`samskrita_dhvani.build_registry`,
  :mod:`samskrita_dhvani.calibrate`) call :func:`filter_excluded`,
  which drops listed paths **and prints the loud skip count**.

Honesty rule (Ground Rule 1): a missing or malformed register is a
loud failure (:class:`ExclusionRegisterError`, CLIs return rc=2), never
a silent "exclusion disabled" fallback. A register that cannot be read
means the project cannot prove which files are excluded, so it must
stop rather than proceed.

Paths in the CSV are repository-relative (POSIX separators) or
absolute; both are normalised with :meth:`pathlib.Path.resolve` before
comparison, so a relative path and its absolute spelling match.
"""

from __future__ import annotations

import csv
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
"""Repository root — the register lives under it."""

DEFAULT_REGISTER = PROJECT_ROOT / "data" / "EXCLUDED.csv"
"""The tracked exclusion register (``data/EXCLUDED.csv``)."""

REGISTER_ENV_VAR = "SAMSKRITA_EXCLUDED_CSV"
"""Optional override, used by tests and by explicit re-sweeps run
against a candidate register before it is committed."""

REQUIRED_COLUMNS = ("path", "reason", "date")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ExclusionRegisterError(RuntimeError):
    """The register is missing or malformed — exclusion cannot be applied.

    The CLIs turn this into a stderr message and exit code 2; it is
    never swallowed into "no exclusions".
    """


class ExcludedAudioError(RuntimeError):
    """A caller tried to load a path the register excludes."""


@dataclass(frozen=True)
class ExcludedRow:
    """One verified row of the register."""

    path: str
    """Normalised absolute path string (see :func:`_normalise`)."""

    reason: str
    date: str
    raw_path: str
    """The path exactly as written in the CSV (for messages)."""


def register_path() -> Path:
    """The register path in force: ``$SAMSKRITA_EXCLUDED_CSV`` or the
    tracked default."""
    override = os.environ.get(REGISTER_ENV_VAR)
    if override:
        return Path(override).expanduser()
    return DEFAULT_REGISTER


def _normalise(path: str | Path) -> str:
    return str(Path(path).expanduser().resolve())


def _normalise_registered(raw: str) -> str:
    """Register rows are repository-relative by convention; resolve
    them against :data:`PROJECT_ROOT` so the register means the same
    thing from any working directory."""
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return str(p.resolve())


def load_excluded_rows(path: str | Path | None = None) -> dict[str, ExcludedRow]:
    """Parse and validate the register.

    Raises :class:`ExclusionRegisterError` when the file is missing,
    empty, has the wrong header, has a row with the wrong number of
    fields, a blank path/reason, or a date that is not ``YYYY-MM-DD``.
    """
    reg = Path(path) if path is not None else register_path()
    try:
        handle = open(reg, "r", encoding="utf-8-sig", newline="")
    except FileNotFoundError as exc:
        raise ExclusionRegisterError(
            f"exclusion register not found: {reg} — DataIntegrity.md §4 "
            "requires data/EXCLUDED.csv; refusing to run with exclusion "
            f"silently disabled (set {REGISTER_ENV_VAR} only to point at a "
            "deliberate alternative register)"
        ) from exc
    except OSError as exc:
        raise ExclusionRegisterError(
            f"exclusion register unreadable: {reg}: {exc}"
        ) from exc

    rows: dict[str, ExcludedRow] = {}
    with handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ExclusionRegisterError(
                f"exclusion register is empty: {reg} (expected header "
                f"{','.join(REQUIRED_COLUMNS)})"
            ) from exc
        header = [h.strip() for h in header]
        if tuple(header) != REQUIRED_COLUMNS:
            raise ExclusionRegisterError(
                f"malformed exclusion register {reg}: header is "
                f"{','.join(header)!r}, expected "
                f"{','.join(REQUIRED_COLUMNS)!r}"
            )
        for line_no, row in enumerate(reader, start=2):
            if not row or all(not cell.strip() for cell in row):
                continue  # tolerate blank lines; they carry no claim
            if len(row) != len(REQUIRED_COLUMNS):
                raise ExclusionRegisterError(
                    f"malformed exclusion register {reg} line {line_no}: "
                    f"expected {len(REQUIRED_COLUMNS)} columns, got "
                    f"{len(row)}: {row!r}"
                )
            raw_path, reason, date = (cell.strip() for cell in row)
            if not raw_path:
                raise ExclusionRegisterError(
                    f"malformed exclusion register {reg} line {line_no}: "
                    "empty path"
                )
            if not reason:
                raise ExclusionRegisterError(
                    f"malformed exclusion register {reg} line {line_no}: "
                    f"no reason given for '{raw_path}' — an exclusion "
                    "without a reason cannot be reviewed or cleared"
                )
            if not _DATE_RE.match(date):
                raise ExclusionRegisterError(
                    f"malformed exclusion register {reg} line {line_no}: "
                    f"date {date!r} is not YYYY-MM-DD"
                )
            key = _normalise_registered(raw_path)
            rows.setdefault(
                key,
                ExcludedRow(path=key, reason=reason, date=date,
                            raw_path=raw_path),
            )
    if not rows:
        raise ExclusionRegisterError(
            f"exclusion register has no rows: {reg} — an empty register "
            "cannot be distinguished from a broken one"
        )
    return rows


_CACHE: dict[Path, tuple[tuple[int, int], dict[str, ExcludedRow]]] = {}


def _cached_rows(reg: Path) -> dict[str, ExcludedRow]:
    """Parse once per (mtime, size); edits invalidate automatically."""
    try:
        st = reg.stat()
    except OSError as exc:
        raise ExclusionRegisterError(
            f"exclusion register not found: {reg} — DataIntegrity.md §4 "
            "requires data/EXCLUDED.csv; refusing to run with exclusion "
            f"silently disabled (set {REGISTER_ENV_VAR} only to point at a "
            "deliberate alternative register)"
        ) from exc
    key = (st.st_mtime_ns, st.st_size)
    cached = _CACHE.get(reg)
    if cached is not None and cached[0] == key:
        return cached[1]
    rows = load_excluded_rows(reg)
    _CACHE[reg] = (key, rows)
    return rows


def load_excluded_paths(path: str | Path | None = None) -> frozenset[str]:
    """The normalised excluded-path set, validated and cached."""
    reg = Path(path) if path is not None else register_path()
    return frozenset(_cached_rows(reg))


def excluded_row(path: str | Path) -> ExcludedRow | None:
    """The register row for ``path``, or ``None`` when it is allowed."""
    return _cached_rows(register_path()).get(_normalise(path))


def assert_allowed(path: str | Path) -> None:
    """Raise :class:`ExcludedAudioError` if ``path`` is registered.

    Called by the shared loader; the message names the register, the
    reason, and the date so a caller can act instead of guessing.
    """
    row = excluded_row(path)
    if row is not None:
        reg = register_path()
        raise ExcludedAudioError(
            f"'{row.raw_path}' is excluded by {reg} "
            f"(reason: {row.reason}; registered {row.date}) — "
            "DataIntegrity.md §4 forbids using it as reference, training, "
            "or evaluation material"
        )


def filter_excluded(
    paths,
    *,
    label: str = "corpus sweep",
    register: str | Path | None = None,
) -> tuple[list[Path], list[Path]]:
    """Split ``paths`` into (kept, skipped) by the register.

    Prints one loud line to stderr when anything is skipped: the count
    is the evidence that the sweep did not silently absorb excluded
    audio. Returns plain lists so callers can log totals.
    """
    reg = Path(register) if register is not None else register_path()
    rows = _cached_rows(reg)
    kept: list[Path] = []
    skipped: list[Path] = []
    for p in paths:
        p = Path(p)
        if _normalise(p) in rows:
            skipped.append(p)
        else:
            kept.append(p)
    if skipped:
        print(
            f"  ! EXCLUDED register: skipped {len(skipped)} file(s) listed "
            f"in {reg} ({label}) — see DataIntegrity.md §4",
            file=sys.stderr,
        )
    return kept, skipped
