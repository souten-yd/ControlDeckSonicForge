from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .schemas import GRANT_PATTERN, UPLOAD_PATTERN, Language, Quality, RoutingSpec

ASSET_PATTERN = r"^asset:[A-Za-z0-9._:-]{1,256}$"

PipelineInputKind = Literal[
    "text", "audio_grant", "audio_upload", "audio_asset", "audio_stream"
]
PipelineStageKind = Literal[
    "speech.asr",
    "host.ai.text",
    "speech.tts",
    "audio.sfx",
    "music.generate",
    "audio.process",
]
PipelineDeliveryMode = Literal[
    "text", "asset", "project", "http", "websocket", "package"
]
MediaType = Literal["text", "audio"]

_STAGE_TYPES: dict[str, tuple[MediaType, MediaType]] = {
    "speech.asr": ("audio", "text"),
    "host.ai.text": ("text", "text"),
    "speech.tts": ("text", "audio"),
    "audio.sfx": ("text", "audio"),
    "music.generate": ("text", "audio"),
    "audio.process": ("audio", "audio"),
}
_INPUT_TYPES: dict[str, MediaType] = {
    "text": "text",
    "audio_grant": "audio",
    "audio_upload": "audio",
    "audio_asset": "audio",
    "audio_stream": "audio",
}


class PipelineInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: PipelineInputKind
    text: str | None = Field(default=None, max_length=100_000)
    grant_id: str | None = Field(default=None, pattern=GRANT_PATTERN)
    upload_id: str | None = Field(default=None, pattern=UPLOAD_PATTERN)
    asset_id: str | None = Field(default=None, pattern=ASSET_PATTERN)
    stream_id: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_payload(self):
        fields = {
            "text": self.text,
            "grant_id": self.grant_id,
            "upload_id": self.upload_id,
            "asset_id": self.asset_id,
            "stream_id": self.stream_id,
        }
        expected = {
            "text": "text",
            "audio_grant": "grant_id",
            "audio_upload": "upload_id",
            "audio_asset": "asset_id",
            "audio_stream": "stream_id",
        }[self.kind]
        if expected == "text":
            if not (self.text or "").strip():
                raise ValueError("text pipeline input requires non-empty text")
        elif fields[expected] is None:
            raise ValueError(f"{self.kind} pipeline input requires {expected}")
        for key, value in fields.items():
            if key != expected and value is not None:
                raise ValueError(f"{self.kind} pipeline input cannot include {key}")
        return self


class PipelineStage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    kind: PipelineStageKind
    language: Language = "auto"
    profile: str | None = Field(default=None, max_length=120)
    voice_id: str | None = Field(default=None, max_length=128)
    quality: Quality = "balanced"
    routing: RoutingSpec = Field(default_factory=RoutingSpec)
    parameters: dict[str, Any] = Field(default_factory=dict, max_length=32)

    @model_validator(mode="after")
    def validate_parameters(self):
        if any(str(key).startswith("_internal_") for key in self.parameters):
            raise ValueError("internal pipeline fields cannot be supplied by clients")
        return self


class PipelineDelivery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: PipelineDeliveryMode = "asset"
    profile: str = Field(default="default", min_length=1, max_length=120)
    project_output_grant: str | None = Field(default=None, pattern=GRANT_PATTERN)
    filename: str | None = Field(default=None, min_length=1, max_length=240)

    @model_validator(mode="after")
    def validate_grant(self):
        if self.mode == "project" and self.project_output_grant is None:
            raise ValueError("project delivery requires project_output_grant")
        if self.mode != "project" and self.project_output_grant is not None:
            raise ValueError("project_output_grant is only valid for project delivery")
        return self


@dataclass(frozen=True)
class CompiledPipeline:
    start_index: int
    stop_index: int
    input_type: MediaType
    output_type: MediaType
    stage_ids: tuple[str, ...]


def compile_pipeline(request: "PipelineRequest") -> CompiledPipeline:
    ids = [stage.id for stage in request.stages]
    if len(set(ids)) != len(ids):
        raise ValueError("pipeline stage ids must be unique")

    start_index = 0
    stop_index = len(request.stages) - 1
    if request.start_at is not None:
        if request.start_at not in ids:
            raise ValueError("start_at must reference a pipeline stage id")
        start_index = ids.index(request.start_at)
    if request.stop_after is not None:
        if request.stop_after not in ids:
            raise ValueError("stop_after must reference a pipeline stage id")
        stop_index = ids.index(request.stop_after)
    if stop_index < start_index:
        raise ValueError("stop_after cannot precede start_at")

    current_type: MediaType = _INPUT_TYPES[request.input.kind]
    active = request.stages[start_index : stop_index + 1]
    for stage in active:
        expected, produced = _STAGE_TYPES[stage.kind]
        if current_type != expected:
            raise ValueError(
                f"pipeline type mismatch before {stage.id}: "
                f"{current_type} cannot feed {stage.kind} ({expected} required)"
            )
        current_type = produced

    if request.delivery.mode == "text" and current_type != "text":
        raise ValueError("text delivery requires text output")
    if request.delivery.mode in {"asset", "project", "http", "package"} and current_type != "audio":
        raise ValueError(f"{request.delivery.mode} delivery requires audio output")

    return CompiledPipeline(
        start_index=start_index,
        stop_index=stop_index,
        input_type=_INPUT_TYPES[request.input.kind],
        output_type=current_type,
        stage_ids=tuple(stage.id for stage in active),
    )


class PipelineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pipeline: str | None = Field(default=None, min_length=1, max_length=120)
    input: PipelineInput
    stages: list[PipelineStage] = Field(min_length=1, max_length=8)
    start_at: str | None = Field(default=None, max_length=64)
    stop_after: str | None = Field(default=None, max_length=64)
    delivery: PipelineDelivery = Field(default_factory=PipelineDelivery)

    @model_validator(mode="after")
    def validate_compilation(self):
        compile_pipeline(self)
        return self


class AudioFormat(BaseModel):
    model_config = ConfigDict(extra="forbid")
    codec: Literal["pcm_s16le", "opus"]
    rate: int = Field(ge=8000, le=48000)
    channels: Literal[1, 2]
    frame_ms: int = Field(default=20, ge=10, le=100)


class EdgeAudioCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input: list[AudioFormat] = Field(min_length=1, max_length=8)
    output: list[AudioFormat] = Field(min_length=1, max_length=8)
    aec: bool = False
    vad: bool = False
    wake: bool = False


class EdgeUiCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display: bool = False
    touch: bool = False
    buttons: int = Field(default=0, ge=0, le=16)


class EdgeDeviceDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")
    protocol: Literal["sonic-edge/1"] = "sonic-edge/1"
    device_class: Literal["m5", "mobile", "pc", "simulator"]
    model: str = Field(min_length=1, max_length=80)
    firmware: str = Field(min_length=1, max_length=40)
    audio: EdgeAudioCapabilities
    ui: EdgeUiCapabilities = Field(default_factory=EdgeUiCapabilities)
    psram_bytes: int | None = Field(default=None, ge=0, le=64 * 1024 * 1024)


class LiveSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preset: Literal[
        "m5-voice-agent",
        "m5-dictation",
        "m5-ask-text",
        "voice-assistant",
        "simultaneous-translation",
        "meeting",
        "dictation",
    ] = "voice-assistant"
    pipeline: PipelineRequest
    device: EdgeDeviceDescriptor | None = None
    transport: Literal["websocket"] = "websocket"
    save_transcript: bool = False
    save_input_audio: bool = False
    save_output_audio: bool = False
    keep_warm: bool = True
    streaming_response: bool = True
    target_language: Literal["ja", "en"] | None = None
    # None means no arbitrary product duration limit. Implementations must spool
    # or chunk rather than accumulating unbounded audio in RAM.
    max_utterance_seconds: int | None = Field(default=None, ge=1, le=86_400)

    @model_validator(mode="after")
    def validate_live_contract(self):
        if self.pipeline.delivery.mode != "websocket":
            raise ValueError("live session pipeline must use websocket delivery")
        if self.pipeline.input.kind not in {"audio_stream", "text"}:
            raise ValueError("live session input must be audio_stream or text")
        if self.preset == "simultaneous-translation" and self.target_language is None:
            raise ValueError("simultaneous-translation requires target_language")
        return self
