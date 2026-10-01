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

### Phase 2 (Resource Gathering) — corpus acquisition, continued
[continued session, same date]

**Trigger:** DataSources.md §4 acquisition order executed against the
downloaded sources, with the §5 open items resolved. Per the
instruction governing this session: no advancement on the acquisition
track until the Gita-specific GVR registry and at least one SPD
reference word are downloaded, swept, and logged with real counts.

**What was checked and acquired (in §4 order):**

1. **Vāksañcayaḥ (§4 step 1) — layout, transcripts, license, and the
   Gita-subset question, all resolved from the actual archive:**
   - Layout (DataSources §5 item, resolved): `spNNN/spNNN-NNNNNN_TEXTID.mp3`,
     45,953 MP3s across 54 speaker dirs; per-speaker transcripts at
     `Transcript/Devanagari/spNNN.txt` and `Transcript/SLP1/spNNN.txt`,
     TSV `<uttID>\t<text>`; official train/val/test/OOD speaker split
     printed in the corpus README (matches design D3's per-reciter
     split policy).
   - License (PROVENANCE discrepancy, resolved): the corpus's own
     README states **CC BY-NC 4.0**; the AIKosh "CC0" label is wrong.
     Corpus README governs.
   - **Gita-subset check: NEGATIVE.** Full transcript grep for
     canonical verse markers: `धृतराष्ट्र उवाच`,
     `कर्मण्येवाधिकारस्ते`, `यदा यदा हि धर्मस्य`, `चञ्चलं`,
     `समवेताः युयुत्सवः` → **zero hits**. The `GB_*` family (2,161
     utterances, all in sp006) is **Śaṅkara Bhāṣya prose**; the one
     `धर्मक्षेत्रे` hit is a retold narrative (sp022, text-ID `_008`)
     rendering BG 1.1 as story prose. The AIKosh "Bhagvadgita" tag
     resolves to bhāṣya readings, not verse recitations. **Conclusion:
     Vāksañcayaḥ cannot supply the FR-22 verse registry.** Retained as
     the general front-end validation pool (§2.3); archive held
     unextracted as the provenance-anchored master copy.
2. **Gita Supersite (§4 step 2) — reuse terms checked directly;
   acquisition remains BLOCKED:** the user's observation that
   `www.gitasupersite.in/srimad/texts` "has nothing in it" was
   confirmed and root-caused: the current site is a JS SPA behind
   **Cloudflare Turnstile** (plain fetches dropped; headless Chrome
   receives only the challenge shell; the app bundle exposes a generic
   `/api` base with no usable static endpoints). The legacy
   `old.gitasupersite.in` is live and server-rendered, but verse
   content loads via AJAX POST and the served HTML contains **no audio
   URLs**. So bulk retrieval is blocked **both by the still-unstated
   license and technically**. Maintainer contact is the only path to
   verse audio here; a draft contact request is queued (Open Item 5).
3. **SPD reference audio (§4 step 3):**
   - Deshpande *Saṃskṛta-Subodhini* (§3.2): `umich.edu/~iinet/csas/...`
     DNS-dead — confirmed excluded (PROVENANCE.md excluded table).
   - **Hall *Sanskrit Pronunciation* (§3.3): ACQUIRED and swept.** The
     earlier download attempt had left **0-byte files** (skpro_00,
     skpro_02) — a DataIntegrity violation-in-waiting, caught and fixed
     by re-download with referer header. All 5 MP3s now valid MPEG-1
     L3, 64 kbps, **16 kHz mono** (matches the D1 front-end rate).
     DataIntegrity §4 automated sweep run per file with real values
     (durations 67.5–1237.3 s; rms −28 to −31 dB; 1,696 speech
     segments total) — recorded in PROVENANCE.md SPD-01 sub-table.
     **Per-file label spot-check (listen-through) still pending**; the
     files are not pipeline-eligible until that is done.
   - Forvo (§3.1): deliberately deferred until the SPD word list is
     finalized; manual per-clip downloads only, per its ToS.
4. **mahabharata-audio-2018 (§1.3) — checked, dead end:** the org has
   exactly 6 public repos (parva01-001-100, parva01-101-233, parva02,
   parva03, parva04, parva12-001-100) — **no Bhīṣma Parva repo, hence
   no Gita audio**. The parva zips downloaded earlier are held
   unextracted pending a keep/delete decision.

**Data Integrity Sweep (source-level, §4 columns; per-file detail in
PROVENANCE.md):**

| Item | Samples | Corrupted found/excluded | Duplicates | Cross-split leaks (GVR only) | Provenance on file? | Label spot-checked? |
|---|---|---|---|---|---|---|
| Hall skpro_00–04 (SPD refs) | 5 | 2 found (0-byte) → re-fetched, 0 remain | 0 | — | yes (SPD-01) | automated pass done (0 VAD/clip/DC fails); **owner ear check staged** (`spd_listen_2026-09-23/CHECKLIST.md`) |
| Loyola/Cahill (SPD-02, Wayback-recovered) | 63 | 1 found (Wayback HTML interstitial) → re-fetched, 0 remain | 0 (sha256 distinct) | — | yes (SPD-02) | automated pass done (min speech frac 0.449 = pauses, not silence; item counts match paradigms); **owner ear check staged** incl. boosted noun-set renders; noun1–9 quarantine unchanged pending the intelligibility call |
| Vāksañcayaḥ (GVR pool) | 45,953 (held unextracted) | 0 at transcript level | n/a | n/a (registry unused) | yes (GVR-01) | GB family checked (Gita question) |
| Vedavani (GVR-03, front-end pool) | 30,799 on disk / 30,779 indexed | 0 corrupted; 299 clipped + 87 borderline flagged; 1,444 sample-rate anomalies (resampled at use) | 20 sha-dup `(1)` extras → excluded (EXCLUDED_FILES.csv) | n/a (not GVR training data) | yes (GVR-03) | done — 515-file sample + owner ear check (2026-09-23) |
| ASR-Sanskrit (GVR-04) | 72 parquet shards | n/a — no raw audio (Whisper features first only) → excluded | — | — | yes (GVR-04, excluded) | n/a — excluded |
| Vedavani label listen-through (GVR-03, §4 step 1) | 515-file sample (all 299 clipped, 87 borderline, 2×48 kHz, 7 quiet, 120 stratified per split) | 0 VAD/silence fails (min speech frac 0.787); no sustained flat-topping in the clipped set (max 0.035% samples); 82-file DC-offset batch finding (Rigveda_39_*/RigVeda_*, median 0.037 — CMVN-removable) | 0 new (20 `(1)` dups already excluded) | n/a (not GVR training data) | yes (GVR-03) | **done 2026-09-23 — automated 515-file pass + owner review of the 12 evidence-pack files** |
| Supersite / mahabharata Gita | 0 acquired | — | — | — | n/a (blocked) | — |

**Gate status (per this session's governing instruction):** SPD half
**met** — a named-scholar reference-recitation set is downloaded,
swept, and logged (label spot-check pending before pipeline use). GVR
registry half **externally blocked**: all four candidate Gita sources
(Supersite, Vāksañcayaḥ, mahabharata-audio, archive.org) are now
verified dead ends or permission-gated, each with the check logged.
The D4 self-recording program (approved design) plus the new
recording-protocol template is the remaining path to the FR-22
registry; Phase 4 work may proceed on modules that do not depend on
the registry (front-end first), per Development.md phase rules.

**Follow-up unit (same date): SPD reference-recitation sources
installed (DataSources.md §3).**

- **§3.4 Loyola/Cahill — RECOVERED.** The live site is dead
  (`www.loyno.edu/~tccahill/...` 302-redirects to
  `people.loyno.edu`, which does not respond at all; HTTPS fails).
  The Internet Archive Wayback Machine, however, holds **63 MP3
  captures** (2011-06-06) of the full sound-file set — enumerated via
  the CDX index and downloaded 63/63 with `web.archive.org/web/<ts>id_/
  <original>` URLs. One file (`yad_fem.mp3`) initially returned a
  Wayback HTML page instead of audio; re-fetched from its single
  capture → valid MPEG. Content: traditional recitations of
  grammatical paradigms — nominal declensions by gender (43),
  pronouns (12), verb conjugations by class (8), verse/exercise
  readings; **74.9 min total, 44.1 kHz stereo** (resampled by the D1
  front-end at use time).
- **§4 sweep run immediately on the new source (real values):**
  63/63 valid MPEG; no clipping (max peak < 0.99); **no content
  duplicates** (sha256 all distinct); rms −35.7 to −52.0 dB. Quality
  quarantine applied: the `noun1–noun9` set is very low-level (rms
  −49 to −52 dB; `noun1_deva.mp3` peak 0.047) — those files are NOT
  eligible as reference material until the listen-through confirms
  intelligibility. Per-file data in
  `data/spd/loyola_cahill_sound_files/MANIFEST.csv`; provenance entry
  SPD-02 added to `PROVENANCE.md`.
- **§3.2 Deshpande/UMich — conclusively unrecoverable.** Wayback CDX
  domain-wide check: **zero successful audio captures** for any
  `umich.edu` Sanskrit audio path (only 404 captures of attempted
  URLs, 2012–2013). Excluded-sources table updated from "check
  Internet Archive" to "cannot acquire from any channel"; the named-
  scholar reference role is now covered by SPD-01 (Hall) + SPD-02
  (Loyola).
- **§3.1 Forvo — plan fixed, no downloads:** manual per-clip
  downloads only (ToS), after the SPD word list is finalized;
  each clip's speaker username/country to be logged in
  `PROVENANCE.md`; cross-check material only, never sole references.

**SPD reference-source roster after this unit:** Hall §3.3 ✓ (5 MP3s,
swept), Loyola §3.4 ✓ (63 MP3s, swept, partially quarantined), Forvo
§3.1 (planned, manual), Deshpande §3.2 ✗ (unrecoverable). All
downloads from this unit were swept immediately (no un-swept batches).

**Follow-up unit (2026-09-23): manually downloaded corpora verified,
swept, and ledgered.** The repo acquired new material outside the
agent sessions (owner's manual downloads at the repo root). Per the
Phase 2 rule, each was identified from its own bytes, not assumed,
then swept before any ledger claim:

1. **Inventory of new material:** `ASR-Sanskrit/` (72 parquet shards,
   6.9 GB), `Vedavani-Dataset/` (full HF clone, 6.4 GB, batches 1–4 +
   split CSVs), `Vedavani-main.zip` (16 KB, the project's GitHub code),
   `Vaksanca-master.zip` (17 MB, Vāksañcayaḥ Kaldi recipe — matches
   GVR-01's companion), five `parvaNN-*-master.zip` files (3.1 GB
total), and the Vāksañcayaḥ dataset-metadata PDF.
2. **ASR-Sanskrit (§2.2) — EXCLUDED, no raw audio.** Identified via
   its `.git` remote as `komalsai234/ASR-Sanskrit` (Apache-2.0).
   Local parquet schema probe: `input_features` (list<list<float>> =
   precomputed Whisper mel features) + `labels` (token IDs) — **no
   waveform column exists**, so it cannot feed the D1 MFCC front-end.
   DataSources §2.2 and PROVENANCE GVR-04 updated with the disposition.
3. **Vedavani (§2.1) — ACQUIRED + SWEPT (GVR-03).** Identified via its
   `.git` remote as the genuine `sanganaka/Vedavani-Dataset`
   (Apache-2.0; ACL 2025). Index integrity: 30,779 CSV rows ↔ 30,779
   on-disk files, **0 missing, 0 duplicates, 54.38 h** (matches the
   paper's stats). Full DataIntegrity §4 sweep of all 30,799 on-disk
   WAVs (`Vedavani-Dataset/MANIFEST.csv`): 30,799/30,799 decode
   cleanly; 0 silent; all PCM_16 mono; **1,444 not at the card's
   claimed 16 kHz** (1,442 @ 44.1 kHz + 2 @ 48 kHz; 1,436 in the
   `Rigvedha*` family = one recorder batch — resampled by D1 at use
   time, non-blocking); **299 clipped (peak ≥ 0.99, 0.97%)** + 87
   borderline flagged (not reference material); duration vs CSV label:
   median |Δ| = 0.000 s, max 0.000 s. The 20 `(1)`-suffixed extras are
   sha-identical browser re-download artifacts → excluded via
   `EXCLUDED_FILES.csv`. **Not Gita content** (Rig + Atharva Veda) —
   front-end validation pool per §2.1, not a GVR training corpus.
4. **mahabharata-audio-2018 parva zips — verified, license resolved,
   still a Gita dead end.** All five zips open cleanly; their READMEs
   confirm the Gita-Press-edition crowdsourced project. `parva12`
   contains **no audio at all** (README/.travis.yml/.gitignore only,
   4 entries). License **RESOLVED**: the project page
   (`sanskrit.github.io/groups/dyuganga/projects/audio/mbh-audio/`)
   declares **CC BY-SA 4.0** project-wide with per-file named
   reciters; the archive item `mahAbhArata-mUla-paThanam-GP` carries
   per-file creator metadata but **no `licenseurl` field** — the
   license basis is the project page's declaration. Status unchanged
   for GVR: 3 parvas only, no Bhīṣma Parva, no Gita audio. §1.3 and
   the PROVENANCE excluded table updated accordingly.
5. **User-supplied Google Drive folder — verified DUPLICATE of GVR-03
   (Vedavani); nothing to install.** Folder
   `1bDE8Vlm9Be-Lf2Tab12SWQ5vrwfvTf0S` (public, checked 2026-09-23)
   holds `Audio_files/` + `train/validation/test.csv`. Inspection via
   the public folder listing: **5,499 unique WAVs, exclusively
   `Atharvaveda_Kanda_1..13`** (Vedavani naming). Identity checks: all
   5,499 filenames already exist in the local Vedavani index (**0 new
   files**); the three CSVs are **byte-identical row-for-row** to the
   local `Vedavani-Dataset/{train,validation,test}.csv`
   (24,623/3,078/3,078 data rows, same file→split assignment); 20
   files sampled across all 12 kandas → **20/20 sha256 match** against
   `MANIFEST.csv`. Disposition: **no download into the corpus** —
   installing would only create sha-duplicates, which DataIntegrity
   §4 excludes. Logged in PROVENANCE.md GVR-03 as a corroborating
   availability mirror; content inherits GVR-03 license/provenance
   (Apache-2.0, sanganaka). Nothing further pending on this source.

### Phase 4 (Coding) —

**Unit 1 (2026-09-23): shared front-end module — built, tested, and
verified against the library path.**

- `samskrita_dhvani/frontend.py` — implements design D1 exactly:
  `FrontendConfig` (frozen dataclass exposing every parameter as a
  named, documented attribute — FR-02: sr=16000, pre-emphasis 0.97,
  25 ms/10 ms → 400/160 samples, Hamming, 26 mel filters HTK-scale
  0–8 kHz, 13 MFCC kept with c0 discarded, Δ/ΔΔ width 9, CMVN on),
  `load_audio_16k` (any soundfile format → 16 kHz mono float32),
  `vad_speech_fraction` / `vad_trim` (WebRTC VAD; the DataIntegrity
  §1.1 near-silence rule is applied via the fraction, not silently),
  `extract_features` (library path → **(T, 39) float32**, the
  compatibility contract for both branches), `hand_mfcc`
  (course-math implementation: centered framing, periodic Hamming,
  raw rFFT power, mel-spaced triangular filterbank built by hand,
  10·log10 with amin floor, hand-written orthonormal DCT-II —
  verified equal to scipy's to 7.2e-15), and `cross_check_mfcc`
  (FR-03 measurement surface).
- `tests/test_frontend.py` — 20 tests, all on clearly labeled
  synthetic fixtures (NFR-02): pre-emphasis formula/DC behaviour,
  frame geometry (400/160, tail padding), config immutability +
  documented values, output contract (T,39) float32, CMVN
  zero-mean/unit-variance, resampling duration preservation, VAD
  fraction/trim behaviours incl. the §1.1 rule, and three FR-03
  cross-check properties (frame-count equality, exact-agreement on a
  steady tone, scale-invariance under gain).
- **FR-03 measured numbers (actual runs, per NFR-01):** hand-vs-librosa
  static-MFCC max-abs-difference = **1.3e-7** (synthetic steady tone,
  101 frames), **≈5e-8 mean / 2.2e-7 max** (real Vedavani speech,
  `Atharvaveda_Kanda_10_0001.wav`, 800 frames, provenance GVR-03),
  **2.2e-7 max** (real 44.1 kHz→16 kHz resampled speech,
  `Rigvedha_006_0125.wav`, 853 frames). The two paths are the same
  math to float32/float64 noise.
- **Bugs the cross-check caught and fixed during the build** (worth
  keeping in the log as evidence the FR-03 exercise did its job):
  (1) mel filter edge points evenly spaced in **Hz** instead of mel
  (classic MFCC bug — filters landed at ~2.8× their intended
  frequencies); (2) Hamming window computed on raw indices instead of
  n/length; (3) power spectrum normalized by /fl and then by
  w.sum()² — both wrong; librosa's STFT applies **no** magnitude
  normalization, and with a fixed amin floor the scale must match
  exactly or floor clamping diverges (c0-shift-only intuition fails).
- **Test run:** `python -m pytest tests/` → **20 passed**
  (1 known benign warning: webrtcvad's pkg_resources deprecation,
  covered by the setuptools<81 pin).

**Unit 1b (2026-09-23): FR-04 optional LPCC + formant/pitch path —
built and tested.**

- `lpcc()` — course UNIT II_LPCC steps in order: pre-emphasis → frame
  blocking (the module's shared 25 ms/10 ms centered Hamming framing,
  one definition per front-end) → autocorrelation (p+1 values, exact
  linear lags via zero-padded FFT) → **Durbin method**
  (`_levinson_durbin`, reflection coefficients clamped to ±0.999 so
  degenerate frames stay stable) → **direct recursive cepstral
  conversion** (`_lpc_to_ceps`, c_m = a_m + (1/m)Σ k·c_k·a_{m−k},
  a_m zero-extended beyond p so Q > p works — course: "Q may be
  greater than p, Q ≈ 3/2 p"). Defaults p=14 (course range 8–16),
  Q=21; c0/log-gain excluded per the course's V(t) = [c1..cQ, Δc1..ΔcQ];
  optional Δ via the shared regression stage.
- `formants_pitch()` — Praat Burg formants (25 ms windows = D1 frame
  length, 10 ms steps) + pitch, sampled **exactly at the MFCC frame
  centers** (grid count matches librosa's centered framing
  exactly), so the FR-11 per-axis breakdown can join formant and MFCC
  features frame-by-frame. Unvoiced/unmeasured → NaN; intended for
  word-length clips (SPD), not hour-long files.
- **Verification (9 new tests, all synthetic per NFR-02):** Durbin
  recovers a known AR(2) process (a within 0.05); degenerate-frame
  stability under reflection clamping; c1 = a1 identity; Q=10 > p=4
  regression guard (the zero-extension bug was caught here before it
  shipped); LPCC shape/dtype/frame-count parity with the MFCC path;
  spectral-envelope prominence near synthetic resonances; formant/pitch
  grid alignment; formant recovery at 750/1200 Hz; pitch median within
  10 Hz of the fixture F0 (150 Hz). `pytest tests/` → **29 passed**.
- **Fixture lesson worth keeping:** the first vowel fixture mixed
  150 Hz harmonics with non-harmonic 700/1200 Hz sines — Praat's pitch
  track read 172 Hz, which is the honest analysis of an acoustically
  ambiguous signal (composite period 100 Hz). Fixed by placing
  resonances at 750/1200 Hz (true harmonics). A debugging reminder
  that a failing analysis can be a correct analysis of a bad fixture.

**Unit 2 (2026-09-23): FR-12/FR-13/FR-22 registry scaffolding —
built and tested.**

- `samskrita_dhvani/registry.py` — label/registry layer for both
  branches:
  - **FR-13 (Done):** `devanagari_to_iast` / `iast_to_devanagari` via
    `indic_transliteration` (ISO: IAST scheme, verified in Phase 2),
    plus `transliteration_round_trip_ok` (Dev→IAST→Dev must be the
    identity — enforced on every load, not just at build time) and
    `harvard_kyoto_slug` (deterministic ASCII word-IDs that preserve
    length/retroflex distinctions: tāla→tAla vs tala→tala stay
    unique).
  - **FR-12 (scaffold done):** `SpdWord`/`SpdWordlist` with the 29-word
    seed list over five difficulty axes (retroflex-dental,
    aspirated-unaspirated, vowel-length, consonant-cluster, control),
    each word carrying Devanagari, IAST, HK word-ID, difficulty axis,
    optional minimal-pair ID, reference-audio path, and provenance.
    Lexical correction over the first draft: tāla/tala reclassified as
    a vowel-LENGTH pair (both dental — not retroflex/dental), and the
    pāta/pāṭa pair is the true retroflex/dental minimal pair; aspirate
    pairs (dharma/dhāma, pala/phala, kāma/khāga) chosen to be minimal
    in aspiration only. JSON round-trip loader rejects rows with
    missing provenance (DataIntegrity Rule 2) or failed round-trips.
  - **FR-22 (scaffold done):** `VerseEntry`/`GvrRegistry` —
    verse_id ↔ audio_file rows with reciter, split, optional text, and
    provenance. Design correction: verse_id is deliberately NOT unique
    (multiple recitations per verse per Implementation.md §5.1);
    `audio_file` is the unique key. `assert_no_split_leak` enforces
    the per-reciter split policy (no verse may appear under different
    splits for the same reciter) — the NFR-04/FR-23 hazard made
    load-blocking, matching the Vedavani finding (609 verse texts in
    >1 split). Schema is registry-of-record for the D4 self-recording
    program and any future permissioned source.
  - **Provenance gate (Rule 2):** shared `PROVENANCE_REQUIRED_KEYS`
    (source_id, acquired_on) enforced in both loaders; builders accept
    a provenance dict for the whole batch or mark rows `PENDING`
    (which explicitly marks them pipeline-ineligible).
- **Test run:** 20 new tests (all synthetic fixtures per NFR-02) —
  round-trip identity for every seed word, HK slug distinctness,
  FR-12 minimum count + pair grouping, JSON round-trips, Rule-2
  rejection, duplicate-ID/audio_file rejection, split-leak detection
  (in-memory and from-file), bad-split rejection.
  `pytest tests/` → **49 passed** (29 front-end + 20 registry).
- **Honest scope note:** FR-12/FR-22 are *format-complete*; the FR-12
  reference-audio column stays empty until the Hall/Loyola ear check
  passes (CHECKLIST staged, owner action), and the FR-22 registry has
  zero entries until the Gita permission path or D4 self-recordings
  produce audio. The scaffolding is built so that both populate by
  dropping data in, with every gate already enforced.

**Unit 3 (2026-10-01): D2 SPD scorer — built, tested, and wired to
the seam.** (Numbered per the Implementation.md Phase 3 module
layout; the "Unit 5" entry above is the frontend wiring pass, which
this completes the backend half of.)

- **`samskrita_dhvani/spd_scorer.py` implements the approved D2
  formula verbatim** (the Phase 3 sign-off text is the binding
  spec): with CMVN-normalized static MFCCs (first 13 columns of the
  D1 (T, 39) output) and DTW alignment,
  `D = mean over aligned frame pairs of ‖Δmfcc_13‖₂` and
  `sim = 100·exp(−D/D₀)`. There is **no arbitrary constant**: D₀ is
  the per-word mean DTW distance of known-correct recitations to the
  canonical reference, stored in `data/spd/calibration.json`
  (schema version 1, provenance-carrying) and rebuilt via
  `CalibrationBuilder` on corpus change. By construction a
  recitation at the calibration population's mean distance scores
  100·e⁻¹ ≈ 36.8, and the D = 0 boundary maps to exactly 100.
- **Per-axis breakdown (FR-11), same mapping style with measured
  per-word scales (D₀ᶠᵒʳᵐ, D₀ᵈᵘʳ):** vowel/formant axis = mean
  relative formant mismatch (Praat Burg formants on the D1 frame
  grid, averaged over frames voiced in both clips); consonant/
  spectral axis = MFCC-DTW restricted to likely-consonant frames of
  the attempt (low-pitch-flatness + low-energy mask, guaranteed
  non-empty); duration axis = |log(vad-trimmed duration ratio)|,
  symmetric in r ↔ 1/r.
- **API seam (`api.py`) — the honesty chain got more precise, not
  more permissive.** `/api/spd/score` now walks: 404 `unknown_word`
  → 422 `invalid_audio` → 422 `near_silence` (DataIntegrity §1.1:
  ≤ 10% speech frames; measured via the real D1 VAD) → 503
  `reference_unavailable` (no ear-verified clip for the word) → 503
  `calibration_unavailable` (no measured D₀; the D2 formula forbids
  guessing the scale) → 200 with the exact FR-11 shape
  `{similarity_pct, vowel_score, consonant_score, duration_score,
  mfcc_dtw_score, reference_word}`.
- **Measured this session (actual runs):** WebRTC VAD speech
  fraction on the 220 Hz sine fixture = **0.091** — below the gate,
  so the tone now gets an honest *invalid input* ("Only 9% of frames
  contain speech…") instead of any 5xx; the harmonic-stack fixture
  measures **0.909** and proceeds to the 503 chain. Live-server
  smoke: tone → `422 near_silence`; speech-like clip → `503
  reference_unavailable` naming the expected file path and the
  pending Hall/Loyola ear check. UI honesty lines updated
  ("Design D2 — built, data pending").
- **Tests:** 21 scorer unit tests (synthetic vowel fixtures per
  NFR-02): static-MFCC block identity + CMVN zero-mean; DTW D = 0
  on identical inputs, distance grows with formant distortion, path
  monotonicity + spanning (starts (0,0), ends (Tₐ−1, Tᵣ−1)); sim
  mapping boundary/monotonicity/D₀-scale properties; formant axis
  ≈ 0 on identical clips, grows with formant shift, raises on
  silence; duration symmetry; consonant mask never covers the
  loud voiced nucleus; end-to-end good-over-bad ranking; the 200
  contract through the API with test doubles for exactly the two
  data prerequisites. API contract tests updated for the new chain
  (the old "503 until D2 lands" stub is replaced by the three
  new-mode tests + one 200-path test). `pytest tests/` → **84
  passed** (was 60).
- **Honest limits:** no real-word 200 can occur yet — that requires
  the ear check to pass, reference clips to be cut (FR-12), and the
  D5 calibration recordings to be made. The 200 path is verified
  with the reference file and measured D₀ supplied as explicit test
  doubles; everything upstream of them (features, DTW, mapping,
  response shape) is the real production code.

**Unit 4 (2026-10-01): D3 GVR recognizer — built, tested, and wired
to the seam.**

- **`samskrita_dhvani/gvr_classifier.py` implements the approved D3
  topology verbatim** (Phase 3 sign-off text is the binding spec):
  one GaussianHMM per verse, **6 states, left-to-right no-skip**
  (self + advance-by-one only), **diagonal Gaussians**,
  **hand-initialized startprob/transmat** before `fit()` (one-hot
  start; 0.5/0.5 self/advance rows; `init_params=""` so nothing
  auto-initializes the topology), Viterbi `decode()` across all
  verse HMMs → verse ID + log-likelihood **gap as confidence**
  (softmax over the closed set — a monotone map of the pairwise
  gaps: a verse that beats every other by a wide margin scores near
  1, a near-tie near 1/n). Features are the D1 (T, 39) matrix — one
  feature definition for both branches (Ground Rule 4).
- **Two bugs the synthetic-fixture tests caught before this shipped**
  (kept in the log as evidence the NFR-02 discipline works):
  (1) **Split leak in `train()`** — the first draft consumed ALL
  registry rows; the test asserting `n_training_clips == 2` (2 train
  + 1 test per verse) caught `== 3`. Training now skips every
  non-`train` split; held-out data stays held out.
  (2) **State collapse with k-means emission init** — hmmlearn's
  k-means start on near-stationary speech features parked several
  states on the same region; the L-R topology then never visited
  them ("Some rows of transmat_ have zero sum" → NaN startprob →
  `ValueError` at decode). Fix: HTK-style **equal-segmentation
  emission init** (each state's Gaussian starts at its equal slice
  of the concatenated training sequence, variance floored at 1e-3),
  plus a post-fit degeneracy check (`_assert_fitted_lrhmm`) that
  refuses to store a model with NaN parameters or dead states — a
  verse needing more/better audio must say so, not silently repair.
- **Fixture lesson (second of the project):** the first synthetic
  verses were stationary vowels — and D1's per-utterance CMVN
  *correctly* strips stationary spectral signatures, making every
  "verse" identical to the classifier. The fixtures now render each
  verse as a fixed **sequence of four formant-target phones** (with
  per-recitation F0/timing jitter + noise), i.e. temporal structure
  that survives CMVN. A classifier can only recognize what the
  features keep.
- **API seam (`api.py`):** `/api/gvr/recognize` now walks: 422
  `invalid_audio` → 422 `near_silence` (§1.1) → 503
  `model_unavailable` (no trained artifact at `data/gvr/model.pkl`,
  with the registry state named) → 200 with the exact FR-21 shape
  `{top_match: {verse_id, devanagari, gloss, confidence},
  candidates: [{verse_id, confidence}, ...]}`. Verse text is what
  the training registry rows carried (`text_for`). Confidence
  values are transmitted unrounded: runner-up softmax shares can
  legitimately **underflow to exact 0.0** in float64 (exp(−2000)
  IS 0.0 to the machine) — an honest "vanishingly unlikely", not a
  bug, and `round(·, 4)` would have hidden it. `/api/status`
  `gvr_scorer_available` now flips to true when a trained model
  artifact actually exists (it reads the file; no flag is hardcoded).
- **Measured this session (actual runs):** training 4 synthetic
  verses (2 train recitations each) + decoding 4 held-out renditions
  → **4/4 correct top-1** in the unit tests, rank-monotone softmax
  shares summing to 1; persistence round-trip reproduces identical
  predictions. Live-server smoke: speech-like clip → 503 with the
  new message; `gvr_scorer_available` false until a model exists.
- **Tests:** 11 recognizer tests (topology invariants before/after
  fit, train-split-only accounting, too-short-clip rejection,
  held-out recognition, candidate ranking/normalization, text
  capture, schema-versioned save/load incl. wrong-schema rejection)
  + 3 new API contract tests (tone→422, speech→503 naming the
  artifact path, and the 200 path with a model trained on synthetic
  verses). `pytest tests/` → **96 passed** (was 84).
- **Honest limits:** the recognizer cannot be trained for real until
  the FR-22 registry holds actual recitations (Gita sources blocked,
  D4 self-recordings pending — Open Item 5). The 200 path is
  verified with a model trained on synthetic verses; everything in
  the production path (features, topology, EM training, Viterbi,
  response shape) is the real code. Accuracy-vs-data-per-verse
  curves and the confusion matrix (NFR-20) remain Phase 5 work on
  real data.

**Unit 5 (2026-09-30 → 10-01): Stitch exports wired to the live API —
all four screens functional.**

- **Export inventory (step 1 of the wiring order).** Two complete
  Stitch sets existed under `web/stitch_exports/` (`app/` and `web/`).
  The `web/` set is canonical (matches Frontend.md §3.1–3.4: GVR
  candidates + inconclusive state, status 3-card layout, the
  Chrome/Firefox footer); the `app/` set drifted off-spec ("Verse
  Scansion Inspector") and is left untouched as an alternate. Working
  copies were moved from `web/live/` to `web/` root — `api.py` serves
  `PROJECT_ROOT/web` with `html=True`, so the pages must sit at
  `web/index.html`, `/spd.html`, `/gvr.html`, `/status.html`. The
  exports remain byte-pristine.
- **`web/app.js` (new, shared).** Typed `fetchJSON` (network / 4xx /
  5xx become explicit Error objects with `.kind`; the UI renders
  them, it never falls back to placeholder data), `Recorder`
  (getUserMedia + MediaRecorder with a live level meter), and
  `toWav16k` (decodeAudioData → OfflineAudioContext at 16 kHz mono →
  16-bit PCM WAV). The transcode step is required, not cosmetic:
  MediaRecorder emits webm/opus, which the backend's soundfile
  decoder cannot read; the browser resamples to the D1 analysis rate
  client-side. `wireNav()` replaces Stitch's placeholder nav
  (corpus-reader, spectrogram-workbench, …) with the four real
  routes and marks the active page.
- **Per-screen wiring (surgical edits only; Stitch layout kept):**
  - **Home** — static routing only; fabricated telemetry neutralized:
    "Acoustic Model: Active [Kaldi/PyTorch]", the 48.0 kHz/24-bit +
    "Kaldi-HMM / SD-1.4" pipeline card, the p=0.942/0.038 hypothesis
    bars, "SD-PhonoNet-v1.4b", the ±4.2 ms / 48-scholars claims, the
    "WebAssembly local inference" privacy line, and the © 2025
    footer. Each is replaced with an honest statement of what exists
    today (D2/D3 pending, D1 front-end built, audio never leaves the
    machine) or removed.
  - **SPD Practice** — the word picker renders the live FR-12 list
    from `GET /api/words` (27 words; the filter pills map the five
    real difficulty axes, not Stitch's invented categories);
    recording via `Recorder` with a real timer; upload fallback
    (hidden file input) accepts .wav/.flac/.mp3/.webm/.m4a/.ogg;
    Submit posts `{word_id, audio}` to `POST /api/spd/score` and
    renders FR-11 per-axis bars **only** from a 200 response; 503 /
    422 / 404 / network each get their own explicit message.
    Fabricated content removed: the pre-filled कृष्ण search value,
    the F1/F2/VOT/MĀTRĀ readouts (420/1980 Hz, 14 ms, 2.0), fake
    "48 kHz · 24-bit / SNR 32 dB", the simulated 00:01.42 timer, the
    static waveform bars + /k/ /ṣ/ /ṇa/ tics, the 78% result with
    84/71/91/78% bars and the "Mūrdhanya Locus Deviation…"
    paragraph, the fake "Pandit K. Sharma" reference bar, and the
    WebAssembly privacy line. Reference playback is honestly
    disabled (ear check pending): the button renders hidden with the
    reason stated in the UI.
  - **GVR Recognition** — same recorder/upload/submit pattern against
    `POST /api/gvr/recognize`. The export's two result states now
    carry real meaning: the match card renders only from a 200
    `{top_match, candidates}` response, and the "Inconclusive Match"
    card renders the API's explicit 503 `model_unavailable` /
    not-confidently-recognized / network states (title, flag chip,
    and body all driven by the response). Fabricated content
    removed: the 00:18.4 timer, static SVG waveform, F0/LUFS/SNR/
    noise-gate readouts, "Viterbi 1,420", the 94.2% + verse 9.26
    text/gloss + three candidates, the Log-P/KLD values, and the
    TextGrid/attention-matrix buttons. Pre-result state: both cards
    hidden, status line "no submission yet".
  - **Status** — all three cards, the audit table, and the manifest
    download button are bound live to `GET /api/status` (plus `GET
    /api/words` for the per-axis word breakdown): word count,
    reference-audio availability, verse coverage (honest "no
    entries" quoting the registry detail), and the sweep card
    (honest "not found on this machine" where the manifest is
    absent). Removed: fake "29 / 12 stems / 48kHz TextGrid", the
    142-file / 4.82-hr / 2025-05-18 sweep, "SHA-COMMIT
    rev-2025.04-a12", "PyTorch 2.3 · Kaldi v5.5", the fabricated
    checksum drawer, and the hardcoded JSON the download button used
    to emit (it now downloads the live response).
- **Ground Rule 1 verification:** a grep sweep for fabricated tokens
  (SD-PhonoNet, Kaldi, PyTorch, 48 kHz, SNR, 78%, 94.2%, rev-2025,
  …) finds 0 remaining on all four pages, and the 31-assertion
  headless render check below asserts specific fabricated strings
  stay absent from the **rendered** DOM, not just the source.
- **Bug found and fixed during verification:** the first wiring pass
  loaded `app.js` with `defer` while the page scripts are inline —
  the inline IIFEs ran first, dereferenced the not-yet-defined `SD`
  global, and silently died (pages looked fine, nothing was wired).
  Caught by the headless render check (bindings never rendered, zero
  console errors — the throw happened before any listener attached);
  fixed by loading `app.js` synchronously (its top level touches no
  DOM). Lesson: a beautiful static page can be completely unwired
  and look identical.

### Phase 5 (Testing) —

**Frontend E2E (2026-10-01): record → submit → result flows driven in
a real browser against the live server.** All four screens exercised
through headless Chrome (CDP-driven), real server
(`uvicorn samskrita_dhvani.api:app --port 8000`), no mocked HTTP.

1. **API contract smoke (curl + urllib multipart):** `GET /api/words`
   → 27 words, `reference_audio_available: false`; `GET /api/status`
   → honest degradations on this machine (Vedavani manifest absent,
   GVR registry empty); `POST /api/spd/score` with word_id=nope →
   **404 unknown_word**; valid word + synthetic 1.0 s WAV → **503
   model_unavailable** with detail "Audio validated OK (1.00s, word
   'kRSNa')" — the validation layer genuinely decoded the upload;
   garbage bytes → **422 invalid_audio** (soundfile: "Format not
   recognised"); `POST /api/gvr/recognize` + WAV → **503** (registry-
   missing variant). All shapes match Frontend.md §4.
2. **Render check** (`tools/e2e_render_check.py`): **31/31 assertions
   PASS, 0 JS console errors** across /, /spd.html, /gvr.html,
   /status.html — live bindings verified in the rendered DOM (27 word
   buttons on SPD; both GVR result cards hidden at load; status word
   count equal to the API value) plus the fabricated-content absence
   checks. Harness lesson: `--virtual-time-budget --dump-dom` does
   not run pending fetches; CDP evaluate-after-settle does.
3. **Flow E2E** (`tools/e2e_flow.py`): **13/13 PASS.** Chrome launched
   with `--use-fake-device-for-media-stream`, so getUserMedia /
   MediaRecorder ran the real capture path (the fake mic produces a
   real tone WAV):
   - SPD upload fallback: attempt.wav decoded in-page → submit →
     explicit `model_unavailable` card; headline score stays "—".
   - SPD mic: recorded 1.6 s (timer advanced live: "00:01.8 /
     00:10.0 max"), stop → client transcode → submit → same honest
     503 card.
   - GVR mic: recorded 2.0 s → submit → fallback panel titled "Not
     Recognized — Model Unavailable"; the match card stays hidden;
     no verse text exists anywhere in the DOM.
   - GVR garbage upload: explicit in-page decode-failure message;
     submit stays disabled.
   Screenshots: `files/e2e-screens/*.png` (4, committed as evidence).
4. **Negative E2E** (`tools/e2e_flow_negative.py`): **7/7 PASS.**
   With the API process killed, SPD submit renders the explicit
   `network` card including the recovery hint ("start the backend:
   uvicorn …"), score stays "—"; with `/api/*` blocked via CDP, the
   status page renders "Status unavailable: …" in the card, the word
   meta, and the audit table (the failure, not stale rows), word
   count "—".
5. **Test suite:** `.venv/bin/python -m pytest tests/` → **60 passed**
   (the previously-skipped web-mount test now runs and passes since
   `web/` exists).

**Honest limits of this E2E pass:** no human-voice recording was made
(the automated runs use the fake-mic tone and in-page-built WAVs; a
short owner smoke test with a real microphone is the remaining
action). The SPD 200-response and GVR match paths cannot be exercised
until D2/D3 exist — by design, this pass proves the *honest
unavailable* states at the model seam instead. Screen status: Home
wired + routed; SPD wired (scorer pending); GVR wired (recognizer
pending); Status fully live.

**Phase 3 design note (2026-10-01): D5 calibration-recording
program + FR-22 GVR data plan — approved by direct owner request
(same session as units 3b/4; Design precedes Coding per Development.md).**

- **Goal:** close the D5 data gap — after the Hall/Loyola ear check,
  produce the `<word_id>.wav` canonical clips and
  `<word_id>__take.wav` known-correct recitations that
  `python -m samskrita_dhvani.calibrate --references
  data/spd/reference_words --recitations data/spd/recitations`
  consumes; and draft the FR-22 GVR registry plan so D4 recording
  can start the moment source permission lands.
- **Shape:** a capture service (`samskrita_dhvani/record.py`,
  uvicorn, its own port — entirely separate from the demo API)
  serving `web/record.html`; the page drives word-by-word capture
  with the same `SD.Recorder` / `SD.toWav16k` path the demo screens
  use, uploading 16 kHz mono WAV. No new recording dependency
  (sounddevice/PortAudio is unusable on this headless box — browser
  capture is both the convention here and the testable path).
- **Write discipline (DataIntegrity §2 / Rule 2 / §5):** uploads land
  ONLY in `data/_incoming/<session-id>/`. Nothing is ever written
  into `data/spd/reference_words/` or `data/spd/recitations/` —
  promotion to the calibrate layout is a separate, deliberate,
  ear-check-gated step. Per-clip checklists and the session sheet
  (RecordingProtocol.md §1–§2) are emitted alongside the audio.
- **Naming:** capture files follow RecordingProtocol.md §3
  (`spd_<item>_<reciter>_<sessionid>_t<take>.wav`, item = romanized
  key); a promotion mapping step converts to the calibrate CLI's
  word_id-keyed layout. The capture tool itself never writes inside
  the corpus tree.
- **Server-side acceptance:** every upload is decoded with the real
  D1 loader, VAD speech fraction must clear the DataIntegrity §1.1
  10% line, duration ≥ 0.2 s; failure is a 422 with the clip
  discarded server-side and a loud client error — a bad take can
  never enter the incoming tree silently. Take numbers are computed
  by the server from the session directory, not trusted from the
  client. Clipping/level acceptance stays a §4-sweep decision, not a
  client-side gate (the page's meter is a level *guide* only).
- **Provenance not invented:** session start requires reciter,
  location/room, device, and consent confirmation; `source_id` is
  required (pre-filled, editable) and the PROVENANCE.md registration
  happens at promotion time, not capture time.
- **Not designed (Ground Rule 2):** zero changes to the demo API,
  the D2 scorer, or the calibrate CLI — the CLI already defines the
  target layout; this tool only produces its inputs.
- **Test plan:** new `tests/test_record_api.py` (200 happy path with
  session/take/provenance assertions, 422 invalid audio, 422
  near-silence, 409 take collision, 400 unknown word, manifest
  integrity); full suite stays green; browser E2E via the fake-mic
  CDP harness. FR-22 plan lands as `files/GvrRegistryDataPlan.md`.
- **Report impact:** none — no reported number changes.

**Phase 5 — Unit 5 (2026-10-01): D5 calibration-recording program
(the recording booth) — built and tested.**

- **What was built:** `python -m samskrita_dhvani.record --port
  8030` serves `web/record.html` — a session-sheet form (reciter,
  location/room, device, consent confirmation, provenance source-id;
  RecordingProtocol §1 fields) → a 27-word capture grid → a per-word
  recorder modal using the same `SD.Recorder` / `SD.toWav16k` path
  as the demo screens (16 kHz mono WAV uploads). Separate uvicorn
  app on its own port; shares nothing with the demo API.
- **Integrity machinery (the point of the tool):** uploads land only
  in `data/_incoming/<session-id>/`; each take is decoded with the
  real D1 loader and VAD-gated (DataIntegrity §1.1 10% line) before
  anything touches disk — rejected takes (undecodable, <0.2 s,
  near-silence) are a loud 422 and never stored. Take numbers are
  server-computed (max+1, append-only; the client cannot claim a
  number and nothing on disk is ever overwritten). Every take gets
  a checklist sidecar (protocol §2 row as JSON: duration, peak
  dBFS, clipping flag, VAD fraction, with transcript-verified /
  sweep-date / provenance fields left open for the §4 sweep);
  `session_meta.json` doubles as the session sheet.
  `/api/record/promote` writes a `PROMOTION.md` mapping (canonical
  → `reference_words/<word_id>.wav`, recitations →
  `recitations/<word_id>__t<take>.wav`, plus the exact calibrate-CLI
  command) — it never copies into the corpus tree itself; promotion
  stays the deliberate, ear-check-gated operator step.
- **Two real bugs caught by the tests during the build:** (1)
  lowercase-folding capture filenames collide the vowel-length
  minimal pair — `tala` and `tAla` are distinct words on the SPD
  list, so filenames now keep the Harvard-Kyoto word_id verbatim
  (deliberate deviation from RecordingProtocol §3's lowercase
  example, which assumed romanized keys, not case-significant HK
  slugs); (2) FastAPI's empty-string Form validation silently turned
  the session-form 400 contract into a 422 — fields are now
  validated in the handler for the exact error bodies.
- **Verification:** 14 new tests (`tests/test_record_api.py`) —
  happy path with D1 re-decode of the stored WAV + sidecar content,
  loud invalid-audio / near-silence rejections (nothing stored),
  server-computed append-only take numbering across roles,
  tala/tAla non-collision, unknown word / bad role / unknown
  session errors, promote mapping content + explicit
  corpus-tree-untouched assertion, empty-session 409, booth page
  served with the shared app.js. Full suite: **118 passed**.
  Browser E2E (`tools/e2e_booth.sh` → `tools/e2e_booth.py`, fake
  mic): **10/10** — real capture of `spd_kRSNa_canonical_t0.wav`
  (2.22 s, VAD 45% speech) plus two recitation takes through the
  page, sidecars verified on disk, promotion mapping rendered, and
  the corpus tree never created; screenshots
  `files/e2e-screens/booth-*.png`. E2E fixture sessions were
  deleted from `data/_incoming/` after the run — synthetic audio
  never lingers where real captures land (DataIntegrity §1.5).

**Phase 3 design note (2026-10-01, second note): GVR (D4) verse-item
mode for the recording booth — approved by direct owner request.**

- **Goal:** the FR-22 plan's §2.3 fallback ("D4 self-recording via
  the booth") currently has no booth support — the booth's item list
  is the SPD seed words only. This unit adds a program switch (D5
  SPD words / D4 Gita verses) to the same capture flow: same
  session discipline, same upload gating, per-program items,
  filenames, and promotion mapping.
- **Text source (no fabricated mūla):** verses come from
  sanskritdocuments.org's `bhagvadnew.itx` (proofread 2021-05-15,
  volunteer-prepared, personal study/research use statement in the
  file header) — fetched, parsed by a checked tool
  (`tools/build_gvr_itemlist.py`), and emitted as
  `data/gvr/ch2_itemlist.json` (schema v1: verse_id, devanagari,
  fname_key; all 72 verses parsed, booth serves the FR-22 20-verse
  subset). Parse gates: exactly 72 verses for chapter 2;
  spot-verified known lines (2.13 dehino'smin, 2.47
  karmannyadhikāras…) before the file is trusted; source URL +
  sha256 recorded in a new PROVENANCE.md entry (GVR-TXT-01).
- **Interfaces changed:** `GET /api/record/items?program=D4|D5`
  (new; D4 serves the verse list, honestly unavailable if the item
  file is absent); `/api/record/session` gains `program` +
  `tradition` (protocol §3.6: tradition stated per session, carried
  into every checklist row); session ids become `SPD-REC-…` /
  `GVR-REC-…`; D4 uploads use verse ids (`2.13`) validated against
  the item list, filenames `gvr_c<ch>v<v>_recitation_t<N>.wav`
  (protocol §3 key), role restricted to `recitation` (D4 has no
  single canonical reference — all takes are corpus takes per the
  FR-22 plan); D4 promotion maps to protocol-compliant names
  (`gvr_c2v13_<reciter>_<sid>_t<take>.wav` under
  `data/gvr_recordings/`) and names the future registry-build step.
- **Not designed (Ground Rule 2):** zero changes to the demo API,
  scorer, recognizer, calibrate CLI, or the D5 flow's behavior —
  D5 responses/filenames are byte-identical to unit 5's.
- **Test plan:** extend `tests/test_record_api.py` (D4 item list,
  GVR session ids + tradition, D4 upload naming/role/verse
  validation, per-verse take numbering, D4 promotion content);
  extend `tools/e2e_booth.py` with a D4 capture flow; full suite
  green.
- **Report impact:** none — no reported number changes.

**Phase 5 — Unit 6 (2026-10-01): GVR (D4) verse-item mode for the
recording booth — built and tested.**

- **What was built:** the booth now takes a program switch — D5 (SPD
  words, byte-identical behavior to unit 5) or D4 (Gita verses).
  D4 sessions mint `GVR-REC-…` ids, require the recitation tradition
  at session start (protocol §3.6; carried into every checklist row
  as `recitation_tradition`), serve the FR-22 20-verse subset (Ch. 2,
  vv. 1–20) with real mūla text in the capture modal, restrict the
  role to `recitation` (D4 has no single canonical reference — all
  takes are corpus takes per the FR-22 plan), name takes
  `gvr_c<ch>v<v>_recitation_t<N>.wav` (protocol §3 key; the dot in
  verse ids stays out of filenames), and promote to the
  protocol-compliant registry-prep names
  `gvr_c<ch>v<vv>_<reciter>_<sid>_t<take>.wav` under
  `data/gvr_recordings/` with the registry-build step named. The
  corpus-tree boundary is unchanged: capture never writes into
  `data/spd/` or `data/gvr_recordings/`.
- **Text source (no fabricated mūla — Ground Rule 1):** verse text is
  parsed from sanskritdocuments.org's proofread `bhagvadnew.itx`
  (sha256 `084f037a…f13aa`, recorded with the URL in the item file
  and in a new PROVENANCE.md entry **GVR-TXT-01** — label TEXT only,
  no audio from this source; the site's personal study/research
  statement covers this internal academic use). The checked builder
  (`tools/build_gvr_itemlist.py`) enforces: exactly 72 verses for
  chapter 2, verse-number sequence, spot-check lines (2.13, 2.47)
  before write, and a per-verse Devanagari→IAST→Devanagari round
  trip. Three builder bugs were caught by its own gates during the
  build: my spot-check constants were written in a mixed translit
  convention (fixed to the source's `.n` orthography), the chapter
  `\section` header and speaker lines leaked into verse 2.1 (filtered),
  and the round-trip check compared IAST against ITRANS (always
  false — replaced with the FR-13-style Deva→IAST→Deva identity).
  Output: `data/gvr/ch2_itemlist.json` (schema v1, 72 verses; the
  booth serves vv. 1–20). The booth's `/api/record/items?program=D4`
  is honestly 503 `itemlist_unavailable` if that file is absent or
  fails its schema gate.
- **Verification:** 5 new D4 tests (items endpoint + honest 503,
  tradition-required session with `GVR-REC-` id, upload role/verse
  validation + sidecar content incl. tradition, per-verse take
  numbering, promotion mapping with protocol §3 names + explicit
  corpus-untouched assertion). Full suite: **123 passed**. Browser
  E2E (`tools/e2e_booth.sh`) extended with a D4 flow: **15/15** —
  20-verse grid, real 2.13 mūla displayed (देहिनोऽस्मिन्यथा देहे
  कौमारं यौवनं जरा), fake-mic take saved as
  `gvr_c2v13_recitation_t0.wav` (2.04 s, VAD 40%), sidecar carries
  tradition, `GVR-REC-` session verified on disk, corpus tree never
  created; screenshot `files/e2e-screens/booth-d4-verse-take.png`.
  E2E fixture sessions deleted from `data/_incoming/` after the run.

**Phase 3 design note (2026-10-01, third note): registry-build tool
(`python -m samskrita_dhvani.build_registry`) — approved by direct
owner request.**

- **Goal:** FR-22 plan §5 step 3 — turn a promoted D4 recording
  batch (protocol §3 names under `data/gvr_recordings/`, exactly as
  the booth's PROMOTION.md emits:
  `gvr_c<ch>v<vv>_<reciter>_<sid>_t<take>.wav`) into
  `data/gvr_registry.json` with every per-row acceptance gate applied
  (plan §4). No registry is written if zero rows survive (rc=2).
- **Split policy — correction to the FR-22 plan (Ground Rule 7
  honesty):** plan §3's "validation carved by take parity" and
  "single-reciter per-recording split" assignments would VIOLATE
  `GvrRegistry.assert_no_split_leak` — a (verse, reciter) pair may
  never span two splits. The tool implements what the registry
  actually enforces: **auto** mode → ≥2 reciters: per-reciter with
  explicit `--reciter-splits R=train,R=test` assignment (unassigned
  reciter = error); exactly 1 reciter: all rows train with
  `split_policy: per-recording` recorded in the file, and every
  reported number must carry the FR-23 single-reciter sentence
  (plan §3 gets the same correction in this unit). `GvrRegistry`
  gains an explicit optional `split_policy` field (default
  `per-reciter`, value-validated, written by `to_json`, read by
  `from_json` — small, declared change so the file never lies about
  its policy per NFR-04).
- **Per-row gates (each failure = loud skip line + counted, never
  fixed):** filename grammar parse; verse ∈ itemlist (mūla text from
  the checked GVR-TXT-01 item file — the tool never types verse
  text); D1 decode + duration ≥ 0.2 s + VAD speech fraction > 10%
  (DataIntegrity §1.1); unique `audio_file`; mandatory
  `--recitation-tradition` (protocol §3.6) and `--source-id` /
  `--acquired-on` provenance; per-reciter split policy as above.
  Verses whose rows all land outside train are listed in a warning
  (they cannot be learned by `GvrRecognizer.train`).
- **Self-check:** the tool loads its own output through
  `GvrRegistry.from_json` (which runs the leak + provenance gates)
  before reporting success, and prints the split summary + verse
  coverage as-run.
- **Not designed (Ground Rule 2):** no changes to the booth, scorer,
  recognizer, or demo API; the registry format change is limited to
  the explicit `split_policy` field.
- **Test plan:** new `tests/test_build_registry_cli.py` — happy path
  (2 reciters, per-reciter splits, from_json self-check, mūla text
  attached), single-reciter auto per-recording policy, leak-avoidance
  (reciter-splits validation), every gate's skip behavior, unknown
  verse, duplicate target names, empty-result rc=2, --force. Full
  suite green.
- **Report impact:** none — no reported number changes.

**Phase 5 — Unit 7 (2026-10-01): registry-build tool
(`python -m samskrita_dhvani.build_registry`) — built and tested.**

- **What was built:** the FR-22 plan §5 step 3. Turns a promoted D4
  batch (protocol §3 names under `data/gvr_recordings/`, exactly as
  the booth's PROMOTION.md emits) into `data/gvr_registry.json`:
  filename grammar parsed right-to-left (reciter slugs and session
  ids containing underscores survive), verse resolved against the
  GVR-TXT-01 item list for the canonical id + mūla
  `devanagari_text` (the tool never types verse text), D1 decode +
  duration + VAD gates applied per row, mandatory
  tradition/provenance attached, splits assigned per the corrected
  §3 policy, and the output self-checked through
  `GvrRegistry.from_json` (the same load-time gates training will
  apply) before success is reported. Per-row failures are loud
  counted skips (Rule 1); zero survivors → nothing written, rc=2.
  Split summary and a no-train-rows warning (verses that cannot be
  learned) print as-run.
- **Split-policy correction (the important find):** plan §3's draft
  assignments (validation by take parity; single-reciter
  per-recording split) violate `assert_no_split_leak` — a
  (reciter, verse) pair must sit in exactly one split. The plan is
  corrected in this unit; the tool implements only what the registry
  can honestly hold: explicit complete `--reciter-splits` when ≥2
  reciters (an explicit single-reciter assignment is honored with a
  warning about untrainable verses), and single-reciter-no-spec →
  all-train with `split_policy: "per-recording"` recorded in the
  file (NFR-04). `GvrRegistry` gained an explicit, value-validated
  `split_policy` field (default `per-reciter`) so the file never
  lies about its policy; `to_json`/`from_json` round-trip it.
- **Convention unification (caught by the tool's own tests):**
  verse-id forms had drifted — the D3 fixture canon is zero-padded
  (`4.07`) but the item-list builder emitted unpadded ids (`2.1`).
  `build_gvr_itemlist.py` now emits padded ids (`2.01`…`2.72`) and
  the committed `data/gvr/ch2_itemlist.json` was regenerated (same
  source sha256; one id form runs booth → registry → model).
- **Verification:** 10 new tests (right-to-left name parse, two-
  reciter happy path with load-time self-check + mūla + provenance,
  single-reciter auto policy, incomplete `--reciter-splits` rc=2,
  every gate's loud skip, unknown verse → rc=2, overwrite protection
  + deterministic `--force` rebuild, empty dir rc=2, explicit
  single-reciter test-split assignment warns). Full suite: **133
  passed**. As-run check on a synthetic 5-clip batch against the REAL
  item list: 5 rows, per-reciter policy, train/test summary printed,
  real 2.01 mūla (तं तथा कृपयाविष्टमश्रुपूर्णाकुलेक्षणम् ।) attached
  from the parsed source; scratch dirs removed after the run.

**Unit 3b (2026-10-01): calibration CLI — built and tested.**

- `python -m samskrita_dhvani.calibrate` turns the D5 recording
  program into a calibration file directly: point it at the
  ear-verified canonical clips (`--references`, named
  `<word_id>.wav`) and the known-correct recitations
  (`--recitations`, `<word_id>__take.wav` siblings or `<word_id>/`
  subdirs), pass mandatory provenance (`--source-id`,
  `--acquired-on`), and it writes `data/spd/calibration.json`
  (schema v1) with the measured per-word D₀, D₀_formant, D₀_duration
  and prints them. Provenance and the Rule-2 discipline apply to the
  calibration file itself.
- **Failure handling is loud and per-item:** a word missing one side
  is skipped with a printed notice; a corrupt take is skipped while
  the surviving takes still calibrate the word; a word whose
  recitations all fail is dropped with a reason. Overwriting an
  existing calibration file requires `--force` (regeneration must be
  deliberate).
- **Degenerate-calibration guard (found by the CLI's own tests):**
  fixtures with zero duration variation measured D₀_duration =
  exactly 0 — `sim = 100·exp(−x/0)` is undefined, so that corpus
  must be rebuilt with real recitation variation. `Calibration`
  now validates all three scales positive at construction (and
  `n_references ≥ 1`), failing loudly instead of dividing by zero
  later.
- **Verification:** 8 CLI tests through `main()` on synthetic clips
  (measured output + printed table, one-side-missing skip, overwrite
  protection + `--force`, provenance requirement, missing-dir
  error, corrupt-take resilience, all-fail word drop). A full
  end-to-end run on a 3-word × 3-take synthetic layout produced the
  measured table (e.g. kRSNa: D₀ 2.5951, D₀_formant 0.0149,
  D₀_duration 0.0862, 3 refs). `pytest tests/` → **104 passed**.

### Phase 6 (Maintenance) — repo cleanup, hygiene, and structure pass

**Date:** 2026-09-23 · **Phase:** 6 · **Scope:** cleanup-and-organize
only — no feature work, no audio-sweep-triggering corpus change
(no new audio entered the pipeline; the §4 table below stays unfilled
until the first lazy-extraction sweep, Open Item 6).

**Inventory findings (local ↔ GitHub):**

- 0 tracked files missing locally; branch in sync with `origin/main`
  at `955c9f95` before this pass.
- 11,300 untracked + 5 modified files locally. Breakdown: 10,097 WAVs
  in `Audio_files/` (2.2 GB); 1,104 MP3s + metadata across 6 untracked
  `parva*-master/` dirs (2.5 GB); 67 untracked but **should-be-tracked**
  `data/spd/` files (63 Loyola MP3s + `MANIFEST.csv`, 3 valid Hall
  MP3s); 12 `Vedavani-main/` code files; 14 GB `ASR-Sanskrit/` clone;
  13 GB `Vedavani-Dataset/` WAVs (HF clone); 5 modified tracked files
  (valid skpro_00/02 MP3s vs git's 0-byte stubs + 3 doc updates).
- Hygiene: **96 tracked `.pyc`** (90 in `Vaksanca-master/`, 6 project),
  **7 tracked `.DS_Store`**, **no `.gitignore` at all**.
- Provenance doc discrepancies: PROVENANCE GVR-01 claimed the master
  zip "held at repo root" — absent; mahabharata "zips held unextracted"
  — actually found extracted on disk.
- **Bucket (b) verification:** all 10,097 `Audio_files/` names match
  the Vedavani `MANIFEST.csv` index; sha256-16 spot-checks 11/11 match;
  sampled files byte-identical (`cmp`) to `Vedavani-Dataset/AudioFiles/`
  copies; 6 are `(1)`-suffixed re-download duplicates of files in the
  same dir. No multi-reciter material involved (Vedavani dup check
  against DataIntegrity §1.4/§3.3: identical sha = same recording,
  not cross-reciter variation).

**Removed / untracked (owner-approved, with reasoning):**

| Action | Count | Bucket / reason |
|---|---:|---|
| Deleted `Audio_files/` WAVs | 10,097 (2.2 GB) | (b) byte-verified duplicates of `corpus/vedavani/` content |
| Untracked + deleted `.pyc` | 96 | (a) build artifacts (90 upstream-committed in Vaksanca, 6 local) |
| Untracked + deleted `.DS_Store` | 7 | (a) macOS junk |
| Deleted local `__pycache__/`, `.pytest_cache/` | 6 dirs + 1 | (a) caches |
| Deleted `.venv/` | — | (a) recreatable from pinned `requirements.txt` |
| Deleted `.kilo/` (+ `git worktree remove capable-bird`) | — | (a) tool state, deregistered properly |
| Deleted `SVP/Ques` | 1 | owner decision (course revision notes) |
| Deleted `files/TEST QUESTION_31_07_2026.md` | 1 | owner decision (coursework file in project docs) |
| Untracked Vāksañcayaḥ corpus (kept local) | 46,010 | owner decision — local-only copy, `.gitignore`d |
| Untracked mahabharata audio, kept READMEs | 1,104 MP3s | owner decision — keep + reorganize |
| Untracked Vedavani WAVs/HF clone (kept local) | 30,799 WAVs | embedded git-lfs clone; parent repo cannot track it |

**Structure adopted (owner-approved; Implementation.md §3 split):**

- `corpus/vaksancayah/` (local-only), `corpus/vedavani/` (local-only
  HF clone), `corpus/vedavani-code/` (12 files tracked),
  `corpus/mahabharata_audio/parva*` (18 metadata files tracked),
  `corpus/vaksancayah-dataset-metadata.pdf`.
- `third_party/vaksanca/` + `third_party/Vaksanca-master.zip` —
  1,133 tracked files moved (git recorded 1,132 R100 renames + the
  separately-modified zip blob).
- `.gitignore` created (caches, tool state, corpus audio holdings).
- PROVENANCE.md (GVR-01 zip status + local dir; GVR-03 path;
  mahabharata disposition) and DataSources.md (§1.3 parva status;
  §2.1 path) amended in the same commit (Ground Rule 5).

**Actual result (commands run, real output):**

- `.venv/bin/python -m pytest tests/ -q` → **49 passed** before the
  pass (baseline) and **49 passed** after the moves/renames (code
  sources untouched by this pass; venv removed after the verified run).
- `git diff --cached --stat` → 47,350 files changed, 1,171
  insertions(+), 92,268 deletions(-). Post-commit tracked tree:
  **1,299 files** (from 47,316).

**Open after this pass:** master Vāksañcayaḥ zip missing (re-download
if a provenance-anchored archive copy is needed); `corpus/vedavani-code/`
license unverified (tracked, flagged); `.git` still ~2.1 GB from the
committed corpus — history purge would be a separate explicit unit of
work (Ground Rules 2/8), not done here.

_(The Data Integrity Sweep table below is left unfilled — no new audio
sweep was required by this pass; next sweep runs at first lazy
extraction per Open Item 6.)_

| Item (word/verse) | Samples | Corrupted found/excluded | Duplicates | Cross-split leaks (GVR only) | Provenance on file? | Label spot-checked? |
|---|---|---|---|---|---|---|
| | | | | | | |

---

**SVP/ course-material cleanup (2026-09-24):** extract, then prune —
per the Phase 6 discipline (no bulk-delete first).

- **Inventory (before):** `SVP/` = **22 files, 31.0 MB**, all
  git-tracked (7 chapter PDFs, 9 lecture PDFs, 4 UNIT II PDFs, lesson
  plan, midsem paper, question bank).
- **Extraction → `docs/theory/` (12 source files + citation map =
  **13 files, ~16.0 MB**):** the 10
  PDFs cited by `Implementation.md` §2 (Ch-2–Ch-7,
  `UNIT II_MFCC/_Cepstrum analysis/_LPCC`, `Speech Processing L3`) —
  every copy verified **byte-identical via `cmp` (10/10)** — plus
  **`Ques`, recovered from git history** (deleted in the prior
  cleanup commit `ce2dbbcb`; sha256 `e47ba3b7…` matches
  `ce2dbbcb^:SVP/Ques`; the file is absent from the synced working
  tree and exists only in history). The recovered `Ques` is the file §2
  actually cites: **Q6** = "Why overlapping windows are used instead
  of clear cut windows?" and **Q1** = the MFCC-perception
  True/False — numbering belongs to *this* file, **not** to
  `SVP_question_bank 2026.pdf` (whose Module II Q13/Q14 cover the
  same topics under different numbers; verified by extraction). Also
  kept per owner decision: `UNIT II_Feature Extraction.pdf` (umbrella
  TOC of the cited UNIT II set). `docs/theory/README.md` added — a
  citation map (file → §2 use → code traceability) so the reference
  set is self-describing. `docs/theory/` = **13 files, ~16.0 MB**
  (11 PDFs + `Ques` + `README.md`).
- **Ambiguity resolution (flag-then-decide, owner confirmed
  "proceed as recommended"):** `UNIT II_Feature Extraction.pdf` kept;
  L2/L4/L10 (theory-adjacent but uncited; covered by cited
  chapters), L1/L12, L6-L7-L8, L9, Ch-1, lesson plan, midsem, and
  the question bank deleted. No code or doc depends on `SVP/` paths
  (grep-verified; `docs/theory/README.md`'s historical mention is
  prose only).
- **Removal (after):** `SVP/` = **0 files** — 10 files removed from
  the working tree (all recoverable from git history), 12 source
  files + README preserved in `docs/theory/` (13 on disk). Committed locally as a standalone cleanup
  commit (not pushed; push awaits owner instruction).
- **Ground Rule 1 check:** every count above from actual `find`/
  `git ls-files`/`cmp`/`sha256sum` runs, not estimates.

## Open Items (carry forward until resolved or explicitly deferred)

1. Finalize SPD word list (20–30 words, difficulty pairs) and GVR verse
   subset size — now constrained by the self-recording decision (D4/D5,
   prior session). **Candidate mining source:** Hall skpro_01/02 term
   list (160+ terms; 1,696 speech segments) — after its label
   spot-check (item 3).
2. ~~Create `PROVENANCE.md` and the recording protocol~~ — **DONE**
   (PROVENANCE.md schema v1 live; `files/RecordingProtocol.md` created
   this session; sheets go to `data/provenance/` at first session).
3. Listen-through spot-check of Hall skpro_00–04 **and the 63 Loyola
   files** (DataIntegrity §4 step 1) — files stay out of the pipeline
   until done; the quarantined Loyola `noun1–noun9` set needs an
   intelligibility call (low-level capture) before any use. Then
   finalize the SPD word list (candidate mining from Hall skpro_01/02
   terms + Loyola declension stems) and cut reference word clips.
   **2026-09-23:** Vedavani listen-through **COMPLETE** — automated
   515-file sample pass (0 VAD fails, no audible-distortion signature,
   DC-batch finding logged) plus owner review of the 12 evidence-pack
   files at `data/provenance/vedavani_listen_2026-09-23/`, confirming
   genuine recitation content consistent with labels. Vedavani is
   cleared as the front-end validation pool (§2.1); the 299
   peak-flagged files remain barred from reference-material duty.
4. Record verse/word audio via the self-recording programs using
   `files/RecordingProtocol.md` (reciter, device, room, tradition
   logged; consent recorded).
5. ~~Draft and send the Gita Supersite maintainer contact~~ —
   **DRAFTED 2026-09-23** (`files/GitaSupersitePermissionEmail.md`):
   ready-to-send body + verified addressing (primary:
   `head@cse.iitk.ac.in` per the CSE Contact Us page; no mailto exists
   on either Supersite host — checked) + pre-send checklist + yes/no
   response playbooks. **Send remains a human action** (owner's
   institute email + supervisor cc). Until a grant is logged in
   PROVENANCE.md GVR-02, the GVR registry stays on the D4
   self-recording path.
6. Extract from the Vāksañcayaḥ archive only the subsets actually used
   (lazy extraction), running the §4 per-file sweep at that point.
7. ~~Decide keep/delete for the mahabharata-audio parva zips (no Gita
   content; candidate for deletion at next cleanup).~~ **RESOLVED
   2026-09-23 (Phase 6):** kept as a low-priority depth/backup source,
   untracked, at `corpus/mahabharata_audio/` (owner decision); audio
   ignored, per-repo READMEs tracked.
8. Cross-check SPD's automated similarity score against human/
   instructor ratings (NFR-10 in `SRS.md`).
9. Report GVR accuracy on a real held-out split with a confusion matrix
   (NFR-20 in `SRS.md`).
10. ~~Phase 4 unit 1: implement `samskrita_dhvani/frontend.py` per
    design D1, with the FR-03 manual-vs-librosa cross-check test
    (registry-independent; may start now).~~ **DONE 2026-09-23** —
    20/20 tests green; FR-03 max-abs-diff 2.2e-7 on real audio
    (see Phase 4 unit 1 entry). Next: unit 2 (`registry.py`),
    SPD/GVR branches per the Phase 3 module sequence.
11. Frontend Phase 3 (Design) sign-off — `Frontend.md` §6 items 1–4,
    **all resolved 2026-09-23** (owner decisions, one per item):
    1. §3.2 waveform/spectrogram comparison — **DEFERRED** for v1
       (per-axis bars carry the diagnostic content; comparison strip
       documented as a future enhancement; v1 no longer blocked on the
       SPD reference-audio ear check).
    2. §3.4 Corpus/Model status page — **IN SCOPE for v1** (four
       screens: Home, SPD, GVR, Status; status numbers pulled live
       from the registry/manifest, never hardcoded).
    3. Backend framework/endpoint paths — **CONFIRMED: FastAPI** with
       `GET /api/words`, `POST /api/spd/score`,
       `POST /api/gvr/recognize`, `GET /api/status` (as tabled in
       Frontend.md §4; pydantic-validated schemas; FastAPI/uvicorn
       pinned via Phase 2 verify-then-pin before any code).
    4. Browser target — **desktop Chrome/Firefox minimum**, stated in
       the UI footer; file-upload fallback for other browsers; mobile
       explicitly out of scope for v1.
    Also recorded in the sign-off context: the SPD scorer (D2) and GVR
    HMM (D3) units are not yet built, so v1 endpoints return explicit
    "model not available" states rather than scores until those units
    land (Ground Rule 1 in the UI); SPD reference playback shows an
    honest disabled state until the Hall/Loyola ear check passes;
    GVR stays honest-empty until the permission path or D4
    self-recordings populate the registry. Stitch division of labor
    confirmed: Stitch generates visual design only (user runs
    stitch.withgoogle.com per screen using the Frontend.md §2 + §3.x
    prompts, exports Tailwind HTML to `web/stitch_exports/`); all
    wiring, recording, state, and E2E testing is Phase 4/5 agent work.

**Frontend Phase 4 (2026-09-23): demo API backend — built and tested
(`samskrita_dhvani/api.py`).**

- **Environment note:** the session restart lost `.venv` (fresh clone
  state; no `pyvenv.cfg` anywhere). Rebuilt from `requirements.txt`
  pins — all 59 tests re-ran green afterwards. New pins added under
  Phase 2 verify-then-pin: fastapi 0.141.1, uvicorn[standard] 0.53.0,
  python-multipart 0.0.32, httpx 0.28.1, and `setuptools<81`
  (uncovered that a fresh venv no longer bundles `pkg_resources`,
  which `webrtcvad` imports at module load — the rebuild made the
  latent requirement explicit; it is now pinned).
- **Contract implemented exactly as signed off** (Frontend.md §4):
  `GET /api/words` (FR-12 list from the real seed registry; FR-13
  round-trip holds by construction; `reference_audio_url` is None per
  word until clips exist — honest empty state), `POST /api/spd/score`
  (validates word ID → 404, decodes upload via the real D1
  `load_audio_16k` → 422 on garbage/too-short, then **503
  `model_unavailable`** at the marked `# SCORER SEAM` until design D2
  lands — never a fabricated score), `POST /api/gvr/recognize` (same
  validation + 503 pattern; registry < 20 entries also reports the
  data gap), `GET /api/status` (§3.4 transparency data read live at
  request time: real word count, honest verse-coverage gap citing the
  permission blocker, Vedavani sweep numbers from `MANIFEST.csv` when
  the corpus is on the machine, explicit "not found on this machine"
  detail when it is not).
- **Design for the seams:** both POST endpoints validate everything
  that can be validated today and mark the single call site (`#
  SCORER SEAM`) where Phase 4 units 3/4 (D2 DTW scorer, D3 HMM) drop
  in — wiring the models later touches exactly one block per endpoint.
- **Tests:** 10 new (synthetic WAV fixtures only, NFR-02) — contract
  shape, transliteration consistency of served rows, honest 503 on
  valid-but-unscorable requests, 404/422 validation paths, and a
  conditional static-mount test. `pytest tests/` → **59 passed,
  1 skipped** (skip = `web/` mount, pending Stitch exports).
- **Stitch hand-off:** `files/StitchPromptPack.md` prepared —
  ready-to-paste prompts for the four screens (Home, SPD, GVR,
  Status), each with the §2 design direction embedded, iterate-until
  criteria, and the required honest-state variants. Owner action:
  generate + iterate the four screens, export Tailwind HTML into
  `web/stitch_exports/`, then the wiring pass starts.

## Bugs Fixed This Session

- **0-byte Hall downloads** (skpro_00, skpro_02 from the prior
  acquisition attempt): detected by the §4 sweep, re-downloaded with a
  referer header, re-swept clean. Root cause: no referer/UA on the
  first attempt plus a transient DNS failure on the retry. Valid files
  committed to git 2026-09-23 (Phase 6) — the repo previously held the
  0-byte versions.

**Phase 6 maintenance entry (2026-10-01): SPD reference-source audio
restoration + ear-check staging repair.**

- **Finding (data loss):** the ear-check staging of 2026-09-23
  (`data/provenance/spd_listen_2026-09-23/`) referenced audio that
  went missing from local disk — all 63 Loyola MP3s (SPD-02), all 5
  Hall MP3s (SPD-01), and the 9 gain-boosted noun-set evidence
  renders. Only the tracked `MANIFEST.csv`, the checklist, the
  automated-pass CSV, and 5 spectrogram PNGs survived. The owner's
  ear check (the final FR-12 gate) was impossible in this state.
- **Restoration (`tools/restore_spd_audio.py`, repeatable):**
  - Loyola: Wayback recovery per the method recorded in the SPD-02
    entry (CDX-verified captures, `id_` raw fetches, timestamp
    fallbacks for stragglers) — **63/63 restored, every file
    sha256-prefix-verified against MANIFEST.csv** before it was
    written; nothing that failed verification was kept.
  - Hall: re-downloaded from the SPD-01 source — **5/5 restored,
    byte-size-identical to the PROVENANCE sub-table**, duration
    re-verified with the real decoder (the first attempt used a
    first-frame MP3 probe that misreads VBR durations — replaced).
    One transient DNS failure and one filename-guess bug
    (noun3_kanyaa/dhii/strii/bhaanu have doubled vowels; stems now
    come from MANIFEST.csv, not guesses) were caught by the tool's
    own verification gates and fixed.
  - Boosted evidence renders: 9/9 re-rendered from the restored
    sources with the documented recipe (peak → 0.60; the recorded
    ×6.7–13.2 range reproduced).
- **Sweep validity:** the restored bytes are identical to what the
  2026-09-22 sweep measured (hash/size anchors), so the recorded
  sweep values and `listenthrough_auto.csv` remain valid as-run — no
  re-sweep required.
- **Ear-check staging:** `WALKTHROUGH.md` added to the staging
  directory — next-session quickstart with real file paths, ~30 min
  timeboxed plan (Hall term list → Loyola healthy set → quarantined
  noun1–9 intelligibility call), and the verdict handoff template.
  **The verdict itself is still PENDING and belongs to the owner** —
  Ground Rule 1: nothing is logged as heard until the owner says so.
- **Tracking note (owner decision):** the restored audio (~91 MB
  total) is deliberately untracked — the SPD-01/SPD-02 licenses say
  do-not-redistribute and the repo's GitHub visibility is unknown;
  the Phase 6 audit's "should-be-tracked" suggestion is superseded
  by that caution. Recommend a private local backup instead.

**Phase 6 addendum (2026-10-01): D4 owner-reciter session STAGED —
no takes exist yet.**

- The booth was launched for the owner (`python -m
  samskrita_dhvani.record --port 8030`, real Chrome-targetable URL,
  `setsid`-detached so it survives between agent commands — the
  "servers die with the command" trap is escaped by a new session;
  stop it with `kill <pid>`, never `pkill` by pattern). Verified
  serving the real D4 list: 20 verses, first `2.01` with the real
  mūla, text source = the GVR-TXT-01 URL.
- `data/provenance/d4_recite_sheet_2026-10-01.md` — the owner's
  recite sheet: all 20 verses from the checked item list with take
  checkboxes, the text-source citation for the session sheet
  (protocol §1 materials field), the take plan (3 takes/verse,
  ~20–30 min), and the post-session handoff steps (promote →
  build_registry → train).
- **Integrity boundary stated:** the agent cannot recite and will
  not feed synthetic takes into a session as if they were real
  (DataIntegrity §1.5, Rule 4) — the fake-mic captures used in the
  unit-6 E2E were deleted, and no `GVR-REC-` session was created by
  the agent. Session creation, consent, and the reciting itself are
  the owner's steps; takes begin existing only under their voice.

**Phase 6 addendum 2 (2026-10-01): full-chain rehearsal (synthetic,
quarantined) — chain validated, zero numbers reported.**

- To prove the D4 plumbing end-to-end without a human reciter, the
  LIVE booth server on :8030 was driven exactly as the browser
  would: session `GVR-REC-20261001-90d68a` (reciter
  `synthetic_rehearsal`, source-id `SYNTHETIC-REHEARSAL-DRYRUN`,
  tradition field literally "synthetic rehearsal — not a
  recitation") → two agent-generated tone takes for verse 2.13
  (both cleared the real §1.1 gates, VAD 0.935) → `/api/record/
  promote` mapping parsed → `build_registry` on the promoted pair →
  `GvrRecognizer.train` → `save` → `load` → `predict`.
- **Result:** the chain works — registry emitted (2 rows,
  `split_policy: per-recording` auto for a single reciter, real 2.13
  mūla attached from the item list), model trained + reloaded, and a
  rehearsal take decoded to `verse 2.13, confidence 1.000`. That
  confidence is the arithmetic artifact of a one-verse closed set
  (softmax over a single class), NOT a recognition result — no
  accuracy is claimed anywhere (FR-23).
- **Quarantine held:** everything synthetic lived in /tmp and the
  session dir; both were deleted in the same run, and the script
  asserts `data/gvr_registry.json` and `data/gvr/model.pkl` are
  still absent — no synthetic byte entered the corpus trees, the
  registry of record, or the model path. `data/_incoming/` verified
  empty after cleanup.
- **What remains for real D4:** the owner's recited takes (booth
  live on :8030, recite sheet staged). The rehearsal changes
  nothing about that gate — it only removes "untested plumbing"
  from the list of possible surprises.

## Changes Made This Session

- `requirements.txt` — created; pins the versions installed and
  smoke-tested in Phase 2 (incl. `praat-parselmouth` naming note and
  the `setuptools<81` constraint for `webrtcvad`). [prior session]
- `files/Implementation.md` — §4 table: corrected the Praat binding's
  PyPI name to `praat-parselmouth` with the trap documented. [prior
  session]
- `files/PROVENANCE.md` — created earlier today, then updated this
  session: Hall SPD-01 sub-table populated with real sweep values;
  GVR-01 acquisition status → ACQUIRED with verified layout/split;
  GVR-01 license discrepancy resolved (CC BY-NC 4.0 per corpus README);
  Gita-subset negative result recorded; GVR-02 blocked-status detail
  (Cloudflare + no static endpoints); mahabharata-audio marked dead
  end for Gita.
- `files/DataSources.md` — §1.1 Gita-subset + license resolutions; §1.2
  direct-check note; §1.3 repo-list dead end; §5 four items resolved.
- `files/RecordingProtocol.md` — created: session sheet, per-file
  checklist, naming convention, role-specific requirements (D4/D5),
  acceptance rule (Open Item 2's protocol half).
- `data/spd/loyola_cahill_sound_files/` — created; 63 Wayback-recovered
  MP3s (74.9 min, 44.1 kHz stereo) + `MANIFEST.csv` with per-file sweep
  data (sha256-16, duration, rms, peak, segments).
- `files/PROVENANCE.md` — SPD-02 (Loyola) entry added with recovery
  method, group sweep table, and quality quarantine; Deshpande row
  upgraded to "unrecoverable" (zero Wayback audio captures); Forvo
  plan recorded.
- `files/DataSources.md` — §3.2 resolved (unrecoverable), §3.4
  resolved (recovered, 63 files), §3.1 plan set, §4 step 3 order
  updated.
- `data/spd/hall_sanskrit_pronunciation/` — 5 valid MP3s (274 KB–3.5
  MB; 16 kHz mono), swept 2026-09-22.
- `files/Review.md` — Phase 2-continued entry, sweep table, updated
  Open Items.
- `Vedavani-Dataset/MANIFEST.csv` + `EXCLUDED_FILES.csv` — per-file
  sweep data (sha256-16, sr, channels, duration, rms, peak) for all
  30,799 on-disk WAVs; 20 sha-duplicate re-download artifacts excluded
  with reasons. [2026-09-23]
- `files/PROVENANCE.md` — GVR-03 (Vedavani) entry with group sweep
  table and quality flags; GVR-04 (ASR-Sanskrit) excluded-disposition
  entry; mahabharata-audio license resolution (CC BY-SA 4.0 via
  project page; archive item lacks `licenseurl`). [2026-09-23]
- `files/DataSources.md` — §2.1 Vedavani acquisition + sweep results;
  §2.2 ASR-Sanskrit excluded (no raw audio); §1.3 license resolved.
  [2026-09-23]
- `samskrita_dhvani/frontend.py` + `tests/test_frontend.py` +
  `conftest.py` — Phase 4 unit 1: shared D1 front-end with hand-
  derived MFCC cross-check (FR-01/02/03), 20 tests green. [2026-09-23]
- `files/GitaSupersitePermissionEmail.md` — permission-request draft
  for the GVR registry path (Open Item 5): verified addressing
  options, scoped ask (no redistribution, one chapter, rate-limited
  retrieval), provenance commitments, follow-up template, and
  yes/no playbooks. [2026-09-23]
- `data/provenance/spd_listen_2026-09-23/` — SPD listen-through
  staging: full automated audit of all 68 files (5 Hall + 63 Loyola:
  VAD speech fraction, item counts, flat-top, DC, head/tail levels —
  **0 failures of any kind**), 6 spectrogram renders, 9 gain-boosted
  WAVs of the quarantined noun set (the intelligibility-call
  enablement), and `CHECKLIST.md` — the 25–35 min owner ear-check
  protocol with pre-stated PASS/QUARANTINE/FAIL decision rules.
  SPD reference sets remain pipeline-ineligible until the verdict is
  logged. [2026-09-23]
- `data/provenance/vedavani_listen_2026-09-23/` — created: 515-file
  sample audit CSV (VAD speech fraction, flat-top, hard-clip, DC,
  head/tail RMS per file) + 12 spectrogram PNGs of the worst-case
  clipped/DC/stratified files as the evidence pack for the human ear
  check. `requirements.txt` gained the verified pins
  (matplotlib 3.11.2, pyarrow 25.0.1). [2026-09-23]
- **New corpus-level finding logged:** 609 verse texts appear in more
  than one Vedavani split (same verse text, different recitations —
  normal for ASR corpora, recorded in the GVR-03 entry context below).
  **Rule adopted:** if Vedavani is ever used beyond front-end
  validation for any verse-level classification experiment, it must be
  **re-split by text**, not by the official ASR split, to avoid label
  leakage (§4 step 3 analog).
- `web/index.html`, `web/spd.html`, `web/gvr.html`, `web/status.html`,
  `web/app.js` — Phase 4 wiring pass: the four canonical Stitch
  screens wired to the live FastAPI backend with real recording
  (MediaRecorder → client-side 16 kHz WAV), an upload fallback, live
  registry/status bindings, explicit error/empty states for every
  failure mode, and zero fabricated numbers (`web/stitch_exports/`
  left pristine). [2026-09-30 → 10-01]
- `samskrita_dhvani/spd_scorer.py` + `tests/test_spd_scorer.py` —
  Phase 4 unit 3: design D2 implemented (sim = 100·exp(−D/D₀),
  measured D₀ per word, per-axis FR-11 breakdown, calibration.json
  schema v1 + CalibrationBuilder), 21 synthetic-fixture tests.
  `api.py` `/api/spd/score` seam now walks the full honesty chain
  (422 near_silence → 503 reference_unavailable → 503
  calibration_unavailable → 200 FR-11 shape). [2026-10-01]
- `web/index.html`, `web/spd.html` — honesty lines updated to the
  D2-built state ("built, data pending"; backend names exactly what
  is missing). [2026-10-01]
- `samskrita_dhvani/gvr_classifier.py` + `tests/test_gvr_classifier.py`
  — Phase 4 unit 4: design D3 implemented (6-state L-R no-skip
  diagonal-Gaussian HMM per verse, hand-init topology,
  equal-segmentation emission init + degeneracy guard, Viterbi
  decode with softmax-gap confidence, schema-v1 model envelope),
  11 synthetic-fixture tests. `api.py` `/api/gvr/recognize` seam
  wired (422 near_silence → 503 model_unavailable naming the
  artifact → 200 FR-21 shape); `/api/status` `gvr_scorer_available`
  now reads the model artifact. [2026-10-01]
- `web/index.html`, `web/gvr.html` — honesty chips updated to the
  D3-built state ("built, training data pending"). [2026-10-01]
- `samskrita_dhvani/calibrate.py` + `tests/test_calibrate_cli.py` —
  CLI for rebuilding the D2 per-word D₀ calibration from audio on
  disk (`python -m samskrita_dhvani.calibrate --references …
  --recitations … --source-id … --acquired-on …`): conventional
  layout (`<word_id>.wav` canonicals; `<word_id>__take.wav` or
  `<word_id>/` known-correct groups), mandatory provenance,
  overwrite protection, loud per-word/per-take skip notices, and a
  printed measured-values table. Its fixtures exposed and fixed a
  real degenerate-calibration edge case: a corpus with zero duration
  variation measures D₀_duration = 0, which would divide by zero at
  scoring time — `Calibration` now rejects non-positive scales at
  construction. 8 CLI tests. [2026-10-01]
- `tools/e2e_render_check.py`, `tools/e2e_flow.py`,
  `tools/e2e_flow_negative.py` — reusable headless-Chrome E2E
  harnesses (CDP-driven; render assertions, fake-mic flow, and
  negative/offline cases). [2026-10-01]
- `files/e2e-screens/` — 4 evidence screenshots from the flow E2E
  (SPD upload/mic 503 cards, GVR fallback panel, GVR decode
  failure). [2026-10-01]
- `samskrita_dhvani/record.py` + `web/record.html` +
  `tests/test_record_api.py` — Phase 4 unit 5: the D5 recording
  booth (session sheets, per-clip checklists, D1+VAD gating,
  server-computed take numbers, `data/_incoming/` capture
  discipline, ear-check-gated promotion mapping; see the Unit 5
  entry above). 14 tests; pytest 118. [2026-10-01]
- `tools/e2e_booth.py`, `tools/e2e_booth.sh`,
  `files/e2e-screens/booth-*.png` — booth E2E harness + 4 evidence
  screenshots (fake-mic capture flows + server-side disk truth).
  [2026-10-01]
- `files/GvrRegistryDataPlan.md` — FR-22 GVR training-data plan:
  one-chapter target (Ch. 2, vv. 1–20, ≥3 recitations across ≥2
  reciters), source priority (Gita Supersite permission → licensed
  archives → D4 booth fallback), per-reciter split assignments
  fixed in advance, the 9 per-row acceptance gates, and the exact
  machine steps from audio to trained model to NFR-20 evaluation.
  Plan only — no audio acquired under it yet. [2026-10-01]
- `.gitignore` — `Audio_files/` added (Atharvaveda kanda WAV batch,
  10,097 files / 2.2 GB local-only clip download), following the
  large-corpus-holdings convention. [2026-10-01]
- `tools/build_gvr_itemlist.py` + `data/gvr/ch2_itemlist.json` +
  `files/PROVENANCE.md` GVR-TXT-01 — checked chapter-2 mūla item
  list for the D4 booth mode from the named public-domain text
  source (parse/sequence/spot-check/round-trip gates; label text
  only). [2026-10-01]
- `samskrita_dhvani/record.py` + `web/record.html` +
  `tests/test_record_api.py` — Phase 4 unit 6: D4 verse mode for the
  recording booth (program switch, `GVR-REC-` sessions, tradition
  capture, verse item list + modal text, per-verse take numbering,
  protocol-named promotion mapping; D5 flow unchanged). 5 new tests;
  pytest 123. [2026-10-01]
- `tools/e2e_booth.py` + `files/e2e-screens/booth-d4-verse-take.png`
  — D4 E2E flow added (verse capture with real mūla display;
  server-side sidecar/tradition assertions). [2026-10-01]
- `samskrita_dhvani/build_registry.py` + `tests/test_build_registry_cli.py`
  — Phase 4 unit 7: the FR-22 registry-build CLI (gated conversion of
  a promoted D4 batch into `data/gvr_registry.json`; split policy per
  the corrected plan §3; from_json self-check). `registry.py` gained
  the explicit `split_policy` field; `build_gvr_itemlist.py`/`data/gvr/ch2_itemlist.json`
  unified on zero-padded verse ids. 10 new tests; pytest 133.
  [2026-10-01]
- `tools/restore_spd_audio.py` +
  `data/provenance/spd_listen_2026-09-23/WALKTHROUGH.md` — SPD-01/02
  audio restoration after the local wipe (63/63 Loyola sha16-verified,
  5/5 Hall byte-verified, 9/9 boosted renders rebuilt) + the owner's
  ear-check quickstart with the verdict handoff template. Restored
  audio deliberately untracked (do-not-redistribute licenses).
  [2026-10-01]
- `data/provenance/d4_recite_sheet_2026-10-01.md` — D4 owner-reciter
  session aid: 20 verses from the checked item list with take
  checkboxes + post-session handoff. Booth launched for the owner
  (`setsid`-detached, :8030); no takes captured by the agent —
  session + consent + reciting are the owner's. [2026-10-01]
- Full-chain rehearsal (synthetic, quarantined to /tmp, deleted
  after): live booth → promote mapping → `build_registry` →
  `GvrRecognizer.train/save/load/predict` all verified working
  against the real server and real item list; registry-of-record and
  model path confirmed untouched. No numbers reported (FR-23).
  [2026-10-01]
