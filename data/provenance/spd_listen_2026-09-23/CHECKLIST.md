# SPD Reference Listen-Through — Human Ear Check Checklist

**Date staged:** 2026-09-23
**Automated pass:** complete (`listenthrough_auto.csv` — 68/68 files, 0
VAD failures, 0 clipping signatures, 0 DC offsets; per-file VAD speech
fraction, item counts, head/tail levels).
**What this checklist decides:** DataIntegrity §4 step 1's "matches its
label by listening" for the SPD reference sets (PROVENANCE SPD-01,
SPD-02). Estimated time: **25–35 min**. Mark boxes as you go; your
final verdict gets logged in PROVENANCE.md and Review.md, and it is
what makes these files pipeline-eligible.

**Decision rule (pre-stated, apply as written):**
- PASS → the file's group is eligible as reference material (final
  gate before FR-12 reference-clip cutting).
- QUARANTINE → usable for pipeline development, excluded from
  reference duty and from any reported number.
- FAIL → excluded outright; count it, do not replace it
  (DataIntegrity §3.1).

---

## Part 1 — Hall term list (skpro_01, skpro_02) — ~10 min

Files: `data/spd/hall_sanskrit_pronunciation/skpro_01.mp3` (1001 s),
`skpro_02.mp3` (1237 s). These carry the 160+ term list that Open
Item 1 mines the SPD word list from.

- [ ] **Itemization:** skip through at ~5 points per file. Spoken terms
      should be clearly separated (term → pause → term). Note whether
      the speaker also gives the English meaning (the booklet says he
      does) — this affects how reference clips get cut.
- [ ] **Count check:** the VAD proxy found 668 + 946 items. Given
      term+definition pairs, 160+ terms is plausible. Sanity only —
      no exact match expected.
- [ ] **Pronunciation quality:** spot 8–10 terms you know (e.g.
      कृष्ण kṛṣṇa, धर्म dharma, ज्ञान jñāna, क्षेत्र kṣetra). Retroflex
      ṭ/ḍ, aspirates kh/gh/th/dh, and ṛ should be clearly articulated
      (this is an instruction recording by a Harvard-trained Sanskritist
      — expect crisp). Verdict per file: PASS / QUARANTINE / FAIL.
- [ ] **skpro_00/03/04:** 60-second spot each (intro, summary, Gita
      verses). Verdict per file: ___

## Part 2 — Loyola declensions/pronouns (non-quiet files) — ~10 min

Files: 54 files outside the noun1–9 quiet set (declensions by gender,
pronouns, verbs, verse readings). Levels are healthy here (rms −35 to
−40 dB).

- [ ] **Paradigm structure:** listen to `deva_masc.mp3`, `phala_neut.mp3`,
      `dhenu_fem.mp3` (or similar) — each should be a systematic
      case-by-case recitation (nom/acc/inst/dat/abl/gen/loc/voc ×
      sg/du/pl). The VAD counts (129–304 items/file) suggest forms
      are repeated (likely 2× or case+example-noun patterns) — note
      the actual pattern for the clip-cutting plan.
- [ ] **Label consistency:** the filename stem should match the
      recited stem (e.g. `nadii_fem.mp3` recites नदी nadī- forms;
      `gauri_fem.mp3` गौरी gaurī-). Check 6–8 files across genders
      and the pronoun set (`yusmad`, `asmad`, `etad`, `idam`, `tad`,
      `kim`, `yad`, `adas`). Mismatch = label error → note the file.
- [ ] **Verb files** (`verb_*`, 11 files): stem should match (bhū-,
      gam-, etc.). Spot 3.
- [ ] **Verse/exercise readings:** spot 2. Verdict per group: ___

## Part 3 — The quarantined noun1–9 set — the intelligibility call — ~10 min

Files: `data/provenance/spd_listen_2026-09-23/boosted_audio/
noun{1..9}_*_boost.wav` — gain-boosted renders (peaks lifted 0.045–0.09
→ 0.60; boosts ×6.7–13.2). **The boost is a listening aid** — the
decision is about whether the *content* beneath the low level is
intact speech, not whether the original level is acceptable (we know
it isn't; that's why they were quarantined).

For each of the 9 (or spot 4 minimum: noun1, noun4, noun6, noun8):

- [ ] Words are clearly articulable above the noise floor (hiss is
      expected and OK if words ride over it).
- [ ] Stem matches the filename (1 deva- masc, 2 ramā-? fem, 3 kanyā-
      fem, 4 phala- neut, 5 nadī- fem, 6 vāri- neut, 7 dhī- fem,
      8 strī- fem, 9 bhānu- masc).
- [ ] Syllable-final stops/visarga audible enough for formant analysis
      (the SPD use case).
- [ ] Verdict per file: INTELLIGIBLE / UNINTELLIGIBLE. If ≥ 6 of 9
      pass → the quarantine lifts for those files with **gain
      normalization at the front-end** noted as mandatory; else the
      whole noun1–9 set stays excluded from reference duty and the
      word list mines only Hall + the healthy Loyola files.

## Part 4 — Record the verdict

Fill in and paste into Review.md (or tell me the results and I'll
log them):

```
Ear check verdict 2026-09-23 (owner):
- Hall skpro_00..04: [PASS/QUARANTINE/FAIL per file]
- Loyola declensions/pronouns/verbs: [verdict + any label mismatches]
- noun1–9 intelligibility: [n]/9 intelligible → [lift quarantine for
  those files / keep excluded]
- Label mismatches found: [list, or none]
- Overall: SPD reference sets eligible? [yes / partially (which) / no]
```
