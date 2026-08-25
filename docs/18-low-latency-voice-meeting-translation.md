# Low-Latency Voice Chat, Meeting Minutes, and Simultaneous Translation

Status: normative architecture and acceptance plan  
Date: 2026-08-25

## 1. Scope

SonicForge must support the following from one shared speech/media core:

- low-latency voice chat;
- ASR-only dictation;
- long-running meeting transcription/minutes;
- simultaneous translation;
- translated speech playback;
- M5/PC/mobile clients;
- OpenCode/agent invocation;
- ordinary local unauthenticated ASR/TTS/SFX/music use.

The implementation must not force all of these workloads through one fixed 60-second turn model.

## 2. Access policy

The normal personal/local deployment is trusted-local first.

No ControlDeck user authentication is required for the basic SonicForge inference surface:

```text
local ASR
local TTS
local SFX generation
local music generation
local ASR/TTS live audio where no Host-only capability is used
```

ControlDeck authentication remains an internal boundary only when a Host-owned feature is requested, for example:

```text
ControlDeck text/vision AI router
Host Jobs
Resource Broker leases
scoped file/project grants
project output commit
device relay exposed by ControlDeck
```

The user should not have to perform an extra login step merely because SonicForge internally calls the ControlDeck router from an already-authenticated Add-on session.

Do not expose raw ControlDeck service tokens to local clients or M5 firmware.

## 3. Do not use one hard duration limit

The previous fixed 60-second PTT bound is not a product requirement.

Use workload semantics instead:

### Voice chat

Speech is divided into utterances by PTT release or VAD end-of-speech. A configurable soft guard may stop an obviously stuck microphone, but it must not be a hidden universal limit.

### Dictation

Continuous input is accepted and transcribed incrementally. The process should be limited by storage and operator policy rather than an arbitrary short utterance timeout.

### Meeting

A meeting is a durable session that may last hours. Audio is never accumulated into one unbounded RAM buffer or one monolithic ASR request.

Use bounded spool/chunk processing:

```text
continuous input
 -> disk/ring spool
 -> VAD/time segment commit
 -> ASR segment
 -> durable timestamped transcript
 -> optional translation
 -> optional rolling/final meeting analysis
```

A failed segment must not invalidate the rest of the meeting.

## 4. Low-latency voice chat pipeline

The preferred path is:

```text
microphone
 -> ASR partial/final
 -> ControlDeck LLM token stream
 -> clause/sentence chunker
 -> warm TTS worker
 -> first completed audio chunk immediately to client
 -> while chunk N is playing, generate chunk N+1
```

Do not wait for the full LLM answer and full TTS file before playback unless the selected engine lacks streaming/chunk support.

### 4.1 LLM streaming

ControlDeck owns provider/model selection. SonicForge consumes the provider-neutral Add-on AI stream and never selects a raw provider port/model.

The ControlDeck Add-on AI Gateway exposes:

```text
POST /api/v1/addon-runtime/{addon_id}/ai/stream
```

for `text.generate`.

Thinking/reasoning tokens are not exposed to SonicForge. Only user-visible content and usage events are streamed.

### 4.2 Text chunking for TTS

For Japanese and English, chunk commitment must balance latency and prosody.

Use all of:

- strong punctuation boundary;
- weak punctuation boundary after a minimum text size;
- maximum characters/estimated spoken duration;
- maximum wait since the first unspoken token;
- flush at LLM completion.

Do not split mechanically every N tokens.

A useful initial target for measurement is first spoken audio within roughly 0.5-1.5 seconds after the LLM starts returning useful visible text, but acceptance is based on measured stage timings rather than one universal number.

### 4.3 Double buffering

Playback and synthesis should overlap:

```text
TTS chunk 1 -> PLAY 1
              TTS chunk 2
PLAY 2        TTS chunk 3
...
```

Queues are bounded. Cancellation invalidates queued future speech.

## 5. LLM + ASR + TTS coexistence

Voice chat must not cold-load all three models on every turn.

### 5.1 LLM

ControlDeck provides a renewable session-scoped AI residency hold.

Properties:

- model remains warm between turns;
- ordinary explicit `ai.release` cannot unload it while the hold is active;
- Resource Broker yield treats the held residency as non-yieldable;
- hold is short-lived and renewable;
- hold is in-memory only;
- SonicForge crash stops heartbeat and the hold expires automatically;
- ControlDeck restart drops all holds automatically;
- renewing the hold updates LLM recent-use time so idle unload does not race a live session.

Current host contract:

```text
POST   /api/v1/addon-runtime/{addon_id}/ai/residency/holds
POST   /api/v1/addon-runtime/{addon_id}/ai/residency/holds/{hold_id}/renew
DELETE /api/v1/addon-runtime/{addon_id}/ai/residency/holds/{hold_id}
```

The current renewable lease uses an internal 120-second TTL and 30-second recommended heartbeat. This is not a voice-session length limit; it is orphan cleanup.

### 5.2 ASR / TTS

Use persistent SonicForge worker processes for live speech workloads. Their model objects stay loaded between turns.

When integrated with ControlDeck GPU admission, the resident worker must be backed by a session-scoped Resource Broker lease. Do not keep GPU memory after returning the corresponding lease.

ControlDeck Broker leases already expire when renewal stops. Therefore if SonicForge is killed, Host-side lease expiry reclaims the reservation automatically.

### 5.3 Insufficient VRAM

"Keep everything warm" is a preference, not permission to overcommit VRAM.

When LLM + ASR + TTS do not fit concurrently, routing must make the condition explicit and choose a measured fallback, for example:

1. place ASR on CPU or a second GPU;
2. place TTS on CPU or a second GPU;
3. select a smaller speech model/profile;
4. queue a non-interactive workload rather than evicting a live voice session;
5. as a last resort, allow a documented model swap.

Do not silently trigger OOM and do not claim a coexistence profile is supported until measured on the target machine.

## 6. Simultaneous translation

Default architecture:

```text
speech
 -> streaming/segmented ASR
 -> stable source-language unit
 -> ControlDeck streaming LLM translation
 -> translated text event
 -> optional warm TTS
 -> translated audio playback
```

The same session may emit all of:

```text
source partial text
source final text
translated partial/final text
translated audio chunks
```

### Translation policy

- preserve names, units, numbers, code and domain terminology;
- allow a project/session glossary;
- expose source and target language independently;
- allow text-only translation to avoid unnecessary TTS;
- allow translation start/end stages to be selected by the typed pipeline;
- preserve source and translated text in provenance/meeting records.

Dedicated speech-to-speech models may be added as optional engines, but the default path remains ASR -> ControlDeck Router -> TTS because it shares terminology control, meeting storage, general instructions and existing resource routing.

## 7. Meeting mode

Meeting mode is not a giant PTT turn.

Recommended state:

```text
meeting_id
started_at
source language / auto
translation targets[]
recording policy
segments[]
rolling transcript
rolling summary (optional)
final summary
items/decisions/actions
```

Each segment stores at minimum:

```text
segment_id
start_ms
end_ms
source_text
source_language
translations{}
speaker_id?        # optional until diarization is validated
confidence/qa
source_audio_ref?  # only when recording is enabled
```

### Long-session durability

- commit transcript segments incrementally;
- fsync/SQLite commit at bounded intervals;
- do not keep the entire recording in RAM;
- reconnect by meeting/session id;
- already-finalized segments are immutable except explicit correction;
- unfinished segment may be discarded/restarted after disconnect;
- final analysis is a separate durable job;
- partial failure must preserve completed transcript segments.

### Speaker diarization

Diarization is optional for the first usable meeting release. Add it as a separate capability/profile after testing rather than blocking basic minutes on it.

## 8. M5 / PC / mobile transport

Use one live protocol family.

- PC/mobile browser through ControlDeck: existing authenticated proxy is fine.
- trusted-local PC client: direct SonicForge WebSocket may be used.
- M5: use either trusted-local direct mode for a personal LAN deployment or ControlDeck Device Session relay when the Host boundary is desired.
- basic ASR/TTS should not require a user login.

For M5, keep heavy inference on the server. Device performs capture/playback plus optional AEC/VAD/Wake.

## 9. Streaming events

Recommended event family:

```text
session.ready
input.started
asr.partial
asr.final
translation.partial
translation.final
llm.delta
llm.final
tts.chunk.started
tts.chunk.ready
audio.start
binary audio frames
audio.end
turn.complete
meeting.segment.final
meeting.summary.updated
warning
error
```

Events and audio queues must be bounded. Slow clients must not cause unbounded memory growth.

## 10. Cancellation / barge-in

When a user interrupts playback:

1. stop client playback immediately;
2. invalidate queued TTS chunks for the old turn;
3. cancel active TTS work if supported;
4. cancel the current LLM stream when appropriate;
5. preserve already-final ASR text/history according to session policy;
6. begin the next turn.

Never play stale queued speech after a new user turn begins.

## 11. Crash recovery

### SonicForge process crash

Expected behavior:

- WebSocket closes;
- in-flight ephemeral audio is lost unless explicitly recorded;
- durable Jobs/meeting transcript already committed remain;
- ControlDeck AI residency hold stops renewing and expires;
- ControlDeck Resource Broker ASR/TTS lease stops renewing and expires;
- Host Job becomes failed/orphaned according to normal reconciliation;
- restart must not assume old worker processes or old leases still exist;
- reconnect obtains fresh residency/leases and resumes from durable state.

### Worker crash

- only the current stage/segment fails;
- worker is restarted on next use;
- meeting transcript already committed is retained;
- a failed meeting segment can be retried without retranscribing the entire meeting.

### ControlDeck crash/restart

- in-memory LLM residency holds disappear;
- SonicForge must detect renew failure and reacquire;
- stale service/lease credentials are not reused blindly;
- direct local ASR/TTS continues if it does not depend on Host-owned features.

## 12. Metrics required for acceptance

Record at least:

```text
mic -> ASR partial latency
mic end -> ASR final latency
ASR final -> first LLM token
LLM first token -> first TTS chunk submitted
TTS submit -> first playable PCM
first playable PCM -> speaker playback start
turn total latency
LLM cold/warm load count
ASR cold/warm load count
TTS cold/warm load count
residency hold acquire/renew/expiry
Broker lease acquire/renew/expiry
queue depth / dropped frames / underruns
```

The most important performance regression test is that turn 2+ remains warm and materially faster than a cold turn when the target machine has enough memory for coexistence.

## 13. Implementation sequence

1. trusted-local basic ASR/TTS/SFX/music API;
2. ControlDeck provider-neutral LLM streaming;
3. crash-safe LLM residency hold;
4. persistent ASR/TTS worker protocol and cache;
5. session-scoped speech Resource Broker leases;
6. Japanese/English clause chunker and TTS double buffer;
7. simultaneous translation preset/events;
8. long-running meeting spool + segment durability;
9. optional diarization;
10. M5 real-device latency/AEC/VAD validation;
11. barge-in/full duplex after half-duplex streaming is stable.

Do not promote an engine/hardware profile from experimental until the local acceptance checklist in `19-codex-local-acceptance.md` passes on the target machine.
