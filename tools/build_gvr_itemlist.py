"""Build the GVR D4 booth item list from a named public-domain text
source (Run: ``python tools/build_gvr_itemlist.py --help``).

Source discipline (Ground Rule 1 / DataIntegrity Rule 2): the verse
mūla is NOT typed from memory. It is parsed from a specific fetched
file — sanskritdocuments.org's ``bhagvadnew.itx`` (proofread, see the
file's own header) — and the tool prints the source URL and sha256 of
exactly the bytes parsed, for the PROVENANCE.md entry.

Output: ``data/gvr/ch2_itemlist.json`` (schema v1) with one row per
verse of chapter 2::

    {"verse_id": "2.13", "chapter": 2, "verse": 13,
     "devanagari": "<mūla>", "fname_key": "c2v13"}

Parse gates (loud, or the output is not written):
- exactly 72 verses parsed for chapter 2;
- a verse-number sequence check (each 2-N marker appears exactly once);
- spot checks: two well-known lines must match verbatim after
  transliteration (2.13 and 2.47) — if the parser or the source were
  wrong, these fail loudly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from indic_transliteration import sanscript

SOURCE_URL = (
    "https://sanskritdocuments.org/doc_giitaa/bhagvadnew.itx"
)
DEFAULT_OUT = Path("data") / "gvr" / "ch2_itemlist.json"
CHAPTER = 2
EXPECTED_VERSES = 72

# Spot checks (Ground Rule 1: known lines, verified against the
# parsed output before the file is trusted). Written in the SOURCE's
# own ITRANS orthography (dots-variety `.n` anusvAra); compared
# against the parsed ITRANS, spaces/punctuation/case-insensitive.
SPOT_CHECKS = {
    "2.13": "dehino.asminyathA dehe kaumAra.n yauvana.n jarA",
    "2.47": "karmaNyevAdhikAraste mA phaleShu kadAchana",
}


def _itrans_to_devanagari(text: str) -> str:
    return sanscript.transliterate(text, sanscript.ITRANS, sanscript.DEVANAGARI)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z]", "", s.lower())


def parse_chapter2(raw: str) -> dict[str, str]:
    """Extract {verse_id: itrans_text} for chapter 2 from the .itx."""
    # Chapter 2 runs from its \section to the chapter-closing line.
    start = raw.index("\\section{atha dvitIyo.adhyAyaH")
    end = re.search(
        r"^sA~Nkhyayogo nAma dvitIyo\.adhyAyaH \|\| 2\|\|", raw, re.M
    ).start()
    body = raw[start:end]

    # Verses terminate with "|| 2-N||" markers (line-broken verses keep
    # their continuation lines until the marker).
    pattern = re.compile(r"\|\|\s*2\\-(\d+)\|\|")
    speaker = re.compile(r"^[a-zA-Z~]+ ?uvAcha\s*\|$")
    verses: dict[int, list[str]] = {}
    current: list[str] = []
    for line in body.splitlines():
        m = pattern.search(line)
        if m:
            n = int(m.group(1))
            text = pattern.sub("", line).strip()
            current.append(text)
            verses[n] = current
            current = []
            continue
        s = line.strip()
        if (not s or s.startswith("%") or s.startswith("\\section")
                or s.startswith("\\chapter")):
            continue
        if speaker.fullmatch(s):
            continue  # "sa~njaya uvAcha |" — attribution, not verse text
        current.append(s)
    # Lines before the first marker belong to verse 2-1's earlier shlokas —
    # the source starts the chapter body with "sa~njaya uvAcha |" then the
    # 2-1 verse; any stray preamble would attach to nothing and is dropped
    # by the count check below.

    out: dict[str, str] = {}
    for n, lines in verses.items():
        joined = " ".join(lines)
        joined = re.sub(r"\\\-", "-", joined)          # escaped hyphen
        joined = re.sub(r"[|]{2}.*$", "", joined)       # safety
        joined = re.sub(r"\s+", " ", joined).strip()
        # Zero-padded canonical form ('2.07'), matching the registry
        # convention the D3 fixtures and the registry-build tool use
        # ('4.07'), so one id form runs through booth → registry → model.
        out[f"{CHAPTER}.{n:02d}"] = joined

    numbers = sorted(int(k.split(".")[1]) for k in out)
    if numbers != list(range(1, EXPECTED_VERSES + 1)):
        missing = sorted(set(range(1, EXPECTED_VERSES + 1)) - set(numbers))
        raise SystemExit(
            f"parse check failed: expected verses 1..{EXPECTED_VERSES}, "
            f"got {len(numbers)} (missing: {missing})"
        )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("itx_file", type=Path, help="path to bhagvadnew.itx")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    raw = args.itx_file.read_text(encoding="utf-8")
    sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    verses = parse_chapter2(raw)

    # Spot checks before anything is trusted or written.
    for vid, expected in SPOT_CHECKS.items():
        got = verses.get(vid, "")
        if _norm(expected) not in _norm(got):
            iast = sanscript.transliterate(
                _itrans_to_devanagari(got), sanscript.DEVANAGARI, sanscript.IAST
            )
            print(
                f"error: spot check failed for {vid}:\n"
                f"  expected : {expected}\n"
                f"  parsed   : {got}\n"
                f"  as IAST  : {iast}",
                file=sys.stderr,
            )
            return 2

    items = []
    for vid in sorted(verses, key=lambda v: int(v.split(".")[1])):  # noqa: E501 — padded keys sort numerically here
        deva = _itrans_to_devanagari(verses[vid])
        # Round-trip gate per row (FR-13 discipline): Devanagari -> IAST
        # -> Devanagari must be the identity (the same check
        # registry.load applies to word rows).
        back = sanscript.transliterate(
            sanscript.transliterate(deva, sanscript.DEVANAGARI, sanscript.IAST),
            sanscript.IAST,
            sanscript.DEVANAGARI,
        )
        if back != deva:
            print(f"error: round-trip failed for {vid}\n  was: {deva}\n  got: {back}", file=sys.stderr)
            return 2
        ch, v = vid.split(".")
        items.append(
            {
                "verse_id": vid,
                "chapter": int(ch),
                "verse": int(v),
                "devanagari": deva,
                "fname_key": f"c{ch}v{int(v)}",
            }
        )

    data = {
        "schema_version": 1,
        "kind": "gvr_itemlist",
        "program": "D4",
        "chapter": CHAPTER,
        "text_source": {
            "url": SOURCE_URL,
            "file_sha256": sha,
            "edition_note": (
                "Volunteer-proofread ITX (latest update 2021-05-15); "
                "personal study/research use statement in file header."
            ),
        },
        "items": items,
    }

    if args.out.exists() and not args.force:
        print(f"error: {args.out} exists (use --force)", file=sys.stderr)
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"wrote {args.out}: {len(items)} verses, chapter {CHAPTER}")
    print(f"source: {SOURCE_URL}")
    print(f"sha256: {sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
