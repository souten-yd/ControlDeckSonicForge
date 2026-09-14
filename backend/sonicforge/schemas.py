from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from . import vocal_language

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
# 書き起こしが音を受け取る道。どれか 1 つが要る。
ASR_SOURCE_FIELDS = ("asset_id", "upload_id", "grant_id", "audio_grant")
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
    gpt_sovits_voice_id: str | None = Field(default=None, pattern=r"^voice:[0-9a-f-]{36}$")


class TtsSampleInstall(BaseModel):
    model_config = ConfigDict(extra="forbid")
    accepted_terms: bool = False


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
                raise ValueError("invalid_grant_reference: ASR input must use a scoped grant ID")
            # Audio recorded or picked in the browser never becomes a ControlDeck
            # grant; it is uploaded to SonicForge and referenced by upload ID.
            upload = self.input.get("upload_id")
            if upload is not None and (
                not isinstance(upload, str)
                or re.fullmatch(UPLOAD_PATTERN, upload) is None
            ):
                raise ValueError("invalid_upload_reference: ASR upload reference is invalid")
            # 自分で作った音も書き起こせる。sonic.inspect は長さと状態しか返さず
            # 「言葉は sonic.transcribe で」と案内するのに、その transcribe が
            # asset を受け取らなかった（実測: asset_id を渡して 500）。
            asset = self.input.get("asset_id")
            if asset is not None and (
                not isinstance(asset, str) or not asset.startswith("asset:")
            ):
                raise ValueError("invalid_asset_reference: ASR asset reference must be an asset: ID")

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
        limits = DURATION_LIMITS.get(self.task)
        if limits is not None and self.input.get("duration_sec") is not None:
            low, high = limits
            try:
                seconds = float(self.input["duration_sec"])
            except (TypeError, ValueError):
                raise ValueError(
                    "invalid_duration: duration_sec must be a number"
                ) from None
            if not low <= seconds <= high:
                raise ValueError(
                    f"duration_out_of_range: {self.task} makes {low:g} to {high:g} "
                    f"seconds; {seconds:g} is outside that"
                )
        if self.task == "music.generate":
            # 歌ありは歌詞が要る。instrumental を false にするだけでは歌にならない。
            #
            # ACE-Step の lyrics 既定は空文字で、空のまま歌えと言われたモデルは
            # 伴奏だけを返す。ジョブは成功し、長さも合っているので、頼んだ側からは
            # 「歌を頼んだのに歌っていない」としか見えない（実測 2026-09-14:
            # instrumental=false で作った 30 秒を聴いて「歌に聞こえない。音楽だけ」）。
            # 黙って伴奏を返すより、何が足りないかを言って断る。
            lyrics = str(self.input.get("lyrics") or "").strip()
            if self.input.get("instrumental") is False and not lyrics:
                raise ValueError(
                    "missing_lyrics: vocal music requires input.lyrics; "
                    "instrumental=false alone produces an instrumental track"
                )
            if lyrics and self.input.get("instrumental") is not False:
                # 逆向きの取り違えも黙って捨てない。歌詞を書いたのに
                # instrumental が既定の true のままだと歌詞は無視される。
                raise ValueError(
                    "lyrics_ignored: input.lyrics is ignored while instrumental is "
                    "true; set instrumental=false to sing them"
                )
            language = self.input.get("vocal_language")
            if language is not None and language not in VOCAL_LANGUAGES:
                raise ValueError(
                    "unsupported_vocal_language: vocal_language must be one of "
                    + ", ".join(sorted(VOCAL_LANGUAGES))
                )
            # 言語を決めていないなら、歌詞の文字から決める。
            #
            # 渡さないとモデルは unknown を受け取り、日本語の歌詞では**歌わない**
            # （実測 2026-09-14: 同じ歌詞・同じ prompt の 30 秒 2 本で、ja を
            # 指定したほうだけが歌った）。画面の簡易モードは言語を選ぶ場所を
            # 持たないので、そこから頼むと必ずこれに当たっていた。
            # 書かれた文字を見れば分かるものを、モデルに当てさせない。
            if lyrics and language in (None, "auto"):
                detected = vocal_language.detect(lyrics)
                if detected:
                    self.input["vocal_language"] = detected
        known = INPUT_FIELDS.get(self.task)
        if known is not None:
            # 読まない項目は黙って捨てない。duration_seconds と書いた要求が
            # duration_sec と読まれずに既定の 30 秒で作られ、頼んだ側からは
            # 20 秒を頼んだのに 30 秒が返ったようにしか見えなかった。
            unknown = sorted(
                key for key in self.input
                if key not in known and not key.startswith("_internal_")
            )
            if unknown:
                raise ValueError(
                    "unknown_input_fields: "
                    f"{self.task} does not read these input fields: {', '.join(unknown)}"
                )
        return self


# task ごとに worker が実際に読む input の項目。
#
# 一覧にしておくのは、読まないものを黙って受け取らないためである。名前を
# 間違えた要求は既定値で作られ、頼んだ側からは「頼んだとおりに作られなかった」
# ようにしか見えない（実測: duration_seconds と書いた 20 秒の依頼が 30 秒で
# 返った）。schemas/generate-request.json の説明文と対になっている。
# task ごとに作れる長さが違う。1 つの範囲を全 task で共用していたため、
# 契約の 1〜300 秒はどちらにも合っていなかった。
#
# 音楽（ACE-Step）: 実力は GPU の VRAM 段で決まり、この機械（31.9GB / tier
# unlimited）では 600 秒。契約が 300 で止めていたので半分が使えなかった。
# 下限は締めない。ACE-Step が自分で名乗る範囲は 10〜600 だが、下限は出力長の
# 下限ではなく生成トークン数の見積りに効くだけで、実測では 5 秒を頼むと
# 5.12 秒が返る。動くものを契約で塞がない（10 秒未満は出来を保証しないという
# 注意は説明に書く）。
# 効果音・環境音（Stable Audio）: worker 側が 0.1〜120 秒で受ける。
# 契約の下限 1 のせいで、0.1〜0.9 秒は画面から入力できても弾かれていた。
DURATION_LIMITS: dict[str, tuple[float, float]] = {
    "audio.sfx.generate": (0.1, 120.0),
    "audio.ambience.generate": (0.1, 120.0),
    "music.generate": (1.0, 600.0),
}
# 契約に書く範囲は全 task の和集合。task ごとの正確な境目は下の検証で見る。
DURATION_MIN = min(low for low, _ in DURATION_LIMITS.values())
DURATION_MAX = max(high for _, high in DURATION_LIMITS.values())

# 歌わせられる言語。ACE-Step の VALID_LANGUAGES の部分集合で、"auto" は
# 「歌詞から推定させる」（worker が "unknown" へ写す）。
VOCAL_LANGUAGES = frozenset({
    "auto", "ja", "en", "zh", "ko", "es", "fr", "de", "it", "pt", "ru",
})

INPUT_FIELDS: dict[str, frozenset[str]] = {
    "speech.tts.synthesize": frozenset({
        "text", "voice_id", "speaker", "style", "emotion", "reference_text",
        "reference_grant", "upload_id",
    }),
    "speech.asr.transcribe": frozenset({
        "audio_grant", "grant_id", "upload_id", "asset_id",
    }),
    "audio.sfx.generate": frozenset({"prompt", "description", "duration_sec", "loop"}),
    "audio.ambience.generate": frozenset({"prompt", "description", "duration_sec", "loop"}),
    "music.generate": frozenset({
        "prompt", "description", "duration_sec", "bpm", "instrumental",
        "lyrics", "vocal_language", "loop",
    }),
}


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
