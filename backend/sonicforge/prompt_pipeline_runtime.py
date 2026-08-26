from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from .jobs import HostedExecution
from .pipeline_runtime import PipelineRuntime, PipelineValue
from .pipeline_schema import PipelineStage
from .prompting import normalize_sfx_prompt
from .workers import WorkerError, WorkerResult, execute


class PromptAwarePipelineRuntime(PipelineRuntime):
    """Pipeline runtime with SonicForge-private SFX conditioning.

    Prompt normalization is deliberately performed before Resource Broker
    admission for the SFX worker. If ControlDeck AI is used, its inference and
    explicit release complete before the local audio stage can acquire a GPU.
    """

    async def _worker_stage(
        self,
        job_id: str,
        stage: PipelineStage,
        value: PipelineValue,
        execution: HostedExecution | None,
        stage_dir: Path,
        stage_index: int,
        total_stages: int,
    ) -> tuple[PipelineValue, dict[str, Any], WorkerResult, dict[str, Any]]:
        if stage.kind != "audio.sfx":
            return await super()._worker_stage(
                job_id,
                stage,
                value,
                execution,
                stage_dir,
                stage_index,
                total_stages,
            )
        request = self._worker_request(stage, value)

        start = 0.05 + (stage_index / max(total_stages, 1)) * 0.85
        span = 0.85 / max(total_stages, 1)

        async def progress(value_fraction: float, message: str) -> None:
            fraction = max(0.0, min(1.0, value_fraction))
            await self.jobs._set(
                job_id,
                progress=min(0.94, start + span * fraction),
                result={"message": f"Pipeline {stage.id}: {message}"},
            )

        request = await normalize_sfx_prompt(
            request,
            identity=execution.identity if execution is not None else None,
            host_client=self.host_client,
            progress=progress,
        )

        lease_renew: asyncio.Task | None = None
        needs_gpu = self.jobs._gpu_required(request)
        if needs_gpu and execution is None:
            raise WorkerError(
                f"Pipeline stage {stage.id} requires a ControlDeck Resource Broker lease"
            )
        if execution is not None:
            execution.resource_request_id = None
            execution.lease_id = None
            lease_renew = await self.jobs._acquire_resource(job_id, request, execution)

        try:
            async with self.jobs.process_lock:
                result = await execute(self.settings, request, stage_dir, progress)
        finally:
            if lease_renew is not None:
                lease_renew.cancel()
                await asyncio.gather(lease_renew, return_exceptions=True)
            if execution is not None:
                await self.jobs._release_resource(execution)
                execution.resource_request_id = None
                execution.lease_id = None

        trace: dict[str, Any] = {
            "id": stage.id,
            "kind": stage.kind,
            "state": "succeeded",
        }
        normalization = (result.payload or {}).get("prompt_normalization")
        if isinstance(normalization, dict):
            trace["prompt_conditioning"] = str(normalization.get("state") or "unknown")
        if stage.kind == "speech.asr":
            text = result.payload.get("text")
            if not isinstance(text, str):
                raise WorkerError("ASR pipeline stage returned no text")
            trace["output"] = "text"
            return PipelineValue(kind="text", text=text), trace, result, request
        if result.output_path is None:
            raise WorkerError(f"Pipeline stage {stage.id} returned no audio")
        trace["output"] = "audio"
        return PipelineValue(kind="audio", audio_path=result.output_path), trace, result, request
