# SonicForge Implementation Status

Last updated: 2026-08-25

This document records **observed project state and evidence**. It is not a wish list. Anything not executed is marked `NOT TESTED`.

## 1. Current summary

| Area | State | Evidence / note |
|---|---|---|
| Specification baseline | COMPLETE | Architecture/specification documents committed to `main` on 2026-08-25 |
| ControlDeck Add-on v2 contract review | COMPLETE for design pass | Current `ControlDeck` host docs/schema and `ControlDeckMediaForge` reference inspected on 2026-08-25 |
| SonicForge code skeleton | NOT STARTED | Repository contains specification documents only at this point |
| Lightweight core service | NOT STARTED | No `/health` implementation yet |
| Dedicated core `.venv` bootstrap | NOT STARTED | Design only |
| Runtime-pack provisioning | NOT STARTED | Design only |
| One-click setup UI/API | NOT STARTED | Design only |
| Add-on manifest installed in real ControlDeck | NOT TESTED | Only draft manifest exists under `docs/contracts/` |
| Host Job integration | NOT TESTED | No SonicForge runtime code yet |
| Resource Broker integration | NOT TESTED | No SonicForge runtime code yet |
| File/project grant integration | NOT TESTED | No SonicForge runtime code yet |
| TTS engines | NOT TESTED | Candidates selected for evaluation only |
| ASR engines | NOT TESTED | Candidates selected for evaluation only |
| SFX engine | NOT TESTED | Candidate selected for evaluation only |
| Music engine | NOT TESTED | Candidate selected for evaluation only |
| ControlDeck historical TTS migration | NOT STARTED | Exact historical source commit/branch still must be located during SF2-0 |
| Browser UX | NOT TESTED | Design only |
| Target hardware compatibility | NOT TESTED | No local engine benchmark has been run as part of this repository yet |

## 2. Design evidence recorded

### 2026-08-25 — ControlDeck host contract inspection

Inspected current ControlDeck sources including:

- `docs/design-addon-platform-v2.md`
- `docs/plugin-sdk.md`
- `backend/app/addons/schema.py`
- `backend/app/applications/router.py`

Observed for design purposes:

- Add-on v2 is an out-of-process `external-service` contract.
- Current Host capability values are allowlisted.
- embedded views are intended to be Host-mediated/isolated.
- Runtime APIs provide jobs/resources/grants/output paths through scoped protocols rather than raw project paths.
- `setup_checklist` is declarative metadata and does not supply an arbitrary installation command.
- the generic Apps subsystem is the appropriate existing ControlDeck area for external-service lifecycle reasoning.

This is a source inspection, not a SonicForge E2E test.

### 2026-08-25 — MediaForge architectural precedent inspection

Inspected:

- `ControlDeckMediaForge/AGENTS.md`
- `ControlDeckMediaForge/addon.json`
- `ControlDeckMediaForge/docs/controldeck-integration-plan.md`
- `ControlDeckMediaForge/docs/implementation/mf0-0-environment.md`

Adopted principles:

- no Host imports
- separate lightweight core/heavy workers
- Resource Broker
- scoped grants
- capability-driven UX
- provenance/lineage
- real evidence requirements

SonicForge intentionally specifies its own independent environment/data/cache defaults rather than sharing MediaForge runtime state.

### 2026-08-25 — User reference repositories inspected

Inspected available content in:

- `souten-yd/GPTSoVITS`
- `souten-yd/StyleBertVITS2WithFileManager`

Important design conclusion:

- GPT-SoVITS and Style-Bert-VITS2 are TTS/voice systems, not ASR engines.
- useful engine/deployment concepts may be adapted through workers.
- broad root/file-manager assumptions from historical reference deployment are not accepted as SonicForge security architecture.

## 3. Documentation deliverables

Created on `main`:

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
- `docs/contracts/addon.example.json`
- `docs/contracts/capabilities.example.json`
- `docs/implementation-status.md`

## 4. Decisions fixed by the baseline

1. SonicForge is a real Add-on, not a ControlDeck core module.
2. SonicForge and MediaForge are sibling Add-ons.
3. SonicForge owns separate Python/runtime/model/data environments.
4. Heavy environment/model setup is button-driven after the lightweight SonicForge service is available.
5. ControlDeck is not given an arbitrary Add-on shell-execution escape hatch.
6. Public APIs are capability/task-based rather than model-based.
7. TTS is Japanese-first; Qwen3-TTS, Style-Bert-VITS2 and GPT-SoVITS are initial TTS candidates/roles.
8. ASR is a separate engine family; Kotoba-Whisper and ReazonSpeech are initial candidates.
9. game SFX/audio and music are first-class capability groups.
10. GPU work under ControlDeck uses the common Resource Broker.
11. Host files/projects use scoped grants/assets rather than raw paths.
12. voice rights, model license and generated provenance are first-class metadata.
13. old ControlDeck TTS ownership moves to SonicForge through an explicit migration/cutover plan.
14. contract freeze occurs before the end of SF1.

## 5. Next implementation slice

According to `docs/09-roadmap.md`, begin with:

**SF0-1 — Lightweight core**

Expected first implementation PR:

```text
FastAPI skeleton
configuration/data_dir
DB baseline
/health
/addon/v1/capabilities
structured logging
sf.sh serve/doctor/test
core .venv auto-bootstrap
```

Do not add torch/Qwen/Whisper/music models in the first slice.

## 6. Required evidence for the next update

When SF0-1 is implemented, record:

- clean core environment build command/output
- actual service start command
- real `/health` response
- real capability response with `setup_required`
- `doctor` before/after proof that it did not modify state
- test command/result
- process stop/restart behavior
- any NOT TESTED platform behavior

Do not replace these items with expected output.