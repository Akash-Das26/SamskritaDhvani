"""Restore the SPD reference-source audio from its documented origins,
with per-file identity verification (Run: ``python tools/restore_spd_audio.py [--skip-hall]``).

Why this exists: the ear-check staging
(``data/provenance/spd_listen_2026-09-23``, staged 2026-09-23)
references audio that went missing from disk — the 63 Loyola MP3s
(SPD-02), the 5 Hall MP3s (SPD-01), and the 9 gain-boosted noun-set
evidence renders. Nothing can be listened through until the exact
bytes are back. Identity is not assumed: every restored file is
sha256-checked against the values recorded in
``data/spd/loyola_cahill_sound_files/MANIFEST.csv`` (Loyola) and
re-verified after download with a re-sweep of decodability, sample
rate, channels, and duration (Hall, whose source carries no
manifest).

Usage::

    .venv/bin/python tools/restore_spd_audio.py            # both sets
    .venv/bin/python tools/restore_spd_audio.py --skip-hall

DataIntegrity discipline: this tool restores files to the exact state
the 2026-09-22 sweep verified — it never regenerates or substitutes
content. Any file that cannot be recovered byte-identical stays
absent and is reported as FAILED (excluded-and-counted, Rule 1); the
owner's ear-check verdict then applies only to what was actually
present.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import struct
import sys
import time
import urllib.request
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOYOLA_DIR = PROJECT_ROOT / "data" / "spd" / "loyola_cahill_sound_files"
MANIFEST = LOYOLA_DIR / "MANIFEST.csv"
HALL_DIR = PROJECT_ROOT / "data" / "spd" / "hall_sanskrit_pronunciation"

WAYBACK_TS = "20110606"  # capture year referenced by PROVENANCE SPD-02
UA = ("Mozilla/5.0 (X11; Linux x86_64) SamskritaDhvani-restore/1.0 "
      "(academic, non-commercial)")


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _fetch(url: str, timeout: float = 60.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _mp3_probe(data: bytes) -> dict:
    """Minimal MPEG-1 Layer III probe: header + duration estimate from
    the first frame header (bitrate/sr) and file size."""
    if data[:3] == b"ID3":
        # Skip ID3v2 tag to find the first frame sync.
        size = 0
        if len(data) > 9 and data[5] & 0x80:
            size = (data[6] << 21) | (data[7] << 14) | (data[8] << 7) | data[9]
        off = 10 + size
    else:
        off = 0
    i = off
    end = min(len(data), off + 65536)
    while i < end - 4:
        if data[i] == 0xFF and (data[i + 1] & 0xE0) == 0xE0:
            ver = (data[i + 1] >> 3) & 0x03     # 3 = MPEG1
            layer = (data[i + 1] >> 1) & 0x03   # 1 = Layer III
            br_idx = (data[i + 2] >> 4) & 0x0F
            sr_idx = (data[i + 2] >> 2) & 0x03
            if ver == 3 and layer == 1 and br_idx not in (0, 15) \
                    and sr_idx != 3:
                br = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192,
                      224, 256, 320][br_idx] * 1000
                sr = [44100, 48000, 32000][sr_idx]
                n = len(data) - off
                return {"mpeg": "1-III", "sr": sr, "bitrate": br,
                        "dur_s": round(n * 8.0 / br, 1)}
        i += 1
    return {}


def _restore_one_loyola(row: dict) -> tuple[str, str | None]:
    """Restore one Loyola file; returns (name, problem-or-None)."""
    name = row["file"]
    dest = LOYOLA_DIR / name
    if dest.is_file():
        if _sha256(dest.read_bytes()).startswith(row["sha16"]):
            return name, None
        return name, (
            f"{name}: on-disk bytes do not match MANIFEST sha16 {row['sha16']}"
        )
    original = f"http://www.loyno.edu/~tccahill/skt_sound_files/{name}"
    candidates = [
        f"https://web.archive.org/web/{ts}id_/{original}"
        for ts in (WAYBACK_TS, "2011", "2012", "2013", "2014")
    ]
    data = None
    for url in candidates:
        try:
            data = _fetch(url)
            if data[:3] == b"ID3" or (len(data) > 2 and data[0] == 0xFF):
                break
            data = None  # HTML/JSON error page, not audio
        except Exception as exc:  # noqa: BLE001 — try next capture
            print(f"    retry {name}: {exc}", file=sys.stderr)
            time.sleep(1.0)
    if data is None:
        return name, f"{name}: no Wayback capture yielded audio bytes"
    if not _sha256(data).startswith(row["sha16"]):
        return name, (
            f"{name}: recovered sha256 does not match MANIFEST sha16 "
            f"{row['sha16']} (got {_sha256(data)[:16]}) — NOT saved"
        )
    dest.write_bytes(data)
    print(f"    restored {name} ({len(data)} B, sha16 ok)")
    return name, None


def restore_loyola() -> tuple[list[str], list[str]]:
    """Wayback-recover the 63 MP3s, verifying against MANIFEST.csv.

    Fetches run 4-at-a-time (Wayback latency dominates); results are
    reported in MANIFEST order and every write is sha16-verified
    before it lands.
    """
    if not MANIFEST.is_file():
        return ["MANIFEST.csv missing — cannot verify identity"], []
    rows = list(csv.DictReader(MANIFEST.read_text(encoding="utf-8").splitlines()))
    results: list[tuple[str, str | None]] = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(_restore_one_loyola, rows))
    ok, failed = [], []
    for name, problem in results:
        if problem is None:
            ok.append(name)
        else:
            failed.append(problem)
    return [f"Loyola: {m}" for m in failed], ok


def restore_hall() -> tuple[list[str], list[str]]:
    """Re-download the 5 Hall MP3s; identity = exact byte size (recorded
    in the PROVENANCE sub-table) + real-decoder duration check. The
    first-frame MP3 probe is useless on VBR files, so verification uses
    soundfile/libsndfile (the same decoder the sweep used)."""
    expected = {
        "skpro_00.mp3": (274013, 78.5),
        "skpro_01.mp3": (3039419, 1001.3),
        "skpro_02.mp3": (3495647, 1237.3),
        "skpro_03.mp3": (885755, 297.0),
        "skpro_04.mp3": (197363, 67.5),
    }
    base = "https://theosociety.org/pasadena/sk-pron/"
    problems, ok = [], []
    import soundfile as sf

    HALL_DIR.mkdir(parents=True, exist_ok=True)
    for name, (size, dur) in expected.items():
        dest = HALL_DIR / name
        if not dest.is_file():
            try:
                data = _fetch(base + name)
            except Exception as exc:  # noqa: BLE001 — reported, not fatal
                problems.append(f"Hall: {name}: download failed: {exc}")
                continue
            if len(data) != size:
                problems.append(
                    f"Hall: {name}: size {len(data)} != recorded {size} — "
                    "NOT saved (source may have changed)"
                )
                continue
            dest.write_bytes(data)
            print(f"    restored {name} ({len(data)} B)")
        info = sf.info(str(dest))
        got_dur = info.frames / info.samplerate
        if abs(got_dur - dur) > max(2.0, 0.02 * dur):
            problems.append(
                f"Hall: {name}: decoder duration {got_dur:.1f}s inconsistent "
                f"with recorded {dur}s — investigate before use"
            )
            continue
        ok.append(name)
    return problems, ok


def rebuild_boosted() -> tuple[list[str], list[str]]:
    """Re-render the 9 gain-boosted noun-set evidence WAVs from the
    restored Loyola files (the boost recipe: peak → 0.60)."""
    src_dir = LOYOLA_DIR
    out_dir = PROJECT_ROOT / "data" / "provenance" / "spd_listen_2026-09-23" / "boosted_audio"
    out_dir.mkdir(parents=True, exist_ok=True)
    problems, ok = [], []
    try:
        import soundfile as sf
        import numpy as np
    except ImportError:
        return ["boosted renders: soundfile/numpy unavailable"], []
    # Noun-set stems come from MANIFEST.csv (the swept truth), not from
    # guessed transliterations — e.g. kanyaa/dhii/strii/bhaanu have
    # doubled vowels the guess list got wrong.
    stems = sorted(
        row["file"][:-4] for row in csv.DictReader(
            MANIFEST.read_text(encoding="utf-8").splitlines())
        if row["file"].startswith("noun")
    )
    if len(stems) != 9:
        problems.append(
            f"boosted: expected 9 noun-set rows in MANIFEST, found {len(stems)}"
        )
        return problems, ok
    for stem in stems:
        src = src_dir / f"{stem}.mp3"
        if not src.is_file():
            problems.append(f"boosted: source missing: {src.name}")
            continue
        try:
            audio, sr = sf.read(str(src), dtype="float32", always_2d=True)
            mono = audio.mean(axis=1)
            peak = float(np.abs(mono).max())
            if peak <= 0:
                problems.append(f"boosted: {stem}: silent source")
                continue
            boosted = (mono * (0.60 / peak)).clip(-1.0, 1.0)
            buf = io.BytesIO()
            with wave.open(buf, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(sr)
                w.writeframes(b"".join(
                    struct.pack("<h", int(s * 32767)) for s in boosted
                ))
            (out_dir / f"{stem}_boost.wav").write_bytes(buf.getvalue())
            ok.append(f"{stem}_boost.wav")
        except Exception as exc:  # noqa: BLE001 — per-file, loud
            problems.append(f"boosted: {stem}: {exc}")
    return problems, ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--skip-hall", action="store_true")
    parser.add_argument("--skip-boosted", action="store_true")
    args = parser.parse_args(argv)

    print("== Loyola (SPD-02) — Wayback recovery + sha16 verification")
    problems, ok = restore_loyola()
    print(f"    {len(ok)}/63 present-and-verified")

    if not args.skip_hall:
        print("== Hall (SPD-01) — re-download + size/probe identity")
        p2, ok2 = restore_hall()
        print(f"    {len(ok2)}/5 verified")
        problems += p2

    if not args.skip_boosted:
        print("== Boosted noun-set evidence renders (rebuild)")
        p3, ok3 = rebuild_boosted()
        print(f"    {len(ok3)}/9 rendered")
        problems += p3

    if problems:
        print("\nFAILED items (excluded and counted — Rule 1):")
        for p in problems:
            print(f"  - {p}")
    print("\nRESULT:", "ALL VERIFIED" if not problems else
          f"{len(problems)} PROBLEM(S) — see above")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
