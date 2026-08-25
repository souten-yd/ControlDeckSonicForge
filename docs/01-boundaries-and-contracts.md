# Architecture, Ownership and Boundary Rules

Status: Normative  
Date: 2026-08-25

## 1. Executive rule

SonicForge is an **out-of-process Add-on v2 service**. ControlDeck is the generic host. MediaForge is a sibling Add-on.

The architecture succeeds only if each repository can evolve independently without importing the other's private implementation.

## 2. Ownership matrix

| Concern | ControlDeck | SonicForge | MediaForge |
|---|---|---|---|
| Add-on install/enable/effective registry | owns | consumes | consumes |
| manifest validation | owns | declares | declares |
| host navigation/shell | owns generic slots | contributes Audio entry | contributes Media entry |
| embedded view proxy/sandbox | owns | consumes | consumes |
| theme/locale/safe-area bridge | owns | consumes | consumes |
| authentication identity | owns | introspects scoped token | introspects scoped token |
| RBAC/host permissions | owns | requests fixed host capabilities | requests fixed host capabilities |
| durable global Jobs | owns | attaches/updates jobs | attaches/updates jobs |
| GPU Resource Broker | owns | requests leases | requests leases |
| project/file grants | owns | consumes grants | consumes grants |
| raw project paths | owns only | forbidden | forbidden |
| TTS/ASR business logic | none | owns | none |
| audio/music generation | none | owns | none |
| image/video/3D generation | none | none | owns |
| engine/model registry | generic host models only | owns audio engine registry | owns media engine registry |
| worker Python dependencies | none | owns | owns |
| SonicForge asset/provenance DB | none | owns | none |
| MediaForge asset/provenance DB | none | none | owns |

## 3. ControlDeck contracts SonicForge must obey

Current host baseline:

- Add-on contract: `>=2.0 <3.0`
- runtime kind: `external-service`
- runtime URL: HTTPS or loopback HTTP
- default SonicForge loopback: `http://127.0.0.1:9140`
- host-mediated embedded proxy; browser must not access the loopback service directly from the HTTPS ControlDeck origin
- opaque iframe origin; no `allow-same-origin`
- ControlDeck strips Host Cookie/Authorization before proxying upstream
- service authentication uses short-lived Add-on service tokens
- Runtime API service identity must match Add-on ID/audience/path
- Host picker/export/project access uses scoped grants rather than paths
- GPU/resource work uses Runtime Resource APIs
- unavailable execution contributions are removed from executable discovery; navigation remains visible for enabled Add-ons with an explanatory state

### Current Host capabilities relevant to SonicForge

Use only existing allowlisted capabilities unless a separately reviewed generic host change is required:

```text
context.read
theme.read
route.open
files.pick
files.export
projects.pick
jobs.read
jobs.write
notifications.show
resources.acquire
ai.inference
```

Do not invent Sonic-specific host capability names in the manifest.

## 4. Proposed SonicForge manifest contributions

The first public contract should remain small:

### Navigation / view

- `workspace` -> `/x/sonic-forge/workspace`
- embedded view path `/`
- mobile mode `companion` unless the compact UI proves viable

### Settings

- `settings` -> `/x/sonic-forge/workspace/settings`

### Commands

- `create-audio` -> task chooser / quick create
- optional later commands may be added, not required for v1 contract freeze

### Workflow executors

Prefer a small set of stable task-level executors rather than one executor per model:

```text
sonic.speech.synthesize
sonic.speech.transcribe
sonic.audio.generate
sonic.music.generate
```

A later additive executor may support transform/edit operations.

### Agent tools

Initial set:

```text
sonic.capabilities
sonic.generate
sonic.transcribe
sonic.inspect
sonic.pack
```

`sonic.generate` uses a task/capability field; agents should not need to call engine-specific tools.

### Context actions

Initial candidates:

- `transcribe-audio`
- `open-in-sonic-forge`
- `create-variation`
- `pack-audio-to-project`

Context actions consume Host-validated `grant:` IDs, never raw paths.

### Setup checklist

At minimum:

```text
core
recommended-speech
recommended-asr
recommended-audio
recommended-music
```

The actual setup state is reported by health/setup APIs. The manifest only declares stable checklist IDs/labels.

## 5. Health and capability health

Add-on process health and individual engine health are separate.

Top-level states follow ControlDeck:

```text
available
 degraded
 unavailable
 setup_required
```

SonicForge should keep the core available/degraded while optional workers are missing.

Example capability document:

```text
speech.tts.synthesize          available
speech.tts.voice_clone         available
speech.asr.transcribe          available
audio.sfx.generate             setup_required
music.generate                 unavailable
```

Each unavailable/degraded capability includes a reason code and a user-facing remediation hint.

## 6. Job boundary

ControlDeck Job = user-visible durable unit of work.
SonicForge internal task/worker step = implementation detail.

Rules:

- UI, workflow and agent invocation create/attach a Host Job when durable work begins.
- Resource waiting does not consume an execution runner slot in ControlDeck.
- SonicForge can have detailed internal phases, but normalizes them to Host progress/status.
- high-frequency diffusion/token/step telemetry stays inside SonicForge.
- cancellation is polled/propagated to the active worker.
- terminal Host result remains bounded; large audio is referenced as an asset/output.

## 7. Resource Broker boundary

GPU jobs request a Host lease using estimates such as:

```text
resource_class       gpu.compute
device               auto
vram_estimate_bytes  engine/profile estimate
execution_mode       shared | exclusive-preferred | exclusive-required
priority             bounded by host subject class
interactive          true/false
model_residency_key  opaque stable residency fingerprint
```

The runtime client must not set a forged owner; Host derives `addon:sonic-forge`.

SonicForge owns per-engine local worker pools and their process lifecycle, but not cross-application GPU arbitration.

## 8. File and asset boundary

When embedded in ControlDeck:

Input:

```text
Host file/project picker
 -> grant:<id>
 -> SonicForge Runtime grant metadata/content API
 -> private job staging
```

Output:

```text
SonicForge generated asset
 -> Host output staging API
 -> commit into granted destination
 -> logical Host/project result
```

Forbidden in host-facing protocol:

- `/home/...`
- `/share/...`
- repository absolute paths
- ControlDeck project root paths
- symlink-derived escape paths

Standalone SonicForge may support local filesystem paths behind its own authorization model, but these must never leak into the Add-on protocol.

## 9. SonicForge and MediaForge relationship

No direct imports and no shared venv/database.

Allowed reuse:

- conceptual patterns
- copied-and-adapted small generic utilities only when their license permits and ownership is clear
- JSON vocabulary that is deliberately standardized
- Host contracts

Preferred cross-Add-on composition:

```text
ControlDeck Workflow
  -> MediaForge image/video generation
  -> Host asset/grant
  -> SonicForge audio generation
  -> project export
```

or through agent tools.

Do not create a private MediaForge-to-SonicForge filesystem shortcut.

## 10. Host-change rule

A ControlDeck change is permitted only when all are true:

1. the requirement cannot be satisfied safely within the existing Add-on contract;
2. the feature is generic for future Add-ons, not named SonicForge/MediaForge;
3. the host contract, threat model and backward compatibility are documented first;
4. the ControlDeck change is a separate PR;
5. SonicForge remains compatible with the old host where practical by degrading capability.

### Example: true zero-touch bootstrap

Current Add-on v2 intentionally does not execute arbitrary Add-on-supplied shell commands. If the product later requires "install an entirely absent external service from one Host button", design a generic, signed/approved managed-service package mechanism in ControlDeck. Do **not** add `command: ./sf.sh` to the Add-on manifest and execute it from the Host.

The initial SonicForge implementation instead assumes the lightweight service has been registered/started via the generic Apps/service layer; all heavy Python/model environments are then installed from the SonicForge UI button.

## 11. Contract compatibility policy

- reject unsupported Add-on major versions
- rely on current Host schema rather than stale copied examples
- additive public schema evolution within v1
- keep unknown model/engine details behind capability metadata
- never couple clients to internal worker process names
- contract test against ControlDeck fake-add-on/reference behavior where applicable
