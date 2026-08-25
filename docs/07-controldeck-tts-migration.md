# ControlDeck TTS Migration Plan

Status: Normative migration plan  
Date: 2026-08-25

## 1. Goal

Move ownership of ControlDeck's historical TTS functionality into SonicForge without turning SonicForge into a copied internal module and without leaving a permanent Sonic-specific subsystem in ControlDeck core.

The target end state is:

```text
ControlDeck
  -> generic Add-on v2 contribution / workflow / agent / UI bridge
  -> SonicForge
       -> TTS routing
       -> voice/model/runtime management
       -> generated audio assets/provenance
```

ControlDeck no longer owns TTS engine dependencies, model lifecycle or voice-specific business logic.

## 2. Important current-state caveat

The ControlDeck `main` branch inspected on 2026-08-25 does not expose an obvious current `tts`/`speech` implementation in the repository tree/code search, while prior ControlDeck work contained Qwen-family TTS UI/runtime behavior.

Therefore implementation must **first locate the exact historical branch/commit/source of truth** before migrating anything. Do not reconstruct old behavior from memory or screenshots alone.

Record the discovered source commit(s) in `docs/implementation-status.md` before porting code.

## 3. Historical behavior to inventory

The migration inventory should explicitly check for the following historical concepts and preserve only behavior that is still useful:

- Qwen3-TTS model selection, including quality/speed-oriented variants
- enable/disable and auto-speak settings
- voice selection/listing
- speech speed
- device selection
- model load/unload state
- TTS status endpoint/state
- generated WAV/audio handling
- frontend controls and user preferences
- model/data directory conventions
- any call sites from assistant/chat/workflow features

This list is an inventory aid, not a claim that every item exists on current `main`.

## 4. Ownership after migration

### SonicForge owns

- TTS engine adapters
- Qwen3-TTS runtime/model installation
- Style-Bert-VITS2 / GPT-SoVITS integration
- voice library
- reference/clone voice workflows
- speech profiles/styles
- pronunciation overrides
- synthesis API
- streaming TTS session implementation
- TTS worker lifecycle
- audio output validation
- provenance/licensing
- TTS model/runtime settings

### ControlDeck owns only generic host behavior

- whether SonicForge Add-on is installed/enabled
- navigation/embedded view slot
- generic settings link
- Jobs
- permissions/audit
- Resource Broker
- file/project grants
- workflow/agent contribution discovery and invocation
- generic notifications

ControlDeck must not gain a new `sonicforge.py`, Qwen-specific dependency, voice database or `/api/v1/tts` implementation simply to preserve legacy behavior.

## 5. Migration phases

### M0 — Source inventory and behavior capture

Before writing the replacement:

1. identify the exact historical ControlDeck TTS source branch/commit;
2. list backend/frontend files and settings keys;
3. identify every caller;
4. capture representative request/response examples;
5. create legally safe Japanese text fixtures;
6. record existing model storage expectations;
7. mark features to retain, replace or intentionally drop.

Deliverable:

`docs/migration/controldeck-tts-inventory.md`

Do not modify ControlDeck yet.

### M1 — SonicForge TTS baseline

Implement SonicForge core + Qwen3-TTS adapter behind:

```text
speech.tts.synthesize
```

Minimum:

- Japanese synthesis
- logical voice id
- speed/style normalization where supported
- fast/balanced/quality routing
- durable job for non-trivial work
- output asset + provenance
- model load/unload through worker lifecycle
- setup/runtime installation through SonicForge setup flow

Acceptance is real Japanese audio generation, not only unit tests.

### M2 — Compatibility behavior in SonicForge

Map useful historical ControlDeck concepts into SonicForge settings/profile objects.

Example conceptual mapping:

| Historical concept | SonicForge target |
|---|---|
| TTS enabled | Add-on enabled + capability state |
| engine | optional advanced routing preference |
| model | optional engine/model pin or quality preset |
| voice | logical `voice:<id>` |
| speed | normalized TTS style parameter |
| device | routing/device policy |
| load/unload | worker/runtime lifecycle |
| status | capability/runtime status |

Do not expose legacy config keys as the new canonical API merely for compatibility.

### M3 — User preference/data migration

If historical preferences/model assets still exist, migration is explicit and non-destructive.

Preferred migration wizard:

```text
旧ControlDeck TTS設定を検出
  -> import preview
  -> map settings/voices/models
  -> user confirms
  -> copy/import metadata/model assets as needed
  -> validate
  -> SonicForge becomes active
```

Rules:

- no direct import of ControlDeck Python modules
- no direct ControlDeck DB access from SonicForge
- use an explicit export/import file, generic Host endpoint, or user-selected scoped grant if migration data must cross the boundary
- never expose ControlDeck's DB path to SonicForge
- never silently delete old settings or models

## 6. Model-weight migration

Environment independence also applies during migration.

Do not make SonicForge depend on a model living inside an old ControlDeck TTS runtime directory.

Allowed strategies:

1. **copy/import** the model into a SonicForge-managed model library;
2. **move** only after explicit user confirmation and successful validation;
3. **reference an external user-managed model library** when the user deliberately configures it and the model catalog can validate the artifact.

Avoid cross-project symlinks as the normal migration mechanism because they create hidden lifecycle coupling.

After import, verify:

- model files/revision/hash
- license metadata
- engine compatibility
- smoke synthesis
- disk impact

## 7. Voice migration

Legacy voice identifiers must be converted to logical SonicForge voice records.

Possible mapping:

```text
old speaker/model settings
  -> voice record
       id = voice:<stable-id>
       source_type = built_in | imported_model | reference_recipe
       engine compatibility
       license/rights metadata
```

Do not use a model checkpoint path as the stable user-facing voice identity.

## 8. Frontend migration

Do not transplant old TTS React/components into the privileged ControlDeck frontend unless they are truly generic host UI.

Speech-specific UI belongs in SonicForge embedded view.

If another ControlDeck feature needs "speak this text" without opening the workspace, use a generic Add-on execution contribution/tool contract rather than importing SonicForge UI code.

Any generic Host shortcut added for this purpose must be capability-based and reusable by another speech Add-on.

## 9. Auto-speak behavior

Historical `auto_speak` behavior, if retained, needs a clean ownership decision.

Recommended target:

- the feature that decides **when** a message should be spoken owns the user preference/trigger;
- SonicForge owns **how** it is synthesized;
- invocation occurs through a generic Add-on tool/execution contract.

Do not move chat/assistant behavioral preferences into SonicForge merely because it produces audio.

## 10. Temporary compatibility shims

A Sonic-specific permanent compatibility API in ControlDeck is rejected.

If an unavoidable temporary shim is required during a staged migration:

- document why existing generic Add-on execution cannot cover it;
- place it in a separate ControlDeck PR;
- mark it deprecated at creation;
- add a removal issue/milestone;
- do not add ML dependencies;
- do not expose raw model/path concepts;
- remove after all callers move to the generic contract.

Prefer no shim when current ControlDeck `main` no longer contains the old caller.

## 11. Cutover criteria

Do not remove/deprecate any remaining ControlDeck TTS path until all applicable checks pass:

- SonicForge setup from a clean state succeeds
- Japanese synthesis quality is at least acceptable against captured fixtures
- relevant prior settings can be represented or intentionally documented as removed
- voice selection works
- cancellation/error handling works
- GPU lease behavior works when GPU is used
- generated audio is validated and provenance exists
- all known ControlDeck callers use generic Add-on invocation
- rollback instructions exist

## 12. Rollback

During migration:

- keep old model/settings data untouched by default
- keep migration import records
- switching SonicForge off must not corrupt old data
- a failed import must not leave half-created active voice/model records
- use staging + transaction/atomic activation for imported metadata

Rollback is not "restore the shared old venv" because sharing that environment is explicitly forbidden.

## 13. Removal from ControlDeck

If historical TTS code is found and still present, final cleanup should remove only after cutover:

- TTS-specific backend dependencies/routes/services
- TTS-specific model management
- TTS-specific privileged frontend panels
- stale settings keys only after migration/deprecation window
- obsolete tests/docs

Keep generic Add-on/Jobs/Resource Broker/notification capabilities.

## 14. Evidence required

Record:

- historical source commit identified
- exact migrated settings/features
- real old-vs-new Japanese audio fixture results
- measured first-load/warm latency
- measured memory/VRAM
- migration disk behavior
- rollback test
- items intentionally not migrated

Anything not executed is `NOT TESTED`, not assumed successful.