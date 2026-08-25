# Runtime Environment and One-Click Setup

Status: Normative  
Date: 2026-08-25

## 1. Requirement

SonicForge owns its environment independently from ControlDeck and MediaForge.

This is an architectural boundary, not merely an installation preference.

## 2. What must be independent

SonicForge owns and isolates:

- lightweight core Python virtual environment
- heavy ML runtime virtual environments
- runtime lock/fingerprint state
- model library/catalog state
- asset DB and provenance DB
- temporary job workspaces
- logs
- downloadable model weights unless the user explicitly points to an external model library
- default package/model download caches

No SonicForge venv may be reused by ControlDeck or MediaForge, and vice versa.

## 3. Default paths

Repository-local:

```text
ControlDeckSonicForge/
├─ .venv/                              lightweight core
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

Respect explicit environment variables and configured model-library roots.

## 4. Environment layering

### 4.1 Core environment

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

The core should remain small and start even when no ML runtime is installed.

### 4.2 Runtime environments

Heavy engines are grouped by **dependency fingerprint**, not arbitrarily by feature name.

A runtime fingerprint should include at least:

```text
python major/minor
torch version/build
ROCm/CUDA/CPU backend family
critical compiled dependency versions
engine lockfile hash
platform/architecture
```

Multiple SonicForge worker packs may share one runtime only when the fingerprint is compatible and verified.

Never mutate a compatible working runtime just to satisfy a newly added incompatible engine. Create another runtime family.

### 4.3 Worker packs

Each worker pack declares:

- stable pack id/version
- capabilities provided
- runtime fingerprint/requirements
- required model artifacts
- optional model artifacts
- estimated disk footprint
- supported hardware backends
- smoke-test command/protocol
- license/terms metadata
- resource estimate policy
- adapter protocol version

Core launches workers as subprocesses/services; core does not import their heavy Python modules.

## 5. One-click provisioning UX

The expected normal setup path is a button:

**推奨環境をセットアップ**

The button lives in SonicForge's setup/runtime UI and invokes a SonicForge API. ControlDeck does not execute arbitrary manifest commands.

### 5.1 API sketch

```text
GET  /addon/v1/setup/status
GET  /addon/v1/setup/plan?profile=recommended
POST /addon/v1/setup/apply
POST /addon/v1/setup/cancel
POST /addon/v1/setup/repair
POST /addon/v1/setup/update
```

`POST /setup/apply` request example:

```json
{
  "profile": "recommended",
  "components": [],
  "accepted_terms": []
}
```

Profiles:

```text
recommended   Japanese TTS + Japanese ASR + practical SFX + music if hardware permits
speech-only   TTS + ASR
cpu-only      CPU-capable subset
advanced      explicit component selection
```

The UI default is `recommended`; component checkboxes are not shown until advanced mode.

## 6. Preflight plan

Before changing the machine, calculate and show:

- detected OS/architecture
- Python availability
- GPU inventory and backend detection
- ROCm/CUDA usability where relevant
- disk free space
- planned runtime packs
- planned model downloads
- approximate download/disk sizes where known
- gated model terms that require explicit acceptance
- capabilities expected to become available
- components that cannot be installed on this hardware

The plan must be obtainable without modifying the environment.

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

Failure/cancel states:

```text
failed_recoverable
failed_blocked
canceled
```

Each phase has:

- progress 0..1 when measurable
- current component
- concise status message
- bounded recent log excerpt
- durable resume metadata

Setup should attach to a ControlDeck Job when invoked through the Add-on so progress survives browser closure.

## 8. Atomic install strategy

Never build directly into the active runtime.

Use:

```text
runtimes/.staging/<runtime-id>-<operation-id>/
   -> create venv
   -> install locked dependencies
   -> install/prepare engine
   -> run import/hardware smoke tests
   -> write manifest/fingerprint
   -> atomic rename/symlink activation
```

Keep the previous active runtime until the new runtime passes validation.

Interrupted staging directories are detected on next startup and either resumed when safe or removed/rebuilt.

## 9. Idempotency

Repeated `setup/apply(recommended)` must converge, not reinstall everything.

Each component records:

- desired version/fingerprint
- installed version/fingerprint
- dependency lock hash
- model artifact hash/revision
- last smoke-test result/time

No-op when already reconciled.

## 10. Package installation rules

Preferred package tooling may be `uv` for reproducibility/speed, with pip-compatible fallback if required.

Rules:

- exact/pinned lock for runtime-critical dependencies
- verify expected package sources
- no `shell=True`
- no arbitrary package names from browser input
- no global site-packages modification
- no system Python package pollution
- no silent sudo

## 11. Model download rules

Models are separate from venvs.

- model catalog contains source, revision, expected files and license metadata
- use resumable downloads where supported
- store partial files safely
- verify hashes/size when available
- atomic activation after validation
- do not redownload an identical valid artifact
- model uninstall never deletes unrelated shared user libraries

If a model requires gated access or license acceptance, stop in `awaiting_terms`. Do not auto-accept.

## 12. Hardware validation

An installed package is not proof of usable inference.

GPU runtime validation should include:

- framework imports
- target GPU visible
- device properties readable
- small tensor operation succeeds
- required dtype/attention path works when applicable
- free/total VRAM obtainable
- engine-specific minimal model smoke test when feasible

CPU engine validation should include a minimal inference or decode/transcription path.

A failed engine smoke test marks only that worker/capability unavailable or degraded.

## 13. Runtime lifecycle

Core controls worker lifecycle:

```text
stopped
starting
loading_model
ready
busy
draining
failed
```

Worker protocol should include:

- `/health` or equivalent IPC health
- capability/version handshake
- load/unload model
- execute/cancel task
- graceful shutdown

A crashed worker is restarted according to bounded policy without killing the core.

## 14. Model residency

SonicForge can decide which of its own model processes are loaded, but ControlDeck Resource Broker owns cross-application GPU admission.

Recommended worker behavior:

1. request lease before expensive load when GPU reservation is needed;
2. activate lease;
3. load/use model;
4. obey Host yield/cancel policy where contract supports it;
5. release model if needed;
6. release lease.

Do not keep VRAM permanently allocated while claiming no lease.

## 15. Update/repair

### Update

- plan changes first
- download/build beside active runtime
- validate
- atomically switch
- retain one rollback target where disk policy permits

### Repair

- revalidate fingerprints/files
- rebuild only broken component
- never wipe all models/assets as a default repair action

### Remove

Component uninstall shows reclaimed size and affected capabilities.

## 16. What one-click setup does not do

The first implementation should **not** silently:

- install/upgrade kernel drivers
- modify ROCm system packages as root
- change BIOS settings
- install arbitrary system services outside the approved SonicForge service registration path
- accept third-party licenses

`doctor` reports these blockers with exact remediation. A future generic privileged setup facility belongs to ControlDeck's managed-service layer, not a SonicForge-specific escape hatch.

## 17. CLI parity

Every setup operation exposed in the UI must have a deterministic CLI equivalent for recovery and automation:

```text
./sf.sh serve
./sf.sh doctor
./sf.sh setup plan [profile]
./sf.sh setup apply [profile]
./sf.sh setup repair [component]
./sf.sh env list
./sf.sh env prune
./sf.sh model list
./sf.sh test
```

The CLI and UI call the same backend orchestration logic rather than implementing two installers.