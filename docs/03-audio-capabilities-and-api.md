# Audio Capabilities and Public API

Status: Normative API direction  
Date: 2026-08-25

## 1. API philosophy

Public callers describe **what they want**, not which internal Python package/model to call.

Bad stable contract:

```json
{"engine":"gpt-sovits","model":"foo.ckpt","temperature":0.8}
```

Preferred:

```json
{
  "task":"speech.tts.synthesize",
  "input":{"text":"こんにちは / Hello"},
  "profile":"character-dialogue",
  "quality":"balanced"
}
```

Engine/model pinning is an optional Expert `routing` hint and never required for ordinary callers.

The stable API is intentionally smaller than the full UI feature set. Do not add a new workflow/tool contract merely because one engine exposes another knob.

## 2. Language contract

Initial public normalized values:

```text
content_language = auto | ja | en
ui_locale        = auto | ja | en        UI/settings concept, not an inference requirement
```

Internally SonicForge may retain BCP-47/localized metadata such as `ja-JP` or `en-US`, but normal callers should not be forced to choose a region unless it materially changes the requested voice/output.

Rules:

- Japanese and English are first-class speech languages.
- `auto` is convenient for unknown/mixed content.
- when the language is known, explicit `ja`/`en` is preferred for predictable routing/pronunciation.
- capability metadata advertises the actual languages tested/available for the installed route.
- requesting an unsupported language fails clearly; do not silently synthesize/transcribe with the wrong language.
- language support is metadata, **not** a combinatorial capability name. Do not create `speech.asr.ja_en`, `speech.asr.en_fr`, etc.

## 3. Capability namespace

### 3.1 TTS

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

### 3.2 ASR

```text
speech.asr.transcribe
speech.asr.stream
speech.asr.timestamps
speech.asr.segment
speech.asr.diarize          optional
speech.asr.align            optional
```

### 3.3 Localization/QA

These are high-level SonicForge capabilities, not additional model IDs:

```text
speech.localization.batch
speech.qa.roundtrip         optional heuristic
```

### 3.4 Audio/SFX

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
audio.qa.loudness
audio.qa.loop_seam
```

### 3.5 Music

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

### 3.6 Packaging

```text
asset.pack.generic
asset.pack.game
asset.pack.web
asset.pack.dialogue
```

## 4. Capability document

`GET /addon/v1/capabilities`

Runtime-derived example:

```json
{
  "id": "speech.tts.synthesize",
  "state": "available",
  "quality_tier": "recommended",
  "reason_code": null,
  "reason": null,
  "features": {
    "languages": ["ja", "en"],
    "mixed_language": true,
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

The UI/workflow/agent descriptions derive availability from this document.

Keep state meanings distinct from install catalog state. `installed`, `available`, `recommended`, `loaded`, and `running` are not synonyms.

## 5. Generic create request

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

Stable wire quality values may remain:

```text
fast
balanced
quality
```

User-facing copy is:

```text
Fast / Recommended / High quality
高速 / おすすめ / 高品質
```

`routing` is Expert/optional. Unknown engine/model IDs are rejected cleanly rather than forwarded to arbitrary loaders.

## 6. TTS request

```json
{
  "task": "speech.tts.synthesize",
  "input": {
    "text": "おはよう。Ready to go?",
    "content_language": "auto",
    "voice_id": "voice:character-a",
    "style": {
      "preset": "cheerful",
      "strength": 0.7,
      "speed": 1.0,
      "pitch": 0.0
    },
    "pronunciation_dictionary_id": "dictionary:project-main"
  },
  "profile": "character-dialogue",
  "quality": "balanced"
}
```

Normalized controls are capability-dependent. UI does not expose unsupported fields merely as disabled clutter.

### Voice identity

Use logical IDs:

```text
voice:<uuid-or-slug>
```

A voice record may represent:

- built-in engine speaker
- imported trained model
- reference-audio clone recipe
- voice-design recipe

Voice metadata includes supported/preferred languages. Callers never use raw checkpoint paths as identity.

## 7. Pronunciation dictionary

Project-scoped logical dictionary:

```json
{
  "dictionary_id": "dictionary:project-main",
  "entries": [
    {
      "surface": "SonicForge",
      "language": "ja",
      "pronunciation": "ソニックフォージ"
    }
  ]
}
```

Stable entries describe desired pronunciation. Engine-specific phoneme syntax belongs to adapter/Expert extensions.

## 8. ASR request

```json
{
  "task": "speech.asr.transcribe",
  "input": {
    "asset_id": "asset:...",
    "content_language": "auto",
    "timestamps": "segment",
    "punctuation": true,
    "normalize_text": true
  },
  "quality": "balanced"
}
```

Result:

```json
{
  "text": "...",
  "detected_language": "ja",
  "segments": [
    {
      "start_ms": 0,
      "end_ms": 1820,
      "text": "...",
      "language": "ja"
    }
  ],
  "engine_metadata": {},
  "asset_id": null
}
```

Segment language is optional and emitted only if the route can support it reliably.
Long transcripts may be stored as assets/documents with bounded Host Job summaries.

## 9. Streaming ASR/TTS

Conceptual protocol:

```text
POST   /addon/v1/realtime/sessions
WS     /addon/v1/realtime/sessions/{id}
DELETE /addon/v1/realtime/sessions/{id}
```

Requirements:

- scoped authorized session
- explicit audio format negotiation
- language mode
- bounded concurrent sessions
- backpressure
- heartbeat/timeout/reconnect semantics
- cancellation/close
- Resource Broker lease when GPU-backed
- no raw Host credentials

Do not freeze detailed frame semantics until real engine prototypes establish requirements.

## 10. SFX request

```json
{
  "task": "audio.sfx.generate",
  "input": {
    "prompt": "short futuristic menu confirm click, clean and bright",
    "duration_sec": 0.8,
    "category": "ui.confirm",
    "loop": false,
    "variation_count": 3
  },
  "profile": "game-ui",
  "quality": "balanced"
}
```

Variation count is bounded; the Easy UI should not encourage large candidate batches by default.

Useful normalized metadata:

- category
- loopable / loop start/end
- peak level / integrated loudness when measured
- duration
- sample rate/channels
- variation group id
- tags

## 11. Music request

```json
{
  "task": "music.generate",
  "input": {
    "prompt": "uplifting cyberpunk exploration BGM, energetic but not aggressive",
    "duration_sec": 90,
    "instrumental": true,
    "bpm": 118,
    "loop": true,
    "variation_count": 2
  },
  "profile": "game-bgm",
  "quality": "balanced"
}
```

Engine-specific lyric/section/repaint controls remain optional namespaced extensions until a stable normalized contract is proven.

## 12. Localization batch

Localization Studio can use a dedicated SonicForge endpoint/capability while keeping the public Host executor set small.

Conceptual request:

```json
{
  "project_profile_id": "project-profile:game-a",
  "lines": [
    {
      "line_id": "npc_001",
      "character_id": "character:guide",
      "texts": {
        "ja": "こっちだよ。",
        "en": "Over here."
      },
      "voice_id": "voice:guide",
      "style": "friendly"
    }
  ],
  "qa": {
    "roundtrip_asr": true
  }
}
```

This creates durable per-batch/per-line state and logical JP/EN assets.

The ControlDeck public workflow catalog does **not** need a fifth permanent executor solely for Localization. It may invoke generic speech generation/batch contracts or a future additive executor only if real workflow use proves the need.

## 13. Automatic QA result

QA is evidence about checks actually performed.

Example:

```json
{
  "status": "warning",
  "checks": [
    {"id":"decode","state":"passed"},
    {"id":"clipping","state":"passed"},
    {"id":"tts_asr_roundtrip","state":"warning","score":0.91},
    {"id":"semantic_naturalness","state":"not_checked"}
  ]
}
```

Never return an empty warning list as if an unverifiable requirement was checked.

## 14. Output asset contract

Every generated artifact becomes a SonicForge asset.

Required:

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

Useful optional:

```text
content_language
loudness_lufs
true_peak_dbfs
loop_start_samples
loop_end_samples
bpm
key
tags
variation_group
localization_line_id
waveform_preview
spectrogram_preview
```

The asset `sha256` is a content identity/integrity field and is unrelated to release publisher authorization.
Raw local paths are never Host-facing metadata.

## 15. Provenance contract

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
content_language
prompt_hash or prompt text according to privacy policy
seed when supported
normalized parameters
adapter version
SonicForge version
created_at
```

Voice clone/reference operations additionally record rights/consent metadata.

## 16. Engine adapter interface

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

Heavy adapters run out of the core process.

## 17. Routing

Routing considers:

1. required capability/features
2. explicit/auto content language
3. requested voice/project profile
4. quality/latency policy
5. hardware/backend availability
6. model installation/license state
7. locally measured performance/resource estimates
8. current Resource Broker constraints
9. explicit Expert engine/model pin

Japanese specialization does not justify routing English to a Japanese-only model. Use a language-appropriate adapter.

## 18. Stable Workflow executors

Keep the first frozen set deliberately small:

```text
sonic.speech.synthesize
sonic.speech.transcribe
sonic.audio.generate
sonic.music.generate
```

Do not create an executor for every capability. Rich capability metadata exists for discovery/routing.

## 19. Agent tools

Initial stable set:

```text
sonic.capabilities
sonic.generate
sonic.transcribe
sonic.inspect
sonic.pack
```

Agents can request language/task/profile without knowing model IDs.
No tool accepts arbitrary Host paths.

## 20. Error model

Stable categories include:

```text
invalid_request
unsupported_language
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

Errors include stable machine code, localized/presentable information, retryability and optional remediation action; never leak secrets/absolute paths/stack traces.

## 21. Output validation

Before success:

- file decodes
- duration is sane/non-zero
- sample rate/channels match metadata
- samples are valid
- hash/size recorded
- loop points in bounds
- codec/container valid
- required provenance exists
- requested deterministic profile constraints are actually checked

Profile-specific validators can enforce loudness/peak/duration/loop requirements.