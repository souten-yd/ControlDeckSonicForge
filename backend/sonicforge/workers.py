from __future__ import annotations

import asyncio
import json
import os
import shlex
import signal
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

from .config import Settings

ProgressCallback = Callable[[float, str], Awaitable[None]]
MAX_WORKER_OUTPUT_BYTES = 1024 * 1024 * 1024
MAX_STDERR_TAIL_BYTES = 32 * 1024


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


def route(
    settings: Settings,
    task: str,
    language: str,
    routing_engine: str | None = None,
) -> tuple[str, Path, Path]:
    del language
    if settings.enable_fake_worker or routing_engine == "fake":
        return (
            "fake",
            Path(sys.executable),
            settings.repo_root / "worker_packs/fake/worker.py",
        )
    if task == "speech.tts.synthesize":
        py = _runtime_python(settings, "speech-rocm") or _runtime_python(
            settings, "speech-cpu"
        )
        if not py:
            raise WorkerError("Speech Essentials is not installed")
        return (
            "tts.qwen3",
            py,
            settings.repo_root / "worker_packs/qwen_tts/worker.py",
        )
    if task == "speech.asr.transcribe":
        py = _runtime_python(settings, "speech-rocm") or _runtime_python(
            settings, "speech-cpu"
        )
        if not py:
            raise WorkerError("Speech Essentials is not installed")
        return (
            "asr.whisper",
            py,
            settings.repo_root / "worker_packs/whisper/worker.py",
        )
    if task.startswith("audio."):
        py = _runtime_python(settings, "game-audio-cpu")
        if py:
            return (
                "audio.stable-audio-3",
                py,
                settings.repo_root / "worker_packs/stable_audio3/worker.py",
            )
        env_name = "SONICFORGE_GAME_AUDIO_COMMAND"
    else:
        py = _runtime_python(settings, "music-rocm")
        if py:
            return (
                "music.ace-step-1.5",
                py,
                settings.repo_root / "worker_packs/acestep/worker.py",
            )
        env_name = "SONICFORGE_MUSIC_COMMAND"

    command = os.environ.get(env_name)
    if command:
        parts = shlex.split(command)
        if not parts:
            raise WorkerError(f"{env_name} is empty")
        # The stable worker contract sends the request as JSON on stdin. Keep the
        # override deliberately small: executable + optional script. Previously
        # extra arguments were silently discarded, which could run a materially
        # different command than the operator configured.
        if len(parts) > 2:
            raise WorkerError(
                f"{env_name} supports an executable plus one optional script only; "
                "wrap commands requiring additional arguments in a script"
            )
        return (
            "external",
            Path(parts[0]),
            Path(parts[1]) if len(parts) == 2 else Path(""),
        )
    raise WorkerError("Requested optional worker pack is not installed")


async def _terminate(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is not None:
        return
    try:
        if os.name != "nt":
            os.killpg(proc.pid, signal.SIGTERM)
        else:
            proc.terminate()
    except ProcessLookupError:
        return
    try:
        await asyncio.wait_for(proc.wait(), timeout=3)
    except TimeoutError:
        try:
            if os.name != "nt":
                os.killpg(proc.pid, signal.SIGKILL)
            else:
                proc.kill()
        except ProcessLookupError:
            pass
        await proc.wait()


def _close_process_transport(proc: asyncio.subprocess.Process) -> None:
    transport = getattr(proc, "_transport", None)
    if transport is not None:
        transport.close()


async def _stderr_tail(stream: asyncio.StreamReader | None) -> bytes:
    if stream is None:
        return b""
    tail = bytearray()
    while True:
        chunk = await stream.read(4096)
        if not chunk:
            return bytes(tail)
        tail.extend(chunk)
        if len(tail) > MAX_STDERR_TAIL_BYTES:
            del tail[:-MAX_STDERR_TAIL_BYTES]


async def execute(
    settings: Settings,
    request: dict,
    work_dir: Path,
    progress: ProgressCallback,
) -> WorkerResult:
    engine_id, python, script = route(
        settings,
        request["task"],
        request.get("content_language", "auto"),
        request.get("routing", {}).get("engine"),
    )
    work_dir.mkdir(parents=True, exist_ok=True)
    work_root = work_dir.resolve()
    payload = {"request": request, "work_dir": str(work_root)}
    if engine_id == "external":
        argv = [str(python)] + ([str(script)] if str(script) else [])
    else:
        argv = [str(python), str(script)]
    env = {
        **os.environ,
        "PYTHONPATH": str(settings.repo_root),
        "HF_HOME": str(settings.models_dir / "huggingface"),
        # ACE-Step honors this upstream variable before project_root/checkpoints.
        # Keeping it under SonicForge avoids hidden writes to ~/.cache/ace-step.
        "ACESTEP_CHECKPOINTS_DIR": str(settings.models_dir / "ace-step"),
    }
    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
        start_new_session=os.name != "nt",
    )
    assert proc.stdin and proc.stdout
    stderr_task = asyncio.create_task(
        _stderr_tail(proc.stderr), name=f"sonicforge-worker-stderr-{proc.pid}"
    )
    try:
        proc.stdin.write((json.dumps(payload, ensure_ascii=False) + "\n").encode())
        await proc.stdin.drain()
        proc.stdin.close()
        await proc.stdin.wait_closed()
        final = None
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            if len(line) > 1024 * 1024:
                raise WorkerError("worker emitted an oversized protocol event")
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise WorkerError("worker emitted invalid JSON protocol data") from exc
            if event.get("type") == "progress":
                await progress(
                    float(event.get("progress", 0)),
                    str(event.get("message", ""))[:300],
                )
            elif event.get("type") == "result":
                final = event
            elif event.get("type") == "error":
                raise WorkerError(str(event.get("message", "worker failed"))[:1000])
        code = await proc.wait()
        stderr = await stderr_task
        _close_process_transport(proc)
        if code != 0 or final is None:
            raise WorkerError(
                stderr.decode(errors="replace")[-1000:] or f"worker exited {code}"
            )
    except asyncio.CancelledError:
        await _terminate(proc)
        stderr_task.cancel()
        await asyncio.gather(stderr_task, return_exceptions=True)
        _close_process_transport(proc)
        raise
    except BaseException:
        await _terminate(proc)
        stderr_task.cancel()
        await asyncio.gather(stderr_task, return_exceptions=True)
        _close_process_transport(proc)
        raise

    output = Path(final["output_path"]).resolve() if final.get("output_path") else None
    if output is not None:
        if not output.is_relative_to(work_root) or not output.is_file():
            raise WorkerError("worker output escaped its private work directory")
        if output.stat().st_size > MAX_WORKER_OUTPUT_BYTES:
            raise WorkerError("worker output exceeds the 1 GiB bound")
    result_payload = final.get("payload", {})
    if not isinstance(result_payload, dict):
        raise WorkerError("worker result payload must be an object")
    return WorkerResult(
        engine_id=str(final.get("engine_id", engine_id)),
        engine_version=final.get("engine_version"),
        model_id=final.get("model_id"),
        model_revision=final.get("model_revision"),
        model_license_id=final.get("model_license_id"),
        output_path=output,
        payload=result_payload,
    )
