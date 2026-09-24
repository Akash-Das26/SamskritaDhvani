# SamskritaDhvani — Frontend.md

**Project full title:** *SamskritaDhvani: A Hybrid Signal Processing
Approach to Sanskrit Phonetic Assessment and Bhagavad Gita Verse
Recognition*

**Purpose:** This is the frontend design plan for the SamskritaDhvani
demo — the web UI a user interacts with to (a) practice/test Sanskrit
word pronunciation (SPD) and (b) submit a Gita verse recitation for
recognition (GVR). It supersedes the placeholder "Streamlit dashboard"
line in `Implementation.md` §4 with a properly designed frontend, built
with **Google Stitch** (`stitch.withgoogle.com`) and backed by the
Python SPD/GVR pipeline as an API. This is `Development.md` Phase 3
(Design) work for the frontend specifically — get sign-off on the
screen list and data contract below before Phase 4 (Coding) generates
or wires up any UI.

Companion documents: `Development.md` (process), `Implementation.md`
(pipeline architecture this UI calls into), `SRS.md` (FR/NFR IDs the UI
must expose), `DataIntegrity.md`, `Review.md`.

---

## 1. What Stitch is and how it fits here

**Google Stitch** is a free, browser-based AI UI design tool
(`stitch.withgoogle.com`, Google Labs, Gemini-powered). You describe a
screen in plain language (or feed it a sketch/reference image), it
generates a high-fidelity mockup, and you iterate on it with further
prompts. It exports to **Figma** or to **clean HTML/CSS (Tailwind)**
code directly — the HTML/CSS export is what this project will use,
since the backend is Python/FastAPI-style, not a Figma-to-code
pipeline.

**Division of labor:**
- **Stitch** produces the visual design and static markup/styling for
  each screen (§3).
- **You (Phase 4 Coding)** wire that static markup to the real backend:
  replace Stitch's placeholder text/data with live calls to the SPD/GVR
  inference endpoints (§4), add the audio recording/upload widget
  (Stitch won't generate working `<audio>`/`MediaRecorder` logic —
  that's real frontend code layered onto its output), and add state
  management for multi-step flows (record → score → view breakdown).

**Rule specific to this file (mirrors `Development.md`'s Phase 3
rule):** Stitch's output is a starting visual design, not a finished
feature. No screen is "done" until its live data binding is wired and
tested per `Development.md` Phase 5 — a good-looking static export is
not a completion state, same as "should work" isn't for the backend.

---

## 2. Design direction (brief for every Stitch prompt below)

State this once and reuse it in every Stitch prompt so the screens
stay visually consistent (Stitch treats each generation somewhat
independently unless you carry the context forward on its canvas):

> Clean, calm, academic tool — not a gamified language-learning app.
> The audience is a linguistics/CS student and their instructor, not a
> mass consumer. Warm, parchment-adjacent neutral background (off-white
> / warm gray), a single accent color (deep saffron or maroon — evoke
> manuscript/temple contexts without being kitschy), Devanagari
> typography treated as a first-class visual element (large, legible,
> given room to breathe) alongside a clean sans-serif for UI chrome and
> a monospace for technical readouts (MFCC values, IDs). Generous
> whitespace, minimal iconography, no stock "language app" mascots or
> flags. Data (scores, confusion matrices, waveforms) should look
> precise and legible, not decorative — this is closer to a research
> dashboard than a consumer app.

---

## 3. Screens

### 3.1 Home / Landing

**Purpose:** Orient a first-time visitor (student, instructor, evaluator)
and route to SPD or GVR.

**Contents:**
- Project title (full title from this doc's header, or a shortened
  "SamskritaDhvani" wordmark) with a one-line subtitle explaining the
  two tools.
- Two clear entry cards: "Practice Pronunciation" (SPD) and "Recognize
  a Verse" (GVR) — each with a one-sentence description, not marketing
  copy.
- A small, honest scope note: closed-set verse recognition, diagnostic
  (not certifying) pronunciation scoring — mirrors `Implementation.md`
  §10's stated trade-offs; this belongs in the UI too, not just the
  report.
- Footer link to "About / Methodology" (optional page linking out to
  the project report or `Implementation.md`'s public summary).

**Stitch prompt to generate this screen:**
> [paste the Design Direction from §2] — Design a landing page for a
> Sanskrit speech-processing research tool called "SamskritaDhvani."
> Two large entry cards: "Practice Pronunciation" (icon: sound wave)
> and "Recognize a Gita Verse" (icon: manuscript/scroll). Include a
> one-line subtitle and a small italic scope note about the tool's
> limitations. No login/signup — this is a local demo tool.

### 3.2 SPD — Practice Pronunciation

**Purpose:** Implements `SRS.md` FR-10/FR-11 in the UI — pick a word,
record/submit an attempt, see the similarity score and per-axis
breakdown.

**Flow (multi-step, single screen with state):**
1. **Word picker:** a searchable/browsable list of the SPD word list
   (`SRS.md` FR-12) showing Devanagari + IAST transliteration
   side-by-side (e.g. कृष्ण / kṛṣṇa) with a "play reference" button per
   word.
2. **Record/upload step:** a record button (mic icon, with a visible
   recording-in-progress state and a re-record option) plus a
   drag-and-drop/file-picker fallback for uploading a `.wav` clip.
3. **Result view:**
   - Large headline similarity score (e.g. "78%").
   - Per-axis breakdown as a small horizontal bar set or radar chart:
     vowel/formant distance, consonant/spectral distance, duration
     ratio, overall MFCC-DTW distance (`SRS.md` FR-11) — labeled
     plainly, not just numbers.
   - A waveform or aligned-spectrogram strip comparing reference vs.
     attempt (nice-to-have, not required for v1 — flag as optional in
     Phase 3 sign-off).
   - A "try again" action returning to step 2 for the same word.

**Stitch prompt:**
> [Design Direction] — Design a pronunciation-practice screen. Top:
> a word picker showing a Devanagari word large, with its IAST
> transliteration beneath it in italics, and a small "play reference
> audio" button. Middle: a prominent circular record button with a
> waveform visualizer while recording, and a secondary "upload audio
> file" link. Bottom (shown after submission): a large percentage
> score, and below it four labeled horizontal bars for sub-scores
> (Vowel accuracy, Consonant accuracy, Duration match, Overall
5 spectral match), each with its own percentage. Include a "Try again"
> button.

### 3.3 GVR — Recognize a Verse

**Purpose:** Implements `SRS.md` FR-21 — submit a recitation, get back
a recognized verse ID and confidence.

**Flow:**
1. **Record/upload step:** same record/upload pattern as §3.2 step 2,
   but framed for a full verse (longer expected duration — show a
   timer, not just a level meter).
2. **Result view:**
   - Recognized verse ID prominently (e.g. "Bhagavad Gita 9.26") with
     its Devanagari text and a short English gloss shown beneath once
     recognized.
   - Confidence score, and — important for honesty per
     `Implementation.md` §8 — a short list of the next-best candidate
     verses with their scores, not just the top-1 answer presented as
     certain.
   - A note if the input verse falls outside the closed set the model
     was trained on (don't force a confident wrong answer — surface
     "not confidently recognized" as a legitimate result state).

**Stitch prompt:**
> [Design Direction] — Design a verse-recognition result screen. Show
> a large "Recognized: Bhagavad Gita 9.26" headline, the Devanagari
> verse text beneath it in a large serif-adjacent Devanagari font, a
> confidence percentage as a horizontal progress bar, and below that a
> compact ranked list of the next 2–3 candidate verses with their
> lower confidence scores in muted gray. Include a state for "Not
> confidently recognized" with a neutral, non-alarming visual
> treatment (not a red error state — this is an expected outcome, not
> a failure).

### 3.4 (Optional, Phase-3-decide) Corpus/Model status page

**Purpose:** For the instructor/evaluator audience — a transparency
page showing what the model actually knows: SPD word list size, GVR
verse coverage (e.g. "62 of 700 verses, Chapter 9"), and links to the
Data Integrity Sweep summary from `Review.md`. This directly serves
`Development.md` Ground Rule 1 (no fabricated numbers) by making the
tool's real scope visible in the UI itself, not just buried in docs.

**Decide in Phase 3 sign-off:** include for v1, or defer to a
"future work" note — this is not required for the core SPD/GVR
functionality to work, so treat it as optional scope, not a blocker.

**Stitch prompt (if included):**
> [Design Direction] — Design a simple transparency/status page: a
> card showing "Pronunciation word list: 24 words," a second card
> showing "Verse recognition coverage: Chapter 9, 26 of 34 verses
> trained," and a small table of when the corpus was last validated
> (date, samples checked, issues found) styled like a lightweight
> research changelog, not a marketing stats page.

---

## 4. Frontend ↔ backend data contract (for Phase 4 wiring)

Stitch's export gives you markup and styling only — these are the
calls the real frontend code needs to make once wired to the SPD/GVR
Python pipeline (exact endpoint paths/framework are a Phase 3 decision
if not already fixed — FastAPI is a reasonable default, consistent
with `Implementation.md`'s Python-first stack):

| UI action | Needs from backend | Returns to UI |
|---|---|---|
| Load word list (§3.2 step 1) | Word registry (`SRS.md` FR-12) | List of `{devanagari, iast, reference_audio_url}` |
| Submit SPD attempt (§3.2 step 3) | Reference audio + uploaded attempt audio | `{similarity_pct, vowel_score, consonant_score, duration_score, mfcc_dtw_score}` per `SRS.md` FR-11 |
| Submit GVR attempt (§3.3 step 2) | Uploaded recitation audio | `{top_match: {verse_id, devanagari, gloss, confidence}, candidates: [{verse_id, confidence}, ...]}` per `SRS.md` FR-21 |
| Load status page (§3.4, if built) | Corpus registry + latest `Review.md` sweep entry | `{word_count, verse_coverage, last_sweep_date, sweep_summary}` |

**No fabricated states in the UI.** If a backend call fails or a model
isn't loaded, the UI must show an explicit error/empty state — never a
default/placeholder score presented as if it were real (this is the UI
equivalent of `Development.md` Ground Rule 1).

---

## 5. Workflow: from Stitch to a working screen

1. Open `stitch.withgoogle.com`, paste the Design Direction (§2) plus
   the specific screen prompt (§3.x) for one screen at a time.
2. Iterate with follow-up prompts on the same canvas (e.g. "make the
   score more prominent," "use a warmer accent color") until the
   screen matches the spec.
3. Export as HTML/CSS (Tailwind) — Stitch's native code export format
   — for each screen.
4. In Phase 4 (Coding), replace Stitch's placeholder content with real
   data bindings per §4's contract, add the recording widget (Web
   Audio API / `MediaRecorder`, not something Stitch generates
   functionally), and wire routing between screens.
5. Test each screen against `Development.md` Phase 5: does the record
   → submit → result flow actually work end-to-end against the real
   SPD/GVR backend, not just look right with placeholder data.

---

## 6. Open items (carry into `Review.md`)

**All four resolved by Phase 3 sign-off, 2026-09-23** (owner decisions;
logged in full in `Review.md`):  

1. ~~Waveform/spectrogram comparison (§3.2)~~ — **DEFERRED** for v1.
   The four per-axis bars carry the diagnostic content; the comparison
   strip is documented as a future enhancement (also unblocks v1 from
   the SPD reference-audio ear check).
2. ~~Corpus/Model status page (§3.4)~~ — **IN SCOPE for v1.** Four
   screens total: Home, SPD, GVR, Status. Status numbers are pulled
   live from the registry/manifest — never hardcoded (Ground Rule 1
   applies to the status page too).
3. ~~Backend framework/endpoint paths (§4)~~ — **CONFIRMED: FastAPI**,   
   endpoints exactly as tabled in §4: `GET /api/words`,
   `POST /api/spd/score`, `POST /api/gvr/recognize`, `GET /api/status`.
   Score schemas validated with pydantic. FastAPI/uvicorn enter via the
   Phase 2 verify-then-pin discipline (they were not previously
   installed).
4. ~~Browser compatibility target~~ — **CONFIRMED: desktop
   Chrome/Firefox minimum**, stated explicitly in the UI footer; the
   file-upload fallback covers other browsers. Mobile support is
   explicitly out of scope for v1.

---

*Update this file whenever a Phase 3 (Design) decision changes a
screen's scope, and log each screen's Stitch export + wiring status in
`Review.md` as it's completed.*
