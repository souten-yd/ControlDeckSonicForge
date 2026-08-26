# SonicForge Implementation Status

Last updated: 2026-08-26

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

Setup now prepares the heavyweight assets exposed by the selected pack instead of marking a component available while leaving an avoidable first-use model download. Speech Essentials includes the Qwen CustomVoice/Clone/VoiceDesign and ASR model snapshots, Game Audio includes Small-SFX after terms acceptance, and Music invokes the pinned ACE-Step upstream downloader for its selected DiT/LM checkpoints. Speech Essentials and Music have now been executed successfully on the target R9700. Game Audio remains **NOT TESTED** because its Stability license terms have not been accepted; SonicForge does not accept those terms implicitly.

The remaining promotion work is primarily **local execution/benchmarking and merge validation**, not missing architecture.

## 2. Current implementation matrix

| Area | State | Evidence / note |
|---|---|---|
| Specification / Add-on v2 boundary | COMPLETE | external-service; Host owns generic control plane, Add-on owns domain engines/assets |
| FastAPI core / health / setup | IMPLEMENTED | durable SQLite state, setup profiles, isolated runtimes, staged atomic activation and model-prefetch metadata |
| Durable Jobs / cancel / restart handling | IMPLEMENTED | local + Host Job projection |
| Host Job credential lifetime | IMPLEMENTED ON SONICFORGE + CONTROLDECK #240 | short-lived bearer remains internal safety TTL; active Job/lease/AI residency renews credentials so 10 minutes is not a processing limit |
| Resource Broker | REAL HOSTED + LIVE + CRASH PASS | hosted and live speech acquired/renewed/released leases; SIGKILL stopped renewal, killed the persistent ASR child and the orphaned lease expired through Host TTL reaping |
| LLM residency hold | IMPLEMENTED ON CONTROLDECK #240 | 120 s TTL + 30 s heartbeat; dead SonicForge stops heartbeat and hold expires |
| Host AI streaming | IMPLEMENTED ON CONTROLDECK #240 | provider-neutral SSE `text.generate`; reasoning/private chunks suppressed |
| Local unauthenticated media API | IMPLEMENTED, REAL JA TTS PASS | trusted-local work remains independent of Host-owned Jobs/Broker credentials; real Japanese Qwen TTS passed without user-facing authentication, while Host-managed executions still acquire Broker leases before GPU work |
| TTS | CUSTOMVOICE/CLONE/DESIGN REAL PASS | real Qwen3-TTS CustomVoice, rights-confirmed Base clone and VoiceDesign all generated assets on the R9700; hosted CustomVoice used Host Job/Broker and direct-local variants required no user-facing auth |
| ASR Japanese | REAL MODEL PASS | Kotoba-Whisper v2 transcribed the generated Japanese fixture through scoped `grant:` + Host Job/Broker in 10.057 s; recognition was usable but rendered “SonicForge” imperfectly |
| ASR multilingual/English | EN/AUTO/MIXED REAL PASS | Whisper large-v3-turbo accurately transcribed explicit `en`, single-language `auto`, and a JA+EN fixture; mixed `auto` re-runs language detection across long-silence segments and preserves continuous timestamps |
| Speech Essentials provisioning | CLEAN ROCM INSTALL PASS | isolated `speech-rocm` runtime activated only after all five model snapshots completed; exact revisions recorded in runtime metadata |
| SFX | TERMS GATE REAL PASS, MODEL NOT TESTED | real setup without acceptance failed `terms_required:stability-ai-community-license` and kept Game Audio `missing`; Small-SFX download/generation awaits explicit user acceptance |
| Japanese SFX conditioning | IMPLEMENTED | ControlDeck LLM may normalize JP intent to English acoustic prompt; both prompts kept in provenance |
| Music/BGM | CLEAN ROCM SETUP + REAL GENERATION PASS | ACE-Step 1.5 pinned source and prepared `acestep-v15-turbo` + `acestep-5Hz-lm-0.6B`; real target generation produced a 10.000 s, 48 kHz stereo WAV without model-cache growth |
| Localization Studio | IMPLEMENTED | JP/EN lines, durable render, `pending/failed/changed/all` retry modes |
| Typed Pipeline | IMPLEMENTED | type checking, `start_at`, `stop_after`, durable execution |
| OpenCode / Agent tools | REAL MCP E2E PASS | `sonic.generate`, detached `sonic.pipeline` and opaque-grant `sonic.pack` completed through the existing ControlDeck Agent MCP; six frozen initial Agent Tools |
| `audio.process` | REAL FFMPEG PIPELINE PASS | fixed-argv ffmpeg trim/duration/gain/loudnorm/resample/channels; real 10 s ACE-Step asset was trimmed to 3.5 s, normalized, converted to 24 kHz mono and persisted with performed-check metadata |
| `package` delivery | REAL PIPELINE + HTTP PASS | canonical audio Asset plus separate ZIP Asset containing `audio/*` and canonical `manifest.json`; provenance, SHA-256 and content route verified |
| Audio delivery profiles | REAL FFMPEG SUBSET PASS | web-mobile MP3, Unity OGG and M5 16 kHz mono WAV were rendered and probed; remaining named profiles retain unit coverage |
| Low-latency PTT WebSocket | REAL TWO-TURN PASS | no arbitrary 60 s default; optional explicit `max_utterance_seconds` only; real direct-local turns completed with ordered audio |
| Persistent ASR/TTS | REAL TWO-TURN REUSE PASS | same session reused real workers; turn 2 completed materially faster without a second avoidable cold load |
| ASR/TTS crash cleanup | REAL SIGKILL PASS | killing only SonicForge terminated the persistent Whisper child immediately, stopped Broker renewal, expired the lease and auto-restarted a healthy service |
| Warm LLM+ASR+TTS coexistence | TARGET CAPACITY MEASURED, SEQUENTIAL FALLBACK PASS | current 27B llama plus speech workers do not fit the 32 GiB target together; simultaneous translation explicitly evicts/releases the prior stage and passed without deadlock/OOM |
| Progressive LLM -> TTS | UNIT OVERLAP + REAL FALLBACK CHUNK OVERLAP PASS | bounded SSE/TTS/audio overlap remains available when admitted; on the 32 GiB fallback, chunk 1 TTS began when chunk 0 playback began, though synthesis remained slower than playback and left a measured gap |
| Simultaneous translation | REAL JA->EN + EN->JA PASS | hosted ASR -> ControlDeck llama -> target TTS passed both directions; current target uses explicit sequential residency release because full overlap exceeds VRAM |
| Meeting / minutes | REAL ASR/TRANSLATION/SUMMARY PASS | real English segments persisted with Japanese translation; final summary contained Summary / Decisions / Action Items / Open Questions |
| Meeting disconnect durability | REAL DISCONNECT + RESTART PASS | three queued Whisper segments finalized after transport loss and remained available from the transcript endpoint after restart |
| RAM-first audio spool | REAL AUTO/SPILL/DISK PASS | 384,000-byte auto spool used `/dev/shm`; a 5 MiB stream crossed the 4 MiB soft limit and migrated intact to disk; explicit disk mode also passed |
| M5/edge binary protocol | MODERN + DEPLOYED COMPATIBILITY IMPLEMENTED | `sonic-edge/1` keeps sequence/sample-clock framing; deployed M5Companion protocol 2 maps `listen.*`, header-less raw PCM, `state` and `speech.*` without firmware changes |
| Existing M5/edge client server API | REAL MODEL SIMULATED-CLIENT PASS, REAL DEVICE NOT CONNECTED | exact CoreS3 protocol-2 frames completed real Whisper-large-v3-turbo -> Qwen TTS turns with paced 16 kHz PCM; physical Wi-Fi/reconnect/playback remains NOT TESTED because the device is absent |
| ControlDeck paired Device Relay | REAL PAIRING/ROTATION/MODEL E2E PASS, REAL REVOKE NOT TESTED | one-time code reuse returned 403; relay/device-scoped 8-hour token rotated on reconnect; protocol-2 CoreS3 frames completed Whisper -> Host llama -> Qwen TTS through #240; live disabled/revoked relay remains NOT TESTED beyond unit coverage |
| Bilingual/mobile browser UX | REAL CHROME PASS | direct service rendered the required JA and EN top-level/task labels at 320x720 with `scrollWidth == innerWidth` and authoritative service state `available` |
| Wake/VAD | CLIENT/OPTIONAL ENHANCEMENT | not required for SonicForge v1 acceptance unless it changes the server contract |
| Full-duplex/AEC/barge-in | PLANNED SERVER ENHANCEMENT | intentionally not a v1 promotion blocker |
| Release signing | REAL BUILD/VERIFY/TAMPER PASS | disposable Ed25519 key, canonical byte-exact manifest, onefile `doctor`/service startup and artifact tamper rejection passed |
| ControlDeck signed Release Bundle verifier | REAL HOST INSTALL/UPDATE/ROLLBACK PASS ON #239 | disposable trusted key: fresh 0.1.0, side-by-side 0.1.1 and post-switch unhealthy 0.1.2 rollback to healthy 0.1.1 passed; production publisher key remains an operator input |
| Current branch-wide lightweight tests | PASS WITH WARNING | current worktree: 87 passed; only the known Starlette TestClient deprecation warning remains |
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

Current target-machine evidence on 2026-08-26:

```text
SonicForge:
  python -m compileall -q backend worker_packs tests
  pytest -q
  87 passed; 1 warning (TestClient deprecation only)

ControlDeck combined local Host (#239 + #240):
  ./deck.sh test
  815 passed, 1 skipped, 1 warning

ControlDeck affected integration set:
  111 passed
```

Real setup/runtime evidence:

- real `game-audio` setup with an empty acceptance list terminated as `failed` with `terms_required:stability-ai-community-license`; no pack activation or model download occurred and the component remained `missing`;
- clean `speech-rocm` provisioning completed with Qwen CustomVoice, Clone Base, VoiceDesign, Kotoba-Whisper and Whisper Turbo snapshots and recorded their exact revisions;
- first provisioning attempt failed correctly in staging because unpinned PyPI torchaudio was ABI-incompatible with ROCm torch; `torchaudio==2.10.0` now resolves to the ROCm 7.2.1 wheel and the second clean activation passed;
- ControlDeck restarted on the combined Host changes, reported `/api/v1/health` healthy, accepted the SonicForge v2 manifest, enabled all requested capabilities and projected `sonic-forge` into the effective registry;
- real Japanese CustomVoice TTS completed through a ControlDeck Host Job and Resource Broker lease and produced a 4.320 s, 24 kHz, mono PCM WAV;
- real Kotoba-Whisper Japanese ASR consumed that WAV through a scoped `grant:` and completed through a Host Job/Broker lease in 10.057 s;
- the initial direct trusted-network TTS attempt incorrectly required a Host identity for GPU work; after removing that unconditional guard, real Japanese Qwen TTS completed without user-facing authentication as `asset:6df66bb1-32c0-4513-b852-622c10389683`; hosted executions still acquire Broker leases before worker launch;
- real English Qwen TTS produced a 13.040 s, 24 kHz mono WAV and Whisper Turbo returned the intended sentence for both explicit `en` and `auto` requests;
- the first concatenated Japanese/English `auto` run returned only English because one Whisper language decision covered the full clip; long-silence segmentation now re-runs detection per region, and the same fixture returned both JA and EN segments at 0.72–4.28 s and 4.32–16.72 s;
- real Qwen Base voice clone completed from a rights-confirmed scoped `grant:` reference as `asset:f5e6a7f3-f943-4359-a41c-6d16c7139d66`, and real VoiceDesign completed from a textual instruction as `asset:c4f59fbc-4a4f-4654-9b96-478404152d4b`;
- a direct trusted-local two-turn PTT session kept the real ASR/TTS worker processes scoped to one WebSocket: turn 1 completed in 52.266 s and turn 2 in 25.581 s with ordered audio delivery, demonstrating reuse without an avoidable second cold load;
- hosted simultaneous translation passed Japanese to English in 103.238 s (`job:d1c2d282-...`) and English to Japanese in 56.980 s (`job:6e49826c-...`), with accurate transcripts, translated text and target-language audio; the target cannot hold the current approximately 30.2 GiB llama allocation beside the speech workers, so SonicForge now releases each prior residency before the next GPU stage;
- a 660-second hosted Meeting kept the same logical scope while refreshing its short-lived Host credential; the Host Job remained active and completed without operator action;
- real Meeting disconnect testing queued three 5-second Whisper chunks, closed the WebSocket immediately, finalized all three segments, and retained them through service restart; a hosted retry persisted Japanese translation and generated all four required summary sections;
- after a forced parent SIGKILL, Whisper worker PID `1704830` disappeared immediately, service restart counter advanced, health recovered, lease `5a4b3646-cb99-47f4-a7b9-6f686615fd56` stopped renewing and reached `expired`; a crashed LLM residency hold also stopped heartbeat and allowed explicit release after TTL;
- graceful shutdown with an open Meeting WebSocket and resident Whisper worker completed in 164 ms and removed the child; queued/waiting and running cancellation requests both converged to durable `canceled` terminal state;
- RAM spool measurements wrote 384,000 bytes to `/dev/shm` in approximately 0.10 ms, transparently spilled 5 MiB to managed disk in approximately 3.16 ms, and wrote an explicit 384,000-byte disk spool in approximately 0.04 ms with no leftover acceptance files;
- clean `music-rocm` provisioning downloaded the pinned ACE-Step runtime/checkpoints into SonicForge-owned paths and activated fingerprint `09bba6cf5968a62ea1f7f449d93475a6df08563e44d05e2cf31a926495ceb525`;
- the first ACE-Step execution exposed third-party stdout pollution of the worker JSON protocol; redirecting upstream stdout to stderr fixed the boundary, and the retry produced `asset:f3fb4585-0c4c-44ff-974f-99be2bc51192` as a 10.000 s, 48 kHz stereo PCM WAV with unchanged model-cache byte size;
- after routing ACE-Step's writable project cache under SonicForge storage, a second real 10 s generation produced `asset:49ccfbc0-5c65-492c-9688-00dd8015a80e` and did not recreate a source-tree `.cache` directory;
- the real ACE-Step asset then passed the typed `audio.process` stage with trim, gain, loudness normalization, resampling and mono conversion as `asset:8112b814-0cd3-4c2c-894a-d09ef2a371e0`; package delivery produced `asset:a055cbc7-8d13-4e13-a36e-550a1c769c99`, a 155,959-byte ZIP whose SHA-256, provenance, manifest and HTTP content route were verified;
- release acceptance first exposed and fixed two real packaging defects: building with a foreign PyInstaller venv omitted runtime dependencies, and Uvicorn's string import omitted `sonicforge.bootstrap`; the corrected 29,987,441-byte onefile bundle passed `doctor`, served `setup_required`, verified against a disposable Ed25519 publisher key, rejected byte tampering, installed fresh as 0.1.0, updated side-by-side to 0.1.1 and rolled an unhealthy 0.1.2 switch back to healthy 0.1.1 through the generic ControlDeck #239 path;
- real Agent MCP execution completed `sonic.generate` (`job:81c713b8-...`, detached Host Job `f70bd8fa303f`), `sonic.pipeline` (`job:dcabcfa5-...`, detached Host Job `dda2a0410a71`) and `sonic.pack` through opaque `grant:0bc68e65-...`; direct profile exports produced valid web-mobile MP3, Unity OGG and M5 WAV assets;
- headless real Google Chrome at 320x720 rendered Japanese `スタジオ / ボイス / ライブラリ / ランタイム / 音声生成` and English `Studio / Voices / Library / Runtime / Speech` without horizontal overflow; both views reported the service as `available`;
- real execution exposed and fixed Qwen third-party stdout pollution of the JSON worker protocol and the greedy asset-content route shadowing bug.

The existing M5 client remains **NOT TESTED** in this acceptance run: no `303a:1001` USB device, `/dev/ttyACM*` device or active TCP client connection was present. The independent `m5companion-bridge.service` was running, but that is not evidence of a connected physical client.

Source inspection found that the deployed M5Companion 0.3.0 client uses protocol integer `2`, `listen.begin`/`listen.end` controls and header-less PCM rather than `sonic-edge/1`. SonicForge now negotiates that exact wire contract on `/addon/v1/live/ws`: a regression fixture passed the deployed CoreS3 hello and 16 kHz capture rate, accepted periodic `device.state`/`device.telemetry` messages and raw PCM, returned real-time-paced 16 kHz raw speaker bytes bracketed by `speech.begin`/`speech.end`, and persisted a successful durable live Job. The server also honors a different valid capture rate declared by another board.

A real service-level simulated CoreS3 then sent the same 6.0 s Japanese utterance in paced 20 ms raw frames. The direct path completed Whisper-large-v3-turbo ASR and Qwen TTS, returned 6.56 s of non-silent 16 kHz PCM (`mean_volume=-22.4 dB`, `max_volume=-4.2 dB`), and persisted `job:027d0558-...` as succeeded. In a same-socket two-turn run, speech began at 57.01 s cold and 40.32 s on turn two; this proves reuse but is not yet acceptable conversational latency on the current sequential low-VRAM route. A separate local ASR-only run processed the 6.0 s file in 8.38 s and misrecognized some Japanese technical terms. Physical-device behavior remains uncredited until the board reconnects.

The generic ControlDeck #240 Device Relay also passed real HTTP/WebSocket execution. A user-scoped service credential created a one-time pairing; its first connection returned a relay/device-scoped token with an exact 28,800-second TTL, code reuse was rejected with HTTP 403, and token reconnect returned the same device scope with a rotated credential. The relay replaced that device credential with a Host-minted Add-on service identity upstream. Exact M5Companion protocol-2 frames then completed real Whisper -> ControlDeck llama -> Qwen TTS as local `job:34a43e46-...` and Host Job `2ffd7198f8fc`; the bounded spoken response returned 8.16 s of non-silent 16 kHz PCM (`mean_volume=-22.6 dB`, `max_volume=-5.4 dB`). Speech began at 90.98 s and the turn reached idle at 99.15 s. The run exposed and fixed two low-VRAM defects: the streaming path retained ASR residency while requesting Host AI, and its first TTS request could block the bounded LLM queue while the LLM held GPU admission. ASR is now evicted before Host AI; rejected concurrent TTS admission drains the bounded stream, releases AI and retries as an explicitly recorded sequential fallback. An exact-head warm-cache confirmation completed in 47.92 s with speech beginning at 41.77 s; `job:bc694c70-...` records `delivery_overlap=false` and `sequential_fallback=true` on the TTS stage. A subsequent two-sentence fallback run (`job:30c92bb1-...`, Host Job `fce3ef1b1c8b`) began chunk 1 TTS at the same timestamp as first audio playback, proving generation/playback overlap under the target capacity constraint. The 14.24 s of audio occupied a 19.91 s speaking interval, so a 5.67 s synthesis gap remains a known latency limitation. Physical-device relay and a live disabled/revoked relay remain NOT TESTED.

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
