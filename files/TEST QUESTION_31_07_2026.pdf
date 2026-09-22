# SamskritaDhvani — DataSources.md

**Project full title:** *SamskritaDhvani: A Hybrid Signal Processing
Approach to Sanskrit Phonetic Assessment and Bhagavad Gita Verse
Recognition*

**Purpose:** This is the Phase 2 (Resource Gathering) deliverable for
corpus acquisition — a checked, real list of what audio can actually
be downloaded for SPD (Sanskrit Pronunciation error Detection) and GVR
(Bhagavad Gita Verse Recognition), with access method, format, size,
and license/ToS status for each source. Nothing here is assumed —
every entry below was looked up and verified against a live page or
paper in this session (per `Development.md` Ground Rule 1 and Phase 2
rule: claims about current state must come from an actual check, not
recall).

**Important:** Downloading a source does **not** make it "valid data."
Every file pulled from here still goes through `DataIntegrity.md` §1–4
in full — opened, listened to, labeled, and logged in
`PROVENANCE.md` and `Review.md` — before it can be used in a reported
result.

---

## 1. GVR primary sources (Bhagavad Gita–specific audio)

### 1.1 Vāksañcayaḥ — Sanskrit ASR Corpus ⭐ recommended primary source

- **What it is:** 78+ hours, 45,953 sentence recordings, 22 kHz, spanning
  many Sanskrit Śāstra texts, contemporary stories, radio programs, and
  extempore discourse. The AIKosh listing explicitly tags this corpus
  with **"Bhagvadgita"** as one of its content categories, so a Gita
  subset can be filtered from the full corpus's metadata/transcripts.
- **License:** **CC0 1.0 (Public Domain)** per the AIKosh (Government
  of India) listing — the cleanest license of any source here.
- **How to get it:**
  - Government portal listing (browse/download UI):
    `https://aikosh.indiaai.gov.in/home/datasets/details/v_ksa_caya_sanskrit_asr_corpus.html`
  - Primary distribution (per the corpus's own GitHub README):
    `https://www.cse.iitb.ac.in/~asr/` (IIT Bombay ASR group's page —
    this is where the actual corpus archive is hosted; the AIKosh page
    mirrors it).
  - Code/recipe + documentation: `https://github.com/cyfer0618/Vaksanca`
    (Kaldi ASR recipe repo; corpus itself is not stored in this repo,
    only scripts and a linked summary datasheet).
- **Format:** Audio + sentence-level transcripts; originally distributed
  as `.mp3` per the repo's own testing notes (convert to `.wav` for the
  feature-extraction pipeline, per `Implementation.md` §3).
- **Use for:** Primary GVR training/eval material — filter for Gita
  content by transcript matching against the Gita Supersite text
  (§1.2) to build the verse-ID ↔ audio registry (`SRS.md` FR-22).
- **Caveat to log in `PROVENANCE.md`:** the corpus is multi-speaker and
  multi-text; you must confirm which sentences are actually Gita verses
  (by transcript match) rather than assuming from the "Bhagvadgita" tag
  alone — spot-check per `DataIntegrity.md` §4 step 1.

### 1.2 Gita Supersite (IIT Kanpur) — verse-by-verse text + audio

- **What it is:** All 700 verses of the Bhagavad Gita, chapter-by-chapter
  (1–18), each with Devanagari text and an audio recitation, from a
  single consistent academic source — exactly the clean verse-ID ↔
  audio structure `Implementation.md` §5.1 and `SRS.md` FR-22 call for.
- **URL:** `https://www.gitasupersite.iitk.ac.in/srimad/` (also mirrored
  at `https://www.gitasupersite.in/srimad/texts`).
- **License/access status:** No explicit open-data license is stated on
  the site — it is a public academic resource (IIT Kanpur CSE
  department project), not a downloadable dataset package. **Before
  bulk-using this audio, log it in `PROVENANCE.md` as "public academic
  resource, no stated bulk-reuse license" and, if this project will be
  published or shared beyond coursework, contact the Gita Supersite
  team for permission** — this satisfies `DataIntegrity.md` §2's
  provenance requirement more defensibly than silently scraping it.
- **How to get it:** Verse pages are individually addressable
  (chapter/verse query parameters); audio must be downloaded per verse
  through the site's player — there is no bulk-archive download link
  found in this session. Budget this as a scripted-but-polite retrieval
  task (respect the site's servers — this is a small academic site, not
  a CDN), not a one-command bulk pull.
- **Use for:** The canonical, highest-quality single-reciter reference
  recording per verse — ideal for GVR's "one clean reference per class"
  need, and for validating the Vāksañcayaḥ-derived Gita subset (§1.1)
  against a known-correct reference.

### 1.3 Mahabharata Audio 2018 (crowdsourced) — backup/supplementary

- **What it is:** A crowdsourced project (GitHub org
  `mahabharata-audio-2018`) to record the entire Mahabharata (Gita Press
  edition) in Sanskrit, split into per-Parva repositories. The Bhagavad
  Gita is chapters 23–40 (or 13–42 depending on the numbering scheme) of
  the **Bhishma Parva** (the 6th of 18 parvas).
- **URL pattern:** `https://github.com/mahabharata-audio-2018/parvaNN`
  (confirmed live for `parva02`; the Bhishma Parva repo number was not
  independently confirmed in this session — check the org's repo list
  at `https://github.com/mahabharata-audio-2018` before relying on a
  specific parva number).
- **License:** Not independently confirmed in this session — check each
  repo's own README/LICENSE before use; log whatever is found in
  `PROVENANCE.md`.
- **Use for:** A second, independently-sourced reciter for GVR (useful
  for the "multiple recitations per verse, multiple reciters" goal in
  `Implementation.md` §5.1, which reduces single-reciter overfitting in
  the per-verse HMMs) — treat as supplementary, not primary, since it
  wasn't purpose-built for verse-level ASR and needs its own alignment
  work.

---

## 2. General Sanskrit speech corpora (front-end validation, not Gita-specific)

Use these to validate the shared MFCC front-end (`SRS.md` FR-01–FR-03)
against real chanted/read Sanskrit speech beyond the Gita itself, and
for LPCC/formant ablation experiments — **not** as GVR training data
unless you specifically align a Gita subset out of them (Vedavani does
not contain Gita content; it's Rig/Atharva Veda).

### 2.1 Vedavani

- **What it is:** 54-hour Sanskrit ASR dataset, 30,779 labelled audio
  samples from the Rig Veda and Atharva Veda, with an 80/10/10
  train/val/test split already defined by the paper authors (ACL 2025).
- **License:** **Apache License 2.0**.
- **How to get it:**
  - HuggingFace: `https://huggingface.co/datasets/sanganaka/Vedavani-Dataset`
  - GitHub (code + docs): `https://github.com/SujeetNlp/Vedavani`
- **Format:** WAV audio files (segmented and aligned to verse text);
  HuggingFace note: files are split across multiple folders of ≤9,000
  files each — consolidate into one directory before use, per the
  dataset card's own instructions.
- **Use for:** Front-end cross-validation on real chanted Sanskrit;
  optionally, a stretch-goal ablation showing the SPD/GVR pipeline
  generalizes beyond Gita-only material.

### 2.2 ASR-Sanskrit (HuggingFace)

- **URL:** `https://huggingface.co/datasets/komalsai234/ASR-Sanskrit`
- **Format:** Parquet, 10K–100K rows.
- **License:** Apache 2.0 (per the dataset card).
- **Use for:** A second, independent cross-check dataset for the shared
  front-end if Vedavani alone isn't enough for your report's validation
  section.

### 2.3 Vāksañcayaḥ (non-Gita portion)

Same corpus as §1.1 — its non-Gita sentences (readings of other
Śāstras, contemporary stories, radio, discourse) are a large, real,
CC0-licensed pool for general front-end testing beyond the Gita subset.

---

## 3. SPD reference-recitation sources (word-level pronunciation)

No ready-made "Sanskrit mispronunciation" corpus exists publicly — this
was checked and not found. The **mispronounced/learner-variant side of
SPD's data (krishna/kishna/krisna-type variants) still has to be
self-recorded**, per `Implementation.md` §5.1. What's available
publicly are **correct reference recitations by named speakers**,
which cover the "one verified reference per word" half of the
requirement (`SRS.md` FR-12):

### 3.1 Forvo.com — crowdsourced word pronunciations

- **URL pattern:** `https://forvo.com/word/<word>/` (has a Sanskrit
  `[sa]` language tag; confirmed working for at least one Sanskrit
  entry in this session).
- **What it gives:** Multiple community-submitted pronunciations per
  word, voted good/bad, individually downloadable as MP3.
- **License/access caveat:** Forvo's Terms of Service restrict bulk/
  automated scraping — **do not script a bulk pull**; use their API
  (paid tiers exist) or download individual clips manually for your
  ~20–30 word list, and log each clip's speaker attribution (Forvo
  gives a username, country) in `PROVENANCE.md`. Speaker fluency is
  crowdsourced and unverified — cross-check against §3.2/§3.3 or your
  own instructor before treating a Forvo clip as "the" reference.

### 3.2 Madhav Deshpande's *Saṃskṛta-Subodhini* audio set (University of Michigan)

- **What it is:** A complete, freely downloadable MP3 set recorded by
  Prof. Madhav Deshpande (Sanskrit scholar, University of Michigan) to
  accompany his Sanskrit primer textbook — a named, credentialed
  reciter, which is exactly the provenance strength `DataIntegrity.md`
  §2 asks for.
- **URL (as last referenced):**
  `http://www.umich.edu/~iinet/csas/publications/sanskrit/audio.html`
  — **verify this URL is still live before relying on it**; it was
  found via an archived mailing-list reference, not a direct fetch in
  this session, so treat it as "reported to exist, not independently
  confirmed live" until you check it yourself and log the check date in
  `PROVENANCE.md`.
- **Use for:** A strong, named-scholar reference recitation source for
  isolated words/declension forms.

### 3.3 Bruce Cameron Hall's *Sanskrit Pronunciation: Booklet and Audio* (Theosophical University Press)

- **What it is:** A booklet + audio recording by Bruce Cameron Hall
  (Ph.D., Sanskrit and Indian Studies, Harvard) covering (1) letter/word
  pronunciation instruction, (2) 160+ Sanskrit terms pronounced and
  defined, (3) a pronunciation summary, and — directly useful for this
  project — **(4) sample verses from the Bhagavad Gita** in Devanagari,
  romanization, and English translation.
- **URL:** `https://theosociety.org/pasadena/ts/hallskt.htm` (landing
  page); PDF booklet at
  `https://www.theosociety.org/pasadena/sk-pron/skpro_00.pdf`.
- **Use for:** Named-scholar reference audio for both isolated
  words (SPD) and a small set of Gita sample verses (a nice
  cross-check for GVR reference quality, though not a full-verse
  corpus).

### 3.4 Loyola University New Orleans — Sanskrit sound files (backup)

- **URL:** `http://www.loyno.edu/~tccahill/skt_sound_files.html`
- **What it is:** ~50 nouns and ~20 verbs in MP3, recorded by Tim
  Cahill c. 1981–82.
- **Caveat:** Older recording quality (per the source's own mailing-list
  description) — use as a backup/ablation source, not a primary
  reference, and note the recording-condition limitation in
  `DataIntegrity.md`'s sweep table if used.

---

## 4. Recommended acquisition order (maps to `Development.md` Phase 2)

1. **Vāksañcayaḥ corpus (§1.1)** — download first; CC0, largest, most
   flexible, and gives you both a Gita subset (via transcript matching)
   and a general-Sanskrit validation pool (§2.3) from one source.
2. **Gita Supersite (§1.2)** — acquire verse-by-verse in parallel; this
   is your clean, single-reciter GVR reference registry and the
   ground truth you'll match Vāksañcayaḥ's Gita subset against.
3. **SPD reference words (§3.2, §3.3, §3.1 in that order)** — Deshpande
   and Hall first (named scholars, better provenance), Forvo as a
   supplementary/cross-check source, respecting its ToS.
4. **Vedavani (§2.1)** — pull once the Gita-specific pipeline is working,
   for front-end validation and any "generalizes beyond Gita" claim in
   the report.
5. **Mahabharata Audio 2018 (§1.3)** and **Loyola set (§3.4)** — optional
   depth/backup sources, lowest priority.
6. **Self-recorded mispronunciation variants** — start alongside step 1;
   this is the one piece nothing above supplies, and it's on the
   project's own timeline (finding willing student volunteers to
   mispronounce words takes longer than downloading a corpus).

After each acquisition step, run `DataIntegrity.md` §4's sweep on
whatever was just added and log it in `Review.md` — do not batch all
five sources into one un-swept pile before checking any of them.

---

## 5. What still needs a session-time check

These were not fully confirmed in this session and must be verified
before being relied on (log the verification in `Review.md` when done):

- Exact license terms for the specific `mahabharata-audio-2018` repo
  covering Bhishma Parva (repo number and license unconfirmed).
- Whether `umich.edu/~iinet/csas/...` (§3.2) is still live.
- Gita Supersite's actual reuse terms for bulk/programmatic audio
  retrieval — the site itself should be checked directly, and if
  ambiguous, the maintainers contacted, before scripting a full
  700-verse pull.
- The exact file layout and transcript format inside the Vāksañcayaḥ
  archive once downloaded from `cse.iitb.ac.in/~asr/` (the GitHub repo
  only hosts code, not the corpus itself, so this needs direct
  inspection after download).

---

*Update this file whenever a new source is checked or an access URL
changes, and cross-reference the `PROVENANCE.md` entry created for each
source once actually downloaded.*
