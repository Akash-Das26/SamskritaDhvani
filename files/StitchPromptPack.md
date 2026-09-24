# Stitch prompt pack — SamskritaDhvani demo UI

**For:** generating the four signed-off screens (Phase 3 sign-off
2026-09-23) in Google Stitch → `stitch.withgoogle.com`.

**Workflow per screen:** paste the prompt below into a **new** Stitch
project → iterate with the follow-up suggestions → when it matches
spec, **Export → Code (HTML/CSS, Tailwind)** → save as
`web/stitch_exports/<screen>.html` in the repo. Stitch generates
visual design only; all wiring (recording, API calls, state) happens
afterwards in Phase 4.

---

## Screen 1 — Home / Landing → `web/stitch_exports/home.html`

```
Clean, calm, academic research tool — not a gamified language-learning
app. Audience: a linguistics/CS student and their instructor. Warm
parchment-adjacent neutral background (off-white / warm gray), a single
accent color (deep saffron or maroon — evoke manuscript/temple contexts
without being kitschy). Devanagari typography as a first-class visual
element (large, legible, room to breathe) alongside a clean sans-serif
for UI chrome and a monospace for technical readouts. Generous
whitespace, minimal iconography, no mascots or flags. Data should look
precise and legible, not decorative — closer to a research dashboard
than a consumer app.

Design a landing page for a Sanskrit speech-processing research tool
called "SamskritaDhvani." Header: the wordmark "SamskritaDhvani" in
large Devanagari-supporting type with the subtitle "Sanskrit
pronunciation assessment and Bhagavad Gita verse recognition." Two
large entry cards side by side: "Practice Pronunciation" (icon: sound
wave) described as "Record a word, compare it to a reference
recitation, and see a per-axis similarity breakdown" and "Recognize a
Verse" (icon: manuscript/scroll) described as "Recite a Gita verse and
see the recognized verse ID with confidence and runner-up candidates."
Below the cards: a small italic scope note reading "Scope: closed-set
verse recognition over a fixed verse list; pronunciation scores are
diagnostic, not certifying." Footer: "About / Methodology" link on the
left and "Best viewed in desktop Chrome or Firefox · microphone
required for recording" on the right. No login or signup — local demo
tool.
```

**Iterate until:** the two cards are visually equal in weight; the
scope note is visible without scrolling on a 1280×800 viewport; the
footer carries the browser line verbatim.

---

## Screen 2 — SPD Practice → `web/stitch_exports/spd.html`

```
Clean, calm, academic research tool — not a gamified language-learning
app. Audience: a linguistics/CS student and their instructor. Warm
parchment-adjacent neutral background (off-white / warm gray), a single
accent color (deep saffron or maroon). Devanagari typography as a
first-class visual element, clean sans-serif UI chrome, monospace for
technical readouts. Generous whitespace, minimal iconography. Precise,
legible data presentation — research dashboard, not consumer app.

Design a pronunciation-practice screen in three vertical sections.
Top section — word picker: a dropdown/search field ("Search the word
list…"), then the selected word shown large in Devanagari (e.g. कृष्ण)
with its IAST transliteration beneath it in italics (kṛṣṇa), a small
gray difficulty-axis tag (e.g. "consonant cluster"), and a "play
reference audio" button. Middle section — recording: a prominent
circular record button with a waveform visualizer strip beside it that
fills while recording, a live timer in monospace, a "re-record" text
link, and a secondary "upload audio file instead" link. Bottom section
— result: a large percentage score (e.g. 78%) as the headline, and
below it four labeled horizontal bars: "Vowel accuracy", "Consonant
accuracy", "Duration match", "Overall spectral match", each with its
own percentage in monospace. Include a "Try again" button at the
bottom. All numbers are placeholders in the mock only — visually mark
the result section as appearing after submission.
```

**Iterate until:** the Devanagari word is the largest element on
screen; the four bars have distinct labels AND values; record button
has a clear recording-in-progress state. **Note:** also add a result
variant showing an error card (muted, not red) reading "Scoring model
not available yet — audio validated OK" — this is the honest state the
wired UI shows until the scorer ships.

---

## Screen 3 — GVR Recognize → `web/stitch_exports/gvr.html`

```
Clean, calm, academic research tool — not a gamified language-learning
app. Warm parchment-adjacent neutral background, single accent color
(deep saffron or maroon), Devanagari as first-class typography,
monospace technical readouts, generous whitespace. Research dashboard
aesthetic.

Design a verse-recognition screen. Top: the heading "Recognize a
Verse" with a one-line instruction "Recite a verse from the trained
set, or upload a recording." A circular record button with an elapsed
timer (mm:ss in monospace) — verses are longer than words, so show the
timer prominently — plus a waveform level strip and an "upload audio
file instead" link. Below, the result view: a large headline
"Recognized: Bhagavad Gita 9.26", the Devanagari verse text beneath it
in a large serif-adjacent Devanagari font with room to breathe, a
short English gloss in smaller gray text, and a confidence percentage
as a horizontal progress bar. Under that: a compact ranked list of the
next 2–3 candidate verses with their lower confidence scores in muted
gray (verse IDs only). Also include a distinct result-state card for
"Not confidently recognized" — neutral, non-alarming treatment (not a
red error state; this is an expected outcome) with the text "The
recitation did not closely match any verse in the trained set."
```

**Iterate until:** the Devanagari verse text is large and readable;
the candidates list is visually secondary to the top match; the
"not confidently recognized" card exists as its own state. **Note:**
also add an "unavailable" variant: same layout, result area replaced
by a muted card reading "Verse recognition model not available yet —
no training recordings in the registry."

---

## Screen 4 — Corpus/Model Status → `web/stitch_exports/status.html`

```
Clean, calm, academic research tool. Warm parchment-adjacent neutral
background, single accent color (deep saffron or maroon), monospace
for all numbers, generous whitespace. Lightweight research changelog
aesthetic — not a marketing stats page.

Design a transparency/status page titled "Corpus & Model Status" with
the subtitle "What the tool actually knows, read live from the project
registries." Three cards in a row: (1) "Pronunciation word list" with
a large monospace count (e.g. 29) and sub-line "reference audio: not
yet verified"; (2) "Verse recognition coverage" showing "no entries"
in a muted style with a one-line reason "Gita audio sources blocked;
self-recording program pending"; (3) "Latest data-integrity sweep"
showing a monospace file count, total hours, and sweep date. Below the
cards: a small two-column table styled like a changelog with columns
Date | Check | Outcome and three example rows. Footer: "All numbers on
this page are read from project artifacts at request time."
```

**Iterate until:** all three cards present the "not available" states
as calmly as the available ones; the table reads as a changelog.

---

## After export — hand-off checklist

- [ ] All four exports in `web/stitch_exports/` (any filenames; tell
      me which file is which screen)
- [ ] Each screen visually iterated to match its spec above
- [ ] Any deviations from Frontend.md §2/§3 noted (I'll record them in
      Review.md)

Then the wiring pass happens: real `fetch()` calls to the four
endpoints, MediaRecorder/Web Audio recording, upload fallback, routing
between screens, all error/empty states live, and the Phase 5
end-to-end test per screen (record → submit → real result, or the
honest unavailable state where the model isn't built yet).
