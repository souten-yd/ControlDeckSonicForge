# M5 Edge Agent and Voice Chat Architecture

Status: Normative design and implementation plan  
Date: 2026-08-25

## 1. Goal

SonicForge must support M5Stack-class embedded devices as first-class thin clients for:

```text
push-to-talk voice agent
wake-word voice agent
ASR-only dictation
ASR -> ControlDeck LLM -> text
ASR -> ControlDeck LLM -> TTS -> speaker
text/status notifications -> local display
remote-generated voice/SFX/BGM -> device playback where appropriate
```

M5 devices are **edge I/O clients**, not hosts for Qwen/Whisper/ACE-Step/Stable Audio generation.

The heavy path remains:

```text
M5 microphone/UI
 -> secure ControlDeck device gateway
 -> SonicForge live session
 -> ASR
 -> ControlDeck AI router
 -> TTS
 -> SonicForge live session
 -> M5 speaker/display
```

## 2. Hardware tiers

### Tier A — ESP32-S3 audio-capable M5

Examples include CoreS3/CoreS3-Lite/StickS3-class devices.

CoreS3 currently provides:

- ESP32-S3 dual-core 240 MHz;
- 8 MB PSRAM / 16 MB Flash;
- 2.4 GHz Wi-Fi;
- ES7210 dual-microphone input;
- I2S speaker path;
- touchscreen/display.

This tier can target:

- local audio front end;
- VAD;
- WakeNet;
- optional AEC;
- WebSocket streaming;
- richer touch/status UI.

### Tier B — older/lower-resource ESP32 M5

Use conservative behavior:

- push-to-talk first;
- half-duplex playback;
- raw PCM or the simplest validated codec;
- no assumption that local Wake/AEC models fit or perform well;
- smaller display/state UI.

Device behavior is selected by capabilities, not product-name string checks.

## 3. Device capability handshake

On session creation/connect, device advertises a bounded descriptor:

```json
{
  "protocol": "sonic-edge/1",
  "device": {
    "class": "m5",
    "model": "core-s3",
    "firmware": "0.1.0"
  },
  "audio": {
    "input": [
      {"codec":"pcm_s16le","rate":16000,"channels":1,"frame_ms":20}
    ],
    "output": [
      {"codec":"pcm_s16le","rate":24000,"channels":1,"frame_ms":20}
    ],
    "aec": true,
    "vad": true,
    "wake": true
  },
  "ui": {
    "display": true,
    "touch": true,
    "buttons": 2
  },
  "memory": {
    "psram_bytes": 8388608
  }
}
```

The server returns the selected subset. Unsupported features are disabled rather than guessed.

## 4. Audio baseline

### Uplink baseline

```text
PCM signed 16-bit little-endian
16 kHz
mono
20 ms frames
320 samples / frame
640 bytes / audio frame
```

Raw payload rate is about 256 kbit/s before WebSocket/TCP/IP overhead, acceptable on ordinary Wi-Fi/LAN/Tailscale for the first implementation.

Why this baseline:

- aligns with ESP-SR/WakeNet/MultiNet 16 kHz 16-bit mono expectations;
- no codec dependency required on the first firmware;
- easiest to debug for microphone timing/dropout problems;
- avoids masking capture bugs behind a compressed codec.

### Downlink baseline

TTS may negotiate:

```text
PCM s16le mono 24 kHz
```

or another model-native/validated rate. The device must not assume uplink and downlink rates are identical.

### Optional compressed transport

Opus or another low-bitrate speech codec is valuable for remote/mobile use, but is **not v1 mandatory**.

Promotion requires measurement of:

- ESP32-S3 encode/decode CPU;
- PSRAM/internal RAM use;
- latency;
- packet loss behavior;
- library/build/license maintenance;
- battery impact.

Do not sacrifice microphone reliability merely to reduce LAN bandwidth.

## 5. Device-side audio front end

ESP-SR provides a suitable architecture for ESP32-S3 edge preprocessing:

```text
microphone(s)
 -> AFE
    -> optional AEC
    -> noise suppression
    -> VAD
    -> optional WakeNet
 -> normalized PCM stream
```

SonicForge should not require every firmware to enable every AFE function.

### Recommended modes

#### Mode 1 — Push-to-Talk, half-duplex

```text
button/touch press
 -> capture/stream
release or local VAD end
 -> stop uplink
 -> receive/play TTS
```

This is the v1 default.

Advantages:

- simplest echo behavior;
- low false-trigger risk;
- easiest failure recovery;
- suitable for older M5 devices.

#### Mode 2 — Wake + VAD, half-duplex

```text
WakeNet
 -> session/input start
 -> VAD speech
 -> VAD end-of-speech
 -> ASR/LLM/TTS
 -> playback
 -> return to wake state
```

Use only when wake model/firmware is actually validated on that device.

#### Mode 3 — Full duplex / barge-in

```text
speaker playback reference
 + microphone input
 -> AEC
 -> VAD
 -> user interruption
 -> server cancels/pauses current TTS
 -> ASR/LLM/TTS next turn
```

This is a later capability. It needs device AEC plus server-side interruption semantics and must be tested under real speaker volume/room conditions.

## 6. Local recognition policy

Do not move full ASR to M5 merely because ESP-SR supports command recognition.

MultiNet is useful for small offline commands, but current official ESP32-S3 support is Chinese/English command-word recognition, not general Japanese ASR.

Therefore:

```text
Japanese free-form speech -> SonicForge ASR
English free-form speech  -> SonicForge ASR
small offline emergency/device commands -> optional local command table
```

Examples of optional local-only commands:

- stop playback;
- cancel;
- mute;
- reconnect;
- volume up/down.

These should also have physical-button equivalents where practical.

## 7. M5 agent session presets

### `m5-voice-agent`

```text
audio_stream
 -> ASR
 -> ControlDeck LLM
 -> TTS
 -> audio_stream
```

### `m5-dictation`

```text
audio_stream
 -> ASR
 -> text event
```

### `m5-ask-text`

```text
text/device input
 -> ControlDeck LLM
 -> TTS or text display
```

### `m5-notify`

```text
text/event
 -> optional TTS
 -> display + speaker
```

All presets use the same typed pipeline stage rules from `16-pipeline-agent-and-delivery-architecture.md`.

## 8. Turn state machine

Device-visible states:

```text
DISCONNECTED
CONNECTING
IDLE
LISTENING
TRANSCRIBING
THINKING
SPEAKING
ERROR
```

The server is authoritative for pipeline state; the device is authoritative for immediate local I/O state.

Example transition:

```text
IDLE
 -> PTT
 -> LISTENING
 -> input.end
 -> TRANSCRIBING
 -> THINKING
 -> SPEAKING
 -> IDLE
```

Display/LED/animation should map to these semantic states rather than engine/model names.

## 9. WebSocket protocol

M5 uses the same SonicForge live-session protocol family as mobile/PC clients, with a device capability profile.

Control messages are JSON text frames.
Audio is binary frames.

Example:

```text
server -> session.hello
client -> device.capabilities
server -> session.ready + negotiated formats
client -> input.start
client -> binary PCM frames
server -> asr.partial
client -> input.end
server -> asr.final
server -> llm.final
server -> audio.format
server -> binary TTS frames
server -> turn.done
```

### Binary frame envelope

For v1, prepend a tiny versioned header rather than relying on WebSocket message order alone for diagnostics:

```text
magic/version
stream kind
sequence number
timestamp/sample clock
payload length
PCM payload
```

Requirements:

- monotonically increasing sequence;
- gap detection;
- maximum payload/frame;
- no unbounded reassembly;
- explicit format renegotiation before format changes.

## 10. Buffering and backpressure

The embedded client must remain bounded.

Recommended starting values, subject to measurement:

```text
capture DMA/ring      100-300 ms
network outbound      <= 500 ms
playback jitter       100-250 ms
hard queue maximum    <= 1 s audio per direction
```

When a limit is exceeded:

- never keep allocating;
- increment drop/overrun metrics;
- prefer dropping stale live partial audio over crashing;
- for microphone uplink, a sustained overflow should terminate the turn with an explicit error because ASR integrity is compromised.

The exact thresholds become device-profile evidence, not universal constants.

## 11. Reconnect

M5 must tolerate Wi-Fi roam/drop and server restart.

Rules:

- exponential backoff with jitter;
- bounded retry ceiling;
- device remains locally usable for mute/volume/state;
- do not replay already-finalized microphone turns automatically;
- unfinished ephemeral turn may be abandoned and restarted;
- durable assets/jobs remain retrievable by id;
- after reconnect, request authoritative session/device state.

## 12. Device authentication: generic Host gate required

Do **not**:

- store a ControlDeck user password on M5;
- store browser cookies on M5;
- expose an Add-on service token to firmware;
- bind SonicForge service to `0.0.0.0` merely for M5;
- rely only on LAN/Tailscale source address as authentication.

Current Add-on `addon-frame` is designed for authenticated browser sessions. M5 needs a device-native identity.

Track:

```text
HOST-GATE-DEVICE-001
Generic ControlDeck Device Session / Add-on relay
```

This should be reusable by future embedded/mobile clients and other Add-ons, not SonicForge-specific Host code.

## 13. Proposed generic pairing model

### Device identity

On first boot the device generates a key pair and stores the private key in device persistent storage. Prefer hardware-backed/secure storage where supported by the chosen firmware platform.

The private key never leaves the device.

### Pairing

```text
1. user opens ControlDeck Device Pairing UI
2. ControlDeck creates short-lived one-time pairing code/QR
3. M5 submits pairing code + device public key + capability summary
4. user sees device name/fingerprint and approves
5. Host stores device public key, owner, allowed Add-ons/scopes
6. pairing code expires and cannot be reused
```

### Session authentication

```text
M5 -> Host challenge request
Host -> nonce
M5 -> signature(nonce + context)
Host verifies registered public key
Host -> short-lived device session token
M5 -> generic Add-on device relay WebSocket
Host -> SonicForge loopback with scoped service identity
```

Scopes should be narrow, for example:

```text
addon:sonic-forge
live.audio
live.text
assets.read:own-session
```

Project write/export is not granted by default to an M5 voice client.

## 14. Device relay

Preferred Host shape conceptually:

```text
/device-gateway/{addon_id}/...
```

The Host:

- authenticates device session;
- checks user/device/Add-on enablement;
- applies rate/connection limits;
- proxies HTTP/WebSocket only to the Add-on's approved loopback runtime;
- injects a short-lived Add-on runtime identity;
- strips caller-supplied Host auth headers;
- audits device/session activity.

This mirrors the security strengths of `addon-frame` without pretending an MCU is a browser.

## 15. LAN, Tailscale and Internet use

### LAN

Works with the same secure Host endpoint. LAN location is not authentication.

### Tailscale

Strongly suitable for remote personal M5 deployments because routing remains private, but application/device authentication is still required.

### Public Internet

Only after:

- HTTPS/WSS;
- generic Host device auth;
- rate limiting;
- revocation;
- explicit deployment guidance.

Do not directly publish port 9140.

## 16. M5 firmware architecture

Recommended modules:

```text
app_state
wifi_manager
device_identity
pairing_client
sonic_ws_client
audio_capture
audio_playback
audio_frontend
wake_manager
ui_renderer
metrics
ota
```

Tasks/cores must be designed so slow network/UI operations cannot block audio capture DMA.

A practical queue topology:

```text
I2S capture
 -> fixed audio ring
 -> AFE/VAD/Wake task
 -> network TX queue

network RX
 -> fixed playback jitter buffer
 -> I2S speaker

control/event queue
 -> UI state renderer
```

No dynamic allocation in the hot per-frame path where avoidable.

## 17. Device metrics

Expose bounded diagnostics to SonicForge/ControlDeck:

- firmware version;
- uptime;
- Wi-Fi RSSI;
- free heap/PSRAM;
- capture frame count;
- dropped capture frames;
- outbound queue high water;
- playback underruns;
- reconnect count;
- last round-trip latency;
- AFE mode;
- negotiated audio format.

Do not upload raw microphone audio as telemetry.

## 18. Latency budget

For a natural PTT assistant, measure separately:

```text
capture end detection
network uplink
ASR first/final result
LLM first/final text
TTS first audio
network downlink
playback start
```

Target architecture should support streaming partial stages, but correctness first:

- v1 may wait for final ASR and complete short LLM text before TTS;
- later versions may stream LLM -> streaming TTS once cancellation and sentence-boundary behavior are robust.

Do not optimize aggregate latency without knowing which stage dominates.

## 19. Streaming LLM -> TTS policy

Later optimization:

```text
ASR final
 -> LLM token stream
 -> sentence/clause chunker
 -> TTS chunk queue
 -> audio playback
```

Requirements before enabling:

- bounded text/TTS queue;
- correct Japanese sentence segmentation;
- cancellation invalidates queued future audio;
- no speaking obsolete text after barge-in;
- voice continuity across chunks;
- punctuation/prosody quality measurement.

Initial durable `text -> LLM -> TTS` may use complete text first for simplicity.

## 20. Local fallback behavior

If server is unreachable, M5 should not hallucinate that an agent response succeeded.

Useful offline functions:

- show disconnected state;
- reconnect;
- local mute/volume;
- optional pre-defined English/Chinese command recognition where supported;
- optional canned status tones/messages;
- cached UI assets.

Free-form Japanese assistant behavior remains unavailable until the server returns.

## 21. Security/privacy choices

Default live voice policy:

```text
partial microphone frames   ephemeral
ASR text                    session-scoped unless saved
LLM text                    session-scoped unless saved
TTS stream                  ephemeral unless finalized
recorded source audio       off by default
```

A user/project can explicitly enable transcript/history/recording.

Device UI should visibly distinguish LISTENING from IDLE.

## 22. Implementation phases

### M5-0 — Host-independent protocol simulator

- define capability/session schemas;
- fake M5 client in Python;
- 16k PCM frame generator;
- sequence/drop/reconnect tests;
- no physical device required.

### M5-1 — Push-to-Talk CoreS3 baseline

- CoreS3 ESP-IDF/Arduino decision after driver evaluation;
- I2S dual-mic capture reduced to mono AFE output;
- button/touch PTT;
- WebSocket binary PCM;
- half-duplex TTS playback;
- state display;
- metrics.

### M5-2 — Generic Host device pairing/relay

Separate ControlDeck PR:

- generic device registration/pairing;
- public-key challenge auth;
- short-lived session token;
- Add-on device relay;
- scope/revocation/rate limits/audit;
- no SonicForge special-case.

### M5-3 — End-to-end voice agent

```text
M5 -> ASR -> ControlDeck LLM -> TTS -> M5
```

Measure real latency and failure handling.

### M5-4 — Wake/VAD

- ESP-SR AFE;
- VAD;
- WakeNet where useful;
- start/end semantics;
- false wake tests;
- power measurements.

### M5-5 — AEC/barge-in

- playback reference into AEC;
- interruption event;
- cancel TTS queue/current pipeline turn;
- room/volume tests;
- only promote on devices where quality passes.

### M5-6 — compressed remote transport

Evaluate Opus/alternative only after PCM path is stable.

Compare:

- latency;
- CPU;
- memory;
- battery;
- bandwidth;
- packet loss robustness.

## 23. Acceptance criteria

1. PTT does not lose/corrupt audio under normal LAN conditions.
2. Capture task cannot be stalled by UI/network work.
3. Session buffers remain bounded.
4. M5 contains no ControlDeck user password/browser cookie/Add-on service token.
5. SonicForge remains loopback-only behind the Host gateway.
6. Disconnect/reconnect does not replay old microphone turns unexpectedly.
7. ASR -> LLM -> TTS uses stage-local GPU ownership.
8. TTS playback can be canceled safely.
9. Wake/VAD is optional and capability-negotiated.
10. Full duplex is not advertised until AEC/barge-in passes physical tests.
11. Device metrics expose drops/underruns so audio-path failures are diagnosable.
12. The same server pipeline model remains usable by PC/mobile/OpenCode rather than creating an M5-specific AI backend.
