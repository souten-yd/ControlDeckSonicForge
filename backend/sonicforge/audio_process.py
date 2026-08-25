from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path
from typing import Any, Awaitable, Callable

from .audio import inspect_wav
from .workers import WorkerError, WorkerResult

Progress = Callable[[float, str], Awaitable[None]]
_ALLOWED = {
    "trim_start_sec",
    "duration_sec",
    "gain_db",
    "normalize",
    "sample_rate",
    "channels",
}


def _number(value: Any, *, name: str, low: float, high: float) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise WorkerError(f"audio.process {name} must be numeric") from exc
    if not low <= result <= high:
        raise WorkerError(f"audio.process {name} is outside the supported range")
    return result


def process_argv(ffmpeg: str, source: Path, target: Path, parameters: dict[str, Any]) -> list[str]:
    unknown = set(parameters) - _ALLOWED
    if unknown:
        raise WorkerError(
            "audio.process has unsupported parameters: " + ", ".join(sorted(unknown))
        )

    start = _number(parameters.get("trim_start_sec"), name="trim_start_sec", low=0.0, high=24 * 60 * 60)
    duration = _number(parameters.get("duration_sec"), name="duration_sec", low=0.01, high=24 * 60 * 60)
    gain = _number(parameters.get("gain_db"), name="gain_db", low=-60.0, high=24.0)

    sample_rate = parameters.get("sample_rate")
    if sample_rate is not None:
        if isinstance(sample_rate, bool):
            raise WorkerError("audio.process sample_rate is invalid")
        try:
            sample_rate = int(sample_rate)
        except (TypeError, ValueError) as exc:
            raise WorkerError("audio.process sample_rate is invalid") from exc
        if not 8000 <= sample_rate <= 192000:
            raise WorkerError("audio.process sample_rate is outside the supported range")

    channels = parameters.get("channels")
    if channels is not None:
        if isinstance(channels, bool):
            raise WorkerError("audio.process channels is invalid")
        try:
            channels = int(channels)
        except (TypeError, ValueError) as exc:
            raise WorkerError("audio.process channels is invalid") from exc
        if channels not in {1, 2}:
            raise WorkerError("audio.process channels must be 1 or 2")

    normalize = parameters.get("normalize", False)
    if not isinstance(normalize, bool):
        raise WorkerError("audio.process normalize must be boolean")

    argv = [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y"]
    if start is not None:
        argv += ["-ss", f"{start:.6f}"]
    argv += ["-i", str(source), "-vn"]
    if duration is not None:
        argv += ["-t", f"{duration:.6f}"]

    filters: list[str] = []
    if gain is not None and gain != 0:
        filters.append(f"volume={gain:.3f}dB")
    if normalize:
        filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")
    if filters:
        argv += ["-af", ",".join(filters)]
    if sample_rate is not None:
        argv += ["-ar", str(sample_rate)]
    if channels is not None:
        argv += ["-ac", str(channels)]
    argv += ["-c:a", "pcm_s16le", str(target)]
    return argv


async def process_audio(
    source: Path,
    target: Path,
    parameters: dict[str, Any],
    progress: Progress,
) -> WorkerResult:
    source = source.resolve()
    target = target.resolve()
    if not source.is_file():
        raise WorkerError("audio.process source audio is missing")
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.is_relative_to(target.parent):
        raise WorkerError("audio.process target is invalid")
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise WorkerError("audio.process requires ffmpeg")

    argv = process_argv(ffmpeg, source, target, parameters)
    await progress(0.1, "Processing audio")
    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=os.name != "nt",
    )
    try:
        _stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=600)
    except (asyncio.CancelledError, TimeoutError):
        if proc.returncode is None:
            proc.kill()
        await proc.wait()
        raise
    if proc.returncode != 0:
        raise WorkerError(
            stderr.decode(errors="replace")[-1500:]
            or f"audio.process ffmpeg exited {proc.returncode}"
        )
    if not target.is_file():
        raise WorkerError("audio.process produced no output")
    meta = inspect_wav(target)
    await progress(1.0, "Audio processing complete")
    return WorkerResult(
        engine_id="ffmpeg.audio-process",
        engine_version=None,
        model_id=None,
        model_revision=None,
        model_license_id=None,
        output_path=target,
        payload={
            "process": dict(parameters),
            "qa": meta.get("qa", {}),
            "duration_ms": meta.get("duration_ms"),
            "sample_rate": meta.get("sample_rate"),
            "channels": meta.get("channels"),
        },
    )
