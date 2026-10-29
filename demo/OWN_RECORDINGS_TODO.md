# demo/OWN_RECORDINGS_TODO.md — resume the owner's own recordings

**Status: postponed.** The demo currently runs on the copied TTS corpus in
`demo/data/`. No own takes exist; `demo/data_own/` is empty and gitignored.
This file is the checklist for picking the work back up. Nothing here has
been executed.

## 1. Record, one word per run

Run each command from the project root, at the microphone, and check the
measurements the recorder prints before accepting a take:

```
.venv/bin/python -m demo.record_own --word kRSNa
.venv/bin/python -m demo.record_own --word yoga
.venv/bin/python -m demo.record_own --word zAnti
```

Each run walks through one reference take and the four correct takes, with
a countdown before each. A clipped, silent, too-quiet or too-short take is
rejected and re-recorded; nothing is saved until a take passes the gates
and you accept it. The recorder refuses to overwrite an existing word's
takes without `--force`, and refuses any root that points at the TTS
corpus, `data/` or `corpus/`.

Takes land in:

```
demo/data_own/reference_words/<word_id>.wav
demo/data_own/recitations/<word_id>__own_t0.wav … t3
demo/data_own/variants/<word_id>__var-<label>.wav
```

`demo/data_own/recordings.json` records what each accepted take measured,
with its sha256, timestamp, device and the Capture level in force.

## 2. Optional demonstration variants

Offered at the end of each word's run. They are demonstration material and
are **never** read by the calibration builder.

| word | say | tag | note |
|---|---|---|---|
| kRSNa | `krisna` | `var-sub` | the vowel ṛ becomes ri |
| kRSNa | `kishna` | `var-del` | the r is dropped |
| yoga | `yog` | `var-del` | the final a is dropped |
| yoga | `yogo` | `var-sub` | the final a becomes o |
| zAnti | `santi` | `var-sub` | ś becomes a dental s |
| zAnti | `shaati` | `var-del` | the n is dropped |

## 3. Calibrate from the correct takes only

```
DEMO_DATA_ROOT=demo/data_own .venv/bin/python -m demo.build_demo_calibration
```

Writes `demo/data_own/calibration.json` with the same `CalibrationBuilder`
the project's `calibrate` CLI uses. `demo/data/` is untouched.

## 4. Start the demo

```
DEMO_DATA_ROOT=demo/data_own .venv/bin/python -m demo.server   # own recordings
.venv/bin/python -m demo.server                                # TTS corpus
```

The startup banner prints which data root is active.

## 5. Log it in demo/DEMO_DATA.md

For every accepted file, add: its `demo/data_own/...` path, sha256, UTC
date, device (**Realtek ALC245 internal mic, card 1, HD-Audio Generic**),
the Capture level used, and this sentence verbatim:

> speaker: demo owner, recitation tradition not stated, not ear-verified,
> demo-only

For variants, add the error tag from the table above. Everything needed is
in `demo/data_own/recordings.json`. Leave the existing TTS section as it is
and keep the two corpora clearly separated.

## Still not done afterwards

No ear-check, no reported result, and nothing from these takes may enter
`data/`, `corpus/`, the project calibration, training or evaluation.
