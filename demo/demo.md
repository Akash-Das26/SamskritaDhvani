# SamskritaDhvani demo — run sheet

> **DEMO ONLY.** Every audio reference is synthetic TTS. Calibration is
> provisional. Nothing here is a measured research result.
>
> **Credit.** Dhvani-Yantra was built by **AtulTejaswi**
> (<https://github.com/AtulTejaswi/Dhvani-Yantra>). The author gave
> permission to copy its audio, figures and model into this demo. The
> copies live under `demo/data/` (gitignored) and are credited on the
> pages that show them. Upstream states no licence, so nothing is
> re-licensed; see `DEMO_DATA.md`.

---

## 1. Start

```bash
# from the project root
.venv/bin/python -m demo.server          # http://127.0.0.1:8000
```

First run only, in this order:

```bash
.venv/bin/python -m demo.prepare_demo_data      # 25 WAVs -> demo/data/
.venv/bin/python -m demo.prepare_demo_static    # audio, gita, P1–P3 -> demo/data/static/
.venv/bin/python -m demo.build_demo_calibration # -> demo/data/calibration.json
```

The video tab runs its worker in a separate environment (the project venv
has no OpenCV):

```bash
python3 -m venv demo/.venv-video
demo/.venv-video/bin/pip install -r demo/requirements-video.txt
```

Pages: `/` · `/spd.html` · `/gvr.html` · `/status.html` · `/video.html` ·
`/demo-guide.html`.

---

## 2. Order to show things

1. **Home** — say what the demo is and that it is not a result.
2. **SPD, record `kRSNa`** — let the room watch one real take go to the API.
3. **SPD, sample take** — pick “different-voice reading of the word” and
   show that the score moves; then a “variant spelling” take.
4. **SPD charts A–D** — point at the source chip on each panel.
5. **GVR** — load the BG 9.26 sample (held-out voice), submit.
6. **GVR charts E–G** — live DTW distance, then the imported P2 figures.
7. **Video** — upload the 60 s sample, watch progress, walk the five
   sections. Say the banner out loud.
8. **Close** — the limitations, in the “do not claim” list.

Do not skip step 8; it is the point of the demo.

---

## 3. What to say at each step

**Home.** “Two speech tasks and one add-on: word-level similarity,
closed-set verse recognition, and a video analysis demo. Everything is
local and everything is synthetic.” Point at the DEMO banner.

**SPD record.** “I am recording one word. The browser resamples to
16 kHz and sends it to the local API. That request is scored by this
project's D2 scorer.” Say the number is a relative similarity, not a
grade.

**SPD sample take.** “This file is a different voice reading the same
word. The score drops even though the word is right — that is the
honest behaviour of a reference-matching scorer.”

**SPD charts.** “Each panel carries a chip: `LIVE · this attempt` for
numbers this request produced, `IMPORTED · Dhvani-Yantra, synthetic TTS
audio` for figures copied from the neighbouring project. The imported
ones are context, not our measurement.”

**GVR.** “Ten verses, closed set. This sample is from a voice that was
never used to build the templates.” Submit; read the relative score and
say “not a probability”.

**GVR charts.** “Graph E is live: the mean DTW distance to each of the
ten verse templates, lower is closer. Graphs F and G are Dhvani-Yantra's
P2 results — 60 synthetic clips, their model, their split.”

**Video.** “This is an add-on outside the SRS. The tracker is the OpenCV
HOG fallback plus centroid association, so it finds people-shaped
regions, not identities. The five panels are frames, scenes, motion,
tracks and a summary.”

**Close.** “No accuracy figure here belongs to this project. The only
real measurements are the per-request scores and the video pipeline's
own timings.”

---

## 4. What each chart is and where its data comes from

### `/api/spd/score` — provenance of every field

| field | where it comes from |
|---|---|
| `similarity_pct`, `vowel_score`, `consonant_score`, `duration_score`, `mfcc_dtw_score`, `reference_word` | **This project's D2 scorer**, `samskrita_dhvani/spd_scorer.py:335` (`score_attempt`); the % mapping is `100·exp(−D/D₀)` in `_norm_loglike_to_pct`, line 230, with the per-word D₀ from `demo/data/calibration.json` |
| `segments` | **Not from Dhvani-Yantra.** Built in `demo/server.py:270` from the vowel/consonant sub-scores (5–7 alternating entries with fixed multipliers). It is demo telemetry, not a per-segment measurement. |
| `dtw_path` | **Not this attempt's path.** `demo/server.py:284` returns entry 0 of Dhvani-Yantra's P1 `results.json` — the *reference-versus-itself* path, downsampled to ≤30 points. |
| `f1_ref`, `f2_ref` | Dhvani-Yantra P1 `results.json` baseline for the word's first entry (`demo/server.py:255`, `291`). |
| `f1_stu`, `f2_stu` | **Derived**, not measured: reference F1/F2 scaled by `(100 − vowel_score)/100` in `demo/server.py:262–263`. |
| `d_mfcc` | **Derived**, not the scorer's distance: `(100 − similarity_pct)/100 · 0.55` at `demo/server.py:288`. |
| `duration_ratio` | **Derived**: `duration_score/100` at `demo/server.py:290`. |

Plain statement: the D2 scorer supplies the five percentage fields.
**None** of `segments`, `dtw_path`, `formants`, `d_mfcc` or
`duration_ratio` comes from Dhvani-Yantra's scoring code; they are
constructed in `demo/server.py` from the D2 sub-scores and the P1 JSON
baselines. The UI labels them accordingly.

### Graphs

| panel | chip | what is plotted | data |
|---|---|---|---|
| A · Similarity gauge | LIVE · this attempt | similarity + four sub-scores | `POST /api/spd/score` (D2) |
| B · Acoustic segment profile | LIVE · this attempt | per-entry bar from `segments[]`, labelled *acoustic segments (voiced/unvoiced)* | derived in `demo/server.py:270` |
| C · Score vs perturbation severity | IMPORTED · Dhvani-Yantra, synthetic TTS audio | 19 measured P1 perturbation points + fitted curve labelled **`fitted: 100·exp(−α·ε), α = 3.056, Dhvani-Yantra scorer`** | `GET /api/spd/diagnostic/{word}` → P1 `results.json` |
| D · Reference-baseline panels | IMPORTED · Dhvani-Yantra, synthetic TTS audio | F1/F2 baseline, reference-vs-itself DTW path, segment profile | P1 `results.json` entry 0 + derived student markers |
| E · DTW distance per verse | LIVE · this attempt | mean DTW distance to each of 10 templates; **lower is closer** | `POST /api/gvr/recognize` → `dtw_distances` (`demo/server.py:366`) |
| F · Confusion matrix | IMPORTED · Dhvani-Yantra P2 | 10×10 counts, n=60 | `GET /api/gvr/diagnostic` → `P2/p2_summary.json` |
| G · Accuracy comparison | IMPORTED · Dhvani-Yantra P2 | HMM 36.7 % vs DTW 100.0 % | same P2 summary |
| Video P3 figures | imported label + CC-BY credit | 5 pre-computed figures | Dhvani-Yantra P3 over *Tears of Steel*, *Sintel*, *Elephants Dream* (YOLOv8 + ByteTrack there) |

“Relative score” on `/gvr.html` is the API's `confidence` value (a
softmax over scaled distances). It is **not a probability**.

The verse texts are Dhvani-Yantra's `VERSE_TEXT` constant from
`src/speech_b/p2_build_data.py`; differences are recorded in
`DEMO_DATA.md` (9.22 upstream typo kept out of the demo, 18.66 corrected
here).

---

## 5. Why the verse route is DTW, not HMM

The SRS (FR-20/21) specifies one left-to-right Gaussian HMM per verse.
This project has no trained GVR model on real, permissioned data yet
(FR-22 registry has zero entries). The demo therefore overrides
`/api/gvr/recognize` in `demo/server.py` (`_demo_gvr_recognize`, line
299) with DTW exemplar matching against Dhvani-Yantra's synthetic
clips, purely so the screen can be exercised. That route is a demo
shim, not the FR-21 implementation, and no accuracy is claimed from it.

---

## 6. Do not claim

- No accuracy, error-rate or “validated” claim for this project.
- No “correct pronunciation”, “pronunciation quality” or grading claim:
  these are relative acoustic distances.
- No claim that the HMM/DTW numbers (36.7 % / 100.0 %) are ours.
- No speaker identity, confidence-as-probability, or per-segment
  phoneme claim.
- No claim that segments, formants, `d_mfcc` or `duration_ratio` are
  measured from the take.
- No claim that the P3 video figures were produced by this demo.
- The exact sentence to use: “These are demo outputs, not results.”

---

## 7. Likely questions

**Why does a correct word score about 40 %?**
Because the formula is `100·exp(−D/D₀)` and D is the mean MFCC-DTW
distance between two *different* synthetic voices (a `hi-IN` reference
and an `en-IN` reading of the romanised spelling). With D₀ ≈ 2.9 for
`kRSNa`, a cross-voice distance of ≈ 2.6 gives ≈ 40 %. The speaker and
channel difference dominates; it is not a 40 % “wrongness” and not an
error rate. The same word in the reference voice scores near 100 %.

**Why HMM 36.7 % and DTW 100 %?**
Those are Dhvani-Yantra's P2 numbers: HMMs trained on two voices and
tested on two held-out voices over 60 synthetic clips (36.7 %), and a
DTW nearest-exemplar baseline that compares a test clip with the
matching synthetic template (100 %). Synthetic TTS makes the DTW
comparison close to trivially separable. They are imported context and
say nothing about this project's models or real recitation.

**Why does the demo use DTW while the SRS says HMM?**
Because no trained, FR-23-compliant HMM exists here yet; see §5. The
demo shim exists to show the interface, and is labelled as such.

**Why is the audio synthetic?**
It is Edge-TTS output from Dhvani-Yantra (`data/SOURCES.md` flags every
clip `[SYNTHETIC]`). No real recitations with permission were available,
and synthetic audio avoids speaker-consent and licensing problems. The
cost is that voice variety is unrealistically narrow, which flatters
template matching.

**Is the video tracker the same as Dhvani-Yantra's?**
No. Dhvani-Yantra used YOLOv8n + ByteTrack. This demo uses OpenCV's HOG
person detector plus centroid association — no YOLO, no torch, no model
download. Boxes are labelled `person`, without identity or confidence.

---

## 8. Files and data boundaries

- Demo code: `demo/`; add-on video code: `demo/video/`; pages: `web/`.
- Outputs: `demo/tmp/` and `demo/tmp/video/` only (gitignored).
- `demo/data/` and `demo/data_own/` are gitignored and never committed.
- Nothing is written to `data/`, `corpus/`, or `samskrita_dhvani/`.
- `Dhvani-Yantra-main/` is a read-only neighbour; nothing in it was
  modified except removing a symlink this demo had created. The server
  does not read it at runtime.
