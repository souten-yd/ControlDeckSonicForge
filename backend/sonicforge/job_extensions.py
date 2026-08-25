from __future__ import annotations

import asyncio
import time
from typing import Any

from .db import Asset, Job, Provenance
from .host.client import HostApiError
from .prompting import normalize_sfx_prompt


def install_job_extensions(jobs) -> None:
    """Install additive durable-job orchestration without changing public APIs."""
    if getattr(jobs, "_sonicforge_extensions_installed", False):
        return

    original_run = jobs._run
    original_persist = jobs._persist_audio_result
    original_watch_host_cancel = jobs._watch_host_cancel

    async def run_with_preprocessing(job_id: str) -> None:
        with jobs.session_factory() as session:
            row = session.get(Job, job_id)
            request = dict(row.request or {}) if row is not None else {}
        if str(request.get("task") or "").startswith("audio."):
            execution = jobs.hosted.get(job_id)

            async def progress(value: float, message: str) -> None:
                await jobs._set(
                    job_id,
                    progress=max(0.0, min(0.05, value)),
                    result={"message": message},
                )

            normalized = await normalize_sfx_prompt(
                request,
                identity=execution.identity if execution is not None else None,
                host_client=jobs.host_client,
                progress=progress,
            )
            if normalized != request:
                with jobs.session_factory() as session:
                    row = session.get(Job, job_id)
                    if row is not None:
                        row.request = normalized
                        session.commit()
        await original_run(job_id)

    async def watch_host_with_credential_heartbeat(job_id: str, execution) -> None:
        """Keep the 10-minute bearer TTL internal to the Host/Add-on boundary.

        The active Host Job is the liveness anchor. While the durable execution
        remains active, refresh shortly before expiry. If SonicForge dies, the
        heartbeat dies too; no long-lived refresh credential exists. Older Hosts
        that do not implement job-bound refresh simply keep the previous behavior.
        """

        async def heartbeat() -> None:
            if jobs.host_client is None:
                return
            while True:
                await asyncio.sleep(30)
                if execution.identity.expires_at - int(time.time()) >= 120:
                    continue
                try:
                    execution.identity = await jobs.host_client.refresh_job_identity(
                        execution.identity, execution.host_job_id
                    )
                except HostApiError as exc:
                    if exc.status_code in {404, 401, 403, 409}:
                        return
                    continue

        task = asyncio.create_task(
            heartbeat(), name=f"sonicforge-job-credential-{job_id}"
        )
        try:
            await original_watch_host_cancel(job_id, execution)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    def persist_with_prompt_provenance(
        job_id: str,
        request: dict,
        result,
        *,
        metadata_extra: dict[str, Any] | None = None,
    ):
        asset_id, target, meta = original_persist(
            job_id,
            request,
            result,
            metadata_extra=metadata_extra,
        )
        normalization = (result.payload or {}).get("prompt_normalization")
        if isinstance(normalization, dict):
            with jobs.session_factory() as session:
                asset = session.get(Asset, asset_id)
                provenance = (
                    session.get(Provenance, asset.provenance_id)
                    if asset is not None
                    else None
                )
                if provenance is not None:
                    parameters = dict(provenance.parameters or {})
                    parameters["prompt_normalization"] = normalization
                    provenance.parameters = parameters
                    session.commit()
        return asset_id, target, meta

    jobs._run = run_with_preprocessing
    jobs._watch_host_cancel = watch_host_with_credential_heartbeat
    jobs._persist_audio_result = persist_with_prompt_provenance
    jobs._sonicforge_extensions_installed = True
