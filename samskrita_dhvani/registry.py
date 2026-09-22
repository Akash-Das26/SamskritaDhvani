"""Registry formats for SPD and GVR (Phase 4 unit 2).

Scaffolding for the label/registry requirements:

- **FR-13** — deterministic Devanagari <-> IAST mapping via
  ``indic_transliteration`` (the only transliteration path allowed; the
  round trip must be the identity, and the code below enforces it).
- **FR-12** — the SPD word-list schema plus a seed list covering the
  required difficulty axes (retroflex vs. dental, aspirated vs.
  unaspirated, vowel length), with difficulty-pair grouping.
- **FR-22** — the GVR verse registry (verse ID <-> audio file mapping)
  with split policy enforcement (FR-23 / NFR-04) and the DataIntegrity
  Rule 2 provenance gate applied at load time.

Design decisions (from the Phase 3 signed-off plan and DataIntegrity.md):

- Word IDs are Harvard-Kyoto slugs (deterministic ASCII that preserves
  vowel-length and retroflex distinctions, so ``tAla`` vs ``tala`` or
  ``zAstra`` vs ``zastra`` never collide).
- Verse IDs are the canonical ``chapter.verse`` form ("2.13").
- Registry files are JSON with an explicit ``schema_version`` field so
  any later format change is detectable (Ground Rule 4).
- No registry is valid without provenance entries per item
  (DataIntegrity Rule 2): ``load_spd_wordlist`` /
  ``load_gvr_registry`` refuse files whose items lack a provenance
  key, and new items cannot be added without one.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from indic_transliteration import sanscript

__all__ = [
    "SCHEMA_VERSION",
    "devanagari_to_iast",
    "iast_to_devanagari",
    "transliteration_round_trip_ok",
    "harvard_kyoto_slug",
    "SpdWord",
    "SpdWordlist",
    "VerseEntry",
    "GvrRegistry",
    "SEED_SPD_WORDS",
    "build_seed_wordlist",
    "PROVENANCE_REQUIRED_KEYS",
]

SCHEMA_VERSION = 1

PROVENANCE_REQUIRED_KEYS = ("source_id", "acquired_on")
"""Minimum provenance fields per item (DataIntegrity Rule 2): which
PROVENANCE.md source entry (SPD-01, SPD-02, GVR-01, ...) the clip comes
from and when it was acquired. Recording-session items instead carry a
``recording_session_id`` pointing at a RecordingProtocol.md sheet."""


# --------------------------------------------------------------- FR-13

def devanagari_to_iast(text: str) -> str:
    """Deterministic Devanagari -> IAST (FR-13)."""
    return sanscript.transliterate(text, sanscript.DEVANAGARI, sanscript.IAST)


def iast_to_devanagari(text: str) -> str:
    """Deterministic IAST -> Devanagari (FR-13)."""
    return sanscript.transliterate(text, sanscript.IAST, sanscript.DEVANAGARI)


def transliteration_round_trip_ok(deva: str, iast: str) -> bool:
    """True iff IAST is the exact transliteration of ``deva`` and maps
    back to it character-for-character (the FR-13 determinism gate)."""
    return devanagari_to_iast(deva) == iast and iast_to_devanagari(iast) == deva


def harvard_kyoto_slug(deva: str) -> str:
    """Deterministic ASCII slug for word IDs (round-trip safe)."""
    return sanscript.transliterate(deva, sanscript.DEVANAGARI, sanscript.HK)


# --------------------------------------------------------------- FR-12

@dataclass
class SpdWord:
    """One SPD word-list entry (FR-12)."""

    word_id: str
    """ASCII slug (Harvard-Kyoto), unique in the list."""

    devanagari: str
    iast: str
    difficulty_axis: str
    """One of: retroflex-dental, aspirated-unaspirated, vowel-length,
    consonant-cluster, control."""

    pair_id: str | None = None
    """Difficulty-pair group the word belongs to (e.g. 'ta-Ta'), or
    None for control words."""

    reference_audio: str | None = None
    """Path to the verified reference recitation, once cut and
    listen-through-verified. None = not yet acquired."""

    provenance: dict = field(default_factory=dict)
    """Must satisfy :data:`PROVENANCE_REQUIRED_KEYS` (Rule 2)."""


def _check_provenance(item: dict, kind: str) -> None:
    if "recording_session_id" not in item and not all(
        k in item.get("provenance", {}) for k in PROVENANCE_REQUIRED_KEYS
    ):
        raise ValueError(
            f"{kind} '{item.get('word_id', item.get('verse_id', '?'))}' "
            "has no provenance (DataIntegrity Rule 2): needs "
            f"{PROVENANCE_REQUIRED_KEYS} or a recording_session_id"
        )


class SpdWordlist:
    """The SPD word list: schema-checked, provenance-gated (FR-12)."""

    def __init__(self, words: list[SpdWord]):
        ids = [w.word_id for w in words]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate word_id in word list")
        self.words = words

    def __len__(self) -> int:
        return len(self.words)

    @property
    def difficulty_pairs(self) -> dict[str, list[str]]:
        pairs: dict[str, list[str]] = {}
        for w in self.words:
            if w.pair_id:
                pairs.setdefault(w.pair_id, []).append(w.word_id)
        return pairs

    def to_json(self, path: str | Path) -> None:
        data = {
            "schema_version": SCHEMA_VERSION,
            "kind": "spd_wordlist",
            "words": [
                {
                    "word_id": w.word_id,
                    "devanagari": w.devanagari,
                    "iast": w.iast,
                    "difficulty_axis": w.difficulty_axis,
                    "pair_id": w.pair_id,
                    "reference_audio": w.reference_audio,
                    "provenance": w.provenance,
                }
                for w in self.words
            ],
        }
        Path(path).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @classmethod
    def from_json(cls, path: str | Path) -> "SpdWordlist":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {data.get('schema_version')}")
        if data.get("kind") != "spd_wordlist":
            raise ValueError("not an spd_wordlist file")
        for w in data["words"]:
            _check_provenance(w, "word")
            if not transliteration_round_trip_ok(w["devanagari"], w["iast"]):
                raise ValueError(f"word '{w['word_id']}' fails the FR-13 round trip")
        return cls(
            [
                SpdWord(
                    word_id=w["word_id"],
                    devanagari=w["devanagari"],
                    iast=w["iast"],
                    difficulty_axis=w["difficulty_axis"],
                    pair_id=w.get("pair_id"),
                    reference_audio=w.get("reference_audio"),
                    provenance=w.get("provenance", {}),
                )
                for w in data["words"]
            ]
        )


SEED_SPD_WORDS: list[tuple[str, str, str | None]] = [
    # (IAST, difficulty_axis, pair_id)
    # --- retroflex vs dental (the classic English-speaker difficulty)
    #     pairs are MINIMAL: only the retroflex/dental member differs
    ("pāta", "retroflex-dental", "t-T"),      # पात dental t
    ("pāṭa", "retroflex-dental", "t-T"),      # पाट retroflex ṭ
    ("kaṇa", "retroflex-dental", None),       # कण retroflex ṇ (exemplar)
    ("ṛṣi", "retroflex-dental", None),        # ऋषि vocalic r (exemplar)
    # --- aspirated vs unaspirated (minimal pairs)
    ("kala", "aspirated-unaspirated", "k-kh"),   # कल
    ("khala", "aspirated-unaspirated", "k-kh"),  # खल
    ("pala", "aspirated-unaspirated", "p-ph"),   # पल
    ("phala", "aspirated-unaspirated", "p-ph"),  # फल
    ("dāma", "aspirated-unaspirated", "d-dh"),   # दाम
    ("dhāma", "aspirated-unaspirated", "d-dh"),  # धाम
    # --- vowel length (minimal: only the vowel length differs)
    ("tala", "vowel-length", "a-ā"),          # तल / ताल
    ("tāla", "vowel-length", "a-ā"),
    ("kāka", "vowel-length", "a-ā"),          # काक / काका
    ("kākā", "vowel-length", "a-ā"),
    ("vāṇī", "vowel-length", None),           # वाणी long ī (exemplar)
    # --- consonant clusters (kr/jñ/kṣ — hard for learners)
    ("kṛṣṇa", "consonant-cluster", None),     # कृष्ण
    ("jñāna", "consonant-cluster", None),     # ज्ञान
    ("kṣetra", "consonant-cluster", None),    # क्षेत्र
    ("patra", "consonant-cluster", None),     # पत्र
    ("candra", "consonant-cluster", None),    # चन्द्र
    # --- control words (no target difficulty)
    ("rāma", "control", None),
    ("sītā", "control", None),
    ("yoga", "control", None),
    ("karma", "control", None),
    ("vidyā", "control", None),
    ("śānti", "control", None),
    ("vānara", "control", None),
]

for _iast in {w[0] for w in SEED_SPD_WORDS}:
    _deva = iast_to_devanagari(_iast)
    assert transliteration_round_trip_ok(_deva, _iast), _iast


def build_seed_wordlist(
    provenance: dict | None = None,
    reference_audio_dir: str | None = None,
) -> SpdWordlist:
    """Build the seed SPD word list (FR-12: 20+ words, difficulty pairs).

    ``provenance`` is applied to every word (e.g. the Hall/Loyola source
    entry once reference clips are actually cut from the swept,
    listen-through-verified recordings). Words without provenance get a
    placeholder that marks them NOT pipeline-eligible
    (``source_id: "PENDING"``) — Rule 2 gate still applies on load.
    """
    words: list[SpdWord] = []
    seen: set[str] = set()
    for iast, axis, pair_id in SEED_SPD_WORDS:
        deva = iast_to_devanagari(iast)
        slug = harvard_kyoto_slug(deva)
        if slug in seen:
            continue  # same word listed under two axes
        seen.add(slug)
        ref = None
        if reference_audio_dir:
            ref = f"{reference_audio_dir.rstrip('/')}/{slug}.wav"
        words.append(
            SpdWord(
                word_id=slug,
                devanagari=deva,
                iast=iast,
                difficulty_axis=axis,
                pair_id=pair_id,
                reference_audio=ref,
                provenance=dict(provenance or {"source_id": "PENDING", "acquired_on": "PENDING"}),
            )
        )
    return SpdWordlist(words)


# --------------------------------------------------------------- FR-22

@dataclass
class VerseEntry:
    """One GVR verse-registry row (FR-22)."""

    verse_id: str
    """Canonical 'chapter.verse' form, e.g. '2.13'."""

    audio_file: str
    """Path (repo-relative) to the verse recitation."""

    reciter: str
    """Named reciter (DataIntegrity §2)."""

    split: str
    """'train' | 'validation' | 'test' — the per-reciter policy split
    (FR-23/NFR-04)."""

    devanagari_text: str | None = None
    """Optional reference text (mūla), for label verification."""

    provenance: dict = field(default_factory=dict)
    """Must satisfy :data:`PROVENANCE_REQUIRED_KEYS` or carry a
    recording_session_id (Rule 2)."""


class GvrRegistry:
    """The GVR verse registry (FR-22) with split enforcement (FR-23)."""

    def __init__(self, entries: list[VerseEntry]):
        # verse_id is NOT unique (multiple recitations per verse are
        # wanted, Implementation.md §5.1) — audio_file is.
        files = [e.audio_file for e in entries]
        if len(files) != len(set(files)):
            raise ValueError("duplicate audio_file in registry")
        known = {"train", "validation", "test"}
        for e in entries:
            if e.split not in known:
                raise ValueError(f"verse '{e.verse_id}': bad split '{e.split}'")
        self.entries = entries

    def __len__(self) -> int:
        return len(self.entries)

    def assert_no_split_leak(self) -> None:
        """FR-23 / DataIntegrity §4 step 3: the per-reciter split policy
        means a reciter's recordings of a verse must all sit in the
        SAME split. A verse-reciter pair spanning two splits is a leak
        and invalidates any accuracy number."""
        seen: dict[tuple[str, str], str] = {}
        for e in self.entries:
            key = (e.verse_id, e.reciter)
            if key in seen and seen[key] != e.split:
                raise ValueError(
                    f"split leak: verse {e.verse_id}, reciter '{e.reciter}' "
                    f"appears in both '{seen[key]}' and '{e.split}'"
                )
            seen[key] = e.split

    def reciters_by_split(self) -> dict[str, set[str]]:
        out: dict[str, set[str]] = {"train": set(), "validation": set(), "test": set()}
        for e in self.entries:
            out[e.split].add(e.reciter)
        return out

    def to_json(self, path: str | Path) -> None:
        data = {
            "schema_version": SCHEMA_VERSION,
            "kind": "gvr_registry",
            "split_policy": "per-reciter",
            "entries": [
                {
                    "verse_id": e.verse_id,
                    "audio_file": e.audio_file,
                    "reciter": e.reciter,
                    "split": e.split,
                    "devanagari_text": e.devanagari_text,
                    "provenance": e.provenance,
                }
                for e in self.entries
            ],
        }
        Path(path).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @classmethod
    def from_json(cls, path: str | Path) -> "GvrRegistry":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {data.get('schema_version')}")
        if data.get("kind") != "gvr_registry":
            raise ValueError("not a gvr_registry file")
        entries = [
            VerseEntry(
                verse_id=d["verse_id"],
                audio_file=d["audio_file"],
                reciter=d["reciter"],
                split=d["split"],
                devanagari_text=d.get("devanagari_text"),
                provenance=d.get("provenance", {}),
            )
            for d in data["entries"]
        ]
        reg = cls(entries)
        for d in data["entries"]:
            _check_provenance(d, "verse")
        reg.assert_no_split_leak()
        return reg
