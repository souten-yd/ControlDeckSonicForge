# Decisions and Open Questions

Status: Living design ledger  
Last updated: 2026-08-25

## 1. Purpose

This document separates fixed architectural/product decisions from questions that still require measurement or a generic Host implementation.

Do not reopen fixed decisions casually. If evidence requires a change, record reason, impact and migration before changing normative contracts.

## 2. Fixed decisions

### D-001 — SonicForge is an out-of-process ControlDeck Add-on

- Add-on Contract v2 external service
- no SonicForge Python/JavaScript imported into ControlDeck

Reasons: dependency/crash isolation, independent releases, security/audit boundary and reusable Add-on architecture.

### D-002 — SonicForge and MediaForge are siblings

- no parent/child runtime relationship
- no shared internal modules/database/venv
- composition through ControlDeck workflow/agent/grant contracts

### D-003 — SonicForge owns its environment

- separate core environment
- separate heavy runtime packs
- separate model/data/state
- separate default cache
- user-configured external model libraries may be supported explicitly

### D-004 — One-click capability setup is mandatory

The normal user does not manually create venvs or run pip commands.

Default first setup is **Speech Essentials**, while Game Audio and Music are optional one-click packs. Full Studio is explicit rather than the default.

### D-005 — Product installation uses the generic trusted Release Bundle Feature direction

Do not add an arbitrary shell command to the Add-on manifest.

The target flow is:

```text
ControlDeck generic trusted feature installer
 -> signed lightweight SonicForge release bundle
 -> SonicForge service healthy/setup_required
 -> SonicForge one-click ML capability provisioning
```

### D-006 — Capability-first public API

Stable callers use task/capability IDs. Engine/model IDs are optional Expert routing hints.

### D-007 — Japanese and English are first-class speech languages

Japanese remains a priority quality benchmark, but English is not a secondary afterthought.

Initial requirements:

- Japanese TTS/ASR
- English TTS/ASR
- representative mixed Japanese/English content
- Japanese/English UI localization

Final default engines are chosen by language/task evidence, not architectural symmetry.

### D-008 — GPT-SoVITS / Style-Bert-VITS2 are not ASR

They are TTS/voice worker families. ASR uses dedicated recognition adapters.

### D-009 — ControlDeck owns cross-application GPU arbitration

SonicForge requests Resource Broker leases and does not create a competing global GPU scheduler.

### D-010 — Raw Host paths are forbidden

Host inputs/outputs use `asset:` / `grant:` identifiers and Runtime APIs.

### D-011 — Provenance and rights metadata are first-class

Every generated asset records engine/model/license/provenance. Reusable clone/reference voices record explicit rights/permission confirmation events.

### D-012 — ControlDeck TTS ownership migrates to SonicForge

Do not keep a second permanent ControlDeck TTS ML implementation after cutover. Locate the exact historical source before migration.

### D-013 — UX uses three-level progressive disclosure

```text
Easy       small task-level form
Customize  normalized outcome controls
Expert     model/runtime/native details
```

A normal task must be possible without Expert mode.

### D-014 — Contract freeze at SF1

Freeze the stable Add-on contribution IDs, four workflow executors, initial agent tools, public schemas, language contract, asset/provenance fields and setup state/profile contract before heavy engine expansion.

### D-015 — Release authorization uses Ed25519 publisher signing

Adopt the current MediaForge direction.

ControlDeck trusts the SonicForge publisher public key once. Every release publishes a canonical manifest signed by the corresponding private key.

The signed manifest binds:

```text
feature_id
version
platform
architecture
artifact_name
sha256
size_bytes
```

SHA-256 remains artifact integrity data **inside the signed manifest**, not a per-release catalog trust pin.

### D-016 — No SonicForge-specific signature verifier

If ControlDeck requires changes to consume signed SonicForge releases, those changes must implement a generic publisher-signature Release Bundle Feature contract reusable by MediaForge/future Add-ons.

### D-017 — Small top-level product navigation

Inside the Add-on use:

```text
Studio
Voices
Library
Runtime
```

Studio owns Speech/Transcribe/SFX/Music/Localization task tabs. Avoid duplicate navigation and quick-action routes that all land on the same editor.

### D-018 — Localization Studio is in scope

Bilingual game dialogue batches, voice consistency profiles, pronunciation dictionaries, JP/EN project naming/export profiles and partial retry are product features.

Localization does not automatically create another frozen Host workflow executor.

### D-019 — Automatic QA reports only checks actually performed

Deterministic audio validation is mandatory. Optional TTS->ASR round-trip may flag text mismatches, but cannot claim naturalness/emotion correctness. Unverified requirements use `not_checked`.

### D-020 — Expensive preparation belongs to durable jobs

Do not spend significant LLM/VLM/analysis/generation work only in browser state before creating durable server ownership. Navigation/backgrounding must not discard progress.

## 3. Open questions requiring measurement

### OQ-001 — Which TTS route is `Recommended` for Japanese?

Compare Qwen3-TTS and suitable Japanese specialist profiles on listening quality, latency, memory, long-form stability and style control.

### OQ-002 — Which TTS route is `Recommended` for English and bilingual character consistency?

Qwen3-TTS is the first strong candidate because upstream explicitly supports both languages, but local evidence must measure:

- English naturalness
- Japanese/English same-character consistency
- mixed language behavior
- preview/final latency

### OQ-003 — Which ASR routes are default by language/hardware?

Japanese candidates:

- Kotoba-Whisper v2.0
- ReazonSpeech K2/current suitable successor

English/mixed candidate family:

- current multilingual Whisper-family/faster-whisper/whisper.cpp route or measured successor

Measure CER/WER, real-time factor, startup, RAM/VRAM, timestamps, noisy/casual audio and streaming.

### OQ-004 — Exact AMD/ROCm support matrix

Only real tested OS/kernel/ROCm/GPU/framework/engine combinations become supported.

### OQ-005 — First recommended SFX engine

Primary candidate: Stable Audio 3 Small-SFX. Alternate only if measured benefit/gap.

### OQ-006 — First recommended music engine/profile

Primary candidate: ACE-Step 1.5 family. Need real AMD behavior, latency/VRAM, BGM usefulness, duration/loop behavior and license verification.

### OQ-007 — Streaming speech protocol details

Need real prototypes before freezing frame codec/duration/backpressure/interim result/reconnect semantics.

### OQ-008 — Worker IPC: loopback HTTP versus local socket

Internal decision; compare debug simplicity, streaming, cancellation, permissions and portability.

### OQ-009 — Exact deterministic audio-processing stack

Likely ffmpeg/ffprobe plus Python libraries, but packaging must not require unsafe root mutation.

### OQ-010 — Cache deduplication policy

Default remains SonicForge-owned cache. Optional generic content-addressed sharing only if lifecycle/deletion/permissions remain independent.

### OQ-011 — Retention/cleanup defaults

Measure previews, temp audio, rollback runtimes, model versions and logs before choosing defaults. Never silently delete user assets.

### OQ-012 — Preview implementation per engine

`Preview` is a UX concept, not necessarily the same optimization for each model. Determine whether to use smaller model, shorter duration, fewer steps or another safe route without making preview misleading.

### OQ-013 — Localization round-trip QA threshold

Need bilingual fixtures to choose normalization/scoring thresholds that flag genuine omissions/repetitions without flooding users with false warnings.

## 4. Current Host compatibility gate

### HOST-GATE-001 — Signature-aware Release Bundle verifier

Observed during the 2026-08-25 review:

- MediaForge `main` has moved release signing to Ed25519 publisher-signed canonical manifests;
- MediaForge v0.6.7 is described as its first publisher-signature release;
- the inspected ControlDeck `main` still exposes older per-artifact SHA-pin logic.

SonicForge therefore **targets the signature model and does not fall back architecturally to permanent per-release SHA pins**.

Before SF1 claims trusted fresh-install/update E2E, verify/land the generic ControlDeck signature-aware verifier.

This is a compatibility gate, not an open product-design question.

## 5. Open migration question

### OQ-MIG-001 — Exact historical ControlDeck TTS source

During SF2-0:

- search branches/PRs/commits
- identify source revision
- identify settings/data/model paths
- identify callers
- write migration inventory

Do not implement a guessed compatibility layer beforehand.

## 6. Decision change template

```text
ID:
Date:
Old decision:
New decision:
Evidence/reason:
Affected documents/schemas:
Backward compatibility impact:
Migration required:
ControlDeck/MediaForge impact:
```

Do not silently erase important architectural decision history.