from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Language = Literal["auto", "ja", "en"]
Quality = Literal["fast", "balanced", "quality"]


class OutputSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    format: str = "wav"
    sample_rate: int | None = Field(default=None, ge=8000, le=192000)
    channels: int | None = Field(default=None, ge=1, le=2)


class RoutingSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    engine: str | None = None
    model: str | None = None
    device: str = "auto"


class TaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task: str
    input: dict[str, Any] = Field(default_factory=dict)
    profile: str = "default"
    quality: Quality = "balanced"
    content_language: Language = "auto"
    output: OutputSpec = Field(default_factory=OutputSpec)
    routing: RoutingSpec = Field(default_factory=RoutingSpec)
    seed: int | None = None
    project_output_grant: str | None = None

    @model_validator(mode="after")
    def validate_task(self):
        allowed = {
            "speech.tts.synthesize",
            "speech.asr.transcribe",
            "audio.sfx.generate",
            "audio.ambience.generate",
            "music.generate",
        }
        if self.task not in allowed:
            raise ValueError("unsupported task")
        if self.task == "speech.tts.synthesize" and not str(self.input.get("text", "")).strip():
            raise ValueError("speech synthesis requires input.text")
        return self


class SetupApplyRequest(BaseModel):
    profile: Literal["speech-essentials", "game-audio", "music", "full-studio", "cpu-essentials", "custom"] = "speech-essentials"
    components: list[str] = Field(default_factory=list)
    accepted_terms: list[str] = Field(default_factory=list)


class VoiceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    source_type: Literal["built-in", "clone", "trained", "design", "imported"] = "built-in"
    languages: list[Literal["ja", "en"]] = Field(default_factory=lambda: ["ja", "en"])
    engine_id: str | None = None
    recipe: dict[str, Any] = Field(default_factory=dict)
    rights_confirmed: bool = False


class LocalizationLineInput(BaseModel):
    line_id: str = Field(min_length=1, max_length=120)
    character: str | None = None
    ja_text: str | None = None
    en_text: str | None = None
    voice_id: str | None = None


class LocalizationBatchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    profile: dict[str, Any] = Field(default_factory=dict)
    lines: list[LocalizationLineInput] = Field(default_factory=list, max_length=10000)
