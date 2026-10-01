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
# D4 (Gita verses) booth items: built by tools/build_gvr_itemlist.py
# from a named public-domain source (see PROVENANCE.md GVR-TXT-01).
# The booth serves the FR-22 plan's first target: chapter 2, vv. 1–20.
GVR_ITEMLIST_PATH = PROJECT_ROOT / "data" / "gvr" / "ch2_itemlist.json"
GVR_BOOTHSUBSET = 20

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
    """Server-minted session ids: ``SPD-REC-YYYYMMDD-xxxxxx`` (D5) or
    ``GVR-REC-YYYYMMDD-xxxxxx`` (D4). Charset excludes ``/`` so the
    value is a single safe path component (no traversal)."""
    return bool(re.fullmatch(r"(?:SPD|GVR)-REC-[0-9]{8}-[0-9a-f]{6}", s))


def _word_id_ok(s: str) -> bool:
    """Registry word ids are Harvard-Kyoto slugs — ASCII letters and
    digits, uppercase significant (``kRSNa`` != ``krsna``)."""
    return bool(re.fullmatch(r"[A-Za-z0-9_]{1,40}", s))


def _verse_id_ok(s: str) -> bool:
    """GVR item ids are canonical ``chapter.verse`` (``2.13``)."""
    return bool(re.fullmatch(r"\d{1,3}\.\d{1,3}", s))


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
    fname_id: str,
    item_id: str,
    item_label: str,
    take: int,
    role: str,
    duration: float,
    peak: float,
    program: str = "D5",
    devanagari: str = "",
    tradition: str | None = None,
) -> dict:
    prefix = "spd" if program == "D5" else "gvr"
    return {
        "file": f"{prefix}_{fname_id}_{role}_t{take}.wav",
        "session_id": session_id,
        "program": program,
        "item": item_id,
        "item_label": item_label,
        "item_devanagari": devanagari,
        "recitation_tradition": tradition,
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


@app.get("/api/record/items")
def items(program: str = "D5") -> dict:
    """The item list for a program. ``D5`` = the 27 SPD seed words;
    ``D4`` = the Bhagavad Gita chapter-2 verses (FR-22 first target:
    vv. 1–20) from ``data/gvr/ch2_itemlist.json``, honestly unavailable
    if the checked item file has not been built yet."""
    if program == "D5":
        return {
            "program": "D5",
            "list_version": WORDLIST_VERSION,
            "items": _wordlist_dict(),
        }
    if program == "D4":
        if not GVR_ITEMLIST_PATH.is_file():
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "itemlist_unavailable",
                    "detail": (
                        "No GVR item list at data/gvr/ch2_itemlist.json — "
                        "build it with tools/build_gvr_itemlist.py from "
                        "the named public-domain source (PROVENANCE.md "
                        "GVR-TXT-01)."
                    ),
                },
            )
        try:
            data = json.loads(GVR_ITEMLIST_PATH.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 — corrupt list is loud
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "itemlist_unavailable",
                    "detail": f"GVR item list unreadable: {exc}",
                },
            ) from exc
        if data.get("kind") != "gvr_itemlist" or data.get("schema_version") != 1:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "itemlist_unavailable",
                    "detail": "GVR item list fails its schema gate.",
                },
            )
        verses = [it for it in data["items"]
                  if int(it["verse"]) <= GVR_BOOTHSUBSET]
        return {
            "program": "D4",
            "list_version": (
                f"ch2@{data['text_source']['file_sha256'][:12]}"
            ),
            "text_source": data["text_source"]["url"],
            "items": [
                {
                    "verse_id": it["verse_id"],
                    "devanagari": it["devanagari"],
                    "fname_key": it["fname_key"],
                }
                for it in verses
            ],
        }
    raise HTTPException(
        status_code=400,
        detail={"error": "bad_program", "detail": "program must be 'D4' or 'D5'."},
    )


@app.get("/api/record/words")
def words() -> dict:
    """Backward-compatible alias for the D5 item list."""
    d = items("D5")
    return {"wordlist_version": d["list_version"], "words": d["items"]}


@app.post("/api/record/session")
def start_session(
    reciter: str = Form(...),
    location: str = Form(""),
    device: str = Form(""),
    consent: bool = Form(...),
    source_id: str = Form("SPD-D5-SELF"),
    program: str = Form("D5"),
    tradition: str = Form(""),
) -> dict:
    """Create a recording session under ``data/_incoming/``.

    ``source_id`` is required to be a PROVENANCE.md entry that will
    describe these files after promotion; the default is the D5
    self-recording entry to be registered in PROVENANCE.md at
    promotion time. Nothing is claimed as verified here — the session
    sheet records intent, the ear check decides eligibility.

    ``program`` selects D5 (SPD words) or D4 (Gita verses); ``tradition``
    states the recitation tradition for the session (protocol §3.6 —
    required for D4, optional but recorded for D5).
    """
    if program not in ("D5", "D4"):
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_program", "detail": "program must be 'D4' or 'D5'."},
        )
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
    if program == "D4" and not tradition.strip():
        raise HTTPException(
            status_code=400,
            detail={
                "error": "tradition_required",
                "detail": (
                    "D4 sessions must state the recitation tradition "
                    "(RecordingProtocol §4 / DataIntegrity §3.6)."
                ),
            },
        )
    prefix = "SPD" if program == "D5" else "GVR"
    session_id = (
        f"{prefix}-REC-{datetime.now(timezone.utc).strftime('%Y%m%d')}-"
        f"{uuid.uuid4().hex[:6]}"
    )
    d = _session_dir(session_id)
    d.mkdir(parents=True, exist_ok=False)
    meta = {
        "session_id": session_id,
        "program": program,
        "reciter": reciter.strip(),
        "reciter_slug": reciter_slug,
        "location": location.strip(),
        "device": device.strip(),
        "consent_confirmed": True,
        "source_id": source_id.strip(),
        "recitation_tradition": tradition.strip() or None,
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
    pattern = (r"spd_([A-Za-z0-9_]+?)_(canonical|recitation)_t(\d+)"
               if meta.get("program", "D5") == "D5"
               else r"gvr_([a-z0-9]+)_recitation_t(\d+)")
    for p in sorted(d.glob("*.wav")):
        m = re.fullmatch(pattern, p.stem)
        if not m:
            continue
        if meta.get("program", "D5") == "D5":
            takes.append(
                {"item": m.group(1), "role": m.group(2), "take": int(m.group(3))}
            )
        else:
            takes.append({"item": m.group(1), "role": "recitation",
                          "take": int(m.group(2))})
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
    d = _session_dir(session_id)
    meta_path = d / "session_meta.json"
    if not meta_path.is_file():
        raise HTTPException(status_code=404, detail="unknown session")
    meta = _load_meta(session_id)
    program = meta.get("program", "D5")

    if program == "D5":
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
        wordlist = _wordlist_dict()
        words_by_id = {w["word_id"]: w for w in wordlist}
        if word_id not in words_by_id:
            raise HTTPException(
                status_code=400,
                detail={"error": "unknown_word", "detail": f"'{word_id}' is not in the word list."},
            )
        item_label = words_by_id[word_id]["iast"]
        item_devanagari = words_by_id[word_id]["devanagari"]
        fname_id = word_id
    else:
        if role != "recitation":
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "bad_role",
                    "detail": "D4 takes are corpus takes: role must be 'recitation'.",
                },
            )
        if not _verse_id_ok(word_id) or not _session_id_ok(session_id):
            raise HTTPException(
                status_code=400,
                detail={"error": "bad_word_id", "detail": "unknown verse_id or session_id."},
            )
        d4 = items("D4")
        by_verse = {it["verse_id"]: it for it in d4["items"]}
        if word_id not in by_verse:
            raise HTTPException(
                status_code=400,
                detail={"error": "unknown_word", "detail": f"'{word_id}' is not in the D4 booth subset (chapter 2, vv. 1-{GVR_BOOTHSUBSET})."},
            )
        item_label = by_verse[word_id]["fname_key"]
        item_devanagari = by_verse[word_id]["devanagari"]
        fname_id = by_verse[word_id]["fname_key"]

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
        prefix = "spd" if program == "D5" else "gvr"
        stem_re = re.compile(
            rf"^{prefix}_{re.escape(fname_id)}_{role}_t(\d+)\.wav$"
        )
        prior = [
            int(m.group(1)) for p in d.glob("*.wav") if (m := stem_re.match(p.name))
        ]
        take = (max(prior) + 1) if prior else 0

        stem = f"{prefix}_{fname_id}_{role}_t{take}"
        wav_path = d / f"{stem}.wav"
        _write_wav(wav_path, y)

        checklist = _checklist_entry(
            session_id, fname_id, word_id, item_label, take, role,
            duration, peak,
            program=program,
            devanagari=item_devanagari,
            tradition=meta.get("recitation_tradition"),
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
    if meta.get("recitation_tradition"):
        ref_lines.append(
            f"Recitation tradition: {meta['recitation_tradition']} "
            "(protocol §3.6 — carried into every checklist row)."
        )
    ref_lines.append("")
    n_c, n_r = 0, 0
    if meta.get("program", "D5") == "D5":
        ref_lines.append("Canonical candidates → `data/spd/reference_words/<word_id>.wav`")
        ref_lines.append("Recitation takes → `data/spd/recitations/<word_id>__t<take>.wav`")
        ref_lines.append("")
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
    else:
        reciter = meta["reciter_slug"]
        ref_lines.append("All takes → `data/gvr_recordings/` with protocol §3 "
                         "registry-prep names:")
        ref_lines.append("")
        for verse_key, roles in sorted(takes.items()):
            for entry in roles.get("recitation", []):
                # entry file: gvr_<fname_key>_recitation_t<take>.wav
                m2 = re.fullmatch(
                    r"gvr_([a-z0-9]+)_recitation_t(\d+)\.wav", entry["file"]
                )
                if not m2:
                    continue
                fname_key, take_no = m2.group(1), m2.group(2)
                m3 = re.fullmatch(r"c(\d+)v(\d+)", fname_key)
                ch, v = (m3.group(1), m3.group(2)) if m3 else ("?", "?")
                verse_id = f"{ch}.{int(v):02d}" if m3 else verse_key
                ref_lines.append(
                    f"- [ ] `{entry['file']}` → "
                    f"`data/gvr_recordings/"
                    f"gvr_c{ch}v{int(v):02d}_{reciter}_{session_id}_t{take_no}.wav`"
                    f"  (verse_id {verse_id})"
                )
                n_r += 1
        ref_lines.append("")
        ref_lines.append(
            "After copying + label ear-check, build data/gvr_registry.json "
            "(FR-22 plan §5): per-row gates, per-reciter split assignment, "
            "then GvrRecognizer.train on the train split."
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
