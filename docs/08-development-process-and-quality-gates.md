# Development Process and Quality Gates

Status: Normative  
Date: 2026-08-25

## 1. Objective

SonicForge combines a privileged Host integration boundary, third-party ML engines, large runtime downloads, audio processing and GPU resource management. Development must therefore be incremental, contract-first and evidence-driven.

## 2. Source-of-truth order

Before changing code, read:

1. `AGENTS.md`
2. `docs/00-master-spec.md`
3. `docs/01-boundaries-and-contracts.md`
4. the relevant feature document
5. current `docs/implementation-status.md`
6. the current ControlDeck Add-on host contract files

If implementation pressure suggests breaking a design rule, update/review the design first. Do not encode a new architecture accidentally in code.

## 3. Repository boundaries

A SonicForge PR modifies SonicForge only.

A ControlDeck host change:

- is a separate ControlDeck branch/PR;
- is generic, not Sonic-specific;
- includes host-level tests and documentation;
- states why SonicForge cannot solve the requirement within the current contract.

A MediaForge change is never bundled as convenience refactoring for SonicForge.

## 4. Branch and PR convention

Recommended branch naming:

```text
sf0/<slug>
sf1/<slug>
sf2/<slug>
...
```

One PR should contain one reviewable slice with one main risk profile.

Good examples:

```text
sf0/core-health
sf0/setup-state
sf1/addon-manifest
sf2/qwen-tts-worker
sf3/kotoba-asr-worker
```

Avoid a single PR that simultaneously changes public schemas, setup, two engines and the frontend.

## 5. Commit rules

- concise functional commits
- generated model files/venvs/assets are never committed
- lock/fingerprint metadata may be committed when it is part of reproducible runtime definition
- tests accompany behavior changes
- documentation accompanies public contract changes
- do not claim runtime evidence in a commit message if it was not executed

## 6. Contract-first sequence

For a new public feature:

1. define/update capability name;
2. define JSON schema;
3. write validation/contract tests;
4. implement fake adapter path;
5. implement core orchestration;
6. implement real worker adapter;
7. integrate UI;
8. execute real E2E;
9. record evidence.

This prevents third-party engine APIs from becoming SonicForge's public API by accident.

## 7. Test pyramid

### 7.1 Unit tests

Cover:

- request validation
- routing decisions
- resource estimates
- setup state transitions
- path containment
- provenance construction
- audio metadata validation
- error normalization
- config migration

### 7.2 Schema/contract tests

Validate:

- `addon.json` against current ControlDeck host parser
- public JSON schemas Draft 2020-12 where Host requires it
- all contribution IDs and endpoints
- capability document shape
- worker protocol version compatibility
- backwards-compatible schema fixtures after contract freeze

### 7.3 Fake worker integration tests

A deterministic fake audio worker should support:

- configurable latency
- generated tiny valid WAV
- progress
- cancellation
- forced crash/failure
- resource estimate variants
- load/unload states

This lets core/job/setup/UI behavior be tested without multi-GB models.

### 7.4 Real engine tests

Each promoted engine requires a real target-hardware run.

Measure at least:

- cold worker startup
- model load time
- warm inference latency / real-time factor as relevant
- peak host RAM
- peak VRAM when GPU-backed
- output duration/format
- cancellation latency
- recovery after worker termination

### 7.5 ControlDeck integration tests

With actual ControlDeck or a contract-faithful harness, verify:

- install/enable/effective contribution
- opaque embedded view
- token introspection
- Host Job attach/update
- Resource request -> lease -> activate -> renew/release
- disable while waiting/running
- file input grant
- output staging/commit
- workflow invocation
- agent tool invocation

### 7.6 Browser E2E

Use a real browser for:

- first-use setup_required
- setup button/progress/reload persistence
- dark/light theme
- mobile companion layout
- task generation flow
- unavailable/degraded messaging
- project export
- disable/re-enable recovery

## 8. Clean-install gate

Environment/setup code is not complete until exercised from a clean SonicForge state.

At least once per release candidate:

```text
no .venv
no SonicForge runtime packs
empty SonicForge data_dir except config
empty or known-cache state
```

Run the documented setup path and record what was downloaded/built and the final capability state.

Tests on a developer machine with a preexisting working venv do not satisfy this gate.

## 9. Japanese speech quality gate

TTS/ASR changes must run the versioned Japanese benchmark fixtures described in `04-engine-model-strategy.md`.

TTS evidence should include listening-review notes for representative files; an automated waveform check cannot prove naturalness.

ASR evidence should include CER/WER or another appropriate error metric on redistributable test data when feasible, plus real-time factor.

Never select a default engine based solely on upstream benchmark claims.

## 10. Audio-generation quality gate

For SFX/music candidate promotion, use a repeatable prompt suite.

Track:

- prompt adherence review
- usable-result rate
- duration behavior
- loop suitability where requested
- clipping/invalid outputs
- generation latency
- resource footprint

Human evaluation is acceptable but record criteria and sample identifiers.

## 11. Resource safety gate

For every GPU worker:

- resource estimate implemented
- Host lease obtained before protected GPU work
- wait path tested
- cancel while waiting tested
- cancel while running tested
- lease release in success/failure/cancel paths tested
- worker crash does not leak a permanent lease beyond Host fail-safe TTL
- worker does not retain large VRAM indefinitely outside declared residency/lease policy

## 12. Setup safety gate

Provisioning tests must cover:

- idempotent second run
- network interruption
- process interruption
- insufficient disk
- missing system prerequisite
- gated license/terms
- invalid staged runtime
- rollback to prior good runtime
- cancellation

`doctor` must remain read-only.

## 13. Security gate

Before merge for code touching files/processes/network/models:

- no `shell=True`
- no unchecked user executable/path
- no path traversal/symlink escape
- no secret/token logging
- no Host cookie forwarding
- bounded uploads/responses/logs
- non-root worker default
- license metadata known or explicitly marked unverified

## 14. Static quality

Target tooling should include:

- Python formatting/linting
- type checking suitable for the codebase
- pytest
- JSON Schema validation
- frontend type/lint/build checks when frontend exists
- dependency/lock consistency checks

Exact tools may evolve; CI commands are documented in the repository rather than hidden in individual developer environments.

## 15. CI philosophy

CI should stay practical and deterministic.

### Required on ordinary PRs

- lightweight core tests
- fake worker integration
- schema/manifest validation
- setup planner tests without large downloads
- frontend tests/build when relevant
- security invariants

### Separate/optional hardware CI

Heavy model downloads and GPU tests should use dedicated runners/workflows and caching with explicit triggers because they are expensive and backend-specific.

CI success does not replace real target-machine evidence before promoting an engine to recommended.

## 16. Dependency updates

For runtime-critical dependency upgrades:

1. create a new fingerprint/lock;
2. build in staging;
3. run engine smoke/benchmark;
4. compare resource/quality regressions;
5. activate only after passing;
6. preserve rollback metadata.

Do not mutate the active venv in place during development and call it an upgrade strategy.

## 17. Database migrations

- Alembic-style explicit migrations for persistent schema changes
- migrations are additive/reversible where practical
- assets/provenance are not deleted silently
- migration tests include an old fixture DB once releases exist
- public IDs remain stable

## 18. Documentation discipline

Keep synchronized:

```text
public schema <-> docs/03-audio-capabilities-and-api.md
setup behavior <-> docs/02-runtime-environment-and-setup.md
host contract <-> docs/01-boundaries-and-contracts.md
engine promotion <-> docs/04-engine-model-strategy.md
actual state <-> docs/implementation-status.md
```

Do not edit only an implementation note to change a normative design decision.

## 19. Evidence format

For each completed roadmap slice record in `docs/implementation-status.md`:

```text
Date / commit
Environment/hardware
Commands actually executed
Observed result
Measured latency/RAM/VRAM/disk where applicable
Browser/API assertions
Known limitations
NOT TESTED items
```

Evidence must distinguish upstream claims from locally measured data.

## 20. Definition of done

A slice is done when:

- code is merged/reviewable;
- tests pass;
- public docs/schema are synchronized;
- relevant real E2E was executed;
- failure/cancel path relevant to the slice was tested;
- evidence is recorded;
- there is no known boundary violation;
- untested areas are explicitly marked.

## 21. Stop conditions

Stop and return to design rather than forcing implementation when:

- an engine requires incompatible dependencies in an existing runtime -> create a separate runtime;
- a worker needs unrestricted Host paths -> redesign around grants;
- the only solution seems to require importing ControlDeck -> boundary is wrong;
- a model license cannot be understood -> do not promote it to recommended;
- target hardware cannot run the engine reliably -> keep experimental/defer;
- public contract must break after freeze -> write migration/version plan first;
- one-click setup appears to require arbitrary root shell execution -> design a generic privileged mechanism, do not bypass Host security.

## 22. PR review checklist

- [ ] Does this remain out-of-process from ControlDeck?
- [ ] Is the public concept capability/task-oriented rather than model-oriented?
- [ ] Are SonicForge environments independent?
- [ ] Are Host files represented by grants/assets only?
- [ ] Does GPU work use the Host broker?
- [ ] Are setup changes idempotent and rollback-safe?
- [ ] Are generated assets validated and provenance recorded?
- [ ] Are license/voice-rights states preserved?
- [ ] Are unavailable states actionable in the UI?
- [ ] Were real relevant behaviors actually tested and recorded?