"""Demo recorder argument contract (synthetic fixture only, NFR-02).

One guarded invariant: the arecord call must never carry both a duration
(``-d``/``--duration``) and a sample count (``-s``/``--samples``) — ALSA
refuses that combination outright, which is how the first real take
failed. No audio hardware and no corpus audio are involved: the stubbed
runner writes a short silent WAV in the test's own tmp dir.
"""

from __future__ import annotations

import subprocess
import wave
from pathlib import Path

from demo import record_own


def _silent_wav(path: Path, seconds: float = 2.5) -> None:
    sr = record_own.RATE
    with wave.open(str(path), "wb") as w:
        w.setnchannels(record_own.CHANNELS)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"\x00\x00" * int(sr * seconds))


def test_arecord_args_never_pair_duration_with_samples(tmp_path, monkeypatch):
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):  # noqa: ANN001 — mirrors subprocess.run
        calls.append(list(cmd))
        _silent_wav(Path(cmd[-1]))
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(record_own.subprocess, "run", fake_run)
    monkeypatch.setattr(record_own.time, "sleep", lambda *_: None)

    out = record_own.record(tmp_path, "REFERENCE")

    assert out.is_file()
    assert len(calls) == 1
    cmd = calls[0]
    assert cmd[0] == "arecord"

    duration_flags = {"-d", "--duration"} & set(cmd)
    sample_flags = {"-s", "--samples"} & set(cmd)
    assert not (duration_flags and sample_flags), (
        f"arecord cannot take both a duration and a sample count: {cmd}"
    )

    # The 2.5 s take is requested by sample count only.
    assert "-s" in cmd
    assert cmd[cmd.index("-s") + 1] == str(record_own.SAMPLES)
    assert "-d" not in cmd and "--duration" not in cmd
