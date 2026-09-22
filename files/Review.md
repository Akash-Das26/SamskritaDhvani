# SamskritaDhvani — Review.md

**Project full title:** *SamskritaDhvani: A Hybrid Signal Processing
Approach to Sanskrit Phonetic Assessment and Bhagavad Gita Verse
Recognition*

Running log of verification work, changes made, and open items.
Pairs with `Development.md` (the phased process this log tracks
against), `Implementation.md` (the technical plan), `SRS.md` (the
requirements being verified), and `DataIntegrity.md` (the audio-validity
policy checked in the "Data Integrity Sweep" entries below).

Format per entry: **Date · Phase · What was checked/changed · Actual
result (command + output) · Open items.** Nothing goes in the "result"
column unless it was actually run in this session
(`Development.md` Ground Rule 1: no fabricated numbers).

---

## Session: 2026-09-22

### Phase 1 (Feasibility) —

**What was done:**
- _(fill in: scope confirmed for SPD/GVR, effort/impact estimate,
  trade-offs named)_

**Verdict:** go / no-go / needs more information

### Phase 2 (Resource Gathering) — shared feature-extraction module [prior session]

**What was done (every claim verified in this session by an actual
command run, code inspection, or live API/page fetch — none recalled):**

1. **Repo/corpus state.** `find` over the repo (`.venv` excluded): no
   Python source, no tests, no `requirements.txt`, and **zero audio
   files** anywhere. The shared front-end, SPD, and GVR modules do not
   exist yet — this Phase 2 establishes ground truth for the first
   build rather than reviewing existing modules. All SRS statuses
   remain Open (unchanged, per SRS.md's update rule).

2. **Environment (fresh `.venv`, Python 3.14.4).** Installed and
   import/smoke-tested:
   `numpy 2.5.3, scipy 1.18.1, soundfile 0.14.0, librosa 1.0.0
   (numba 0.67.0), hmmlearn 0.3.3, praat-parselmouth 0.4.7,
   python_speech_features 0.6, indic_transliteration 2.3.82,
   dtaidistance 2.5.1, fastdtw 0.3.4, webrtcvad 2.0.10, pytest 9.1.1`;
   `setuptools` held at `80.10.2 (<81)`.
   - **Trap found:** `pip install parselmouth` fails on this Python —
     its dependency graph pulls `googleads`, which cannot build. The
     Praat binding is published as **`praat-parselmouth`**
     (imports as `parselmouth`). Recorded in `requirements.txt`.
   - `webrtcvad` imports `pkg_resources` → setuptools must stay <81
     (pinned); smoke test on a 16 kHz int16 PCM frame passed.
   - **librosa defaults ≠ course spec** (verified via
     `inspect.signature` + a run on 1 s @16 kHz): `sr=22050`,
     `n_mfcc=20`, `n_mels=128`, `mel norm='slaney'`, `htk=False`,
     `lifter=0`, implicit `n_fft=2048/hop=512` → ~32 frames/s. Course
     (`UNIT II_MFCC`, Ch-5): 8/16 kHz sampling, Hamming window,
     triangular Mel bank, log, IDFT, **12–13 cepstral coefficients
     kept**. ⇒ FR-02's explicit-parameter mandate is confirmed
     necessary; every parameter will be set explicitly, none inherited.
   - **hmmlearn 0.3.3** `GaussianHMM` defaults verified:
     `n_components=1, covariance_type='diag', min_covar=1e-3,
     n_iter=10, tol=1e-2, algorithm='viterbi', implementation='log',
     init_params='stmc'` (random init). **No left-to-right constructor
     exists** → L-R/no-skip topology must be hand-initialized before
     `fit` (matters for FR-20); Viterbi `decode()` confirmed available.
   - **praat-parselmouth 0.4.7**: `Sound` from ndarray @16 kHz,
     `to_pitch()`, and `To Formant (burg)` via `praat.call` — smoke
     test passed (pitch frames + formant object produced).
   - `librosa.sequence.dtw` available ⇒ SPD alignment needs **no
     additional dependency**.
   - Course PDFs (Ch-5/6/7, UNIT II_MFCC) extracted with `pdftotext`
     and read (see item 3).

3. **Course-convention ground truth** (from the extracted PDF text):
   - `UNIT II_MFCC` / Ch-5: 8 or 16 kHz; pre-emphasis; Hamming
     windowing; power spectrum → triangular Mel filterbank → log →
     IDFT; "MFCC just takes the first 12 cepstral values" (12–13 per
     frame).
   - Ch-6: Δ/ΔΔ equations; CMN (cepstral mean normalization) as the
     channel-effect reducer, distinct from generic mean normalization.
   - Ch-7: left-to-right (Bakis) HMM with **backward transitions
     disallowed** in the basic configuration; standard phoneme model =
     **3 emitting states** (onset/steady/offset); word/verse models as
     concatenations; Viterbi decoding for recognition; Baum-Welch (EM)
     training; Gaussian **or** GMM emissions. DTW is the course's
     template/distance-based alternative — matching SPD's design.
   ⇒ Phase 3 design must match these conventions, not generic
   tutorials.

4. **Audio availability** (license/provenance checked via live
   fetches, per `DataIntegrity.md` Rule 2):
   - **Kathbath** (`ai4bharat/Kathbath`, Hugging Face): **CC BY-4.0**
     (verified via HF dataset API); Sanskrit config exists with a
     `speaker_id` field (enables per-reciter splits, FR-23/NFR-04);
     gated="auto" (instant acceptance). Suitable for SPD-side read
     speech; exact Sanskrit sample count to be confirmed at download.
   - **Vedavani** (`sanganaka/Vedavani-Dataset`, HF): **Apache-2.0**
     (verified via HF API); Vedic Sanskrit chanting (Rig/Atharva
     Veda), ~24.6k/3.1k/3.1k verse-unit splits, per-verse WAVs,
     ~5.4 GB. **Not Gita content** — usable for GVR only if the text
     scope is explicitly changed (Ground Rule 7 decision; not assumed).
   - **Vāksañcayaḥ** (IIT Bombay, cse.iitb.ac.in/~asr): 78 h Sanskrit,
     22 kHz; **CC BY-NC 4.0 + download form**. Usable for this
     academic project with attribution; procurement friction (form).
   - **Gita-specific audio:** archive.org items exist (T S Ranganathan
     chapter-wise tracks; "BHAGAVAD GITA SANSKRIT BY ANURADHA
     PAUDWAL") but **both lack license metadata** (`licenseurl` absent
     — verified via the archive.org metadata API) → cannot enter the
     corpus per `DataIntegrity.md` Rule 2 without explicit permission.
     A license-filtered archive.org search (`licenseurl:[* TO *]`)
     returned **no verse-wise Sanskrit Gita audio with a reuse
     license**; LibriVox's Gita recordings are English translations
     (PD, wrong language); streaming/app sources have unknown rights →
     excluded.
   - **Verdict:** no license-cleared, verse-labeled Gita audio was
     found this session. The GVR corpus must come from (a) a
     self-recording program with named consenting reciters, (b)
     cooperating faculty/department recordings, or (c) an explicit,
     logged scope change to another verse corpus (e.g. Vedavani). SPD
     reference recitations face the same sourcing decision; Kathbath
     (CC BY-4.0) covers learner-side/read-speech material.

**Open items carried forward:** GVR audio-source decision + verse
subset size (queued for Phase 3 sign-off); SPD word list (20–30 words,
difficulty pairs) + reference-recitation sourcing (Phase 3);
`PROVENANCE.md` creation at first ingest; first Data Integrity Sweep
after first ingest; recitation tradition recorded per reference
(`DataIntegrity.md` §3.6).

### Phase 3 (Design) — shared front-end, SPD scorer, GVR classifier

**What was decided** (drafted from Phase 2 findings; signed off by the
project owner in this session — all three core decisions approved as
drafted):

**D1 · Shared front-end (approved).** 16 kHz mono → pre-emphasis 0.97 →
framing 25 ms / 10 ms shift (`n_fft=512`, `hop=160`) → Hamming window →
26-triangle Mel filterbank (0–8 kHz) → log → DCT-II → **13 MFCC kept**
(c0 discarded, per the course's "first 12–13" convention) → Δ + ΔΔ →
CMVN per utterance. Output per clip: **39 × T** float matrix. Every
parameter passed explicitly (FR-02); no librosa default inherited.
*Breaking-change surface:* any change to this shape/normalization is a
flagged breaking change to both branches (Ground Rule 4).

**D2 · SPD scoring formula (approved).** With CMVN-normalized MFCC+Δ+ΔΔ
and DTW alignment (librosa.sequence.dtw) between student and reference:

```
D   = mean over aligned frame pairs of ||Δmfcc_13||₂
sim = 100 · exp(−D / D₀)
D₀  = per-word mean DTW distance of that word's known-correct
      recitations to the canonical reference (stored in
      calibration.json, schema version 1; recomputed on corpus change)
```

No arbitrary constant; by construction correct recitations anchor near
100·e⁻¹ ≈ 37% and mispronunciations fall below. Per-axis breakdown
(FR-11): formant-distance axis (praat-parselmouth), spectral axis
(MFCC-DTW over the consonant-window slice), duration ratio — same
documented mapping style.

**D3 · GVR HMM topology (approved).** One GaussianHMM per verse:
**6 states, left-to-right no-skip** (self + advance-by-one only),
**diagonal Gaussians**, hand-initialized startprob/transmat before
`fit()` (hmmlearn has no L-R constructor — verified in Phase 2),
Viterbi `decode()` across all verse HMMs → verse ID + log-likelihood
gap as confidence. Split policy: **per-reciter** (stated per FR-23;
NFR-04).

**D4 · GVR corpus source (owner decision): self-recording program.**
No license-cleared verse-wise Gita audio was found (Phase 2). Verses
will be recorded with named consenting reciters, logging reciter,
date, device, room conditions, and recitation tradition
(`DataIntegrity.md` §2, §3.6). Implication: corpus recording is now
the schedule bottleneck (as `Implementation.md` §5.1 anticipated).

**D5 · SPD reference recitations (owner decision): self-recording
program.** Canonical word recitations recorded with a named fluent
reciter + learner attempts incl. deliberate mispronunciations, same
logging discipline.

**Planned Phase 4 module layout (sequential, independently testable
units — Phase 3 rule on smallest change units):**
1. `samskrita_dhvani/frontend.py` — D1 feature extraction + config
   object (FR-01/FR-02) + hand-derived MFCC for cross-check (FR-03).
2. `samskrita_dhvani/registry.py` — SPD word list + GVR verse registry
   formats, Devanagari⇄IAST via indic_transliteration (FR-12/FR-13/
   FR-22 scaffolding), PROVENANCE entry schema.
3. `samskrita_dhvani/spd_scorer.py` — D2 formula + per-axis breakdown
   (FR-10/FR-11).
4. `samskrita_dhvani/gvr_classifier.py` — D3 topology/training/decode
   (FR-20/FR-21).

**Test plan (written up front, per phase rules).** All tests use clearly
labeled synthetic fixtures only (NFR-02) until real corpus audio
exists: resampling correctness; frame-count math (25/10 ms @16 kHz);
Hamming edge attenuation; **manual-MFCC vs librosa cross-check — the
max-abs-difference is measured and reported from the actual run, not
asserted** (FR-03); Δ/ΔΔ vs course formula; CMVN zero-mean/unit-var
check; DTW alignment monotonicity; sim-mapping monotonicity + D=0 →
100 boundary; L-R transmat row-stochasticity + no-backward-transitions
property; Viterbi decode smoke on synthetic sequences. "Done" for the
front-end unit = pytest green + the FR-03 cross-check number recorded
in Review.md. Existing tests to keep passing: none (first suite).

**Report/doc impact.** Methodology section of the project report will
cite D1 parameters, D2 formula, D3 topology verbatim (they are now the
binding spec). SRS statuses remain Open until Phase 5 verifies each
(`SRS.md` update rule). No Implementation.md edit needed beyond the
parselmouth package-name correction already made this session.

**Migration/compat notes.** Front-end output 39×T is the compatibility
contract for both branches; `calibration.json` carries a schema version
so regeneration is detectable; registry formats get schema version 1 at
first ingest.

**Verdict:** Design approved (D1–D3 as drafted; D4/D5 self-recording).
Phase 3 exit criteria met — Phase 4 may begin.

### Phase 4 (Coding) —

**What was built:**
- _(fill in: modules implemented, matching `Implementation.md` §3
  architecture)_

### Phase 5 (Testing) —

**Test run result (actual, not estimated):**
- _(fill in: command run, pass/fail, actual accuracy/correlation
  numbers with the exact script used to produce them)_

### Phase 6 (Maintenance) — Data Integrity Sweep

_(fill in using the table format from `DataIntegrity.md` §4 once a
sweep has actually been run)_

| Item (word/verse) | Samples | Corrupted found/excluded | Duplicates | Cross-split leaks (GVR only) | Provenance on file? | Label spot-checked? |
|---|---|---|---|---|---|---|
| | | | | | | |

---

## Open Items (carry forward until resolved or explicitly deferred)

1. Finalize SPD word list (20–30 words, difficulty pairs) and GVR verse
   subset size — now constrained by the self-recording decision (D4/D5,
   this session).
2. Create `PROVENANCE.md` (`DataIntegrity.md` §2) and draft the
   recording protocol (reciter/device/room/tradition log template)
   before first ingest.
3. Record verified reference recitations (SPD) / canonical verse audio
   (GVR) via the self-recording programs, with recitation tradition
   stated.
4. Run the first Data Integrity Sweep and populate the table above with
   real counts.
5. Cross-check SPD's automated similarity score against human/
   instructor ratings (NFR-10 in `SRS.md`).
6. Report GVR accuracy on a real held-out split with a confusion matrix
   (NFR-20 in `SRS.md`).
7. Phase 4 unit 1: implement `samskrita_dhvani/frontend.py` per design
   D1, with the FR-03 manual-vs-librosa cross-check test.

## Bugs Fixed This Session

None. (The `parselmouth` PyPI package-name failure is recorded as a
documentation correction under Changes Made, not a code bug.)

## Changes Made This Session

- `requirements.txt` — created; pins the versions installed and
  smoke-tested in Phase 2 (incl. `praat-parselmouth` naming note and
  the `setuptools<81` constraint for `webrtcvad`).
- `files/Implementation.md` — §4 table: corrected the Praat binding's
  PyPI name to `praat-parselmouth` with the trap documented.
- `files/Review.md` — Phase 2 and Phase 3 entries for session
  2026-09-22; Open Items updated.
