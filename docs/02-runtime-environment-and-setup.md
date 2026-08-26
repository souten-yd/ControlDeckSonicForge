# Runtime Environment and One-Click Setup

Status: Normative  
Date: 2026-08-25

## 1. Requirement

SonicForge owns its environment independently from ControlDeck and MediaForge.

This is an architectural boundary, not merely an installation preference.

The product separates two installation layers:

```text
A. lightweight SonicForge feature
   installed/updated by ControlDeck's generic trusted Release Bundle Feature path
   target trust = Ed25519 publisher-signed release manifest

B. SonicForge ML capability packs
   provisioned by SonicForge itself after the service is available
   separate runtimes/models, durable one-click setup
```

See `13-release-distribution-and-signing.md` for release trust.

## 2. What must be independent

SonicForge owns and isolates:

- lightweight core Python virtual environment
- heavy ML runtime virtual environments
- runtime lock/fingerprint state
- model library/catalog state
- asset DB and provenance DB
- voice profiles and dictionaries
- localization project/profile state
- temporary job workspaces
- logs
- downloadable model weights unless the user explicitly points to an external model library
- default package/model download caches

No SonicForge venv may be reused by ControlDeck or MediaForge, and vice versa.

## 3. Default paths

Repository/source checkout:

```text
ControlDeckSonicForge/
├─ .venv/                              lightweight development/core env
├─ runtimes/
│  ├─ torch-rocm-a/.venv/              shared only by compatible SonicForge packs
│  ├─ torch-rocm-b/.venv/              incompatible dependency family
│  ├─ cpu-asr/.venv/
│  └─ ...
├─ worker_packs/
│  ├─ tts-qwen/
│  ├─ tts-gptsovits/
│  ├─ tts-sbv2/
│  ├─ asr-kotoba/
│  ├─ asr-multilingual/
│  ├─ asr-reazon/
│  ├─ audio-stable3/
│  └─ music-acestep/
├─ schemas/
└─ sf.sh
```

Default persistent state:

```text
~/.local/share/control-deck-sonic-forge/
├─ sonicforge.db
├─ models/
├─ voices/
├─ dictionaries/
├─ assets/
├─ runtime-state/
├─ tmp/
└─ logs/
```

Default cache:

```text
~/.cache/control-deck-sonic-forge/
├─ pip/
├─ uv/
├─ huggingface/
└─ downloads/
```

When installed by ControlDeck Release Bundle Features, the generic Host may provide managed feature roots/data/cache environment variables. SonicForge maps those generic paths into its own data/runtime policy without importing ControlDeck Python internals.

Respect explicit environment variables and configured model-library roots.

## 4. Environment layering

### 4.1 Lightweight core environment

Purpose:

- FastAPI/Uvicorn
- Pydantic
- SQLAlchemy/Alembic
- httpx
- JSON Schema
- lightweight audio metadata/probing helpers
- setup orchestration
- worker process supervision
- Host Add-on Runtime client
- UI/backend localization resources

The core starts without torch or production models and can report `setup_required`.

### 4.2 Runtime environments

Heavy engines are grouped by **dependency fingerprint**, not arbitrarily by feature name.

A fingerprint includes at least:

```text
python major/minor
torch version/build
ROCm/CUDA/CPU backend family
critical compiled dependency versions
engine lockfile hash
platform/architecture
```

Multiple SonicForge packs may share a runtime only when compatibility is proven. Never mutate a known-good runtime merely to satisfy a newly introduced incompatible engine; create another runtime family.

### 4.3 Worker packs

Each pack declares:

- stable pack id/version
- capabilities provided
- supported content languages/locales
- runtime fingerprint/requirements
- required/optional model artifacts
- estimated download/disk footprint
- supported hardware backends
- smoke-test protocol
- license/terms metadata
- resource estimate policy
- adapter protocol version

Core launches workers as subprocesses/services; it does not import their heavy ML modules.

## 5. One-click provisioning UX

The default prominent action is deliberately smaller than the original "install everything" design:

**音声基本環境をセットアップ / Set up Speech Essentials**

Speech Essentials targets first-class Japanese + English TTS/ASR on the detected hardware.

SFX and Music are optional contextual packs. Entering an uninstalled task gives a direct action such as:

```text
効果音生成をセットアップ / Set up Game Audio
音楽生成をセットアップ / Set up Music
```

Users who explicitly want all supported packs can choose `Full Studio` under setup details.

### 5.1 API sketch

```text
GET  /addon/v1/setup/status
GET  /addon/v1/setup/plan?profile=speech-essentials
POST /addon/v1/setup/apply
POST /addon/v1/setup/cancel
POST /addon/v1/setup/repair
POST /addon/v1/setup/update
```

Request example:

```json
{
  "profile": "speech-essentials",
  "components": [],
  "accepted_terms": []
}
```

Profiles:

```text
speech-essentials   default; Japanese + English TTS/ASR
 game-audio          SFX + deterministic processing additions
 music               local music/BGM additions
 full-studio         all currently supported recommended packs
 cpu-essentials      practical CPU-capable speech subset
 custom              explicit component selection
```

The normal UI does not show component checkboxes until setup details/Custom is opened.

## 6. Preflight plan

Before changing state, show:

- detected OS/architecture
- Python availability
- GPU inventory/backend
- ROCm/CUDA usability where relevant
- disk free space
- planned runtime packs
- planned model downloads
- approximate download/disk sizes where known
- required gated terms
- capabilities/languages expected to become available
- components unsupported on the current hardware

The plan is read-only.

Do not show dozens of wheels/packages in the primary UI. Technical details belong under disclosure/diagnostics.

## 7. Provisioning state machine

```text
not_started
  -> planning
  -> awaiting_terms          optional
  -> downloading
  -> building_runtime
  -> installing_engine
  -> downloading_models
  -> validating
  -> activating
  -> completed
```

Failure/cancel:

```text
failed_recoverable
failed_blocked
canceled
```

Each phase has:

- progress 0..1 when measurable
- current component/capability pack
- localized concise message
- bounded recent technical log excerpt
- durable resume metadata

Setup attaches to a ControlDeck Job when invoked through the Add-on. Browser closure/navigation does not own or cancel it.

## 8. Atomic install strategy

Never build directly into an active runtime.

```text
runtimes/.staging/<runtime-id>-<operation-id>/
   -> create venv
   -> install locked dependencies
   -> install/prepare engine
   -> acquire/download model artifacts
   -> run import/hardware/real minimal smoke tests
   -> write manifest/fingerprint
   -> atomic rename/symlink activation
```

Keep the previous active runtime until validation succeeds.

Interrupted staging is resumed only when reconciliation can prove it safe; otherwise it is discarded/rebuilt without touching the active runtime.

## 9. Idempotency and reconciliation

Repeated `setup/apply(speech-essentials)` converges rather than reinstalling.

Record per component:

- desired version/fingerprint
- installed version/fingerprint
- dependency lock hash
- model source revision/digest
- last smoke-test result/time

A second run is a no-op when already reconciled.

## 10. Package installation rules

Preferred tooling may use `uv`, with pip-compatible fallback when needed.

Rules:

- exact/pinned runtime-critical dependency sets
- known package sources
- no `shell=True`
- no arbitrary browser-provided package names
- no global site-packages modification
- no system Python pollution
- no silent sudo
- no `curl | sh`

Release-bundle publisher signing does not authorize arbitrary packages downloaded later. Runtime dependencies still follow lock/source integrity policy.

## 11. Model download rules

Models are separate from venvs and from the signed lightweight release bundle.

Model catalog stores:

- source/repository identity
- immutable revision where possible
- expected files
- digests when available
- size
- language/capability support
- license/terms state

Use resumable downloads where supported, private partial staging and atomic activation.

If gated terms are required, stop at `awaiting_terms`. Never auto-accept.

A signed SonicForge release is not proof that a third-party model is licensed or authentic; third-party model trust/provenance remains separately recorded.

## 12. Hardware validation

Installation success is not inference success.

GPU validation includes where applicable:

- framework imports
- target device visible
- device properties readable
- small tensor operation succeeds
- required dtype/attention path works
- VRAM total/free obtainable
- engine-specific minimal real inference

CPU workers require a real minimal inference/transcription smoke test.

A failed worker only degrades its capabilities.

## 13. Runtime lifecycle

```text
stopped
starting
loading_model
ready
busy
draining
failed
```

Worker protocol includes:

- health/version/capability handshake
- load/unload model
- execute/progress/cancel
- graceful shutdown

Worker crash does not terminate SonicForge core.

## 14. Model residency and ControlDeck Resource Broker

SonicForge controls its own worker/model residency, but ControlDeck owns cross-application GPU arbitration.

GPU behavior:

1. create/attach durable Host Job;
2. request Host resource lease before protected GPU work/model load;
3. wait without consuming unrelated runner capacity;
4. activate lease;
5. load/execute;
6. obey cancel/yield/release contract;
7. release lease on success/failure/cancel.

Do not retain large VRAM outside declared resource/residency policy.

## 15. Update/repair/remove

### Lightweight product update

Use generic signed Release Bundle Feature side-by-side update/health/atomic current/rollback semantics. See `13-release-distribution-and-signing.md`.

### ML pack update

- plan first
- stage beside active runtime
- validate
- atomically activate
- preserve rollback target where storage permits

### Repair

- revalidate only affected fingerprints/files
- rebuild broken components
- preserve models/assets/voices unless the user explicitly removes them

### Remove

Show reclaimed size and lost capabilities before deletion.

## 16. What one-click setup does not silently do

- install/upgrade kernel drivers
- modify ROCm system packages as root
- change BIOS settings
- accept third-party licenses
- grant new ControlDeck Host capabilities
- delete user assets/voices

`doctor` reports blockers with actionable remediation.

## 17. CLI parity

UI and CLI call the same orchestration logic:

```text
./sf.sh serve
./sf.sh doctor
./sf.sh setup plan [profile]
./sf.sh setup apply [profile] [--component component] [--accept-term terms-id]
./sf.sh setup repair <component> [--accept-term terms-id]
./sf.sh env list
./sf.sh env prune
./sf.sh model list
./sf.sh test
```

`doctor` is strictly read-only.

`--accept-term` is explicit, repeatable and restricted to known setup terms.
Omitting it never accepts a third-party license. `provision --profile ...`
remains a compatibility alias for `setup apply`.

## 18. UX rule for complexity

Setup state shown to ordinary users is capability-oriented:

```text
Speech Essentials       Ready / Needs setup / Update available
Game Audio              Optional / Ready
Music                   Optional / Ready
```

Runtime IDs, Python packages, model revisions and exact fingerprints remain visible in Expert/Diagnostics, not on the default setup card.
