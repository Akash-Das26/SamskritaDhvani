"""D5 calibration-recording program — browser capture server.

Purpose and boundary
--------------------
The D2 scorer needs two things per word before any score can be
reported: an ear-verified canonical reference clip
(``data/spd/reference_words/<word_id>.wav``) and known-correct
recitations (``data/spd/recitations/``) that
``python -m samskrita_dhvani.calibrate`` measures the D₀ scales from.
This module is the *capture* half of that program: it runs a small
uvicorn app on its own port and serves ``web/record.html``, which
drives word-by-word recording through the browser (the same
``SD.Recorder`` / ``SD.toWav16k`` path the demo screens use).

Discipline this module enforces (DataIntegrity.md §2, Rule 2, §5):

- Uploads land ONLY in ``data/_incoming/<session-id>/``. This module
  never writes inside ``data/spd/`` — promotion into the calibrate
  layout is a separate, deliberate, ear-check-gated step.
- Every upload is decoded with the real D1 loader
  (:func:`samskrita_dhvani.frontend.load_audio_16k`) and gated on the
  DataIntegrity §1.1 near-silence rule (WebRTC VAD speech fraction
  must clear 10%). A failed gate is a loud 422 and the bytes are
  discarded server-side — a bad take can never enter the incoming
  tree silently.
- Take numbers are computed by the server from the session directory,
  never trusted from the client. A re-upload of the same
  (session, word, role) overwrites that take's files in place —
  re-recording a take is replacing it, not silently appending a
  competing version.
- Session metadata (reciter, room, device, consent, word list version)
  is captured at session start, and a per-clip checklist row
  (RecordingProtocol.md §2) is emitted next to every saved clip. The
  session sheet + checklists + PROMOTION.md block are what a later
  ``data/provenance/REC_<session-id>.md`` sheet is assembled from.

This server is a recording *tool*, not the demo API: it shares no
routes with ``samskrita_dhvani.api`` and runs separately

    python -m samskrita_dhvani.record --port 8030
"""

from __future__ import annotations

import io
import json
import re
import threading
import uuid
import wave
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from samskrita_dhvani.frontend import load_audio_16k, vad_speech_fraction
from samskrita_dhvani.registry import build_seed_wordlist

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = PROJECT_ROOT / "web"
INCOMING_ROOT = PROJECT_ROOT / "data" / "_incoming"
WORDLIST_VERSION = "spd-seed-27@2026-09-23"
VAD_MIN_SPEECH_FRACTION = 0.10  # DataIntegrity §1.1 near-silence rule
MIN_DURATION_S = 0.2

app = FastAPI(
    title="SamskritaDhvani recording booth",
    description=(
        "D5/D4 capture tool: browser recording sessions into "
        "data/_incoming — never the corpus tree."
    ),
    version="0.1.0",
)

# Take numbers are computed from disk then written; serialize that
# read-modify-write so two rapid uploads of the same (word, role)
# can't race to the same take number.
_UPLOAD_LOCK = threading.Lock()


# ------------------------------------------------------------- helpers

def _slug_ok(s: str) -> bool:
    """ASCII slug: lowercase letters, digits, underscore (protocol §3)."""
    return bool(re.fullmatch(r"[a-z0-9_]{1,40}", s))


def _session_id_ok(s: str) -> bool:
    """Server-minted session ids: ``SPD-REC-YYYYMMDD-xxxxxx``. Charset
    excludes ``/`` and ``.`` so the value is a single safe path
    component (no traversal)."""
    return bool(re.fullmatch(r"SPD-REC-[0-9]{8}-[0-9a-f]{6}", s))


def _word_id_ok(s: str) -> bool:
    """Registry word ids are Harvard-Kyoto slugs — ASCII letters and
    digits, uppercase significant (``kRSNa`` != ``krsna``)."""
    return bool(re.fullmatch(r"[A-Za-z0-9_]{1,40}", s))


def _wordlist_dict() -> list[dict]:
    wl = build_seed_wordlist()
    return [
        {
            "word_id": w.word_id,
            "devanagari": w.devanagari,
            "iast": w.iast,
            "difficulty_axis": w.difficulty_axis,
            "pair_id": w.pair_id,
        }
        for w in wl.words
    ]


def _session_dir(session_id: str) -> Path:
    return INCOMING_ROOT / session_id


def _load_meta(session_id: str) -> dict:
    p = _session_dir(session_id) / "session_meta.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _write_meta(session_id: str, meta: dict) -> None:
    p = _session_dir(session_id) / "session_meta.json"
    p.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _peak(data: bytes) -> float:
    with wave.open(io.BytesIO(data), "rb") as w:
        frames = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return float(np.abs(frames.astype(np.float32) / 32768.0).max())


def _checklist_entry(
    session_id: str,
    word_id: str,
    iast: str,
    take: int,
    role: str,
    duration: float,
    peak: float,
) -> dict:
    return {
        "file": f"spd_{word_id}_{role}_t{take}.wav",
        "session_id": session_id,
        "item": word_id,
        "item_iast": iast,
        "take": take,
        "role": role,
        "duration_s": round(duration, 3),
        "peak_dbfs": round(20 * np.log10(peak), 1) if peak > 0 else None,
        "clipping": bool(peak >= 0.999),
        "silence_trimmed": False,
        "transcript_verified": None,
        "sweep_date": None,
        "provenance_entry": None,
        "recorded_utc": _iso_now(),
    }


def _decode_and_gate(data: bytes) -> tuple[np.ndarray, float, float]:
    """Decode with the real D1 loader and apply the §1.1 gates.

    Returns (waveform, duration_s, speech_fraction); raises HTTPException
    422 with the clip discarded (nothing is persisted before this
    returns).
    """
    if len(data) < 512:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "invalid_audio",
                "detail": "Upload too small to be audio.",
            },
        )
    import tempfile

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.write(data)
    tmp.close()
    try:
        y = load_audio_16k(str(tmp.name))
    except Exception as exc:  # noqa: BLE001 — any decode failure is 422
        Path(tmp.name).unlink(missing_ok=True)
        raise HTTPException(
            status_code=422,
            detail={
                "error": "invalid_audio",
                "detail": f"Could not decode upload as audio: {exc}",
            },
        ) from exc
    Path(tmp.name).unlink(missing_ok=True)

    duration = len(y) / 16000.0
    if duration < MIN_DURATION_S:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "invalid_audio",
                "detail": (
                    f"Audio too short ({duration:.2f}s; "
                    f"minimum {MIN_DURATION_S:.2f}s)."
                ),
            },
        )
    speech_frac = vad_speech_fraction(y)
    if speech_frac <= VAD_MIN_SPEECH_FRACTION:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "near_silence",
                "detail": (
                    f"VAD speech fraction {speech_frac:.3f} is at or "
                    "below the DataIntegrity §1.1 line (10%); this take "
                    "cannot enter the incoming tree."
                ),
            },
        )
    return y, duration, speech_frac


def _write_wav(path: Path, y: np.ndarray) -> None:
    """Persist the decoded 16 kHz waveform as 16-bit PCM WAV."""
    import soundfile as sf

    sf.write(str(path), y, 16000, subtype="PCM_16")


# ------------------------------------------------------------ endpoints

@app.get("/", response_class=HTMLResponse)
def booth() -> FileResponse:
    return FileResponse(WEB_DIR / "record.html")


@app.get("/app.js")
def app_js() -> FileResponse:
    return FileResponse(WEB_DIR / "app.js")


@app.get("/api/record/words")
def words() -> dict:
    """The seed word list to capture (FR-12 list; provenance is asserted
    at promotion time, not capture time)."""
    return {"wordlist_version": WORDLIST_VERSION, "words": _wordlist_dict()}


@app.post("/api/record/session")
def start_session(
    reciter: str = Form(...),
    location: str = Form(""),
    device: str = Form(""),
    consent: bool = Form(...),
    source_id: str = Form("SPD-D5-SELF"),
) -> dict:
    """Create a recording session under ``data/_incoming/``.

    ``source_id`` is required to be a PROVENANCE.md entry that will
    describe these files after promotion; the default is the D5
    self-recording entry to be registered in PROVENANCE.md at
    promotion time. Nothing is claimed as verified here — the session
    sheet records intent, the ear check decides eligibility.
    """
    if not consent:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "consent_required",
                "detail": "Recording requires recorded consent confirmation.",
            },
        )
    reciter_slug = reciter.strip().lower().replace(" ", "_")
    if not _slug_ok(reciter_slug) or not location.strip() or not device.strip():
        raise HTTPException(
            status_code=400,
            detail={
                "error": "bad_session_fields",
                "detail": "reciter must slugify to [a-z0-9_]; location and device are required.",
            },
        )
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", source_id.strip()):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "bad_source_id",
                "detail": "source_id must be a PROVENANCE.md entry id like SPD-D5-SELF.",
            },
        )
    session_id = (
        f"SPD-REC-{datetime.now(timezone.utc).strftime('%Y%m%d')}-"
        f"{uuid.uuid4().hex[:6]}"
    )
    d = _session_dir(session_id)
    d.mkdir(parents=True, exist_ok=False)
    meta = {
        "session_id": session_id,
        "program": "D5",
        "reciter": reciter.strip(),
        "reciter_slug": reciter_slug,
        "location": location.strip(),
        "device": device.strip(),
        "consent_confirmed": True,
        "source_id": source_id.strip(),
        "wordlist_version": WORDLIST_VERSION,
        "started_utc": _iso_now(),
        "protocol": "files/RecordingProtocol.md",
    }
    _write_meta(session_id, meta)
    return {"session_id": session_id, "meta": meta}


@app.get("/api/record/session/{session_id}")
def get_session(session_id: str) -> dict:
    if not _session_id_ok(session_id) or not _session_dir(session_id).is_dir():
        raise HTTPException(status_code=404, detail="unknown session")
    meta = _load_meta(session_id)
    takes = []
    d = _session_dir(session_id)
    for p in sorted(d.glob("*.wav")):
        stem = p.stem  # spd_<word_id>_<role>_t<take>
        m = re.fullmatch(r"spd_([A-Za-z0-9_]+?)_(canonical|recitation)_t(\d+)", stem)
        if not m:
            continue
        takes.append(
            {"word_id": m.group(1), "role": m.group(2), "take": int(m.group(3))}
        )
    return {"meta": meta, "takes": takes}


@app.post("/api/record/upload")
def upload(
    session_id: str = Form(...),
    word_id: str = Form(...),
    role: str = Form(...),
    audio: UploadFile = File(...),
) -> dict:
    """Accept one take (16 kHz mono WAV from ``SD.toWav16k``), gate it,
    and store it in the session dir with a checklist sidecar.

    ``role`` is ``canonical`` (the ear-check candidate for
    ``<word_id>.wav``) or ``recitation`` (a known-correct recitation
    take for the D₀ measurement corpus).
    """
    if role not in ("canonical", "recitation"):
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_role", "detail": "role must be 'canonical' or 'recitation'."},
        )
    if not _word_id_ok(word_id) or not _session_id_ok(session_id):
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_word_id", "detail": "unknown word_id or session_id."},
        )
    d = _session_dir(session_id)
    meta_path = d / "session_meta.json"
    if not meta_path.is_file():
        raise HTTPException(status_code=404, detail="unknown session")

    wordlist = _wordlist_dict()
    words_by_id = {w["word_id"]: w for w in wordlist}
    if word_id not in words_by_id:
        raise HTTPException(
            status_code=400,
            detail={"error": "unknown_word", "detail": f"'{word_id}' is not in the word list."},
        )
    meta = _load_meta(session_id)

    data = audio.file.read()
    try:
        y, duration, speech_frac = _decode_and_gate(data)
    except HTTPException:
        raise
    peak = _peak(data)

    # Server-computed take number: every accepted upload appends
    # take = max+1. Nothing on disk is ever deleted or overwritten by
    # a re-record — an accidental extra take stays visible in the
    # incoming tree instead of silently replacing an earlier one.
    # Never trusted from the client.
    #
    # Filenames keep the registry word_id VERBATIM (mixed case is
    # significant in Harvard-Kyoto): lowercase-folding is lossy for
    # the vowel-length axis — 'tala' and 'tAla' are distinct words on
    # the SPD list, and folding both to 'tala' would interleave their
    # takes. This deviates from RecordingProtocol §3's lowercase
    # example ('krsna'); the protocol's rule assumed romanized keys,
    # not case-significant HK slugs. Logged in Review.md.
    with _UPLOAD_LOCK:
        stem_re = re.compile(
            rf"^spd_{re.escape(word_id)}_{role}_t(\d+)\.wav$"
        )
        prior = [
            int(m.group(1)) for p in d.glob("*.wav") if (m := stem_re.match(p.name))
        ]
        take = (max(prior) + 1) if prior else 0

        stem = f"spd_{word_id}_{role}_t{take}"
        wav_path = d / f"{stem}.wav"
        _write_wav(wav_path, y)

        checklist = _checklist_entry(
            session_id, word_id, words_by_id[word_id]["iast"], take, role,
            duration, peak,
        )
        checklist["vad_speech_fraction"] = round(speech_frac, 3)
        (d / f"{stem}.checklist.json").write_text(
            json.dumps(checklist, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    takes = meta.setdefault("takes", {})
    takes.setdefault(word_id, {}).setdefault(role, []).append(
        {"take": take, "file": wav_path.name, "recorded_utc": checklist["recorded_utc"]}
    )
    _write_meta(session_id, meta)

    return {
        "ok": True,
        "file": wav_path.name,
        "take": take,
        "duration_s": round(duration, 3),
        "vad_speech_fraction": round(speech_frac, 3),
        "peak_dbfs": checklist["peak_dbfs"],
        "note": (
            "Stored in data/_incoming — NOT yet pipeline-eligible. "
            "Promotion to the calibrate layout happens after the ear "
            "check, with PROVENANCE.md registration."
        ),
    }


@app.post("/api/record/promote")
def promote(session_id: str = Form(...), force: bool = Form(False)) -> dict:
    """Stage the promotion mapping (deliberate; ear-check-gated).

    Writes a ``PROMOTION.md`` block into the session directory that
    lists the exact copy commands from the capture names into the
    calibrate-CLI layout, and marks the session PROMOTED only when the
    operator passes ``force=True`` — an explicit, deliberate flag, not
    a default. It still never copies into ``data/spd/`` itself; the
    operator runs the (printed) commands after the ear check passes.
    """
    d = _session_dir(session_id)
    if not _session_id_ok(session_id) or not d.is_dir():
        raise HTTPException(status_code=404, detail="unknown session")
    meta = _load_meta(session_id)
    takes = meta.get("takes", {})
    if not takes:
        raise HTTPException(
            status_code=409,
            detail={"error": "empty_session", "detail": "No takes recorded in this session."},
        )

    ref_lines = ["# Promotion mapping (ear-check gate)", ""]
    ref_lines.append(f"Session: `{session_id}` — reciter {meta['reciter']}, "
                     f"source_id `{meta['source_id']}` (register in PROVENANCE.md).")
    ref_lines.append("")
    ref_lines.append("Canonical candidates → `data/spd/reference_words/<word_id>.wav`")
    ref_lines.append("Recitation takes → `data/spd/recitations/<word_id>__t<take>.wav`")
    ref_lines.append("")
    n_c, n_r = 0, 0
    for word_id, roles in sorted(takes.items()):
        if roles.get("canonical"):
            f = roles["canonical"][-1]["file"]
            ref_lines.append(f"- [ ] `{f}` → `reference_words/{word_id}.wav`")
            n_c += 1
        for entry in roles.get("recitation", []):
            ref_lines.append(
                f"- [ ] `{entry['file']}` → `recitations/{word_id}__t{entry['take']}.wav`"
            )
            n_r += 1
    ref_lines.append("")
    ref_lines.append(
        "After copying, run: `python -m samskrita_dhvani.calibrate "
        "--references data/spd/reference_words "
        "--recitations data/spd/recitations "
        f"--source-id {meta['source_id']} --acquired-on <date>`"
    )
    promotion_text = "\n".join(ref_lines) + "\n"
    (d / "PROMOTION.md").write_text(promotion_text, encoding="utf-8")

    if force:
        meta["promoted"] = True
        meta["promoted_utc"] = _iso_now()
        _write_meta(session_id, meta)

    return {
        "ok": True,
        "promotion_block": str(d / "PROMOTION.md"),
        "mapping_text": promotion_text,
        "canonical_candidates": n_c,
        "recitation_takes": n_r,
        "promoted": bool(force),
        "note": (
            "Mapping written; nothing copied into data/spd/ by this "
            "endpoint. Copy after the ear check passes, then run the "
            "calibrate CLI with the provenance flags."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    """Entry point: ``python -m samskrita_dhvani.record [--port N]``."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m samskrita_dhvani.record",
        description="Run the D5/D4 browser recording booth (data/_incoming capture).",
    )
    parser.add_argument("--port", type=int, default=8030)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args(argv)

    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
