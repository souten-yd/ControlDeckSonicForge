from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from .host.client import HostApiError
from .host.devices import create_device_pairing


class PairingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relay_id: str = Field(default="voice", pattern=r"^[a-z][a-z0-9._-]{0,127}$")
    device_label: str | None = Field(default=None, max_length=80)


def create_device_router(base) -> APIRouter:
    router = APIRouter(prefix="/addon/v1/devices", tags=["devices"])

    @router.post("/pairings", status_code=201)
    async def create_pairing(body: PairingRequest, request: Request):
        if not base._host_headers_present(request):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "control_deck_required",
                    "message": "Device pairing must be initiated through ControlDeck",
                },
            )
        try:
            identity = await base.host_client.authenticate(request.headers)
            return await create_device_pairing(
                base.host_client,
                identity,
                relay_id=body.relay_id,
                device_label=body.device_label,
            )
        except HostApiError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail={"code": exc.code, "message": str(exc)},
            ) from exc

    return router
