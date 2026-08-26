# M5 / Edge Agent and Voice Chat Server Contract

Status: Normative v1 server/API architecture  
Date: 2026-08-25

## 1. Scope

M5Stack-class devices, mobile clients and PC clients are thin audio/UI clients for the same SonicForge live runtime.

**Device firmware/client implementation is outside this repository.** SonicForge owns only the published HTTP/WebSocket/media contract and server-side behavior.

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
edge client
 -> ControlDeck Device Relay
 -> Host-minted SonicForge service identity
 -> SonicForge
```

Use relay mode when the pipeline needs:

- ControlDeck LLM;
- Host Job/resource policy associated with a user;
- future project/file-grant operations.

The edge client never receives a browser cookie or Add-on service token. It receives only a relay-scoped device credential.

Device Relay credentials follow the normal ControlDeck Add-on maximum credential lifetime: **8 hours**, with a same-scope replacement issued on successful reconnect. There is no special 30-day device-token exception. Basic direct SonicForge speech remains usable without pairing.

## 3. Audio wire baseline

Uplink baseline:

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

Opus remains an optional transport. Raw PCM is preferred first because it exposes microphone timing/dropout problems clearly and ordinary LAN bandwidth is sufficient.

## 4. Supported wire contracts

### Modern `sonic-edge/1`

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

### Existing M5Companion protocol 2

The user's deployed M5Companion 0.3.0 firmware predates `sonic-edge/1`. SonicForge therefore accepts its existing handshake on the same endpoint without requiring a firmware fork:

```json
{
  "type": "hello",
  "protocol": 2,
  "audio_format": "pcm_s16le",
  "audio_rate": 16000,
  "chunk_samples": 320
}
```

Compatibility mapping:

```text
listen.begin        -> PTT start (the message's microphone rate is authoritative)
raw binary PCM16    -> bounded/adaptive input spool
listen.end          -> PTT commit
state               <- idle/listening/thinking/speaking state
speech.begin        <- playback starts
raw binary PCM16    <- real-time-paced 16 kHz speaker audio
speech.end          <- playback drains and ends
```

The current CoreS3 microphone declares 16 kHz. Other supported boards, including the M5GO path, may declare 12 kHz in `listen.begin` even though the speaker/hello rate is 16 kHz. SonicForge writes the input WAV at the declared capture rate and lets the selected ASR path perform the normal conversion. Downlink is resampled to the hello rate. The server also accepts the client's periodic `device.state` and `device.telemetry` reports without disrupting the live session.

Legacy raw frames have no sequence or sample-clock header, so the server cannot invent per-frame gap evidence. For that client, use its existing uplink sent/failed counters and playback `dropped` telemetry. `sonic-edge/1` clients retain exact server-side sequence-gap/duplicate reporting.

## 5. Live session handshake

Modern clients send one `hello` containing the normal `LiveSessionCreate` contract plus an optional device descriptor. Existing M5Companion protocol 2 uses the compatibility handshake above.

Example descriptor:

```json
{
  "protocol": "sonic-edge/1",
  "device_class": "m5",
  "model": "existing-client",
  "firmware": "external",
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

Unsupported capabilities are disabled instead of guessed. An unauthenticated trusted-LAN legacy connection uses the local `m5-dictation` ASR-to-TTS confirmation path. The same legacy frames forwarded through the authenticated ControlDeck Device Relay select `m5-voice-agent` and may use Host AI.

## 6. PTT v1

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

## 7. Low-latency voice response

Voice-agent path:

```text
ASR persistent worker
 -> final transcript
 -> ControlDeck SSE LLM tokens
 -> stable clause chunker
 -> bounded text queue
 -> persistent TTS
 -> bounded ordered audio-delivery queue
 -> first completed audio chunk immediately sent
 -> further chunks synthesized while prior audio is delivered
```

Chunk boundaries use punctuation, length and elapsed-time fallback. The system does not wait for the complete LLM response before starting TTS when streaming mode is available.

ASR/TTS workers remain warm inside the live session when capacity permits. ControlDeck LLM uses a renewable residency hold. If the GPU cannot hold all residents safely, Resource Broker accounting remains authoritative and SonicForge explicitly evicts/reloads a peer worker rather than OOMing or self-deadlocking.

## 8. Session / credential lifetime

ControlDeck service credentials are short-lived internally but automatically refreshed while an active Host Job/lease/residency heartbeat proves continued execution. Ten minutes is not a voice-session limit.

LLM residency:

```text
hold TTL: 120 s
heartbeat: ~30 s
```

If SonicForge dies, heartbeat stops and the hold expires.

Persistent ASR/TTS workers set Linux parent-death handling. Broker lease renew stops if the parent dies, allowing Host lease expiry to reclaim the reservation.

The optional Device Relay credential is separate from service-token refresh and uses the normal ControlDeck Add-on maximum TTL (8 hours). Reconnect may rotate it; no long-lived device-token exception is required.

## 9. Meeting and dictation

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

## 10. Simultaneous translation

Current standard path:

```text
speech
 -> ASR
 -> ControlDeck streaming LLM translation
 -> target-language TTS
 -> progressive playback
```

This keeps terminology/system prompts and meeting storage consistent with the general ControlDeck router. Dedicated speech-to-speech engines can later implement the same typed stage contract if target-hardware benchmarks justify them.

## 11. Client-side optional enhancements

Wake/VAD/AEC implementation is owned by the external device/client unless a server contract extension becomes necessary.

Server roadmap items that may matter later:

- automatic end-of-speech semantics;
- full-duplex session state;
- barge-in/cancellation semantics;
- optional compressed transport negotiation.

These are not v1 merge blockers for the current PTT/live API.

## 12. Acceptance

`SF受入確認` validates the **published server contract against the user's existing client**, not a SonicForge-maintained firmware build.

Measure/verify:

- `sonic-edge/1` hello/capability negotiation or the deployed M5Companion protocol 2 compatibility handshake;
- effective input/output sample-rate negotiation;
- sequence gaps/drop behavior where the client carries sequence metadata; otherwise existing M5 uplink/drop telemetry;
- direct trusted-LAN dictation/PTT;
- optional paired relay voice-agent path if used;
- end-of-speech -> ASR final;
- ASR final -> first LLM token;
- first speakable clause -> first TTS audio;
- end-of-speech -> first audible output;
- second/subsequent turn reload behavior;
- network/client reconnect;
- SonicForge/ControlDeck restart;
- SIGKILL cleanup of worker/lease/LLM hold;
- ordered progressive audio without underrun/frame-order corruption.

No PlatformIO/firmware compilation step is part of SonicForge acceptance.
