# SonicForge Implementation Roadmap

Status: Normative implementation order  
Date: 2026-08-25

## 1. Rule

Implement in dependency order. Do not jump directly to large TTS/music engines before the lightweight core, signed release lifecycle, setup state, durable jobs, worker protocol and Host boundary exist.

Each PR is one independently reviewable slice.

## 2. Phase summary

```text
SF0  Foundation, release packaging and fake runtime
SF1  Add-on v2 integration + bilingual UX shell + public contract freeze
SF2  Japanese/English TTS + voice/localization foundation + ControlDeck TTS migration
SF3  Japanese/English ASR + live transcription + speech QA
SF4  Game Audio / SFX
SF5  Music
SF6  Project, Localization, Workflow and Agent integration polish
SF7  Hardening, benchmark and release readiness
```

## 3. SF0 — Foundation and trusted lightweight feature

### SF0-0 Documentation baseline

Deliverables include the normative architecture/product documents through `18-controldeck-generic-ai-media-gateway.md` plus the implementation evidence ledger.

Acceptance:

- no contradictions on environment ownership
- Japanese + English first-class language contract
- Easy/Customize/Expert UX fixed
- Speech Essentials default setup fixed
- publisher-signature release direction fixed
- external engines remain candidates until measured

### SF0-1 Lightweight core

Implement:

- Python package/project skeleton
- FastAPI service
- config/data-dir
- DB/migration baseline
- `/health`
- `/addon/v1/capabilities`
- localization resource framework for `ja`/`en`
- structured logging/redaction
- `sf.sh serve/doctor/test`

Acceptance:

- starts without torch/models
- clean core environment builds
- `doctor` is read-only
- health reports `setup_required`
- capability response can advertise language-specific state

### SF0-2 Worker protocol + fake audio worker

Implement:

- descriptor/version/capability/language handshake
- execute/progress/cancel
- load/unload/shutdown
- fake valid WAV
- delay/failure/crash modes
- supervision/restart boundary

Acceptance:

- crash does not kill core
- queued/running cancellation semantics tested
- fake WAV validation/provenance passes

### SF0-3 Durable asset/job/localization state

Implement:

- assets
- provenance/lineage
- internal task state
- bounded Host Job result metadata
- variation groups
- project/voice profile skeletons
- localization batch/line state skeleton
- staging cleanup

Acceptance:

- restart preserves authoritative job/asset state
- failed work cannot become valid asset
- browser state is never sole owner of expensive preparation

### SF0-4 Setup planner/state machine

Implement:

- setup status/plan/apply/cancel/repair
- `speech-essentials` default
- optional `game-audio`, `music`, `full-studio`, `cpu-essentials`
- staging/atomic activation
- runtime fingerprint registry
- model catalog skeleton

Use fake/small packs first.

Acceptance:

- idempotent
- reload/background resilient
- interruption does not damage active runtime
- contextual optional-pack setup works

### SF0-5 Signed release bundle build/sign tooling

Mirror the proven MediaForge direction:

- build lightweight ControlDeck feature bundle
- bind package/Add-on/package-version identity
- canonical signed release manifest
- Ed25519 signing script/build runtime
- signature self-verification
- artifact SHA-256/size inside signed manifest
- disposable-key negative tests

Acceptance:

- release bundle contains no heavyweight ML runtime/model
- private key never enters repository/runtime
- tampered manifest/artifact tests fail
- wrong feature/version/platform/arch tests fail

## 4. SF1 — ControlDeck integration and public contract freeze

### SF1-0 Host release-signature compatibility gate

Before claiming one-click fresh install, verify the current ControlDeck generic Release Bundle Feature provider supports the publisher-signature contract targeted in `13-release-distribution-and-signing.md`.

Current 2026-08-25 inspection found MediaForge already publishing signed releases while inspected ControlDeck `main` still exposed older SHA-pin verifier behavior. Treat this as an explicit compatibility gate, not a reason to reintroduce SonicForge per-release SHA pins.

If Host work is required:

- separate ControlDeck PR
- generic publisher-signature support only
- no SonicForge-specific verifier branch
- keep capability allowlist/downgrade/safe extraction rules

### SF1-1 Valid Add-on manifest

Implement root `addon.json` from reviewed draft.

Acceptance:

- install/enable/effective registry
- single `Audio` Host navigation
- no Host import
- ja/en localized manifest labels follow Host locale selection

### SF1-2 Bilingual embedded Studio shell

Implement:

- isolated workspace
- Host theme/locale/safe-area handshake
- `Studio / Voices / Library / Runtime`
- Studio task tabs
- Easy/Customize/Expert disclosure
- setup/degraded/unavailable states
- server-side locale override
- no Host cookies/shared localStorage assumptions
- reconnect/visibility-return handling

Acceptance:

- Japanese UI browser E2E
- English UI browser E2E
- desktop/mobile no-overflow checks
- dead WebSocket/reopen state recovers

### SF1-3 Host Runtime client

Implement:

- token introspection as required
- Host Jobs
- resources/leases
- grants/content
- output staging/commit
- disable/cancel control
- generic AI release/Host capability paths only when needed by actual workflows

Acceptance:

- fake GPU lease lifecycle
- file round-trip via grants
- disable while waiting/running
- no raw paths/tokens in results/logs

### SF1-4 Setup as Host Job

Connect Speech Essentials and optional pack setup to durable Host Jobs.

Acceptance:

- browser closure does not stop ownership/progress
- global job deep link works
- queued cancel and running cancel behave correctly

### SF1-5 Public contract freeze

Freeze v1:

- Add-on contribution IDs
- four stable workflow executors
- six initial agent tools
- capability naming principles
- `auto|ja|en` content language contract
- public request/result schemas
- asset/provenance required fields
- setup state/profile names
- stable error codes

Rich engine features remain capability metadata/extensions rather than growing the frozen executor set.

## 5. SF2 — Bilingual TTS, voices and migration

### SF2-0 Historical ControlDeck TTS inventory

Locate exact historical source commits/branches and write migration inventory before porting behavior.

### SF2-1 Qwen3-TTS bilingual baseline

Implement first general TTS adapter/runtime.

Minimum:

- Japanese synthesis
- English synthesis
- representative mixed-language cases
- logical voices
- Recommended quality route
- output validation/provenance
- resource estimates
- load/unload/cancel/recovery
- clean Speech Essentials installation

Acceptance:

- Japanese fixture evidence
- English fixture evidence
- mixed fixture evidence
- cold/warm latency and RAM/VRAM measured

### SF2-2 Preview / candidate / advanced Qwen profiles

Add only after measured:

- Fast/High quality routing
- reference clone
- voice design
- streaming/low-latency
- bounded A/B preview candidates

### SF2-3 Style-Bert-VITS2 Japanese specialist

Focus:

- Japanese character/style voices
- custom voice assets
- CPU/GPU behavior where useful
- model licensing

Do not force it as an English route without evidence.

### SF2-4 GPT-SoVITS reference/few-shot

Focus:

- authorized reference workflows
- imported trained voices
- Japanese/English/multilingual behavior only as verified
- rights/provenance

### SF2-5 Voice library + pronunciation dictionary

Implement:

- logical voices
- source/rights distinctions
- Japanese/English preferred/tested language metadata
- preview
- voice consistency profiles
- project pronunciation/terminology dictionaries
- dialogue batch

### SF2-6 Localization Studio foundation

Implement:

- line table/import/export
- character -> voice mappings
- JP/EN paired text
- durable bilingual render batch
- project naming/output profile
- review state

QA can be placeholder until ASR route is available, but schema/state should not need redesign.

### SF2-7 ControlDeck TTS migration/cutover

Execute migration plan after SonicForge behavior is actually available.

Acceptance:

- useful legacy behavior represented or explicitly retired
- old data not silently deleted
- no permanent Sonic-specific Host ML subsystem
- rollback documented/tested

## 6. SF3 — Bilingual ASR and speech QA

### SF3-1 Generic ASR adapter contract

Implement file transcription, language metadata and timestamps.

### SF3-2 Japanese ASR candidates

Benchmark Kotoba-Whisper and ReazonSpeech/current suitable routes for Japanese.

### SF3-3 English/multilingual ASR route

Implement and benchmark a current multilingual Whisper-family or measured successor route for:

- English
- mixed Japanese/English
- timestamps
- long-form
- practical target hardware backends

Do not choose exact default before evidence.

### SF3-4 Language-aware router

Route:

- explicit Japanese to best Japanese route
- explicit English to best English route
- Auto/mixed to verified multilingual or segmented strategy

Acceptance includes incorrect-silent-fallback tests.

### SF3-5 Live transcription

Implement microphone/session protocol, reconnect, backpressure, stop/cancel and optional GPU lease.

### SF3-6 Speech QA

Implement optional TTS->ASR normalized round-trip flagging for:

- missing phrases
- repeated phrases
- severe mismatch

Never label naturalness/emotion as checked by this heuristic.

### SF3-7 ASR exports

Text, timestamped JSON and subtitle formats; diarization/alignment only when separately verified.

## 7. SF4 — Game Audio / SFX

### SF4-1 Deterministic audio processing + QA

Implement decode/probe, trim, fade, resample, loudness/normalization, channel conversion, loop metadata/seam checks and codec export.

### SF4-2 First SFX candidate

Evaluate/adopt Stable Audio 3 Small-SFX if license/runtime/hardware evidence passes.

### SF4-3 Alternate SFX evaluator

Add TangoFlux/newer engine only for measurable benefit/capability gap.

### SF4-4 Game Audio Studio

Implement presets, Easy/Customize/Expert, bounded candidates, variation groups and sound-pack jobs.

### SF4-5 Project asset profiles

Export through scoped Host grants. No raw paths.

## 8. SF5 — Music

### SF5-1 ACE-Step 1.5 candidate

Implement smallest stable `music.generate` path and verify target hardware.

### SF5-2 BGM/loop Studio

Easy duration/instrumental/loop; Customize BPM/mood/quality/candidates; Expert engine-native details.

### SF5-3 transforms

Remix/extend/repaint/stems only after verified and advertised individually.

### SF5-4 advanced song workflows

Lyrics/cover/reference personalization remains later/experimental with additional rights review.

## 9. SF6 — Project, workflow, agent and localization polish

### SF6-1 Stable Workflow executors

```text
sonic.speech.synthesize
sonic.speech.transcribe
sonic.audio.generate
sonic.music.generate
```

No mandatory separate localization executor unless real workflow evidence justifies additive contract growth.

### SF6-2 Agent tools

```text
sonic.capabilities
sonic.generate
sonic.pipeline
sonic.transcribe
sonic.inspect
sonic.pack
```

Language/profile based; model IDs optional only.

### SF6-3 Context actions

Useful file/project/job actions with localized labels and grant-only files.

### SF6-4 Localization production workflow

Complete:

- CSV/JSON interchange
- bilingual batch
- QA filter
- project profile
- resume partial batch
- only retry failed/changed lines

### SF6-5 MediaForge composition

Through ControlDeck contracts only:

```text
visual asset/project context
 -> SonicForge dialogue/SFX/BGM
 -> scoped project outputs
```

No internal imports/shared directory shortcuts.

## 10. SF7 — Hardening and release readiness

### SF7-1 Clean install/update matrix

Test signed lightweight install plus:

- Speech Essentials
- Game Audio optional pack
- Music optional pack
- Full Studio
- CPU Essentials where practical
- update/repair/rollback/interrupted setup

### SF7-2 Language quality matrix

Publish Japanese/English/mixed support evidence by capability/engine/hardware.

### SF7-3 Hardware/resource matrix

Only measured configurations are supported/recommended.

### SF7-4 Security/license/signature audit

Review:

- release signing/key handling
- bundle verifier negative paths
- every promoted engine/model/import path
- voice-rights flows

### SF7-5 UX resilience matrix

Real browser tests:

- Japanese/English locale
- desktop/mobile
- network drop/reconnect
- background/restore
- running-job reattach
- queued/running cancel
- empty/partial capability setup

### SF7-6 Performance/residency tuning

Cold/warm model, broker estimates, safe concurrency, idle unload and setup storage/download.

### SF7-7 Release documentation

User setup, troubleshooting, license table, compatibility matrix, migration, backup/restore and publisher-key/release process.

## 11. Host change rule

Host changes are separate ControlDeck PRs.

For publisher signing, the generic Host contract must verify trusted publisher signatures rather than adding `sonic-forge`-specific code. Current compatibility is a tracked SF1 gate.

For any other blocker:

1. show why SonicForge cannot solve it safely;
2. prove generic reuse;
3. design/version Host contract;
4. implement/test separately;
5. let SonicForge degrade until available.

## 12. Milestones

### v0.1 — Foundation

SF0 + essential SF1 using fake workers and signed release tooling.

### v0.2 — Speech

Japanese/English TTS + ASR baseline, Speech Essentials, bilingual UI, basic Localization Studio.

### v0.3 — Game Audio

SFX + processing/QA + project packs.

### v0.4 — Music

Verified local BGM/music generation.

### v1.0 — Stable SonicForge

Contract-frozen bilingual speech/audio/music/localization platform with signed distribution, migration, workflow/agent integration, clean setup/repair, resilient UI and published evidence.
