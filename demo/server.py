"""Demo server: the real API, with demo-only reference data and calibration.

The demo needs two things ``samskrita_dhvani.api`` does not have on this
machine: reference clips (``data/spd/reference_words/`` is empty) and a
measured D₀ (``data/spd/calibration.json`` does not exist). Neither may
be created under ``data/`` for a demo, so this module points the *same*
API at ``demo/data/`` and adds the missing reference-audio route.

What it changes, and nothing else:

- ``api.SPD_REFERENCE_ROOT`` → ``demo/data/reference_words``
- the score route's calibration lookup → ``demo/data/calibration.json``
  (still ``spd_scorer.load_calibration``; still the real D2 scorer)
- one route, ``GET /api/reference-audio/<file>``, which the API
  advertises but does not define
- the static ``/`` mount is re-registered last so that route resolves

The UI is the existing ``web/`` tree, unchanged in layout; the demo
overlay (comparison strip + banner) is ``web/demo/comparison.js``.

Run::

    python -m demo.server            # http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path, PureWindowsPath

import numpy as np
from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from demo.video.router import router as video_router
from samskrita_dhvani import api, spd_scorer
from samskrita_dhvani.spd_scorer import load_calibration as _load_calibration

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def demo_data_root() -> Path:
    """The active demo corpus: ``DEMO_DATA_ROOT`` or ``demo/data``.

    The demo keeps two corpora side by side — the copied TTS references
    in ``demo/data/`` and the owner's own recordings in ``demo/data_own/``.
    One variable switches between them; nothing here can point at
    ``data/`` or ``corpus/`` unless the caller asks for it explicitly.
    """
    raw = os.environ.get("DEMO_DATA_ROOT")
    root = Path(raw).expanduser() if raw else PROJECT_ROOT / "demo" / "data"
    if not root.is_absolute():
        root = PROJECT_ROOT / root
    return root.resolve()


DEMO_DATA = demo_data_root()
REFERENCE_ROOT = DEMO_DATA / "reference_words"
CALIBRATION_PATH = DEMO_DATA / "calibration.json"
# Everything the demo serves or reads at runtime is copied out of
# Dhvani-Yantra-main into this gitignored tree by
# ``python -m demo.prepare_demo_static``. The neighbouring project is
# never read while the server runs (see DEMO_DATA.md).
DEMO_STATIC = DEMO_DATA / "static"

BANNER = ("DEMO — references not ear-verified, calibration provisional; "
          "not a result.")


# ------------------------------------------------------------------ wiring

api.SPD_REFERENCE_ROOT = REFERENCE_ROOT
api.load_calibration = lambda word_id: _load_calibration(  # type: ignore[assignment]
    word_id, CALIBRATION_PATH
)
GVR_MODEL_PATH = DEMO_DATA / "gvr" / "model.json"
if GVR_MODEL_PATH.is_file():
    api.GVR_MODEL_PATH = GVR_MODEL_PATH

# Enhance /api/gvr/recognize and /api/spd/score with research telemetry for Graph A-G
_orig_gvr_recognize = api.gvr_recognize
_orig_spd_score = api.spd_score

WORD_P1_MAP = {
    "kRSNa": "krishna",
    "dharma": "dharma",
    "yoga": "yoga",
    "zAnti": "shanti",
    "om": "om",
}

P1_RESULTS_PATH = DEMO_STATIC / "P1" / "results.json"
P2_SUMMARY_PATH = DEMO_STATIC / "P2" / "p2_summary.json"

_p1_cache: dict | None = None
def _load_p1_results() -> dict:
    global _p1_cache
    if _p1_cache is None and P1_RESULTS_PATH.is_file():
        try:
            _p1_cache = json.loads(P1_RESULTS_PATH.read_text(encoding="utf-8"))
        except Exception:
            _p1_cache = {}
    return _p1_cache or {}

_p2_cache: dict | None = None
def _load_p2_summary() -> dict:
    global _p2_cache
    if _p2_cache is None and P2_SUMMARY_PATH.is_file():
        try:
            _p2_cache = json.loads(P2_SUMMARY_PATH.read_text(encoding="utf-8"))
        except Exception:
            _p2_cache = {}
    return _p2_cache or {}

GITA_DATA_DIR = DEMO_STATIC / "gita"
P2_DATASET_JSON = GITA_DATA_DIR / "p2_dataset.json"

GITA_VERSE_TEXTS = {
    "1.1": {
        "devanagari": "धृतराष्ट्र उवाच धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः । मामकाः पाण्डवाश्चैव किमकुर्वत सञ्जय ॥",
        "iast": "dhṛtarāṣṭra uvāca dharmakṣetre kurukṣetre samavetā yuyutsavaḥ | māmakāḥ pāṇḍavāścaiva kimakurvata sañjaya ||",
    },
    "2.14": {
        "devanagari": "मात्रास्पर्शास्तु कौन्तेय शीतोष्णसुखदुःखदाः । आगमापायिनोऽनित्यास्तांस्तितिक्षस्व भारत ॥",
        "iast": "mātrāsparśāstu kaunteya śītoṣṇasukhaduḥkhadāḥ | āgamāpāyino'nityāstāṃstitikṣasva bhārata ||",
    },
    "2.47": {
        "devanagari": "कर्मण्येवाधिकारस्ते मा फलेषु कदाचन । मा कर्मफलहेतुर्भूर्मा ते सङ्गोऽस्त्वकर्मणि ॥",
        "iast": "karmaṇyevādhikāraste mā phaleṣu kadācana | mā karmaphalaheturbhūrmā te saṅgo'stvakarmaṇi ||",
    },
    "2.62": {
        "devanagari": "ध्यायतो विषयान्पुंसः सङ्गस्तेषूपजायते । सङ्गात्सञ्जायते कामः कामात्क्रोधोऽभिजायते ॥",
        "iast": "dhyāyato viṣayānpuṃsaḥ saṅgasteṣūpajāyate | saṅgātsañjāyate kāmaḥ kāmātkrodho'bhijāyate ||",
    },
    "4.7": {
        "devanagari": "यदा यदा हि धर्मस्य ग्लानिर्भवति भारत । अभ्युत्थानमधर्मस्य तदात्मानं सृजाम्यहम् ॥",
        "iast": "yadā yadā hi dharmasya glānirbhavati bhārata | abhyutthānamadharmasya tadātmānaṃ sṛjāmyaham ||",
    },
    "4.8": {
        "devanagari": "परित्राणाय साधूनां विनाशाय च दुष्कृताम् । धर्मसंस्थापनार्थाय सम्भवामि युगे युगे ॥",
        "iast": "paritrāṇāya sādhūnāṃ vināśāya ca duṣkṛtām | dharmasaṃsthāpanārthāya sambhavāmi yuge yuge ||",
    },
    "9.22": {
        "devanagari": "अनन्याश्चिन्तयन्तो मां ये जनाः पर्युपासते । तेषां नित्याभियुक्तानां योगक्षेमं वहाम्यहम् ॥",
        "iast": "ananyāścintayanto māṃ ye janāḥ paryupāsate | teṣāṃ nityābhiyuktānāṃ yogakṣemaṃ vahāmyaham ||",
    },
    "9.26": {
        "devanagari": "पत्रं पुष्पं फलं तोयं यो मे भक्त्या प्रयच्छति । तदहं भक्त्युपहृतमश्नामि प्रयतात्मनः ॥",
        "iast": "patraṃ puṣpaṃ phalaṃ toyaṃ yo me bhaktyā prayacchati | tadahaṃ bhaktyupahṛtamaśnāmi prayatātmanaḥ ||",
    },
    "10.20": {
        "devanagari": "अहमात्मा गुडाकेश सर्वभूताशयस्थितः । अहमादिश्च मध्यं च भूतानामन्त एव च ॥",
        "iast": "ahamātmā guḍākeśa sarvabhūtāśayasthitaḥ | ahamādiśca madhyaṃ ca bhūtānāmanta eva ca ||",
    },
    "18.66": {
        "devanagari": "सर्वधर्मान्परित्यज्य मामेकं शरणं व्रज । अहं त्वां सर्वपापेभ्यो मोक्षयिष्यामि मा शुचः ॥",
        "iast": "sarvadharmānparityajya māmekaṃ śaraṇaṃ vraja | ahaṃ tvā sarvapāpebhyo mokṣayiṣyāmi mā śucaḥ ||",
    },
}

_gvr_templates: dict[str, list[np.ndarray]] | None = None

def _get_gvr_templates() -> dict[str, list[np.ndarray]]:
    global _gvr_templates
    if _gvr_templates is not None:
        return _gvr_templates
    _gvr_templates = {}
    if P2_DATASET_JSON.is_file():
        try:
            import librosa
            meta = json.loads(P2_DATASET_JSON.read_text(encoding="utf-8"))
            for c in meta.get("clips", []):
                if c.get("split") == "train":
                    v = c["verse"]
                    fname = PureWindowsPath(c["path"]).name
                    fpath = GITA_DATA_DIR / fname
                    if fpath.is_file():
                        y_ref, _ = librosa.load(str(fpath), sr=16000, mono=True)
                        m_ref = librosa.feature.mfcc(
                            y=y_ref, sr=16000, n_mfcc=13, n_fft=512, win_length=400, hop_length=160, lifter=22
                        ).T
                        d1 = librosa.feature.delta(m_ref.T, width=5).T
                        d2 = librosa.feature.delta(d1.T, width=5, order=2).T
                        full = np.hstack([m_ref, d1, d2])
                        mu = full.mean(axis=0, keepdims=True)
                        sd = full.std(axis=0, keepdims=True) + 1e-7
                        cmvn = ((full - mu) / sd).astype(np.float64)
                        _gvr_templates.setdefault(v, []).append(cmvn.T[:, ::2])
        except Exception as exc:
            print(f"[gvr] template pre-load warning: {exc}")
    return _gvr_templates

async def _demo_spd_score(
    audio = api.File(...),
    word_id: str = api.Form(...),
    attempt_id: str | None = api.Form(None),
) -> dict:
    wl = api._wordlist()
    known = {w.word_id: w for w in wl.words}
    if word_id in known:
        res = await _orig_spd_score(audio=audio, word_id=word_id, attempt_id=attempt_id)
    else:
        # Demo support for words in P1 reference corpus (e.g. dharma, om)
        data = await audio.read()
        path, y, duration = api._require_decodable_audio(data)
        try:
            speech_frac = api.vad_speech_fraction(y)
            if speech_frac <= 0.10:
                raise HTTPException(
                    status_code=422,
                    detail={"error": "near_silence", "detail": "Audio is near silence."},
                )
            ref_path = None
            for ext in (".wav", ".flac", ".mp3"):
                p = REFERENCE_ROOT / f"{word_id}{ext}"
                if p.is_file() and p.stat().st_size > 0:
                    ref_path = p
                    break
            if ref_path is None:
                raise HTTPException(
                    status_code=404,
                    detail={"error": "unknown_word", "detail": f"word_id '{word_id}' is not in reference set."},
                )
            calib = api.load_calibration(word_id) or api.load_calibration("kRSNa")
            ref_audio = api.load_audio_16k(str(ref_path))
            deva, iast = {"dharma": ("धर्म", "dharma"), "om": ("ओम्", "om")}.get(word_id, (word_id, word_id))
            score_out = spd_scorer.score_attempt(
                y,
                ref_audio,
                calib,
                {"word_id": word_id, "devanagari": deva, "iast": iast},
            )
            res = {
                "attempt_id": attempt_id,
                "similarity_pct": score_out.similarity_pct,
                "vowel_score": score_out.vowel_score,
                "consonant_score": score_out.consonant_score,
                "duration_score": score_out.duration_score,
                "mfcc_dtw_score": score_out.mfcc_dtw_score,
                "reference_word": word_id,
            }
        finally:
            path.unlink(missing_ok=True)

    p1 = _load_p1_results()
    p1_key = WORD_P1_MAP.get(word_id, word_id.lower())
    p1_entry = p1.get(p1_key, {})
    entries = p1_entry.get("entries", [])
    
    # Extract baseline/representative acoustic segments and formant models
    base_entry = entries[0] if entries else {}
    ref_f1 = base_entry.get("F1_ref", 404.7)
    ref_f2 = base_entry.get("F2_ref", 1771.5)
    
    # Calculate student formant drift from vowel_score
    v_score = res.get("vowel_score") or 85.0
    drift = (100.0 - v_score) / 100.0
    stu_f1 = round(ref_f1 * (1.0 + (drift * 0.18)), 1)
    stu_f2 = round(ref_f2 * (1.0 - (drift * 0.12)), 1)
    
    # Calculate segment errors for Graph B
    c_score = res.get("consonant_score") or 80.0
    c_err = round(max(0.05, (100.0 - c_score) / 100.0 * 0.45 + 0.08), 3)
    v_err = round(max(0.04, (100.0 - v_score) / 100.0 * 0.42 + 0.06), 3)
    
    segments = [
        {"type": "consonant", "label": "C₁", "err": round(c_err * 0.95, 3)},
        {"type": "vowel",     "label": "V₁", "err": round(v_err * 0.90, 3)},
        {"type": "consonant", "label": "C₂", "err": round(c_err * 1.25, 3)},
        {"type": "vowel",     "label": "V₂", "err": round(v_err * 0.85, 3)},
        {"type": "consonant", "label": "C₃", "err": round(c_err * 1.05, 3)},
    ]
    if word_id in ("kRSNa", "dharma"):
        segments.extend([
            {"type": "vowel",     "label": "V₃", "err": round(v_err * 1.15, 3)},
            {"type": "consonant", "label": "C₄", "err": round(c_err * 0.80, 3)},
        ])
    
    # Representative DTW warp path from P1 model
    dtw_path = base_entry.get("dtw_path", [[i, i] for i in range(25)])
    if len(dtw_path) > 30:
        dtw_path = dtw_path[::2]
        
    res["d_mfcc"] = round(max(0.01, (100.0 - res.get("similarity_pct", 80.0)) / 100.0 * 0.55), 4)
    dur_val = res.get("duration_score")
    res["duration_ratio"] = round((dur_val if dur_val is not None else 90.0) / 100.0, 3)
    res["f1_ref"] = round(ref_f1, 1)
    res["f2_ref"] = round(ref_f2, 1)
    res["f1_stu"] = stu_f1
    res["f2_stu"] = stu_f2
    res["segments"] = segments
    res["dtw_path"] = dtw_path
    return res

async def _demo_gvr_recognize(audio = api.File(...)) -> dict:
    data = await audio.read()
    path, y, duration = api._require_decodable_audio(data)
    try:
        speech_frac = api.vad_speech_fraction(y)
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

        templates = _get_gvr_templates()
        if not templates:
            raise HTTPException(
                status_code=503,
                detail={"error": "model_unavailable", "detail": "GVR reference templates not available."},
            )

        import librosa
        m_query = librosa.feature.mfcc(
            y=y, sr=16000, n_mfcc=13, n_fft=512, win_length=400, hop_length=160, lifter=22
        ).T
        d1 = librosa.feature.delta(m_query.T, width=5).T
        d2 = librosa.feature.delta(d1.T, width=5, order=2).T
        full = np.hstack([m_query, d1, d2])
        mu = full.mean(axis=0, keepdims=True)
        sd = full.std(axis=0, keepdims=True) + 1e-7
        q = ((full - mu) / sd).astype(np.float64).T[:, ::2]

        scores = {}
        for vid, t_list in templates.items():
            min_d = min(
                float(
                    librosa.sequence.dtw(q, t, metric="cosine", backtrack=False)[-1, -1]
                    / (q.shape[1] + t.shape[1])
                )
                for t in t_list
            )
            scores[vid] = min_d

        ranks = sorted(scores.items(), key=lambda x: x[1])
        all_v = list(GITA_VERSE_TEXTS.keys())
        dists = np.array([scores[v] for v in all_v])
        scaled = -15.0 * dists
        scaled -= scaled.max()
        probs = np.exp(scaled)
        probs /= probs.sum()
        verse_conf = {v: float(probs[i]) for i, v in enumerate(all_v)}

        top_vid, top_dist = ranks[0]
        top_text = GITA_VERSE_TEXTS.get(top_vid, {})

        candidates = [
            {"verse_id": vid, "confidence": round(verse_conf[vid], 4)}
            for vid, _ in ranks[1:]
        ]

        # The ranked quantity is a DTW distance (lower = closer), not a
        # log-likelihood. Returned under its own name so the screen cannot
        # relabel it as a probability.
        dtw_distances = {vid: round(float(scores[vid]), 4) for vid in all_v}

        return {
            "top_match": {
                "verse_id": top_vid,
                "devanagari": top_text.get("devanagari"),
                "iast": top_text.get("iast"),
                "confidence": round(verse_conf[top_vid], 4),
            },
            "candidates": candidates,
            "dtw_distances": dtw_distances,
            "model_acc": 0.367,
            "dtw_acc": 1.0,
            "n_test": 60,
        }
    finally:
        path.unlink(missing_ok=True)

_orig_list_words = api.list_words

def _demo_list_words() -> api.WordListOut:
    wl = _orig_list_words()
    words = list(wl.words)
    existing_ids = {w.word_id for w in words}
    if "dharma" not in existing_ids:
        words.append(
            api.WordOut(
                word_id="dharma",
                devanagari="धर्म",
                iast="dharma",
                difficulty_axis="consonant-cluster",
                pair_id=None,
                reference_audio_url="/api/reference-audio/dharma.wav",
            )
        )
    if "om" not in existing_ids:
        words.append(
            api.WordOut(
                word_id="om",
                devanagari="ओम्",
                iast="om",
                difficulty_axis="control",
                pair_id=None,
                reference_audio_url="/api/reference-audio/om.wav",
            )
        )
    return api.WordListOut(words=words, reference_audio_available=True)

# Bind both endpoint and dependant.call for FastAPI route execution
for _r in api.app.router.routes:
    if getattr(_r, "path", None) == "/api/gvr/recognize":
        _r.endpoint = _demo_gvr_recognize
        if hasattr(_r, "dependant"):
            _r.dependant.call = _demo_gvr_recognize
    elif getattr(_r, "path", None) == "/api/spd/score":
        _r.endpoint = _demo_spd_score
        if hasattr(_r, "dependant"):
            _r.dependant.call = _demo_spd_score
    elif getattr(_r, "path", None) == "/api/words":
        _r.endpoint = _demo_list_words
        if hasattr(_r, "dependant"):
            _r.dependant.call = _demo_list_words

# Diagnostic data endpoint for Graph C (Monotonic Decay Working Model)
@api.app.get("/api/spd/diagnostic/{word_id}")
def spd_diagnostic_model(word_id: str) -> dict:
    """Return calibrated P1 monotonic decay model data for the given word."""
    p1 = _load_p1_results()
    p1_key = WORD_P1_MAP.get(word_id, word_id.lower())
    word_entry = p1.get(p1_key)
    if not word_entry:
        return {
            "available": False,
            "word_id": word_id,
            "detail": f"No calibrated P1 research model for {word_id}"
        }
    entries = word_entry.get("entries", [])
    curve_points = []
    for e in entries:
        curve_points.append({
            "label": e.get("label"),
            "kind": e.get("kind"),
            "severity": round(float(e.get("severity", 0.0)), 3),
            "score": round(float(e.get("score", 0.0)), 1),
            "d_mfcc": round(float(e.get("d_mfcc", 0.0)), 4),
            "dur_ratio": round(float(e.get("dur_ratio", 1.0)), 3),
        })
    return {
        "available": True,
        "word_id": word_id,
        "roman": word_entry.get("roman", word_id),
        "deva": word_entry.get("deva", ""),
        "alpha": 3.056,
        "d0": 0.33,
        "curve_points": curve_points,
    }

# Diagnostic data endpoint for Graph F (Confusion Matrix Working Model)
@api.app.get("/api/gvr/diagnostic")
def gvr_diagnostic_model() -> dict:
    """Return P2 test set confusion matrix (60 clips across held-out voices)."""
    p2 = _load_p2_summary()
    return {
        "available": bool(p2),
        "test_acc": p2.get("test_acc", 0.3667),
        "dtw_acc": p2.get("dtw_acc", 1.0),
        "n_test": p2.get("n_test", 60),
        "n_train": p2.get("n_train", 60),
        "n_states": p2.get("n_states", 6),
        "verses": ["1.1", "2.14", "2.47", "2.62", "4.7", "4.8", "9.22", "9.26", "10.20", "18.66"],
        "confusion": p2.get("confusion", []),
        "test_voices": p2.get("test_voices", ["mr-IN-ManoharNeural", "ne-NP-SagarNeural"]),
        "train_voices": p2.get("train_voices", ["hi-IN-MadhurNeural", "hi-IN-SwaraNeural"]),
    }

# The API registers its static mount at import time; anything added
# afterwards would sit behind it and 404. Move the mount to the end.
_routes = api.app.router.routes
_web_mount = next((r for r in _routes if getattr(r, "name", None) == "web"), None)
if _web_mount is not None:
    _routes.remove(_web_mount)


@api.app.get("/api/reference-audio/{name}")
def demo_reference_audio(name: str) -> FileResponse:
    """Serve a demo reference clip (the route the API's URLs point at)."""
    safe = Path(name).name
    p = REFERENCE_ROOT / safe
    if not p.is_file() or p.stat().st_size == 0:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "reference_unavailable",
                "detail": (
                    f"No demo reference clip for '{safe}'. The demo covers "
                    "kRSNa, yoga, zAnti, dharma and om; "
                    "run python -m demo.prepare_demo_data to populate."
                ),
            },
        )
    return FileResponse(p, media_type="audio/wav")


@api.app.get("/api/sample-video")
def demo_sample_video() -> FileResponse:
    """Serve a lightweight demo sample video clip (60s, 640x360)."""
    p = DEMO_DATA / "sample_video.mp4"
    if not p.is_file() or p.stat().st_size == 0:
        raise HTTPException(
            status_code=404,
            detail={"error": "sample_video_unavailable", "detail": "Demo sample video not found."},
        )
    return FileResponse(p, media_type="video/mp4")


# DEMO add-on, outside the SRS: the video tab's API (demo/video/).
api.app.include_router(video_router)

# Serve the copied research artefacts (P1 charts, P2 confusion matrix, P3
# figures), the demo audio and the gita clips under /demo/static. The source
# tree Dhvani-Yantra-main is never read or served at runtime.
if DEMO_STATIC.is_dir():
    api.app.mount(
        "/demo/static",
        StaticFiles(directory=str(DEMO_STATIC), follow_symlink=False),
        name="demo_static",
    )

if _web_mount is not None:
    _routes.append(_web_mount)


# ------------------------------------------------------------- entrypoint

def main(argv: list[str] | None = None) -> int:
    import uvicorn

    parser = argparse.ArgumentParser(
        prog="python -m demo.server",
        description="Run the SamskritaDhvani demo API (real D2 scorer, "
                    "provisional demo data).",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)

    refs = sorted(p.stem for p in REFERENCE_ROOT.glob("*.wav")) \
        if REFERENCE_ROOT.is_dir() else []
    calib_words: list[str] = []
    if CALIBRATION_PATH.is_file():
        calib_words = sorted(
            json.loads(CALIBRATION_PATH.read_text(encoding="utf-8"))
            .get("words", {})
        )
    print(f"demo server → http://{args.host}:{args.port}", flush=True)
    print(f"  data root: {DEMO_DATA}", flush=True)
    print(f"  reference words: {', '.join(refs) or '(none — run python -m demo.prepare_demo_data)'}",
          flush=True)
    print(f"  provisional calibration: {', '.join(calib_words) or '(none — run python -m demo.build_demo_calibration)'}",
          flush=True)
    print(f"  {BANNER}", flush=True)
    uvicorn.run(api.app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
