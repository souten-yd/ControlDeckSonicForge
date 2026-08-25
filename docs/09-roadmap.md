# SonicForge Implementation Roadmap

Status: Normative implementation order  
Date: 2026-08-25

## 1. Rule

Implement in dependency order. Do not jump directly to a large TTS/music engine before the lightweight core, setup lifecycle, durable jobs, worker protocol and Host boundary exist.

Each phase is split into independently reviewable PR slices.

## 2. Phase summary

```text
SF0  Foundation and fake runtime
SF1  Add-on v2 integration + public contract freeze
SF2  Japanese TTS + ControlDeck TTS migration
SF3  Japanese ASR
SF4  Game audio / SFX
SF5  Music
SF6  Project, Workflow and Agent integration polish
SF7  Hardening, benchmark and release readiness
```

## 3. SF0 — Foundation and fake runtime

### SF0-0 Documentation baseline

Deliverables:

- master specification
- boundary contract
- dedicated runtime/setup design
- capability/API design
- engine strategy
- UX design
- security/license/provenance
- migration plan
- development rules
- roadmap

Acceptance:

- docs are internally consistent
- all external-engine choices are explicitly candidates until measured
- environment independence and setup-button behavior are normative

### SF0-1 Lightweight core

Implement:

- Python package/project skeleton
- FastAPI service
- configuration/data-dir handling
- DB/migration baseline
- `/health`
- `/addon/v1/capabilities`
- structured logging/redaction
- `sf.sh serve/doctor/test`

Acceptance:

- service starts without torch/models
- clean core venv builds automatically
- `doctor` changes nothing
- health can report `setup_required`

### SF0-2 Worker protocol + fake audio worker

Implement:

- worker descriptor/version handshake
- task execute/progress/cancel
- load/unload/shutdown lifecycle
- fake valid WAV generation
- forced delay/failure/crash modes
- worker supervision/restart boundaries

Acceptance:

- fake worker crash does not kill core
- cancellation works
- produced WAV passes validation/provenance

### SF0-3 Durable internal asset/job state

Implement:

- SonicForge asset records
- provenance/lineage records
- internal task state
- bounded job result metadata
- temp/staging cleanup policy

Acceptance:

- restart does not orphan completed asset metadata
- failed work does not become a valid asset

### SF0-4 Setup planner/state machine

Implement:

- `/setup/status`
- `/setup/plan`
- `/setup/apply`
- cancel/repair skeleton
- staging/atomic activation framework
- runtime fingerprint registry
- model catalog skeleton

Use fake/small components first.

Acceptance:

- one-click flow is idempotent
- browser close/reload does not lose setup state
- interruption/invalid staging does not corrupt active runtime

## 4. SF1 — ControlDeck Add-on v2 integration and contract freeze

### SF1-1 Valid Add-on manifest

Implement root `addon.json` from the reviewed draft.

Validate using current ControlDeck host parser/reference harness.

Acceptance:

- install/enable/effective registry works
- `Audio` navigation is contributed only through manifest
- no SonicForge code is imported by ControlDeck

### SF1-2 Embedded workspace bridge

Implement:

- isolated workspace frontend
- Host theme/locale/safe-area handshake
- route sync
- setup_required/degraded/unavailable views
- no dependency on Host cookies/localStorage

Acceptance:

- real ControlDeck HTTPS embedded proxy test
- dark/light and reload behavior verified
- enabled-but-unavailable navigation remains understandable

### SF1-3 Host Runtime client

Implement client support for:

- token introspection as needed
- Host Jobs
- resource requests/leases
- grants/content
- output staging/commit
- disable/cancel control

Acceptance:

- fake GPU job obtains/releases lease
- file round trip via grants only
- disable while waiting/running tested

### SF1-4 Setup as Host Job

Connect setup flow to ControlDeck Jobs.

Acceptance:

- setup survives browser closure
- global Job opens SonicForge setup detail
- cancel propagates safely

### SF1-5 Public contract freeze

Freeze v1 of:

- Add-on contribution IDs
- capability namespace
- public request/result schemas
- agent tool ids
- workflow executor ids
- asset/provenance required fields
- setup state model

After this point, default evolution is additive.

## 5. SF2 — Japanese TTS and ControlDeck migration

### SF2-0 Historical ControlDeck TTS inventory

Locate exact source commits/branches and write:

`docs/migration/controldeck-tts-inventory.md`

No migration coding until callers/settings/data locations are verified.

### SF2-1 Qwen3-TTS worker

Implement first recommended general TTS adapter/runtime.

Minimum:

- Japanese synthesis
- logical voices
- balanced quality preset
- output validation/provenance
- resource estimates
- load/unload
- clean setup installation

Acceptance:

- real Japanese fixtures generated
- cold/warm latency and RAM/VRAM measured
- cancel/recovery measured

### SF2-2 Qwen advanced profiles

Add as supported/benchmarked:

- fast/quality routing
- reference voice clone
- voice design
- streaming/low-latency path

Keep unsupported features hidden by capability metadata.

### SF2-3 Style-Bert-VITS2 worker

Focus:

- Japanese character/style voices
- imported/custom voice assets
- CPU/GPU behavior as available
- per-model license metadata

Do not copy the historical root/file-manager security model from the reference repo.

### SF2-4 GPT-SoVITS worker

Focus:

- reference/few-shot workflows
- imported trained models
- Japanese quality benchmark
- rights/provenance flow

### SF2-5 Voice library + pronunciation/dialogue UX

Implement:

- logical voice records
- built-in/imported/clone/design distinctions
- rights confirmation
- preview
- dialogue batch
- pronunciation overrides

### SF2-6 ControlDeck TTS migration/cutover

Execute `07-controldeck-tts-migration.md`.

Acceptance:

- useful prior behavior covered or explicitly retired
- old data not silently deleted
- no permanent Sonic-specific Host dependency
- rollback documented/tested

## 6. SF3 — Japanese ASR

### SF3-1 ASR adapter contract and file transcription

Implement generic ASR worker request/result and timestamps.

### SF3-2 Kotoba-Whisper v2.0 candidate

Implement and benchmark:

- Japanese file transcription
- segment timestamps
- VAD/chunking path
- GPU/CPU behavior as supported

Promotion to recommended requires local quality/speed evidence.

### SF3-3 ReazonSpeech K2 candidate

Implement efficient CPU-oriented path if target tests validate it.

Compare against Kotoba on:

- CER
- real-time factor
- RAM
- startup
- streaming suitability

### SF3-4 Live transcription

Implement:

- microphone/session UX
- bounded real-time session protocol
- backpressure/heartbeat
- cancel/stop
- optional GPU lease

### SF3-5 ASR exports

Add:

- text
- timestamped JSON
- subtitle formats when supported
- optional diarization/alignment only after separate adapters are proven

## 7. SF4 — Game audio / SFX

### SF4-1 Deterministic audio processing

Before generative SFX, implement robust:

- probe/decode validation
- trim
- fade
- resample
- normalization/loudness
- channel conversion
- loop metadata
- codec export

Acceptance:

- malformed/oversized inputs handled safely
- processing preserves lineage

### SF4-2 Stable Audio 3 Small-SFX candidate

Implement first SFX adapter if license/runtime verification passes.

Benchmark categories:

- UI
- impact
- mechanical
- magic/sci-fi
- ambience
- loop

### SF4-3 Alternate SFX engine evaluation

Evaluate TangoFlux or a newer suitable engine only if it offers a measurable advantage or fills a capability gap.

Do not add engines merely to increase count.

### SF4-4 Game Audio workspace

Implement:

- category presets
- variation groups
- coherent sound-pack jobs
- loop handling
- project packaging profiles

### SF4-5 Project asset packs

Use Host output grants for project-relative placement. No raw project paths.

## 8. SF5 — Music

### SF5-1 ACE-Step 1.5 candidate runtime

Implement the smallest stable music capability first:

`music.generate`

Measure:

- target AMD GPU compatibility
- load time
- generation latency
- VRAM
- duration fidelity
- output validity

### SF5-2 BGM/loop UX

Implement:

- instrumental BGM default
- duration
- BPM hint
- loop workflow
- candidate variations

### SF5-3 Music transforms

Add only after verified by engine:

- remix
- extend
- repaint/edit
- stems/accompaniment

Capabilities are advertised individually.

### SF5-4 Advanced song workflows

Lyrics/song/cover/reference personalization remains later/experimental and must pass additional rights/licensing review.

## 9. SF6 — Workflow, Agent and project integration polish

### SF6-1 Workflow executors

Stabilize:

```text
sonic.speech.synthesize
sonic.speech.transcribe
sonic.audio.generate
sonic.music.generate
```

Acceptance:

- dry-run/schema validation
- unavailable saved nodes fail clearly without deletion
- project export uses grants

### SF6-2 Agent tools

Stabilize:

```text
sonic.capabilities
sonic.generate
sonic.transcribe
sonic.inspect
sonic.pack
```

Acceptance:

- agents can operate by capability without model IDs
- bounded outputs
- no raw paths

### SF6-3 Context actions

Add useful actions for selected file/project/job contexts.

### SF6-4 MediaForge composition tests

Through ControlDeck only, validate cross-media workflows such as:

```text
MediaForge visual asset
 -> ControlDeck workflow/project context
 -> SonicForge SFX/BGM/dialogue
 -> authorized project outputs
```

No direct private import/filesystem coupling.

## 10. SF7 — Hardening and release readiness

### SF7-1 Clean-install matrix

Test:

- recommended
- speech-only
- cpu-only where practical
- upgrade
- repair
- rollback
- interrupted setup

### SF7-2 Hardware/resource matrix

Record support tiers for tested CPU/GPU/backends.

Do not mark unsupported hardware as supported from upstream claims alone.

### SF7-3 Security/license audit

Review every promoted engine/model and import path.

### SF7-4 Performance and residency tuning

Tune:

- cold vs warm model behavior
- broker estimates
- safe concurrency
- idle unload policy
- setup download/storage behavior

### SF7-5 Release docs

Finalize:

- user setup instructions
- troubleshooting
- engine/model license table
- compatibility matrix
- migration guide
- backup/restore guidance

## 11. Host change track

Host changes are **not** phases in this repository.

When blocked:

1. document the gap in SonicForge;
2. prove it is generic;
3. open a separate ControlDeck design/PR;
4. keep SonicForge degraded/blocked until the generic contract exists.

Likely future generic candidate, only if truly needed:

- signed/approved managed-service bootstrap for installing an entirely absent Add-on service from ControlDeck UI.

Do not solve this with an arbitrary command field in the Add-on manifest.

## 12. Release milestones

### v0.1 — Foundation

SF0 + essential SF1 complete using fake workers.

### v0.2 — Speech

TTS baseline + Japanese ASR baseline, setup button and Host integration usable.

### v0.3 — Game Audio

SFX + processing + project pack workflow.

### v0.4 — Music

Local BGM/music generation available on verified hardware.

### v1.0 — Stable SonicForge

Contract-frozen speech/audio/music platform with migration, workflow/agent integration, clean setup/repair and published evidence/compatibility.