# Codex Final Local Acceptance Addendum

Status: normative supplement to `CODEX_LOCAL_ACCEPTANCE.md`  
Date: 2026-08-25

When `SF受入確認` or `SF受入マージ` is invoked, read **both** this file and `CODEX_LOCAL_ACCEPTANCE.md`.

This addendum covers implementation added after the base runbook was written.

## A. Long-running credential test

The default ControlDeck service bearer remains short-lived internally. It must not become a 10-minute job/session limit.

Create at least one **CPU-only hosted Job** that runs longer than 10 minutes and verify:

- same logical subject/scope throughout rolling credential refresh;
- Host Job remains active and progress/cancel still works after the original token would have expired;
- no manual credential action is required;
- terminal Job can no longer refresh its credential;
- killing SonicForge stops refresh activity;
- no unlimited service bearer is issued.

Also exercise:

- Resource Broker lease credential refresh;
- LLM residency hold heartbeat/credential refresh;
- temporary Host loss/restart recovery where practical.

## B. RAM-first spool / SSD write test

Default policy is `SONICFORGE_SPOOL_MODE=auto`.

Verify on Linux:

1. short PTT PCM is created under the configured tmpfs or `/dev/shm` path;
2. live TTS work dirs are ephemeral/RAM-backed when capacity permits;
3. meeting chunks use RAM first;
4. force a tiny `SONICFORGE_SPOOL_STREAM_MB` and prove an active stream transparently spills to `data/tmp/spool` without truncation;
5. set `SONICFORGE_SPOOL_MODE=disk` and prove explicit disk mode works;
6. finalized Job/transcript/Asset metadata remains durable after restart;
7. RAM threshold is a **spill threshold**, never an arbitrary recording-duration limit.

Record approximate:

```text
RAM/tmpfs high water
persistent temp bytes
SSD writes attributable to raw temporary audio if measurable
ASR/TTS latency with auto spool
ASR/TTS latency with disk spool
```

Do not implement shared-memory/zero-copy IPC merely because it sounds faster. Promote it only if the measurement shows serialization/I/O is material relative to inference.

## C. Streaming voice acceptance

Use the exact production live path:

```text
ASR persistent worker
 -> ControlDeck SSE LLM
 -> speakable clause chunker
 -> persistent TTS
 -> progressive WebSocket audio
```

Required evidence:

- first speakable chunk is emitted before the full LLM response is complete;
- multiple TTS chunks preserve order;
- backpressure does not grow memory without bound;
- turn 2+ reuses ASR/TTS process/model when capacity permits;
- LLM remains warm while residency hold is healthy;
- live session does not call `ai.release` after every turn while hold is active;
- low-VRAM fallback explicitly evicts/reloads a peer resident instead of self-deadlocking/OOMing.

Record first-turn and second-turn timing separately.

## D. Simultaneous translation

Test:

```text
JA speech -> JA ASR -> EN streaming translation -> EN TTS
EN speech -> EN ASR -> JA streaming translation -> JA TTS
```

Also run text-only target output if available to isolate translation quality from TTS quality.

Verify:

- source transcript and target translation are distinct;
- target speech begins progressively;
- names/numbers/technical terminology dictionary/system prompt can be injected;
- no private LLM reasoning content is streamed to SonicForge/client.

## E. Meeting/minutes

Run a long meeting beyond ordinary PTT durations.

Required:

- no total duration limit;
- `chunk_seconds` changes processing granularity only;
- segments are persisted incrementally;
- one failed segment does not destroy prior/future segments;
- disconnect after several queued chunks and verify queued ASR still finalizes;
- transcript endpoint remains usable after reconnect/restart;
- optional translation persists beside the source segment;
- optional final summary contains Summary / Decisions / Action Items / Open Questions;
- original transcript remains independently available;
- RAM spool can spill to disk without losing timestamps/content.

Speaker diarization is optional and must remain reported as unavailable/not-tested if not installed.

## F. `audio.process` and package delivery

Test real ffmpeg with:

- trim start/duration;
- gain;
- loudness normalization;
- sample-rate conversion;
- mono/stereo conversion.

Verify arbitrary command arguments/shell syntax are rejected.

Run a pipeline ending in `package` and inspect ZIP:

```text
audio/<canonical audio file>
manifest.json
```

Verify package Asset/provenance, SHA-256 and HTTP content route.

## G. M5 CoreS3 firmware

Before hardware testing:

```bash
cd firmware/m5-sonic-edge
cp include/config.example.h include/config.h
pio run
```

Compilation failure is a merge blocker for the M5 baseline.

Then test real CoreS3:

### Direct mode

```text
SONIC_USE_CONTROLDECK_RELAY=0
SONIC_PRESET=m5-dictation
```

Verify trusted-LAN use without user-facing authentication.

### Relay voice-agent

Create one ControlDeck pairing, connect with the code once, confirm the firmware stores a device token in NVS, then remove the pairing code from local config.

Verify:

- subsequent reconnect uses stored token;
- ControlDeck returns a different/refreshed device token;
- token is scoped to SonicForge `voice` relay;
- device does not receive the upstream Add-on service token;
- ordinary reboot does not require re-pairing;
- current design uses 30-day rolling device credential, refreshed on successful reconnect;
- explicit pair reset clears NVS credential.

Real audio checks:

- effective mic rate near 16 kHz;
- 20 ms frame cadence / sequence gaps;
- no old M5 analog-ADC slow-capture behavior;
- speaker playback without underrun/noise;
- second voice turn avoids unnecessary model cold loads;
- Wi-Fi drop/reconnect;
- SonicForge restart;
- ControlDeck restart in relay mode.

Wake/VAD/AEC/barge-in are not v1 blockers unless the user explicitly promotes them.

## H. Final merge rule

`SF受入マージ` must not merge until:

- base runbook required items PASS;
- all applicable items in this addendum PASS;
- exact tested PR head SHAs are unchanged;
- one batched milestone CI has been run where configured and is green;
- ControlDeck generic dependency PRs are merged before SonicForge;
- SonicForge is updated/rebased as necessary and affected smoke checks are repeated.

Do not reinterpret `NOT TESTED` as PASS. Do not merge because GitHub merely reports `mergeable`.
