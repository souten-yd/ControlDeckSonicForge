# SonicForge Implementation Status

Last updated: 2026-08-25

This document records **observed implementation state and evidence**. `IMPLEMENTED` means code exists on `impl/full-platform-baseline`; it does not imply target-hardware validation. Anything not actually executed is explicitly marked `NOT TESTED`.

## 1. Current summary

| Area | State | Evidence / note |
|---|---|---|
| Specification baseline | COMPLETE | Normative design/specification baseline exists on `main` |
| Japanese + English product contract | IMPLEMENTED baseline | Separate UI locale/content language/voice language concepts; bilingual speech/localization APIs |
| Easy / Customize / Expert UX | IMPLEMENTED | Embedded Studio exposes task-level defaults and hides engine/model controls from normal flow |
| SonicForge core service | IMPLEMENTED | FastAPI service, `/health`, capability discovery, durable SQLite state, assets, voices, jobs, setup APIs |
| Dedicated SonicForge state/cache | IMPLEMENTED | Uses SonicForge-owned data/cache/runtime/model directories; no ControlDeck/MediaForge imports into workers |
| Add-on v2 manifest | IMPLEMENTED | `addon.json` contains navigation, embedded view, 4 workflow executors, 5 agent tools, context actions and setup checklist |
| Browser Bridge integration | IMPLEMENTED | Uses ControlDeck `host.file.pick` for scoped input grants; proxy-relative embedded URLs |
| Direct embedded settings route | IMPLEMENTED, TEST ADDED | `/settings/` static entry opens Runtime view; regression test added, latest suite not yet run |
| Browser reconnect | IMPLEMENTED, NOT BROWSER-E2E TESTED | WebSocket reconnect/backoff and authoritative reload implemented |
| Durable generation jobs | IMPLEMENTED | SQLite Job state, cancellation, restart interruption handling, server-owned work |
| Host Job integration | IMPLEMENTED, NOT HOST-E2E TESTED | create/attach, bounded progress/terminal sync and Host cancel polling implemented |
| Resource Broker integration | IMPLEMENTED, NOT HOST-E2E TESTED | request/wait/activate/renew/release and credential refresh implemented for GPU work |
| Scoped input grants | IMPLEMENTED, NOT HOST-E2E TESTED | ASR/reference audio are copied from Host read grants; raw Host paths are not accepted |
| Project output grants | IMPLEMENTED, NOT HOST-E2E TESTED | generated assets can be uploaded/committed through Host output API |
| Speech Essentials provisioning | IMPLEMENTED, TARGET MACHINE NOT TESTED | isolated speech CPU/ROCm runtime construction and model preparation |
| Music/SFX model research | COMPLETE FOR PLAN | `docs/15-music-and-sfx-generation-plan.md` records 2026-08-25 model/runtime/license decisions |
| Game Audio default model decision | RESEARCHED + ADAPTER IMPLEMENTED, MODEL NOT TESTED | Stable Audio 3 Small-SFX CPU-first; upstream officially identifies Small-SFX as CPU/no-GPU-required |
| Japanese SFX prompt normalization | PLANNED, NOT IMPLEMENTED | Stable Audio 3 is trained on English descriptions; plan requires original Japanese prompt -> engine English prompt with both preserved in provenance |
| Music primary model decision | RESEARCHED + ADAPTER IMPLEMENTED, MODEL NOT TESTED | ACE-Step 1.5 Turbo first; upstream explicitly supports ROCm/AMD, but SonicForge target hardware has not been tested |
| Music CPU fallback | PLANNED | Stable Audio 3 Small-Music selected as optional CPU fallback after setup/runtime integration |
| Stable Audio 3 Medium | EVALUATION ONLY | upstream official runtime describes Medium as CUDA GPU; not an AMD default |
| TangoFlux | RESEARCH-ONLY / NOT DEFAULT | checkpoint terms are non-commercial research-only; must not silently route production jobs to it |
| AudioGen/MusicGen/AudioLDM2 | BENCHMARK-ONLY | published weights have non-commercial restrictions; not default production routes |
| Qwen3-TTS CustomVoice | IMPLEMENTED, MODEL INFERENCE NOT TESTED | worker code present |
| Qwen3-TTS VoiceDesign | IMPLEMENTED, MODEL INFERENCE NOT TESTED | logical voice recipe routing present |
| Qwen3-TTS Voice Clone | IMPLEMENTED, MODEL INFERENCE NOT TESTED | reference grant import + rights confirmation + Base-model clone path present |
| Japanese ASR | IMPLEMENTED, MODEL INFERENCE NOT TESTED | Kotoba-Whisper route present |
| English/multilingual ASR | IMPLEMENTED, MODEL INFERENCE NOT TESTED | Whisper large-v3-turbo route present |
| SFX generation | IMPLEMENTED, MODEL INFERENCE NOT TESTED | Stable Audio 3 Small-SFX worker present |
| Music generation | IMPLEMENTED, MODEL INFERENCE NOT TESTED | ACE-Step worker present; ROCm is upstream-supported but local compatibility/performance remains unverified |
| Localization Studio storage | IMPLEMENTED | JP/EN paired lines, voice mapping, QA/output state |
| Localization durable rendering | IMPLEMENTED, FOCUSED TEST ADDED | parent Job renders locale outputs and stores per-locale input hashes/state |
| Localization partial retry | IMPLEMENTED | `pending / failed / changed / all` modes; unchanged successful lines can be skipped |
| Deterministic audio QA | IMPLEMENTED baseline | WAV decode/duration/hash metadata; richer SFX/music QA remains planned |
| TTS->ASR semantic QA | NOT IMPLEMENTED | design exists but thresholds/false-positive policy are not yet validated |
| Signed release bundle build | IMPLEMENTED | PyInstaller bundle builder plus runtime/frontend/schema/worker packaging |
| SonicForge release signing | IMPLEMENTED + FOCUSED TESTED | Ed25519 canonical-manifest signer/verifier; tamper/context/wrong-key/noncanonical negative tests |
| ControlDeck signature-aware verifier | IMPLEMENTED ON SEPARATE BRANCH, NOT E2E TESTED | `souten-yd/ControlDeck` branch `infra/publisher-signed-release-bundles`; generic publisher-key path with legacy compatibility |
| Publisher public key registration | OPERATIONAL INPUT REQUIRED | Host code supports one-time trusted public key; production SonicForge/MediaForge public key must be registered in trusted catalog |
| Real signed Host install/update/rollback | NOT TESTED | requires trusted publisher public key and target ControlDeck runtime |
| Historical ControlDeck TTS migration | NOT STARTED | migration source inventory remains separate work |
| Target hardware performance/compatibility | NOT TESTED | no current SonicForge Qwen/Whisper/Stable Audio/ACE-Step benchmark on target hardware |
| Batched CI | NOT RUN | intentionally deferred per project CI policy; workflow is manual/tag-triggered rather than every push |

## 2. Music / SFX research decision

The researched implementation plan is:

```text
Game Audio
  default -> Stable Audio 3 Small-SFX / CPU
  prompt conditioning -> English
  Japanese UX -> PromptNormalizer before engine
  optional future -> inpaint/continue after validation

Music
  default accelerator -> ACE-Step 1.5 Turbo
  first planner comparison -> 0.6B vs 1.7B
  CPU fallback -> Stable Audio 3 Small-Music
  high quality -> ACE-Step standard/XL only after benchmark
```

Important distinctions:

- Stable Audio 3 Small-SFX is upstream-supported as CPU-first, but SonicForge has not run the actual model yet.
- ACE-Step 1.5 is upstream-supported on ROCm/AMD, including official ROCm installation guidance. This resolves the earlier uncertainty about whether ROCm is an upstream-supported route; it **does not** prove the current SonicForge runtime pin works on the target machine.
- Stable Audio 3 Medium is not the default AMD route because upstream currently documents it as CUDA GPU.
- TangoFlux remains useful for research comparison but is not a production fallback because its published checkpoint is non-commercial research-only.
- AudioCraft AudioGen/MusicGen and AudioLDM2 remain benchmark references rather than standard engines because their published model weights impose non-commercial restrictions.

See `docs/15-music-and-sfx-generation-plan.md` for the complete runtime, routing, UX, QA, license and benchmark plan.

## 3. Implementation branch evidence

Primary implementation branch:

```text
impl/full-platform-baseline
```

Important implementation milestones include:

- platform/core baseline;
- speech workers and logical voice routing;
- setup/packaging/worker-boundary hardening;
- proxy-safe embedded Studio and Browser Bridge integration;
- durable bilingual Localization rendering;
- signed release negative-test hardening;
- direct `/settings/` embedded entry and frontend regression test;
- researched Music/SFX implementation plan.

The branch is ahead of `main`. GitHub Actions has not been triggered during iterative implementation.

## 4. Focused validation actually executed

### Release signing

A focused local test run was executed for SonicForge release signing:

```text
pytest -q tests/test_release_signing.py tests/test_release_signing_negative.py
.... [100%]
4 passed in 0.07s
```

Validated cases include:

- valid Ed25519 signature over canonical manifest;
- artifact tamper rejection;
- valid signature over wrong feature/version/platform/architecture/name/size/digest rejected;
- wrong publisher key rejected;
- malformed signature rejected;
- noncanonical manifest rejected.

### Schema validation

Focused Pydantic validation was executed for `speech.localization.batch`:

- valid JP/EN request accepted;
- duplicate locale entries rejected;
- invalid localization mode rejected.

### Frontend static checks

`frontend/localization.js` passed `node --check` when authored. A later regression test was added for root frontend, `localization.js` and the direct `/settings/` embedded route, but the current full suite has not yet been executed.

### Earlier baseline tests

An earlier lightweight baseline run had 9 tests passing and a fake-worker/Uvicorn smoke was exercised before later hardening changes. Because the implementation changed afterward, **that earlier result is not treated as proof that the current branch full suite is green**.

### Current local-environment limitation

Attempting to clone the current GitHub branches into the execution container failed with:

```text
Could not resolve host: github.com
```

Therefore the latest branch-wide pytest/browser suite has not been executed locally in this session. CI is intentionally not being used as a substitute until the large batch is ready.

## 5. Runtime and security boundaries now implemented

1. SonicForge remains an out-of-process Add-on; ControlDeck does not import SonicForge Python/JavaScript.
2. Heavy workers run in SonicForge-owned runtime environments and communicate through a bounded JSON subprocess protocol.
3. No `shell=True`; external command parsing uses argv semantics.
4. Worker cancellation terminates the worker process group and escalates to kill after a bounded timeout.
5. Worker output must remain under its private work directory and below a size bound.
6. Host file/project access uses scoped grants and output receipts; raw Host paths are not a public protocol.
7. GPU work requires a ControlDeck-managed Host Job and Resource Broker lease.
8. CPU Small-SFX should not require a GPU lease.
9. Host service credentials are short-lived; active lease credentials can be refreshed through the Host API.
10. Voice clone reference audio is copied into SonicForge-owned storage and the expiring Host grant is not stored as the durable voice identity.
11. Clone/import/trained voice profiles require an explicit rights-confirmation event; this is a product safety gate, not legal certification.
12. Stability model terms are not silently accepted during Game Audio setup.
13. Optional Game Audio/Music absence does not make healthy Speech Essentials unavailable.
14. Future Japanese SFX prompt normalization must preserve both original and engine prompt in provenance rather than hiding translation/rewrite behavior.

## 6. Localization implementation

`Localization Studio` is no longer only a draft-state UI.

Current behavior:

```text
LocalizationBatch
  └─ LocalizationLine[]
       ├─ ja_text / en_text
       ├─ voice_id
       ├─ outputs.ja / outputs.en -> asset IDs
       └─ qa
            ├─ locales.ja / locales.en
            └─ input_hashes.ja / input_hashes.en
```

A `speech.localization.batch` task owns expensive work server-side. Supported modes are:

- `pending`: render missing/non-successful locale outputs;
- `failed`: retry failed locale outputs only;
- `changed`: rerender only missing/hash-changed outputs;
- `all`: explicitly rerender all selected outputs.

Each output becomes a normal SonicForge asset with provenance. Semantic correctness is not falsely marked passed; it remains `not_checked` until a real semantic validator is used.

## 7. Release trust state

SonicForge release tooling implements the same trust split as current MediaForge release direction:

```text
publisher authorization = Ed25519 signature over canonical manifest
artifact integrity       = SHA-256 + size inside that signed manifest
runtime authority        = ControlDeck Add-on capability allowlist
```

SonicForge verifier binds:

```text
schema_version
feature_id
version
platform
architecture
artifact_name
sha256
size_bytes
```

The separate ControlDeck branch `infra/publisher-signed-release-bundles` adds a generic `publisher_public_key` catalog path. If a trusted public key is present, manifest/signature assets are mandatory and the installer must not fall back to the legacy SHA-pin path. Catalog entries without a publisher key temporarily retain the old SHA-pin flow for migration compatibility.

A production publisher public key has **not** been invented or committed by this implementation session. The private signing key must be created and retained outside the repositories; only its public key belongs in ControlDeck trusted configuration.

## 8. Remaining release gates

Before calling SonicForge production-ready, the following evidence is still required:

1. run the current full lightweight pytest/static suite as one batched validation;
2. install the Add-on into a real ControlDeck using a registered publisher public key;
3. test signed fresh install, same-version repair, upgrade, downgrade rejection and rollback;
4. test Host Job + Resource Broker lifecycle against real ControlDeck;
5. test scoped input/output grants through the real embedded Browser Bridge;
6. run Japanese/English Qwen3-TTS inference on target hardware;
7. run Japanese/English/mixed ASR fixtures on target hardware;
8. load Stable Audio 3 Small-SFX on CPU and run the SF4 fixture bank;
9. implement/validate Japanese SFX PromptNormalizer behavior;
10. reproduce a pinned ACE-Step ROCm runtime and run 30/60/90 second music fixtures;
11. compare ACE-Step 0.6B vs 1.7B planner routes;
12. add/test Stable Audio 3 Small-Music CPU fallback;
13. validate loop processing/export for SFX and music;
14. run browser/mobile reconnect/reattach E2E;
15. benchmark RAM/VRAM/disk/download/latency and record measured routing thresholds.

Until those checks are complete, model/hardware compatibility remains `NOT TESTED`, even where the worker/runtime implementation is present.
