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
    """Own Host-side state whose lifetime matches one live voice/meeting socket."""

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
        self._job_heartbeat_task: asyncio.Task | None = None
        self._leases: dict[str, _SessionLease] = {}
        self._identity_lock = asyncio.Lock()
        self._closed = False
        self._keep_llm_warm = False

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
        self._keep_llm_warm = keep_llm_warm
        identity = await self.identity()
        if identity is None:
            return
        if "jobs.write" in identity.granted_capabilities:
            created = await self.host_client.create_or_attach_job(identity, self.title)
            identity = await self.host_client.identity_from_job_response(identity, created)
            await self._set_identity(identity)
            raw = created.get("job") if isinstance(created, dict) else None
            host_job_id = raw.get("id") if isinstance(raw, dict) else None
            if isinstance(host_job_id, str) and host_job_id:
                self.host_job_id = host_job_id
                self._job_heartbeat_task = asyncio.create_task(
                    self._job_credential_heartbeat(),
                    name=f"sonicforge-live-job-credential-{host_job_id}",
                )

    async def ensure_llm_hold(self) -> None:
        identity = await self.identity()
        if (
            not self._keep_llm_warm
            or self.hold_id is not None
            or identity is None
            or "ai.inference" not in identity.granted_capabilities
        ):
            return
        await self._start_llm_hold()

    async def release_llm_hold(self, *, stop_runtime: bool = False) -> None:
        task = self._hold_task
        self._hold_task = None
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        identity = await self.identity()
        hold_id = self.hold_id
        self.hold_id = None
        if identity is not None and hold_id is not None:
            try:
                await self.host_client.ai_residency_release(identity, hold_id)
            except HostApiError:
                pass
        if stop_runtime and identity is not None:
            try:
                await self.host_client.ai_release(identity)
            except HostApiError as exc:
                if exc.status_code not in {404, 409, 503}:
                    raise

    async def _job_credential_heartbeat(self) -> None:
        while not self._closed and self.host_job_id:
            await asyncio.sleep(30)
            identity = await self.identity()
            if identity is None or self.host_job_id is None:
                return
            if identity.expires_at - int(time.time()) >= 120:
                continue
            try:
                refreshed = await self.host_client.refresh_job_identity(
                    identity, self.host_job_id
                )
                await self._set_identity(refreshed)
            except HostApiError as exc:
                if exc.status_code in {404, 401, 403, 409}:
                    return

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
                    self.hold_id = None
                    try:
                        await self._start_llm_hold()
                    except HostApiError:
                        pass
                    return
                if exc.status_code in {401, 403, 409}:
                    return

    async def acquire_worker_lease(
        self,
        key: str,
        request: dict[str, Any],
        *,
        fail_fast: bool = False,
    ) -> None:
        """Hold one SonicForge GPU worker residency for the live session."""
        if key in self._leases or not self.jobs._gpu_required(request):
            return
        identity = await self.identity()
        if identity is None:
            return
        if self.host_job_id is None:
            raise WorkerError("Live GPU residency requires a ControlDeck Host Job")
        if "resources.acquire" not in identity.granted_capabilities:
            raise WorkerError(
                "ControlDeck resources.acquire is required for live GPU residency"
            )
        payload = self.jobs._resource_estimate(request, self.host_job_id)
        payload["compute_mode"] = "shared-safe"
        payload["priority"] = 30
        payload["class"] = "interactive"
        payload["estimated_runtime_sec"] = 3600
        payload["max_wait_sec"] = 300
        payload["on_insufficient"] = "fail_fast" if fail_fast else "queue"
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
        for task_name in ("_hold_task", "_job_heartbeat_task"):
            task = getattr(self, task_name)
            if task is not None:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                setattr(self, task_name, None)
        for key in list(self._leases):
            await self.release_worker_lease(key)
        identity = await self.identity()
        await self.release_llm_hold()
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
