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
 -> ordered bounded audio-delivery queue
 -> progressive WebSocket audio
```

Required evidence:

- first speakable chunk is emitted before the full LLM response is complete;
- multiple TTS chunks preserve order;
- chunk N+1 TTS generation proceeds while chunk N audio is being delivered;
- the bounded text/audio queues apply backpressure instead of allowing memory growth without bound;
- client-facing JSON/binary frame order is serialized by the audio-delivery stage;
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

## G. Existing M5 / edge client API compatibility

M5 firmware is **not part of the SonicForge repository acceptance scope**. The user already owns the device-side implementation. Do not add, build, or gate merge on a SonicForge-maintained firmware project.

Validate the published server contracts against the existing client instead.

### Direct trusted-LAN path

```text
existing M5 client
 -> ws://<sonicforge-host>:9140/addon/v1/live/ws
 -> sonic-edge/1
```

Verify:

- trusted-LAN basic ASR/TTS/PTT path requires no user-facing authentication;
- `hello` capability negotiation succeeds;
- PCM input/output rate negotiation matches the existing client;
- `ptt.start` / binary mic frames / `ptt.stop` produce expected transcript/audio events;
- sequence gaps/duplicates are reported without corrupting later turns;
- repeated turns keep warm models when resources allow;
- SonicForge restart and Wi-Fi/client reconnect recover cleanly.

### Optional ControlDeck relay path

If the existing M5 client uses ControlDeck-hosted LLM voice/translation:

```text
existing M5 client
 -> ControlDeck Device Relay
 -> SonicForge live API
```

Verify:

- one-time pairing is required only for first relay registration;
- reconnect uses the stored device credential and receives a rotated credential;
- current design uses a 30-day rolling device credential;
- device credential is scoped to the declared SonicForge relay;
- the device never receives the upstream Add-on service token or browser cookie;
- ordinary reconnect/reboot does not require repeated pairing;
- disabled Add-on/revoked relay is rejected on the next connection.

Wake/VAD/AEC/barge-in remain client-side/optional enhancements and are not SonicForge v1 merge blockers unless a server contract change is required.

## H. Final merge rule

`SF受入マージ` must not merge until:

- base runbook required items PASS;
- all applicable items in this addendum PASS;
- exact tested PR head SHAs are unchanged;
- one batched milestone CI has been run where configured and is green;
- ControlDeck generic dependency PRs are merged before SonicForge;
- SonicForge is updated/rebased as necessary and affected smoke checks are repeated.

Do not reinterpret `NOT TESTED` as PASS. Do not merge because GitHub merely reports `mergeable`.
