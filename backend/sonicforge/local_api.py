from __future__ import annotations

import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from .schemas import OutputSpec, Quality, RoutingSpec, TaskRequest


class LocalTtsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=100_000)
    language: Literal["auto", "ja", "en"] = "auto"
    voice_id: str | None = Field(default=None, max_length=128)
    profile: str = Field(default="default", min_length=1, max_length=120)
    quality: Quality = "balanced"
    output: OutputSpec = Field(default_factory=OutputSpec)
    routing: RoutingSpec = Field(default_factory=RoutingSpec)
    seed: int | None = None


class LocalGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1, max_length=100_000)
    language: Literal["auto", "ja", "en"] = "auto"
    profile: str = Field(default="default", min_length=1, max_length=120)
    quality: Quality = "balanced"
    output: OutputSpec = Field(default_factory=OutputSpec)
    routing: RoutingSpec = Field(default_factory=RoutingSpec)
    seed: int | None = None


def _suffix_for_content_type(content_type: str | None) -> str:
    value = (content_type or "").split(";", 1)[0].strip().lower()
    return {
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/flac": ".flac",
        "audio/mpeg": ".mp3",
        "audio/mp3": ".mp3",
        "audio/ogg": ".ogg",
        "audio/webm": ".webm",
        "audio/mp4": ".m4a",
        "video/mp4": ".m4a",
    }.get(value, ".bin")


async def _stream_request_to_file(request: Request, target: Path, *, max_bytes: int = 0) -> int:
    target.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    try:
        with target.open("wb") as output:
            async for chunk in request.stream():
                if not chunk:
                    continue
                written += len(chunk)
                if max_bytes > 0 and written > max_bytes:
                    raise HTTPException(status_code=413, detail="local audio upload exceeds configured limit")
                output.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    if written == 0:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="audio body is empty")
    return written


def create_local_router(base) -> APIRouter:
    """Trusted-local API.

    These endpoints deliberately do not require ControlDeck authentication.
    ControlDeck-only operations (grants, project writes, Host Jobs) keep their
    existing authenticated boundary.
    """

    router = APIRouter(prefix="/local/v1", tags=["local"])

    @router.get("/capabilities")
    async def local_capabilities():
        value = await base.capabilities()
        return {
            **value,
            "access": "unauthenticated-local",
            "endpoints": {
                "asr": "/local/v1/asr",
                "tts": "/local/v1/tts",
                "sfx": "/local/v1/sfx",
                "music": "/local/v1/music",
                "live": "/addon/v1/live/ws",
            },
        }

    @router.post("/asr")
    async def local_asr(
        request: Request,
        language: Literal["auto", "ja", "en"] = "auto",
        quality: Quality = "balanced",
    ):
        suffix = _suffix_for_content_type(request.headers.get("content-type"))
        target = base.settings.data_dir / "tmp" / "local-upload" / f"{uuid.uuid4().hex}{suffix}"
        await _stream_request_to_file(
            request,
            target,
            max_bytes=getattr(base.settings, "local_max_upload_bytes", 0),
        )
        payload = TaskRequest(
            task="speech.asr.transcribe",
            input={},
            quality=quality,
            content_language=language,
        ).model_dump(mode="json")
        payload["input"]["_internal_staged_input"] = str(target)
        try:
            job = base.jobs.create(payload)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        return {"job_id": job.id, "state": job.state}

    @router.post("/tts")
    async def local_tts(body: LocalTtsRequest):
        input_value: dict[str, object] = {"text": body.text}
        if body.voice_id:
            input_value["voice_id"] = body.voice_id
        request = TaskRequest(
            task="speech.tts.synthesize",
            input=input_value,
            profile=body.profile,
            quality=body.quality,
            content_language=body.language,
            output=body.output,
            routing=body.routing,
            seed=body.seed,
        )
        job = base.jobs.create(request.model_dump(mode="json"))
        return {"job_id": job.id, "state": job.state}

    async def generate(body: LocalGenerateRequest, task: str):
        request = TaskRequest(
            task=task,
            input={"prompt": body.prompt},
            profile=body.profile,
            quality=body.quality,
            content_language=body.language,
            output=body.output,
            routing=body.routing,
            seed=body.seed,
        )
        job = base.jobs.create(request.model_dump(mode="json"))
        return {"job_id": job.id, "state": job.state}

    @router.post("/sfx")
    async def local_sfx(body: LocalGenerateRequest):
        return await generate(body, "audio.sfx.generate")

    @router.post("/music")
    async def local_music(body: LocalGenerateRequest):
        return await generate(body, "music.generate")

    return router
