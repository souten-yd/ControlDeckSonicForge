from __future__ import annotations

from typing import Any

from .db import Asset, Job, Provenance
from .prompting import normalize_sfx_prompt


def install_job_extensions(jobs) -> None:
    """Install additive durable-job preprocessing without changing JobManager's public API.

    The baseline JobManager is shared by speech/localization/audio/music. SFX
    prompt normalization is a SonicForge orchestration concern that must happen
    after the durable Job exists but before a worker/GPU lease is acquired.
    Keeping it as an installed extension avoids moving model semantics into the
    generic Host or duplicating the entire JobManager implementation.
    """
    if getattr(jobs, "_sonicforge_extensions_installed", False):
        return

    original_run = jobs._run
    original_persist = jobs._persist_audio_result

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
    jobs._persist_audio_result = persist_with_prompt_provenance
    jobs._sonicforge_extensions_installed = True
