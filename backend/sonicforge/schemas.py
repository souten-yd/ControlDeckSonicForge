from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Language = Literal["auto", "ja", "en"]
Quality = Literal["fast", "balanced", "quality"]
TaskName = Literal[
    "speech.tts.synthesize",
    "speech.asr.transcribe",
    "speech.localization.batch",
    "audio.sfx.generate",
    "audio.ambience.generate",
    "music.generate",
]
GRANT_PATTERN = r"^grant:[A-Za-z0-9._:-]{1,256}$"
UPLOAD_PATTERN = r"^upload:[0-9a-f]{32}$"


class OutputSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    format: Literal["wav", "flac", "mp3", "ogg"] = "wav"
    sample_rate: int | None = Field(default=None, ge=8000, le=192000)
    channels: int | None = Field(default=None, ge=1, le=2)


class RoutingSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    engine: str | None = Field(default=None, min_length=1, max_length=120)
    model: str | None = Field(default=None, min_length=1, max_length=240)
    device: str = Field(default="auto", min_length=1, max_length=64)


class TtsPreferenceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    engine_id: Literal["tts.qwen3", "tts.gpt-sovits"]
    gpt_sovits_model_id: str | None = Field(default=None, min_length=1, max_length=80)


class TaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task: TaskName
    input: dict[str, Any] = Field(default_factory=dict)
    profile: str = Field(default="default", min_length=1, max_length=120)
    quality: Quality = "balanced"
    content_language: Language = "auto"
    output: OutputSpec = Field(default_factory=OutputSpec)
    routing: RoutingSpec = Field(default_factory=RoutingSpec)
    seed: int | None = None
    project_output_grant: str | None = Field(default=None, pattern=GRANT_PATTERN)

    @model_validator(mode="after")
    def validate_task(self):
        if any(str(key).startswith("_internal_") for key in self.input):
            raise ValueError("internal task fields cannot be supplied by clients")
        if self.task == "speech.tts.synthesize" and not str(
            self.input.get("text", "")
        ).strip():
            raise ValueError("speech synthesis requires input.text")
        if self.task == "speech.asr.transcribe":
            grant = self.input.get("audio_grant") or self.input.get("grant_id")
            if grant is not None and (
                not isinstance(grant, str) or not grant.startswith("grant:")
            ):
                raise ValueError("ASR input must use a scoped grant ID")
            # Audio recorded or picked in the browser never becomes a ControlDeck
            # grant; it is uploaded to SonicForge and referenced by upload ID.
            upload = self.input.get("upload_id")
            if upload is not None and (
                not isinstance(upload, str)
                or re.fullmatch(UPLOAD_PATTERN, upload) is None
            ):
                raise ValueError("ASR upload reference is invalid")

        if self.task == "speech.localization.batch":
            batch_id = self.input.get("batch_id")
            if not isinstance(batch_id, str) or not batch_id.startswith("loc:"):
                raise ValueError("localization batch requires input.batch_id")
            locales = self.input.get("locales", ["ja", "en"])
            if (
                not isinstance(locales, list)
                or not locales
                or len(locales) > 2
                or any(locale not in {"ja", "en"} for locale in locales)
                or len(set(locales)) != len(locales)
            ):
                raise ValueError("localization locales must be unique ja/en values")
            mode = self.input.get("mode", "pending")
            if mode not in {"pending", "failed", "changed", "all"}:
                raise ValueError(
                    "localization mode must be pending, failed, changed or all"
                )
            line_ids = self.input.get("line_ids", [])
            if (
                not isinstance(line_ids, list)
                or len(line_ids) > 10000
                or any(
                    not isinstance(line_id, str)
                    or not line_id
                    or len(line_id) > 120
                    for line_id in line_ids
                )
            ):
                raise ValueError("localization line_ids are invalid")
        if self.task in {
            "audio.sfx.generate",
            "audio.ambience.generate",
            "music.generate",
        } and not str(
            self.input.get("prompt") or self.input.get("description") or ""
        ).strip():
            raise ValueError("generation requires input.prompt or input.description")
        return self


class SetupApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile: Literal[
        "speech-essentials",
        "gpt-sovits",
        "game-audio",
        "music",
        "full-studio",
        "cpu-essentials",
        "custom",
    ] = "speech-essentials"
    components: list[
        Literal["speech-essentials", "gpt-sovits", "game-audio", "music"]
    ] = Field(default_factory=list, max_length=4)
    accepted_terms: list[str] = Field(default_factory=list, max_length=16)


class SetupCredentials(BaseModel):
    """Provisioning credentials the operator supplies.

    A Hugging Face access token is required for gated repositories such as
    Stable Audio 3 Small-SFX. Send an empty string to clear it. The value is
    stored write-only and is never returned.
    """

    model_config = ConfigDict(extra="forbid")
    huggingface_token: str | None = Field(default=None, max_length=400)


class VoiceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    source_type: Literal[
        "built-in", "clone", "trained", "design", "imported"
    ] = "built-in"
    languages: list[Literal["ja", "en"]] = Field(
        default_factory=lambda: ["ja", "en"], min_length=1, max_length=2
    )
    engine_id: str | None = Field(default=None, max_length=120)
    recipe: dict[str, Any] = Field(default_factory=dict)
    rights_confirmed: bool = False

    @model_validator(mode="after")
    def validate_voice(self):
        if len(set(self.languages)) != len(self.languages):
            raise ValueError("voice languages cannot contain duplicates")
        if any(str(key).startswith("_internal_") for key in self.recipe):
            raise ValueError("internal voice fields cannot be supplied by clients")
        if self.source_type == "clone":
            if "reference_audio" in self.recipe:
                raise ValueError(
                    "voice clone reference audio must be imported through reference_grant"
                )
            grant = self.recipe.get("reference_grant")
            if grant is not None and (
                not isinstance(grant, str) or not grant.startswith("grant:")
            ):
                raise ValueError("reference_grant must be a scoped grant ID")
            upload = self.recipe.get("reference_upload")
            if upload is not None and (
                not isinstance(upload, str)
                or re.fullmatch(UPLOAD_PATTERN, upload) is None
            ):
                raise ValueError("reference_upload must be an upload reference")
            if self.engine_id == "tts.gpt-sovits" and not str(
                self.recipe.get("reference_text") or ""
            ).strip():
                raise ValueError("GPT-SoVITS sample voice requires reference_text")

        return self


class LocalizationLineInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    line_id: str = Field(min_length=1, max_length=120)
    character: str | None = Field(default=None, max_length=120)
    ja_text: str | None = Field(default=None, max_length=10000)
    en_text: str | None = Field(default=None, max_length=10000)
    voice_id: str | None = Field(default=None, max_length=64)


class LocalizationBatchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=160)
    profile: dict[str, Any] = Field(default_factory=dict)
    lines: list[LocalizationLineInput] = Field(
        default_factory=list, max_length=10000
    )
