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
4. local raw-ASR upload uses the same Adaptive Spool path;
5. force a tiny `SONICFORGE_SPOOL_STREAM_MB` and prove an active stream transparently spills to `data/tmp/spool` without truncation;
6. set `SONICFORGE_SPOOL_MODE=disk` and prove explicit disk mode works;
7. finalized Job/transcript/Asset metadata remains durable after restart;
8. RAM threshold is a **spill threshold**, never an arbitrary recording-duration limit.

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

- pairing code is used for initial registration or after a stored credential has expired;
- reconnect with a still-valid credential receives a rotated same-scope credential;
- device credentials follow the normal ControlDeck Add-on maximum TTL of 8 hours; there is no 30-day exception;
- device credential is scoped to the declared SonicForge relay;
- the device never receives the upstream Add-on service token or browser cookie;
- disabled Add-on/revoked relay is rejected on the next connection.

Wake/VAD/AEC/barge-in remain client-side/optional enhancements and are not SonicForge v1 merge blockers unless a server contract change is required.

## H. Clean pack provisioning / no hidden first-use download

Start from controlled empty SonicForge runtime/model state. Do not reuse a developer cache when proving this gate.

### Speech Essentials

Run setup and confirm the component does not become `available` until the exposed initial models are present:

```text
Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice
Qwen/Qwen3-TTS-12Hz-0.6B-Base
Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign
kotoba-tech/kotoba-whisper-v2.0
openai/whisper-large-v3-turbo
```

Confirm runtime metadata records the downloaded snapshot/revision information. Then run one simple CustomVoice, Clone/authorized reference, VoiceDesign, Japanese ASR and English/Auto ASR request. The first request may load weights into RAM/VRAM, but it must not start an avoidable multi-GB model download that setup claimed was already complete.

### Game Audio

Verify setup refuses to proceed until the Stability terms identifier is explicitly accepted. Do not auto-accept terms in code/tests.

After acceptance, confirm `stabilityai/stable-audio-3-small-sfx` is present before `game-audio` becomes `available`. Run the first CPU Small-SFX generation and verify there is no hidden first-use model download.

### Music

On the supported experimental Linux ROCm target, confirm setup installs the pinned ACE-Step source and uses the upstream downloader to prepare at least:

```text
acestep-v15-turbo
acestep-5Hz-lm-0.6B
```

The checkpoint root must be SonicForge-managed. Verify a failed `(message, success=False)` from either ACE-Step initializer fails the job instead of continuing into generation. Then run the first music request and confirm the required checkpoints were already prepared by setup.

### Failure/interruption behavior

For each applicable pack verify:

- canceled/interrupted setup never reports the incomplete component as `available`;
- staging failure preserves the previous known-good runtime;
- an idempotent second setup does not redownload unchanged model snapshots unnecessarily;
- `SONICFORGE_SETUP_SKIP_MODEL_PREFETCH=1` is treated only as an explicit developer/testing escape hatch and is not used for release acceptance.

## I. Final merge rule

`SF受入マージ` must not merge until:

- base runbook required items PASS;
- all applicable items in this addendum PASS;
- exact tested PR head SHAs are unchanged;
- one batched milestone CI has been run where configured and is green;
- ControlDeck generic dependency PRs are merged before SonicForge;
- SonicForge is updated/rebased as necessary and affected smoke checks are repeated.

Do not reinterpret `NOT TESTED` as PASS. Do not merge because GitHub merely reports `mergeable`.
