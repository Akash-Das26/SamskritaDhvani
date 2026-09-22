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
| skpro_00.mp3 | 274,013 B | 78.5 s | yes (rms −28.2 dB, 38 segments) | booklet part 1 — pending listen-through | 2026-09-22 |
| skpro_01.mp3 | 3,039,419 B | 1001.3 s | yes (rms −29.6 dB, 694 segments) | term list — pending listen-through | 2026-09-22 |
| skpro_02.mp3 | 3,495,647 B | 1237.3 s | yes (rms −30.8 dB, 725 segments) | term list — pending listen-through | 2026-09-22 |
| skpro_03.mp3 | 885,755 B | 297.0 s | yes (rms −30.1 dB, 206 segments) | summary — pending listen-through | 2026-09-22 |
| skpro_04.mp3 | 197,363 B | 67.5 s | yes (rms −30.3 dB, 33 segments) | Gita sample verses — pending listen-through | 2026-09-22 |

All 5 files verified as valid MPEG-1 L3 audio, 64 kbps, 16 kHz mono
(`DataIntegrity.md` §4 automated pass, 2026-09-22). Initial acquisition
of skpro_00/skpro_02 produced 0-byte files; re-downloaded 2026-09-22
with referer header and re-swept — values above are from the re-sweep.
**Label listen-through progress (§4 step 1):** automated content pass
complete 2026-09-23 (68/68 SPD files incl. these: 0 VAD failures,
0 clipping signatures, 0 DC offsets; `data/provenance/
spd_listen_2026-09-23/`). Human ear check staged via `CHECKLIST.md`
in the same directory — **files remain pipeline-ineligible until the
owner's verdict is logged.**

### SPD-02 · Loyola University New Orleans — Sanskrit sound files (Tim Cahill)

| Field | Value |
|---|---|
| **Source name** | Sanskrit Resources (sound files) — traditional recitations of grammatical paradigms |
| **Recorder / reciter** | Tim Cahill, Loyola University New Orleans (Religious Studies Dept.) |
| **Recording era** | c. 1981–82 (per the source's own description) |
| **Original URL (dead)** | `http://www.loyno.edu/~tccahill/skt_sound_files.html` — 302-redirects to `people.loyno.edu`, which does not respond; HTTPS fails. Checked dead 2026-09-22. |
| **Recovery method (verified 2026-09-22)** | Internet Archive Wayback Machine: 63 MP3 captures under `loyno.edu/~tccahill/skt_sound_files/*` (captured 2011-06-06), enumerated via the CDX index and fetched as `web.archive.org/web/<timestamp>id_/<original-url>`. Archived page text retained as provenance evidence. |
| **License / permission basis** | No license statement on the archived page. Academic, non-commercial, internal use only; **do not redistribute**. Same treatment as SPD-01. |
| **Content** | 63 MP3s: nominal declensions by gender (fem/masc/neut), pronouns, verb conjugations by class (1–10), verse and exercise readings — continuous paradigm recitations, not isolated words |
| **Audio format** | MP3, 44.1 kHz stereo, mixed bitrates (yad_fem: 128 kbps JntStereo) — D1 front-end resamples to 16 kHz mono |
| **Acquisition date** | 2026-09-22 |
| **Acquired by** | Scripted Wayback retrieval (63/63 HTTP-successful; yad_fem.mp3 re-fetched after first capture returned a Wayback HTML page) |
| **Use for** | SPD reference material (FR-12): paradigm recitations for declension/form pronunciation; per-word reference clips to be cut only after the label listen-through. Recording-era quality limitation noted (DataSources.md §3.4). |
| **Local directory** | `data/spd/loyola_cahill_sound_files/` (per-file sweep data in `MANIFEST.csv`: sha256-16, sr, channels, duration, rms, segments, peak) |

**File sub-table (group summary — per-file values in MANIFEST.csv; swept 2026-09-22):**

| Group | Files | Duration | Non-silent? | Label spot-checked? | Sweep date |
|---|---|---|---|---|---|
| Nominal declensions (fem/masc/neut) | 43 | — | yes (valid MPEG, no clipping) | pending listen-through | 2026-09-22 |
| Pronouns (incl. yuṣmad/as mad) | 12 | — | yes | pending | 2026-09-22 |
| Verbs (classes 1–10) | 8 | — | yes | pending | 2026-09-22 |
| **All 63 files** | 63 | 74.9 min total | 63/63 valid | pending | 2026-09-22 |

**Quality flags from the sweep (§4):** no clipping (max peak < 0.99
anywhere); no content duplicates (sha256 distinct); recordings are low-
level overall (rms −35.7 to −52.0 dB) — the `noun1–noun9` set is
quietest (rms −49 to −52 dB; `noun1_deva.mp3` peak only 0.047).
**Quarantine rule applied:** files with peak < 0.1 are NOT eligible as
reference material until the listen-through confirms intelligibility;
gain normalization at the front-end may be evaluated then.
**Label listen-through progress (§4 step 1):** automated content pass
complete 2026-09-23 — 63/63 pass (0 VAD failures, min speech fraction
0.449 on `noun5_nadii` = recitation pauses, not silence; item counts
consistent with paradigm structure, e.g. `noun6_vaari` = 24 VAD items
= the full 24-form declension). Evidence pack staged for the owner's
eye/ear check: spectrograms + **gain-boosted WAV renders of all 9
noun-set files** (peaks 0.045–0.09 → 0.60) at
`data/provenance/spd_listen_2026-09-23/` with `CHECKLIST.md`
(pre-stated decision rules: ≥6/9 intelligible → quarantine lifts for
those files with mandatory front-end gain normalization). Files remain
pipeline-ineligible until the owner's verdict is logged.

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
| **License (AIKosh listing metadata API, verified 2026-09-22)** | ~~CC0 1.0 Public Domain~~ **RESOLVED 2026-09-22:** the corpus archive's own README states **CC BY-NC 4.0**; the corpus site's CC badge agrees. The AIKosh "CC0" label is wrong — corpus README is authoritative. **CC BY-NC 4.0 governs.** |
| **Acquisition status** | **ACQUIRED 2026-09-22** — full archive `vaksancayah_sanskrit_asr_corpus_v1.zip` (2.0 GB, 45,953 MP3s, 54 speaker dirs) downloaded, held at repo root (unextracted); Kaldi recipe zip `Vaksanca-master.zip` also present. Verified layout: `spNNN/spNNN-NNNNNN_TEXTID.mp3`; transcripts `Transcript/Devanagari/spNNN.txt` + `Transcript/SLP1/spNNN.txt`, TSV `<uttID>\t<text>`. Official README split: train sp001/002/003/004/006/008/009/012/016/019/020/021, val sp005/013/014/017, test sp007/010/011/015/018/022, OOD sp023–027. |
| **Content** | 78+ hours, 45,953 sentence recordings, 22 kHz, multi-speaker, multi-text: Śāstras, contemporary stories, radio programs, extempore discourse. AIKosh tags include "Bhagvadgita" — Gita subset must be filtered by transcript matching (DataSources.md §1.1 caveat). File size: ~1.97 GB (per AIKosh stats: 2,059,272,842 bytes). |
| **Audio format** | MP3 (convert to WAV for feature extraction per Implementation.md §3) |
| **Corpus paper** | Adiga et al., ACL Findings 2021. arXiv: https://arxiv.org/abs/2106.05852 |
| **Recitation tradition** | Multi-speaker; per-recording tradition not documented in metadata — must spot-check transcripts (DataIntegrity.md §4 step 1). |
| **Use for** | Primary GVR training/eval after Gita subset is filtered; non-Gita portions for general front-end validation (DataSources.md §2.3). |
| **Local directory** | `data/gvr/vaksancayah/` (to be created at download time) |

**Gita-subset check (DataSources.md §5 item, resolved 2026-09-22):**
transcripts were grepped for canonical Gita verse markers after
download. The `GB_*` utterance family (2,161 lines, all in sp006) is
**Śaṅkara Bhāṣya prose commentary**, not verse text; a retold narrative
(sp022, `_008`) renders BG 1.1 as story prose. `धृतराष्ट्र उवाच`,
`कर्मण्येवाधिकारस्ते`, `यदा यदा हि धर्मस्य`, `चञ्चलं` return **zero**
hits. **No canonical Gita verse audio exists in this corpus — it cannot
supply the FR-22 verse registry.** Permitted uses: general front-end
validation pool (§2.3) and SLP1/Devanagari transcript alignment
reference.

**Action required:** ~~Submit form~~ (resolved — archive obtained).
Remaining: extraction + per-file sweep only for the subsets actually
used; keep zip as the provenance-anchored master copy.

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
| **Acquisition status** | **BLOCKED** — license ambiguity. Maintainers must be contacted before any bulk pull. Contact: `gitasupersite.in` site or IIT Kanpur CSE. Log response here when received. Checked directly 2026-09-22: `www.gitasupersite.in` is a JS SPA behind Cloudflare Turnstile (curl dropped, headless Chrome gets challenge shell only); legacy `old.gitasupersite.in` is live and server-rendered but loads verse content via AJAX POST and exposes **no audio URLs** in served HTML; SPA bundle shows only a generic `/api` base. Scripted retrieval blocked technically as well — maintainer contact is the only path. |
| **Content** | All 700 verses, chapters 1–18, Devanagari text + audio, single consistent reciter |
| **Use for** | Canonical single-reciter GVR reference registry (FR-22) and ground truth for Vāksañcayaḥ transcript matching |
| **Local directory** | `data/gvr/gita_supersite/` (create only after permission is confirmed) |

---

### GVR-03 · Vedavani — Vedic Sanskrit ASR Corpus (sanganaka, Hugging Face)

| Field | Value |
|---|---|
| **Source name** | Vedavani: A Benchmark Corpus for ASR on Vedic Sanskrit Poetry |
| **Publisher** | sanganaka (Hugging Face); paper: ACL 2025, arXiv:2506.00145 |
| **URL (verified live 2026-09-23)** | `https://huggingface.co/datasets/sanganaka/Vedavani-Dataset` |
| **License** | **Apache-2.0** (dataset card + HF API) — reuse permitted with attribution |
| **Content** | 30,779 verse-unit recordings from the **Rig Veda (20,782) + Atharva Veda (9,997)**, ~54 h, Devanagari transcripts incl. prosodic markers, 80/10/10 official split |
| **Audio format** | WAV PCM_16 mono — 29,355 @ 16 kHz; 1,442 @ 44.1 kHz + 2 @ 48 kHz (see sweep flags) |
| **Acquisition date** | 2026-09-23 |
| **Acquired by** | Full HF clone (git LFS) by the project owner; local dir `Vedavani-Dataset/` (6.4 GB) |
| **Use for** | **Not Gita content** — general front-end validation pool (DataSources.md §2.1) and optional "generalizes beyond Gita" ablation. Not a GVR training corpus under the current scope. |
| **Local directory** | `Vedavani-Dataset/` (batches 1–4; CSVs train/validation/test) |

**File sub-table (group summary — per-file values in `Vedavani-Dataset/MANIFEST.csv`; swept 2026-09-23):**

| Group | Files | Result | Sweep date |
|---|---|---|---|
| All on-disk WAVs | 30,799 | 30,799/30,799 decode cleanly, 0 silent, all WAV/PCM_16 mono | 2026-09-23 |
| Indexed ↔ CSV | 30,779 | 0 missing, 0 CSV duplicates; duration vs CSV label: median \|Δ\| = 0.000 s, 0 files > 0.25 s | 2026-09-23 |
| Sample-rate anomalies | 1,444 | 1,442 @ 44.1 kHz + 2 @ 48 kHz (card claims 16 kHz); 1,436 in the `Rigvedha*` family (one recorder batch); resampled by D1 at use time — non-blocking | 2026-09-23 |
| Clipped (peak ≥ 0.99) | 299 | flagged, NOT excluded — mild peak scaling at front-end; barred from reference-material duty | 2026-09-23 |
| Borderline (0.985–0.99) | 87 | monitored | 2026-09-23 |
| Browser re-download artifacts `(1)` | 20 | sha-identical to originals → **excluded** via `EXCLUDED_FILES.csv` | 2026-09-23 |

**Label spot-check (§4 step 1) — 2026-09-23:** sample-based
programmatic listen-through executed (515-file sample: all 299
clipped, 87 borderline, both 48 kHz, 7 quiet, 120 stratified per
split); results in
`data/provenance/vedavani_listen_2026-09-23/` (auto-audit CSV + 12
spectrogram PNGs of the worst-case files for human verification).
Findings: 0 VAD/silence failures (min speech fraction 0.787, median
0.994); the 299 "clipped" files show **no sustained flat-topping**
(median flat-top 0.004%, max 0.035% — peak excursions, not audible
distortion); 82 files from the `Rigveda_39_*` and `RigVeda_*`
recorder batches carry a systematic DC offset (median 0.037 — removed
by the D1 front-end's per-utterance CMVN); the 24 shortest labels are
`'ॐ'` invocatory chants, correctly labeled. **Human ear verification — COMPLETE 2026-09-23:** the project owner
reviewed the 12 evidence-pack files (spectrogram + waveform renders of
the worst-case clipped, DC-batch, and stratified samples) at
`data/provenance/vedavani_listen_2026-09-23/` and confirmed genuine
Vedic recitation content consistent with labels and splits. §4 step 1
sample-based verification is therefore complete: Vedavani is cleared
as the front-end validation pool (DataSources.md §2.1). Standing
restriction unchanged: the 299 peak-flagged files remain barred from
reference-material duty, and any verse-level classification use
requires a text-based re-split (leak rule in Review.md).

---

### GVR-04 · ASR-Sanskrit (komalsai234, Hugging Face) — EXCLUDED

| Field | Value |
|---|---|
| **Source name** | ASR-Sanskrit |
| **URL** | `https://huggingface.co/datasets/komalsai234/ASR-Sanskrit` |
| **License** | Apache-2.0 (dataset card) |
| **Content** | 72 parquet shards (~6.9 GB), 30,000 train + 7,215 test examples |
| **Disposition — EXCLUDED 2026-09-23** | Schema verified locally: `input_features` = precomputed Whisper mel features, `labels` = token IDs. **No raw audio.** Cannot feed the D1 MFCC front-end (needs waveforms). No pipeline use; kept at repo root only as the owner's downloaded artifact. |

---

## Sources Checked — Excluded or Not Yet Acquired

| Source | Status | Reason | Checked date |
|---|---|---|---|
| Deshpande *Saṃskṛta-Subodhini* (UMich) | **DEAD LINK — unrecoverable** | DNS timeout on `www.umich.edu/~iinet/csas/publications/sanskrit/audio.html`; Wayback CDX check 2026-09-22 shows **zero successful audio captures** for any `umich.edu` Sanskrit audio path (only 404 captures of attempted URLs). Cannot acquire from any channel. | 2026-09-22 |
| Forvo.com (Sanskrit crowdsourced) | **PLAN SET — manual only** | ToS prohibits bulk/automated scraping. Plan (2026-09-22): after the SPD word list is finalized from Hall/Loyola material, download the ~20–30 word clips **manually, one at a time**, logging each clip's speaker username/country in this file; fluency is unverified, so Forvo clips serve as cross-check material only, never sole references. | 2026-09-22 |
| archive.org Gita audio (Ranganathan, Paudwal) | **Excluded** | No `licenseurl` metadata — cannot enter corpus per DataIntegrity.md Rule 2 without explicit permission. Confirmed excluded. | 2026-09-22 |
| mahabharata-audio-2018 (GitHub) | **Checked — DEAD END for Gita** | Org has exactly 6 public repos (parva01-001-100, parva01-101-233, parva02, parva03, parva04, parva12-001-100) — **no Bhishma Parva repo; no Gita audio**. **License resolved 2026-09-23:** project page declares **CC BY-SA 4.0** (per-file named reciters; archive item `mahAbhArata-mUla-paThanam-GP` carries per-file creator metadata but **no `licenseurl` field** — license basis is the project page's declaration). Zips held unextracted pending a use decision. | 2026-09-23 |

---

*Update this file whenever a file is downloaded or a source is
checked. Cross-reference the Review.md Data Integrity Sweep entry.
Never mark a source "acquired" here without a matching sweep entry in
Review.md.*
