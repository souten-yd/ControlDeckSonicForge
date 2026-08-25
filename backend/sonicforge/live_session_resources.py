from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

from .host.client import ControlDeckHostClient, HostApiError, HostIdentity
from .host.residency import AiResidencyHold, create_ai_hold, release_ai_hold, renew_ai_hold
from .jobs import HostedExecution, JobManager
from .persistent_workers import PersistentSpeechWorkers
from .pipeline_schema import PipelineStage
from .workers import WorkerError


@dataclass
class SessionLease:
    kind: str
    execution: HostedExecution
    device_id: str | None
    renew_task: asyncio.Task | None


class LiveSessionResources:
    """Resources that intentionally survive across multiple conversational turns."""

    def __init__(
        self,
        *,
        jobs: JobManager,
        host_client: ControlDeckHostClient,
        identity: HostIdentity | None,
        stages: list[PipelineStage],
        label: str,
    ) -> None:
        self.jobs = jobs
        self.host_client = host_client
        self.identity = identity
        self.stages = stages
        self.label = label
        self.host_job_id: str | None = None
        self.leases: list[SessionLease] = []
        self.ai_hold: AiResidencyHold | None = None
        self.ai_heartbeat: asyncio.Task | None = None
        self.workers: PersistentSpeechWorkers | None = None
        self._closed = False

    @property
    def has_asr(self) -> bool:
        return any(stage.kind == "speech.asr" for stage in self.stages)

    @property
    def has_tts(self) -> bool:
        return any(stage.kind == "speech.tts" for stage in self.stages)

    @property
    def has_host_ai(self) -> bool:
        return any(stage.kind == "host.ai.text" for stage in self.stages)

    async def start(self) -> None:
        if self.identity is not None and self.has_host_ai:
            await self._start_ai_hold()

        asr_device: str | None = None
        tts_device: str | None = None
        if self.identity is not None and (self.has_asr or self.has_tts):
            await self._ensure_host_job()
            if self.has_asr:
                asr_device = await self._acquire_speech_lease("asr")
            if self.has_tts:
                tts_device = await self._acquire_speech_lease("tts")

        if self.has_asr or self.has_tts:
            self.workers = PersistentSpeechWorkers(
                self.jobs.settings,
                asr_device=asr_device,
                tts_device=tts_device,
            )
            # Start processes now, but model loading remains lazy until the first
            # request because exact language/voice model selection is request-specific.
            if self.has_asr:
                await self.workers.asr.start()
            if self.has_tts:
                await self.workers.tts.start()

    async def _ensure_host_job(self) -> None:
        if self.identity is None or self.host_job_id is not None:
            return
        if "jobs.write" not in self.identity.granted_capabilities:
            raise WorkerError("jobs.write is required for hosted live session residency")
        created = await self.host_client.create_or_attach_job(
            self.identity,
            title=f"SonicForge live session: {self.label}"[:300],
        )
        host_job = created.get("job") if isinstance(created, dict) else None
        host_job_id = host_job.get("id") if isinstance(host_job, dict) else None
        if not isinstance(host_job_id, str) or not host_job_id:
            raise WorkerError("ControlDeck did not return a live session Host Job")
        self.host_job_id = host_job_id

    def _request_for(self, kind: str) -> dict[str, Any]:
        if kind == "asr":
            return {
                "task": "speech.asr.transcribe",
                "content_language": "auto",
                "routing": {"engine": None, "model": None, "device": "auto"},
            }
        return {
            "task": "speech.tts.synthesize",
            "content_language": "auto",
            "routing": {"engine": None, "model": None, "device": "auto"},
        }

    async def _acquire_speech_lease(self, kind: str) -> str | None:
        assert self.identity is not None and self.host_job_id is not None
        request = self._request_for(kind)
        if not self.jobs._gpu_required(request):
            return None
        if "resources.acquire" not in self.identity.granted_capabilities:
            raise WorkerError("resources.acquire is required for GPU live speech")
        estimate = self.jobs._resource_estimate(request, self.host_job_id)
        peak = int((estimate.get("vram") or {}).get("execution_peak_bytes") or 0)
        estimate["vram"]["resident_bytes"] = peak
        estimate["compute_mode"] = "shared-safe"
        estimate["priority"] = 30
        estimate["class"] = "interactive"
        estimate["estimated_runtime_sec"] = 3600
        estimate["on_insufficient"] = "fail_fast"
        status = await self.host_client.request_resource(self.identity, estimate)
        if status.get("state") != "granted":
            raise WorkerError(
                f"Live {kind.upper()} cannot coexist in current VRAM: {status.get('reason') or status.get('state')}"
            )
        lease_id = status.get("lease_id")
        device_id = status.get("device_id")
        if not isinstance(lease_id, str):
            raise WorkerError("ControlDeck granted live speech without a lease ID")
        execution = HostedExecution(
            identity=self.identity,
            host_job_id=self.host_job_id,
            resource_request_id=status.get("request_id") if isinstance(status.get("request_id"), str) else None,
            lease_id=lease_id,
        )
        await self.host_client.lease_action(execution.identity, lease_id, "activate")
        renew = asyncio.create_task(
            self.jobs._renew_lease(execution),
            name=f"sonicforge-live-{kind}-lease-{lease_id}",
        )
        self.leases.append(SessionLease(kind, execution, device_id if isinstance(device_id, str) else None, renew))
        return device_id if isinstance(device_id, str) else None

    async def _start_ai_hold(self) -> None:
        assert self.identity is not None
        try:
            self.ai_hold = await create_ai_hold(self.host_client, self.identity)
        except HostApiError as exc:
            if exc.status_code in {404, 409}:
                self.ai_hold = None
                return
            raise
        if not self.ai_hold.held or not self.ai_hold.hold_id:
            return
        self.ai_heartbeat = asyncio.create_task(
            self._ai_heartbeat_loop(),
            name=f"sonicforge-ai-hold-{self.ai_hold.hold_id}",
        )

    async def _ai_heartbeat_loop(self) -> None:
        assert self.identity is not None
        while not self._closed and self.ai_hold and self.ai_hold.held and self.ai_hold.hold_id:
            interval = max(5, self.ai_hold.heartbeat_interval_seconds or 30)
            await asyncio.sleep(interval)
            if self._closed:
                return
            try:
                self.ai_hold = await renew_ai_hold(
                    self.host_client,
                    self.identity,
                    self.ai_hold.hold_id,
                )
            except HostApiError as exc:
                if exc.status_code in {401, 403, 404, 409, 503}:
                    # Do not convert a temporary Host failure into a process-wide
                    # failure. The Host TTL makes stale holds self-cleaning.
                    return
                raise

    async def close(self, *, status: str = "succeeded") -> None:
        if self._closed:
            return
        self._closed = True
        if self.ai_heartbeat is not None:
            self.ai_heartbeat.cancel()
            await asyncio.gather(self.ai_heartbeat, return_exceptions=True)
            self.ai_heartbeat = None
        if self.ai_hold and self.ai_hold.held and self.ai_hold.hold_id and self.identity is not None:
            try:
                await release_ai_hold(self.host_client, self.identity, self.ai_hold.hold_id)
            except HostApiError:
                pass
        self.ai_hold = None

        if self.workers is not None:
            await self.workers.close()
            self.workers = None

        for lease in reversed(self.leases):
            if lease.renew_task is not None:
                lease.renew_task.cancel()
                await asyncio.gather(lease.renew_task, return_exceptions=True)
            try:
                await self.jobs._release_resource(lease.execution)
            except HostApiError:
                pass
        self.leases.clear()

        if self.identity is not None and self.host_job_id is not None:
            try:
                await self.host_client.update_job(
                    self.identity,
                    self.host_job_id,
                    {
                        "phase": "complete" if status == "succeeded" else status,
                        "status": status if status in {"succeeded", "failed", "canceled"} else "succeeded",
                        "result": {"message": "Live session closed"},
                    },
                )
            except HostApiError:
                pass
        self.host_job_id = None
