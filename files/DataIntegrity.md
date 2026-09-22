# SamskritaDhvani — DataIntegrity.md

**Project full title:** *SamskritaDhvani: A Hybrid Signal Processing
Approach to Sanskrit Phonetic Assessment and Bhagavad Gita Verse
Recognition*

**Purpose:** Defines how the SamskritaDhvani project guarantees that
audio used for training, evaluation, and reported scores is **valid,
correctly labeled, and provably real** — and how corrupted, silent,
unattributed, or mislabeled audio is kept out of the pipeline rather
than silently absorbed into it. Covers both sub-projects: SPD (Sanskrit
Pronunciation error Detection) and GVR (Bhagavad Gita Verse
Recognition).

This is a **policy + process** document. `Implementation.md` §5–7
defines the pipeline this policy governs; `Development.md` Phase 2, 5,
and 6 require this policy to be followed whenever the audio corpus is
touched; `Review.md` records *whether the corpus currently satisfies
it, and when it was last checked*.

---

## 1. Ground Truth: What "Valid Audio" Means for SamskritaDhvani

Audio flowing into training, evaluation, or a reported score is only
valid if **all** of the following hold:

1. **It is real, openable, non-silent speech audio** — not a 0-byte or
   corrupted file, not a clip that is more than ~90% silence after VAD
   trimming, not a duplicate masquerading as a new recording.
2. **Its label is correct** — the word (SPD) or verse ID (GVR) attached
   to a clip is what was actually spoken, verified by listening, not
   assumed from the filename.
3. **It has known, traceable provenance** — every clip is traceable to
   a named public/open corpus, a named consenting reciter you recorded
   yourself, or a named cooperating source (see §2 below) — never an
   unverified or unattributed source.
4. **It does not leak across splits** — for GVR, no reciter+verse
   recording used in training also appears in the test split (state
   whether your split is per-recording or per-reciter, since this
   changes what accuracy means).
5. **Synthetic or placeholder audio is never mistaken for real speech**
   — silence/tone fixtures used for pipeline unit tests must be clearly
   distinguishable in code and must never be the basis for a reported
   similarity or accuracy number.

If any of these fail for a clip, that clip is **invalid data** for the
purposes of this project and must be excluded or corrected — never
silently kept.

---

## 2. Provenance Requirements

Every audio file must be traceable to one of:

- **A named public/open Sanskrit audio corpus or Vedic chanting
  archive** — record the exact source name/URL and license.
- **A self-recorded clip with a named, consenting reciter** — record
  reciter name/role, recording date, device used, and room/noise
  conditions.
- **A clip provided by a cooperating faculty member or department** —
  record who provided it and under what permission.

**No unattributed audio.** If you cannot state where a clip came from,
it does not go in either corpus.

**Required artifact:** maintain `PROVENANCE.md` (or a structured
`provenance.json`) listing, per word (SPD) or verse (GVR):
source/reciter, recording or acquisition date, license or permission
basis, and file path.

---

## 3. Standing Rules (apply to all future data work)

1. **No silent substitution, ever.** A missing, corrupted, or
   near-silent clip is excluded and counted — never replaced with a
   placeholder feature vector that keeps the original label.
2. **No clip without traceable provenance.** New words/verses are not
   added to the registry (`SRS.md` FR-12/FR-22) without a provenance
   entry.
3. **No cross-split leakage (GVR).** Verify reciter+verse disjointness
   between train and test whenever the corpus changes.
4. **No synthetic data in reported results.** Any similarity/accuracy
   number in the project report must state which audio (real vs.
   synthetic fixture) produced it — synthetic-derived numbers are for
   pipeline tests only.
5. **No unverified "clean" claim.** A word/verse's audio is only
   "validated" after an actual sweep (§4) has been run and logged in
   `Review.md` with real counts — not assumed clean at registration
   time.
6. **Reference recitations are explicitly justified.** State which
   recitation tradition (e.g. classical vs. Vedic accentuation) each
   SPD reference and GVR canonical recording follows — do not present
   one tradition as universally "correct" without saying so.

---

## 4. The Data Integrity Sweep (recurring maintenance task)

Run this whenever: new words/verses are added, before any reported
score, and periodically as part of `Development.md` Phase 6
maintenance.

**Steps:**
1. For each word (SPD) / verse (GVR): confirm every audio file opens,
   is non-silent after VAD trimming, and matches its label by listening
   to a sample.
2. Count and log corrupted/unusable files found — excluded, not
   replaced.
3. For GVR: confirm no reciter+verse recording appears in both train
   and test splits.
4. Confirm reference recitations (SPD) and canonical verse audio (GVR)
   are the verified, intended versions.
5. Cross-check every word/verse against the provenance manifest (§2) —
   flag anything missing an entry.
6. Record results in `Review.md` using this file's table format — real
   counts only, never estimates.

**Sweep result table format (for Review.md):**

| Item (word/verse) | Samples | Corrupted found/excluded | Duplicates | Cross-split leaks (GVR only) | Provenance on file? | Label spot-checked? |
|---|---|---|---|---|---|---|
| | | | | | | |

---

## 5. Open Items (carry forward until resolved)

1. Build the word list (SPD) and verse subset (GVR) per
   `Implementation.md` §5.1.
2. Create `PROVENANCE.md`.
3. Record at least one verified reference recitation per SPD word and
   one canonical recording per GVR verse, with tradition noted (§3.6).
4. Run the first full Data Integrity Sweep (§4) and log it in
   `Review.md` — until then, no word/verse should be described as
   "validated," only as "in use."

---

*Update this file whenever a Data Integrity Sweep changes a finding's
status, or a new word/verse is added to either registry. Reference the
`Review.md` entry that verified any fix, and vice versa.*
