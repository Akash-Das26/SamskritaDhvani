# demo/DEMO_DATA.md — demo-only data copied from Dhvani-Yantra-main

> **Credit.** Dhvani-Yantra was built by **AtulTejaswi**
> (<https://github.com/AtulTejaswi/Dhvani-Yantra>). The author gave
> permission to copy it into this demo; these copies are used only for
> the demo screen and are credited here and in `demo/demo.md`. The
> upstream repository states no licence of its own, so nothing from it
> has been re-licensed or presented as this project's work.

**These files are not project data.** They are synthetic machine-generated
speech (Microsoft Edge Neural TTS) taken from a read-only neighbouring
project, copied only so the demo screen has a reference clip and a
provisional D₀ to score against. None of it is ear-verified, none of it
has a PROVENANCE.md entry under this project, and none of it may feed
`calibrate`, `build_registry`, training, `evaluate`, `score_attempts`, or
any reported number.

- Source tree: `Dhvani-Yantra-main/` (treated as read-only; nothing in it
  was modified, moved or deleted). Upstream project named in its README:
  <https://github.com/AtulTejaswi/Dhvani-Yantra>.
- Source statements: `Dhvani-Yantra-main/README.md` and
  `Dhvani-Yantra-main/data/SOURCES.md`. Everything in `data/audio/` is
  flagged `[SYNTHETIC …]` there.
- Licence as stated upstream: "edge-tts output (free Microsoft Neural
  TTS)". No other licence is stated for the audio.
- The copies live under `demo/data/`, which is gitignored
  (`demo/.gitignore`); they are never committed.
- Regenerate with `python -m demo.prepare_demo_data` (decodes each file
  with `load_audio_16k` and rejects anything whose WebRTC-VAD speech
  fraction is ≤ 0.10).

## Served assets (`demo/data/static/`)

The server no longer reads `Dhvani-Yantra-main/` at runtime. Every asset
it serves is copied first by `python -m demo.prepare_demo_static` into
`demo/data/static/`, which is gitignored with the rest of `demo/data/`:

| source | copy | files |
|---|---|---|
| `Dhvani-Yantra-main/data/audio/` | `demo/data/static/audio/` | 101 WAV + `p1_dataset.json` |
| `Dhvani-Yantra-main/data/gita/` | `demo/data/static/gita/` | 180 WAV + `p2_dataset.json` |
| `Dhvani-Yantra-main/results/P1/` | `demo/data/static/P1/` | 9 PNG + 5 JSON/CSV |
| `Dhvani-Yantra-main/results/P2/` | `demo/data/static/P2/` | 1 PNG + 3 JSON/CSV |
| `Dhvani-Yantra-main/results/P3/` | `demo/data/static/P3/` | 5 PNG + 1 MP4 + 4 JSON/CSV |

`/demo/static` mounts `demo/data/static/` with `follow_symlink=False`.
The P3 figures are Dhvani-Yantra's own run over three Blender Foundation
CC-BY films (*Tears of Steel*, *Sintel*, *Elephants Dream*), analysed
there with YOLOv8 + ByteTrack; the live video page uses the OpenCV HOG
+ centroid fallback instead. The symlink `Dhvani-Yantra-main/results/audio`
(created during earlier demo work) was removed after the copy; nothing
in the source tree was otherwise changed.

## Copied files

All 15 files are 16 kHz mono WAV, **59,982 bytes** each, VAD speech
fraction 0.26–0.37. `sha256` is of the copied bytes (identical to the
source bytes).

| demo path (under `demo/data/`) | original path (under `Dhvani-Yantra-main/`) | sha256 | source as stated by Dhvani-Yantra |
|---|---|---|---|
| `reference_words/kRSNa.wav` | `data/audio/ref_krishna.wav` | `6b4303c6509df42cf41fc089129e04b5675ecbbcdd25d417f66dd71a3e7853a9` | SYNTHETIC REFERENCE — Edge-TTS `hi-IN-MadhurNeural` reading कृष्ण (data/SOURCES.md, "References") |
| `reference_words/yoga.wav` | `data/audio/ref_yoga.wav` | `9bc93c5c5f4f564b9c206d2afcc93ac8e12ba6e9ee3ffdc3791940ae45fe02e5` | SYNTHETIC REFERENCE — Edge-TTS `hi-IN-MadhurNeural` reading योग (data/SOURCES.md, "References") |
| `reference_words/zAnti.wav` | `data/audio/ref_shanti.wav` | `e4ab61ead8deaf4e2804e1262cbb0c3f849cce362a0dc7ea3d044fadfde09064` | SYNTHETIC REFERENCE — Edge-TTS `hi-IN-MadhurNeural` reading शान्ति (data/SOURCES.md, "References") |
| `recitations/kRSNa__ref_krishna_alt.wav` | `data/audio/ref_krishna_alt.wav` | `85e0a5657dccb262dac6a36dadc76585078c8a2403df7a8bdcb3203004dec348` | SYNTHETIC REFERENCE (alternate voice) — Edge-TTS `hi-IN-SwaraNeural`, same word (data/SOURCES.md, "References") |
| `recitations/kRSNa__stud_krishna.wav` | `data/audio/stud_krishna.wav` | `3c9c174e7e9946622298ff4af3735b4d602105cf48f1619d9a8cc028b18430d6` | SYNTHETIC STUDENT TAKE — Edge-TTS `en-IN-PrabhatNeural` reading the romanised form "krishna" (data/SOURCES.md, "Student takes") |
| `recitations/kRSNa__stud_krishna_0_krisna.wav` | `data/audio/stud_krishna_0_krisna.wav` | `3465bf6f4ff8ddc324dbfdd92d850d0ad048e560e81067de8cef01c4fd2e378a` | SYNTHETIC STUDENT TAKE — same voice, romanised variant "krisna" (filename + data/SOURCES.md) |
| `recitations/kRSNa__stud_krishna_1_kishna.wav` | `data/audio/stud_krishna_1_kishna.wav` | `f9b23869ddeb3197ad85082504227256a4a52440e2fd21ca86d8847ba36cbb74` | SYNTHETIC STUDENT TAKE — same voice, romanised variant "kishna" (filename + data/SOURCES.md) |
| `recitations/yoga__ref_yoga_alt.wav` | `data/audio/ref_yoga_alt.wav` | `483c72ceb3d61e4ca7ea0d43166a7346d124bfa97ad5169c616b76fad808df61` | SYNTHETIC REFERENCE (alternate voice) — `hi-IN-SwaraNeural` (data/SOURCES.md) |
| `recitations/yoga__stud_yoga.wav` | `data/audio/stud_yoga.wav` | `111ff61a6061b9a95141f0e71e457424b909e10a0c8da49b71e5ab4da67f747c` | SYNTHETIC STUDENT TAKE — `en-IN-PrabhatNeural`, romanised "yoga" (data/SOURCES.md) |
| `recitations/yoga__stud_yoga_0_yog.wav` | `data/audio/stud_yoga_0_yog.wav` | `dac56270b8a65758221359a7f754ccc563edcf67ecf5b54ec96a02269939f8bc` | SYNTHETIC STUDENT TAKE — romanised variant "yog" (filename + data/SOURCES.md) |
| `recitations/yoga__stud_yoga_1_yuga.wav` | `data/audio/stud_yoga_1_yuga.wav` | `9bf4434898d185ba1355ca3b834f8af14ee986df8e22ab94ab450aa7a2258193` | SYNTHETIC STUDENT TAKE — romanised variant "yuga" (filename + data/SOURCES.md) |
| `recitations/zAnti__ref_shanti_alt.wav` | `data/audio/ref_shanti_alt.wav` | `ddcc60801d73d16b94c91ec647cc1083d13ea1328bc9a77eb8de0455102f3896` | SYNTHETIC REFERENCE (alternate voice) — `hi-IN-SwaraNeural` (data/SOURCES.md) |
| `recitations/zAnti__stud_shanti.wav` | `data/audio/stud_shanti.wav` | `cb565f6f90f380f63adfe58a13bf709e8a67724838b4c16a0035dbf3ccf9a463` | SYNTHETIC STUDENT TAKE — `en-IN-PrabhatNeural`, romanised "shanti" (data/SOURCES.md) |
| `recitations/zAnti__stud_shanti_0_shant.wav` | `data/audio/stud_shanti_0_shant.wav` | `f9a174149425e1ac52850c964931e9bbcb13c1f57fa93e2a93040711b27779c5` | SYNTHETIC STUDENT TAKE — romanised variant "shant" (filename + data/SOURCES.md) |
| `recitations/zAnti__stud_shanti_1_shanti.wav` | `data/audio/stud_shanti_1_shanti.wav` | `afea54bb4aee18496bac98c7658b953550586d1b167bd21321c13efa19e649a9` | SYNTHETIC STUDENT TAKE — romanised variant "shanti" (filename + data/SOURCES.md) |

## Not documented upstream

- **Per-file synthesis parameters** (exact voice per individual file, rate,
  seed, Edge-TTS version, generation date): **source not documented**.
  Only the per-family voice assignment quoted above is stated.
- **Why `ref_*_alt.wav` is exactly the same byte length as the reference**:
  **source not documented**; no per-file production note exists upstream.
- **Any human verification of these clips**: **source not documented** —
  nothing upstream claims a listen-through, and this project has none.
- **A licence beyond "edge-tts output (free Microsoft Neural TTS)"**:
  **source not documented**.

## GVR model

`demo/data/gvr/model.json` is the demo's verse model. It is a JSON
envelope (`gvr_classifier` persists JSON under a `.pkl` name upstream),
so the file was renamed from `model.pkl` to `model.json` without changing
a byte; `demo/server.py` is the only reference. The demo's
`/api/gvr/recognize` route does not use it — see `demo/demo.md` §5.

## Verse texts

The 10 Devanagari verse texts the demo displays come from
`Dhvani-Yantra-main/src/speech_b/p2_build_data.py`, `VERSE_TEXT`
(the same constant used to synthesize the verse audio). They were
compared with the demo's `GITA_VERSE_TEXTS` after stripping spaces,
`।`/`॥` and `|`:

| verse | difference |
|---|---|
| 1.1 | the demo adds the speaker tag `धृतराष्ट्र उवाच`; the rest matches |
| 2.14, 2.47, 2.62, 4.7, 4.8, 9.26, 10.20 | identical |
| 9.22 | Dhvani-Yantra has `अनायाश्चिन्तयन्तो`; the demo has the correct `अनन्याश्चिन्तयन्तो` (`ananyāś cintayanto`). The demo text was kept; the upstream typo is recorded here. |
| 18.66 | the demo had `त्वा`; Dhvani-Yantra has `त्वां` (`tvāṃ`), which is correct. The demo was corrected on 2026-10-30. |

## Derived artifact

`demo/data/calibration.json` is generated from these files by
`python -m demo.build_demo_calibration` (same `CalibrationBuilder` the
`calibrate` CLI drives). It is provisional, synthetic, and gitignored. It
was **not** written to `data/spd/calibration.json` and must never be
treated as the project's calibration.

## Never

- Never copy these into `data/` or `corpus/`.
- Never cite any number produced from them as a result.
- Never let them into `calibrate`, `build_registry`, `train`,
  `evaluate`, `score_attempts`, or the NFR-10 correlation.
