from __future__ import annotations

import asyncio
import json
import os
import signal
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

from .config import Settings
from .live_host_session import LiveHostSession
from .workers import (
    MAX_STDERR_TAIL_BYTES,
    MAX_WORKER_OUTPUT_BYTES,
    WorkerError,
    WorkerResult,
    route,
)

ProgressCallback = Callable[[float, str], Awaitable[None]]


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


@dataclass
class _PersistentWorker:
    key: str
    proc: asyncio.subprocess.Process
    stderr_task: asyncio.Task
    lock: asyncio.Lock


class LiveWorkerPool:
    """Persistent ASR/TTS workers scoped to one live/meeting session.

    When the Broker says ASR+TTS cannot coexist, the pool explicitly evicts the
    other warm worker and retries. This preserves correctness on smaller VRAM
    devices while keeping both resident on machines where they actually fit.
    """

    def __init__(
        self,
        *,
        settings: Settings,
        host_session: LiveHostSession,
    ) -> None:
        self.settings = settings
        self.host_session = host_session
        self._workers: dict[str, _PersistentWorker] = {}
        self._closed = False

    @staticmethod
    def _key(request: dict) -> str:
        task = request.get("task")
        if task == "speech.asr.transcribe":
            return "asr"
        if task == "speech.tts.synthesize":
            return "tts"
        raise WorkerError("persistent live pool only supports ASR/TTS")

    def _live_script(self, key: str, engine_id: str) -> Path:
        if engine_id == "fake":
            return self.settings.repo_root / "worker_packs/fake/live_worker.py"
        if key == "asr":
            return self.settings.repo_root / "worker_packs/whisper/live_worker.py"
        if key == "tts":
            return self.settings.repo_root / "worker_packs/qwen_tts/live_worker.py"
        raise WorkerError(f"unsupported live worker key: {key}")

    async def _evict(self, key: str) -> None:
        worker = self._workers.pop(key, None)
        if worker is not None:
            await _terminate(worker.proc)
            worker.stderr_task.cancel()
            await asyncio.gather(worker.stderr_task, return_exceptions=True)
        await self.host_session.release_worker_lease(key)

    async def _admit(self, key: str, request: dict) -> None:
        try:
            await self.host_session.acquire_worker_lease(
                key, request, fail_fast=bool(self._workers)
            )
            return
        except WorkerError as exc:
            if "admission ended: rejected" not in str(exc) or not self._workers:
                raise
        # The held peer is the likely blocker. Stop it before releasing its
        # reservation, then retry normally. Never release a lease while its model
        # process still owns VRAM.
        for other_key in list(self._workers):
            if other_key != key:
                await self._evict(other_key)
        await self.host_session.acquire_worker_lease(key, request, fail_fast=False)

    async def _start(self, key: str, request: dict) -> _PersistentWorker:
        if self._closed:
            raise WorkerError("live worker pool is closed")
        existing = self._workers.get(key)
        if existing is not None and existing.proc.returncode is None:
            return existing

        await self._admit(key, request)
        engine_id, python, _script = route(
            self.settings,
            request["task"],
            request.get("content_language", "auto"),
            request.get("routing", {}).get("engine"),
        )
        live_script = self._live_script(key, engine_id)
        if not live_script.is_file():
            await self.host_session.release_worker_lease(key)
            raise WorkerError(f"persistent live worker is missing: {live_script.name}")
        env = {
            **os.environ,
            "PYTHONPATH": str(self.settings.repo_root),
            "HF_HOME": str(self.settings.models_dir / "huggingface"),
        }
        try:
            proc = await asyncio.create_subprocess_exec(
                str(python),
                str(live_script),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                start_new_session=os.name != "nt",
            )
        except BaseException:
            await self.host_session.release_worker_lease(key)
            raise
        assert proc.stdin is not None and proc.stdout is not None
        worker = _PersistentWorker(
            key=key,
            proc=proc,
            stderr_task=asyncio.create_task(
                _stderr_tail(proc.stderr),
                name=f"sonicforge-live-worker-stderr-{proc.pid}",
            ),
            lock=asyncio.Lock(),
        )
        self._workers[key] = worker
        return worker

    async def execute(
        self,
        request: dict,
        work_dir: Path,
        progress: ProgressCallback,
    ) -> WorkerResult:
        key = self._key(request)
        worker = await self._start(key, request)
        async with worker.lock:
            if worker.proc.returncode is not None:
                await self._evict(key)
                worker = await self._start(key, request)
            assert worker.proc.stdin is not None and worker.proc.stdout is not None
            work_dir.mkdir(parents=True, exist_ok=True)
            work_root = work_dir.resolve()
            request_id = f"live:{uuid.uuid4().hex}"
            envelope = {
                "request_id": request_id,
                "request": request,
                "work_dir": str(work_root),
            }
            worker.proc.stdin.write(
                (json.dumps(envelope, ensure_ascii=False) + "\n").encode()
            )
            await worker.proc.stdin.drain()
            final: dict | None = None
            while True:
                line = await worker.proc.stdout.readline()
                if not line:
                    stderr = await worker.stderr_task
                    self._workers.pop(key, None)
                    await self.host_session.release_worker_lease(key)
                    raise WorkerError(
                        stderr.decode(errors="replace")[-1000:]
                        or "persistent live worker exited unexpectedly"
                    )
                if len(line) > 1024 * 1024:
                    raise WorkerError("persistent live worker emitted an oversized event")
                try:
                    event = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise WorkerError(
                        "persistent live worker emitted invalid JSON"
                    ) from exc
                if event.get("request_id") != request_id:
                    raise WorkerError("persistent live worker response correlation failed")
                kind = event.get("type")
                if kind == "progress":
                    await progress(
                        float(event.get("progress", 0)),
                        str(event.get("message", ""))[:300],
                    )
                elif kind == "result":
                    final = event
                    break
                elif kind == "error":
                    raise WorkerError(
                        str(event.get("message", "live worker failed"))[:1000]
                    )

            output = (
                Path(final["output_path"]).resolve()
                if final.get("output_path")
                else None
            )
            if output is not None:
                if not output.is_relative_to(work_root) or not output.is_file():
                    raise WorkerError(
                        "persistent live worker output escaped work directory"
                    )
                if output.stat().st_size > MAX_WORKER_OUTPUT_BYTES:
                    raise WorkerError("persistent live worker output exceeds 1 GiB")
            payload = final.get("payload", {})
            if not isinstance(payload, dict):
                raise WorkerError("persistent live worker payload must be an object")
            return WorkerResult(
                engine_id=str(final.get("engine_id") or key),
                engine_version=final.get("engine_version"),
                model_id=final.get("model_id"),
                model_revision=final.get("model_revision"),
                model_license_id=final.get("model_license_id"),
                output_path=output,
                payload=payload,
            )

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for key in list(self._workers):
            await self._evict(key)
