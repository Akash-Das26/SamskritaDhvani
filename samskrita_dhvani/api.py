"""FastAPI backend for the SamskritaDhvani demo UI (Frontend.md §4).

Phase 3 sign-off (2026-09-23) fixed the contract:

- ``GET  /api/words``        — SPD word list (FR-12), Devanagari + IAST
- ``POST /api/spd/score``    — score an attempt against a reference word (FR-11)
- ``POST /api/gvr/recognize``— recognize a verse recitation (FR-21)
- ``GET  /api/status``       — corpus/model transparency page (Frontend.md §3.4)

Ground Rule 1 in the UI: every unavailability is an explicit error
state with a structured body — never a placeholder score.

SPD scoring (design D2, Phase 4 unit 3) is implemented
(``samskrita_dhvani.spd_scorer``) but stays honestly unavailable until
its two data prerequisites exist: an ear-verified reference clip per
word (503 ``reference_unavailable``) and a measured per-word D₀ from
known-correct recitations (503 ``calibration_unavailable``). The D2
formula forbids guessing the scale, so no score is fabricated in the
meantime. The GVR recognizer (design D3, Phase 4 unit 4) is likewise
implemented (``samskrita_dhvani.gvr_classifier``) but returns 503
``model_unavailable`` until a trained model artifact exists — and a
model can only be trained once the FR-22 registry has real data.

Run::

    .venv/bin/uvicorn samskrita_dhvani.api:app --port 8000

If ``web/`` exists it is served at ``/`` (Stitch exports + the wired
UI), so one process serves both the API and the demo.
"""

from __future__ import annotations

import csv
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from samskrita_dhvani.evaluate import (
    EVAL_REPORT_KIND,
    EVAL_REPORT_SCHEMA_VERSION,
)
from samskrita_dhvani.frontend import load_audio_16k, vad_speech_fraction
from samskrita_dhvani.gvr_classifier import GvrRecognizer
from samskrita_dhvani.registry import (
    SpdWordlist,
    VerseEntry,
    GvrRegistry,
    build_seed_wordlist,
    iast_to_devanagari,
)
from samskrita_dhvani.spd_scorer import load_calibration, score_attempt

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORDLIST_PROVENANCE = {
    "source_id": "SPD-SEED",
    "acquired_on": "2026-09-23",
}
# Registry of record for FR-22 (populated by D4 self-recordings or a
# future permissioned source). Absent file = honest empty registry.
GVR_REGISTRY_PATH = PROJECT_ROOT / "data" / "gvr_registry.json"
# Trained D3 recognizer artifact (written by GvrRecognizer.save).
GVR_MODEL_PATH = PROJECT_ROOT / "data" / "gvr" / "model.pkl"
# Published NFR-20/FR-23 evaluation report (written by the unit-8 CLI:
#   python -m samskrita_dhvani.evaluate --registry data/gvr_registry.json
#                                     --json data/gvr/eval_report.json
# ). The status endpoint READS this file — it never re-scores audio or
# runs predict: evaluation is the CLI's job and the report is the single
# source for any displayed number (Ground Rule 1).
GVR_EVAL_REPORT_PATH = PROJECT_ROOT / "data" / "gvr" / "eval_report.json"
# Reference-audio root for SPD (populated only after the Hall/Loyola
# ear check passes and per-word clips are cut).
SPD_REFERENCE_ROOT = PROJECT_ROOT / "data" / "spd" / "reference_words"
# Vedavani sweep manifest (may be absent on fresh clones — the status
# endpoint degrades honestly rather than inventing numbers).
VEDAVANI_MANIFEST = PROJECT_ROOT / "Vedavani-Dataset" / "MANIFEST.csv"

app = FastAPI(
    title="SamskritaDhvani API",
    description="SPD pronunciation scoring + GVR verse recognition (demo backend).",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # local demo tool; Stitch exports may open on any port
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------- schemas

class WordOut(BaseModel):
    word_id: str
    devanagari: str
    iast: str
    difficulty_axis: str
    pair_id: str | None
    reference_audio_url: str | None


class WordListOut(BaseModel):
    words: list[WordOut]
    reference_audio_available: bool


class SweepSummaryOut(BaseModel):
    available: bool
    detail: str
    files_swept: int | None = None
    total_hours: float | None = None
    last_sweep_date: str | None = None


class VerseCoverageOut(BaseModel):
    available: bool
    detail: str
    verse_count: int | None = None
    recitation_count: int | None = None
    chapters: list[str] | None = None


class VerseEvalOut(BaseModel):
    """One verse's NFR-20 row (mirrors the evaluate CLI's report)."""

    verse_id: str
    recall: float | None
    n_correct: int
    support: int
    n_training_clips: int | None
    modelled: bool
    single_row_support: bool


class GvrEvalOut(BaseModel):
    """Held-out evaluation summary (FR-23/NFR-20), or the honest
    reason it does not exist yet. Numbers are only ever mirrored from
    the published ``gvr_eval_report`` — never recomputed here."""

    available: bool
    detail: str
    schema_version: int | None = None
    split_policy: str | None = None
    fr23_statement: str | None = None
    speaker_overlap_note: str | None = None
    curve_note: str | None = None
    n_test: int | None = None
    n_correct: int | None = None
    accuracy_fraction: float | None = None
    accuracy_percent: float | None = None
    per_verse: list[VerseEvalOut] | None = None
    unmodelled_test_verses: list[dict] | None = None


class StatusOut(BaseModel):
    word_count: int
    spd_reference_audio_available: bool
    gvr_scorer_available: bool
    gvr_eval: GvrEvalOut
    verse_coverage: VerseCoverageOut
    last_sweep: SweepSummaryOut
    generated_at: str


# ------------------------------------------------------------- helpers

def _wordlist() -> SpdWordlist:
    return build_seed_wordlist(provenance=WORDLIST_PROVENANCE)


def _reference_url_for(word_id: str) -> str | None:
    """Return a served URL only for files that actually exist on disk.

    No path is ever returned speculatively: until the Hall/Loyola ear
    check passes and clips are cut, this returns None and the UI must
    show an honest 'reference audio pending' state.
    """
    for ext in (".wav", ".mp3", ".flac"):
        p = SPD_REFERENCE_ROOT / f"{word_id}{ext}"
        if p.is_file() and p.stat().st_size > 0:
            return f"/api/reference-audio/{word_id}{ext}"
    return None


def _load_gvr_registry() -> GvrRegistry | None:
    if not GVR_REGISTRY_PATH.is_file():
        return None
    return GvrRegistry.from_json(GVR_REGISTRY_PATH)


def _gvr_eval() -> GvrEvalOut:
    """Mirror the published held-out evaluation (FR-23/NFR-20), or name
    exactly which artifact is missing — same honesty ladder as
    ``_verse_coverage``/``_sweep_summary``. Never computes a number."""
    if not GVR_REGISTRY_PATH.is_file():
        return GvrEvalOut(
            available=False,
            detail=(
                "No GVR registry (data/gvr_registry.json): FR-23 requires "
                "a held-out test split before any accuracy can exist."
            ),
        )
    if GvrRecognizer.load(GVR_MODEL_PATH) is None:
        return GvrEvalOut(
            available=False,
            detail=(
                "Registry exists but no trained model at "
                "data/gvr/model.pkl — train per FR-22 plan §5 step 4, "
                "then evaluate (step 5)."
            ),
        )
    if not GVR_EVAL_REPORT_PATH.is_file():
        return GvrEvalOut(
            available=False,
            detail=(
                "Trained model + registry found, but no published "
                "evaluation report at data/gvr/eval_report.json. Run: "
                "python -m samskrita_dhvani.evaluate --registry "
                "data/gvr_registry.json --json data/gvr/eval_report.json"
            ),
        )
    try:
        data = json.loads(
            GVR_EVAL_REPORT_PATH.read_text(encoding="utf-8")
        )
        if (
            data.get("kind") != EVAL_REPORT_KIND
            or data.get("schema_version") != EVAL_REPORT_SCHEMA_VERSION
        ):
            raise ValueError(
                f"kind/schema mismatch (got kind={data.get('kind')!r}, "
                f"schema_version={data.get('schema_version')!r})"
            )
        overall = data["overall"]
        verses = data["verses"]
        curve = data.get("curve", {})
        return GvrEvalOut(
            available=True,
            detail=(
                "Held-out evaluation of record: "
                f"{GVR_EVAL_REPORT_PATH.name} (written by the evaluate "
                "CLI; re-run it with --json to refresh)."
            ),
            schema_version=data["schema_version"],
            split_policy=data["split_policy"],
            fr23_statement=data["fr23_statement"],
            speaker_overlap_note=data.get("speaker_overlap_note"),
            curve_note=curve.get("note"),
            n_test=overall["n_test"],
            n_correct=overall["n_correct"],
            accuracy_fraction=overall["accuracy_fraction"],
            accuracy_percent=overall["accuracy_percent"],
            per_verse=[
                VerseEvalOut(
                    verse_id=vid,
                    recall=v["recall"],
                    n_correct=v["n_correct"],
                    support=v["support"],
                    n_training_clips=v["n_training_clips"],
                    modelled=v["modelled"],
                    single_row_support=v["single_row_support"],
                )
                for vid, v in verses.items()
            ],
            unmodelled_test_verses=data.get(
                "unmodelled_test_verses", []
            ),
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        return GvrEvalOut(
            available=False,
            detail=(
                f"Evaluation report at {GVR_EVAL_REPORT_PATH} is "
                f"unreadable or not a schema-{EVAL_REPORT_SCHEMA_VERSION} "
                f"{EVAL_REPORT_KIND} ({exc}) — re-run the evaluate CLI "
                "to regenerate it. No partial numbers are shown."
            ),
        )


def _sweep_summary() -> SweepSummaryOut:
    """Real numbers from the Vedavani sweep manifest, or an honest
    'not available' if the corpus is not on this machine."""
    if not VEDAVANI_MANIFEST.is_file():
        return SweepSummaryOut(
            available=False,
            detail=(
                "Vedavani-Dataset/MANIFEST.csv not found on this machine; "
                "see PROVENANCE.md GVR-03 for the sweep record."
            ),
        )
    rows = list(csv.DictReader(VEDAVANI_MANIFEST.open(encoding="utf-8")))
    total_s = sum(float(r["dur_s"]) for r in rows)
    mtime = datetime.fromtimestamp(
        VEDAVANI_MANIFEST.stat().st_mtime, tz=timezone.utc
    )
    return SweepSummaryOut(
        available=True,
        detail="Vedavani §4 sweep manifest (front-end validation pool; not Gita data).",
        files_swept=len(rows),
        total_hours=round(total_s / 3600.0, 2),
        last_sweep_date=mtime.date().isoformat(),
    )


def _verse_coverage() -> VerseCoverageOut:
    reg = _load_gvr_registry()
    if reg is None or len(reg) == 0:
        return VerseCoverageOut(
            available=False,
            detail=(
                "No GVR registry entries yet: Gita sources are externally "
                "blocked (Review.md Open Item 5) and the D4 self-recording "
                "program has not produced audio. The GVR model cannot be "
                "trained without it."
            ),
        )
    verses = {e.verse_id for e in reg.entries}
    chapters = sorted({v.split(".")[0] for v in verses if "." in v})
    return VerseCoverageOut(
        available=True,
        detail=f"Registry of record: {GVR_REGISTRY_PATH.name}",
        verse_count=len(verses),
        recitation_count=len(reg),
        chapters=chapters,
    )


def _save_upload_to_temp(data: bytes, suffix: str = ".wav") -> Path:
    """Persist upload bytes to a temp file the DSP layer can decode."""
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.write(data)
    tmp.close()
    return Path(tmp.name)


def _require_decodable_audio(
    data: bytes, min_duration_s: float = 0.2
) -> tuple[Path, "np.ndarray", float]:
    """Decode the upload with the real D1 loader; 422 if not audio.

    Returns ``(temp_path, waveform, duration_s)`` so callers can run
    DSP checks (e.g. the VAD speech fraction) without re-decoding.
    """
    if len(data) < 512:
        raise HTTPException(
            status_code=422,
            detail={"error": "invalid_audio", "detail": "Upload too small to be audio."},
        )
    suffix = ".wav"
    path = _save_upload_to_temp(data, suffix)
    try:
        y = load_audio_16k(str(path))  # always mono 16 kHz on success
        duration = len(y) / 16000.0
    except Exception as exc:  # noqa: BLE001 — any decode failure is 422
        path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=422,
            detail={"error": "invalid_audio", "detail": f"Could not decode upload as audio: {exc}"},
        ) from exc
    if duration < min_duration_s:
        path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=422,
            detail={
                "error": "invalid_audio",
                "detail": f"Audio too short ({duration:.2f}s; minimum {min_duration_s:.2f}s).",
            },
        )
    return path, y, duration


# ------------------------------------------------------------- endpoints

@app.get("/api/words", response_model=WordListOut)
def list_words() -> WordListOut:
    """FR-12 word list. reference_audio_url is None until real
    reference clips exist (Hall/Loyola ear check → cut clips)."""
    wl = _wordlist()
    any_ref = False
    words: list[WordOut] = []
    for w in wl.words:
        url = _reference_url_for(w.word_id)
        any_ref = any_ref or url is not None
        words.append(
            WordOut(
                word_id=w.word_id,
                devanagari=w.devanagari,
                iast=w.iast,
                difficulty_axis=w.difficulty_axis,
                pair_id=w.pair_id,
                reference_audio_url=url,
            )
        )
    return WordListOut(words=words, reference_audio_available=any_ref)


@app.post("/api/spd/score")
async def spd_score(
    audio: UploadFile = File(...),
    word_id: str = Form(...),
) -> dict:
    """Score a pronunciation attempt (FR-10/FR-11) with design D2.

    Full honesty chain, in order: 404 unknown word → 422 undecodable
    audio → 422 near-silence (DataIntegrity §1.1) → 503 missing
    ear-verified reference clip → 503 missing measured D₀ → 200 with
    the FR-11 shape. No path can return a fabricated number.
    """
    wl = _wordlist()
    known = {w.word_id: w for w in wl.words}
    if word_id not in known:
        raise HTTPException(
            status_code=404,
            detail={"error": "unknown_word", "detail": f"word_id '{word_id}' is not in the FR-12 word list."},
        )
    data = await audio.read()
    path, y, duration = _require_decodable_audio(data)
    try:
        # DataIntegrity §1.1: clips that are mostly silence are invalid
        # input, not scorable attempts.
        speech_frac = vad_speech_fraction(y)
        if speech_frac <= 0.10:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "near_silence",
                    "detail": (
                        f"Only {speech_frac:.0%} of frames contain speech "
                        "(DataIntegrity §1.1 excludes clips at or below 10%); "
                        "record closer to the microphone and try again."
                    ),
                },
            )

        # D2 prerequisite 1: an ear-verified reference clip on disk.
        ref_path = None
        for ext in (".wav", ".flac", ".mp3"):
            p = SPD_REFERENCE_ROOT / f"{word_id}{ext}"
            if p.is_file() and p.stat().st_size > 0:
                ref_path = p
                break
        if ref_path is None:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "reference_unavailable",
                    "detail": (
                        f"No verified reference clip for '{word_id}' "
                        f"(expected data/spd/reference_words/{word_id}.wav). "
                        "The Hall/Loyola ear check (PROVENANCE SPD-01/02) is "
                        "still pending, so no reference has been cut; D2 "
                        "cannot score without one."
                    ),
                },
            )

        # D2 prerequisite 2: a measured per-word D₀ (never a guess).
        calibration = load_calibration(word_id)
        if calibration is None:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "calibration_unavailable",
                    "detail": (
                        f"Word '{word_id}' has no measured D0 in "
                        "data/spd/calibration.json. The approved D2 mapping "
                        "sim = 100·exp(−D/D0) requires D0 from known-correct "
                        "recitations (CalibrationBuilder); no scale, no score."
                    ),
                },
            )

        ref_audio = load_audio_16k(str(ref_path))
        w = known[word_id]
        try:
            score = score_attempt(
                y,
                ref_audio,
                calibration,
                {"word_id": word_id, "devanagari": w.devanagari, "iast": w.iast},
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "axis_unmeasurable",
                    "detail": f"The attempt could not be scored on every axis: {exc}",
                },
            )

        return {
            "similarity_pct": round(score.similarity_pct, 1),
            "vowel_score": round(score.vowel_score, 1),
            "consonant_score": round(score.consonant_score, 1),
            "duration_score": round(score.duration_score, 1),
            "mfcc_dtw_score": round(score.mfcc_dtw_score, 1),
            "reference_word": score.reference_word,
        }
    finally:
        path.unlink(missing_ok=True)


@app.post("/api/gvr/recognize")
async def gvr_recognize(audio: UploadFile = File(...)) -> dict:
    """Recognize a verse (FR-21) with the D3 recognizer.

    Honesty chain: 422 undecodable audio → 422 near-silence
    (DataIntegrity §1.1) → 503 model_unavailable when no trained
    recognizer artifact exists → 200 with the FR-21 shape. The
    recognizer only ever answers over the verses it was trained on;
    there is no out-of-set inference to fake.
    """
    data = await audio.read()
    path, y, duration = _require_decodable_audio(data)
    try:
        speech_frac = vad_speech_fraction(y)
        if speech_frac <= 0.10:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "near_silence",
                    "detail": (
                        f"Only {speech_frac:.0%} of frames contain speech "
                        "(DataIntegrity §1.1 excludes clips at or below 10%); "
                        "recite closer to the microphone and try again."
                    ),
                },
            )

        recognizer = GvrRecognizer.load(GVR_MODEL_PATH)
        if recognizer is None:
            reg = _load_gvr_registry()
            reg_state = (
                "data/gvr_registry.json is missing"
                if reg is None
                else f"the registry has {len(reg)} entries"
            )
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "model_unavailable",
                    "detail": (
                        "No trained GVR recognizer at data/gvr/model.pkl "
                        f"({reg_state}). The D3 recognizer is implemented, "
                        "but it can only be trained once the FR-22 registry "
                        "holds real recitations. Audio validated OK "
                        f"({duration:.2f}s)."
                    ),
                },
            )

        pred = recognizer.predict(y)
        text = recognizer.text_for(pred.verse_id)
        return {
            "top_match": {
                "verse_id": pred.verse_id,
                "devanagari": text.get("devanagari"),
                "gloss": text.get("gloss"),
                "confidence": pred.confidence,
            },
            "candidates": [
                {"verse_id": c["verse_id"], "confidence": c["confidence"]}
                for c in pred.candidates
            ],
        }
    finally:
        path.unlink(missing_ok=True)


@app.get("/api/status", response_model=StatusOut)
def status() -> StatusOut:
    """Transparency page data (Frontend.md §3.4). Every number is read
    from real artifacts at request time — nothing hardcoded."""
    return StatusOut(
        word_count=len(_wordlist()),
        spd_reference_audio_available=_reference_url_for(
            _wordlist().words[0].word_id
        ) is not None,
        gvr_scorer_available=GvrRecognizer.load(GVR_MODEL_PATH) is not None,
        gvr_eval=_gvr_eval(),
        verse_coverage=_verse_coverage(),
        last_sweep=_sweep_summary(),
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


# ------------------------------------------------------- static UI mount

_WEB_DIR = PROJECT_ROOT / "web"
if _WEB_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(_WEB_DIR), html=True), name="web")
