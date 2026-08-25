# Decisions and Open Questions

Status: Living design ledger  
Last updated: 2026-08-25

## 1. Purpose

This document separates **decisions already fixed** from **questions that still require measurement or a generic Host decision**.

Do not reopen fixed decisions casually during implementation. If new evidence requires a change, record the reason, impact and migration plan here before changing normative contracts.

## 2. Fixed decisions

### D-001 — SonicForge is an out-of-process ControlDeck Add-on

Decision:

- Add-on Contract v2 external service
- no SonicForge Python/JavaScript imported into ControlDeck

Reason:

- dependency isolation
- crash isolation
- independent releases
- security/audit boundary
- same architectural pattern as MediaForge

### D-002 — SonicForge and MediaForge are siblings

Decision:

- no parent/child runtime relationship
- no shared internal modules, database or venv
- cross-media composition goes through ControlDeck workflow/agent/grant contracts

### D-003 — SonicForge owns its environment

Decision:

- separate core `.venv`
- separate heavy runtime packs
- separate model/data/state paths
- separate default cache
- explicit user-defined external model libraries remain possible

Reason:

The user requires SonicForge to remain independently installable/repairable and not contaminate the ControlDeck/MediaForge dependency graph.

### D-004 — One-click heavy setup is mandatory

Decision:

After the lightweight SonicForge service is available, first-use setup is driven by a button and a durable setup job.

The normal user does not manually create venvs or run pip commands.

### D-005 — Add-on manifest does not execute arbitrary shell

Decision:

Do not add a Sonic-specific shell command field to the ControlDeck Add-on contract.

The existing generic Apps/external-service layer is used for lightweight service lifecycle. A future truly zero-service bootstrap requires a generic reviewed Host mechanism.

### D-006 — Capability-first public API

Decision:

Stable callers use task/capability IDs. Engine/model IDs are optional advanced routing hints.

Reason:

- engines will change faster than user workflows
- workflows/agents should survive model replacement
- UI can hide unavailable engine-specific controls

### D-007 — Japanese-first speech

Decision:

Japanese synthesis/recognition quality is the first speech optimization target.

Initial TTS roles:

- Qwen3-TTS: general/clone/design candidate
- Style-Bert-VITS2: Japanese character/style candidate
- GPT-SoVITS: reference/few-shot/custom voice candidate

Initial ASR candidates:

- Kotoba-Whisper v2.0
- ReazonSpeech K2/current suitable successor

Final defaults require local benchmark evidence.

### D-008 — GPT-SoVITS / Style-Bert-VITS2 are not ASR

Decision:

They are integrated under TTS/voice worker packs. ASR uses dedicated recognition adapters.

### D-009 — ControlDeck owns cross-application GPU arbitration

Decision:

SonicForge requests Host Resource Broker leases for GPU work and does not build a competing global GPU scheduler.

SonicForge may still manage its own worker/model residency inside an active/authorized resource policy.

### D-010 — Raw Host paths are forbidden

Decision:

Host inputs/outputs use `asset:` / `grant:` identifiers and Runtime APIs.

### D-011 — Provenance and rights metadata are first-class

Decision:

Every generated asset records engine/model/license/provenance. Reusable clone/reference voices record an explicit user rights/permission confirmation event.

### D-012 — ControlDeck TTS ownership migrates to SonicForge

Decision:

Do not maintain a second permanent TTS implementation inside ControlDeck after migration.

The exact historical source must be identified before code migration.

### D-013 — Simple UX uses progressive disclosure

Decision:

Default screens expose tasks/presets and recommended settings. Engine/model/runtime internals are Advanced/Diagnostics concepts.

### D-014 — Contract freeze at SF1

Decision:

Freeze contribution IDs, capability namespace, public schemas, tool/executor IDs, asset/provenance required fields and setup state model before heavy engine expansion.

After freeze, additions are preferred over breaking changes.

## 3. Open questions requiring measurement

### OQ-001 — Which TTS engine is the default `balanced` Japanese route?

Candidates:

- Qwen3-TTS family
- Style-Bert-VITS2 for some character profiles

Required evidence:

- Japanese listening suite
- cold/warm latency
- VRAM/RAM
- long-form stability
- style control usefulness
- target hardware reliability

Until measured: no permanent default model mapping in public contract.

### OQ-002 — Which ASR engine is default on CPU versus GPU?

Candidates:

- Kotoba-Whisper v2.0
- ReazonSpeech K2/current suitable model

Measure:

- CER
- real-time factor
- startup latency
- RAM/VRAM
- timestamps
- noise/casual Japanese
- streaming suitability

### OQ-003 — Exact AMD/ROCm support matrix

Upstream projects may claim AMD support, but SonicForge must record actual supported versions/devices after testing.

Need:

- OS/kernel
- ROCm version
- GPU architecture
- torch/backend version
- engine-specific failures/workarounds

### OQ-004 — First recommended SFX engine

Primary candidate:

- Stable Audio 3 Small-SFX

Alternative:

- TangoFlux or a newer engine if it materially outperforms/fills gaps

Need local prompt-adherence, latency, hardware and model-license evaluation.

### OQ-005 — First recommended music profile/model

Primary candidate:

- ACE-Step 1.5 family

Need:

- AMD target test
- generation latency/VRAM
- duration fidelity
- BGM usefulness
- loop behavior
- model/release license verification

### OQ-006 — Streaming speech protocol details

Need to decide after first real engines:

- exact PCM/Opus formats
- frame duration
- backpressure window
- interim ASR result semantics
- TTS first-audio latency target
- reconnect semantics

Do not freeze a streaming wire protocol before an engine prototype proves the requirements.

### OQ-007 — Dedicated worker IPC: loopback HTTP versus local socket

Both can preserve process isolation.

Evaluate:

- simplicity/debuggability
- streaming support
- cancellation
- security/permissions
- Windows/Linux portability if Windows support becomes relevant

This is internal and need not affect public Add-on API.

### OQ-008 — Exact audio processing dependency stack

Candidates include ffmpeg/ffprobe plus Python libraries.

Need to decide packaging/install strategy without introducing root/system mutations during ordinary SonicForge setup.

### OQ-009 — Cache deduplication policy

Current baseline: SonicForge owns its default cache to preserve independence.

A future optional shared content-addressed cache may be considered only if:

- lifecycle remains independent
- deletion cannot corrupt another Add-on
- ownership/permissions are clear
- it is generic rather than a MediaForge shortcut

### OQ-010 — Retention/cleanup defaults

Need measured storage behavior before choosing defaults for:

- generated previews
- temp audio
- old runtime rollback copies
- model versions
- job logs

Never silently delete user assets.

## 4. Open Host-level question

### OQ-HOST-001 — Truly zero-touch installation of an absent SonicForge service

Current safe baseline:

1. generic ControlDeck Apps/service mechanism registers/starts lightweight SonicForge;
2. SonicForge then owns one-click heavy environment/model provisioning.

If the desired final product is "a fresh ControlDeck with no SonicForge files can install SonicForge from one Extensions button", the Host needs a generic package/bootstrap mechanism with properties such as:

- explicit trusted source/package identity
- version/signature/hash
- fixed install scope
- no arbitrary browser-supplied shell
- progress/log/cancel
- least privilege
- rollback/uninstall semantics
- reusable by any future Add-on

This is a ControlDeck platform design item, not something SonicForge should bypass.

## 5. Open migration question

### OQ-MIG-001 — Exact historical ControlDeck TTS source

Current ControlDeck `main` inspection does not show an obvious active TTS implementation.

During SF2-0:

- search branches/PRs/commits
- identify source revision
- identify settings/data/model paths
- identify callers
- write migration inventory

Do not implement a guessed compatibility layer beforehand.

## 6. Decision change template

When changing a fixed decision, append a record:

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

Never silently edit away the history of an important architectural decision.