"""CLI: batch-score promoted SPD attempts into an NFR-10 scores file.

    python -m samskrita_dhvani.score_attempts \
        --attempts data/spd/attempts \
        --out data/spd/scores.jsonl \
        [--word-from-name] [--force]

Input convention — RecordingProtocol.md §3 registry-prep names::

    spd_<item>_<reciter>_<sessionid>_t<take>[_var-<tag>].wav

``<item>`` is matched case-insensitively against the FR-12 word list;
the reference word is never guessed. ``<attempt_id>`` in the output is
the filename stem **verbatim** (including any ``_var-*`` tag), which is
the ID the NFR-10 rater sheet must list.

Scoring path (identical to ``POST /api/spd/score``): the D1 loader →
DataIntegrity §1.1 VAD gate (speech fraction > 10%) → the word's
ear-verified reference clip → the measured per-word D₀ → D2
``score_attempt``. One JSON object per scored attempt is written, in the
exact shape ``python -m samskrita_dhvani.nfr10 --scores`` accepts::

    {"attempt_id": …, "reference_word": {word_id, devanagari, iast},
     "similarity_pct": …, "vowel_score": …, "consonant_score": …,
     "duration_score": …, "mfcc_dtw_score": …}

Refusals (rc=2, one loud stderr line)
-------------------------------------
- attempts directory missing, not a directory, or holding no audio;
- the FR-12 word list cannot be built;
- the measured calibration file does not exist (the API's 503
  ``calibration_unavailable`` state);
- the exclusion register is missing/malformed (DataIntegrity §4);
- ``--out`` already exists without ``--force``;
- no attempt survived the gates (nothing written).

Skips (printed per file with the reason, counted by reason)
-----------------------------------------------------------
``unparsed_name``, ``unknown_word``, ``ambiguous_word`` (e.g. ``pata``
for the pAta/pATa minimal pair), ``excluded``, ``decode_failed``,
``near_silence``, ``reference_missing``, ``reference_unreadable``,
``calibration_missing``, ``axis_unmeasurable``, ``duplicate_attempt_id``.
A skip is never replaced by a guessed word or a fabricated score
(DataIntegrity Rule 1).

Notes
-----
- ``--word-from-name`` additionally accepts the booth's shorter
  ``spd_<item>_<role>_t<take>.wav`` names (no reciter/session segment);
  the word still comes from the name and must be in the 27-word list.
  Without it, the full protocol grammar (reciter **and** session
  present) is required.
- The file is written atomically; a partly-written scores file cannot
  be mistaken for a complete run.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from samskrita_dhvani import api
from samskrita_dhvani.exclusions import (
    ExclusionRegisterError,
    excluded_row,
    load_excluded_paths,
)
from samskrita_dhvani.frontend import load_audio_16k, vad_speech_fraction
from samskrita_dhvani.registry import SpdWord, build_seed_wordlist
from samskrita_dhvani.spd_scorer import (
    CALIBRATION_DEFAULT_PATH,
    Calibration,
    load_calibration,
    score_attempt,
)

AUDIO_EXTS = (".wav", ".flac", ".mp3")
VAD_MIN_SPEECH_FRACTION = 0.10  # DataIntegrity §1.1 (same as the API)
REFERENCE_EXTS = (".wav", ".flac", ".mp3")  # same order as api.spd_score

# spd_<item>_<rest>_t<take>[_var-<tag>]
_NAME_RE = re.compile(
    r"^spd_(?P<item>[A-Za-z0-9]+)_(?P<rest>.+)_t(?P<take>\d+)"
    r"(?P<variant>_var-[A-Za-z0-9-]+)?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ParsedName:
    attempt_id: str
    """Filename stem, verbatim — the NFR-10 join key."""

    item: str
    take: int
    variant: str | None
    rest: str
    """``<reciter>_<sessionid>`` (or the booth's single ``<role>``)."""


class SkipAttempt(Exception):
    """A per-file skip with a machine-readable reason."""

    def __init__(self, reason: str, detail: str):
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


def parse_attempt_name(stem: str, *, booth_style: bool = False) -> ParsedName | None:
    """Parse a RecordingProtocol §3 SPD name, or None.

    ``booth_style`` relaxes the ``<reciter>_<sessionid>`` requirement to
    the booth's single ``<role>`` segment. The item is never guessed
    here — resolution against the word list happens separately.
    """
    m = _NAME_RE.match(stem)
    if m is None:
        return None
    rest = m.group("rest")
    tokens = rest.split("_")
    if any(not tok for tok in tokens):
        return None
    if len(tokens) < (1 if booth_style else 2):
        return None
    return ParsedName(
        attempt_id=stem,
        item=m.group("item"),
        take=int(m.group("take")),
        variant=m.group("variant"),
        rest=rest,
    )


def _word_index(words: list[SpdWord]) -> tuple[dict[str, SpdWord],
                                               dict[str, list[SpdWord]]]:
    """Exact spellings first; case-folded lookup only when unambiguous.

    The word list contains case-only minimal pairs (``pAta``/``pATa``,
    ``tala``/``tAla``, ``kAka``/``kAkA``). Folding those together would
    make a lowercase filename silently pick one — a guessed word — so an
    ambiguous folded item is a skip, never a choice.
    """
    exact = {w.word_id: w for w in words}
    folded: dict[str, list[SpdWord]] = {}
    for w in words:
        folded.setdefault(w.word_id.casefold(), []).append(w)
    return exact, folded


def _resolve_word(
    item: str,
    exact: dict[str, SpdWord],
    folded: dict[str, list[SpdWord]],
) -> tuple[SpdWord | None, str | None]:
    """(word, None) or (None, reason) — never a guess."""
    if item in exact:
        return exact[item], None
    candidates = folded.get(item.casefold(), [])
    if len(candidates) == 1:
        return candidates[0], None
    if not candidates:
        return None, "unknown"
    return None, "ambiguous: " + ", ".join(sorted(w.word_id for w in candidates))


def _reference_clip(word_id: str) -> Path | None:
    """The word's verified reference clip, resolved exactly as the API."""
    for ext in REFERENCE_EXTS:
        p = api.SPD_REFERENCE_ROOT / f"{word_id}{ext}"
        if p.is_file() and p.stat().st_size > 0:
            return p
    return None


def _score_file(path: Path, word: SpdWord) -> dict:
    """Score one attempt through the API's chain; raises SkipAttempt."""
    try:
        y = load_audio_16k(str(path))
    except Exception as exc:  # noqa: BLE001 — per-file, loud skip
        raise SkipAttempt("decode_failed", f"loader refused: {exc}") from exc

    frac = vad_speech_fraction(y)
    if frac <= VAD_MIN_SPEECH_FRACTION:
        raise SkipAttempt(
            "near_silence",
            f"VAD speech fraction {frac:.3f} ≤ {VAD_MIN_SPEECH_FRACTION:.2f} "
            "(DataIntegrity §1.1)",
        )

    ref_path = _reference_clip(word.word_id)
    if ref_path is None:
        raise SkipAttempt(
            "reference_missing",
            f"no non-empty reference clip at {api.SPD_REFERENCE_ROOT}/"
            f"{word.word_id}.wav (ear check open? see SPD Open Item 2)",
        )

    calibration: Calibration | None = load_calibration(word.word_id)
    if calibration is None:
        raise SkipAttempt(
            "calibration_missing",
            f"no measured D0 for '{word.word_id}' in "
            f"{CALIBRATION_DEFAULT_PATH} — the API returns 503 here",
        )

    try:
        ref_audio = load_audio_16k(str(ref_path))
    except Exception as exc:  # noqa: BLE001 — per-file, loud skip
        raise SkipAttempt(
            "reference_unreadable",
            f"reference clip '{ref_path}' failed to load: {exc}",
        ) from exc

    try:
        result = score_attempt(
            y,
            ref_audio,
            calibration,
            {
                "word_id": word.word_id,
                "devanagari": word.devanagari,
                "iast": word.iast,
            },
        )
    except Exception as exc:  # noqa: BLE001 — per-file, loud skip
        raise SkipAttempt("axis_unmeasurable", str(exc)) from exc

    return {
        "attempt_id": path.stem,
        "reference_word": result.reference_word,
        "similarity_pct": round(result.similarity_pct, 1),
        "vowel_score": round(result.vowel_score, 1),
        "consonant_score": round(result.consonant_score, 1),
        "duration_score": round(result.duration_score, 1),
        "mfcc_dtw_score": round(result.mfcc_dtw_score, 1),
    }


def _audio_files(directory: Path) -> list[Path]:
    return sorted(
        p for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() in AUDIO_EXTS
    )


def _write_atomic(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            for line in lines:
                handle.write(line + "\n")
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def _as_run(argv: list[str]) -> str:
    return (
        "python -m samskrita_dhvani.score_attempts "
        + " ".join(shlex.quote(a) for a in argv)
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m samskrita_dhvani.score_attempts",
        description="Batch-score promoted SPD attempts (RecordingProtocol §3 "
                    "names) into a JSONL file accepted by "
                    "`python -m samskrita_dhvani.nfr10 --scores`.",
    )
    parser.add_argument("--attempts", required=True,
                        help="directory of promoted SPD attempt audio")
    parser.add_argument("--out", required=True,
                        help="JSONL output (one scored attempt per line)")
    parser.add_argument("--word-from-name", action="store_true",
                        help="also accept booth-style "
                             "spd_<item>_<role>_t<take> names (no "
                             "reciter/session segment); the word is still "
                             "read from the name, never guessed")
    parser.add_argument("--force", action="store_true",
                        help="overwrite an existing --out deliberately")
    args = parser.parse_args(argv)

    invoked = list(argv) if argv is not None else sys.argv[1:]
    attempts = Path(args.attempts)
    out = Path(args.out)

    if not attempts.is_dir():
        print(f"error: attempts directory not found: {attempts}",
              file=sys.stderr)
        return 2
    files = _audio_files(attempts)
    if not files:
        print(f"error: attempts directory has no audio files "
              f"({', '.join(AUDIO_EXTS)}): {attempts}", file=sys.stderr)
        return 2
    if out.exists() and not args.force:
        print(f"error: output file already exists: {out} (use --force to "
              "overwrite deliberately)", file=sys.stderr)
        return 2

    # ---- global prerequisites: the same honest unavailable states the API has
    try:
        wordlist = build_seed_wordlist(provenance=api.WORDLIST_PROVENANCE)
    except Exception as exc:  # noqa: BLE001 — no word list, no numbers
        print(f"error: SPD word list unavailable: {exc}", file=sys.stderr)
        return 2
    exact_words, folded_words = _word_index(wordlist.words)

    if not CALIBRATION_DEFAULT_PATH.is_file():
        print(f"error: SPD calibration unavailable: {CALIBRATION_DEFAULT_PATH} "
              "does not exist — the API reports the same 503 "
              "calibration_unavailable state; no scale, no score",
              file=sys.stderr)
        return 2

    try:
        load_excluded_paths()  # fail loudly before scoring anything
    except ExclusionRegisterError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    scored: list[dict] = []
    seen_ids: set[str] = set()
    skipped: Counter[str] = Counter()
    ignored_non_audio = 0
    for p in sorted(attempts.iterdir()):
        if not p.is_file():
            continue
        if p.suffix.lower() not in AUDIO_EXTS:
            ignored_non_audio += 1
            continue

        def skip(reason: str, detail: str) -> None:
            skipped[reason] += 1
            print(f"  ! skipped '{p.name}': {detail}", file=sys.stderr)

        parsed = parse_attempt_name(p.stem, booth_style=args.word_from_name)
        if parsed is None:
            skip("unparsed_name",
                 "does not match spd_<item>_<reciter>_<sessionid>_t<take>"
                 "[_var-*] (use --word-from-name for booth-style names)")
            continue
        word, why = _resolve_word(parsed.item, exact_words, folded_words)
        if word is None:
            if why == "unknown":
                skip("unknown_word",
                     f"'{parsed.item}' is not in the "
                     f"{len(exact_words)}-word FR-12 SPD list")
            else:
                skip("ambiguous_word",
                     f"'{parsed.item}' matches more than one word ID "
                     f"({why}); spell the filename with the registry "
                     "spelling")
            continue

        if p.stem in seen_ids:
            skip("duplicate_attempt_id",
                 f"filename stem '{p.stem}' repeats an earlier attempt")
            continue

        row = excluded_row(p)
        if row is not None:
            skip("excluded",
                 f"listed in data/EXCLUDED.csv ({row.reason}; "
                 f"{row.date}) — DataIntegrity §4")
            continue

        try:
            record = _score_file(p, word)
        except SkipAttempt as exc:
            skip(exc.reason, exc.detail)
            continue
        seen_ids.add(p.stem)  # only a scored attempt claims its ID
        scored.append(record)

    if not scored:
        print(f"error: no attempt could be scored ({sum(skipped.values())} "
              "skipped) — nothing written", file=sys.stderr)
        return 2

    try:
        _write_atomic(out, [json.dumps(s, ensure_ascii=False) for s in scored])
    except OSError as exc:
        print(f"error: could not write {out}: {exc}", file=sys.stderr)
        return 2

    print(f"scored {len(scored)}/{len(files)} attempt(s); "
          f"skipped {sum(skipped.values())}")
    if skipped:
        print("  skipped by reason: "
              + " · ".join(f"{r} {n}" for r, n in sorted(skipped.items())))
    if ignored_non_audio:
        print(f"  ignored {ignored_non_audio} non-audio file(s)")
    print(f"  output: {out} ({len(scored)} JSONL line(s), "
          f"attempt_id = filename stem verbatim)")
    print(f"as-run: {_as_run(invoked)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
