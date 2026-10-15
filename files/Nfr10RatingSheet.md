# NFR-10 Rater Sheet — SPD attempt ratings (blank template)

**Purpose:** this is the human-judgment half of `SRS.md` NFR-10
("validate SPD's score against instructor/native-speaker ratings").
It stays blank until D5 pronunciation attempts exist (booth:
`python -m samskrita_dhvani.record --port 8030`). One sheet per rater;
do not alter the rubric — comparability across raters is the point.
No rating in a completed sheet is ever entered anywhere else without
its rater header.

**How to use (once attempts exist):**
1. The attempt folder lists files as `<attempt_id>.wav` with the word
   id and session provenance.
2. For each attempt: play the audio, read the target word below, give
   one 1–5 rating, optionally a short note.
3. Rate the ATTEMPT against the printed target word — not against the
   reference recording, and not against your own accent preferences
   beyond the stated tradition.
4. Sign the footer and return the sheet; the NFR-10 correlation is
   then computed from these ratings and the corresponding
   `POST /api/spd/score` similarity values.

---

## Rater header (completed once per rater)

| Field | Value |
|---|---|
| Rater ID (name or pseudonym) | |
| Role | instructor / native speaker / advanced student *(circle one)* |
| Native language(s) | |
| Script familiarity (Devanagari / IAST / neither) | |
| Recitation tradition practiced or studied *(name it — e.g. classical Sanskrit; Vedic accentuation; regional tradition; per DataIntegrity §3.6)* | |
| Years of Sanskrit study / teaching | |
| Date of rating | |

## Rubric (fixed — applies to every item)

| Rating | Meaning |
|---|---|
| 1 | Incorrect as Sanskrit — wrong sounds/substitutions or wrong syllable structure; a listener could not recover the intended word |
| 2 | Noticeably incorrect but identifiable as the intended word |
| 3 | Acceptable with minor errors (e.g. one axis of a difficulty pair slightly off: retroflex/dental, aspiration, vowel length) |
| 4 | Correct; only a minor non-native tint |
| 5 | Native / credentialled-speaker correct for the stated tradition |

`N/A` may be used instead of a number only when the audio is
unrateable (inaudible/corrupt) — such attempts are excluded from the
correlation and counted in the report's limitations.

## Ratings (one row per attempt — blank until D5 attempts exist)

| Attempt ID | Word ID | Devanagari | IAST | Rating (1–5) | Notes (optional) |
|---|---|---|---|---|---|
| | | | | | |
| | | | | | |
| | | | | | |
| | | | | | |
| | | | | | |
| | | | | | |

*(add rows as needed; keep the Attempt ID exactly as the file/session
names it so the join with `POST /api/spd/score` outputs is unambiguous)*

## Rater footer

| Field | Value |
|---|---|
| Total attempts rated | |
| Attempts marked N/A (with reasons) | |
| Rater signature / initials | |

---

*Template created 2026-10-15 (Phase 6 report-prep pass). Filled sheets
are evidence: attach them (or their scan) to the NFR-10 unit's
Review.md entry, and record the correlation run there with its exact
command (Ground Rule 1 — the sheet itself carries no computed
numbers).*
