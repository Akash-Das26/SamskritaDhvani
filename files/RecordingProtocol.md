# SamskritaDhvani — Recording Protocol (template)

**Purpose:** Per `DataIntegrity.md` §2–§3, no self-recorded clip enters
the corpus without a completed session sheet and per-file checklist.
This file is the template those records use. One filled sheet per
recording session; one checklist row per clip. Store completed sheets
as `data/provenance/REC_<session-id>.md` (create the directory at the
first session).

Applies to both self-recording programs approved in Phase 3 design:
**D4** (GVR canonical verse audio) and **D5** (SPD reference +
mispronunciation-variant recordings).

---

## 1. Session sheet (one per recording session)

| Field | Value (fill in) |
|---|---|
| **Session ID** | `SPD-REC-YYYYMMDD-NN` or `GVR-REC-YYYYMMDD-NN` |
| **Date / time** | |
| **Location / room** | room description, size, furnishings, reverb character |
| **Noise environment** | HVAC off? traffic/computer fans? phone on silent? |
| **Reciter ID** | name or anonymized ID + consent-form reference |
| **Reciter background** | years of study; fluency status (native/fluent/learner); first language |
| **Recitation tradition** | e.g. standard classical pronunciation, unaccented paṭha; **explicitly state whether any Vedic accent tradition is used** (`DataIntegrity.md` §3.6) — required per-file |
| **Consent** | usage consent obtained (form/checkbox reference); scope of use stated to reciter |
| **Device** | mic model/interface/recording app; distance mouth→mic |
| **Recording format** | target: WAV, ≥16 kHz, mono, 16-bit or better |
| **Levels** | peak dBFS observed (target −12 to −6 dBFS); clipping seen? |
| **Materials & version** | SPD word-list version / GVR verse-subset version; **text source for scripts** (verse text source + numbering convention) |
| **Procedure** | warm-up takes? repetitions per item (≥3 recommended); order randomized for variant recordings? breaks taken? |
| **Post-session transfer** | where files were copied, checksum method (e.g. `sha256sum`), who transferred |

## 2. Per-file checklist (one row per clip)

| File | Session ID | Item (word / ch.v) | Take # | Duration (s) | Peak dBFS | Clipping? | Silence trimmed? | Transcript verified? | Sweep date | Provenance entry |
|---|---|---|---|---|---|---|---|---|---|---|
| | | | | | | | | | | |

## 3. Naming convention

- SPD: `spd_<item>_<reciter>_<sessionid>_t<take>.wav`
- GVR: `gvr_c<chapter>v<verse>_<reciter>_<sessionid>_t<take>.wav`
- All lowercase ASCII in filenames; Devanagari text lives in the
  sidecar transcript/label file, never in the filename.
- `<item>` for SPD uses the romanized word-list key (e.g. `krsna`,
  `dharma`); variant takes append the variant tag (e.g. `_var-sub`
  substitution, `_var-del` deletion, `_var-len` vowel-length error).

## 4. Role-specific requirements

- **GVR canonical verse audio (D4, FR-22 registry):** one reference
  clip per verse, ≥3 takes retained per verse; verse ID recorded as
  `c<chapter>v<verse>` and cross-checked against the project's verse
  text transcription; reciter must be a named fluent reciter with
  tradition stated.
- **SPD references (D5, FR-12):** reference clips come from a named
  fluent reciter (Hall audio and self-recording are the current
  sources); learner-variant clips are recorded by separate consented
  speakers with the **intended error type labeled at record time**.
- **Reference-reciter changes:** if the reference reciter changes,
  SPD's per-word `D₀` calibration must be recomputed (design D2) and
  the change logged in `Review.md`.

## 5. Acceptance rule

A clip is eligible for the corpus only when: (a) its checklist row is
complete, (b) the session sheet is complete, (c) the file passes the
`DataIntegrity.md` §4 automated sweep (valid decode, non-silent, no
clipping), and (d) a PROVENANCE.md entry references the session. Until
then it stays in `data/_incoming/` (not the corpus tree).
