# Typed Media Pipeline, Agent and Delivery Architecture

Status: Normative design and implementation plan  
Date: 2026-08-25

## 1. Goal

SonicForge must support both direct media generation and composed speech/AI/media workflows without turning ControlDeck core into a media engine.

Required examples include:

```text
OpenCode -> generate BGM -> project asset
OpenCode -> generate SE/SFX -> project asset
OpenCode -> synthesize voice -> project asset
microphone/file -> ASR -> text
microphone/file -> ASR -> ControlDeck LLM -> text
microphone/file -> ASR -> ControlDeck LLM -> TTS -> audio
text -> ControlDeck LLM -> TTS -> audio
text -> TTS -> audio
text -> SFX -> audio
text -> Music -> audio
```

The user's phrase `ASR -> LLM -> ASR` is not type-correct for ordinary spoken response because ASR consumes audio and emits text. The normal voice-conversation route is:

```text
ASR -> LLM -> TTS
```

SonicForge should reject incompatible stage chains rather than silently reinterpret them.

## 2. Core decision: typed pipeline, not arbitrary shell/workflow

Add a SonicForge-owned **Typed Media Pipeline**.

A pipeline is an ordered typed stage list. v1 is deliberately linear rather than an unrestricted graph. This covers the requested start/end selection while keeping validation, cancellation, resource ownership and provenance understandable.

Each stage declares input/output media types:

| Stage | Input | Output |
|---|---|---|
| `speech.asr` | audio | text/transcript |
| `host.ai.text` | text | text |
| `speech.tts` | text | audio |
| `audio.sfx` | text | audio |
| `music.generate` | text | audio |
| `audio.process` | audio | audio |
| `asset.package` | audio/assets | durable asset/package |

A compiler validates type continuity before execution.

Examples that must fail validation:

```text
text -> ASR
ASR -> ASR
TTS -> LLM
LLM -> ASR
```

unless an explicit compatible conversion stage exists between them.

## 3. Start and end selection

The caller can choose where execution begins and ends without defining a completely different API.

Conceptual request:

```json
{
  "pipeline": "voice-assistant",
  "input": {
    "kind": "text",
    "text": "今日の作業内容を短くまとめて"
  },
  "start_at": "llm",
  "stop_after": "tts",
  "delivery": {
    "mode": "asset",
    "profile": "voice-wav"
  }
}
```

The preset may internally be:

```text
asr -> llm -> tts
```

but `start_at=llm` allows:

```text
text -> LLM -> TTS -> audio asset
```

Other useful selections:

```text
audio -> ASR                           stop_after=asr
audio -> ASR -> LLM                    stop_after=llm
audio -> ASR -> LLM -> TTS             stop_after=tts
text  -> TTS                            direct-tts preset
text  -> LLM                            text-only response
text  -> SFX                            direct SFX
text  -> Music                          direct BGM
```

The implementation should prefer named presets plus optional bounded stage overrides. Do not expose a general-purpose arbitrary code graph.

## 4. Pipeline request model

Normative shape:

```json
{
  "pipeline": "voice-assistant",
  "input": {
    "kind": "audio_grant",
    "grant_id": "grant:..."
  },
  "stages": [
    {"id": "asr", "kind": "speech.asr", "language": "auto"},
    {"id": "llm", "kind": "host.ai.text", "prompt_profile": "assistant"},
    {"id": "tts", "kind": "speech.tts", "voice_id": "voice:..."}
  ],
  "start_at": "asr",
  "stop_after": "tts",
  "delivery": {
    "mode": "asset",
    "profile": "voice-wav"
  }
}
```

Limits:

- maximum 8 stages in v1;
- unique stage ids;
- only known stage kinds;
- no client-supplied `_internal_*` fields;
- no raw filesystem paths;
- scoped grants/assets/streams only;
- explicit timeout/cancellation bounds;
- stage output size limits;
- final output type must match delivery mode.

## 5. Stage-local resource admission

This is mandatory.

Do **not** acquire one SonicForge GPU lease for the entire pipeline.

Bad:

```text
SonicForge acquires GPU for ASR
 -> holds it
 -> calls ControlDeck LLM
 -> ControlDeck LLM requests same GPU
 -> wait/deadlock/resource starvation
```

Correct:

```text
ASR
  acquire SonicForge stage lease
  load/run
  release/unload according to residency policy

LLM
  call ControlDeck /addon-runtime/sonic-forge/ai/complete
  ControlDeck owns its own LLM admission
  call /ai/release when the AI stage is complete

TTS
  acquire SonicForge stage lease
  load/run
  release according to policy
```

CPU-only stages such as the default Stable Audio 3 Small-SFX route do not acquire GPU resources.

The parent pipeline remains one durable SonicForge Job while resource leases are stage-local.

## 6. Durable vs live execution

Two execution classes share the same typed stage model.

### 6.1 Durable pipeline Job

Use for:

- OpenCode/agent generation;
- BGM/SE/SFX/voice assets;
- file ASR;
- long TTS;
- project export;
- localization/batches;
- anything that must survive browser closure.

The server stores:

- original request;
- compiled stage plan;
- current stage;
- stage results;
- input/output asset references;
- model/runtime provenance;
- resource evidence;
- failure/cancel state.

Browser state is never the owner of expensive work.

### 6.2 Live session

Use for:

- microphone ASR;
- push-to-talk;
- conversational ASR -> LLM -> TTS;
- low-latency TTS preview.

A live session has an explicit lifecycle:

```text
create session
 -> negotiate media format
 -> connect transport
 -> stream input
 -> stage events/transcript/text/audio
 -> stop/cancel
 -> optional finalize to durable transcript/audio asset
```

Live sessions may create durable assets at the end, but per-frame audio is not stored by default unless the user/project policy requests recording.

## 7. OpenCode / agent architecture

ControlDeck already exposes Add-on `agent_tools` through its Agent MCP bridge and can issue a scoped project output grant for eligible Add-ons.

Therefore SonicForge does **not** need a parallel independent MCP server.

### 7.1 Direct asset generation

Existing tools remain useful:

```text
sonic.generate
sonic.transcribe
sonic.inspect
sonic.pack
sonic.capabilities
```

OpenCode flow:

```text
1. discover sonic.generate
2. request BGM / SFX / voice
3. receive durable job_id
4. inspect job until terminal if necessary
5. receive asset_id
6. call control_deck.project_output_grant for target project directory
7. call sonic.pack with asset_id + grant_id
```

This never exposes the project's raw host path to SonicForge.

### 7.2 New `sonic.pipeline` agent tool

The explicit composed-pipeline requirement justifies one additive agent tool:

```text
sonic.pipeline
```

It creates a durable typed pipeline Job and normally returns quickly with:

```json
{
  "job_id": "job:...",
  "state": "queued"
}
```

Long music generation must not force the MCP call itself to remain open for the whole render.

### 7.3 Extend `sonic.inspect`

`sonic.inspect` should accept either:

```text
job_id
asset_id
pipeline/session id where appropriate
```

This avoids adding a separate status tool solely for polling.

### 7.4 Agent result discipline

Agent results remain bounded. Do not return binary audio inside MCP JSON.

Return references:

```json
{
  "job_id": "job:...",
  "asset_id": "asset:...",
  "kind": "music",
  "duration_ms": 90000,
  "mime_type": "audio/wav",
  "sha256": "..."
}
```

Binary material is fetched/exported through the asset/grant transport.

## 8. Delivery abstraction

Generation and delivery are separate concerns.

Define a final `DeliverySpec`:

```text
asset        durable SonicForge asset
project      Host scoped output grant
http         browser/mobile download
websocket    low-latency live stream
package      ZIP/directory asset pack + manifest
```

A model worker should never know whether the final user is a browser, OpenCode, Unity or a mobile phone.

## 9. PC/browser delivery

### 9.1 Durable download

Primary route:

```text
GET /addon/v1/assets/{asset_id}/content
```

Use `Content-Type`, `Content-Disposition`, content length and stable metadata.

PC users can Save As / download. Large generation requests remain asynchronous Jobs rather than long HTTP generation requests.

### 9.2 Export profiles

Recommended profiles:

```text
voice-wav
sfx-wav
game-wav
music-wav
lossless-flac
web-ogg
web-opus     only where the selected container/runtime path is validated
preview-aac  optional later
```

Do not force one codec across all use cases.

## 10. Mobile delivery

Mobile needs two modes.

### Asset mode

- durable HTTP asset download;
- browser share/open behavior where supported;
- compressed preview derivative optional;
- original lossless asset remains available.

### Live mode

Use WebSocket v1 through the existing ControlDeck Add-on proxy.

WebSocket control frames are JSON; audio data uses binary frames.

Example control flow:

```text
client -> {type:"session.start", input:{codec:"pcm_s16le", rate:16000, channels:1}}
client -> binary audio chunks
server -> {type:"asr.partial", text:"..."}
server -> {type:"asr.final", text:"..."}
server -> {type:"llm.text", text:"..."}
server -> {type:"audio.format", codec:"pcm_s16le", rate:24000, channels:1}
server -> binary TTS chunks
server -> {type:"session.done"}
```

WebSocket preserves ordering, but the standard WebSocket API lacks automatic backpressure. SonicForge therefore must implement:

- bounded inbound/outbound queues;
- maximum frame size;
- sequence/timing counters;
- high-water/low-water marks;
- explicit overflow policy;
- no unbounded buffering when a mobile browser backgrounds or slows down.

For microphone ASR v1, PCM signed 16-bit little-endian mono at 16 kHz is the simplest interoperable baseline. Alternate codecs are negotiated only after measured implementation.

## 11. WebRTC position

WebRTC is technically better suited to continuous low-latency conversational media because it is designed for real-time audio/video transport.

However the current ControlDeck Add-on proxy already supports HTTP/WebSocket and does not yet provide a generic WebRTC media relay contract. Making WebRTC mandatory now would introduce NAT/ICE/signaling/firewall/Tailscale and Host-boundary complexity.

Decision:

```text
v1 live transport: WebSocket
v2 optional transport: WebRTC after a generic Host-compatible design exists
```

Do not add a SonicForge-only privileged networking exception in ControlDeck merely to get WebRTC sooner.

## 12. Game-asset delivery profiles

Game workflows should consume source assets, not browser preview encodings.

### Generic game source

Recommended default:

```text
WAV PCM 16-bit
48 kHz unless project profile overrides
mono for voice/most positional SFX
stereo for BGM/ambience where appropriate
```

Retain an optional 24-bit/lossless intermediate when useful, but export engine-compatible source separately.

### Unity profile

Current Unity documentation supports importing WAV, Ogg Vorbis, MP3, AIFF and FLAC.

Recommended SonicForge source profile:

```text
Unity voice/SFX -> WAV PCM
Unity BGM       -> WAV or FLAC source; optional OGG delivery when project explicitly wants precompressed material
```

Let Unity's importer/project settings own final platform compression unless the project intentionally requests otherwise.

### Unreal profile

Current Unreal Engine 5.8 documentation accepts WAV, OGG, FLAC, AIFF, OPUS and MP3 and converts imported audio internally to 16-bit WAV. It recommends 16-bit input to avoid unnecessary 24-bit conversion behavior.

Recommended SonicForge profile:

```text
Unreal -> WAV PCM 16-bit
```

Project profiles can override sample rate/channel count.

## 13. Asset-pack format

For batches and external tools, support a pack:

```text
my-audio-pack/
  manifest.json
  voice/
  sfx/
  music/
```

`manifest.json` includes per asset:

- logical id;
- filename;
- kind;
- mime/codec/container;
- sample rate/channels/bit depth;
- duration;
- loop points if any;
- loudness/peak summary;
- language/voice metadata where applicable;
- SHA-256;
- provenance id;
- source job/pipeline id;
- engine/model/revision/license reference.

OpenCode project workflows should prefer direct Host output grants for known project directories. ZIP is useful for download/transfer, not the mandatory internal representation.

## 14. Output and input kinds

Stable pipeline boundary kinds:

```text
text
transcript
audio_grant
audio_asset
audio_stream
media_asset
media_package
```

Do not pass raw host filesystem paths.

An asset reference can be used as a later pipeline input without re-uploading through the browser.

## 15. Pipeline presets

Initial named presets:

```text
direct-tts
file-transcribe
voice-assistant
text-to-spoken-response
direct-sfx
direct-music
sfx-to-game-asset
music-to-game-asset
```

Examples:

### `voice-assistant`

```text
audio stream/grant
 -> ASR
 -> ControlDeck LLM
 -> TTS
 -> audio stream or asset
```

### `text-to-spoken-response`

```text
text
 -> ControlDeck LLM
 -> TTS
 -> audio asset/stream
```

### `direct-sfx`

```text
text
 -> optional prompt normalization
 -> SFX
 -> deterministic QA/process
 -> asset
```

### `direct-music`

```text
text
 -> Music
 -> deterministic QA/process
 -> asset
```

## 16. LLM stage ownership

The LLM stage uses ControlDeck's generic Add-on Runtime `ai.inference` contract.

SonicForge sends bounded text messages to:

```text
/{addon_id}/ai/complete
```

and requests release after the stage:

```text
/{addon_id}/ai/release
```

SonicForge does not import or directly control ControlDeck's LLM implementation.

The original user text and the LLM output are recorded in pipeline stage provenance according to privacy/project policy. Secrets/tokens are not recorded.

## 17. Streaming protocol v1

Namespace:

```text
/addon/v1/sessions
/addon/v1/sessions/{id}
/addon/v1/sessions/{id}/events
```

Creation is authenticated through the normal Add-on runtime boundary.

Suggested WebSocket event classes:

```text
session.hello
session.ready
input.format
input.end
asr.partial
asr.final
llm.delta
llm.final
audio.format
audio.chunk (binary payload)
stage.started
stage.completed
stage.failed
session.done
session.error
```

Binary frames are only accepted when the negotiated session state expects audio.

Protocol limits are explicit and versioned.

## 18. Preview derivatives vs masters

A compressed/mobile preview must not replace the production asset.

Asset lineage:

```text
master WAV/FLAC
  -> preview derivative OGG/AAC/Opus
  -> game export derivative
```

Each derivative references the master/provenance chain.

This prevents a low-bitrate mobile preview from accidentally becoming the project's source asset.

## 19. Failure and resume semantics

Durable pipeline:

- completed stages remain recorded;
- retry starts at the failed stage when inputs/revisions are unchanged;
- model/runtime revision changes invalidate downstream cache as needed;
- cancel stops the current stage and releases its resources;
- parent Job becomes canceled/failed/partial explicitly.

Live session:

- no silent infinite reconnect;
- reconnect token/session id is bounded and short-lived;
- final committed transcript/assets are authoritative;
- ephemeral partial ASR may be lost and regenerated after reconnect.

## 20. Security rules

- no raw filesystem paths from OpenCode/browser/mobile;
- project writes only through scoped Host output grants;
- service tokens never exposed to worker/model code unless required by a bounded Host call;
- workers receive only stage inputs they need;
- live stream sizes/rates/connections are bounded;
- agent/MCP results never contain binary media;
- voice-clone rights gate still applies inside pipelines;
- model license/terms routing still applies inside pipelines;
- pipeline composition cannot bypass capability grants.

## 21. Why this is better than adding many endpoints

Rejected approach:

```text
/asr-llm-tts
/text-llm-tts
/asr-llm
/text-tts
/asr-only
/music-to-unity
/sfx-to-unreal
...
```

That produces combinatorial API growth and makes contracts impossible to evolve cleanly.

Adopted approach:

```text
typed stages
+ named presets
+ start_at / stop_after
+ independent DeliverySpec
```

This provides the requested flexibility without encoding every combination as a permanent endpoint.

## 22. Implementation slices

### PIPE-0 — contract

- Pydantic + JSON Schema for pipeline/stages/input/delivery;
- type compiler;
- preset registry;
- validation negative tests;
- no heavy model change.

### PIPE-1 — durable text pipeline

Implement/test with fake workers:

```text
text -> TTS
text -> Host LLM -> TTS
text -> SFX
text -> Music
```

Use stage-local resource ownership.

### PIPE-2 — file audio pipeline

```text
audio grant/asset -> ASR -> text
audio grant/asset -> ASR -> LLM -> text
audio grant/asset -> ASR -> LLM -> TTS -> asset
```

### PIPE-3 — Agent/OpenCode

- add `sonic.pipeline`;
- extend `sonic.inspect` to jobs/assets;
- test project output grant -> `sonic.pack`;
- long-running jobs return references rather than binary/waiting indefinitely.

### PIPE-4 — WebSocket session

- session state machine;
- negotiated PCM v1;
- bounded queues/backpressure policy;
- ASR partial/final;
- optional LLM/TTS stages;
- browser/mobile reconnect tests.

### PIPE-5 — delivery profiles

- WAV/FLAC/OGG encoders through validated argv/library paths;
- master/preview derivative lineage;
- Unity/Unreal/generic profiles;
- pack manifest/export.

### PIPE-6 — optional WebRTC research

Only after WebSocket v1 is measured and a generic ControlDeck-compatible signaling/media boundary is designed.

## 23. Acceptance criteria

The architecture is not complete until tests demonstrate at least:

1. incompatible stage types are rejected before work starts;
2. start/end selection works for direct TTS and LLM->TTS;
3. ASR->LLM->TTS releases GPU ownership between heterogeneous stages;
4. OpenCode can create BGM/SFX/voice and export to a scoped project directory;
5. long jobs survive browser/agent disconnection;
6. WebSocket input cannot buffer without bound;
7. mobile can send microphone audio and receive transcript/audio through the Host path;
8. PC can download the durable master;
9. Unity/Unreal profiles produce importable source audio;
10. preview derivatives never replace masters;
11. all assets retain model/license/provenance evidence.
