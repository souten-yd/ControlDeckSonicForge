# Audio Capabilities and Public API

Status: Normative API direction  
Date: 2026-08-25

## 1. API philosophy

Public callers describe **what they want**, not which internal Python package to call.

Bad public contract:

```json
{"engine":"gpt-sovits","model":"foo.ckpt","temperature":0.8}
```

Preferred high-level contract:

```json
{
  "task":"speech.synthesize",
  "input":{"text":"こんにちは"},
  "profile":"character-dialogue",
  "quality":"balanced"
}
```

Engine/model pinning remains possible through an optional advanced `routing` object and is never required for ordinary callers.

## 2. Capability namespace

### 2.1 TTS

```text
speech.tts.synthesize
speech.tts.stream
speech.tts.voice_clone
speech.tts.voice_design
speech.tts.style_control
speech.tts.longform
speech.tts.dialogue_batch
speech.tts.pronunciation
```

### 2.2 ASR

```text
speech.asr.transcribe
speech.asr.stream
speech.asr.timestamps
speech.asr.segment
speech.asr.diarize          optional
speech.asr.align            optional
speech.asr.ja_en            optional
```

### 2.3 Audio/SFX

```text
audio.sfx.generate
audio.sfx.variations
audio.ambience.generate
audio.loop.generate
audio.edit.restylize        later
audio.edit.inpaint          later
audio.processing.normalize
audio.processing.trim
audio.processing.resample
audio.processing.convert
audio.processing.fade
audio.processing.loop_points
```

### 2.4 Music

```text
music.generate
music.variations
music.remix
music.extend
music.loop
music.stems                 optional
music.accompaniment         optional
music.lyrics_to_song        later
```

### 2.5 Packaging

```text
asset.pack.generic
asset.pack.game
asset.pack.web
asset.pack.dialogue
```

## 3. Capability document

`GET /addon/v1/capabilities`

The response is runtime-derived, not hard-coded UI configuration.

Each capability includes:

```json
{
  "id": "speech.tts.synthesize",
  "state": "available",
  "quality_tier": "recommended",
  "reason_code": null,
  "reason": null,
  "features": {
    "languages": ["ja"],
    "streaming": true,
    "voice_clone": true
  },
  "limits": {
    "max_text_chars": 10000
  }
}
```

Allowed state model:

```text
available
experimental
degraded
setup_required
unavailable
```

The UI, workflow catalog and agent descriptions derive feature availability from this document.

## 4. Generic create request

The stable cross-domain job request should support a generic task envelope.

```json
{
  "task": "speech.tts.synthesize",
  "input": {},
  "profile": "default",
  "quality": "balanced",
  "output": {
    "format": "wav",
    "sample_rate": null,
    "channels": null
  },
  "routing": {
    "engine": null,
    "model": null,
    "device": "auto"
  },
  "seed": null,
  "project_output_grant": null
}
```

`routing` is advanced/optional. Unknown user-provided engine/model IDs must be rejected cleanly rather than passed to arbitrary loaders.

## 5. TTS request

Example normalized request:

```json
{
  "task": "speech.tts.synthesize",
  "input": {
    "text": "おはよう。今日もよろしくね。",
    "language": "ja",
    "voice_id": "voice:character-a",
    "style": {
      "preset": "cheerful",
      "strength": 0.7,
      "speed": 1.0,
      "pitch": 0.0
    }
  },
  "profile": "character-dialogue",
  "quality": "balanced"
}
```

Normalized fields are best-effort. An adapter may ignore unsupported non-required fields only when capability metadata explicitly says they are unsupported; UI should not expose unavailable controls.

### Voice identity

Use logical IDs:

```text
voice:<uuid-or-slug>
```

A voice record may refer to:

- built-in engine speaker
- imported trained model
- reference-audio clone recipe
- voice-design recipe

Callers do not pass raw checkpoint paths.

## 6. ASR request

```json
{
  "task": "speech.asr.transcribe",
  "input": {
    "asset_id": "asset:...",
    "language": "ja",
    "timestamps": "segment",
    "punctuation": true,
    "normalize_text": true
  },
  "quality": "balanced"
}
```

Result example:

```json
{
  "text": "...",
  "language": "ja",
  "segments": [
    {"start_ms":0,"end_ms":1820,"text":"..."}
  ],
  "engine_metadata": {},
  "asset_id": null
}
```

Long transcripts may be stored as an asset/document with a bounded summary in the Host Job result.

## 7. Streaming ASR/TTS

Streaming requires a session protocol separate from durable batch generation.

Conceptual endpoints:

```text
POST /addon/v1/realtime/sessions
WS   /addon/v1/realtime/sessions/{id}
DELETE /addon/v1/realtime/sessions/{id}
```

Session requirements:

- service token / authorized user context
- bounded concurrent sessions
- explicit sample format negotiation
- backpressure
- heartbeats/timeouts
- cancellation/close
- resource lease when GPU-backed
- no raw Host cookies

For microphone capture, browser permissions remain in the isolated SonicForge view. Audio is sent to SonicForge through the host-mediated proxy path.

## 8. SFX/game-audio request

```json
{
  "task": "audio.sfx.generate",
  "input": {
    "prompt": "short futuristic menu confirm click, clean and bright",
    "duration_sec": 0.8,
    "category": "ui.confirm",
    "loop": false,
    "variation_count": 4
  },
  "profile": "game-ui",
  "quality": "balanced"
}
```

Game-oriented normalized metadata should include when relevant:

- `category`
- `loopable`
- loop start/end
- peak level
- integrated loudness if measured
- duration
- sample rate/channels
- variation group id
- tags

## 9. Music request

```json
{
  "task": "music.generate",
  "input": {
    "prompt": "uplifting cyberpunk exploration BGM, energetic but not aggressive",
    "duration_sec": 90,
    "instrumental": true,
    "bpm": 118,
    "key": null,
    "time_signature": "4/4",
    "loop": true
  },
  "profile": "game-bgm",
  "quality": "balanced"
}
```

Engine-specific lyric/section controls live behind optional feature extensions until a stable normalized contract is proven.

## 10. Output asset contract

Every generated audio artifact becomes a SonicForge asset record.

Required fields:

```text
asset_id
kind
mime_type
codec
sample_rate
channels
duration_ms
size_bytes
sha256
created_at
job_id
capability
generation_profile
provenance_id
```

Useful optional fields:

```text
loudness_lufs
true_peak_dbfs
loop_start_samples
loop_end_samples
bpm
key
tags
variation_group
waveform_preview
spectrogram_preview
```

Raw local storage paths are internal and never included in Host-facing asset metadata.

## 11. Provenance contract

At minimum:

```text
provenance_id
operation
engine_id
engine_version
model_id
model_revision
model_license_id
input_asset_ids
input_voice_ids
prompt_hash or prompt text according to privacy policy
seed when supported
normalized parameters
adapter version
SonicForge version
created_at
```

For voice clone/reference operations also record rights/consent reference metadata; see security document.

## 12. Engine adapter interface

Conceptual Python boundary:

```python
class EngineAdapter(Protocol):
    def describe(self) -> EngineDescriptor: ...
    def capabilities(self) -> list[CapabilityDescriptor]: ...
    def estimate(self, request: TaskRequest) -> ResourceEstimate: ...
    async def prepare(self, context: WorkerContext) -> None: ...
    async def execute(self, request: TaskRequest, context: TaskContext) -> TaskResult: ...
    async def cancel(self, task_id: str) -> None: ...
    async def unload(self) -> None: ...
```

The core communicates with heavy workers over IPC/HTTP and does not import the adapter's heavy ML dependencies into the core process.

## 13. Routing

Routing considers:

1. required capability/features
2. language (Japanese preference)
3. requested voice/profile
4. quality/latency preference
5. hardware/backend availability
6. model availability/license state
7. estimated VRAM/resource wait
8. explicit user pin, if any

Suggested quality presets:

```text
fast
balanced
quality
```

Presets map to routing policy, not globally fixed model names.

## 14. Workflow executors

Recommended stable executors:

```text
sonic.speech.synthesize
sonic.speech.transcribe
sonic.audio.generate
sonic.music.generate
```

Input/output JSON Schemas live under `schemas/` and must validate both at Host boundary and SonicForge boundary.

## 15. Agent tools

### `sonic.capabilities`

Returns bounded capability/runtime information intended for planning.

### `sonic.generate`

Generic TTS/SFX/music generation by stable task id.

### `sonic.transcribe`

Transcribes a Host-granted audio asset.

### `sonic.inspect`

Returns bounded audio/provenance metadata.

### `sonic.pack`

Commits an existing SonicForge asset into the current authorized project output grant.

Agent tools never accept arbitrary host filesystem paths.

## 16. Error model

Stable categories:

```text
invalid_request
capability_unavailable
setup_required
engine_unavailable
model_unavailable
license_required
resource_wait_timeout
resource_denied
input_unsupported
rights_confirmation_required
canceled
worker_failed
output_validation_failed
internal_error
```

Errors include a stable machine code, human message, retryability and optional remediation action. Do not leak stack traces, tokens or absolute paths.

## 17. Audio output validation

Before an asset is marked succeeded, validate:

- file decodes
- duration is sane/non-zero
- sample rate/channels match declared metadata
- no NaN/invalid samples
- file hash/size recorded
- loop points are in bounds
- requested codec/container is valid
- provenance exists

Optional profile-specific validators can enforce loudness/peak/length constraints for game assets.