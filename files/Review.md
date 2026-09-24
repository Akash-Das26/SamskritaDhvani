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

### Phase 5 (Testing) —

**Test run result (actual, not estimated):**
- _(fill in: command run, pass/fail, actual accuracy/correlation
  numbers with the exact script used to produce them)_

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
