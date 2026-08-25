from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from .audio_delivery import AudioDeliveryService, AudioExportRequest, profile_document
from .host.client import HostApiError
from .jobs import HostedExecution


def create_delivery_router(base) -> APIRouter:
    router = APIRouter(prefix="/addon/v1", tags=["delivery"])
    service = AudioDeliveryService(base.jobs, base.session_factory, base.host_client)

    @router.get("/delivery/audio/profiles")
    async def audio_profiles():
        return {"profiles": profile_document()}

    @router.post("/assets/{asset_id:path}/export")
    async def export_audio(asset_id: str, body: AudioExportRequest, request: Request):
        hosted: HostedExecution | None = None
        if base._host_headers_present(request):
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
                    detail={"code": "capability_not_granted", "message": "jobs.write is required"},
                )
            created = await base.host_client.create_or_attach_job(
                identity, title=f"SonicForge audio export: {body.profile}"
            )
            host_job = created.get("job") if isinstance(created, dict) else None
            host_job_id = host_job.get("id") if isinstance(host_job, dict) else None
            if not isinstance(host_job_id, str) or not host_job_id:
                raise HTTPException(
                    status_code=502,
                    detail={"code": "invalid_host_response", "message": "ControlDeck did not return a Host Job"},
                )
            hosted = HostedExecution(identity=identity, host_job_id=host_job_id)
        if body.project_output_grant is not None and hosted is None:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "host_grant_required",
                    "message": "Project export requires ControlDeck Host execution",
                },
            )
        row = service.create(asset_id, body, hosted=hosted)
        return {
            "job_id": row.id,
            "host_job_id": hosted.host_job_id if hosted else None,
            "source_asset_id": asset_id,
            "profile": body.profile,
            "state": "queued",
        }

    return router
