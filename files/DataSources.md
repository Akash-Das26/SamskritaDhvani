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
- **RESOLVED 2026-09-22 (post-download transcript check):** the
  corpus's Gita-tagged material (`GB_*` utterance IDs, 2,161 lines, all
  in speaker sp006) is the **Śaṅkara Bhāṣya prose commentary**, not
  canonical verse text; a retold narrative (sp022, text-ID `_008`)
  renders BG 1.1 as story prose. Canonical verse markers return zero
  transcript hits (`धृतराष्ट्र उवाच`, `कर्मण्येवाधिकारस्ते`,
  `यदा यदा हि धर्मस्य`, `चञ्चलं`). **Conclusion: Vāksañcayaḥ cannot
  supply the GVR verse registry**; it remains valuable as the general
  Sanskrit speech pool (§2.3).
- **License resolution 2026-09-22:** the corpus archive's own README
  states **CC BY-NC 4.0** (matching the corpus site). The AIKosh
  listing's "CC0" label is contradicted by the corpus itself — treat
  the corpus README as authoritative: CC BY-NC 4.0, attribution
  required, non-commercial use only.

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
- **Checked directly 2026-09-22:** `www.gitasupersite.in/srimad/texts`
  is a JS SPA behind **Cloudflare Turnstile** — plain HTTP fetches are
  dropped (curl exit before response) and a headless-Chrome render
  returns only the challenge shell. The legacy server-rendered host
  `old.gitasupersite.in` is live and its `/srimad?field_chapter_value=N`
  pages respond, but verse content loads via AJAX POST and the served
  HTML contains **no audio URLs**. The SPA app bundle exposes only a
  generic `/api` base (no usable static endpoints). **Scripted bulk
  retrieval is blocked both technically and by the still-unstated
  license** — maintainer contact is required before any verse audio
  pull (see PROVENANCE.md GVR-02).
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
- **License — RESOLVED 2026-09-23:** the project's own page
  (`sanskrit.github.io/groups/dyuganga/projects/audio/mbh-audio/`)
  declares **CC BY-SA 4.0** for the whole effort, publishes per-file
  named reciters, and hosts the audio at
  `archive.org/details/mahAbhArata-mUla-paThanam-GP` (per-file creator
  metadata verified). Note: the archive item itself carries **no
  `licenseurl` field** — the license basis is the project page's
  declaration. Still **no Bhīṣma Parva content** (3 parvas only), so
  this does not change the GVR verdict.
- **Checked 2026-09-22:** the org's public repositories are exactly
  `parva01-001-100`, `parva01-101-233`, `parva02`, `parva03`,
  `parva04`, `parva12-001-100` — **no Bhishma Parva repo exists**, so
  this source contains no Bhagavad Gita audio. Dead end for GVR; the
  zips downloaded earlier (parva01/02/03/04/12) cover only non-Gita
  parvas and are held unextracted pending a use decision.
- **Use for:** ~~A second, independently-sourced reciter for GVR~~ (useful
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
- **ACQUIRED + SWEPT 2026-09-23 (full HF clone present at repo root
  `Vedavani-Dataset/`, 6.4 GB):** index integrity verified first —
  30,779 CSV rows across train/val/test ↔ 30,779 on-disk files, 0
  missing, 0 duplicates, total 54.38 h (matches the paper's stats).
  DataIntegrity §4 sweep of all 30,799 on-disk files (MANIFEST.csv):
  30,799/30,799 decode cleanly, 0 silent; all WAV/PCM_16 mono;
  29,355 @ 16 kHz but **1,442 @ 44.1 kHz + 2 @ 48 kHz** (contradicts
  the card's 16 kHz claim — 1,436 of them in the `Rigvedha*` family,
  i.e. one recorder batch; D1 front-end resamples, so non-blocking);
  **299 files peak ≥ 0.99** (0.97%, mostly Atharvaveda) + 87
  borderline 0.985–0.99 — flagged, not excluded (mild peak scaling at
  the front-end; not reference material); duration vs CSV label:
  median |Δ| = 0.000 s, max 0.000 s, 0 files > 0.25 s. 20 on-disk
  extras are `(1)`-suffixed browser re-download artifacts, sha-identical
  to their originals → excluded via `EXCLUDED_FILES.csv`. Label
  listen-through (§4 step 1) **COMPLETE 2026-09-23**: automated
  515-file sample pass (incl. all 299 clipped files) + owner review of
  the 12 evidence-pack renders — see PROVENANCE.md GVR-03.

### 2.2 ASR-Sanskrit (HuggingFace)

- **RESOLVED 2026-09-23 (repo cloned at root `ASR-Sanskrit/`, 6.9 GB,
  `komalsai234/ASR-Sanskrit`):** the parquet shards contain **no raw
  audio** — schema is `input_features` (precomputed Whisper mel
  features) + `labels` (token IDs). It cannot feed the D1 MFCC
  front-end, which needs waveforms. **Excluded for this project**
  (usable only as a Whisper fine-tune artifact, which is not our
  pipeline).

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
  crowdsourced and unverified — cross-check against §3.3/§3.4 or your
  own instructor before treating a Forvo clip as "the" reference.
  **Plan set 2026-09-22:** manual per-clip downloads only, after the
  SPD word list is finalized from Hall/Loyola material (see
  PROVENANCE.md excluded/plan table).

### 3.2 Madhav Deshpande's *Saṃskṛta-Subodhini* audio set (University of Michigan)

- **What it is:** A complete, freely downloadable MP3 set recorded by
  Prof. Madhav Deshpande (Sanskrit scholar, University of Michigan) to
  accompany his Sanskrit primer textbook — a named, credentialed
  reciter, which is exactly the provenance strength `DataIntegrity.md`
  §2 asks for.
- **URL (as last referenced):**
  `http://www.umich.edu/~iinet/csas/publications/sanskrit/audio.html`
  — **RESOLVED 2026-09-22: unrecoverable.** The URL is DNS-dead, and a
  Wayback CDX check across the whole `umich.edu` domain found **zero
  successful audio captures** for any Sanskrit audio path (only 404
  captures of attempted URLs from 2012–2013). The set cannot be
  acquired from any channel; Hall (§3.3) and Loyola (§3.4) are the
  named-scholar sources this project will actually have.
- **Use for:** ~~A strong, named-scholar reference recitation source~~
  — unavailable; role covered by SPD-01 (Hall) and SPD-02 (Loyola).

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

- **URL:** `http://www.loyno.edu/~tccahill/skt_sound_files.html` —
  **live site dead** (302 → `people.loyno.edu`, which does not
  respond; HTTPS fails). **RECOVERED 2026-09-22 via the Internet
  Archive Wayback Machine:** all 63 archived MP3s (captures of
  2011-06-06) enumerated via the CDX index and downloaded — nominal
  declensions by gender, pronouns, verb conjugations by class, and
  verse/exercise readings; 74.9 min total. See PROVENANCE.md SPD-02
  and `data/spd/loyola_cahill_sound_files/MANIFEST.csv`.
- **What it is:** Traditional recitations of grammatical paradigms in
  MP3, recorded by Tim Cahill c. 1981–82 (63 files, more than the
  originally described ~50 nouns + ~20 verbs: pronouns and verse
  readings are included).
- **Caveat:** Older recording quality — sweep found low levels overall
  (rms −35.7 to −52.0 dB), with the `noun1–noun9` set quietest (peak
  0.047 on `noun1_deva.mp3`); those files are quarantined as reference
  material pending a listen-through. Use as a backup/ablation source,
  not a primary reference, and note the recording-condition limitation
  in `DataIntegrity.md`'s sweep table if used.

---

## 4. Recommended acquisition order (maps to `Development.md` Phase 2)

1. **Vāksañcayaḥ corpus (§1.1)** — download first; CC0, largest, most
   flexible, and gives you both a Gita subset (via transcript matching)
   and a general-Sanskrit validation pool (§2.3) from one source.
2. **Gita Supersite (§1.2)** — acquire verse-by-verse in parallel; this
   is your clean, single-reciter GVR reference registry and the
   ground truth you'll match Vāksañcayaḥ's Gita subset against.3. **SPD reference words (§3.3, §3.4, then §3.1)** — ~~Deshpande and
   Hall first~~ **(updated 2026-09-22:** Deshpande §3.2 is
   unrecoverable — dead URL, zero Wayback captures; Hall §3.3 is
   acquired and swept; Loyola §3.4 recovered from the Wayback Machine
   and swept**)**; Forvo as a supplementary/cross-check source,
   respecting its ToS.
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

- ~~Exact license terms for the specific `mahabharata-audio-2018` repo
  covering Bhishma Parva~~ **RESOLVED 2026-09-22:** no Bhishma Parva
  repo exists in the org (6 public repos, parvas 1–4 and 12 only); the
  source cannot supply Gita audio at all.
- ~~Whether `umich.edu/~iinet/csas/...` (§3.2) is still live.~~
  **RESOLVED 2026-09-22:** DNS timeout — dead link; cannot acquire
  (see PROVENANCE.md excluded-sources table).
- ~~Gita Supersite's actual reuse terms for bulk/programmatic audio
  retrieval~~ **RESOLVED 2026-09-22:** no license statement found; site
  is additionally Cloudflare-gated and exposes no static audio/API
  endpoints (see §1.2 note). Bulk retrieval remains **blocked pending
  maintainer contact**.
- ~~The exact file layout and transcript format inside the
  Vāksañcayaḥ archive~~ **RESOLVED 2026-09-22:** layout is
  `spNNN/spNNN-NNNNNN_TEXTID.mp3` (45,953 MP3s, 54 speaker dirs) plus
  per-speaker transcripts `Transcript/Devanagari/spNNN.txt` and
  `Transcript/SLP1/spNNN.txt`, TSV format `<uttID>\t<text>`; official
  train/val/test/OOD speaker split listed in the corpus README.

---

*Update this file whenever a new source is checked or an access URL
changes, and cross-reference the `PROVENANCE.md` entry created for each
source once actually downloaded.*
