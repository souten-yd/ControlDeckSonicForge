from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Awaitable, Callable

from .config import Settings
from .workers import (
    MAX_STDERR_TAIL_BYTES,
    MAX_WORKER_OUTPUT_BYTES,
    WorkerError,
    WorkerResult,
    _close_process_transport,
    _terminate,
    route,
)

ProgressCallback = Callable[[float, str], Awaitable[None]]


def _visible_device_env(device_id: str | None) -> dict[str, str]:
    if not device_id or not device_id.startswith("gpu"):
        return {}
    suffix = device_id.removeprefix("gpu")
    if not suffix.isdigit():
        return {}
    return {
        "HIP_VISIBLE_DEVICES": suffix,
        "ROCR_VISIBLE_DEVICES": suffix,
        "CUDA_VISIBLE_DEVICES": suffix,
    }


class PersistentWorker:
    """Serialize requests through one long-lived worker process.

    Worker scripts keep heavyweight model objects in process-local caches. The
    supervisor intentionally runs one request at a time per worker so the line
    protocol does not need request IDs yet. Cancellation kills the process and
    therefore invalidates the warm cache rather than risking a stale result.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        task: str,
        language: str = "auto",
        routing_engine: str | None = None,
        device_id: str | None = None,
    ) -> None:
        self.settings = settings
        self.task = task
        self.language = language
        self.routing_engine = routing_engine
        self.device_id = device_id
        self._proc: asyncio.subprocess.Process | None = None
        self._stderr_task: asyncio.Task[bytes] | None = None
        self._lock = asyncio.Lock()
        self.start_count = 0
        self.request_count = 0

    async def _read_stderr(self, stream: asyncio.StreamReader | None) -> bytes:
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

    async def start(self) -> None:
        if self._proc is not None and self._proc.returncode is None:
            return
        engine_id, python, script = route(
            self.settings,
            self.task,
            self.language,
            self.routing_engine,
        )
        argv = [str(python), str(script)]
        if engine_id == "external":
            raise WorkerError("external command workers are not persistent-session capable")
        env = {
            **os.environ,
            "PYTHONPATH": str(self.settings.repo_root),
            "HF_HOME": str(self.settings.models_dir / "huggingface"),
            "SONICFORGE_PERSISTENT_WORKER": "1",
            **_visible_device_env(self.device_id),
        }
        self._proc = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            start_new_session=os.name != "nt",
        )
        assert self._proc.stdin is not None and self._proc.stdout is not None
        self._stderr_task = asyncio.create_task(
            self._read_stderr(self._proc.stderr),
            name=f"sonicforge-persistent-stderr-{self._proc.pid}",
        )
        self.start_count += 1

    async def execute(
        self,
        request: dict,
        work_dir: Path,
        progress: ProgressCallback,
    ) -> WorkerResult:
        async with self._lock:
            await self.start()
            assert self._proc is not None
            assert self._proc.stdin is not None and self._proc.stdout is not None
            proc = self._proc
            work_dir.mkdir(parents=True, exist_ok=True)
            work_root = work_dir.resolve()
            payload = {"request": request, "work_dir": str(work_root)}
            try:
                proc.stdin.write((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
                await proc.stdin.drain()
                final: dict | None = None
                while True:
                    line = await proc.stdout.readline()
                    if not line:
                        stderr = await self._stderr_snapshot()
                        raise WorkerError(
                            stderr.decode(errors="replace")[-1000:]
                            or f"persistent worker exited {proc.returncode}"
                        )
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
                        break
                    elif event.get("type") == "error":
                        raise WorkerError(str(event.get("message", "worker failed"))[:1000])
                self.request_count += 1
                return self._result(final, work_root)
            except asyncio.CancelledError:
                await self.close(force=True)
                raise
            except (BrokenPipeError, ConnectionResetError):
                await self.close(force=True)
                raise WorkerError("persistent worker connection was lost")

    def _result(self, final: dict, work_root: Path) -> WorkerResult:
        output = Path(final["output_path"]).resolve() if final.get("output_path") else None
        if output is not None:
            if not output.is_relative_to(work_root) or not output.is_file():
                raise WorkerError("worker output escaped its private work directory")
            if output.stat().st_size > MAX_WORKER_OUTPUT_BYTES:
                raise WorkerError("worker output exceeds the 1 GiB bound")
        payload = final.get("payload", {})
        if not isinstance(payload, dict):
            raise WorkerError("worker result payload must be an object")
        return WorkerResult(
            engine_id=str(final.get("engine_id") or "persistent"),
            engine_version=final.get("engine_version"),
            model_id=final.get("model_id"),
            model_revision=final.get("model_revision"),
            model_license_id=final.get("model_license_id"),
            output_path=output,
            payload=payload,
        )

    async def _stderr_snapshot(self) -> bytes:
        if self._stderr_task is None:
            return b""
        if self._stderr_task.done():
            try:
                return self._stderr_task.result()
            except Exception:
                return b""
        return b""

    async def close(self, *, force: bool = False) -> None:
        proc = self._proc
        self._proc = None
        stderr_task = self._stderr_task
        self._stderr_task = None
        if proc is None:
            return
        if not force and proc.returncode is None and proc.stdin is not None:
            try:
                proc.stdin.write(b'{"type":"shutdown"}\n')
                await proc.stdin.drain()
                proc.stdin.close()
                await proc.stdin.wait_closed()
                await asyncio.wait_for(proc.wait(), timeout=3)
            except (BrokenPipeError, ConnectionResetError, TimeoutError):
                await _terminate(proc)
        elif proc.returncode is None:
            await _terminate(proc)
        if proc.stdout is not None:
            await proc.stdout.read()
        if stderr_task is not None:
            await asyncio.gather(stderr_task, return_exceptions=True)
        _close_process_transport(proc)


class PersistentSpeechWorkers:
    def __init__(
        self,
        settings: Settings,
        *,
        asr_device: str | None = None,
        tts_device: str | None = None,
        asr_engine: str | None = None,
        tts_engine: str | None = None,
    ) -> None:
        self.asr = PersistentWorker(
            settings,
            task="speech.asr.transcribe",
            routing_engine=asr_engine,
            device_id=asr_device,
        )
        self.tts = PersistentWorker(
            settings,
            task="speech.tts.synthesize",
            routing_engine=tts_engine,
            device_id=tts_device,
        )

    async def close(self) -> None:
        await asyncio.gather(self.asr.close(), self.tts.close(), return_exceptions=True)
