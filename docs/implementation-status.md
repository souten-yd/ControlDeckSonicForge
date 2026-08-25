# SonicForge Implementation Status

Last updated: 2026-08-25

This document records **observed implementation state and evidence**. `IMPLEMENTED` means code exists on `impl/full-platform-baseline`; it does not imply current branch-wide tests, real ControlDeck E2E, model inference, or target-hardware validation. Anything not actually executed is explicitly marked `NOT TESTED`.

## 1. Current summary

| Area | State | Evidence / note |
|---|---|---|
| Specification baseline | COMPLETE | Normative architecture/specification exists and has been extended for music/SFX, typed pipelines, M5 and the common Host gateway |
| Japanese + English product contract | IMPLEMENTED baseline | Separate UI locale/content language/voice language concepts; bilingual speech/localization APIs |
| Easy / Customize / Expert UX | IMPLEMENTED | Normal flow hides engine/model details |
| SonicForge core service | IMPLEMENTED | FastAPI, `/health`, capabilities, SQLite, assets, voices, jobs and setup APIs |
| Production bootstrap | IMPLEMENTED, LATEST SUITE NOT RUN | `sonicforge.bootstrap:app` installs pipeline/delivery/job extensions while keeping the root SPA mount last |
| Dedicated SonicForge state/cache/runtimes | IMPLEMENTED | no ControlDeck/MediaForge worker imports or shared venv/DB |
| Add-on v2 manifest | IMPLEMENTED | 4 stable workflow executors, **6 agent tools** including `sonic.pipeline`, context actions and setup checklist |
| Browser Bridge integration | IMPLEMENTED | Host `host.file.pick`, scoped grants and proxy-relative URLs |
| Direct embedded settings route | IMPLEMENTED, TEST ADDED | `/settings/` opens Runtime view |
| Browser reconnect | IMPLEMENTED, NOT BROWSER-E2E TESTED | WebSocket backoff/reload implemented |
| Durable generation jobs | IMPLEMENTED | server-owned SQLite Job state, cancel and restart interruption handling |
| Host Job integration | IMPLEMENTED, NOT HOST-E2E TESTED | create/attach, progress, terminal state and Host cancel polling |
| Resource Broker integration | IMPLEMENTED, NOT HOST-E2E TESTED | request/wait/activate/renew/release and token refresh |
| Scoped input/output grants | IMPLEMENTED, NOT HOST-E2E TESTED | no raw Host paths in public contract |
| ControlDeck Generic AI/Media Gateway client | IMPLEMENTED, TESTS ADDED NOT RUN | versioned discovery plus legacy Host projection in `host/client.py` |
| ControlDeck Generic AI/Media Gateway Host | IMPLEMENTED ON SEPARATE DRAFT PR, NOT E2E TESTED | ControlDeck PR #240 / `feat/generic-ai-media-gateway`; additive discovery only, current endpoints remain authoritative |
| MediaForge alignment | CONFIRMED | MediaForge already uses the same Host Jobs/resources/grants/AI complete/release primitives |
| Typed Pipeline schema | IMPLEMENTED, TESTS ADDED | typed text/audio stages, `start_at`, `stop_after`, delivery modes and invalid-chain rejection |
| Durable Typed Pipeline runner | IMPLEMENTED, TESTS ADDED NOT RUN | `pipeline_runtime.py`; reuses Job/asset/provenance/Host control boundaries |
| Stage-local GPU admission | IMPLEMENTED, REGRESSION TEST ADDED NOT RUN | local worker lease -> release -> Host AI -> `ai.release` -> next worker lease |
| OpenCode `sonic.pipeline` | IMPLEMENTED CONTRACT, NOT AGENT-MCP E2E TESTED | agent contribution and JSON Schema are in `addon.json`/`schemas/pipeline-request.json` |
| Pipeline text -> Host LLM -> TTS | IMPLEMENTED, FOCUSED MOCK-HOST TEST ADDED NOT RUN | Host AI output can feed TTS and return a durable audio asset |
| Pipeline audio -> ASR -> Host LLM -> TTS | IMPLEMENTED, RESOURCE-ORDER TEST ADDED NOT RUN | audio grant input and stage-local admission path implemented |
| Pipeline text -> SFX / Music | IMPLEMENTED, FAKE-WORKER TESTS ADDED NOT RUN | uses the same durable pipeline runner |
| `audio.process` pipeline stage | SCHEMA ONLY / NOT IMPLEMENTED | rejected explicitly at runtime until deterministic stage is connected |
| Pipeline `package` delivery | NOT IMPLEMENTED | contract reserved but runtime rejects it explicitly |
| Pipeline WebSocket delivery | LIVE SESSION REQUIRED / NOT IMPLEMENTED | durable runner rejects WS delivery rather than pretending it is live |
| M5/device descriptor schema | IMPLEMENTED, TEST ADDED | `sonic-edge/1`, capability negotiation, PCM/Opus descriptors, wake/VAD/AEC flags |
| M5 binary framing | IMPLEMENTED, TESTS ADDED | versioned mic/speaker frames, sequence/sample clock, bounded payload/queue |
| M5/voice-chat live session runtime | NOT IMPLEMENTED | PTT live server remains next phase |
| Generic paired Device Session Host relay | DESIGNED, NOT IMPLEMENTED | intentionally advertised unavailable by Gateway v1; required before production M5 LAN/Tailscale use |
| Speech Essentials provisioning | IMPLEMENTED, TARGET MACHINE NOT TESTED | speech CPU/ROCm runtime/model setup code present |
| Qwen3-TTS CustomVoice / VoiceDesign / Clone | IMPLEMENTED, MODEL INFERENCE NOT TESTED | logical voice routing, reference grant import and rights confirmation present |
| Japanese ASR | IMPLEMENTED, MODEL INFERENCE NOT TESTED | Kotoba-Whisper route present |
| English/multilingual ASR | IMPLEMENTED, MODEL INFERENCE NOT TESTED | Whisper large-v3-turbo route present |
| Game Audio model decision | RESEARCHED + ADAPTER IMPLEMENTED, MODEL NOT TESTED | Stable Audio 3 Small-SFX CPU-first |
| Japanese SFX PromptNormalizer helper | IMPLEMENTED, UNIT TESTS EXIST | Host AI converts Japanese intent to concise English acoustic conditioning when available |
| Japanese SFX direct-Job integration | IMPLEMENTED, INTEGRATION TEST ADDED NOT RUN | normalization occurs after durable Job creation and before worker admission |
| Japanese SFX pipeline integration | IMPLEMENTED, LATEST TESTS NOT RUN | prompt-aware pipeline runtime normalizes before SFX resource acquisition |
| Prompt provenance | IMPLEMENTED, TEST ADDED NOT RUN | original and engine-conditioning prompt are stored in asset metadata and Provenance parameters |
| Music primary model | RESEARCHED + ADAPTER IMPLEMENTED, MODEL NOT TESTED | ACE-Step 1.5 Turbo first; ROCm upstream-supported but SonicForge target unverified |
| Music CPU fallback | PLANNED | Stable Audio 3 Small-Music |
| Localization Studio storage/render | IMPLEMENTED | paired JP/EN lines and durable rendering |
| Localization partial retry | IMPLEMENTED | `pending / failed / changed / all` |
| Deterministic WAV QA | IMPLEMENTED baseline | decode/duration/hash; semantic remains `not_checked` |
| Audio delivery profiles | IMPLEMENTED, TESTS ADDED NOT RUN | master WAV, voice WAV, Unity, Unreal, Godot, Web/mobile and M5 profiles |
| Durable `audio.export` | IMPLEMENTED, TESTS ADDED NOT RUN | safe argv ffmpeg subprocess, derived asset/provenance and optional project grant commit |
| Real ffmpeg/ffprobe export | NOT TESTED | tests use fake conversion for orchestration; real codecs remain batched validation gate |
| TTS->ASR semantic QA | NOT IMPLEMENTED | design only |
| Signed release bundle build | IMPLEMENTED | lightweight bundle build/packaging |
| SonicForge Ed25519 release signing | IMPLEMENTED + FOCUSED TESTED | canonical manifest and negative tests; focused signing suite previously 4 passed |
| ControlDeck signature-aware release verifier | IMPLEMENTED ON DRAFT PR, NOT E2E TESTED | ControlDeck PR #239 |
| Publisher public-key registration | OPERATIONAL INPUT REQUIRED | production public key not invented/committed |
| Signed fresh install/update/rollback | NOT TESTED | requires real publisher key + Host environment |
| Target hardware model performance | NOT TESTED | Qwen/Whisper/Stable Audio/ACE-Step not benchmarked by current SonicForge branch |
| Batched CI | NOT RUN | deliberately deferred; latest branch-wide suite is not claimed green |

## 2. Common ControlDeck control-plane decision

SonicForge now follows the same split already exercised by MediaForge:

```text
ControlDeck Generic AI / Media Gateway
  auth / capability scope
  Host Jobs / cancel / progress
  Resource Broker / queue / leases / residency
  provider-neutral Host AI + explicit release
  scoped grants / output receipts
  Agent MCP / Workflow projection
  embedded HTTP/WebSocket relay
  future generic paired Device Session

SonicForge
  TTS / ASR / SFX / music engines
  voice/localization/audio semantics
  Typed Media Pipeline
  M5 turn/audio semantics
  audio assets/provenance/QA/delivery profiles
```

ControlDeck PR #240 adds only versioned discovery. Existing endpoint families are preserved and remain authoritative.

The SonicForge client supports both:

```text
new Host -> /gateway/capabilities
old Host -> existing service-token grants + /ai/capabilities projected locally
```

Discovery never grants authority.

## 3. Typed Pipeline implementation

Implemented stage types:

```text
speech.asr      audio -> text
host.ai.text    text  -> text
speech.tts      text  -> audio
audio.sfx       text  -> audio
music.generate  text  -> audio
audio.process   audio -> audio   # schema reserved; execution not implemented yet
```

Examples:

```text
audio -> ASR -> ControlDeck LLM -> TTS -> asset
text  -> ControlDeck LLM -> TTS -> asset
text  -> TTS -> asset
text  -> SFX -> asset
text  -> Music -> asset
```

`start_at` / `stop_after` may select a valid sub-chain. Invalid media-type transitions such as `LLM -> ASR` are rejected before execution.

Pipeline Jobs are stored in the same durable Job table and use the same cancellation/Host Job surfaces as direct generation.

### Stage-local resource invariant

The pipeline must never hold one GPU lease around the whole chain:

```text
ASR acquire -> ASR -> release
Host LLM admission -> complete -> ai.release
TTS acquire -> TTS -> release
```

A regression test records this ordering. That test has been added but not yet executed in the current batch.

## 4. OpenCode / agent path

SonicForge does not add a second MCP server.

```text
OpenCode
 -> ControlDeck Agent MCP
 -> sonic.generate / sonic.transcribe / sonic.pipeline / sonic.inspect / sonic.pack
 -> durable Host/SonicForge Job
 -> Asset
 -> optional current-project output grant
 -> commit receipt
```

The new `sonic.pipeline` contribution is justified by the explicit requirement to choose pipeline start/end stages. The four stable Workflow executors remain unchanged; no generic free-form pipeline Workflow executor was added prematurely.

## 5. Japanese SFX prompt conditioning

Stable Audio Small-SFX is treated as English-conditioning-first. SonicForge keeps Japanese UX and may perform:

```text
Japanese user intent
 -> durable Job exists
 -> ControlDeck text.generate
 -> concise English acoustic engine prompt
 -> ControlDeck ai.release
 -> SFX worker admission/generation
```

If Host AI is unavailable, the state is explicitly recorded rather than hidden. The original prompt is retained.

Metadata/provenance records:

- user prompt
- user prompt language
- engine prompt
- engine prompt language
- normalizer identity
- normalization state/failure reason

The direct Job path and typed pipeline SFX path both contain this orchestration now. Latest integration tests are added but not run.

## 6. Audio delivery implementation

Generation output remains a canonical SonicForge audio asset. Delivery is derived deterministically rather than regenerating through a model.

Initial profiles:

```text
master-wav   48 kHz / 24-bit PCM
voice-wav    48 kHz mono / 16-bit PCM
unity-sfx    WAV 48 kHz / 16-bit
unity-bgm    OGG/Vorbis 48 kHz
unreal-sfx   WAV 48 kHz / 16-bit
godot-sfx    WAV 48 kHz / 16-bit
godot-bgm    OGG/Vorbis 48 kHz
web-mobile   MP3 160 kbps
m5-wav       WAV 16 kHz mono / 16-bit
```

API:

```text
GET  /addon/v1/delivery/audio/profiles
POST /addon/v1/assets/{asset_id}/export
```

The export runs as durable `audio.export`, invokes ffmpeg by validated argv (no shell), creates a derived asset with source lineage and may commit it through a scoped ControlDeck project grant.

Real ffmpeg/codec execution remains `NOT TESTED` on the latest branch.

## 7. M5 / live audio state

Implemented foundation:

- device capability schema for M5/mobile/PC/simulator
- PCM/Opus negotiation fields
- wake/VAD/AEC capability flags
- `sonic-edge/1` binary mic/speaker frame
- sequence/sample-clock gap detection
- bounded audio queues
- live-session schema/presets

Not implemented yet:

- authenticated production live-session WebSocket runtime
- PTT turn engine
- streaming ASR/TTS integration
- generic ControlDeck paired Device Session
- M5 firmware client in this repository
- full duplex / barge-in

Production M5 architecture deliberately forbids giving an M5 browser cookies/service tokens or directly exposing the loopback SonicForge service to LAN. A generic paired Device Session must be implemented in ControlDeck first.

## 8. Focused validation actually executed

### Release signing

Previously executed:

```text
pytest -q tests/test_release_signing.py tests/test_release_signing_negative.py
.... [100%]
4 passed in 0.07s
```

This covered valid signing plus artifact/context/wrong-key/malformed/noncanonical failures.

### Earlier lightweight baseline

An earlier branch state had 9 lightweight tests passing and a fake-worker/Uvicorn smoke. The code has changed materially since then, therefore that result is **not** proof that the current branch is green.

### Current validation policy

New tests now cover, but have **not yet been run as a batch**:

- production bootstrap route ordering
- Gateway v1 discovery and legacy fallback
- typed pipeline compile/runtime
- Host AI -> TTS composition
- ASR -> Host AI -> TTS stage-local resource ordering
- M5 edge framing/schema
- PromptNormalizer durable/provenance integration
- delivery profile argv and derived asset orchestration
- existing localization/core/Host client/contracts

CI remains intentionally deferred per the requested batched-CI policy.

## 9. Release / promotion gates still required

Before production-ready status:

1. run one current branch-wide lightweight/static batched validation;
2. resolve every failure and only then run the intended batched GitHub CI;
3. merge/validate ControlDeck PR #240 Generic Gateway discovery;
4. merge/validate ControlDeck PR #239 publisher-signature verifier;
5. register real publisher public key and test signed fresh install/update/downgrade rejection/rollback;
6. run real ControlDeck Host Job/Resource/grant/Agent MCP E2E;
7. run Japanese/English Qwen3-TTS inference and voice clone/design on target hardware;
8. run Japanese/English/mixed ASR fixtures;
9. run Stable Audio 3 Small-SFX CPU fixture bank including Japanese PromptNormalizer path;
10. reproduce ACE-Step ROCm runtime and benchmark 30/60/90-second music generation;
11. validate real ffmpeg/ffprobe delivery codecs and game import profiles;
12. implement/test `audio.process` and package delivery only where required;
13. implement browser/mobile PTT live session;
14. implement a separate generic ControlDeck paired Device Session before production M5 access;
15. then validate M5 PTT -> ASR -> LLM -> TTS end-to-end and measure latency/buffer/drop behavior;
16. add WakeNet/VAD and later AEC/barge-in only after the PTT baseline is stable.

Until these checks complete, heavy model/hardware compatibility and live-device readiness remain `NOT TESTED` even where contracts/adapters exist.
