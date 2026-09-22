# SamskritaDhvani — Implementation.md

**Project full title:** *SamskritaDhvani: A Hybrid Signal Processing
Approach to Sanskrit Phonetic Assessment and Bhagavad Gita Verse
Recognition*

**Sub-projects:**
- **SPD** — Sanskrit Pronunciation error Detection
  ("Sanskrit Pronunciation Assessment Using MFCC and Spectral Features")
- **GVR** — Bhagavad Gita Verse Recognition
  ("HMM-Based Recognition of Bhagavad Gita Shlokas Using MFCC Features")

**Purpose of this document:** This is the project-specific technical
plan for both sub-projects — architecture, software stack, and data
plan. `Development.md` defines the general phased process (Feasibility
→ Resource Gathering → Design → Coding → Testing → Maintenance) and
ground rules that govern *how* work on this plan gets done; this file
defines *what* is being built. Every technical choice below is grounded
in the course material you provided (`SVP_tar.gz`): the MFCC, LPCC,
cepstral-analysis, and HMM/pattern-matching chapters (Ch. 5–7, UNIT II)
are the theoretical basis for the pipeline, not just background
reading — the implementation is expected to match the math taught
there.

Companion documents:
- **Development.md** — general phased lifecycle + ground rules
- **SRS.md** — formal functional/non-functional requirements
- **DataIntegrity.md** — audio-corpus validity policy
- **Review.md** — running session log

---

## 1. Why two sub-projects share one plan

SPD and GVR are not independent — they share:
- The **same front-end**: pre-emphasis → framing/windowing → FFT →
  Mel filterbank → log → DCT → MFCC (+ Δ, ΔΔ), exactly as taught in
  `Ch-5` and `UNIT II_MFCC.pdf`.
- The **same corpus discipline**: both need clean, correctly labeled,
  provenance-tracked Sanskrit audio (isolated words for SPD, full
  shloka recitations for GVR).
- The **same evaluation discipline**: no result is reported unless it
  came from an actual run against real (or clearly labeled synthetic)
  data — per `Development.md` Ground Rule 1.

They differ only in the back-end task:

| | SPD | GVR |
|---|---|---|
| Unit of analysis | single word (e.g. कृष्ण) | full verse (e.g. Gita 9.26) |
| Reference | one canonical native/expert recitation per word | 700 known shlokas, each with a canonical audio/text pair |
| Method | frame-level acoustic **distance** (DTW over MFCC + formants + duration), not classification | **HMM** per phoneme/verse-unit, trained on MFCC sequences, used for **classification/recognition** |
| Output | similarity score (%) + per-phoneme/vowel/duration breakdown | verse ID (e.g. "9.26") + confidence |
| Ground truth needed | IAST reference transcription + a "correct" reference recitation | verse-to-audio label mapping for all classes used |

---

## 2. Theoretical basis (from your course material — cite, don't reinvent)

Use these directly; do not re-derive from scratch or from generic
web tutorials, since your own course notes already specify the exact
conventions your evaluator will expect:

- **Digitization & framing:** `Speech Processing L3`, `Ch-2` — sampling
  rate choice (16 kHz is standard for speech front-ends; state this
  explicitly and justify it against the Nyquist content of Sanskrit
  sibilants/aspirates), frame size (20–25 ms) and frame shift (10 ms),
  pre-emphasis coefficient (~0.95–0.97).
- **Windowing & spectral leakage:** `Ch-3`, `Ch-4` — Hamming window,
  why overlapping frames are used instead of disjoint ones (directly
  answers the "Ques" file's Q6).
- **Cepstral analysis:** `Ch-5`, `UNIT II_Cepstrum analysis.pdf` —
  why excitation and vocal-tract response can't be separated directly
  in the time domain, why log is applied before IDFT, real vs. complex
  cepstrum. This is the theoretical justification for *why MFCC works
  as a pronunciation-discriminating feature* — put this in your
  project report's motivation section, not just the code.
- **MFCC extraction:** `UNIT II_MFCC.pdf`, `Ch-5` — Mel filterbank
  design (typically 20–26 filters, 12–13 cepstral coefficients kept),
  liftering, and why Mel spacing matters (matches perceptual pitch
  sensitivity — directly answers the "Ques" file's Q1).
- **LPCC (optional comparison feature):** `UNIT II_LPCC.pdf` — useful as
  an ablation/comparison feature set for SPD, since the project brief
  explicitly lists "spectral differences" as an axis students should
  investigate.
- **Dynamic features & normalization:** `Ch-6` — Δ and ΔΔ coefficients,
  Cepstral Mean (and Variance) Normalization (CMN/CMVN) — needed before
  cross-speaker/cross-recording comparison in both SPD and GVR, since
  raw MFCC is sensitive to channel/recording conditions.
- **Pattern matching & HMM:** `Ch-7` — this chapter is the direct
  specification for GVR's back-end: state topology (left-to-right,
  no-skip is standard for speech), number of states per unit, Gaussian
  vs. GMM emission distributions, Viterbi decoding for recognition,
  Baum-Welch for training.

---

## 3. System Architecture

```
                         ┌─────────────────────────┐
                         │   Raw Audio Ingestion    │
                         │ (mic recording / corpus  │
                         │  files, WAV, 16 kHz mono)│
                         └────────────┬─────────────┘
                                      │
                         ┌────────────▼─────────────┐
                         │   Preprocessing Layer      │
                         │ - resample to 16kHz mono   │
                         │ - VAD / silence trimming   │
                         │ - pre-emphasis             │
                         └────────────┬───────────────┘
                                      │
                         ┌────────────▼───────────────┐
                         │  Shared Feature Extraction   │
                         │ - framing + Hamming window   │
                         │ - FFT → Mel filterbank → DCT │
                         │ - MFCC (13) + Δ + ΔΔ         │
                         │ - CMVN                        │
                         │ - (optional) LPCC, formants,  │
                         │   pitch/F0, duration           │
                         └───────┬───────────────┬───────┘
                                 │               │
                 ┌───────────────▼───┐   ┌───────▼────────────────┐
                 │   SPD branch        │   │   GVR branch            │
                 │ Reference-vs-student│   │ Feature seq → per-verse  │
                 │ MFCC alignment (DTW)│   │ HMM (hmmlearn/HTK-style) │
                 │ + per-phoneme /     │   │ Viterbi decode → verse ID│
                 │ vowel / duration    │   │ + confidence             │
                 │ scoring              │   └───────┬─────────────────┘
                 └───────┬─────────────┘             │
                         │                            │
             ┌───────────▼────────────────────────────▼───────────┐
             │                 Reporting / UI Layer                  │
             │  - similarity % + breakdown (SPD)                     │
             │  - recognized verse + confidence (GVR)                 │
             │  - (optional) Streamlit dashboard for demo             │
             └─────────────────────────────────────────────────────┘
```

Both branches sit on the **same feature-extraction module** — build it
once, unit-test it once, and reuse it. One place where correctness is
enforced, not duplicated per sub-project.

---

## 4. Software Stack — recommended, with rationale

Principle (same as `Development.md` Phase 1's dependency-weight rule):
prefer well-maintained, widely used libraries over hand-rolled DSP where
a correct implementation already exists, but **implement MFCC extraction
by hand at least once** as a learning/verification exercise, then use a
library version for the actual pipeline and cross-check the two agree
(this doubles as a built-in correctness test).

| Purpose | Recommended | Why |
|---|---|---|
| Core language | Python 3.10+ | Standard for speech/ML prototyping |
| Audio I/O & DSP | `librosa`, `soundfile`, `numpy`, `scipy` | Industry-standard, well-documented MFCC/STFT/mel-filterbank implementations you can cross-check your manual implementation against |
| Voice activity detection | `webrtcvad` or `silero-vad` | Needed to trim leading/trailing silence before feature extraction — silence frames otherwise corrupt DTW alignment and HMM training |
| Alternative/verification feature sets | `python_speech_features` (classic LPCC/MFCC reference), `praat-parselmouth` (imports as `parselmouth`; the bare PyPI name installs a broken unrelated package — see `requirements.txt`) (Praat bindings, for formants/pitch — directly supports the "vowel differences," "spectral differences" axes named in your brief) | Cross-validates your own MFCC/LPCC code; Praat is the de facto standard for phonetic formant analysis |
| DTW (for SPD) | `fastdtw` or `dtaidistance` | Standard, fast DTW implementations for aligning reference vs. student MFCC sequences of different lengths |
| HMM (for GVR) | `hmmlearn` (Gaussian/GMM-HMM, pure Python, easiest to instrument for a course project) — mention **HTK** or **Kaldi** in your report as the "production-grade" alternative even if you don't deploy on them, since `Ch-7` and the question bank likely expect you to know both | `hmmlearn` is the most approachable correct HMM implementation for a student project; Kaldi/HTK are the historical/production standard worth citing for depth marks |
| Forced alignment (optional, strengthens SPD) | Montreal Forced Aligner (MFA) — if a Sanskrit acoustic model isn't available, use it in G2P-free mode on a small custom dictionary, or skip and rely on whole-word DTW | Gives phoneme-level timing ground truth, which upgrades SPD from "one whole-word score" to genuine per-phoneme diagnostics |
| Transliteration / reference text handling | `indic_transliteration` (Python) for Devanagari ⇄ IAST | You need a deterministic, reproducible Devanagari→IAST mapping so "कृष्ण" and "kṛṣṇa" are never manually and inconsistently matched |
| Visualization / demo UI | `Streamlit` | Good fit for a live "record → get score" demo |
| Testing | `pytest` | One behavior per test |
| Packaging | `requirements.txt`, pinned versions, `venv` | Reproducible environment |

**Explicitly deferred / not needed for a course-scale project:** full
Kaldi toolchain setup, GPU-based end-to-end ASR (wav2vec2/Whisper
fine-tuning) — these are valid "future work" mentions in your report but
are heavy, hard-to-justify dependencies for a project whose grading
criteria are almost certainly about *correct classical DSP/HMM
implementation*, not state-of-the-art deep ASR. Naming this trade-off
explicitly in your report is itself good practice (`Development.md`
Ground Rule 7).

---

## 5. Data Plan

### 5.1 What data each sub-project needs

**SPD:**
- A word list (start small: 20–30 Sanskrit words with known
  pronunciation difficulty — retroflex vs. dental consonants, aspirated
  vs. unaspirated, vowel length, e.g. कृष्ण, धर्म, ज्ञान, क्षेत्र).
- One **reference recitation per word** — ideally from a fluent
  Sanskrit speaker or a verified pronunciation source (e.g. Vedic
  chanting archives, university Sanskrit department recordings, or a
  cooperating faculty member) — never a machine-TTS voice presented as
  "correct," since that would defeat the purpose of teaching correct
  pronunciation.
- Multiple **student/learner recitations per word**, including
  deliberately mispronounced variants (krishna/kishna/krisna for कृष्ण)
  to validate that the similarity score actually separates correct from
  incorrect.

**GVR:**
- Audio + text pairs for a subset of Bhagavad Gita shlokas — start with
  one chapter (e.g. Chapter 2 or 9, ~20–70 verses) before attempting all
  ~700, since HMM training needs enough repetitions per class to be
  meaningful.
- Multiple recitations per verse if possible (different reciters/takes)
  — a single-example-per-class HMM will overfit and the report should
  say so explicitly rather than presenting inflated accuracy.
- A clean verse-ID ↔ audio-file mapping (a speech-domain registry).

### 5.2 Sourcing (provenance discipline)

Every audio file must be traceable to one of:
- A named public/open Sanskrit audio corpus or Vedic chanting archive
  (cite the exact source and license),
- A recording you made yourself with a named, consenting reciter
  (log reciter, date, device, room conditions),
- A recording from a cooperating faculty/department (log who provided
  it and under what permission).

**No unattributed audio.** If you cannot state where a clip came from,
it does not go in the corpus — see `DataIntegrity.md` Rule 2.

### 5.3 Data validity rules

See `DataIntegrity.md` §1 and §5.3 for the full policy. In summary,
audio is only valid if it's real/openable/non-silent, correctly
labeled, provenance-tracked, non-leaking across splits, and never a
synthetic stand-in presented as real.

---

## 6. Development Phases — how `Development.md` applies here

`Development.md` defines the six phases and ground rules in general.
Applied specifically to this project:

- **Phase 1:** Scope SPD as a *diagnostic scoring tool* and GVR as a
  *closed-set classifier* (not open-vocabulary ASR); this is the
  explicit, stated trade-off (`Development.md` Ground Rule 7).
- **Phase 2:** Confirm exact library versions and their MFCC/HMM
  implementation defaults before designing around assumed behavior;
  confirm what audio you can actually obtain before finalizing word
  list / verse subset size.
- **Phase 3:** Specify feature vector shape (e.g. 13 MFCC + 13 Δ + 13
  ΔΔ = 39-dim per frame), frame rate, and normalization method; specify
  SPD's scoring formula precisely; specify GVR's HMM topology and
  train/test split policy.
- **Phase 4:** Build the shared feature-extraction module first, with
  its own unit tests, before either branch; keep SPD and GVR as
  separate modules.
- **Phase 5:** See §8 below for exact evaluation metrics and what
  counts as a real (not fabricated) result.
- **Phase 6:** Re-run the Data Integrity Sweep (`DataIntegrity.md` §4)
  whenever the corpus changes materially.

---

## 7. Data Integrity Sweep

Full procedure and sweep table format are defined in
`DataIntegrity.md` §4 — run it before any reported result.

---

## 8. Evaluation Metrics & Success Criteria

**SPD:**
- Primary: similarity % per attempt, with a per-axis breakdown
  (vowel-formant distance, consonant/spectral distance, duration
  ratio, overall MFCC-DTW distance) — this directly satisfies the
  brief's "students can investigate: vowel/consonant/duration/
  spectral/MFCC differences."
- Validation: correlation between your automated score and a human
  (instructor/native-speaker) rating on the same set of attempts —
  report this correlation as your main validity evidence, since
  "78% similarity" is meaningless without showing it tracks human
  judgment.

**GVR:**
- Primary: closed-set recognition accuracy on a held-out test split
  (report the exact split policy).
- Secondary: confusion matrix (which verses get confused with which —
  often verses sharing a first line/meter), and accuracy vs. number of
  training examples per verse (to honestly show where the HMM is
  data-starved).

---

## 9. Requirements, Data Policy, and Logging

The full formal requirement IDs live in `SRS.md`; the full audio
validity policy lives in `DataIntegrity.md`; the running session log
lives in `Review.md`. All three are companion files to this one — do
not duplicate their content here, keep this file as the architecture/
stack/data-plan reference and let those three own their respective
concerns (requirements, data policy, log).

---

## 10. Risks & Honest Trade-offs (state these in your report, don't hide them)

1. **Small corpus, per-class HMMs.** With few recitations per verse,
   GVR's HMMs will overfit; state this and show the accuracy-vs-data
   curve rather than a single optimistic number.
2. **No Sanskrit-specific acoustic model exists off-the-shelf.** Forced
   alignment (MFA) may need a custom, small pronunciation dictionary —
   budget time for this or fall back to whole-word DTW for SPD without
   phoneme-level timing.
3. **Recording condition variability.** Different microphones/rooms
   shift MFCC values; CMVN mitigates but does not eliminate this — note
   it as a limitation, especially if reference and student recordings
   come from different devices.
4. **"Correct pronunciation" is itself a judgment call** for a
   classical language with regional recitation traditions (e.g. Vedic
   vs. classical Sanskrit accentuation) — state which tradition your
   reference recitations follow rather than presenting one as
   universally "correct."

---

*This document should be updated whenever a Phase 3 (Design) decision
in `Development.md`'s process changes scope, and cross-referenced from
`Review.md` the same way `SRS.md` and `DataIntegrity.md` cross-reference
each other.*
