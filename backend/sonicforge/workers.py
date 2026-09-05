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
        if routing_engine == "tts.gpt-sovits":
            py = _runtime_python(settings, "speech-gpt-sovits-rocm")
            if not py:
                raise WorkerError("GPT-SoVITS runtime is not installed")
            return (
                "tts.gpt-sovits",
                py,
                settings.repo_root / "worker_packs/gpt_sovits/worker.py",
            )
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


def _worker_environment(
    settings: Settings, engine_id: str | None = None
) -> dict[str, str]:
    ace_project_root = settings.cache_dir / "ace-step"
    env = {
        **os.environ,
        "PYTHONPATH": str(settings.repo_root),
        "HF_HOME": str(settings.models_dir / "huggingface"),
        "ACESTEP_PROJECT_ROOT": str(ace_project_root),
        "ACESTEP_CHECKPOINTS_DIR": str(settings.models_dir / "ace-step"),
        "XDG_CACHE_HOME": str(settings.cache_dir),
        "SONICFORGE_GPT_SOVITS_ROOT": str(settings.models_dir / "gpt-sovits"),
    }
    if engine_id in {"audio.stable-audio-3", "tts.gpt-sovits"}:
        # Provisioning downloads complete snapshots before atomic activation.
        # Generation is cache-only so metadata probes cannot turn an installed
        # pack into a network/authentication failure, and provisioning
        # credentials stay out of ordinary worker processes.
        env["HF_HUB_OFFLINE"] = "1"
        env["TRANSFORMERS_OFFLINE"] = "1"
    return env


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



# モデルを載せたままの worker。engine ごとに 1 本だけ持つ。
#
# worker は _MODELS / _PIPELINES で読み込んだモデルを持ち続ける作りなのに、
# 呼び出し側が要求ごとに stdin を閉じてプロセスを捨てていたため、毎回読み直して
# いた。実測（2026-09-05、Qwen3-TTS 0.6B CustomVoice）: 生成そのものは温まって
# 11〜18 秒だが、プロセスを起こし直すと 40 秒級になる。
#
# 常駐させるのは speech（TTS / ASR）だけにする。音楽と効果音は 1 回が数分かかる
# 上に大きく、抱えたままにする利点が無い。
_WARM_ENGINES = frozenset({"tts.qwen3", "tts.gpt-sovits", "asr.whisper"})
_warm: dict[tuple, asyncio.subprocess.Process] = {}


def _warm_key(engine_id: str, argv: list[str], env: dict[str, str]) -> tuple:
    return (engine_id, tuple(argv), json.dumps(sorted(env.items()), separators=(",", ":")))


async def retire_warm_workers() -> None:
    """常駐している worker を終わらせる。stdin を閉じれば main() の loop が抜ける。"""
    for key in list(_warm):
        proc = _warm.pop(key, None)
        if proc is None or proc.returncode is not None:
            continue
        try:
            if proc.stdin is not None and not proc.stdin.is_closing():
                proc.stdin.close()
            await asyncio.wait_for(proc.wait(), timeout=5)
        except (TimeoutError, asyncio.TimeoutError, ConnectionResetError, BrokenPipeError):
            await _terminate(proc)
        except Exception:  # noqa: BLE001 - 後片付けで job を落とさない
            await _terminate(proc)
        _close_process_transport(proc)


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
    env = _worker_environment(settings, engine_id)
    key = _warm_key(engine_id, argv, env)
    keep = engine_id in _WARM_ENGINES
    proc = _warm.get(key) if keep else None
    if proc is not None and proc.returncode is not None:
        _warm.pop(key, None)
        proc = None
    if proc is None:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            start_new_session=os.name != "nt",
        )
        if keep:
            _warm[key] = proc
    assert proc.stdin and proc.stdout
    stderr_task = asyncio.create_task(
        _stderr_tail(proc.stderr), name=f"sonicforge-worker-stderr-{proc.pid}"
    )
    try:
        proc.stdin.write((json.dumps(payload, ensure_ascii=False) + "\n").encode())
        await proc.stdin.drain()
        if not keep:
            # 使い捨ての engine は従来どおり stdin を閉じて EOF で終わらせる。
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
                # 失敗した worker は状態が分からないので使い回さない。
                _warm.pop(key, None)
                raise WorkerError(str(event.get("message", "worker failed"))[:1000])
            if keep and final is not None:
                # 常駐は EOF を待たない。1 要求 1 結果で切り上げ、次の要求へ残す。
                break
        if keep and final is not None:
            stderr_task.cancel()
            await asyncio.gather(stderr_task, return_exceptions=True)
            code, stderr = 0, b""
        else:
            _warm.pop(key, None)
            code = await proc.wait()
            stderr = await stderr_task
            _close_process_transport(proc)
        if code != 0 or final is None:
            raise WorkerError(
                stderr.decode(errors="replace")[-1000:] or f"worker exited {code}"
            )
    except asyncio.CancelledError:
        _warm.pop(key, None)
        await _terminate(proc)
        stderr_task.cancel()
        await asyncio.gather(stderr_task, return_exceptions=True)
        _close_process_transport(proc)
        raise
    except BaseException:
        _warm.pop(key, None)
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
