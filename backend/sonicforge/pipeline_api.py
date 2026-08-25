from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from .host.client import HostApiError
from .jobs import HostedExecution
from .pipeline_schema import PipelineRequest, compile_pipeline
from .prompt_pipeline_runtime import PromptAwarePipelineRuntime


def create_pipeline_router(base) -> APIRouter:
    router = APIRouter(prefix="/addon/v1", tags=["pipeline"])
    runtime = PromptAwarePipelineRuntime(
        jobs=base.jobs,
        session_factory=base.session_factory,
        host_client=base.host_client,
    )

    async def hosted_execution(request: Request, title: str) -> HostedExecution | None:
        if not base._host_headers_present(request):
            return None
        try:
            identity = await base.host_client.authenticate(request.headers)
        except HostApiError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail={"code": exc.code, "message": str(exc)},
            ) from exc
        if "jobs.write" not in identity.granted_capabilities:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "capability_not_granted",
                    "message": "jobs.write is required for hosted pipeline execution",
                },
            )
        created = await base.host_client.create_or_attach_job(identity, title=title)
        host_job = created.get("job") if isinstance(created, dict) else None
        host_job_id = host_job.get("id") if isinstance(host_job, dict) else None
        if not isinstance(host_job_id, str) or not host_job_id:
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "invalid_host_response",
                    "message": "ControlDeck did not return a Host Job",
                },
            )
        return HostedExecution(identity=identity, host_job_id=host_job_id)

    async def submit(body: PipelineRequest, request: Request) -> dict:
        compiled = compile_pipeline(body)
        execution = await hosted_execution(
            request,
            title=f"SonicForge pipeline: {body.pipeline or 'custom'}",
        )
        if any(stage.kind == "host.ai.text" for stage in body.stages[compiled.start_index : compiled.stop_index + 1]) and execution is None:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "host_ai_required",
                    "message": "This pipeline requires the ControlDeck AI router",
                },
            )
        if body.input.kind == "audio_grant" and execution is None:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "host_grant_required",
                    "message": "audio_grant input requires ControlDeck Host execution",
                },
            )
        if body.delivery.mode == "project" and execution is None:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "host_grant_required",
                    "message": "project delivery requires ControlDeck Host execution",
                },
            )
        row = runtime.create(body, hosted=execution)
        return {
            "job_id": row.id,
            "host_job_id": execution.host_job_id if execution else None,
            "pipeline": body.pipeline,
            "start_at": body.start_at,
            "stop_after": body.stop_after,
            "output_type": compiled.output_type,
            "state": "queued",
        }

    @router.post("/pipelines/compile")
    async def compile_only(body: PipelineRequest):
        compiled = compile_pipeline(body)
        return {
            "valid": True,
            "start_index": compiled.start_index,
            "stop_index": compiled.stop_index,
            "input_type": compiled.input_type,
            "output_type": compiled.output_type,
            "stage_ids": list(compiled.stage_ids),
        }

    @router.post("/pipelines")
    async def create_pipeline(body: PipelineRequest, request: Request):
        return await submit(body, request)

    @router.post("/agent/pipeline")
    async def agent_pipeline(body: PipelineRequest, request: Request):
        return await submit(body, request)

    return router
