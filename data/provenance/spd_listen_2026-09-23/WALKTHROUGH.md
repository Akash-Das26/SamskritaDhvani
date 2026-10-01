# Ear-Check Walkthrough — next session quickstart

**Audio restored 2026-10-01** after a local disk wipe (see Review.md
Phase 6 restoration entry). Every file is verified against the
2026-09-22 sweep: Loyola by sha256-prefix match against
`MANIFEST.csv` (63/63), Hall by exact recorded byte size + decoder
duration (5/5). The boosted evidence renders were regenerated from
the restored sources with the documented recipe (peak → 0.60), so
the 2026-09-23 sweep numbers (VAD fractions, item counts, levels in
`listenthrough_auto.csv`) remain valid as-run data — no re-sweep
needed.

**Only you can do the listening part.** Budget ~30 min. Open this
file, CHECKLIST.md, and a file manager; work top to bottom; mark
CHECKLIST.md boxes as you go.

## Part 1 — Hall term list (~10 min)

Files: `data/spd/hall_sanskrit_pronunciation/skpro_00.mp3` … `skpro_04.mp3`
(sizes byte-identical to the PROVENANCE SPD-01 sub-table).

- skpro_01 (1001 s) + skpro_02 (1237 s): the 160+ term list. Skip
  through at ~5 points per file; note the term → pause → term pattern
  and whether English meanings are interleaved (affects clip cutting).
  Spot 8–10 known terms (kṛṣṇa, dharma, jñāna, kṣetra…) for
  retroflex/aspirate/ṛ crispness. Verdict per file: PASS/QUARANTINE/FAIL.
- skpro_00/03/04: 60-second spot each. Verdict per file.

## Part 2 — Loyola healthy set (~10 min)

Files: `data/spd/loyola_cahill_sound_files/*.mp3` (63 files; the
noun1–9 set is quarantined — skip it here). Per CHECKLIST Part 2:
paradigm structure (`deva_masc`, `phala_neut`, `dhenu_fem` exist in
MANIFEST), label consistency on 6–8 declension files + the pronoun
set, 3 verb files, 2 verse/exercise readings.

## Part 3 — The quarantined noun1–9 intelligibility call (~10 min)

Files: `data/provenance/spd_listen_2026-09-23/boosted_audio/noun{1..9}_*_boost.wav`
(9/9 re-rendered; boost = peak → 0.60, matching the recorded ×6.7–13.2
range). Spot 4 minimum (noun1, 4, 6, 8). Decision per CHECKLIST:
≥6/9 intelligible → quarantine lifts for those files (front-end gain
normalization becomes mandatory); else the whole set stays excluded.

## Part 4 — Hand me the verdict

Paste this (filled) into the chat or CHECKLIST.md — I will log it in
PROVENANCE.md + Review.md, and the eligible sets unlock reference-clip
cutting (FR-12) → the D5 booth → `calibrate` flow:

```
Ear check verdict (owner, <date>):
- Hall skpro_00..04: [PASS/QUARANTINE/FAIL per file]
- Loyola declensions/pronouns/verbs: [verdict + any label mismatches]
- noun1–9 intelligibility: [n]/9 intelligible → [lift quarantine for
  those files / keep excluded]
- Label mismatches found: [list, or none]
- Overall: SPD reference sets eligible? [yes / partially (which) / no]
```

Playback: any local player (mpv/vlc); spectrogram evidence for the
worst-case files is in this directory (`*_head.png`, `noun*.png`,
`verb_bhu_1stc.png`).
