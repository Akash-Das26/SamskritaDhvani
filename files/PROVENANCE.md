# SamskritaDhvani — PROVENANCE.md

**Project full title:** *SamskritaDhvani: A Hybrid Signal Processing
Approach to Sanskrit Phonetic Assessment and Bhagavad Gita Verse
Recognition*

**Purpose:** Per `DataIntegrity.md` §2, every audio file used in
training or evaluation must be traceable to a named source with a
stated license or permission basis. This file is that manifest.
It is updated incrementally — one entry per source added, never
batch-committed.

**Schema version:** 1 (set at first ingest, 2026-09-22).

---

## Format

Each entry covers one source (corpus, scholar recording set, or
self-recording session). Within a corpus, the sub-table lists
individual files or file groups once they are actually downloaded and
swept. An entry with no sub-table means the source was checked but
no files have yet been pulled into the repo (awaiting form/access or
acquisition is pending).

---

## SPD (Sanskrit Pronunciation error Detection) Sources

### SPD-01 · Bruce Cameron Hall — *Sanskrit Pronunciation: Booklet and Audio*

| Field | Value |
|---|---|
| **Source name** | *Sanskrit Pronunciation: Booklet and Audio* by Bruce Cameron Hall |
| **Publisher** | Theosophical University Press (Pasadena, CA) |
| **Landing page (verified live 2026-09-22)** | `https://theosociety.org/pasadena/ts/hallskt.htm` |
| **Online edition (verified live 2026-09-22)** | `https://theosociety.org/pasadena/sk-pron/skpro-hp.htm` |
| **License / permission basis** | © 1992 Theosophical University Press. Stated terms: *"This edition may be downloaded for off-line viewing without charge. No part of this publication may be reproduced for commercial or other use in any form or by any means… without prior permission of Theosophical University Press."* — Usage here is academic, non-commercial, internal only. **Do not redistribute.** |
| **Reciter** | Bruce Cameron Hall (Ph.D., Sanskrit and Indian Studies, Harvard, 1983) |
| **Content** | 4-part booklet + audio: (1) Pronunciation guide; (2) 160+ Sanskrit terms defined and pronounced; (3) Summary; (4) Sample verses from the Bhagavad Gita in Devanagari, romanization, and English translation |
| **Audio format** | MP3 (5 files: skpro_00.mp3 through skpro_04.mp3) |
| **Acquisition date** | 2026-09-22 |
| **Acquired by** | Automated wget (personal academic use only) |
| **Recitation tradition** | Classical Sanskrit pronunciation instruction; theosophical/academic pronunciation standard — not a Vedic accentuation tradition (`DataIntegrity.md` §3.6) |
| **Use for** | SPD reference word audio (FR-12): named scholar pronunciations of Sanskrit terms that appear in the SPD word list. Part 4 provides a small Gita-verse cross-check for GVR (not a full-verse corpus). |
| **Local directory** | `data/spd/hall_sanskrit_pronunciation/` |

**File sub-table** (populated after Data Integrity Sweep):

| File | Size | Duration (est.) | Non-silent? | Label spot-checked? | Sweep date |
|---|---|---|---|---|---|
| skpro_00.mp3 | TBD | TBD | TBD | TBD | pending |
| skpro_01.mp3 | TBD | TBD | TBD | TBD | pending |
| skpro_02.mp3 | TBD | TBD | TBD | TBD | pending |
| skpro_03.mp3 | TBD | TBD | TBD | TBD | pending |
| skpro_04.mp3 | TBD | TBD | TBD | TBD | pending |

*Update this sub-table with real values after the first DataIntegrity
sweep (§4) of this source.*

---

## GVR (Bhagavad Gita Verse Recognition) Sources

### GVR-01 · Vāksañcayaḥ — Sanskrit ASR Corpus (IIT Bombay)

| Field | Value |
|---|---|
| **Source name** | Vāksañcayaḥ — Sanskrit ASR Corpus |
| **Institution** | IIT Bombay (ASR Group, Dept. of CSE; CISTS, Dept. of HSS) |
| **Primary URL (verified live 2026-09-22)** | `https://www.cse.iitb.ac.in/~asr/` |
| **Download gate** | Form required: `https://www.cse.iitb.ac.in/~asr/form.html` (form is live; corpus archive link is returned post-form-submission — not yet obtained) |
| **AIKosh mirror (verified live 2026-09-22)** | `https://aikosh.indiaai.gov.in/home/datasets/details/v_ksa_caya_sanskrit_asr_corpus.html` |
| **License (corpus's own page, CC badge, verified 2026-09-22)** | **CC BY-NC 4.0** — Creative Commons Attribution–NonCommercial 4.0 International. Usable for this academic (non-commercial) project with attribution. |
| **License (AIKosh listing metadata API, verified 2026-09-22)** | **CC0 1.0 Public Domain** (from AIKosh API: `"license":"CC0 1.0 Public Domain"`). Conflicts with corpus-page CC BY-NC 4.0. The more restrictive / authoritative corpus-page statement (CC BY-NC 4.0) governs until discrepancy is formally resolved. See Review.md §5 open item. |
| **Acquisition status** | **PENDING** — form not yet submitted. Must be submitted manually; download link arrives post-submission. |
| **Content** | 78+ hours, 45,953 sentence recordings, 22 kHz, multi-speaker, multi-text: Śāstras, contemporary stories, radio programs, extempore discourse. AIKosh tags include "Bhagvadgita" — Gita subset must be filtered by transcript matching (DataSources.md §1.1 caveat). File size: ~1.97 GB (per AIKosh stats: 2,059,272,842 bytes). |
| **Audio format** | MP3 (convert to WAV for feature extraction per Implementation.md §3) |
| **Corpus paper** | Adiga et al., ACL Findings 2021. arXiv: https://arxiv.org/abs/2106.05852 |
| **Recitation tradition** | Multi-speaker; per-recording tradition not documented in metadata — must spot-check transcripts (DataIntegrity.md §4 step 1). |
| **Use for** | Primary GVR training/eval after Gita subset is filtered; non-Gita portions for general front-end validation (DataSources.md §2.3). |
| **Local directory** | `data/gvr/vaksancayah/` (to be created at download time) |

**Action required:** Submit form at `https://www.cse.iitb.ac.in/~asr/form.html`,
log submission date and received download URL here when done.

---

### GVR-02 · Gita Supersite (gitasupersite.in)

| Field | Value |
|---|---|
| **Source name** | Gita Supersite (Jñānadīpa) |
| **Institution** | Originally IIT Kanpur; now operated independently |
| **URL (original, redirects)** | `https://www.gitasupersite.iitk.ac.in/srimad/` |
| **URL (current, verified live 2026-09-22)** | `https://www.gitasupersite.in/` |
| **License / reuse terms** | **No explicit open-data license found** on live check 2026-09-22. Site is a JavaScript SPA; no static terms-of-service or bulk-reuse statement was found in the served HTML. Status: "public academic resource, no stated bulk-reuse license." Contact maintainers before scripted retrieval. |
| **Bulk download** | No bulk archive link exists. Verse audio is accessed via a JS player. Scripted retrieval requires JS rendering. |
| **Acquisition status** | **BLOCKED** — license ambiguity. Maintainers must be contacted before any bulk pull. Contact: `gitasupersite.in` site or IIT Kanpur CSE. Log response here when received. |
| **Content** | All 700 verses, chapters 1–18, Devanagari text + audio, single consistent reciter |
| **Use for** | Canonical single-reciter GVR reference registry (FR-22) and ground truth for Vāksañcayaḥ transcript matching |
| **Local directory** | `data/gvr/gita_supersite/` (create only after permission is confirmed) |

---

## Sources Checked — Excluded or Not Yet Acquired

| Source | Status | Reason | Checked date |
|---|---|---|---|
| Deshpande *Saṃskṛta-Subodhini* (UMich) | **DEAD LINK** | DNS timeout on `www.umich.edu/~iinet/csas/publications/sanskrit/audio.html` — URL does not resolve. Cannot acquire. Check Internet Archive or contact UMich CSAS for current location. | 2026-09-22 |
| Forvo.com (Sanskrit crowdsourced) | Not yet accessed | ToS prohibits bulk/automated scraping; individual manual downloads only; lowest-priority SPD source. To be done manually after SPD word list is finalized. | — |
| archive.org Gita audio (Ranganathan, Paudwal) | **Excluded** | No `licenseurl` metadata — cannot enter corpus per DataIntegrity.md Rule 2 without explicit permission. Confirmed excluded. | 2026-09-22 |
| mahabharata-audio-2018 (GitHub) | Not checked | License for Bhishma Parva repo unconfirmed; lowest priority. | — |

---

*Update this file whenever a file is downloaded or a source is
checked. Cross-reference the Review.md Data Integrity Sweep entry.
Never mark a source "acquired" here without a matching sweep entry in
Review.md.*
