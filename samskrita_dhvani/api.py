"""FastAPI backend for the SamskritaDhvani demo UI (Frontend.md §4).

Phase 3 sign-off (2026-09-23) fixed the contract:

- ``GET  /api/words``        — SPD word list (FR-12), Devanagari + IAST
- ``POST /api/spd/score``    — score an attempt against a reference word (FR-11)
- ``POST /api/gvr/recognize``— recognize a verse recitation (FR-21)
- ``GET  /api/status``       — corpus/model transparency page (Frontend.md §3.4)

Ground Rule 1 in the UI: every unavailability is an explicit error
state (HTTP 503 with a structured body) — never a placeholder score.
The SPD scorer (design D2) and GVR HMM (design D3) are not yet
implemented; the two POST endpoints validate what can be validated
today (word ID, decodable audio) and then return 503
``model_unavailable``. The scoring/recognition call sites are marked
with ``# SCORER SEAM`` so Phase 4 units 3/4 drop in at exactly one
place each.

Run::

    .venv/bin/uvicorn samskrita_dhvani.api:app --port 8000

If ``web/`` exists it is served at ``/`` (Stitch exports + the wired
UI), so one process serves both the API and the demo.
"""

from __future__ import annotations

import csv
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from samskrita_dhvani.frontend import load_audio_16k
from samskrita_dhvani.registry import (
    SpdWordlist,
    VerseEntry,
    GvrRegistry,
    build_seed_wordlist,
    iast_to_devanagari,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORDLIST_PROVENANCE = {
    "source_id": "SPD-SEED",
    "acquired_on": "2026-09-23",
}
# Registry of record for FR-22 (populated by D4 self-recordings or a
# future permissioned source). Absent file = honest empty registry.
GVR_REGISTRY_PATH = PROJECT_ROOT / "data" / "gvr_registry.json"
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


class StatusOut(BaseModel):
    word_count: int
    spd_reference_audio_available: bool
    gvr_scorer_available: bool
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


def _require_decodable_audio(data: bytes, min_duration_s: float = 0.2) -> tuple[Path, float]:
    """Decode the upload with the real D1 loader; 422 if not audio."""
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
    return path, duration


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
    """Score a pronunciation attempt (FR-11). Validates word + audio
    now; returns 503 model_unavailable until the D2 scorer lands."""
    wl = _wordlist()
    known = {w.word_id for w in wl.words}
    if word_id not in known:
        raise HTTPException(
            status_code=404,
            detail={"error": "unknown_word", "detail": f"word_id '{word_id}' is not in the FR-12 word list."},
        )
    data = await audio.read()
    path, duration = _require_decodable_audio(data)

    # SCORER SEAM: Phase 4 unit 3 (design D2 DTW scorer) replaces the
    # block below with a real call and the FR-11 response shape:
    #   {similarity_pct, vowel_score, consonant_score, duration_score,
    #    mfcc_dtw_score, reference_word: {...}}
    path.unlink(missing_ok=True)
    raise HTTPException(
        status_code=503,
        detail={
            "error": "model_unavailable",
            "detail": (
                "SPD scorer (design D2, Phase 4 unit 3) is not implemented yet; "
                "no score can be reported. Audio validated OK "
                f"({duration:.2f}s, word '{word_id}')."
            ),
        },
    )


@app.post("/api/gvr/recognize")
async def gvr_recognize(audio: UploadFile = File(...)) -> dict:
    """Recognize a verse (FR-21). Returns 503 model_unavailable until
    the D3 HMM exists AND the FR-22 registry has training data."""
    data = await audio.read()
    path, duration = _require_decodable_audio(data)
    reg = _load_gvr_registry()
    registry_ready = reg is not None and len(reg) >= 20

    # SCORER SEAM: Phase 4 unit 4 (design D3 HMM) replaces the block
    # below with a real call and the FR-21 response shape:
    #   {top_match: {verse_id, devanagari, gloss, confidence},
    #    candidates: [{verse_id, confidence}, ...]}
    path.unlink(missing_ok=True)
    if not registry_ready:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "model_unavailable",
                "detail": (
                    "GVR registry has no training data "
                    f"({'data/gvr_registry.json missing' if reg is None else f'{len(reg)} entries; need >= 20'}); "
                    "the HMM (design D3) cannot be trained or queried."
                ),
            },
        )
    raise HTTPException(
        status_code=503,
        detail={
            "error": "model_unavailable",
            "detail": (
                "GVR HMM (design D3, Phase 4 unit 4) is not implemented yet; "
                f"no recognition can be reported. Audio validated OK ({duration:.2f}s)."
            ),
        },
    )


@app.get("/api/status", response_model=StatusOut)
def status() -> StatusOut:
    """Transparency page data (Frontend.md §3.4). Every number is read
    from real artifacts at request time — nothing hardcoded."""
    return StatusOut(
        word_count=len(_wordlist()),
        spd_reference_audio_available=_reference_url_for(
            _wordlist().words[0].word_id
        ) is not None,
        gvr_scorer_available=False,  # flips when unit 4 lands; see SCORER SEAM
        verse_coverage=_verse_coverage(),
        last_sweep=_sweep_summary(),
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


# ------------------------------------------------------- static UI mount

_WEB_DIR = PROJECT_ROOT / "web"
if _WEB_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(_WEB_DIR), html=True), name="web")
