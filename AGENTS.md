# AGENTS.md — SonicForge development contract

This file is normative for human developers and coding agents working in this repository.

## 1. Read order and document precedence

Before implementation, read:

1. `AGENTS.md`
2. `docs/00-master-spec.md`
3. `docs/01-boundaries-and-contracts.md`
4. the domain document for the feature being changed
5. `docs/08-development-process-and-quality-gates.md`
6. `docs/09-roadmap.md`

For ControlDeck integration, also read the current host sources:

- `ControlDeck/docs/design-addon-platform-v2.md`
- `ControlDeck/docs/plugin-sdk.md`
- `ControlDeck/backend/app/addons/schema.py`
- `ControlDeck/tools/fake-addon/`

For architectural precedent, read:

- `ControlDeckMediaForge/AGENTS.md`
- `ControlDeckMediaForge/docs/controldeck-integration-plan.md`

Precedence when documents conflict:

1. current ControlDeck host contract for host-facing behavior
2. this `AGENTS.md`
3. SonicForge master/boundary specifications
4. feature specifications
5. roadmap/implementation instructions

Do not silently reinterpret a contract. Update the design first.

## 2. Hard boundaries

1. Never import ControlDeck backend/frontend internals into SonicForge.
2. Never import MediaForge internals into SonicForge.
3. Never put SonicForge-specific routes, model names, dependencies, UI strings or business logic into ControlDeck core.
4. Host integration is HTTP + Add-on Contract v2 + scoped Browser Bridge/Runtime APIs only.
5. Never share a Python virtual environment with ControlDeck or MediaForge.
6. SonicForge owns its core environment, runtime packs, state DB, models, assets and work directories.
7. Cross-Add-on file exchange uses host-issued `asset:` / `grant:` identifiers; never raw host paths.
8. Public high-level APIs route by capability. Model/engine IDs are optional advanced routing hints, never required business concepts.
9. GPU inference under ControlDeck must acquire/renew/release a Host Resource Broker lease. Do not build a competing global GPU scheduler.
10. A missing worker must degrade only its capabilities. The lightweight SonicForge core should remain healthy whenever possible.

## 3. Environment rules

The default structure is:

```text
.venv/                         lightweight SonicForge core
runtimes/<runtime-id>/.venv/  heavy or incompatible ML stacks
worker_packs/<pack>/           engine adapters/workers
data_dir/                      runtime state outside the repository
```

The core environment must not contain heavy inference stacks merely for convenience.

Runtime sharing is allowed only inside SonicForge when lock/fingerprint compatibility is proven. It is forbidden across ControlDeck/MediaForge boundaries.

The default SonicForge cache is independent. Respect explicit `PIP_CACHE_DIR`, `UV_CACHE_DIR`, `HF_HOME` and model library settings; do not overwrite user choices.

## 4. Setup/provisioning rules

The normal user path is a button-driven setup flow.

- `doctor` is read-only.
- setup is idempotent and resumable.
- build into staging, validate, then atomically activate.
- persist setup progress server-side; do not rely on browser localStorage.
- show planned downloads, disk requirements and license/terms before gated downloads.
- never silently accept a third-party model license for the user.
- never silently invoke `sudo` or modify ROCm/kernel/system drivers.
- missing system prerequisites must become an actionable setup state.
- failed setup must leave the last known-good runtime usable.

## 5. Security rules

- `shell=True` is forbidden.
- subprocess arguments are arrays and validated.
- no prompt/user text concatenation into shell, SQL, paths or command lines.
- no secrets in source, manifest, URLs, job results or logs.
- no ControlDeck session Cookie/Authorization forwarding.
- service tokens are short-lived and audience/add-on scoped.
- normalize real paths and enforce containment for every local file operation.
- external audio/reference uploads are treated as untrusted input.
- generated assets must include provenance and engine/model/license metadata sufficient for later audit.
- voice clone/import requires explicit rights/consent metadata in the library workflow.

## 6. Audio architecture rules

Use stable adapter interfaces. The core must not depend on a specific engine implementation.

Primary capability groups:

```text
speech.tts.*
speech.asr.*
audio.sfx.*
audio.processing.*
music.*
asset.pack.*
```

TTS engines such as Qwen3-TTS, GPT-SoVITS and Style-Bert-VITS2 are TTS/voice engines. They are not ASR engines.

ASR should be Japanese-first and adapter-based. Initial preferred candidates are documented in `docs/04-engine-model-strategy.md`.

## 7. UI rules

- simple mode is the default; advanced settings use progressive disclosure.
- unavailable capabilities are explained rather than silently hidden when the Add-on is enabled.
- setup/waiting/loading states always include a short reason and an actionable next step where possible.
- opaque embedded view rules from ControlDeck apply: no reliance on shared-origin cookies/localStorage.
- theme/locale/safe-area changes are handled through the host bridge.
- mobile may use a companion layout instead of squeezing a desktop DAW-like workspace into 320 px.
- do not build a node graph as the primary UX. Presets/tasks/conversation-style generation come first.

## 8. Public contract freeze

Before the end of roadmap phase SF1, freeze:

- `addon.json` contribution IDs
- public JSON schemas
- agent tool IDs
- workflow executor IDs
- capability names
- asset/provenance required fields
- setup state model

After freeze, changes are additive by default. Breaking changes require an explicit migration document and version bump.

## 9. Development process

- one PR = one independently reviewable slice
- tests are added with the change
- do not edit ControlDeck and SonicForge in the same PR/repository
- if a Host change is truly required, first write one sentence explaining why it cannot be solved within the current generic contract
- Host changes must be generic enough for another future Add-on to use
- update `docs/09-roadmap.md` or implementation status evidence when a phase materially changes

## 10. Definition of done

Build/lint/unit tests are necessary but insufficient.

A feature is complete only when there is evidence of the real behavior relevant to that feature, for example:

- clean environment provisioning executed
- real service health request
- real TTS/ASR/audio generation with measured latency/memory where applicable
- Resource Broker lease lifecycle observed for GPU work
- cancellation observed
- real browser embedded-view assertion for UX work
- produced asset inspected and provenance verified

Record what was NOT TESTED. Never turn assumptions into evidence.