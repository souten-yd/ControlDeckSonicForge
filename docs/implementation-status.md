# SonicForge Implementation Status

Last updated: 2026-08-25

This file separates **code availability** from **executed evidence**. `IMPLEMENTED` means the path exists on `impl/full-platform-baseline`; it does not mean real models, AMD/ROCm, existing M5 hardware/client, browser E2E or the current full test suite have passed. Anything not actually executed remains `NOT TESTED`.

## 1. Executive status

The planned v1 implementation is now **feature-complete at the code/contract level** for the requested local-first scope:

- ASR / TTS / voice profiles and clone/reference handling;
- SFX / BGM generation adapters;
- JP/EN localization batch render + partial retry;
- OpenCode/Agent typed pipelines with selectable start/end stages;
- local trusted-network unauthenticated ASR/TTS/SFX/Music;
- low-latency PTT voice chat with persistent ASR/TTS, ControlDeck streaming LLM, progressive TTS chunks and overlapped ordered audio delivery;
- simultaneous translation preset;
- continuous meeting/minutes capture with incremental durable transcript, optional translation and hierarchical summary;
- RAM-first temporary audio spooling with automatic disk fallback;
- game/web/mobile/M5 audio export profiles;
- deterministic `audio.process` pipeline stage;
- ZIP `package` pipeline delivery;
- published M5/edge API contract (`sonic-edge/1`, trusted-LAN live WebSocket and optional ControlDeck Device Relay); device firmware remains outside this repository;
- generic ControlDeck AI/media gateway, device relay, AI residency and rolling long-job credentials on separate ControlDeck PRs/branch;
- Ed25519 signed release tooling and generic Host verifier path.

Setup now prepares the heavyweight assets exposed by the selected pack instead of marking a component available while leaving an avoidable first-use model download. Speech Essentials includes the Qwen CustomVoice/Clone/VoiceDesign and ASR model snapshots, Game Audio includes Small-SFX after terms acceptance, and Music invokes the pinned ACE-Step upstream downloader for its selected DiT/LM checkpoints. Speech Essentials has now been executed successfully on the target R9700 after fixing the missing ROCm torchaudio pin. Game Audio and Music remain **NOT TESTED** on the target machine.

The remaining promotion work is primarily **local execution/benchmarking and merge validation**, not missing architecture.

## 2. Current implementation matrix

| Area | State | Evidence / note |
|---|---|---|
| Specification / Add-on v2 boundary | COMPLETE | external-service; Host owns generic control plane, Add-on owns domain engines/assets |
| FastAPI core / health / setup | IMPLEMENTED | durable SQLite state, setup profiles, isolated runtimes, staged atomic activation and model-prefetch metadata |
| Durable Jobs / cancel / restart handling | IMPLEMENTED | local + Host Job projection |
| Host Job credential lifetime | IMPLEMENTED ON SONICFORGE + CONTROLDECK #240 | short-lived bearer remains internal safety TTL; active Job/lease/AI residency renews credentials so 10 minutes is not a processing limit |
| Resource Broker | IMPLEMENTED, HOSTED SPEECH E2E PASS | real ControlDeck Host Jobs and Broker leases completed Japanese Qwen TTS and Kotoba-Whisper ASR on the R9700; live session lease retention remains NOT TESTED |
| LLM residency hold | IMPLEMENTED ON CONTROLDECK #240 | 120 s TTL + 30 s heartbeat; dead SonicForge stops heartbeat and hold expires |
| Host AI streaming | IMPLEMENTED ON CONTROLDECK #240 | provider-neutral SSE `text.generate`; reasoning/private chunks suppressed |
| Local unauthenticated media API | IMPLEMENTED, REAL JA TTS PASS | trusted-local work remains independent of Host-owned Jobs/Broker credentials; real Japanese Qwen TTS passed without user-facing authentication, while Host-managed executions still acquire Broker leases before GPU work |
| TTS | CUSTOMVOICE JA PASS, CLONE/DESIGN NOT TESTED | real Qwen3-TTS CustomVoice 0.6B generated a 24 kHz mono Japanese WAV with `Ono_Anna` on R9700 through Host Job/Broker; Clone Base and VoiceDesign remain NOT TESTED |
| ASR Japanese | REAL MODEL PASS | Kotoba-Whisper v2 transcribed the generated Japanese fixture through scoped `grant:` + Host Job/Broker in 10.057 s; recognition was usable but rendered “SonicForge” imperfectly |
| ASR multilingual/English | IMPLEMENTED, REAL MODEL NOT TESTED | Whisper large-v3-turbo path |
| Speech Essentials provisioning | CLEAN ROCM INSTALL PASS | isolated `speech-rocm` runtime activated only after all five model snapshots completed; exact revisions recorded in runtime metadata |
| SFX | IMPLEMENTED, REAL MODEL NOT TESTED | Stable Audio 3 Small-SFX CPU-first; fixed upstream API inspected; model snapshot prefetched only after Stability terms acceptance |
| Japanese SFX conditioning | IMPLEMENTED | ControlDeck LLM may normalize JP intent to English acoustic prompt; both prompts kept in provenance |
| Music/BGM | IMPLEMENTED ADAPTER, REAL MODEL NOT TESTED | ACE-Step 1.5 pinned source; setup uses upstream downloader for `acestep-v15-turbo` + `acestep-5Hz-lm-0.6B`; initialization success tuple is checked; upstream AMD/ROCm support does not count as SonicForge target validation |
| Localization Studio | IMPLEMENTED | JP/EN lines, durable render, `pending/failed/changed/all` retry modes |
| Typed Pipeline | IMPLEMENTED | type checking, `start_at`, `stop_after`, durable execution |
| OpenCode / Agent `sonic.pipeline` | IMPLEMENTED CONTRACT, MCP E2E NOT TESTED | same ControlDeck Agent MCP, no second SonicForge MCP; six frozen initial Agent Tools |
| `audio.process` | IMPLEMENTED, TEST ADDED NOT RUN | fixed-argv ffmpeg trim/duration/gain/loudnorm/resample/channels; no arbitrary args/shell |
| `package` delivery | IMPLEMENTED, TEST ADDED NOT RUN | canonical audio asset + ZIP containing audio and deterministic manifest |
| Audio delivery profiles | IMPLEMENTED, REAL FFMPEG NOT TESTED | master/voice/Unity/Unreal/Godot/web-mobile/M5 profiles |
| Low-latency PTT WebSocket | IMPLEMENTED, FAKE TESTS ADDED NOT RUN | no arbitrary 60 s default; optional explicit `max_utterance_seconds` only |
| Persistent ASR/TTS | IMPLEMENTED, REAL MODEL NOT TESTED | process-local model cache; same process reused across live turns when capacity allows |
| ASR/TTS crash cleanup | IMPLEMENTED | Linux persistent workers set parent-death SIGTERM; Broker lease renew stops on process death |
| Warm LLM+ASR+TTS coexistence | IMPLEMENTED POLICY, TARGET VRAM NOT TESTED | shared-safe live leases; if peer residency prevents admission, peer worker is explicitly evicted and current stage retried rather than self-deadlocking/OOMing |
| Progressive LLM -> TTS | IMPLEMENTED, OVERLAP TEST ADDED NOT RUN | SSE tokens -> clause chunker -> bounded TTS queue -> bounded ordered audio-delivery queue; chunk N+1 synthesis overlaps chunk N delivery |
| Simultaneous translation | IMPLEMENTED PRESET, REAL E2E NOT TESTED | ASR -> streaming Host translation -> target TTS; source/target language selectable |
| Meeting / minutes | IMPLEMENTED, FAKE TEST ADDED NOT RUN | unlimited session duration; bounded processing chunks; incremental SQLite transcript; optional translation + hierarchical summary |
| Meeting disconnect durability | IMPLEMENTED | queued chunks continue processing; finalized segments remain durable even after transport loss |
| RAM-first audio spool | IMPLEMENTED, TESTS ADDED NOT RUN | `/dev/shm`/runtime tmpfs preferred for live/meeting/local-ASR; soft threshold/free-RAM reserve triggers transparent disk spill; no artificial recording-duration cap |
| M5/edge binary protocol | IMPLEMENTED | `sonic-edge/1`, sequence/sample clock, bounded frame size and capability negotiation |
| Existing M5/edge client server API | IMPLEMENTED CONTRACT, REAL CLIENT E2E NOT TESTED | direct trusted-LAN live WS for basic media; optional ControlDeck relay for Host LLM paths; firmware/client code is intentionally outside this repository |
| ControlDeck paired Device Relay | IMPLEMENTED ON #240, E2E NOT TESTED | one-time code; device-scoped token uses the normal ControlDeck maximum 8-hour TTL and rotates on reconnect; upstream receives Host-minted service identity, never device token |
| Wake/VAD | CLIENT/OPTIONAL ENHANCEMENT | not required for SonicForge v1 acceptance unless it changes the server contract |
| Full-duplex/AEC/barge-in | PLANNED SERVER ENHANCEMENT | intentionally not a v1 promotion blocker |
| Release signing | IMPLEMENTED + EARLIER FOCUSED TESTED | Ed25519 canonical manifest; earlier signing focused suite: 4 passed |
| ControlDeck signed Release Bundle verifier | IMPLEMENTED ON DRAFT PR #239, NOT HOST E2E TESTED | production publisher public key still an operator input |
| Current branch-wide lightweight tests | PASS WITH WARNINGS | current head: 71 passed; Starlette TestClient deprecation plus two delayed asyncio subprocess transport warnings remain to resolve |
| Batched GitHub CI | NOT RUN | by explicit project policy, run once only after local acceptance is green |

## 3. Voice-chat execution model

Preferred warm path:

```text
live session start
  -> Host LLM residency hold (TTL + heartbeat)
  -> persistent ASR worker + Broker lease
  -> persistent TTS worker + Broker lease when capacity fits

turn
  -> mic PCM (RAM-first spool)
  -> ASR
  -> ControlDeck LLM SSE tokens
  -> stable clause chunker
  -> bounded text queue
  -> TTS chunk 0 -> ordered audio-delivery queue -> immediate WebSocket playback
  -> TTS chunk 1/2/... generated while prior audio is being delivered
  -> next turn reuses warm workers/models

session end
  -> workers stop
  -> leases release
  -> LLM hold release
```

The client-facing streaming sender is intentionally single-owner: JSON chunk events and binary audio frames are serialized by the ordered delivery stage even while LLM intake and TTS synthesis run concurrently.

If the selected GPU cannot safely hold ASR + TTS + LLM together, Broker accounting remains authoritative. SonicForge may explicitly evict one live worker and continue; it must not silently overcommit VRAM.

### Crash invariant

No live residency is permanent:

```text
SonicForge SIGKILL
 -> Linux child parent-death signal terminates persistent worker processes
 -> lease renew loops stop -> Host lease TTL reaps reservation
 -> LLM residency heartbeat stops -> 120 s hold expires
 -> next SonicForge instance starts cleanly
```

`SF受入確認` must prove this on the target machine before merge.

## 4. Long-session credentials

ControlDeck service tokens remain short-lived bearer credentials to limit exposure if leaked. They are **not** user-visible duration limits.

Active work renews a same-scope credential through one of these liveness authorities:

- active Host Job credential refresh;
- active Resource Broker lease credential refresh;
- active AI residency hold heartbeat.

A CPU-only localization/setup/meeting job may therefore run beyond 10 minutes without extending the original bearer indefinitely. Refresh stops when the Job becomes terminal or the owning process dies.

Device Relay credentials do not use a special long-lived policy. They are scoped to one Add-on relay/device, follow the normal ControlDeck maximum 8-hour TTL, and may be rotated on successful reconnect. Basic direct trusted-LAN SonicForge speech does not require a device credential at all.

## 5. RAM / SSD policy

Temporary latency-sensitive audio is ephemeral:

```text
preferred: operator SONICFORGE_SPOOL_DIR
       -> /dev/shm/sonicforge-<uid>
       -> XDG_RUNTIME_DIR
       -> persistent data/tmp/spool fallback
```

Environment controls:

```text
SONICFORGE_SPOOL_MODE=auto|memory|disk
SONICFORGE_SPOOL_DIR=<path>
SONICFORGE_SPOOL_STREAM_MB=<soft per-stream RAM threshold>
SONICFORGE_SPOOL_RAM_RESERVE_MB=<free-space reserve>
```

The thresholds decide **when to spill**, not when to stop recording. Live/meeting/local-ASR temporary input prefers the spool manager. Ordinary large durable generation work may use SonicForge disk temp so Music/SFX jobs do not opportunistically consume large amounts of RAM. Final Assets, Job state and finalized meeting transcript segments remain durable on disk because recovery value is high.

Shared-memory/zero-copy PCM IPC is deliberately deferred until profiling proves tmpfs serialization is a material bottleneck relative to ASR/TTS inference.

## 6. Meeting/minutes behavior

A meeting is not one huge PTT request.

```text
continuous PCM
 -> RAM-first chunk spool
 -> persistent ASR
 -> finalized timestamped segment -> SQLite immediately
 -> optional per-segment translation
 -> repeat without session duration limit
 -> optional bounded hierarchical final summary
```

`chunk_seconds` (default 20, configurable 5-60) is processing granularity only, not a meeting duration limit. A failed ASR chunk is recorded as failed and does not erase earlier segments.

## 7. M5 / edge client paths

SonicForge publishes the server contract only. Existing device firmware/client code is external to this repository and is not a build/merge gate here.

### Direct local

```text
existing edge client -> ws://SonicForge:9140/addon/v1/live/ws
```

Default `trusted-network` permits local/private/Tailscale peers without user-facing auth for basic ASR/TTS/PTT flows.

### Optional ControlDeck voice agent / translation

```text
existing edge client
 -> ControlDeck paired Device Relay
 -> Host mints service identity upstream
 -> SonicForge ASR
 -> ControlDeck LLM
 -> SonicForge TTS
 -> edge client
```

The device never receives an Add-on service token or browser cookie. It may keep only the device-scoped credential required by the optional Host relay path.

## 8. Validation evidence actually executed

Only evidence actually run remains credited.

Current target-machine evidence on 2026-08-25:

```text
SonicForge:
  python -m compileall -q backend worker_packs tests
  pytest -q
  71 passed; 1 warning (TestClient deprecation only)

ControlDeck combined local Host (#239 + #240):
  ./deck.sh test
  813 passed, 1 skipped, 1 warning

ControlDeck affected integration set:
  111 passed
```

Real setup/runtime evidence:

- clean `speech-rocm` provisioning completed with Qwen CustomVoice, Clone Base, VoiceDesign, Kotoba-Whisper and Whisper Turbo snapshots and recorded their exact revisions;
- first provisioning attempt failed correctly in staging because unpinned PyPI torchaudio was ABI-incompatible with ROCm torch; `torchaudio==2.10.0` now resolves to the ROCm 7.2.1 wheel and the second clean activation passed;
- ControlDeck restarted on the combined Host changes, reported `/api/v1/health` healthy, accepted the SonicForge v2 manifest, enabled all requested capabilities and projected `sonic-forge` into the effective registry;
- real Japanese CustomVoice TTS completed through a ControlDeck Host Job and Resource Broker lease and produced a 4.320 s, 24 kHz, mono PCM WAV;
- real Kotoba-Whisper Japanese ASR consumed that WAV through a scoped `grant:` and completed through a Host Job/Broker lease in 10.057 s;
- the initial direct trusted-network TTS attempt incorrectly required a Host identity for GPU work; after removing that unconditional guard, real Japanese Qwen TTS completed without user-facing authentication as `asset:6df66bb1-32c0-4513-b852-622c10389683`; hosted executions still acquire Broker leases before worker launch;
- release bundle build produced a 24,288,632-byte linux-x86_64 artifact; disposable Ed25519 signing/CLI verification passed and appended-byte tampering was rejected;
- real execution exposed and fixed Qwen third-party stdout pollution of the JSON worker protocol and the greedy asset-content route shadowing bug.

Release signing tests now pass as a five-test focused suite, including direct CLI invocation.

Static upstream/API inspection completed during implementation includes:

- Qwen VoiceDesign official model family uses `Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign`;
- pinned Stable Audio 3 `StableAudioModel.from_pretrained(...).generate(...)` contract matches the adapter, including Small-SFX CPU baseline;
- pinned ACE-Step exposes `AceStepHandler`, `LLMHandler`, `GenerationParams`, `GenerationConfig`, `generate_music`, and `GenerationResult.audios[*]["path"]` as used by the adapter;
- ACE-Step initialization returns explicit `(message, success)` values and SonicForge now checks them.

These are source/API consistency checks, **not target runtime evidence**.

Current new tests cover contracts for:

- trusted-network access and local unauthenticated TTS/ASR durable-job flow;
- setup model lists/prefetch intent and external-command argument rejection;
- RAM spool and disk spill;
- persistent worker process reuse/cleanup;
- PTT/live pipeline foundation;
- low-latency text chunking;
- overlapped TTS generation vs ordered audio delivery;
- Host job credential refresh, AI residency rolling credential and SSE stream parsing;
- meeting transcript durability;
- deterministic audio processing/package helpers;
- ControlDeck Gateway/device/session behavior.

They have been run as the current branch batch described above. Test coverage does not replace the remaining real acceptance items below.

## 9. Promotion / merge gates

The implementation must not be merged merely because the code is feature-complete.

Run `SF受入確認` on the target local machine and prove at least:

1. current full lightweight/static SonicForge + affected ControlDeck suites;
2. clean Speech Essentials provisioning including all exposed Qwen/ASR model prefetches;
3. real Japanese/English/mixed ASR;
4. real Qwen TTS including CustomVoice, Clone and VoiceDesign plus repeated warm turns;
5. voice-chat latency: end-of-speech -> ASR -> first LLM token -> first speakable chunk -> first audio;
6. turn 2+ has no avoidable ASR/TTS/LLM cold reload;
7. chunk N+1 TTS generation overlaps chunk N audio delivery without client frame-order corruption;
8. simultaneous JA<->EN translation text + speech;
9. long meeting capture, incremental transcript, reconnect/interruption behavior and optional summary;
10. >10-minute CPU-only hosted work survives credential rotation;
11. SIGKILL SonicForge while voice stack is warm and prove child/lease/hold cleanup;
12. Stable Audio 3 Small-SFX clean pack setup + CPU generation without first-use hidden model download;
13. ACE-Step AMD/ROCm clean pack setup + music generation using the prepared checkpoints;
14. real ffmpeg export/audio.process and ZIP package;
15. OpenCode `sonic.generate` / `sonic.pipeline` end to end;
16. existing edge/M5 client direct live API and, if used, paired relay voice-agent path;
17. signed Release Bundle fresh install/update/failure rollback with real public key setup.

After all mandatory local gates pass, run the **single batched milestone CI**, inspect exact PR heads, then use `SF受入マージ`. Merge generic ControlDeck dependencies before SonicForge and run a short post-merge smoke test.

Until those checks are executed, target-hardware/model compatibility remains `NOT TESTED`, not PASS.
