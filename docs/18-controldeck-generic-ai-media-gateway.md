# ControlDeck Generic AI / Media Gateway Integration

Status: normative SonicForge integration design  
Date: 2026-08-25

## 1. Decision

SonicForge follows the same Host-boundary philosophy already used by MediaForge.

ControlDeck owns the generic AI/media **control plane**. SonicForge owns speech/audio/music domain execution.

This does **not** move Qwen, Whisper, Stable Audio, ACE-Step, voice semantics, audio profiles or SonicForge routing into ControlDeck.

## 2. Shared ControlDeck control plane

SonicForge consumes generic Host primitives:

```text
ControlDeck Generic AI / Media Gateway
├─ scoped Add-on runtime auth
├─ Host Jobs / progress / cancel / active-job credential refresh
├─ Resource Broker / queue / lease / lease credential refresh
├─ Host AI router
│  ├─ text.generate
│  └─ vision.analyze
├─ provider-neutral SSE text streaming
├─ explicit Host AI release
├─ renewable AI residency holds
├─ scoped input grants
├─ project/output grants + commit receipt
├─ Agent MCP projection (OpenCode etc.)
├─ Workflow executor projection
├─ embedded HTTP relay
├─ embedded WebSocket relay
└─ generic paired Device Relay
```

SonicForge owns:

```text
TTS / ASR / SFX / music engines
voice profiles / rights / pronunciation
Localization Studio
Typed Media Pipeline
audio/live-session semantics
meeting / translation behavior
asset/audio delivery profiles
SonicForge provenance and QA
sonic-edge/1 protocol semantics
```

## 3. Gateway discovery

ControlDeck Gateway 1.4 exposes:

```text
GET /api/v1/addon-runtime/sonic-forge/gateway/capabilities
```

SonicForge uses this versioned discovery document to learn which generic Host facilities are actually granted and available.

Compatibility rules:

- use Gateway discovery when present;
- if an older Host returns 404, project existing service-token grants and `/ai/capabilities` into the local compatibility shape;
- discovery is descriptive, not authorization;
- every execution endpoint remains authoritative for its own capability/scope;
- reject a response that changes `addon_id` or uses an unsupported major protocol version;
- a feature that genuinely requires a newer Host primitive must report unavailable rather than silently weakening the boundary.

## 4. MediaForge alignment

MediaForge already uses the same generic Host families for:

- Host Jobs;
- Resource Broker;
- scoped grants/outputs;
- Host AI capability/complete/release;
- Agent/OpenCode execution.

MediaForge currently does **not** request `devices.relay` or declare a Device Relay. Device Relay therefore remains an additive generic Host primitive and does not alter current MediaForge behavior.

The design test for every ControlDeck addition remains:

> Would this primitive still make sense for MediaForge, Blender/CAD or another Add-on?

If not, keep the behavior in SonicForge.

## 5. Typed Media Pipeline execution model

SonicForge owns typed stages:

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
audio -> audio.process -> audio
```

The caller may select `start_at` and `stop_after` where media types remain valid. Invalid chains such as `LLM -> ASR` are rejected before execution.

The durable runner is implemented and is also exposed to agents through `sonic.pipeline` using the existing ControlDeck Agent MCP.

## 6. Resource admission and residency

### 6.1 Batch / durable pipelines

Heterogeneous batch pipelines use stage-local admission:

```text
ASR worker lease
 -> execute
 -> release

Host LLM
 -> ControlDeck performs its own admission
 -> execute
 -> release when the turn is finished

TTS worker lease
 -> execute
 -> release
```

A single Add-on lease is never held blindly around ASR -> Host LLM -> TTS.

### 6.2 Live voice sessions

Low-latency voice is different because repeated cold loads are unacceptable.

During an active live session, SonicForge may keep ASR/TTS workers resident with matching session-scoped Broker leases while ControlDeck keeps its selected LLM warm using a renewable AI residency hold.

```text
live session start
 -> LLM residency hold (Host-owned)
 -> persistent ASR + lease
 -> persistent TTS + lease when capacity permits

turn 1
turn 2
turn 3
...

session end
 -> stop workers
 -> release leases
 -> release LLM hold
```

Residency is never permission to overcommit VRAM. If all residents do not fit, Broker accounting remains authoritative and SonicForge must explicitly evict/reload, route or queue rather than self-deadlock or OOM.

While an LLM residency hold is active, SonicForge does not call `ai.release` after every live turn.

## 7. Long-running credential behavior

The normal Add-on service bearer remains short-lived. Its TTL is an internal safety mechanism, not a user-visible processing-duration limit.

Long-running active work can receive same-scope replacement credentials from an authoritative liveness object:

- active Host Job credential refresh;
- active Resource Broker lease refresh;
- active AI residency hold heartbeat.

This allows long setup/localization/meeting/live operations without creating an unlimited bearer credential.

If SonicForge dies, the corresponding heartbeat/renew loops stop and Host TTL cleanup returns the system to normal policy.

## 8. Host AI streaming

For voice chat, translation and other latency-sensitive flows, SonicForge uses provider-neutral Host SSE streaming.

```text
POST /api/v1/addon-runtime/sonic-forge/ai/stream
```

ControlDeck owns provider/model choice and admission. SonicForge receives only the public content stream required by the task. Private/thinking/reasoning chunks are not projected to the Add-on.

## 9. OpenCode and coding agents

OpenCode does not connect to a private SonicForge MCP server.

Preferred path:

```text
OpenCode
 -> ControlDeck Agent MCP
 -> SonicForge agent contribution
 -> durable Host/SonicForge Job
 -> direct generation or Typed Pipeline
 -> Asset
 -> optional project output grant
 -> commit receipt
```

Current agent tools include capability inspection, generation, transcription, asset inspection, project placement and `sonic.pipeline`.

## 10. Delivery and receiving model

Generation and delivery are separate concerns.

### 10.1 Durable Asset

Default for generated BGM/SE/voice and processed audio. The Asset stores provenance and QA.

### 10.2 PC/browser download

```text
asset -> HTTP content route
```

Canonical editing/master output remains WAV where appropriate; OGG/MP3 are derived delivery profiles.

### 10.3 ControlDeck project/game asset

```text
asset -> scoped project output grant -> commit -> receipt
```

Game-specific audio semantics remain in SonicForge; ControlDeck only guards the destination.

### 10.4 Mobile/PC live audio

Use WebSocket for current low-latency half-duplex/live-session traffic. WebRTC remains optional future work only if measured full-duplex/AEC requirements justify it.

## 11. M5 / edge client paths

SonicForge publishes the server contract only. Device firmware/client implementation is outside this repository.

Two paths coexist intentionally.

### 11.1 Direct trusted LAN / Tailscale

```text
existing edge client
 -> SonicForge /addon/v1/live/ws
```

Use this for local ASR/TTS/PTT/dictation when no Host-owned capability is required. Default `trusted-network` policy permits local/private/non-global peers without user-facing authentication.

This is not permission to expose an unauthenticated SonicForge service to the public Internet.

### 11.2 Optional ControlDeck Device Relay

```text
existing edge client
 -> ControlDeck paired Device Relay
 -> Host-minted SonicForge service identity
 -> SonicForge live pipeline
```

Use this when the flow needs Host-owned functions such as ControlDeck LLM routing or user-scoped Host policy.

The device never receives a browser cookie or Add-on service token. It receives only a relay/device-scoped credential.

Device credentials use the normal ControlDeck Add-on maximum TTL policy (currently 8 hours). There is no special 30-day device-token exception. A successful reconnect may receive a rotated same-scope replacement.

## 12. Low-latency voice and translation

Current voice path:

```text
mic PCM
 -> RAM-first spool
 -> persistent ASR
 -> ControlDeck SSE LLM
 -> speakable clause chunker
 -> persistent TTS
 -> bounded ordered audio-delivery queue
 -> progressive WebSocket playback
```

LLM intake, TTS synthesis and audio delivery overlap. Chunk N+1 may be synthesized while chunk N is being delivered, while one ordered sender preserves client frame order.

Simultaneous translation is a pipeline preset:

```text
speech
 -> ASR
 -> ControlDeck streaming translation
 -> target-language TTS
 -> progressive playback
```

## 13. Meeting / dictation

Long sessions are not one huge PTT buffer.

```text
continuous PCM
 -> RAM-first bounded processing chunks
 -> persistent ASR
 -> finalized timestamped segment -> SQLite
 -> optional translation
 -> repeat without total duration limit
 -> optional hierarchical final summary
```

Processing chunk size is not a meeting duration limit. Finalized transcript remains durable even if the transport disconnects.

## 14. Prompt normalization through Host AI

SonicForge may use Host `text.generate` to normalize a Japanese prompt for an audio engine that performs better with English acoustic conditioning.

```text
Japanese SFX intent
 -> Host text.generate
 -> concise English acoustic description
 -> release Host AI when no residency hold is needed
 -> Stable Audio worker
```

Both the original prompt and engine-conditioning prompt remain in provenance.

## 15. Implemented status

Implemented on SonicForge / ControlDeck branches, pending local target validation:

- typed pipeline compile + durable runner;
- `sonic.pipeline` Agent tool;
- stage-local batch admission;
- Host AI complete/stream/release;
- LLM residency hold + heartbeat;
- long Host Job credential refresh;
- persistent ASR/TTS live workers;
- progressive LLM -> TTS with overlapped ordered delivery;
- meeting/dictation session model;
- `sonic-edge/1` server framing;
- generic Device Relay in ControlDeck Gateway 1.4;
- trusted-LAN direct local path;
- RAM-first spool with disk fallback.

Real heavy-model, AMD/ROCm, browser and existing-device E2E evidence remains `NOT TESTED` until `SF受入確認` runs on the target machine.

## 16. Non-goals

- moving SonicForge engines into ControlDeck;
- giving edge devices ControlDeck browser cookies or Add-on service tokens;
- adding a SonicForge-only long-lived credential exception to ControlDeck;
- exposing an unauthenticated SonicForge endpoint to arbitrary global/public peers by default;
- holding one batch GPU lease while waiting through unrelated Host LLM work;
- silently overcommitting VRAM to keep every live model resident;
- forcing every generated Asset through WebSocket;
- forcing every live response to become a durable stored Asset;
- adding model names to normal OpenCode/public task contracts;
- maintaining M5 firmware inside SonicForge.
