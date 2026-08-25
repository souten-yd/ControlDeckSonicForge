# SonicForge Implementation Status

Last updated: 2026-08-25

This document records **observed project state and evidence**. It is not a wish list. Anything not executed is marked `NOT TESTED`.

## 1. Current summary

| Area | State | Evidence / note |
|---|---|---|
| Specification baseline | COMPLETE | Architecture/specification baseline and critical refinement committed to `main` on 2026-08-25 |
| Japanese + English product contract | COMPLETE for design | UI/content language model, bilingual TTS/ASR direction and Localization Studio documented |
| Easy / Customize / Expert UX | COMPLETE for design | Default controls simplified; engine/model selection moved to Expert |
| Speech Essentials setup model | COMPLETE for design | Speech is default pack; Game Audio/Music optional contextual packs |
| Publisher-signed release design | COMPLETE for SonicForge design | MediaForge Ed25519 manifest pattern inspected/adopted |
| ControlDeck signature-aware release verifier | HOST COMPATIBILITY GATE | Inspected ControlDeck `main` still showed older SHA-pin verifier behavior; generic signature-aware Host E2E not yet available/verified |
| SonicForge code skeleton | NOT STARTED | Repository remains specification-only at this point |
| Lightweight core service | NOT STARTED | No `/health` implementation yet |
| Signed release build/sign tooling | NOT STARTED | Contract/design only; no SonicForge signer/bundle code yet |
| Dedicated core `.venv` bootstrap | NOT STARTED | Design only |
| Speech Essentials provisioning | NOT STARTED | Design only |
| Game Audio/Music optional provisioning | NOT STARTED | Design only |
| Add-on manifest installed in real ControlDeck | NOT TESTED | Draft manifest only under `docs/contracts/` |
| Host Job integration | NOT TESTED | No SonicForge runtime code yet |
| Resource Broker integration | NOT TESTED | No SonicForge runtime code yet |
| File/project grant integration | NOT TESTED | No SonicForge runtime code yet |
| Japanese TTS | NOT TESTED | Candidate engines only |
| English TTS | NOT TESTED | Qwen3-TTS is a strong upstream-supported candidate; no local measurement yet |
| Japanese ASR | NOT TESTED | Kotoba/Reazon candidates only |
| English/mixed ASR | NOT TESTED | Multilingual Whisper-family route is candidate direction only |
| Localization Studio | NOT STARTED | Product/API/state design only |
| TTS->ASR QA | NOT STARTED | Heuristic design only; thresholds not selected |
| SFX engine | NOT TESTED | Candidate selected for evaluation only |
| Music engine | NOT TESTED | Candidate selected for evaluation only |
| ControlDeck historical TTS migration | NOT STARTED | Exact historical source commit/branch must be located during SF2-0 |
| Browser UX/reconnect | NOT TESTED | Design includes reconnection/reattach requirements; no implementation yet |
| Target hardware compatibility | NOT TESTED | No SonicForge engine benchmark has been run yet |

## 2. Design evidence recorded

### 2026-08-25 — ControlDeck Add-on v2 contract inspection

Inspected current Host sources including:

- `docs/design-addon-platform-v2.md`
- `docs/plugin-sdk.md`
- `backend/app/addons/schema.py`
- `backend/app/applications/router.py`
- `backend/app/features/release_bundle.py`
- trusted feature catalog/release behavior

Observed for design purposes:

- Add-on v2 is an out-of-process `external-service` contract.
- Host capabilities are allowlisted.
- embedded views are Host-mediated/isolated.
- Runtime APIs provide Jobs/resources/grants/outputs rather than raw project paths.
- `setup_checklist` is declarative and does not authorize arbitrary Add-on shell execution.
- generic feature installation is distinct from Add-on runtime authority.
- the inspected `main` release-bundle verifier still contained older per-artifact SHA-pin trust behavior.

This is source inspection, not SonicForge E2E.

### 2026-08-25 — MediaForge architecture and release-signing inspection

Inspected current MediaForge architecture plus recent release tooling/behavior, including:

- `AGENTS.md`
- `addon.json`
- ControlDeck integration/environment docs
- `scripts/sign_release.py`
- recent release history around v0.6.7

Adopted principles/lessons:

- no Host imports; isolated core/heavy workers;
- Resource Broker + scoped grants;
- durable server-owned jobs;
- capability-driven UI and measured promotion;
- Ed25519 publisher signature over canonical manifest;
- SHA-256 retained inside the signed manifest for artifact integrity;
- publisher public key trusted once rather than editing ControlDeck per release;
- distinguish catalog/listed versus installed versus available/running state;
- queued work that has not started can cancel immediately;
- dead WebSocket/background return must reconnect and reload authoritative state;
- expensive preparation should live inside durable server jobs rather than browser memory.

SonicForge intentionally owns independent runtimes/data/cache rather than sharing MediaForge state.

### 2026-08-25 — Qwen3-TTS bilingual capability inspection

Current official Qwen3-TTS documentation was inspected for design purposes and explicitly lists Japanese and English among supported major languages, with 0.6B/1.7B families plus CustomVoice/Base/VoiceDesign/streaming capabilities.

This supports Qwen3-TTS as the first bilingual TTS evaluation candidate, but **does not constitute SonicForge quality/performance evidence**.

### 2026-08-25 — User reference repositories inspected

Inspected available content in:

- `souten-yd/GPTSoVITS`
- `souten-yd/StyleBertVITS2WithFileManager`

Design conclusions:

- GPT-SoVITS and Style-Bert-VITS2 are TTS/voice systems, not ASR engines.
- useful engine/deployment concepts may be adapted through workers.
- broad root/file-manager assumptions from historical reference deployments are not accepted as SonicForge security architecture.

## 3. Critical design changes adopted

The initial baseline was reviewed critically and changed where the cost/UX benefit justified it.

### Adopted

1. **Japanese + English first-class speech support** rather than Japanese-only product behavior.
2. **UI locale / content language / voice language are separate**.
3. **Easy / Customize / Expert** instead of one large settings surface or a weak Simple/Advanced split.
4. **Speech Essentials** becomes default setup; Game Audio and Music are optional packs.
5. In-app navigation reduced to **Studio / Voices / Library / Runtime** with task tabs.
6. **Localization Studio** added for JP/EN dialogue batches.
7. **Preview + bounded candidate comparison** added for subjective generation.
8. **Pronunciation/terminology dictionaries** and voice consistency profiles added.
9. **Automatic deterministic QA** plus optional TTS->ASR mismatch flagging added.
10. **Publisher-signed release model** adopted from current MediaForge direction.
11. Optional missing Game Audio/Music **does not degrade an otherwise healthy Speech Essentials service**.
12. Stable Host workflow executors remain only four; richer language/localization details stay in runtime capability/application contracts.

### Rejected/modified

- rejected installing all TTS/ASR/SFX/Music by default;
- rejected always-visible engine/model pickers;
- rejected `speech.asr.ja_en`-style combinatorial capabilities;
- rejected dozens of engine-native parameters in stable top-level schemas;
- rejected permanent per-release ControlDeck SHA pin churn for SonicForge;
- rejected another localization-specific frozen Host executor before real external workflow demand exists;
- rejected reporting semantic requirements as passed when no validator actually checked them.

## 4. Documentation deliverables

Current `main` includes:

- `README.md`
- `AGENTS.md`
- `docs/00-master-spec.md`
- `docs/01-boundaries-and-contracts.md`
- `docs/02-runtime-environment-and-setup.md`
- `docs/03-audio-capabilities-and-api.md`
- `docs/04-engine-model-strategy.md`
- `docs/05-ux-and-workflows.md`
- `docs/06-security-license-and-provenance.md`
- `docs/07-controldeck-tts-migration.md`
- `docs/08-development-process-and-quality-gates.md`
- `docs/09-roadmap.md`
- `docs/10-reference-repositories.md`
- `docs/11-decisions-and-open-questions.md`
- `docs/12-architecture-diagrams.md`
- `docs/13-release-distribution-and-signing.md`
- `docs/14-bilingual-ux-and-critical-review.md`
- `docs/contracts/addon.example.json`
- `docs/contracts/capabilities.example.json`
- `docs/implementation-status.md`

## 5. Fixed baseline decisions

1. SonicForge is a real out-of-process Add-on, not ControlDeck core.
2. MediaForge/SonicForge are sibling Add-ons with no shared venv/DB/private modules.
3. SonicForge owns core/runtime/model/data environments.
4. Lightweight feature distribution targets Ed25519 publisher-signed generic ControlDeck Release Bundles.
5. SHA-256 remains inside the signed manifest for integrity, not per-release publisher authorization.
6. Runtime Add-on privilege remains separately controlled by Host capability allowlists.
7. Default first ML setup is Speech Essentials for Japanese + English TTS/ASR.
8. Game Audio and Music are optional contextual packs.
9. Public APIs are capability/task/language based; model names are Expert/routing details.
10. ControlDeck Resource Broker owns cross-application GPU admission.
11. Host files/projects use scoped grants/assets only.
12. rights/license/provenance/QA evidence are first-class metadata.
13. historical ControlDeck TTS ownership migrates to SonicForge after source inventory.
14. contract freeze occurs during SF1 after Host-signature compatibility is resolved/verified.

## 6. Next implementation order

According to `docs/09-roadmap.md`:

### Next: SF0-1 — Lightweight core

```text
FastAPI skeleton
configuration/data_dir
DB baseline
/health
/addon/v1/capabilities
ja/en localization resources
structured logging
sf.sh serve/doctor/test
core environment bootstrap
```

Do not add torch/Qwen/Whisper/music models in this first slice.

### Then: SF0-2..SF0-5

- fake worker/durable asset/job state;
- Speech Essentials setup planner;
- signed lightweight release build/sign tooling with disposable-key tests.

### Before SF1 trusted fresh-install claim

Resolve/verify `HOST-GATE-001`: generic ControlDeck publisher-signature Release Bundle verification.

## 7. Required evidence for future updates

When implementation begins, record actual commands/actions and observations, including applicable:

- clean core environment build;
- actual service `/health` and capability responses;
- `doctor` read-only proof;
- disposable-key release signature/tamper tests;
- real signed Host install/update/rollback once Host support exists;
- Japanese/English/mixed speech fixtures;
- measured latency/RAM/VRAM/disk/download;
- Resource Broker lifecycle;
- queued/running cancellation;
- browser locale/reconnect/reattach behavior;
- scoped project export;
- Localization Studio batch behavior;
- every `NOT TESTED` area.

Do not replace runtime evidence with expected output or upstream claims.