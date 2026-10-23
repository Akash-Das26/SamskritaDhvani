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
- **SPD attempts (D5) — batch scoring:** promoted attempts are scored
  through `python -m samskrita_dhvani.score_attempts --attempts <dir>
  --out <scores.jsonl>`, which reads the word from the §3 filename and
  applies the same gates as `POST /api/spd/score`. The **filename stem,
  verbatim** (e.g. `spd_krsna_asha_spd-rec-20261023-01_t2_var-sub`) is
  the attempt ID the NFR-10 rating sheet must list; do not rename a
  promoted clip after it has been rated.
- **Reference-reciter changes:** if the reference reciter changes,
  SPD's per-word `D₀` calibration must be recomputed (design D2) and
  the change logged in `Review.md`.

## 5. Acceptance rule

A clip is eligible for the corpus only when: (a) its checklist row is
complete, (b) the session sheet is complete, (c) the file passes the
`DataIntegrity.md` §4 automated sweep (valid decode, non-silent, no
clipping), and (d) a PROVENANCE.md entry references the session. Until
then it stays in `data/_incoming/` (not the corpus tree).

**Enforced in code (2026-10-23):** this rule is applied by

```bash
python -m samskrita_dhvani.promote --session <session-id> --dry-run
python -m samskrita_dhvani.promote --session <session-id> --apply
```

`--dry-run` prints a per-clip pass/hold table and moves nothing;
`--apply` moves only clips that pass every gate and prints the
promoted/held counts by reason. A held clip stays in
`data/_incoming/<session-id>/` and is never repaired or deleted. What
the code checks:

- **Session sheet (§1):** `data/provenance/REC_<session-id>.md` exists,
  all fourteen §1 fields are filled, the sheet's Session ID matches,
  the recitation tradition is stated, and Consent cites a
  form/reference rather than a bare "yes".
- **Checklist (§2):** the clip has exactly one row with its filename,
  all eleven columns filled, and the row's Session ID matches.
- **Sweep (§4):** the clip re-decodes, clears the VAD speech-fraction
  line, shows no clipping (peak < 0.99 and < 0.1% of samples at
  |x| ≥ 0.999), and is not listed in `data/EXCLUDED.csv`.
- **Provenance:** `files/PROVENANCE.md` references the session ID.
- **Target safety:** an existing target file is never overwritten; the
  clip is held and named.

**Still manual:** the §5 label ear-check (nothing in the promote path
claims a label was listened to), the truthfulness of the filled sheet
(the gate checks completeness and session match, not whether the
reciter details are accurate), and the decision to promote at all.
`POST /api/record/promote` remains a staging helper that writes
`PROMOTION.md` and never moves a file, so it cannot bypass these
gates.

### Using the skeleton

```bash
python -m samskrita_dhvani.rec_skeleton --session <session-id>
```

This writes `data/provenance/REC_<session-id>.md` from the booth's
`session_meta.json` and the clips present. Machine-filled: **§1**
Session ID, Date / time, Program (D4/D5), the recording-format target,
and the materials version when the booth recorded one; **§2** File,
Session ID, Item, Take #, Duration, Peak dBFS, and Clipping? (measured
by the same criterion the §4 sweep uses).

The blanks are deliberate, not omissions: room and noise, reciter ID
and background, recitation tradition, consent reference, device, levels
notes, procedure, transfer details, plus the §2 columns *Silence
trimmed?*, *Transcript verified?*, *Sweep date*, and *Provenance entry*.
Nothing in `session_meta.json` is copied for those fields — a person
must confirm them. Until they are filled, the skeleton **fails**
`promote`'s sheet and checklist gates by design. Re-running without
`--force` refuses to touch an existing sheet; `--force` copies the old
one to `REC_<session-id>.md.bak-<UTC stamp>` first and prints the
backup path.
