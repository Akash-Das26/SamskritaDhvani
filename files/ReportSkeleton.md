# SamskritaDhvani — Report Skeleton: Methodology & Limitations (draft)

**Status:** draft skeleton, written in the 2026-10-15 Phase 6
maintenance pass, from `Implementation.md` §2/§10, the approved D1–D5
designs (Review.md Phase 3 sign-off), and the built architecture
(Review.md Phase 4/5 units 1–10). Ground Rule 1 applies verbatim to
this document: every value below is either **MEASURED** (with the run
that produced it named) or **not yet measured** (with the exact command
or step that will produce it once real audio exists). No placeholder
here may ever be replaced with an estimate.

---

## 1. Methodology (draft)

### 1.1 Shared feature front-end (design D1 — MEASURED configuration)

Every parameter below is a named attribute of `FrontendConfig`
(`samskrita_dhvani/frontend.py`, FR-02) — the exact values the
pipeline uses, not recalled defaults:

- 16 kHz mono analysis rate (any input format resampled at load).
- Pre-emphasis 0.97.
- Framing 25 ms window / 10 ms shift (400 / 160 samples; `n_fft=512`),
  centered, tail-padded; periodic Hamming window (course Ch-3/Ch-4
  convention: overlap instead of disjoint cuts).
- 26 triangular mel filters, HTK mel scale, 0–8 kHz.
- Power spectrum → log (amin-floored) → DCT-II → **13 MFCC kept, c0
  discarded** (course `UNIT II_MFCC`: "first 12–13 cepstral values").
- Δ and ΔΔ via width-9 regression (course Ch-6) → **39-dim per frame**;
  CMVN per utterance (channel-effect reducer, Ch-6).
- Theoretical justification for the report's motivation section comes
  from `Implementation.md` §2's cited course material (cepstral
  analysis Ch-5, mel perceptual spacing, HMM/Viterbi Ch-7) — cite,
  don't re-derive.

**Front-end correctness (MEASURED):** hand-derived MFCC path vs
librosa, max-abs-difference **2.2e-7** on real resampled speech
(FR-03; run: the FR-03 cross-check tests in
`.venv/bin/python -m pytest tests/test_frontend.py`, Review.md Phase 4
unit 1 — the same-math-to-float-noise result is the pipeline's built-in
correctness evidence).

**Optional comparison features (built, FR-04):** LPCC (Durbin
recursion, p=14, Q=21, c0/gain excluded) and Praat Burg formants +
pitch sampled exactly on the MFCC frame grid (Review.md Phase 4 unit
1b). Use for ablation; no ablation result exists yet.

### 1.2 SPD scoring (design D2 — formula MEASURED, real numbers not yet measured)

- Alignment: DTW (`librosa.sequence.dtw`) over CMVN static MFCCs
  (first 13 columns of the 39-dim matrix).
- Overall score: `D` = mean over aligned frame pairs of ‖Δmfcc₁₃‖₂;
  `sim = 100 · exp(−D / D₀)` — no arbitrary constant; D = 0 maps to
  exactly 100, and a recitation at the calibration population's mean
  distance scores 100·e⁻¹ ≈ 36.8 by construction.
- `D₀` (likewise `D₀_formant`, `D₀_duration`): per-word mean distance
  of that word's known-correct recitations to its canonical reference,
  stored in `data/spd/calibration.json` (schema v1, provenance-
  carrying), rebuilt by `python -m samskrita_dhvani.calibrate`.
- Per-axis breakdown (FR-11): vowel/formant axis = mean relative
  formant mismatch over frames voiced in both clips; consonant/
  spectral axis = MFCC-DTW restricted to likely-consonant frames of
  the attempt; duration axis = |log(vad-trimmed duration ratio)|
  (symmetric in r ↔ 1/r). Each axis is normalized by its own measured
  per-word scale.

**SPD similarity numbers on real words: NOT YET MEASURED.** They
require, in order: the owner's Hall/Loyola ear-check verdict
(Review.md Open Item 3), reference clips cut and D5 calibration
recordings made, then:

```bash
python -m samskrita_dhvani.calibrate \
    --references data/spd/reference_words \
    --recitations data/spd/recitations \
    --source-id <PROVENANCE-entry> --acquired-on <YYYY-MM-DD>
# then per attempt, through the live API (or its UI):
curl -F word_id=<word_id> -F audio=@<attempt>.wav \
    http://127.0.0.1:8000/api/spd/score
```

**NFR-10 validation against human judgment: NOT YET MEASURED.** The
producing steps are: (a) D5 attempts recorded via the booth
(`python -m samskrita_dhvani.record --port 8030`); (b) each attempt
scored via `POST /api/spd/score` (command above); (c) one rater
completed sheet per instructor/native speaker using
`files/Nfr10RatingSheet.md`; (d) the correlation (Pearson and
Spearman, automated similarity vs the 1–5 rating) computed from those
two artifacts. **The correlation script does not exist yet** — by
design: it will be specified as its own Phase 3/4 unit once rated
attempts exist to build it against; until then this section reads
"not yet measured" and nothing else.

### 1.3 GVR recognition (design D3 — MEASURED topology; accuracy below)

- One HMM per verse: **6 emitting states, left-to-right, no-skip**
  (self + advance-by-one only; backward transitions disallowed —
  course Ch-7/Bakis), **diagonal-Gaussian emissions**, topology
  hand-initialized before `fit()` (hmmlearn has no L-R constructor —
  verified in Phase 2), HTK-style equal-segmentation emission init, a
  post-fit degeneracy guard that refuses NaN/dead-state models.
- Training: Baum-Welch (`fit`) on train-split rows only (non-train
  rows are structurally skipped — pinned by tests).
- Recognition: Viterbi `decode()` across all trained verse models;
  verse ID = argmax; confidence = softmax over the closed set of
  log-likelihood gaps (a wide-margin winner → near 1, a near-tie →
  near 1/n). Features are the same D1 39-dim matrix (one front-end
  for both branches, Ground Rule 4).

### 1.4 Corpus, registry, and split policy (FR-22 / FR-23 / NFR-04)

- Registry: `data/gvr_registry.json` (schema v1) built only by
  `python -m samskrita_dhvani.build_registry`, which applies nine
  per-row acceptance gates (FR-22 plan §4: D1 decode, VAD > 10%,
  duration ≥ 0.2 s, label vs checked item list, provenance keys,
  Devanagari round-trip, split/no-leak, unique audio file, level
  flags) with loud counted skips.
- Split policy (fixed in advance, FR-22 plan §3): per-reciter when
  ≥ 2 reciters (explicit `--reciter-splits`); a (verse, reciter) pair
  never spans two splits (`assert_no_split_leak`); a single-reciter
  corpus records `split_policy: per-recording` in the file itself
  (NFR-04 — the file never lies about its policy).

**The FR-23 split-policy sentence: NOT YET PRODUCED** (no registry
exists). It is printed and carried verbatim by every evaluation run
(`samskrita_dhvani/evaluate.py`):

- per-reciter corpora: *"split policy: per-reciter — each (verse,
  reciter) pair sits in exactly one split"*;
- single-reciter corpora: *"split policy: per-recording (single-reciter
  corpus) — the accuracy below is NOT speaker-independent (FR-23)."*

Plus the computed speaker-overlap note naming any test reciter who
also holds train rows.

### 1.5 Evaluation protocol (FR-23 / NFR-20)

The evaluator (`python -m samskrita_dhvani.evaluate`) scores **only
rows whose registry split is `test`** — train/validation rows are
counted for transparency and never reach `predict` (pinned by a
call-counting test); it has no training mode by design. Reported
outputs: the headline as the exact fraction `n_correct/n_test`
(percent for reading only, never alone); the confusion matrix (rows =
true verse, cols = predicted, sorted); per-verse recall + support
with `*` on single-recitation support (the data-starved marker); and
the accuracy-vs-training-examples-per-verse curve (x = that verse's
`n_training_clips` from the model envelope, y = held-out recall).

**GVR held-out accuracy: NOT YET MEASURED. Confusion matrix: NOT YET
MEASURED. Accuracy-vs-examples curve: NOT YET MEASURED.** All three
come from one command, run after the owner's D4 takes exist (via
`python -m samskrita_dhvani.d4_chain …`, which ends in exactly this):

```bash
python -m samskrita_dhvani.evaluate \
    --registry data/gvr_registry.json --model data/gvr/model.pkl \
    --json data/gvr/eval_report.json --curve-png data/gvr/eval_curve.png
```

The published report at `data/gvr/eval_report.json` is the single
source the status page mirrors (`/api/status` → `gvr_eval`); the API
never re-scores. Until the registry and model exist, the pipeline's
verified refusal (rc=2, "no registry, no number") is the only honest
output.

---

## 2. Limitations & honest trade-offs (draft — from `Implementation.md`
§10 plus the built state)

1. **Closed-set, not open-vocabulary ASR.** GVR recognizes among the
   trained verse set only; this is the declared Phase 1 scope, not a
   shortcoming to patch silently (Ground Rule 7).
2. **Small corpus, per-class HMM overfitting.** With few recitations
   per verse the per-verse HMMs will overfit; the report shows the
   accuracy-vs-examples curve and the `*` single-recitation markers
   (NFR-20) rather than one optimistic headline.
3. **Speaker independence is conditional on the corpus.** A
   single-reciter corpus can only produce a per-recording split whose
   accuracy is explicitly NOT speaker-independent — the evaluator
   prints that sentence in every report *and* every refusal. Only a
   ≥ 2-reciter registry yields the per-reciter held-out statement.
4. **No off-the-shelf Sanskrit acoustic model.** Forced alignment
   (MFA) would need a custom small dictionary; SPD therefore relies on
   whole-word DTW, not phoneme-level timing ground truth.
5. **Recording-condition variability.** Different microphones/rooms
   shift MFCC values; CMVN mitigates but does not eliminate this.
   Reference and student recordings may come from different devices
   (the booth logs device and room per session, protocol §1).
6. **"Correct pronunciation" is a judgment call** for a classical
   language with regional traditions (Vedic vs. classical
   accentuation). Every recording session states its recitation
   tradition (protocol §3.6); no tradition is presented as universally
   correct.
7. **SPD reference material is not yet pipeline-eligible.** The
   Hall/Loyola sets await the owner's ear-check verdict (Review.md
   Open Item 3); the noun-set quarantine stands until that call. All
   SPD similarity numbers are therefore not yet measured, by gate
   rather than by accident.
8. **NFR-10 is the gate on SPD's headline.** No similarity percentage
   is presented as meaningful until it correlates with
   instructor/native-speaker ratings (§1.2, `files/Nfr10RatingSheet.md`);
   the ratings cannot even be collected until D5 attempts exist.
9. **Everything above is enforced in code, not just promised.**
   Missing registry/model, zero test rows, undecodable audio,
   uncalibrated words, absent references — each is a loud rc=2/rc-path
   refusal verified in this pass (Review.md units 8–10; readiness
   check 2026-10-15).

---

*Fill rule: a section above may gain a number only by replacing its
"NOT YET MEASURED" line with the actual run output and the exact
command, logged in `Review.md` the same day (Ground Rule 1).*
