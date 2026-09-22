# SamskritaDhvani — SRS.md

**Project full title:** *SamskritaDhvani: A Hybrid Signal Processing
Approach to Sanskrit Phonetic Assessment and Bhagavad Gita Verse
Recognition*

**Purpose:** Formal functional and non-functional requirements for the
SamskritaDhvani project (SPD — Sanskrit Pronunciation error Detection,
and GVR — Bhagavad Gita Verse Recognition). `Implementation.md` is the
technical detail behind these requirement IDs; `Development.md` is the
process by which they get built and verified. If a rule in either
changes, update the corresponding requirement here too, and vice versa.

Status column values: **Open** (not yet designed/built), **In Design**,
**In Progress**, **Done** (built + tested, with a `Review.md` entry
proving it), **Deferred** (explicitly postponed, with a reason).

---

## 1. Shared Front-End Requirements

| ID | Requirement | Notes | Status |
|---|---|---|---|
| **FR-01** | Provide a single shared feature-extraction module covering: resampling to 16 kHz mono, VAD/silence trimming, pre-emphasis, framing (20–25 ms, 10 ms shift), Hamming windowing, FFT, Mel filterbank, log, DCT → MFCC, Δ and ΔΔ coefficients, and CMVN normalization. | Must be usable identically by both SPD and GVR — no per-branch duplication. See `Implementation.md` §3–4. | **Done** (Review.md, Phase 4 unit 1, 2026-09-23) |
| **FR-02** | The feature extractor must expose its exact configuration (sample rate, frame size/shift, number of mel filters, number of cepstral coefficients kept, window type) as named, documented parameters — not hardcoded magic numbers. | Needed so the methodology section of the report can state exact values. | **Done** (FrontendConfig frozen dataclass; Review.md, Phase 4 unit 1) |
| **FR-03** | At least one hand-derived MFCC implementation must exist and be cross-checked against a library implementation (`librosa` or `python_speech_features`) on the same input, with the numerical difference reported. | Serves as both a learning exercise and a built-in correctness test. See `Implementation.md` §4. | **Done** (max-abs-diff 2.2e-7 on real audio; Review.md, Phase 4 unit 1) |
| **FR-04** | Provide an optional LPCC and/or formant/pitch (Praat/`parselmouth`) extraction path for ablation/comparison, since the project brief names "spectral differences" as an axis to investigate. | Optional but recommended for SPD depth. | **Done** (lpcc + formants_pitch, both course-convention; Review.md Phase 4 unit 1b, 29 tests green) |

## 2. SPD (Sanskrit Pronunciation error Detection) Requirements

| ID | Requirement | Notes | Status |
|---|---|---|---|
| **FR-10** | Given a reference recitation and a student recitation of the same word, compute a DTW alignment over their MFCC (+Δ/ΔΔ) sequences and derive an overall similarity score, explicitly normalized to a stated 0–100% range with a documented formula. | "Should be lower for wrong pronunciation" is not sufficient — the exact mapping from DTW distance to % must be written down. | Open |
| **FR-11** | Provide a per-axis breakdown of the score: vowel/formant distance, consonant/spectral distance, duration ratio, and overall MFCC-DTW distance. | Directly required by the project brief ("students can investigate vowel/consonant/duration/spectral/MFCC differences"). | Open |
| **FR-12** | Support a word list of at least 20–30 Sanskrit words including known difficulty pairs (retroflex vs. dental, aspirated vs. unaspirated, vowel length), each with a Devanagari form, an IAST transliteration, and a verified reference recitation. | See `Implementation.md` §5.1. | Partially — 29-word seed list + format/validations done (Review.md Phase 4 unit 2); reference-recitation column pending Hall/Loyola ear check (Open Item 2) |
| **FR-13** | Use a deterministic Devanagari ⇄ IAST transliteration mapping (e.g. via `indic_transliteration`) rather than manual, inconsistent matching. | Deterministic label mapping, avoids ad hoc matching. | **Done** (registry.py; round-trip identity enforced on every load; Review.md Phase 4 unit 2, 20 registry tests) |
| **NFR-10** | Validate SPD's score against human judgment: report the correlation between automated similarity scores and instructor/native-speaker ratings on the same attempts. | This is the primary validity evidence for SPD — required before any similarity number is presented as meaningful. | Open |

## 3. GVR (Bhagavad Gita Verse Recognition) Requirements

| ID | Requirement | Notes | Status |
|---|---|---|---|
| **FR-20** | Train one HMM per verse (or per verse-unit, if phoneme-level modeling is chosen in Design) on MFCC feature sequences, using a left-to-right, no-skip topology, per `Ch-7`'s conventions. | State the number of states and emission model (Gaussian vs. GMM) explicitly. | Open |
| **FR-21** | Recognize an input recitation's verse ID via Viterbi decoding across all trained verse HMMs, returning the top match and a confidence value. | | Open |
| **FR-22** | Maintain a clean verse-ID ↔ audio-file registry, starting with one chapter (~20–70 verses) before scaling toward the full ~700. | See `Implementation.md` §5.1. | Partially — `GvrRegistry` format + per-reciter split-leak enforcement done (Review.md Phase 4 unit 2); zero entries until the permission path (Open Item 5) or D4 self-recordings |
| **FR-23** | Report recognition accuracy only on a held-out test split, never on training data, and state explicitly whether the split is per-recording or per-reciter. | See `DataIntegrity.md` §5.3(4) and `Implementation.md` §8. | Open |
| **NFR-20** | Report a confusion matrix and accuracy-vs-training-examples-per-verse curve alongside the headline accuracy number, to honestly represent data-starved classes. | Prevents an inflated single-number headline result. | Open |

## 4. Non-Functional Requirements (project-wide)

| ID | Requirement | Notes | Status |
|---|---|---|---|
| **NFR-01** | No accuracy, similarity, or correlation number is reported unless it came from an actual run against real, provenance-tracked audio, with the exact command/script used to produce it. | Direct carry-over of `Development.md` Ground Rule 1. | Open |
| **NFR-02** | Any use of synthetic/placeholder audio (silence, tone fixtures) is confined to pipeline unit tests and never appears in a reported accuracy/similarity result. | | Open |
| **NFR-03** | Every audio file used in training or evaluation has a traceable provenance entry (source/recording details) before it is added to either corpus. | See `DataIntegrity.md` §5.2. | Open |
| **NFR-04** | Corpus split policy (train/val/test, per-recording or per-reciter) is documented and does not change silently between experiments. | See `DataIntegrity.md` §5.3(4). | Open |
| **NFR-05** | Known trade-offs (out-of-scope open-vocabulary ASR, small-corpus HMM overfitting risk, recording-condition variability, choice of recitation tradition) are stated explicitly in the project report, not silently patched or hidden. | See `Implementation.md` §10. | Open |

---

## 5. Traceability

| Requirement group | Implementation.md section | DataIntegrity.md section | Development.md phase |
|---|---|---|---|
| FR-01 – FR-04 (front-end) | §3, §4 | §5.3 | Phase 2, 4 |
| FR-10 – FR-13, NFR-10 (SPD) | §5.1, §8 | §5.2, §5.3 | Phase 3, 5 |
| FR-20 – FR-23, NFR-20 (GVR) | §5.1, §8 | §5.2, §5.3, §7 | Phase 3, 5 |
| NFR-01 – NFR-05 | §6, §10 | §5.3, §7 | Phase 1, 6 |

---

*Update this file whenever `Development.md`'s Phase 3 (Design) finalizes
a decision that changes a requirement's scope, and update the Status
column only when a `Review.md` entry actually verifies it — not when
work merely starts.*
