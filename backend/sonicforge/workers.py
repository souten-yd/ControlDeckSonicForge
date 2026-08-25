from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

from .config import Settings

ProgressCallback = Callable[[float, str], Awaitable[None]]


@dataclass
class WorkerResult:
    engine_id: str
    engine_version: str | None
    model_id: str | None
    model_revision: str | None
    model_license_id: str | None
    output_path: Path | None
    payload: dict


class WorkerError(RuntimeError):
    pass


def _runtime_python(settings: Settings, runtime_id: str) -> Path | None:
    path = settings.runtime_dir / runtime_id / "bin/python"
    return path if path.exists() and path.stat().st_size > 32 else None


def route(settings: Settings, task: str, language: str, routing_engine: str | None = None) -> tuple[str, Path, Path]:
    if settings.enable_fake_worker or routing_engine == "fake":
        return "fake", Path(sys.executable), settings.repo_root / "worker_packs/fake/worker.py"
    if task == "speech.tts.synthesize":
        py = _runtime_python(settings, "speech-rocm") or _runtime_python(settings, "speech-cpu")
        if not py:
            raise WorkerError("Speech Essentials is not installed")
        return "tts.qwen3", py, settings.repo_root / "worker_packs/qwen_tts/worker.py"
    if task == "speech.asr.transcribe":
        py = _runtime_python(settings, "speech-rocm") or _runtime_python(settings, "speech-cpu")
        if not py:
            raise WorkerError("Speech Essentials is not installed")
        return "asr.whisper", py, settings.repo_root / "worker_packs/whisper/worker.py"
    if task.startswith("audio."):
        py=_runtime_python(settings,"game-audio-rocm")
        if py: return "audio.stable-audio-3",py,settings.repo_root/"worker_packs/stable_audio3/worker.py"
        env_name="SONICFORGE_GAME_AUDIO_COMMAND"
    else:
        py=_runtime_python(settings,"music-rocm")
        if py: return "music.ace-step-1.5",py,settings.repo_root/"worker_packs/acestep/worker.py"
        env_name="SONICFORGE_MUSIC_COMMAND"
    command=os.environ.get(env_name)
    if command:
        parts=command.split(); return "external",Path(parts[0]),Path(parts[1]) if len(parts)>1 else Path("")
    raise WorkerError("Requested optional worker pack is not installed")


async def execute(settings: Settings, request: dict, work_dir: Path, progress: ProgressCallback) -> WorkerResult:
    engine_id, python, script = route(settings, request["task"], request.get("content_language", "auto"), request.get("routing", {}).get("engine"))
    work_dir.mkdir(parents=True, exist_ok=True)
    payload = {"request": request, "work_dir": str(work_dir)}
    if engine_id == "external":
        argv = [str(python)] + ([str(script)] if str(script) else [])
    else:
        argv = [str(python), str(script)]
    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, "PYTHONPATH": str(settings.repo_root)},
    )
    assert proc.stdin and proc.stdout
    proc.stdin.write((json.dumps(payload, ensure_ascii=False) + "\n").encode())
    await proc.stdin.drain()
    proc.stdin.close()
    final = None
    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        event = json.loads(line)
        if event.get("type") == "progress":
            await progress(float(event.get("progress", 0)), str(event.get("message", "")))
        elif event.get("type") == "result":
            final = event
        elif event.get("type") == "error":
            raise WorkerError(str(event.get("message", "worker failed")))
    code = await proc.wait()
    if code != 0 or final is None:
        stderr = (await proc.stderr.read()).decode(errors="replace") if proc.stderr else ""
        raise WorkerError(stderr[-1000:] or f"worker exited {code}")
    output = Path(final["output_path"]) if final.get("output_path") else None
    return WorkerResult(
        engine_id=final.get("engine_id", engine_id),
        engine_version=final.get("engine_version"),
        model_id=final.get("model_id"),
        model_revision=final.get("model_revision"),
        model_license_id=final.get("model_license_id"),
        output_path=output,
        payload=final.get("payload", {}),
    )
