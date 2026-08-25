# Development Process and Quality Gates

Status: Normative  
Date: 2026-08-25

## 1. Objective

SonicForge combines signed feature distribution, privileged Host integration, third-party ML engines, large runtime/model downloads, bilingual speech, audio processing and GPU scheduling. Development must be incremental, contract-first and evidence-driven.

## 2. Source-of-truth order

Before changing code read:

1. `AGENTS.md`
2. `docs/00-master-spec.md`
3. `docs/01-boundaries-and-contracts.md`
4. relevant domain document
5. `docs/13-release-distribution-and-signing.md` for release work
6. `docs/14-bilingual-ux-and-critical-review.md` for UI/product work
7. `docs/implementation-status.md`
8. current generic ControlDeck host/release-bundle contract

Do not let an engine's API, a temporary Host limitation or a convenient shell command silently redefine the architecture.

## 3. Repository boundaries

A SonicForge PR modifies SonicForge only.

A ControlDeck change:

- separate branch/PR;
- generic, not Sonic-specific;
- documented version/threat/backward-compatibility behavior;
- Host tests/evidence;
- explicit explanation why the current generic contract cannot satisfy the requirement.

A MediaForge change is never bundled as convenience refactoring for SonicForge.

## 4. PR/commit discipline

Recommended branches:

```text
sf0/core-health
sf0/release-signing
sf0/setup-state
sf1/bilingual-studio
sf2/qwen-tts
sf3/asr-routing
```

One PR = one reviewable slice/risk profile.

- no generated models/venvs/assets in Git;
- lock/fingerprint/release metadata may be committed where required for reproducibility;
- tests accompany behavior;
- docs accompany public contract/decision changes;
- commit/PR text does not claim evidence that was not executed.

## 5. Contract-first feature sequence

For public behavior:

1. define capability/task/language semantics;
2. define/update JSON schema;
3. write validation/backward-compat tests;
4. fake adapter/worker path;
5. durable core orchestration;
6. real worker adapter;
7. Easy/Customize/Expert UI exposure;
8. real E2E/failure/cancel/reconnect tests;
9. record evidence.

Do not surface engine-native fields as required stable API just because they exist upstream.

## 6. Release signing gate

Before any release can be called trusted-installable:

### Build/sign

- bundle identity/version consistent across release tag, feature manifest, Add-on manifest and package version;
- canonical release manifest generated;
- Ed25519 publisher signature generated only in authorized release context;
- private key absent from repository/runtime/ordinary CI artifacts/logs;
- self-verification succeeds;
- artifact SHA-256 and size in the signed manifest match published bytes.

### Verifier negative cases

Test at least:

```text
valid signature succeeds
manifest one-byte tamper fails
artifact one-byte tamper fails
wrong feature id fails
wrong version fails
wrong platform/architecture fails
wrong artifact name/size fails
wrong publisher key fails
malformed signature fails
valid old release downgrade fails when Host policy forbids it
validly signed capability escalation still fails
provision/health failure preserves previous current version
```

Use disposable test keys, never the publisher private key.

### Host compatibility

Before SF1 fresh-install E2E, verify the target ControlDeck uses the generic publisher-signature Release Bundle Feature verifier. If not, record `HOST-GATE-001` and land generic Host support separately. Do not permanently revert SonicForge to per-release SHA catalog pins.

## 7. Unit/schema/fake integration gates

### Unit

Cover:

- request/language validation
- routing by language/task/profile
- setup state/profile reconciliation
- resource estimates
- path containment
- provenance/lineage
- QA state honesty (`not_checked`)
- audio metadata/output validation
- locale/error normalization
- config/database migrations

### Contract/schema

Validate:

- `addon.json` with current Host parser;
- contribution IDs/permissions/endpoints;
- public JSON Schema as required by Host;
- `auto|ja|en` language contract;
- capability document shape;
- setup checklist `core/speech-essentials/game-audio/music`;
- four workflow executors/five initial agent tools;
- frozen-contract old fixtures after SF1.

### Fake worker

Deterministic fake worker supports:

- Japanese/English/mixed metadata;
- tiny valid WAV;
- configurable latency/progress;
- queued and running cancel;
- failure/crash;
- resource estimates;
- load/unload/reconnect lifecycle.

## 8. Real speech engine gates

Every promoted speech route requires target-hardware evidence.

TTS measure:

- clean install;
- cold start/model load;
- first/warm generation latency;
- RAM/VRAM;
- cancellation/recovery;
- valid output/provenance;
- human listening notes.

ASR measure:

- CER/WER or appropriate metric on redistributable fixtures;
- real-time factor;
- timestamps/segmentation;
- RAM/VRAM/startup;
- cancellation/recovery.

Run language-specific fixtures:

```text
Japanese
English
representative Japanese/English mixed content
```

Do not mark a route globally recommended when only one language was tested. Promotion is capability/language specific.

## 9. Bilingual/localization gate

Before Localization Studio is production-ready verify:

- UI works in Japanese and English;
- `ui_locale` is independent from `content_language`;
- JP/EN paired lines preserve stable `line_id`;
- voice mappings persist by character/profile;
- partial retry regenerates only failed/changed lines;
- project naming/locale directories are deterministic;
- pronunciation dictionary applies as intended;
- export uses scoped grants, no raw project path;
- reconnect/restart preserves batch state.

Optional TTS->ASR round-trip QA must be validated as a **flagging heuristic**, not naturalness proof. Choose thresholds only after real bilingual fixtures; untested semantic requirements remain `not_checked`.

## 10. ControlDeck integration gate

With real ControlDeck or contract-faithful harness verify:

- trusted feature install/update/rollback where signature support is available;
- Add-on install/enable/effective lifecycle;
- opaque embedded view;
- theme/locale/safe-area bridge;
- service token/introspection as required;
- Host Job attach/update;
- Resource request -> wait -> lease -> activate -> renew/release;
- generic AI release path when used;
- disable while waiting/running;
- input grant/output commit;
- workflow and agent invocation;
- optional missing SFX/Music does not incorrectly make Speech Essentials unavailable.

## 11. Browser E2E gate

Real browser checks include applicable cases:

- Japanese UI;
- English UI;
- dark/light;
- desktop and mobile widths;
- Easy/Customize/Expert disclosure;
- no duplicate/stranded navigation paths;
- setup progress and contextual optional-pack install;
- dead WebSocket/network drop then reconnect;
- background/visibility return;
- active Job progress reattach;
- queued cancel immediate settlement;
- running cancel;
- capability unavailable/remediation copy;
- project export;
- no horizontal overflow / unusable wrapped action labels;
- no page/console errors.

## 12. Clean setup gates

At least once per release candidate, test from clean SonicForge state rather than a developer's already-working environment.

### Lightweight signed feature

- no previous SonicForge feature version where the scenario requires fresh install;
- bundle download/verify/extract/provision/health/activate.

### Speech Essentials

```text
no SonicForge ML runtimes
empty/controlled model cache state
known data/config state
```

Record downloads, disk use, build duration and final Japanese/English capability state.

### Optional packs

Game Audio and Music are tested independently. Installing/removing them must not break Speech Essentials.

Setup safety cases:

- idempotent second run;
- network/process interruption;
- insufficient disk;
- missing system prerequisite;
- gated terms;
- invalid staged runtime;
- cancel;
- repair;
- rollback.

`doctor` remains read-only.

## 13. Audio/SFX/music quality gate

Use repeatable prompt/task suites and record:

- usable result rate;
- prompt adherence review;
- duration behavior;
- clipping/invalid/silent output;
- loop suitability/seam where relevant;
- generation latency/resource footprint;
- Japanese/English prompt behavior where user-facing prompts support both languages.

Human evaluation criteria/sample IDs are recorded. Engine popularity is not evidence.

## 14. Resource safety gate

For every GPU worker:

- measured/defensible resource estimate;
- Host lease before protected GPU work/model load;
- wait path;
- cancel while waiting;
- cancel while running;
- release on success/failure/cancel;
- crash cannot leak permanent lease beyond Host fail-safe;
- large VRAM is not retained outside declared residency/resource policy;
- interaction with ControlDeck LLM/AI release policy tested when relevant.

## 15. Security/supply-chain gate

Before merge for files/process/network/setup/release/model code:

- no `shell=True`;
- no unchecked user executable/path/package URL;
- no traversal/symlink escape;
- no secret/token/signing-key logs;
- no Host cookie forwarding;
- bounded request/response/archive/log sizes;
- non-root worker default;
- runtime/package sources locked/known;
- third-party model source/revision/digest/license recorded or explicitly unverified;
- valid release signature does not bypass Host capability allowlist;
- voice rights/consent preserved.

## 16. CI philosophy

Ordinary PR CI:

- lightweight core tests;
- schema/manifest tests;
- fake workers;
- setup planner without large downloads;
- disposable-key signing/verifier tests;
- ja/en localization key completeness;
- frontend type/build/E2E subset when relevant;
- security invariants.

Heavy model/GPU tests use explicit hardware workflows/runners and caching. CI success does not replace target-machine evidence for promotion.

Release signing key is only available to the authorized release-signing step after normal gates, never pull-request CI.

## 17. Dependency/runtime updates

For critical upgrades:

1. new fingerprint/lock;
2. stage separately;
3. smoke + language/task benchmark;
4. compare quality/resource regressions;
5. atomically activate;
6. retain rollback metadata where practical.

Do not mutate the active runtime in place and call it a safe update strategy.

## 18. Database/data migration gate

- explicit migrations;
- additive/reversible where practical;
- assets/provenance/voice/localization records not silently deleted;
- old fixture DB migration tests after releases exist;
- public/logical IDs remain stable;
- migration failure leaves usable prior state.

## 19. Documentation discipline

Synchronize:

```text
Host/release boundary       <-> docs/01 + docs/13
setup                       <-> docs/02
public API/language          <-> docs/03
engine promotion             <-> docs/04
UX/localization/reconnect    <-> docs/05 + docs/14
security/signing/provenance  <-> docs/06
implementation order         <-> docs/09
actual evidence              <-> docs/implementation-status.md
```

## 20. Evidence format

Record for each completed slice:

```text
date / commit
exact environment/hardware
commands/actions actually executed
observed result
latency/RAM/VRAM/disk/download where relevant
language/task fixtures used
browser/API assertions
known limitations
NOT TESTED items
```

Always distinguish upstream claim from local measurement.

## 21. Definition of done

A slice is done only when:

- reviewable code/contracts/docs agree;
- tests pass;
- relevant real E2E/failure/cancel/reconnect path was executed;
- release/security gates relevant to the slice pass;
- evidence is recorded;
- untested areas are explicit;
- no architecture boundary was weakened for convenience.

## 22. Stop conditions

Return to design when:

- a new engine conflicts with a working runtime -> separate runtime;
- a worker seems to require unrestricted Host paths -> redesign around grants;
- solution seems to import ControlDeck/MediaForge -> boundary violation;
- model/release trust/license cannot be established -> do not promote;
- target hardware is unreliable -> keep experimental/defer;
- frozen contract would break -> write migration/version plan;
- setup appears to require arbitrary root shell -> generic Host design, not bypass;
- current Host lacks signature-aware release verification -> record Host gate and implement generic verifier separately, not per-release SHA churn.