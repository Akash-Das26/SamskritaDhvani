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
3. **D4 self-recording program (available fallback — booth support
   built 2026-10-01).** Via the recording booth
   (`python -m samskrita_dhvani.record`), program D4: session ids
   `GVR-REC-…`, the 20-verse FR-22 subset served from
   `data/gvr/ch2_itemlist.json` (real mūla text — PROVENANCE.md
   GVR-TXT-01), tradition stated at session start and carried into
   every checklist row, `recitation`-role takes named
   `gvr_c<ch>v<v>_recitation_t<N>.wav`, and promotion mapping to the
   protocol §3 registry-prep names
   (`gvr_c<ch>v<vv>_<reciter>_<sid>_t<take>.wav` under
   `data/gvr_recordings/`). Named reciter + consent in the session
   sheet; ≥3 takes per verse. The capture/§1.1 gating and
   `data/_incoming/` discipline are identical to the D5 flow.
- **Never mix sources silently:** every registry row carries the
  `source_id` of the PROVENANCE.md entry it came from.

## 3. Split policy (FR-23 / NFR-04) — fixed in advance

**Corrected 2026-10-01 (registry-build unit):** the original draft of
this section assigned splits in ways that violate the leak gate the
registry actually enforces — `assert_no_split_leak` requires a
(reciter, verse) pair to sit in exactly ONE split, so carving
validation from the same reciter's takes (take parity) or splitting
one reciter's rows per-recording is a leak, not a policy. The tool
implements only what the registry can honestly hold:

- **Per-reciter** (`assert_no_split_leak` enforces it at load): a
  reciter's recordings of a verse all sit in the SAME split — no
  exceptions. With ≥2 reciters, `build_registry` requires an explicit,
  complete `--reciter-splits R=train,R=test` assignment (no guessed
  splits; an explicit single-reciter assignment is honored and the
  resulting untrainable verses are warned about).
- **Single-reciter corpora:** reciter-disjoint splits are impossible;
  all rows train and the file records `split_policy:
  "per-recording"` (explicit field on `GvrRegistry`, default
  `per-reciter`), and every reported number carries the sentence
  "single-reciter corpus; accuracy is not speaker-independent"
  (DataIntegrity §1.4).
- **Reciter-level train/validation/test hygiene:** validation and
  test each need their own reciter(s). If only two reciters exist,
  use train + test and tune nothing — do not manufacture a
  validation split out of train-reciter takes.
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
3. Build registry: `python -m samskrita_dhvani.build_registry
   --recordings data/gvr_recordings --source-id … --acquired-on …
   --recitation-tradition … [--reciter-splits R=train,R=test]` —
   built 2026-10-01: parses the protocol §3 names, applies every §4
   gate per row (loud skips, counted), attaches mūla text from the
   GVR-TXT-01 item list, assigns splits per §3 (corrected),
   self-checks through `GvrRegistry.from_json`, and writes
   `data/gvr_registry.json` (schema v1). Zero survivors → nothing
   written, rc=2.
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
   owner-as-reciter fallback — booth mode shipped 2026-10-01),
   ~10–15 s per verse × 3 takes × 20 verses ≈ 20–30 min of recording.
3. Registry-build tool unit + first sweep.
4. Train + evaluate with the full NFR-20 reporting set.
