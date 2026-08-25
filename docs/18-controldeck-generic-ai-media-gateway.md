# ControlDeck Generic AI / Media Gateway Integration

Status: normative SonicForge integration design  
Date: 2026-08-25

## 1. Decision

SonicForge adopts the same host-boundary philosophy already used by MediaForge.

ControlDeck owns a generic AI/media **control plane**; SonicForge owns audio-domain execution.

This is not a request to move Qwen, Whisper, Stable Audio, ACE-Step or voice/audio semantics into ControlDeck.

## 2. Shared ControlDeck control plane

SonicForge consumes these generic Host primitives:

```text
ControlDeck Generic AI / Media Gateway
├─ scoped Add-on runtime auth
├─ Host Jobs / progress / cancel
├─ Resource Broker / queue / lease / residency
├─ Host AI router
│  ├─ text.generate
│  └─ vision.analyze
├─ explicit Host AI release
├─ scoped input grants
├─ project/output grants + commit receipt
├─ Agent MCP projection (OpenCode etc.)
├─ Workflow executor projection
├─ embedded HTTP relay
├─ embedded WebSocket relay
└─ generic Device Session relay (future Host primitive)
```

SonicForge owns:

```text
TTS / ASR / SFX / music engines
voice profiles / rights / pronunciation
Localization Studio
Typed Media Pipeline
live audio semantics
M5 wake/VAD/AEC/turn behavior
asset/audio format profiles
SonicForge provenance and QA
```

## 3. Gateway discovery

New ControlDeck hosts expose:

```text
GET /api/v1/addon-runtime/sonic-forge/gateway/capabilities
```

SonicForge's Host client supports this versioned discovery document.

Compatibility rule:

- if Gateway v1 exists, use it;
- if the Host returns 404, project the existing service-token grants and `/ai/capabilities` response into the same local shape;
- never treat discovery as authorization; the dedicated execution endpoint remains authoritative;
- reject a gateway response that changes `addon_id` or uses an unsupported major protocol version.

This permits SonicForge to work against current ControlDeck while the generic gateway consolidation is merged independently.

## 4. MediaForge alignment

MediaForge already uses the same generic Host endpoint families for:

- Host Jobs
- Resource Broker
- scoped grants/outputs
- Host AI capabilities/complete/release
- Agent/OpenCode execution

SonicForge intentionally follows this rather than inventing a second audio-specific Host gateway.

The generic Host test remains:

> Would the primitive remain useful if SonicForge were replaced with MediaForge, Blender/CAD or another Add-on?

If not, keep it in SonicForge.

## 5. Typed Media Pipeline execution model

SonicForge owns typed pipeline stages:

```text
speech.asr      audio -> text
host.ai.text    text  -> text
speech.tts      text  -> audio
audio.sfx       text  -> audio
music.generate  text  -> audio
audio.process   audio -> audio
```

Typical pipelines:

```text
audio -> ASR -> Host LLM -> TTS -> audio
text  -> Host LLM -> TTS -> audio
text  -> TTS -> audio
text  -> SFX -> audio
text  -> Music -> audio
```

The user/agent may choose `start_at` and `stop_after` where the input/output media types remain valid.

Examples:

```text
start at LLM, stop after TTS
  text input -> generated reply audio

start at ASR, stop after LLM
  audio input -> generated reply text

start at TTS, stop after TTS
  text input -> speech audio
```

`LLM -> ASR` is rejected because ASR requires audio input.

## 6. Stage-local Resource Broker admission

A pipeline does not hold one GPU lease for its entire lifetime.

Required ordering:

```text
ASR
  -> request SonicForge ASR lease
  -> execute
  -> release

Host LLM
  -> ControlDeck AI router performs its own Broker admission
  -> complete
  -> SonicForge requests Host `ai.release` when the AI turn is finished

TTS
  -> request SonicForge TTS lease
  -> execute
  -> release
```

The same pattern applies when a pipeline contains SFX/music stages.

Benefits:

- avoids deadlock between Add-on GPU work and Host LLM GPU work;
- lets ControlDeck choose which resident workload yields;
- exposes accurate stage resource telemetry;
- makes long-lived voice sessions coexist with other ControlDeck workloads.

## 7. OpenCode and coding agents

OpenCode should not connect directly to SonicForge over a private MCP server.

Preferred path:

```text
OpenCode
 -> ControlDeck Agent MCP
 -> SonicForge agent contribution
 -> durable Host/SonicForge Job
 -> Typed Pipeline or direct generation task
 -> Asset
 -> optional ControlDeck project output grant
 -> commit receipt
```

SonicForge capabilities include direct asset generation for:

- voice/TTS
- transcription
- SFX/SE
- ambience
- BGM/music
- asset inspection
- project placement

A `sonic.pipeline` agent tool is justified once the server-side runner is complete because the user has an explicit multi-stage start/stop requirement. It must not be exposed before execution exists.

## 8. Delivery and receiving model

Generation and delivery are separate concerns.

### 8.1 Durable asset

Default for generated BGM/SE/voice and processed audio.

Produces a SonicForge asset ID with provenance and QA.

### 8.2 PC download

```text
asset -> authenticated HTTP download
```

Use WAV/FLAC for editing/master assets and OGG/MP3 only when a delivery profile requests them.

### 8.3 ControlDeck project/game asset

```text
asset -> scoped project output grant -> commit -> receipt
```

Game profiles belong to SonicForge, for example:

- Unity-oriented WAV/OGG profile
- Unreal-oriented WAV profile
- Godot-oriented WAV/OGG profile
- generic web/mobile MP3/OGG profile

ControlDeck does not know engine-specific audio semantics; it only guards the project destination.

### 8.4 Mobile/PC live audio

Use the existing embedded WebSocket relay for bounded session/event traffic when WebSocket is sufficient.

### 8.5 M5 edge device

M5 devices must not receive Host browser cookies, Add-on service tokens, or direct access to the loopback SonicForge origin.

Target path:

```text
M5
 -> ControlDeck paired Device Session (future generic Host primitive)
 -> bounded relay scoped to SonicForge session
 -> SonicForge live pipeline
```

Until generic Device Session exists, M5 live access is not declared production-ready.

## 9. Voice chat presets

### 9.1 Push-to-talk v1

```text
M5/mobile mic
 -> bounded PCM stream
 -> ASR
 -> Host LLM
 -> TTS
 -> bounded playback stream
```

This is the first production target.

### 9.2 Wake/VAD v1.1

Device-side wake/VAD chooses when an utterance begins/ends. Server still owns ASR/LLM/TTS.

### 9.3 Full duplex v2

AEC + barge-in + cancel-current-TTS.

Do not make full duplex mandatory for initial M5 support.

## 10. Live transport framing

SonicForge `sonic-edge/1` binary framing includes:

- protocol magic/version
- mic vs speaker stream
- sequence number
- sample clock
- payload length
- bounded payload size

A bounded queue prevents unlimited latency growth.

Policy distinction:

- microphone uplink overflow should normally terminate/restart the utterance rather than silently losing semantic input;
- playback downlink may discard stale frames after a newer turn supersedes them.

## 11. Prompt normalization through Host AI

Some audio models are stronger with English conditioning text. SonicForge may use ControlDeck `text.generate` to normalize/translate a Japanese user prompt for an engine while retaining the original intent.

Example:

```text
Japanese SFX intent
 -> Host text.generate: concise English acoustic description
 -> Host ai.release
 -> Stable Audio worker
```

The original prompt and engine-conditioning prompt are both retained in provenance. This is an orchestration detail, not a public requirement for users to write English prompts.

## 12. Migration and compatibility

No existing MediaForge or SonicForge execution endpoint is renamed by this design.

Gateway discovery is additive.

SonicForge must remain usable with an older Host by falling back to the existing endpoint set where possible.

New features that genuinely require a new Host primitive, especially paired Device Sessions, must advertise `unavailable` rather than opening an insecure direct-LAN workaround.

## 13. Implementation order

### PIPE-0 — complete

- typed pipeline request schema
- text/audio stage type checking
- start/stop compile rules
- delivery mode schema
- M5/device descriptor schema
- bounded `sonic-edge/1` audio frame helpers

### GATE-0 — implemented on branches, not E2E validated

- ControlDeck generic gateway discovery branch
- SonicForge discovery client with legacy projection

### PIPE-1 — next

- durable server-side pipeline Job runner
- stage-local resource admission
- Host AI complete/release stage
- ASR/TTS/SFX/music task adapters
- asset/text terminal result
- pipeline provenance

### PIPE-2

- expose `sonic.pipeline` through Agent MCP
- add workflow projection only if a concrete workflow need justifies it
- direct project placement delivery

### LIVE-1

- authenticated browser live-session WebSocket
- PTT turn state
- bounded PCM framing
- streaming/session ASR/TTS integration

### HOST-DEVICE-1

Separate ControlDeck PR:

- generic device pairing/session contract
- revocation and short-lived token
- Add-on/session target scope
- rate/byte/session limits
- bounded WebSocket relay

### M5-1

- CoreS3/PTT firmware integration
- device capability negotiation
- PCM 16 kHz mono uplink baseline
- negotiated playback output
- display/turn-state events

### M5-2

- WakeNet/VAD
- optional AEC
- barge-in/full-duplex only after measured stability

## 14. Non-goals

- moving SonicForge engines into ControlDeck;
- giving M5 devices direct ControlDeck browser credentials;
- exposing SonicForge loopback service to the LAN as the normal architecture;
- holding a GPU lease while waiting for Host LLM inference;
- forcing every generated asset through WebSocket;
- forcing every live response to become a durable stored asset;
- adding model names to normal OpenCode/public task contracts.
