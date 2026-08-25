# AGENTS.md — SonicForge development contract

This file is normative for human developers and coding agents working in this repository.

## 1. Read order and precedence

Before implementation, read:

1. `AGENTS.md`
2. `docs/00-master-spec.md`
3. `docs/01-boundaries-and-contracts.md`
4. `docs/13-release-distribution-and-signing.md` for packaging/release work
5. `docs/14-bilingual-ux-and-critical-review.md` for product/UI work
6. the relevant domain document
7. `docs/08-development-process-and-quality-gates.md`
8. `docs/09-roadmap.md`
9. `docs/implementation-status.md`

For ControlDeck integration read current Host sources, especially:

- `ControlDeck/docs/design-addon-platform-v2.md`
- `ControlDeck/docs/plugin-sdk.md`
- `ControlDeck/backend/app/addons/schema.py`
- `ControlDeck/backend/app/features/release_bundle.py`
- `ControlDeck/tools/fake-addon/`

For architectural/release precedent read current MediaForge sources, especially:

- `ControlDeckMediaForge/AGENTS.md`
- `ControlDeckMediaForge/docs/controldeck-integration-plan.md`
- `ControlDeckMediaForge/scripts/sign_release.py`

Precedence for Host-facing behavior:

1. current generic ControlDeck contract actually available on the target Host;
2. this `AGENTS.md` and SonicForge normative design;
3. feature specifications;
4. roadmap/implementation notes.

When a desired SonicForge contract is ahead of current ControlDeck support (for example publisher-signature Release Bundles), treat it as an explicit Host compatibility gate. Do not silently fall back to a weaker permanent architecture.

## 2. Hard boundaries

1. Never import ControlDeck backend/frontend internals into SonicForge.
2. Never import MediaForge internals into SonicForge.
3. Never put SonicForge-specific routes, models, dependencies, UI strings or business logic into ControlDeck core.
4. Runtime Host integration is HTTP + Add-on v2 + scoped Browser Bridge/Runtime APIs.
5. Release installation uses the generic trusted Feature mechanism, not an Add-on-supplied arbitrary shell command.
6. Never share a Python venv/database/runtime registry with ControlDeck or MediaForge.
7. SonicForge owns its core env, runtime packs, state DB, models, voices, assets and work dirs.
8. Cross-boundary files use Host `asset:` / `grant:` identifiers; never raw Host project paths.
9. Public APIs route by capability/task/language. Model/engine IDs are optional Expert hints only.
10. GPU work under ControlDeck acquires/renews/releases Host Resource Broker leases.
11. Optional Game Audio/Music absence must not degrade a healthy Speech Essentials service.
12. Significant preparation/generation is server-owned durable work before expensive compute is spent; browser state is not the sole owner.

## 3. Release trust rules

SonicForge follows the MediaForge publisher-signature model.

- release authorization uses a trusted Ed25519 publisher public key;
- sign a canonical manifest that binds feature id, version, platform, architecture, artifact name, SHA-256 and size;
- SHA-256 remains integrity data inside the signed manifest, not a per-release ControlDeck source pin;
- publisher private key never enters the repository, runtime bundle or ordinary CI/test jobs;
- use disposable test keys for verification tests;
- a valid signature never bypasses Host capability allowlists, downgrade checks, safe extraction, package identity, provisioning or health checks;
- third-party runtime/model downloads have their own revision/digest/license trust records.

If the current ControlDeck target lacks the generic signature-aware verifier, record the blocker and implement the Host support as a separate generic ControlDeck PR. Do not add SonicForge-specific verifier logic.

## 4. Environment/setup rules

Normal layout:

```text
.venv/                         lightweight core/development env
runtimes/<runtime-id>/.venv/  heavy/incompatible ML stacks
worker_packs/<pack>/           engine adapters/workers
data_dir/                      persistent state outside source
```

Rules:

- core stays light and starts without torch/models;
- runtime sharing is allowed only inside SonicForge when fingerprint compatibility is proven;
- `doctor` is read-only;
- provisioning is idempotent/resumable and builds into staging before atomic activation;
- default first setup is `speech-essentials` (Japanese + English TTS/ASR);
- Game Audio and Music are optional contextual one-click packs;
- do not silently invoke sudo, modify drivers/kernel, or accept third-party terms;
- failed setup leaves the last known-good runtime usable;
- UI and CLI use the same setup orchestration logic.

## 5. Security rules

- `shell=True` forbidden.
- subprocess argv is fixed/validated.
- no prompt/user input concatenated into shell, SQL or filesystem paths.
- no secrets/signing key material in source, manifests, URLs, logs or job results.
- no ControlDeck session Cookie/Authorization forwarding.
- service credentials are short-lived and audience/Add-on scoped.
- realpath containment for local files; reject symlink escape.
- treat uploaded audio, archives and model files as untrusted.
- generated assets require provenance/model/license metadata.
- reusable voice clone/import requires explicit rights/consent metadata.
- QA reports only checks actually performed; use `not_checked` rather than implying success.

## 6. Audio/language architecture

Primary capability groups:

```text
speech.tts.*
speech.asr.*
speech.localization.*
speech.qa.*
audio.sfx.*
audio.processing.*
audio.qa.*
music.*
asset.pack.*
```

Japanese and English are first-class product languages. `ui_locale`, `content_language`, and voice language metadata are separate concepts.

GPT-SoVITS and Style-Bert-VITS2 are TTS/voice engines, not ASR engines.

Do not force the same ASR model for Japanese and English. Route by measured language/task quality.

Do not create combinatorial language capabilities such as `speech.asr.ja_en`; language support belongs in capability metadata/request fields.

## 7. UI rules

Use the current baseline:

```text
Top level: Studio / Voices / Library / Runtime
Studio: Speech / Transcribe / SFX / Music / Localization
Settings: Easy / Customize / Expert
```

Rules:

- ordinary tasks work entirely in Easy/Customize;
- no always-visible model picker;
- show a control only when relevant and supported;
- recommended quality is the default; model choice is routing policy;
- Preview and bounded candidate comparison where useful;
- Japanese and English UI strings from localization keys;
- embedded view follows opaque Host isolation; no shared cookie/localStorage assumptions;
- reconnect dead sockets on visibility return and reload authoritative server state;
- running job progress survives navigation/backgrounding;
- queued cancel settles immediately when no work has started; running cancel is owned by the active worker/job;
- distinguish listed / installed / available / loaded / running / recommended / experimental;
- mobile must remain usable without labels collapsing/wrapping into unusable layouts;
- do not build a node graph as primary UX.

## 8. Public contract freeze

Before the end of SF1 freeze:

- `addon.json` contribution IDs
- four initial workflow executor IDs
- five initial agent tool IDs
- `auto|ja|en` content language contract
- public JSON schemas/error codes
- capability naming principles
- asset/provenance required fields
- setup state/profile names

Do not freeze every detailed capability as a separate Host executor. After freeze, prefer additive extensions.

## 9. Development process

- one PR = one independently reviewable slice;
- tests accompany behavior;
- ControlDeck Host changes are separate PRs and generic;
- MediaForge is reference, not a code dependency;
- real engine promotion requires measured target-hardware evidence;
- UI changes require real browser checks in Japanese and English when applicable;
- update `docs/implementation-status.md` with what was actually executed and what remains `NOT TESTED`.
- validate locally first and batch CI at meaningful milestones rather than running CI after every small change.
- do not merge SonicForge or dependent ControlDeck PRs before local functional acceptance on the target machine.

## 10. Definition of done

Build/lint/unit tests are necessary but insufficient.

Relevant real evidence includes:

- signed release build/self-verification and negative tamper cases for release work;
- clean Speech Essentials provisioning;
- real service health/capability responses;
- real Japanese/English TTS/ASR fixtures for speech work;
- Resource Broker lease lifecycle for GPU work;
- queued/running cancellation;
- browser reconnect/reattach for UX work;
- generated asset validation/provenance;
- scoped project export;
- no falsely claimed checks or support.

Record untested areas explicitly.

## 11. Codex short acceptance commands

The detailed local-machine procedure is normative in:

`docs/CODEX_LOCAL_ACCEPTANCE.md`

Recognize these short user commands even in a fresh Codex session:

### `SF受入確認`

Read `docs/CODEX_LOCAL_ACCEPTANCE.md` and execute the local acceptance procedure through the final PASS / FAIL / NOT TESTED report.

**Do not merge any PR.**

### `SF受入マージ`

Read `docs/CODEX_LOCAL_ACCEPTANCE.md`, execute a fresh local acceptance against the exact PR heads, and merge only if the runbook ends with `merge recommendation: YES`.

Rules:

- local functional validation precedes merge;
- do not reuse stale acceptance after relevant code changes;
- run the intentionally batched milestone CI only after local acceptance is green;
- do not bypass required checks;
- do not force merge;
- generic ControlDeck dependency PRs merge before the dependent SonicForge PR;
- after a dependency merge/rebase, re-run the affected SonicForge smoke tests before SonicForge merge;
- after merge, run a short smoke test from `main` and record actual merge/evidence in `docs/implementation-status.md`.

If any required acceptance item fails, stop the merge sequence and fix the failure on a branch first.
