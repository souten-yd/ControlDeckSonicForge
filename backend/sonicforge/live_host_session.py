from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

from .host.client import ControlDeckHostClient, HostApiError, HostIdentity
from .jobs import JobManager
from .workers import WorkerError


@dataclass
class _SessionLease:
    request_id: str
    lease_id: str
    renew_task: asyncio.Task | None = None


class LiveHostSession:
    """Own Host-side state whose lifetime matches one live voice/meeting socket.

    A live session may keep three independent pieces warm at once:
    - the Host-selected LLM through a short renewable residency hold;
    - SonicForge ASR through a normal Resource Broker lease;
    - SonicForge TTS through another Resource Broker lease.

    Nothing here is a permanent lock. ControlDeck LLM holds expire after their
    Host TTL when heartbeats stop, while Resource Broker leases expire when their
    renew loop stops. A killed SonicForge therefore converges back to ordinary
    Host policy without a cleanup callback from the dead process.
    """

    def __init__(
        self,
        *,
        host_client: ControlDeckHostClient,
        jobs: JobManager,
        identity: HostIdentity | None,
        title: str,
    ) -> None:
        self.host_client = host_client
        self.jobs = jobs
        self._identity = identity
        self.title = title
        self.host_job_id: str | None = None
        self.hold_id: str | None = None
        self.hold_interval = 30
        self._hold_task: asyncio.Task | None = None
        self._leases: dict[str, _SessionLease] = {}
        self._identity_lock = asyncio.Lock()
        self._closed = False

    @property
    def hosted(self) -> bool:
        return self._identity is not None

    async def identity(self) -> HostIdentity | None:
        async with self._identity_lock:
            return self._identity

    async def _set_identity(self, value: HostIdentity) -> None:
        async with self._identity_lock:
            self._identity = value

    async def start(self, *, keep_llm_warm: bool) -> None:
        identity = await self.identity()
        if identity is None:
            return
        if "jobs.write" in identity.granted_capabilities:
            created = await self.host_client.create_or_attach_job(identity, self.title)
            raw = created.get("job") if isinstance(created, dict) else None
            host_job_id = raw.get("id") if isinstance(raw, dict) else None
            if isinstance(host_job_id, str) and host_job_id:
                self.host_job_id = host_job_id
        if keep_llm_warm and "ai.inference" in identity.granted_capabilities:
            await self._start_llm_hold()

    async def _start_llm_hold(self) -> None:
        identity = await self.identity()
        if identity is None:
            return
        try:
            gateway = await self.host_client.gateway_capabilities(identity)
            ai = (gateway.get("control_plane") or {}).get("ai") or {}
            if ai.get("residency_hold") is not True:
                return
            value, refreshed = await self.host_client.ai_residency_create(identity)
            await self._set_identity(refreshed)
        except HostApiError as exc:
            # Older Hosts remain usable; residency is an optimization, not a
            # correctness requirement for a voice turn.
            if exc.status_code in {404, 409, 503}:
                return
            raise
        hold_id = value.get("hold_id")
        if value.get("held") is not True or not isinstance(hold_id, str):
            return
        self.hold_id = hold_id
        interval = value.get("heartbeat_interval_seconds")
        if isinstance(interval, int) and 5 <= interval <= 90:
            self.hold_interval = interval
        self._hold_task = asyncio.create_task(
            self._hold_heartbeat(), name=f"sonicforge-live-hold-{hold_id}"
        )

    async def _hold_heartbeat(self) -> None:
        while not self._closed and self.hold_id:
            await asyncio.sleep(self.hold_interval)
            identity = await self.identity()
            hold_id = self.hold_id
            if identity is None or hold_id is None:
                return
            try:
                value, refreshed = await self.host_client.ai_residency_renew(
                    identity, hold_id
                )
                await self._set_identity(refreshed)
                if value.get("held") is not True:
                    return
            except HostApiError as exc:
                if exc.status_code == 404:
                    # Event-loop stalls or temporary Host loss can let the short
                    # hold expire. Recreate it instead of silently running cold.
                    self.hold_id = None
                    try:
                        await self._start_llm_hold()
                    except HostApiError:
                        pass
                    return
                if exc.status_code in {401, 403, 409}:
                    return
                # Network/5xx failures are allowed to retry until the Host TTL
                # naturally expires; no permanent state can be stranded.

    async def acquire_worker_lease(self, key: str, request: dict[str, Any]) -> None:
        """Hold one SonicForge GPU worker residency for the live session."""
        if key in self._leases or not self.jobs._gpu_required(request):
            return
        identity = await self.identity()
        if identity is None:
            # Standalone trusted-local mode has no cross-application broker.
            return
        if self.host_job_id is None:
            raise WorkerError("Live GPU residency requires a ControlDeck Host Job")
        if "resources.acquire" not in identity.granted_capabilities:
            raise WorkerError(
                "ControlDeck resources.acquire is required for live GPU residency"
            )
        payload = self.jobs._resource_estimate(request, self.host_job_id)
        # Voice ASR/TTS are deliberately co-resident when capacity permits.
        # Broker accounting, rather than a hidden process convention, decides
        # whether both reservations fit the selected device(s).
        payload["compute_mode"] = "shared-safe"
        payload["priority"] = 30
        payload["class"] = "interactive"
        payload["estimated_runtime_sec"] = 3600
        payload["max_wait_sec"] = 300
        status = await self.host_client.request_resource(identity, payload)
        request_id = status.get("request_id")
        if not isinstance(request_id, str):
            raise WorkerError("ControlDeck did not return a live resource request ID")
        while True:
            state = status.get("state")
            if state == "granted":
                lease_id = status.get("lease_id")
                if not isinstance(lease_id, str):
                    raise WorkerError("ControlDeck granted live resource without lease ID")
                current = await self.identity()
                if current is None:
                    raise WorkerError("ControlDeck identity disappeared during admission")
                await self.host_client.lease_action(current, lease_id, "activate")
                lease = _SessionLease(request_id=request_id, lease_id=lease_id)
                self._leases[key] = lease
                lease.renew_task = asyncio.create_task(
                    self._renew_lease(key), name=f"sonicforge-live-lease-{key}"
                )
                return
            if state in {"rejected", "canceled", "expired"}:
                raise WorkerError(f"Live GPU admission ended: {state}")
            await asyncio.sleep(1.0)
            current = await self.identity()
            if current is None:
                raise WorkerError("ControlDeck identity disappeared during admission")
            status = await self.host_client.resource_status(current, request_id)

    async def _renew_lease(self, key: str) -> None:
        while not self._closed:
            lease = self._leases.get(key)
            if lease is None:
                return
            await asyncio.sleep(10)
            identity = await self.identity()
            if identity is None:
                return
            try:
                if identity.expires_at - int(time.time()) < 120:
                    refreshed = await self.host_client.refresh_lease_identity(
                        identity, lease.lease_id
                    )
                    await self._set_identity(refreshed)
                    identity = refreshed
                await self.host_client.lease_action(identity, lease.lease_id, "renew")
            except HostApiError:
                return

    async def release_worker_lease(self, key: str) -> None:
        lease = self._leases.pop(key, None)
        if lease is None:
            return
        if lease.renew_task is not None:
            lease.renew_task.cancel()
            await asyncio.gather(lease.renew_task, return_exceptions=True)
        identity = await self.identity()
        if identity is None:
            return
        try:
            await self.host_client.lease_action(identity, lease.lease_id, "release")
        except HostApiError:
            pass

    async def close(self, *, failed: bool = False) -> None:
        if self._closed:
            return
        self._closed = True
        if self._hold_task is not None:
            self._hold_task.cancel()
            await asyncio.gather(self._hold_task, return_exceptions=True)
            self._hold_task = None
        for key in list(self._leases):
            await self.release_worker_lease(key)
        identity = await self.identity()
        if identity is not None and self.hold_id:
            try:
                await self.host_client.ai_residency_release(identity, self.hold_id)
            except HostApiError:
                pass
        self.hold_id = None
        if identity is not None and self.host_job_id:
            try:
                await self.host_client.update_job(
                    identity,
                    self.host_job_id,
                    {
                        "phase": "failed" if failed else "complete",
                        "progress": {"completed": 1000, "total": 1000},
                        "status": "failed" if failed else "succeeded",
                        **(
                            {"error": "Live session ended with an error"}
                            if failed
                            else {"result": {"message": "Live session complete"}}
                        ),
                    },
                )
            except HostApiError:
                pass
