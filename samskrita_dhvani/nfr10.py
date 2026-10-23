"""CLI: NFR-10 correlation — SPD similarity vs human ratings.

    python -m samskrita_dhvani.nfr10 \
        --ratings files/Nfr10RatingSheet.md \
        --scores data/spd/scores.jsonl \
        [--json OUT] [--min-n 20] [--fixtures]

What it does
------------
Joins one completed rater sheet per rater (the markdown template in
``files/Nfr10RatingSheet.md``) to SPD scorer outputs captured from
``POST /api/spd/score`` — the join key is ``attempt_id``, which the
endpoint echoes when the caller supplies it as a form field. Reports
Spearman ρ over the joined pairs, with n and the p-value, plus each
rater's role, background, and stated recitation tradition from the
sheet header.

Honesty contract (Ground Rule 1)
--------------------------------
Every refusal is a single loud stderr line ending in
``no ratings, no number`` and exits rc=2. The CLI refuses when:

- the ratings file is missing, empty, or contains no filled ratings;
- a rating is outside the fixed 1–5 rubric;
- a rated attempt has no matching score (the join is incomplete);
- n is below ``--min-n`` (default 20; the value used is printed);
- there is only one rater, so no inter-rater agreement exists, or no
  attempt was rated by two or more raters.

Two or more raters: pairwise Spearman agreement is reported **before**
the score-versus-mean-rating correlation. Ratings are pooled per
attempt as the mean of the raters who rated it (ties are expected and
handled by average ranks in Spearman).

Every successful report carries two sentences:

1. the correlation covers only the rated attempts present in both
   inputs — it says nothing about unrated attempts; and
2. the reference-reciter tradition, read from ``files/PROVENANCE.md``
   (SPD-01 / SPD-02), together with the ear-check gate state
   (SPD Open Item 2) — still **open**, so no reference clip has passed
   the human listen-through.

Synthetic fixtures (NFR-02) carry the marker ``SYNTHETIC-FIXTURE`` in
the sheet text. Such a run is refused unless ``--fixtures`` is passed
explicitly, and then its output is banner-labelled and its JSON carries
``"synthetic_fixture": true``: a fixture number can never be mistaken
for a measurement of real attempts.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from scipy import stats

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROVENANCE_PATH = PROJECT_ROOT / "files" / "PROVENANCE.md"
EAR_CHECK_CHECKLIST = (
    PROJECT_ROOT / "data" / "provenance" / "spd_listen_2026-09-23"
    / "CHECKLIST.md"
)

SCHEMA_VERSION = 1
KIND = "nfr10_correlation"
MIN_N_DEFAULT = 20
REFUSAL_SUFFIX = "— no ratings, no number"
SYNTHETIC_MARKER = "SYNTHETIC-FIXTURE"


class Nfr10Refusal(RuntimeError):
    """A loud, named refusal to produce a number (the CLI exits rc=2)."""


def _refuse(message: str) -> Nfr10Refusal:
    return Nfr10Refusal(f"{message} {REFUSAL_SUFFIX}")


@dataclass
class Rater:
    """One completed rating sheet (one rater)."""

    source: str
    rater_id: str = ""
    role: str = ""
    native_languages: str = ""
    script_familiarity: str = ""
    years: str = ""
    tradition: str = ""
    date: str = ""
    ratings: dict[str, int] = field(default_factory=dict)
    not_rateable: list[str] = field(default_factory=list)
    synthetic: bool = False

    @property
    def label(self) -> str:
        return self.rater_id or "(unidentified rater)"

    @property
    def background(self) -> str:
        return (
            f"native language(s): {self.native_languages or 'not stated'}; "
            f"script familiarity: {self.script_familiarity or 'not stated'}; "
            f"years of study/teaching: {self.years or 'not stated'}"
        )


# ----------------------------------------------------------------------
# markdown table parsing


def _cells(line: str) -> list[str] | None:
    s = line.strip()
    if not (s.startswith("|") and s.endswith("|")):
        return None
    return [c.strip() for c in s.strip("|").split("|")]


def _clean(cell: str) -> str:
    return cell.strip().strip("*").strip("`").strip()


_SEPARATOR = re.compile(r"^:?-{2,}:?$")


def _is_separator(cells: list[str]) -> bool:
    return bool(cells) and all(_SEPARATOR.match(c.replace(" ", "")) for c in cells)


_HEADER_FIELDS = {
    "rater id": "rater_id",
    "role": "role",
    "native language": "native_languages",
    "script familiarity": "script_familiarity",
    "recitation tradition": "tradition",
    "years of sanskrit study": "years",
    "date of rating": "date",
}


def _parse_header(lines: list[str], rater: Rater) -> None:
    for line in lines:
        cells = _cells(line)
        if not cells or len(cells) < 2:
            continue
        label = _clean(cells[0]).lower()
        for prefix, attr in _HEADER_FIELDS.items():
            if label.startswith(prefix):
                value = _clean(cells[1])
                # A template cell may span multiple columns; join them.
                if len(cells) > 2:
                    value = " | ".join(
                        c for c in (_clean(x) for x in cells[1:]) if c
                    )
                setattr(rater, attr, value)
                break


def _parse_ratings(lines: list[str], rater: Rater) -> None:
    """Parse the ``| Attempt ID | … | Rating (1–5) | … |`` table."""
    start = None
    id_idx = rating_idx = None
    for i, line in enumerate(lines):
        cells = _cells(line)
        if not cells:
            continue
        lowered = [_clean(c).lower() for c in cells]
        if any(c.startswith("attempt id") for c in lowered) and any(
            c.startswith("rating") for c in lowered
        ):
            start = i + 1
            id_idx = next(
                j for j, c in enumerate(lowered) if c.startswith("attempt id")
            )
            rating_idx = next(
                j for j, c in enumerate(lowered) if c.startswith("rating")
            )
            break
    if start is None:
        return

    for line in lines[start:]:
        cells = _cells(line)
        if cells is None:
            break  # table ended
        if _is_separator(cells):
            continue
        attempt = _clean(cells[id_idx]) if id_idx < len(cells) else ""
        if not attempt:
            continue  # blank template row
        raw = _clean(cells[rating_idx]) if rating_idx < len(cells) else ""
        if not raw:
            raise _refuse(
                f"malformed rating sheet '{rater.source}': attempt "
                f"'{attempt}' has no rating entry (use 1–5 or N/A)"
            )
        if raw.lower() in ("n/a", "na", "n/a.", "n.a."):
            rater.not_rateable.append(attempt)
            continue
        try:
            value = int(raw)
        except ValueError:
            raise _refuse(
                f"malformed rating sheet '{rater.source}': rating {raw!r} "
                f"for attempt '{attempt}' is not an integer 1–5"
            ) from None
        if not 1 <= value <= 5:
            raise _refuse(
                f"rating {value} for attempt '{attempt}' in "
                f"'{rater.source}' is outside the fixed 1–5 rubric"
            )
        if attempt in rater.ratings:
            raise _refuse(
                f"malformed rating sheet '{rater.source}': attempt "
                f"'{attempt}' is rated more than once"
            )
        rater.ratings[attempt] = value


def parse_rating_sheet(path: Path) -> Rater:
    """Parse one filled sheet; raises :class:`Nfr10Refusal` on refuse paths."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise _refuse(f"ratings file not found: {path}") from None
    except OSError as exc:
        raise _refuse(f"ratings file unreadable: {path}: {exc}") from exc

    lines = text.splitlines()
    rater = Rater(source=str(path), synthetic=SYNTHETIC_MARKER in text)
    _parse_header(lines, rater)
    _parse_ratings(lines, rater)
    return rater


def load_ratings(paths: list[str]) -> list[Rater]:
    sources: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            found = sorted(p.glob("*.md"))
            if not found:
                raise _refuse(f"ratings directory has no .md sheets: {p}")
            sources.extend(found)
        else:
            sources.append(p)
    if not sources:
        raise _refuse("no ratings file given")
    raters = [parse_rating_sheet(p) for p in sources]
    blank = [r.source for r in raters if not r.ratings and not r.not_rateable]
    if blank:
        raise _refuse(
            f"ratings sheet(s) have no filled ratings (blank template?): "
            f"{', '.join(blank)}"
        )
    return raters


# ----------------------------------------------------------------------
# scores input


def _score_records(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise _refuse(f"scores file not found: {path}") from None
    except OSError as exc:
        raise _refuse(f"scores file unreadable: {path}: {exc}") from exc

    if path.suffix.lower() in (".jsonl", ".ndjson"):
        try:
            return [json.loads(line) for line in text.splitlines() if line.strip()]
        except json.JSONDecodeError as exc:
            raise _refuse(f"scores file is not valid JSONL: {path}: {exc}") from None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise _refuse(f"scores file is not valid JSON: {path}: {exc}") from None
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if isinstance(data.get("scores"), list):
            return data["scores"]
        if "attempt_id" in data:
            return [data]
    raise _refuse(
        f"scores file has an unsupported shape: {path} (expected a JSON "
        "list, a {'scores': [...]} object, one response object, or JSONL)"
    )


def load_scores(path: Path) -> dict[str, dict]:
    """attempt_id → score record. Missing IDs are fatal: no silent join."""
    records = _score_records(path)
    out: dict[str, dict] = {}
    missing = 0
    for rec in records:
        if not isinstance(rec, dict):
            raise _refuse(f"malformed score record in {path}: {rec!r}")
        raw_id = rec.get("attempt_id")
        attempt = str(raw_id).strip() if raw_id is not None else ""
        if not attempt:
            missing += 1
            continue
        sim = rec.get("similarity_pct")
        if not isinstance(sim, (int, float)) or isinstance(sim, bool):
            raise _refuse(
                f"score record '{attempt}' in {path} has no numeric "
                "similarity_pct"
            )
        if not 0.0 <= float(sim) <= 100.0:
            raise _refuse(
                f"score record '{attempt}' in {path} has similarity_pct "
                f"{sim} outside 0–100"
            )
        if attempt in out:
            raise _refuse(f"duplicate attempt_id '{attempt}' in {path}")
        out[attempt] = {"attempt_id": attempt, "similarity_pct": float(sim)}
    if missing:
        raise _refuse(
            f"scores file {path} has {missing} record(s) without "
            "attempt_id — untagged responses cannot be joined (re-capture "
            "POST /api/spd/score with the attempt_id form field)"
        )
    if not out:
        raise _refuse(f"scores file has no score records: {path}")
    return out


# ----------------------------------------------------------------------
# provenance + ear-check honesty lines


def _section(text: str, heading: str) -> str:
    m = re.search(
        rf"^###\s+{re.escape(heading)}.*?$(.*?)(?=^###\s|\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    return m.group(1) if m else ""


def reference_traditions(path: Path = PROVENANCE_PATH) -> dict[str, str | None]:
    """SPD-01/SPD-02 recitation tradition, exactly as provenance states it."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {"SPD-01": None, "SPD-02": None}
    out: dict[str, str | None] = {}
    for sid in ("SPD-01", "SPD-02"):
        body = _section(text, sid)
        m = re.search(
            r"\|\s*\*\*Recitation tradition\*\*\s*\|\s*(.+?)\s*\|", body
        )
        out[sid] = _clean(m.group(1)) if m else None
    return out


def ear_check_status(path: Path = EAR_CHECK_CHECKLIST) -> tuple[bool, str]:
    """(is_open, detail) from the owner checklist's unchecked boxes."""
    if not path.is_file():
        return True, (
            "OPEN/unknown — no listen-through checklist found at "
            f"{path}; no reference clip has a recorded human verdict"
        )
    text = path.read_text(encoding="utf-8")
    unchecked = len(re.findall(r"^\s*-\s*\[\s*\]", text, flags=re.MULTILINE))
    checked = len(
        re.findall(r"^\s*-\s*\[[xX]\]", text, flags=re.MULTILINE)
    )
    if unchecked:
        return True, (
            f"OPEN — {unchecked} unchecked item(s) in {path}; no reference "
            "clip has passed the human listen-through, so these references "
            "are not ear-verified"
        )
    return False, f"closed — {checked} checked item(s) in {path}"


# ----------------------------------------------------------------------
# correlation


def spearman(x: list[float], y: list[float]) -> tuple[float, float]:
    """Spearman ρ and p (scipy; average ranks for ties)."""
    result = stats.spearmanr(x, y)
    return float(result.statistic), float(result.pvalue)


def build_report(
    raters: list[Rater],
    scores: dict[str, dict],
    *,
    min_n: int,
    ratings_sources: list[str],
    scores_source: str,
    synthetic: bool,
    traditions: dict[str, str | None],
    ear_open: bool,
    ear_detail: str,
) -> dict:
    rated: dict[str, list[int]] = {}
    not_rateable: set[str] = set()
    for rater in raters:
        for attempt, value in rater.ratings.items():
            rated.setdefault(attempt, []).append(value)
        not_rateable.update(rater.not_rateable)

    if not rated:
        raise _refuse(
            "ratings sheet(s) contain no filled ratings (blank template?)"
        )

    unscored = sorted(set(rated) - set(scores))
    if unscored:
        ids = ", ".join(unscored[:25]) + (
            f" … (+{len(unscored) - 25} more)" if len(unscored) > 25 else ""
        )
        raise _refuse(
            f"attempt IDs do not match the scores file: {len(unscored)} "
            f"rated attempt(s) have no score — {ids}"
        )
    unrated_scored = sorted(set(scores) - set(rated) - not_rateable)

    if len(raters) < 2:
        raise _refuse(
            f"only 1 rater ('{raters[0].label}') — there is no inter-rater "
            "check, so rater bias cannot be separated from machine error; "
            "supply a second completed sheet"
        )

    agreement: list[dict] = []
    any_overlap = False
    for i in range(len(raters)):
        for j in range(i + 1, len(raters)):
            a, b = raters[i], raters[j]
            common = sorted(set(a.ratings) & set(b.ratings))
            entry = {
                "rater_a": a.label,
                "rater_b": b.label,
                "n": len(common),
                "rho": None,
                "p_value": None,
                "note": None,
            }
            if len(common) >= 2:
                any_overlap = True
                rho, p = spearman(
                    [a.ratings[c] for c in common],
                    [b.ratings[c] for c in common],
                )
                if math.isfinite(rho):
                    entry["rho"], entry["p_value"] = rho, p
                else:
                    entry["note"] = (
                        "undefined — constant ratings over the common attempts"
                    )
            else:
                entry["note"] = "fewer than 2 attempts rated by both raters"
            agreement.append(entry)
    if not any_overlap:
        raise _refuse(
            "no attempt is rated by two or more raters — no inter-rater "
            "agreement can be computed"
        )

    n = len(rated)
    if n < min_n:
        raise _refuse(
            f"n={n} is below the minimum of {min_n} (the --min-n value used "
            f"is {min_n}); collect more rated attempts"
        )

    attempt_ids = sorted(rated)
    mean_ratings = [sum(rated[a]) / len(rated[a]) for a in attempt_ids]
    similarities = [scores[a]["similarity_pct"] for a in attempt_ids]
    rho, p_value = spearman(similarities, mean_ratings)
    if not math.isfinite(rho):
        raise _refuse(
            "Spearman rho is undefined because all ratings or all scores "
            "are identical (constant input)"
        )

    coverage = (
        f"this correlation covers only the {n} rated attempt(s) present in "
        f"both inputs (of {len(scores)} scored attempt(s)); it says nothing "
        "about attempts no rater heard"
    )
    tradition_text = "; ".join(
        f"{sid}: {value if value else 'not stated in provenance'}"
        for sid, value in traditions.items()
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "synthetic_fixture": synthetic,
        "method": "spearman_rank_correlation",
        "pooling": "per-attempt mean of the raters who rated it",
        "n": n,
        "min_n": min_n,
        "spearman_rho": rho,
        "p_value": p_value,
        "coverage_sentence": coverage,
        "rated_attempts": n,
        "scored_attempts": len(scores),
        "scored_but_unrated": {
            "count": len(unrated_scored),
            "attempt_ids": unrated_scored,
        },
        "not_rateable": {
            "count": len(not_rateable),
            "attempt_ids": sorted(not_rateable),
            "note": "marked N/A on a sheet; excluded from the correlation",
        },
        "raters": [
            {
                "source": r.source,
                "rater_id": r.rater_id or None,
                "role": r.role or None,
                "native_languages": r.native_languages or None,
                "script_familiarity": r.script_familiarity or None,
                "years": r.years or None,
                "tradition": r.tradition or None,
                "date": r.date or None,
                "n_rated": len(r.ratings),
                "n_not_rateable": len(r.not_rateable),
            }
            for r in raters
        ],
        "agreement": agreement,
        "reference_tradition": {
            "source": str(PROVENANCE_PATH),
            "entries": traditions,
            "sentence": tradition_text,
        },
        "ear_check": {
            "open": ear_open,
            "detail": ear_detail,
            "open_item": "SPD Open Item 2",
        },
        "ratings_sources": list(ratings_sources),
        "scores_source": scores_source,
    }


def render(report: dict) -> str:
    out: list[str] = []
    if report["synthetic_fixture"]:
        out.append(
            "*** SYNTHETIC FIXTURE — pipeline test only, not evidence "
            "(NFR-02; not a measured correlation) ***"
        )
    out.append("NFR-10 — SPD similarity vs human ratings (Spearman)")
    out.append(f"  scores file: {report['scores_source']} "
               f"({report['scored_attempts']} scored attempt(s))")
    out.append(f"  ratings sheet(s): {len(report['raters'])}")
    for r in report["raters"]:
        out.append(f"    - rater: {r['rater_id'] or '(unidentified)'} "
                   f"· role: {r['role'] or 'not stated'}")
        out.append(
            "      background: native language(s) "
            f"{r['native_languages'] or 'not stated'}; script familiarity "
            f"{r['script_familiarity'] or 'not stated'}; years "
            f"{r['years'] or 'not stated'}"
        )
        out.append(f"      tradition: {r['tradition'] or 'not stated'} "
                   f"· rated {r['n_rated']} attempt(s)")
    out.append(f"  {report['coverage_sentence']}.")
    out.append(
        "  reference-reciter tradition (files/PROVENANCE.md): "
        + report["reference_tradition"]["sentence"]
    )
    out.append(
        f"  ear check ({report['ear_check']['open_item']}): "
        + report["ear_check"]["detail"]
    )
    if report["not_rateable"]["count"]:
        out.append(
            f"  N/A attempts excluded: {report['not_rateable']['count']} "
            f"({', '.join(report['not_rateable']['attempt_ids'])})"
        )

    out.append("  inter-rater agreement (Spearman; reported before the "
               "machine correlation):")
    for pair in report["agreement"]:
        if pair["rho"] is None:
            out.append(
                f"    {pair['rater_a']} vs {pair['rater_b']}: "
                f"not computable — {pair['note']} (n={pair['n']})"
            )
        else:
            out.append(
                f"    {pair['rater_a']} vs {pair['rater_b']}: "
                f"rho={pair['rho']:.4f}, n={pair['n']}, "
                f"p={pair['p_value']:.4g}"
            )

    out.append(
        f"  score vs rating (mean of raters per attempt): "
        f"rho={report['spearman_rho']:.4f}, n={report['n']}, "
        f"p={report['p_value']:.4g}"
    )
    out.append(f"  minimum n applied: {report['min_n']} (--min-n)")
    return "\n".join(out)


# ----------------------------------------------------------------------
# CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m samskrita_dhvani.nfr10",
        description="NFR-10: Spearman correlation between SPD similarity "
                    "scores and human 1–5 ratings, joined on attempt_id.",
    )
    parser.add_argument("--ratings", nargs="+", required=True,
                        help="one filled sheet per rater (markdown), or a "
                             "directory of them")
    parser.add_argument("--scores", required=True,
                        help="JSON/JSONL of POST /api/spd/score responses "
                             "(each must carry attempt_id)")
    parser.add_argument("--json", default=None,
                        help="write the full report as JSON to this path")
    parser.add_argument("--min-n", type=int, default=MIN_N_DEFAULT,
                        help=f"refuse below this n (default {MIN_N_DEFAULT})")
    parser.add_argument("--fixtures", action="store_true",
                        help="allow sheets marked SYNTHETIC-FIXTURE "
                             "(output is banner-labelled; never evidence)")
    args = parser.parse_args(argv)

    try:
        if args.min_n < 2:
            raise _refuse(f"--min-n must be at least 2 (got {args.min_n})")
        raters = load_ratings(args.ratings)
        synthetic = any(r.synthetic for r in raters)
        if synthetic and not args.fixtures:
            marked = [r.source for r in raters if r.synthetic]
            raise _refuse(
                "ratings sheet(s) are marked SYNTHETIC-FIXTURE "
                f"({', '.join(marked)}) — synthetic numbers are not "
                "evidence; pass --fixtures only for pipeline tests"
            )
        scores = load_scores(Path(args.scores))
        report = build_report(
            raters,
            scores,
            min_n=args.min_n,
            ratings_sources=[str(p) for p in args.ratings],
            scores_source=str(args.scores),
            synthetic=synthetic,
            traditions=reference_traditions(),
            ear_open=ear_check_status()[0],
            ear_detail=ear_check_status()[1],
        )
    except Nfr10Refusal as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(render(report))
    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"report JSON: {out} (schema {SCHEMA_VERSION}, kind {KIND})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
