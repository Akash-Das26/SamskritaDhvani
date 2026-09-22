"""Unit tests for the registry formats (Phase 4 unit 2).

Covers FR-12 (SPD word list), FR-13 (deterministic transliteration),
and FR-22 (GVR verse registry) including the DataIntegrity Rule 2
provenance gate and the FR-23/NFR-04 split-leak enforcement. All data
here is synthetic test furniture — no corpus audio is touched.
"""

import json

import pytest

from samskrita_dhvani.registry import (
    PROVENANCE_REQUIRED_KEYS,
    SEED_SPD_WORDS,
    SpdWordlist,
    VerseEntry,
    GvrRegistry,
    build_seed_wordlist,
    devanagari_to_iast,
    harvard_kyoto_slug,
    iast_to_devanagari,
    transliteration_round_trip_ok,
)

GOOD_PROV = {"source_id": "SPD-01", "acquired_on": "2026-09-23"}


# ----------------------------------------------------- FR-13 mapping

def test_known_transliterations():
    assert devanagari_to_iast("कृष्ण") == "kṛṣṇa"
    assert devanagari_to_iast("ज्ञान") == "jñāna"
    assert iast_to_devanagari("kṣetra") == "क्षेत्र"


def test_transliteration_is_deterministic():
    for _ in (1, 2, 3):
        assert devanagari_to_iast("धर्म") == "dharma"
        assert iast_to_devanagari("śānti") == "शान्ति"


def test_round_trip_holds_for_every_seed_word():
    for iast, _axis, _pair in SEED_SPD_WORDS:
        deva = iast_to_devanagari(iast)
        assert transliteration_round_trip_ok(deva, iast), iast


def test_hk_slug_preserves_length_and_retroflex_distinctions():
    assert harvard_kyoto_slug(iast_to_devanagari("tāla")) != harvard_kyoto_slug(
        iast_to_devanagari("tala")
    )
    assert harvard_kyoto_slug(iast_to_devanagari("pāta")) != harvard_kyoto_slug(
        iast_to_devanagari("pāṭa")
    )


# ------------------------------------------------------- FR-12 list

def test_seed_list_meets_frank12_minimum():
    slugs = {harvard_kyoto_slug(iast_to_devanagari(w[0])) for w in SEED_SPD_WORDS}
    assert len(slugs) >= 20                      # FR-12: at least 20–30 words
    axes = {w[1] for w in SEED_SPD_WORDS}
    assert {
        "retroflex-dental",
        "aspirated-unaspirated",
        "vowel-length",
        "consonant-cluster",
        "control",
    } <= axes


def test_seed_difficulty_pairs_are_grouped():
    sl = build_seed_wordlist(provenance=GOOD_PROV)
    pairs = sl.difficulty_pairs
    assert all(len(members) >= 2 for members in pairs.values())
    # the minimal retroflex/dental pair is pāta/pāṭa
    assert set(pairs["t-T"]) == {"pAta", "pATa"}


def test_seed_wordlist_builds_with_unique_ids():
    sl = build_seed_wordlist(provenance=GOOD_PROV)
    ids = [w.word_id for w in sl.words]
    assert len(ids) == len(set(ids))
    assert len(sl) >= 20


def test_wordlist_json_round_trip(tmp_path):
    sl = build_seed_wordlist(provenance=GOOD_PROV, reference_audio_dir="data/spd/refs")
    p = tmp_path / "wordlist.json"
    sl.to_json(p)
    sl2 = SpdWordlist.from_json(p)
    assert len(sl2) == len(sl)
    by_id = {w.word_id: w for w in sl2.words}
    for w in sl.words:
        w2 = by_id[w.word_id]
        assert w2.devanagari == w.devanagari
        assert w2.iast == w.iast
        assert w2.difficulty_axis == w.difficulty_axis
        assert w2.reference_audio == w.reference_audio
        assert w2.provenance == w.provenance


def test_wordlist_load_rejects_missing_provenance(tmp_path):
    data = {
        "schema_version": 1,
        "kind": "spd_wordlist",
        "words": [
            {
                "word_id": "kRSNa",
                "devanagari": "कृष्ण",
                "iast": "kṛṣṇa",
                "difficulty_axis": "control",
                "pair_id": None,
                "reference_audio": None,
                "provenance": {},          # Rule 2 violation
            }
        ],
    }
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="Rule 2"):
        SpdWordlist.from_json(p)


def test_wordlist_load_rejects_failed_round_trip(tmp_path):
    data = {
        "schema_version": 1,
        "kind": "spd_wordlist",
        "words": [
            {
                "word_id": "kRSNa",
                "devanagari": "कृष्ण",
                "iast": "krisna",          # not the deterministic IAST
                "difficulty_axis": "control",
                "pair_id": None,
                "reference_audio": None,
                "provenance": dict(GOOD_PROV),
            }
        ],
    }
    p = tmp_path / "bad2.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="round trip"):
        SpdWordlist.from_json(p)


def test_wordlist_rejects_duplicate_ids():
    sl = build_seed_wordlist(provenance=GOOD_PROV)
    doubled = sl.words + [sl.words[0]]
    with pytest.raises(ValueError, match="duplicate"):
        SpdWordlist(doubled)


def test_pending_provenance_marks_ineligibility():
    sl = build_seed_wordlist()                 # no provenance given
    assert all(w.provenance["source_id"] == "PENDING" for w in sl.words)


# ------------------------------------------------------- FR-22 registry

def _entry(verse, reciter, split, fname):
    return VerseEntry(
        verse_id=verse,
        audio_file=fname,
        reciter=reciter,
        split=split,
        provenance={"source_id": "SELF-REC", "acquired_on": "2026-09-23"},
    )


def test_registry_round_trip_and_policy(tmp_path):
    reg = GvrRegistry(
        [
            _entry("2.13", "reciter-A", "train", "a1.wav"),
            _entry("2.14", "reciter-A", "train", "a2.wav"),
            _entry("2.13", "reciter-B", "test", "b1.wav"),
        ]
    )
    reg.assert_no_split_leak()
    p = tmp_path / "registry.json"
    reg.to_json(p)
    reg2 = GvrRegistry.from_json(p)
    assert len(reg2) == 3
    assert reg2.reciters_by_split()["train"] == {"reciter-A"}
    assert reg2.reciters_by_split()["test"] == {"reciter-B"}


def test_registry_allows_multiple_recitations_per_verse():
    reg = GvrRegistry(
        [
            _entry("2.13", "reciter-A", "train", "a1.wav"),
            _entry("2.13", "reciter-A", "train", "a2.wav"),   # second take
            _entry("2.13", "reciter-B", "test", "b1.wav"),    # other reciter
        ]
    )
    reg.assert_no_split_leak()                 # per-reciter policy respected


def test_registry_detects_split_leak():
    reg = GvrRegistry(
        [
            _entry("2.13", "reciter-A", "train", "a1.wav"),
            _entry("2.13", "reciter-A", "test", "a2.wav"),    # LEAK
        ]
    )
    with pytest.raises(ValueError, match="leak"):
        reg.assert_no_split_leak()


def test_registry_load_rejects_leaked_file(tmp_path):
    data = {
        "schema_version": 1,
        "kind": "gvr_registry",
        "split_policy": "per-reciter",
        "entries": [
            {
                "verse_id": "2.13",
                "audio_file": "a1.wav",
                "reciter": "reciter-A",
                "split": "train",
                "devanagari_text": None,
                "provenance": dict(GOOD_PROV),
            },
            {
                "verse_id": "2.13",
                "audio_file": "a2.wav",
                "reciter": "reciter-A",
                "split": "test",
                "devanagari_text": None,
                "provenance": dict(GOOD_PROV),
            },
        ],
    }
    p = tmp_path / "leak.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError):
        GvrRegistry.from_json(p)


def test_registry_rejects_duplicate_audio_file():
    with pytest.raises(ValueError, match="audio_file"):
        GvrRegistry(
            [_entry("2.13", "A", "train", "same.wav"),
             _entry("2.14", "A", "train", "same.wav")]
        )


def test_registry_rejects_bad_split():
    with pytest.raises(ValueError, match="split"):
        GvrRegistry([_entry("2.13", "A", "holdout", "a.wav")])


def test_registry_provenance_gate(tmp_path):
    data = {
        "schema_version": 1,
        "kind": "gvr_registry",
        "split_policy": "per-reciter",
        "entries": [
            {
                "verse_id": "2.13",
                "audio_file": "a1.wav",
                "reciter": "A",
                "split": "train",
                "devanagari_text": None,
                "provenance": {},
            }
        ],
    }
    p = tmp_path / "noprov.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="Rule 2"):
        GvrRegistry.from_json(p)


def test_required_provenance_keys_are_the_documented_minimum():
    assert set(PROVENANCE_REQUIRED_KEYS) == {"source_id", "acquired_on"}
