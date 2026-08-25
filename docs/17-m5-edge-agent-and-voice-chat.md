# M5 Edge Agent and Voice Chat Architecture

Status: Normative v1 architecture + implemented baseline  
Date: 2026-08-25

## 1. Role

M5Stack-class devices are thin audio/UI clients for the same SonicForge live runtime used by PC/mobile clients.

They do not host Qwen/Whisper/ACE-Step/Stable Audio models.

Primary presets:

```text
m5-dictation
  mic -> ASR -> text

m5-voice-agent
  mic -> ASR -> ControlDeck LLM -> TTS -> speaker

simultaneous-translation
  mic -> ASR -> ControlDeck translation -> target TTS -> speaker
```

## 2. Local-first connection policy

Two connection paths intentionally coexist.

### Direct trusted LAN / Tailscale

```text
M5 / PC / mobile
 -> SonicForge /addon/v1/live/ws
```

Basic local media functions do not require user-facing authentication. SonicForge default `SONICFORGE_LOCAL_ACCESS=trusted-network` accepts loopback/private/link-local/non-global local fabrics such as Tailscale while rejecting global peers by default.

Use direct mode for:

- ASR/dictation;
- TTS/local media where the caller does not need a Host-owned capability;
- local development/latency measurement.

### Optional ControlDeck Device Relay

```text
M5
 -> ControlDeck Device Relay
 -> Host-minted SonicForge service identity
 -> SonicForge
```

Use relay mode when the pipeline needs:

- ControlDeck LLM;
- Host Job/resource policy associated with a user;
- future project/file-grant operations.

M5 never receives a browser cookie or Add-on service token. It receives only a device-scoped relay credential.

Pairing is infrequent: one-time 8-character code, then a 30-day device credential rotated on every successful reconnect. Direct SonicForge speech remains usable without pairing.

## 3. CoreS3 baseline

Reference firmware:

```text
firmware/m5-sonic-edge/
```

Target:

```text
PlatformIO board: m5stack-cores3
ESP32-S3
M5Unified
arduinoWebSockets
ArduinoJson
```

CoreS3 is used half-duplex in v1. M5Unified's own microphone example switches microphone and speaker rather than operating them simultaneously, so the reference firmware follows the same conservative pattern.

## 4. Audio wire baseline

Uplink:

```text
PCM signed 16-bit little-endian
16 kHz
mono
20 ms
320 samples
640 payload bytes per frame
```

Downlink default:

```text
PCM signed 16-bit little-endian
24 kHz
mono
20 ms framing
```

The negotiated server value is authoritative.

Opus remains an optional future transport. Raw PCM is preferred first because it exposes microphone timing/dropout problems clearly and ordinary LAN bandwidth is sufficient.

## 5. `sonic-edge/1` binary frame

Network-order framing:

```text
4 bytes  magic = SFA1
1 byte   version = 1
1 byte   stream  (1 mic / 2 speaker)
1 byte   flags
1 byte   reserved = 0
4 bytes  sequence
4 bytes  sample clock
2 bytes  payload length
N bytes  PCM payload
```

Server/client track sequence gaps and duplicate/old frames. Payload size is bounded.

Control messages use JSON text WebSocket frames.

## 6. Live session handshake

The client sends one `hello` containing the normal `LiveSessionCreate` contract plus an optional device descriptor.

Current device descriptor shape:

```json
{
  "protocol": "sonic-edge/1",
  "device_class": "m5",
  "model": "core-s3",
  "firmware": "0.1.0",
  "audio": {
    "input": [
      {"codec":"pcm_s16le","rate":16000,"channels":1,"frame_ms":20}
    ],
    "output": [
      {"codec":"pcm_s16le","rate":24000,"channels":1,"frame_ms":20}
    ],
    "aec": false,
    "vad": false,
    "wake": false
  },
  "ui": {"display":true,"touch":true,"buttons":3},
  "psram_bytes": 8388608
}
```

Unsupported capabilities are disabled instead of guessed.

## 7. PTT v1

State sequence:

```text
DISCONNECTED
 -> CONNECTING
 -> IDLE
 -> PTT press
 -> LISTENING
 -> PTT release
 -> TRANSCRIBING
 -> THINKING (when LLM is present)
 -> SPEAKING (when TTS is present)
 -> IDLE
```

There is no arbitrary 60-second default cap. `max_utterance_seconds` is optional and only applies when the operator/client explicitly configures it.

Audio capture uses the common RAM-first spool on the server. Large/backlogged input spills to disk automatically rather than turning the RAM threshold into a duration limit.

## 8. Low-latency voice response

Voice-agent path:

```text
ASR persistent worker
 -> final transcript
 -> ControlDeck SSE LLM tokens
 -> stable clause chunker
 -> TTS persistent worker
 -> first completed audio chunk immediately sent
 -> further chunks generated progressively
```

Chunk boundaries use punctuation, length and elapsed-time fallback. The system does not wait for the complete LLM response before starting TTS when streaming mode is available.

ASR/TTS workers remain warm inside the live session when capacity permits. ControlDeck LLM uses a renewable residency hold. If the GPU cannot hold all residents safely, Resource Broker accounting remains authoritative and SonicForge explicitly evicts/reloads a peer worker rather than OOMing or self-deadlocking.

## 9. Session / credential lifetime

ControlDeck service credentials are short-lived internally but automatically refreshed while an active Host Job/lease/residency heartbeat proves continued execution. Ten minutes is not a voice-session limit.

LLM residency:

```text
hold TTL: 120 s
heartbeat: ~30 s
```

If SonicForge dies, heartbeat stops and the hold expires.

Persistent ASR/TTS workers set Linux parent-death handling. Broker lease renew stops if the parent dies, allowing Host lease expiry to reclaim the reservation.

## 10. Meeting and dictation

Long meetings are not implemented as one giant PTT buffer.

```text
continuous PCM
 -> RAM-first processing chunks
 -> persistent ASR
 -> finalized timestamped SQLite segment
 -> optional translation
 -> repeat without meeting duration limit
 -> optional final hierarchical summary
```

`chunk_seconds` is processing granularity, not total duration.

If the WebSocket disconnects, already queued chunks continue processing; finalized segments remain durable. Reconnect/resume UX may be improved later without changing the storage model.

## 11. Simultaneous translation

Current standard path:

```text
speech
 -> ASR
 -> ControlDeck streaming LLM translation
 -> target-language TTS
 -> progressive playback
```

This keeps terminology/system prompts and meeting storage consistent with the general ControlDeck router. Dedicated speech-to-speech engines can later implement the same typed stage contract if target-hardware benchmarks justify them.

## 12. Wake / VAD / AEC roadmap

### v1 — implemented baseline

- PTT;
- half-duplex;
- raw PCM;
- persistent server workers;
- streaming LLM/TTS response;
- reconnect.

### v1.x — after CoreS3 measurement

- device VAD;
- WakeNet;
- automatic end-of-speech;
- configurable noise suppression.

### v2 — only after acoustic validation

- AEC;
- full duplex;
- barge-in;
- playback cancellation/resume semantics.

These enhancements must not destabilize the PTT baseline.

## 13. Acceptance

`SF受入確認` must measure rather than assume:

- real CoreS3 effective mic sample rate;
- sequence gaps/drop rate;
- direct trusted-LAN dictation;
- paired relay voice agent;
- end-of-speech -> ASR final;
- ASR final -> first LLM token;
- first speakable clause -> first TTS audio;
- end-of-speech -> first audible speaker output;
- second/subsequent turn reload behavior;
- Wi-Fi reconnect;
- SonicForge/ControlDeck restart;
- SIGKILL cleanup of worker/lease/LLM hold;
- speaker underrun/noise.

Compilation or simulator-only behavior is not sufficient for production M5 acceptance.
