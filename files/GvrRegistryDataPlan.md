# FR-22 GVR Training-Data Registry Plan

**Status:** PLAN — no audio acquired under it yet; zero registry rows
today (honest state: `/api/status` reports the GVR scorer unavailable).
**Purpose:** Make GVR training startable the moment source permission
lands (or the D4 fallback is exercised) by fixing *now* what the
registry will contain, where each clip comes from, which split it
occupies, and what gates each row must pass. No code or data is
produced by this document; it is the contract the data work follows.
**Prepared:** 2026-10-01. **Governed by:** `SRS.md` FR-22/FR-23/NFR-20,
`DataIntegrity.md` (§1–§4, Rules 1–5), `RecordingProtocol.md` (D4 role
requirements), `Implementation.md` §5.1.

---

## 1. Target corpus (FR-22: "starting with one chapter")

- **Primary target:** Bhagavad Gita Chapter 2, verses 2.01–2.20
  (20 classes — the smallest set that keeps the closed-set HMM
  meaningful per Implementation.md §5.1). **Stretch:** the full 72
  verses of Chapter 2 if a source delivers them in one piece.
- **Per verse:** ≥3 recitations, spanning ≥2 reciters where possible
  (single-example-per-class HMMs overfit; that limitation gets stated
  in the report, never papered over — Ground Rule 7).
- **Text side:** `devanagari_text` (mūla) for every verse row, from a
  text source named in the provenance entry, with the FR-13 round trip
  verified at registry load.

## 2. Sources, in priority order (each with its gate)

1. **Gita Supersite (permission path).** Request email already drafted
   at `files/GitaSupersitePermissionEmail.md` — **unsent**. Ask: Ch. 2
   recitation audio for academic research use, scope of redistribution
   of derived features stated. On any response (yes/no/terms), log it
   verbatim in `files/PROVENANCE.md` as a `GVR-*` entry before any
   download. Technically scripted retrieval is blocked (PROVENANCE
   Open Item 5 notes the Cloudflare/AJAX findings) — maintainer
   contact is the only path.
2. **Named public/open recitation archives.** Only with an explicit
   license statement captured per file batch in PROVENANCE.md
   (DataIntegrity §2). No "found it on YouTube" rows, ever.
3. **D4 self-recording program (always-available fallback).** Via the
   recording booth (`python -m samskrita_dhvani.record`): named
   reciter + consent in the session sheet, tradition stated
   (RecordingProtocol §4: "no Vedic accent tradition — classical
   paṭha"), ≥3 takes per verse. The booth's capture/§1.1 gating and
   `data/_incoming/` discipline apply unchanged; verse takes get the
   RecordingProtocol §3 `gvr_c<chapter>v<verse>_<reciter>_<sid>_t<take>`
   naming. **Known small extension, its own unit:** the booth's word
   list is currently the SPD seed list — a GVR item list plugs into the
   same session/upload endpoints, nothing else changes.
- **Never mix sources silently:** every registry row carries the
  `source_id` of the PROVENANCE.md entry it came from.

## 3. Split policy (FR-23 / NFR-04) — fixed in advance

- **Per-reciter** (registry format already enforces
  `assert_no_split_leak` at load): a reciter's recordings of a verse
  all sit in the SAME split — no exceptions.
- **Initial assignment for the expected shapes:**
  - 2+ self-reciters and no external source → reciter A all-train,
    reciter B all-test; validation carved from A by take parity
    (odd takes) and recorded in the registry, not recomputed.
  - External permissioned source + 1 self-reciter → source rows =
    validation, self-reciter A = train, and test comes from a second
    self-reciter (record one before evaluating).
  - Only ONE reciter achievable → per-recording split, and every
    reported number carries the sentence "single-reciter corpus;
    accuracy is not speaker-independent" (DataIntegrity §1.4).
- The policy does not change between experiments (NFR-04); a change is
  a new Review.md entry with a reason.

## 4. Per-row acceptance gates (all must pass before the row enters `data/gvr_registry.json`)

| Gate | How checked |
|---|---|
| Decodes with the D1 loader, 16 kHz mono | `load_audio_16k` |
| Not near-silence (VAD speech fraction > 10%) | `vad_speech_fraction` (DataIntegrity §1.1) |
| Duration ≥ 0.2 s | load duration |
| Label correct (verse ID ↔ audio) | ear-check sample, §4 step 1 |
| Provenance keys present | `PROVENANCE_REQUIRED_KEYS` or `recording_session_id` (Rule 2) |
| `devanagari_text` round-trips | `transliteration_round_trip_ok` (FR-13) |
| Split ∈ {train, validation, test}, no leak | `GvrRegistry.assert_no_split_leak` |
| Unique `audio_file` | registry constructor |
| Clipping / level | §4 automated sweep (`MANIFEST`-style), not client-side |

A row failing any gate is excluded and counted — never fixed silently
(Rule 1). The first full §4 sweep over the completed registry is logged
in Review.md **before** any accuracy number is reported.

## 5. Machine steps once audio lands (exact commands)

1. Capture (D4 fallback): `python -m samskrita_dhvani.record` → booth
   session into `data/_incoming/`.
2. Promote: copy per the session's `PROMOTION.md`-style mapping into
   `data/gvr_recordings/` with protocol §3 names; register the
   PROVENANCE.md entry; ear-check the labels.
3. Build registry: a small tool (to be written as its own unit when
   the first real batch exists — not before) that emits
   `data/gvr_registry.json` with `schema_version: 1` and loads it back
   through `GvrRegistry.from_json` (which runs every load-time gate).
4. Train: `GvrRecognizer.train(registry)` on the train-split rows
   (non-train rows are skipped — behavior pinned by unit-4 tests),
   `save()` to `data/gvr/model.pkl`. `/api/status` flips
   `gvr_scorer_available` to true automatically; the GVR screen's
   "built, training data pending" chip retires.
5. Evaluate: held-out **test** split only — accuracy, confusion matrix,
   and accuracy-vs-training-examples-per-verse curve (NFR-20), with the
   exact command recorded in Review.md per Ground Rule 1. The eval
   script is a Phase 5 unit written against the real registry, not
   against fixtures.

## 6. Honesty constraints (standing)

- No synthetic fixtures in any reported number (Rule 4); synthetic
  registry fixtures exist only in unit tests.
- Until step 3 completes, the GVR branch's status stays exactly what
  it is today: scorer built, 503 `model_unavailable`, screen chip
  says data pending.
- Zero-verse state is not "hidden" anywhere: it is the reported state.

## 7. Recommended sequence

1. Send the Gita Supersite email (owner action; the draft is ready).
2. While waiting: run a D4 booth session on the 20-verse subset (the
   owner-as-reciter fallback), ~1–2 s per verse × 3 takes × 20 verses
   ≈ 20–30 min of recording.
3. Registry-build tool unit + first sweep.
4. Train + evaluate with the full NFR-20 reporting set.
