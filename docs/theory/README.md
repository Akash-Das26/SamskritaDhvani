# Theory reference set — extracted from the SVP course material

**What this is:** the permanent, citation-backed subset of the original
`SVP/` course dump (22 files, 31 MB). Every file here is directly cited
by `Implementation.md` §2 ("Theoretical basis — cite, don't reinvent")
or answers a question from the course Ques file that §2 explicitly
references. Extracted 2026-09-24 (Development.md Phase 6); each copy
verified byte-identical (10/10 PDFs via `cmp`; `Ques` via sha256
against git history). Nothing in here was modified.

**The governing rule** (Implementation.md §2): match this course's
math and terminology — do not substitute generic tutorial conventions.

## Citation map (file → what Implementation.md §2 uses it for)

| File | §2 citation | Grounds |
|---|---|---|
| `Ch-2 Digital Representation of Speech Signals.pdf` | "Digitization & framing" | sampling-rate choice (16 kHz, Nyquist vs. Sanskrit sibilants/aspirates), 20–25 ms frames, 10 ms shift, pre-emphasis ≈ 0.95–0.97 |
| `Ch-3 Time Frequency Analysis of Speech Signals.pdf` | "Windowing & spectral leakage" | Hamming window, spectral leakage |
| `Ch-4 Frequency Analysis of Speech Signals.pdf` | "Windowing & spectral leakage" | why overlapping frames instead of disjoint ones (with `Ques` Q6) |
| `Ch-5 Feature extraction overview, Real Cepstrum, Cepstral analysis, MFCC and LPCC.pdf` | "Cepstral analysis" + "MFCC extraction" | why excitation/tract can't be separated in time domain; log before IDFT; real vs. complex cepstrum; Mel filterbank design (20–26 filters, 12–13 coefficients), liftering |
| `UNIT II_Cepstrum analysis.pdf` | "Cepstral analysis" | same as Ch-5 cepstrum (the UNIT II statement of it) |
| `UNIT II_MFCC.pdf` | "MFCC extraction" | D1 front-end's exact conventions; with `Ques` Q1 (Mel spacing ≈ perceptual pitch sensitivity) |
| `UNIT II_LPCC.pdf` | "LPCC (optional comparison feature)" | FR-04 ablation path; Durbin/recursion conventions implemented in `samskrita_dhvani/frontend.py::lpcc` |
| `Ch-6 Dynamic Features and Normalization, Vector Quantization.pdf` | "Dynamic features & normalization" | Δ/ΔΔ regression; CMN/CMVN before cross-speaker comparison |
| `Ch-7 Pattern Matching and HMM based Speech Recognition.pdf` | "Pattern matching & HMM" | GVR back-end spec: left-to-right no-skip topology, states/unit, Gaussian vs. GMM emissions, Viterbi decoding, Baum-Welch training |
| `Speech Processing L3 - Speech Signal Representation - Digitization.pdf` | "Digitization & framing" | same as Ch-2 digitization (lecture statement) |
| `Ques` | cited at §2 lines 71 & 81 | **Q6** — "Why overlapping windows are used instead of clear cut windows?"; **Q1** — "MFCC represent the power spectrum … based on how the human ear actually perceives sound". True/False justification. Q1/Q6 numbering is *this* file's, not the question bank's. |

## Where the math landed in code (traceability)

- **D1 front-end** (`samskrita_dhvani/frontend.py`): framing/windowing/
  mel/DCT conventions → Ch-2, Ch-5, UNIT II_MFCC; Δ/ΔΔ + CMVN → Ch-6;
  verified against librosa to 2.2e-7 (FR-03, Review.md Phase 4 unit 1).
- **LPCC** (`frontend.py::lpcc`): UNIT II_LPCC (autocorrelation →
  Durbin → recursive cepstral conversion, Q ≈ 3/2·p) — Review.md unit 1b.
- **GVR back-end (pending, design D3)**: Ch-7 is the direct spec.

## Provenance

- Source: course material originally provided as `SVP_tar.gz`
  (Autumn 2026 "Speech and Video Processing", CS30033).
- These copies are **reference-only course material** — instructor-
  provided teaching documents, not for redistribution.
