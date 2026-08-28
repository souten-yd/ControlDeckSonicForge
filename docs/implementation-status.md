# SonicForge Implementation Status

Last updated: 2026-08-28

This file separates **code availability** from **executed evidence**. `IMPLEMENTED` means the path exists on `impl/full-platform-baseline`; it does not mean real models, AMD/ROCm, existing M5 hardware/client, browser E2E or the current full test suite have passed. Anything not actually executed remains `NOT TESTED`.

## Automatic Speech Essentials Feature provisioning

- The v0.1.2 source follows MediaForge's generic Release Bundle lifecycle: `control-deck-feature.json` declares `provision_args: ["provision"]` instead of running the read-only `doctor` command as provisioning. The existing SonicForge `provision` command defaults to `speech-essentials`; Game Audio and Music remain optional and no gated terms are accepted implicitly.
- ControlDeck's unchanged generic provider runs provision and doctor against managed persistent feature data before switching/starting the staged version, then registers the Add-on only after service health passes. Existing provider tests confirm provision-before-smoke, failed-provision no-switch, failed-health rollback/Add-on restoration and SonicForge's publisher-signed catalog contract.
- Local v0.1.1 branch suite: 97 passed with the known Starlette TestClient deprecation warning. A real PyInstaller bundle exposed the expected provision/doctor/serve lifecycle; its packaged `provision` command converged Speech Essentials in isolated test-mode feature data, and the packaged service then reported `healthy` with `speech-essentials: ok` while optional packs remained missing. A repository-external disposable Ed25519 key signed that artifact and `verify_release.py` accepted its exact identity, size and digest.
- The embedded workspace and settings entry documents now inline their CSS and JavaScript, following MediaForge's self-contained initial-document pattern for ControlDeck's opaque sandbox. An authenticated real Chrome run through the live Host loaded the branch service at both 1280x800 and 320x700, displayed the desktop and mobile navigation respectively, and returned 200 for the initial frame, Bridge-authorized API calls and WebSocket connection. No page or console errors occurred; the only aborted requests were the Host's expected effective-Add-on event stream during navigation. The temporary test Add-on registration, user and service were removed and the installed v0.1.0 registration was restored afterward.
- v0.1.1 was published from merge commit `c4c1f887781da997f18f5012a56b2296f5fe3540`; a fresh download passed SHA-256 and publisher-signature verification. The first live ControlDeck Add-on update correctly retained healthy v0.1.0 but rejected v0.1.1 during provisioning: the frozen launcher was incorrectly used as `python -m venv` and reported `invalid choice: 'venv'`. v0.1.2 follows MediaForge's packaging precedent by resolving the host `python3` executable solely to build SonicForge's own isolated worker venv.
- The v0.1.2 branch suite passed 99 tests. A real frozen v0.1.2 candidate then completed production-mode Speech Essentials provisioning into ControlDeck's managed Feature data: it built the independent ROCm worker venv, installed all five pinned speech model snapshots, and converged 17 GiB of managed state. Its packaged read-only doctor passed and the packaged service reported `healthy` with `speech-essentials: ok`; Game Audio and Music remained missing as intended.
- PR #10 merged as `12b3c5acab2e4f9e0757991dbe70ff2b20b68492`. The exact merged v0.1.2 artifact is 30,001,260 bytes with SHA-256 `27458dc45398bca58ebc38fa4653a228265762f513dec2a2fd354853475c34f5`; the trusted publisher signature verified before publication and a fresh GitHub release download passed its published SHA-256 file. The live generic ControlDeck Add-on update job `654f86ecd846` succeeded from v0.1.0 to v0.1.2 with `enabled=true` and `health=healthy`; `current`, the generated systemd unit and the effective Add-on manifest all resolve to v0.1.2.
- Final authenticated real-Chrome acceptance through the live ControlDeck route `/x/sonic-forge/workspace` passed at 1280x800 and 320x700. Both rendered one SonicForge iframe, the expected desktop/mobile navigation, `serviceState=available`, and no Speech Essentials setup gate. Both initial frame requests returned 200; no external CSS/JavaScript requests, unexpected failed requests, page errors or console errors occurred. The temporary administrator was removed after its sessions were revoked; audit and Feature-job evidence were preserved.

## v0.2.0 workspace UI rebuild

- The v0.2.0 branch suite passed 101 tests. The workspace was driven headlessly through
  the Chrome DevTools Protocol across every mode, task and view, at 1440px and 390px, in
  light and dark, in Japanese and English, with **zero JavaScript exceptions**. Speech,
  SFX, a localization batch and a typed pipeline were executed end to end against a live
  service, and each produced a playable asset through the new result and library surfaces.
- Three defects were found by that run and fixed before release: `applyLocale()` replaced
  the `textContent` of labels that wrap a control and so destroyed the control (the voice
  select rendered empty); assets were rendered before their jobs were known, so fresh
  items displayed a raw asset ID; and `capabilities.py` reported a hardcoded service
  version of `0.1.0`.
- PR #12 merged as `379af838247275c0c5d31acc52c76ddc1d9d9285`. The v0.2.0 artifact is
  30,040,407 bytes with SHA-256
  `d51834272a66c5f1fd4de33f2cb195787eb6127d7c16d456304384dd4be9be8c`. Before publication
  the frozen bundle was served directly and confirmed to emit the rebuilt shell
  (`mode-simple`/`mode-advanced`, `shell-nav`, the `data-adv-template` fragments, the
  inlined localization module), to report `service.version = 0.2.0`, to expose all nine
  delivery profiles, and to serve `/settings/` as the same document with
  `data-start-view="settings"` and `<base href="../">`. `verify_release.py` accepted the
  detached publisher signature against the exact Ed25519 key in ControlDeck's trusted
  catalog (`g4c486WbOPjVYuwtkMLxqriGlolip0Tfen2E262+PC0=`).
- The live generic ControlDeck Add-on update succeeded from v0.1.2 to v0.2.0 with
  `enabled=true`, `health=healthy` and an empty error. `current` resolves to
  `versions/0.2.0`, the running service is the v0.2.0 binary, `/health` reports `healthy`
  with `speech-essentials: ok` while Game Audio and Music remain missing as intended, and
  the effective Add-on manifest is v0.2.0 and passes `deck.sh ext lint`. The 17 GiB of
  managed Speech Essentials state carried over without re-provisioning.
- Authenticated real-browser acceptance through the live ControlDeck route
  `/x/sonic-forge/workspace` is **NOT TESTED** for v0.2.0. The unauthenticated
  `/addon-frame/sonic-forge/` proxy correctly returns 401, and the operator elected to
  perform the logged-in check rather than issue a session. The Host-proxied path itself
  (proxy root derivation, Bridge session nonce header, credentialed API calls and the
  WebSocket subprotocol) is unchanged from the accepted v0.1.2 code and is covered by the
  frontend transport tests, but that is reasoning rather than executed evidence.

## v0.3.0 web capture, gated provisioning and the meeting minutes flow

- Transcription, voice-clone reference audio and typed pipeline audio inputs no longer go
  through ControlDeck's Host file picker. That picker cannot reach a microphone and is not
  the picker a phone user expects; the earlier build failed with `picker_canceled`. Each of
  those inputs is now the same component: **record in the browser** (`MediaRecorder`, opus
  in WebM with an mp4 fallback because iOS has no opus) or **pick a file** with the plain
  web input, uploaded to a new `POST /addon/v1/uploads`.
- `backend/sonicforge/uploads.py` stores every upload under a server-generated UUID name,
  caps it at 200 MiB while streaming, and normalises it with ffmpeg to 48 kHz mono
  `pcm_s16le` WAV so the workers, which read plain waveforms, can consume browser
  containers. `resolve()` matches `^upload:[0-9a-f]{32}$` and requires containment under
  the uploads directory. An unreadable file returns one fixed sentence; the ffmpeg detail
  goes to the log only, so no internal filesystem path reaches the API.
- Voice-clone reference audio is transcribed automatically by the existing ASR route, so
  the operator no longer has to type the reference text by hand. QwenTTS voice clone,
  voice design and per-request speaker customisation are now reachable from the 音声 task
  in both Simple and Advanced.
- 会議 transcribes while it records and asks the LLM for the 議事録 at the end, with a
  JA/EN simultaneous-translation toggle in the same tab.
- Game Audio provisioning failed with an unhandled `GatedRepoError` 401 on
  `stabilityai/stable-audio-3-small-sfx`, which is `gated: auto` on Hugging Face. Two
  causes were confirmed by reproducing the failure with the provisioned speech venv: no
  Hugging Face token existed anywhere on the host, and the in-app licence checkbox only
  records local acknowledgement. Setup now injects a stored token as `HF_TOKEN` /
  `HUGGING_FACE_HUB_TOKEN` and rewrites the gated failure into an instruction naming the
  model page. `GET`/`PUT /addon/v1/setup/credentials` store that token write-only at mode
  0600; it is never returned by the API and never logged.
- `error_message` now keeps the **tail** of the failure (`str(exc)[-1200:]`). The previous
  head truncation discarded the root cause, because `_run_process` already returns only
  the last 2000 characters of stderr — that is why the reported traceback was unusable.
- Music is executed evidence, not just installed. Provisioning job
  `39a152c6-36ee-4bdf-b014-d41e00995bd2` converged `music-rocm` with ACE-Step 1.5 and both
  `acestep-v15-turbo` and `acestep-5Hz-lm-0.6B`, `music.generate` reports `available`, and
  a live `music.generate` produced a 30 s 48 kHz stereo WAV measuring -19.6 dB mean and
  -1.0 dB peak, so it is real audio rather than silence.
- `python-multipart` is now a runtime dependency, because the upload route takes a
  multipart body. The PyInstaller bundle must include it.
- Two defects were found by driving the branch build in a real headless Chrome and fixed
  before release. `setMode()` did not redraw the 作るもの pull-down, so switching to 詳細
  left the simple four in the list and ローカライズ and 会議 were unreachable until a
  reload — the exact requirement that Advanced reach every feature. And 会議 defaulted its
  minutes checkbox to off, although producing the minutes at the end is the point of that
  screen; it now defaults to on. A test now pins the redraw.
- The release sweep drove the branch service at 1440x1000 and 390x844, in Japanese and
  English, through both modes, all six 作るもの and every view: **zero JavaScript
  exceptions, zero console errors and no horizontal overflow anywhere**. Browser file
  selection produced an upload and a finished ASR job, and the voice-clone dialog filled
  its reference transcript automatically from that job's text.
- The same two header changes were applied to MediaForge: the media switch moved into the
  header immediately left of 詳細 as a single compact pull-down, and the in-page duplicate
  of the title is hidden whenever the Host chrome already shows it. MediaForge's 761 tests
  pass.

## Live mobile registry reachability repair

- The live Host still stored the pre-release managed Add-on manifest with `workspace.mobile: companion`, even though repository and public v0.1.0 manifests declare `embedded`. The effective API therefore returned `companion`; authenticated Chrome 320x720 reached `More -> Audio` but rendered the status-only companion with zero workspace iframes.
- Re-registering the current v0.1.0 `addon.json` through the authenticated generic Add-on API atomically refreshed the managed manifest while preserving enabled state, capability grants and healthy service state. The stored manifest remains mode 0600 and now reports `mobile: embedded` / `availability: available`.
- After a ControlDeck restart, authenticated Chrome 320x720 repeated `More -> Audio`, rendered one SonicForge workspace iframe and exposed its `Studio / Library / Jobs / More` navigation. Document/body width remained 320 and failed requests, HTTP errors and console errors were all zero.
- This was stale live registry state rather than a source or release-bundle code defect. Acceptance now compares the live effective contribution with the exact manifest and repeats the mobile route after Host restart.

## Embedded UI repair merge acceptance

- Generic ControlDeck PR #242 merged as `864eeaef892c7ea21a1cf5121623feadc68a5a54`.
- SonicForge PR #3 merged as `ded89ea84d4c866a3ba8fb6516e09239ca70af6c` after the dependency merge and a fresh 95-test SonicForge rerun.
- The post-merge `origin/main` smoke `tests/test_core.py::test_embedded_frontend_routes` passed. The pre-merge exact-head real Chrome evidence remains the authenticated workspace/API/mutation/WebSocket run recorded below; no code changed between that accepted PR head and its merge commit.
- The merged generic Host repair was then integrated into the active local ControlDeck checkout without discarding its parallel commits or unrelated `frontend/tsconfig.tsbuildinfo` change. After restarting `control-deck-web.service`, authenticated Chrome repeated the workspace GET, temporary voice POST/DELETE cleanup and event WebSocket against the live `127.0.0.1:8765` service with zero failed responses, CORS errors or console errors.

## Mobile full-workspace release candidate

- The `workspace` contribution now declares `mobile: embedded` instead of the status-only companion, so phone users receive the real SonicForge workspace.
- At 320x720 the embedded UI uses `Studio / Library / Jobs / More`, keeps Voices and Runtime under More, provides 48 px bottom-navigation targets, reserves Host/device safe areas, prevents iOS input zoom and keeps exactly one workspace view visible.
- Authenticated Chrome against isolated ControlDeck `127.0.0.1:18766` and exact branch SonicForge `127.0.0.1:19140` passed Japanese/English switching, Jobs/More/Runtime navigation, authoritative API reconnect and the event WebSocket with document/body `scrollWidth == 320` and zero failed responses, CORS errors or console errors. Desktop embedded regression also passed GET, temporary voice POST/DELETE cleanup and WebSocket with zero browser errors.
- The branch-wide lightweight suite remains 95 passed with only the known Starlette TestClient deprecation warning.

## v0.1.0 signed release and ControlDeck distribution

- SonicForge PR #6 merged the mobile workspace as `62532efbabc02463bad1163af6eb0c5a76c9dc3a`; the exact merged head was tagged and published as [v0.1.0](https://github.com/souten-yd/ControlDeckSonicForge/releases/tag/v0.1.0).
- The Linux x86_64 artifact is 29,970,963 bytes with SHA-256 `da4a50ffa317fc1bda3ed87a95032a50a83e61470b5e49f1354d87ca7f0efd48`. A repository-external Ed25519 publisher key signed the canonical manifest; a fresh download independently passed signature, adjacent checksum, GitHub digest and artifact digest verification, packaged `doctor`, and the release-focused 5-test suite.
- The public bundle passed generic ControlDeck fresh install/enable/uninstall in isolated data. Before Speech Essentials setup, generic ControlDeck PR #243 preserves only setup-safe UI surfaces so the full mobile workspace remains reachable while execution surfaces stay unavailable.
- ControlDeck PR #244 admitted the release to the trusted catalog without a per-release digest pin or SonicForge-specific Host path. After merge and live Host restart, the feature API returned `available=true` / `not-installed`, and authenticated Settings at 320x720 and 1280x800 displayed the verified bundle candidate with zero horizontal overflow, failed responses, HTTP errors or console errors.

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

The ControlDeck embedded workspace blank-screen defect was reproduced in Chromium 151 as missing Host cookies from the opaque sandbox iframe. The generic Host frame-auth repair and SonicForge Bridge-aware API/reconnect repair now pass real embedded-browser validation; direct service behavior remains unchanged.

The remaining promotion work is primarily **local execution/benchmarking and merge validation**, not missing architecture.

## 2. Current implementation matrix

| Area | State | Evidence / note |
|---|---|---|
| Specification / Add-on v2 boundary | COMPLETE | external-service; Host owns generic control plane, Add-on owns domain engines/assets |
| FastAPI core / health / setup | IMPLEMENTED + CLI PARITY + VENV RELOCATION PASS | durable SQLite state, setup profiles, isolated runtimes, staged atomic activation and model-prefetch metadata; `setup plan/apply/repair` use the same orchestration and require explicit known `--accept-term` values; activated console scripts point at the final runtime path |
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
| SFX | TERMS GATE REAL PASS, MODEL NOT TESTED | real setup without acceptance failed `terms_required:stability-ai-community-license` and kept Game Audio `missing`; on 2026-08-26 the user explicitly removed Small-SFX setup/generation from this merge's required scope, so the optional pack remains missing and must be accepted separately after Hugging Face access is configured |
| Japanese SFX conditioning | IMPLEMENTED | ControlDeck LLM may normalize JP intent to English acoustic prompt; both prompts kept in provenance |
| Music/BGM | CLEAN ROCM SETUP + REAL GENERATION PASS | ACE-Step 1.5 pinned source and prepared `acestep-v15-turbo` + `acestep-5Hz-lm-0.6B`; real target generation produced a 10.000 s, 48 kHz stereo WAV without model-cache growth |
| Localization Studio | IMPLEMENTED | JP/EN lines, durable render, `pending/failed/changed/all` retry modes |
| Typed Pipeline | IMPLEMENTED | type checking, `start_at`, `stop_after`, durable execution |
| OpenCode / Agent tools | REAL MCP E2E PASS | `sonic.generate`, detached `sonic.pipeline` and opaque-grant `sonic.pack` completed through the existing ControlDeck Agent MCP; six frozen initial Agent Tools |
| `audio.process` | REAL FFMPEG PIPELINE PASS | fixed-argv ffmpeg trim/duration/gain/loudnorm/resample/channels; real 10 s ACE-Step asset was trimmed to 3.5 s, normalized, converted to 24 kHz mono and persisted with performed-check metadata |
| `package` delivery | REAL PIPELINE + HTTP PASS | canonical audio Asset plus separate ZIP Asset containing `audio/*` and canonical `manifest.json`; provenance, SHA-256 and content route verified |
| Audio delivery profiles | REAL FFMPEG SUBSET PASS | web-mobile MP3, Unity OGG and M5 16 kHz mono WAV were rendered and probed; remaining named profiles retain unit coverage |
| Low-latency PTT WebSocket | REAL TWO-TURN + DURABLE TIMING PASS | no arbitrary 60 s default; optional explicit `max_utterance_seconds` only; real direct-local turns completed with ordered audio; Relay Job persists the six required `ptt.stop`-based latency intervals |
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
| ControlDeck paired Device Relay | REAL PAIRING/ROTATION/REVOKE/MODEL E2E PASS | one-time code reuse returned 403; relay/device-scoped 8-hour token rotated on reconnect; removing the paired user's relay permission rejected reconnect with HTTP 403; protocol-2 CoreS3 frames completed Whisper -> Host llama -> Qwen TTS through #240 |
| Bilingual/mobile browser UX | REAL DIRECT + FULL EMBEDDED CHROME PASS | direct service rendered required JA/EN labels; the authenticated 320x720 opaque-frame workspace now exposes the full task UI with `Studio / Library / Jobs / More`, 48 px targets, one visible view, zero horizontal overflow and zero failed/CORS/console errors; desktop embedded mutation/WebSocket regression also passed |
| Wake/VAD | CLIENT/OPTIONAL ENHANCEMENT | not required for SonicForge v1 acceptance unless it changes the server contract |
| Full-duplex/AEC/barge-in | PLANNED SERVER ENHANCEMENT | intentionally not a v1 promotion blocker |
| Release signing | PUBLIC v0.1.0 BUILD/VERIFY PASS | repository-external production Ed25519 key, canonical byte-exact manifest, fresh-download signature/checksum/digest verification, packaged `doctor` and release-focused tests passed; disposable-key tamper rejection remains covered |
| ControlDeck signed Release Bundle verifier | LIVE CATALOG + GENERIC INSTALL PASS | #239 verifier/update/rollback evidence remains green; #243 keeps setup UI reachable; #244 trusts the publisher key and exposes the public v0.1.0 candidate on the live Host without a per-release digest pin |
| Current branch-wide lightweight tests | PASS WITH WARNING | current branch: 95 passed; only the known Starlette TestClient deprecation warning remains |
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
- idempotent Speech/Music setup repaired stale staging-path venv shebangs without reinstalling; active-path `hf --help` and `accelerate --help` both executed and no managed runtime console script retained a `.staging` shebang;
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

The generic ControlDeck #240 Device Relay also passed real HTTP/WebSocket execution. A user-scoped service credential created a one-time pairing; its first connection returned a relay/device-scoped token with an exact 28,800-second TTL, code reuse was rejected with HTTP 403, and token reconnect returned the same device scope with a rotated credential. The relay replaced that device credential with a Host-minted Add-on service identity upstream. Exact M5Companion protocol-2 frames then completed real Whisper -> ControlDeck llama -> Qwen TTS as local `job:34a43e46-...` and Host Job `2ffd7198f8fc`; the bounded spoken response returned 8.16 s of non-silent 16 kHz PCM (`mean_volume=-22.6 dB`, `max_volume=-5.4 dB`). Speech began at 90.98 s and the turn reached idle at 99.15 s. The run exposed and fixed two low-VRAM defects: the streaming path retained ASR residency while requesting Host AI, and its first TTS request could block the bounded LLM queue while the LLM held GPU admission. ASR is now evicted before Host AI; rejected concurrent TTS admission drains the bounded stream, releases AI and retries as an explicitly recorded sequential fallback. An exact-head warm-cache confirmation completed in 47.92 s with speech beginning at 41.77 s; `job:bc694c70-...` records `delivery_overlap=false` and `sequential_fallback=true` on the TTS stage. A subsequent two-sentence fallback run (`job:30c92bb1-...`, Host Job `fce3ef1b1c8b`) began chunk 1 TTS at the same timestamp as first audio playback, proving generation/playback overlap under the target capacity constraint. The 14.24 s of audio occupied a 19.91 s speaking interval, so a 5.67 s synthesis gap remains a known latency limitation.

The exact timing-instrumented Relay run persisted local `job:e72ed662-...` and completed Host Job `b81d6485ab2c`. From `listen.end`, ASR final was 7,614.8 ms, first LLM token 16,768.6 ms, first speakable chunk 17,106.0 ms, first audio 86,105.8 ms and full response completion 116,536.3 ms. Derived intervals were ASR-to-first-token 9,153.8 ms, ASR-to-first-speakable 9,491.2 ms and speakable-to-audio 68,999.8 ms. The external client observed `speech.begin` at 86,163.9 ms, only 58.1 ms after the durable server milestone. It received 22.00 s of non-silent 16 kHz PCM (`mean_volume=-29.3 dB`, `max_volume=-5.0 dB`); the Job records `delivery_overlap=false` and `sequential_fallback=true`, and Host audit shows Broker activation/renew/release plus `ai.stream`/`ai.release`. This proves the measurement path but also confirms current first-audio latency is not conversationally acceptable on the constrained sequential route. A separate disposable-user check paired successfully, removed `workflows.run` from that actor, and proved the still-valid device credential was rejected on reconnect with HTTP 403; the user state was restored and no Host Job remained active. Physical-device relay remains NOT TESTED because the board is absent.

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
12. Stable Audio 3 Small-SFX clean pack setup + CPU generation without first-use hidden model download (**explicitly removed by the user from this merge's required scope on 2026-08-26; remains `NOT TESTED`, not PASS**);
13. ACE-Step AMD/ROCm clean pack setup + music generation using the prepared checkpoints;
14. real ffmpeg export/audio.process and ZIP package;
15. OpenCode `sonic.generate` / `sonic.pipeline` end to end;
16. existing edge/M5 client direct live API and, if used, paired relay voice-agent path;
17. signed Release Bundle fresh install/update/failure rollback with real public key setup.

After all mandatory local gates pass, run the **single batched milestone CI**, inspect exact PR heads, then use `SF受入マージ`. For this merge only, item 12 is not mandatory by explicit user direction; this exception does not imply model compatibility, availability or license acceptance. Merge generic ControlDeck dependencies before SonicForge and run a short post-merge smoke test.

Until those checks are executed, target-hardware/model compatibility remains `NOT TESTED`, not PASS.

## 10. Merge completion — 2026-08-26

The user explicitly removed only the terms-gated Stable Audio 3 Small-SFX setup/generation from this merge's required scope. Game Audio remains `missing` and **NOT TESTED**; the merge does not claim model availability, compatibility or third-party account acceptance.

The dependency-first merge sequence completed without force or required-check bypass:

- ControlDeck #239 tested head `4ffcc538cddad43463a90d4bad1776e8bfa6406a` merged as `386899ccc90fce273b9c22a0f2050e19e935d83f`;
- ControlDeck #240 tested head `e10abfa10e7cfcb59282687648395a37860dbfc8` merged as `06d558c65db2961ab600d818d7e1604660953bbe`;
- SonicForge #1 tested head `17d5a3228898dde690e376a4f807de2c96db2110` merged as `947aceda7980cbd29a0c2451a2a6fa5249431b54`.

Exact-head and post-merge evidence:

- SonicForge head and merged `main`: 95 tests passed and `compileall` passed;
- ControlDeck #239 exact head: 803 passed, 1 skipped; #240 exact head: 798 passed, 1 skipped;
- merged ControlDeck `main` `06d558c65db2961ab600d818d7e1604660953bbe`: 815 passed, 1 skipped, including a 53-test post-dependency focused smoke;
- local SonicForge health remained `healthy`, with `core`, `speech-essentials` and `music` `ok` and the intentionally skipped `game-audio` pack `missing`;
- the single batched GitHub workflow run `32920460756` passed on merged SonicForge `main` head `947aceda7980cbd29a0c2451a2a6fa5249431b54`.

The physical M5 board remains **NOT TESTED** because no board was connected. Previously recorded real model, browser, Relay, Resource Broker, long-session, release and delivery evidence remains the acceptance evidence for the unchanged runtime code.
