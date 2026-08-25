# Architecture, Ownership and Boundary Rules

Status: Normative  
Date: 2026-08-25

## 1. Executive rule

SonicForge is an **out-of-process ControlDeck Add-on v2 service** distributed as a generic trusted ControlDeck feature. ControlDeck is the generic host. MediaForge is a sibling Add-on and architectural precedent.

Each repository must evolve independently without importing another repository's private implementation.

## 2. Ownership matrix

| Concern | ControlDeck | SonicForge | MediaForge |
|---|---|---|---|
| trusted publisher / feature install policy | owns generic trust/install mechanism | publishes signed feature | publishes signed feature |
| Add-on install/enable/effective registry | owns | consumes | consumes |
| manifest validation | owns | declares | declares |
| host navigation/shell | owns generic slots | contributes Audio | contributes Media |
| embedded view proxy/sandbox | owns | consumes | consumes |
| theme/locale/safe-area bridge | owns | consumes | consumes |
| authentication identity/RBAC | owns | consumes scoped authority | consumes scoped authority |
| durable global Jobs | owns | attaches/updates | attaches/updates |
| GPU Resource Broker | owns | requests leases | requests leases |
| project/file grants | owns | consumes grants | consumes grants |
| raw project paths | Host-internal only | forbidden | forbidden |
| TTS/ASR/localization business logic | none | owns | none |
| SFX/audio/music generation | none | owns | none |
| image/video/3D generation | none | none | owns |
| audio engine/model registry | none | owns | none |
| media engine/model registry | none | none | owns |
| worker dependencies/runtimes | none | owns | owns |
| SonicForge DB/assets/voices | none | owns | none |
| MediaForge DB/assets | none | none | owns |

## 3. Two distinct contracts

Do not conflate **feature distribution trust** with **runtime Add-on authority**.

### 3.1 Feature distribution

Target generic flow:

```text
trusted publisher public key in ControlDeck
 -> signed SonicForge release manifest
 -> artifact identity/size/SHA verification
 -> safe feature bundle install
 -> bounded provision/smoke/health
 -> atomic version activation/rollback
```

SonicForge adopts MediaForge's publisher-signature direction. SHA-256 remains inside the signed manifest; it is not the per-release authorization pin.

Detailed contract: `13-release-distribution-and-signing.md`.

### 3.2 Runtime Add-on authority

After installation, SonicForge uses Add-on v2:

- declarative manifest/contributions
- scoped service/request tokens
- Host Runtime APIs
- Browser Bridge
- Host Jobs/resources/grants/outputs

A valid release signature does not grant additional runtime capabilities.

## 4. ControlDeck runtime contracts SonicForge must obey

Baseline:

- Add-on contract `>=2.0 <3.0`
- runtime `external-service`
- HTTPS or loopback HTTP service URL
- default SonicForge origin `http://127.0.0.1:9140`
- Host-mediated embedded proxy for HTTPS ControlDeck
- opaque iframe origin; no privileged same-origin shortcut
- Host Cookie/Authorization stripped before upstream proxying
- short-lived Add-on service/request credentials
- Runtime identity must match Add-on ID/audience/path
- file/project access through scoped grants rather than paths
- GPU work through Resource Broker
- enabled navigation remains understandable when the service/capability is unavailable
- unavailable execution contributions are excluded from executable discovery as required by Host policy

### Current relevant Host capabilities

Use only values accepted by the current Host schema:

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

Do not invent `sonic.*` Host capabilities. Sonic-specific capability names belong to SonicForge's own runtime capability document, not ControlDeck's privilege system.

## 5. SonicForge public Add-on contributions

Keep the frozen Host-facing surface intentionally small.

### Navigation / embedded view

```text
workspace -> /x/sonic-forge/workspace
```

One Host navigation entry only: `Audio / オーディオ`.

Do not duplicate Studio tasks as Host quick actions unless a real shortcut use case emerges. The current draft intentionally has no quick actions.

### Settings

```text
settings -> /x/sonic-forge/workspace/settings
```

### Command

```text
create-audio
```

The command opens/routes into the Studio task chooser rather than creating a parallel editor.

### Workflow executors

Freeze four task-level executors initially:

```text
sonic.speech.synthesize
sonic.speech.transcribe
sonic.audio.generate
sonic.music.generate
```

Localization Studio is an application workflow/capability and does not require another frozen Host executor unless actual external workflow use proves it necessary.

### Agent tools

```text
sonic.capabilities
sonic.generate
sonic.transcribe
sonic.inspect
sonic.pack
```

Agents request task/language/profile. Engine/model IDs are optional advanced hints, not required tool concepts.

### Context actions

Initial useful actions:

```text
transcribe-audio
open-audio
```

Additional actions are additive only when they provide a distinct context workflow.

### Setup checklist

Expose user-meaningful capability packs, not internal workers:

```text
core
speech-essentials
game-audio
music
```

TTS/ASR may use separate internal runtimes while remaining one user-facing Speech Essentials setup unit.

## 6. Language boundary

UI locale, content language and voice language are separate.

```text
ui_locale         auto | ja | en
content_language  auto | ja | en initially
voice_language    voice-profile metadata
```

ControlDeck provides locale through the generic Host bridge. SonicForge owns audio-language routing and speech-quality policy.

Do not add language-specific ControlDeck routes/permissions. Do not create combinatorial Host capabilities such as `speech.asr.ja_en`.

## 7. Health versus optional capability state

Add-on/core health and optional pack availability are distinct.

Example after Speech Essentials is working:

```text
SonicForge core               available
speech.tts.synthesize         available (ja/en)
speech.asr.transcribe         available (ja/en)
speech.localization.batch     available
audio.sfx.generate            setup_required (optional pack missing)
music.generate                setup_required (optional pack missing)
```

This overall service is **available**, not degraded merely because optional Game Audio/Music have not been installed.

Use degraded/unavailable only when an expected/installed capability or core behavior is actually impaired.

## 8. Job boundary

ControlDeck Job = global durable user-visible work item.  
SonicForge worker phases = implementation detail.

Rules:

- create/attach durable ownership before significant preparation/generation;
- browser memory is never the only owner of expensive work;
- resource waiting does not consume unrelated execution slots;
- high-frequency engine telemetry stays local and is normalized to bounded Host progress;
- cancellation reaches waiting request/active worker appropriately;
- terminal Host result is bounded; large audio/transcript is an asset/reference;
- reopening/backgrounding reconnects to authoritative server/Host Job state.

## 9. Resource Broker boundary

GPU request examples may contain:

```text
resource_class
device = auto
vram_estimate_bytes
execution_mode
priority within Host ceiling
interactive
model_residency_key
```

Host derives owner from authenticated Add-on identity; SonicForge cannot forge another owner.

SonicForge owns local worker lifecycle/model residency decisions but not cross-application GPU arbitration.

If SonicForge uses ControlDeck generic AI inference for orchestration/analysis and then needs GPU locally, use the generic Host AI release/yield contract where appropriate rather than reaching into LLM process internals.

## 10. File and asset boundary

Input:

```text
Host picker/context
 -> grant:<id>
 -> Runtime grant metadata/content
 -> private SonicForge staging
```

Output:

```text
SonicForge asset
 -> Host output staging
 -> scoped commit
 -> logical project result
```

Forbidden in Host-facing payload/result metadata:

- `/home/...`
- `/share/...`
- ControlDeck project root
- repository absolute path
- symlink-derived escape path

Standalone/local internal storage never weakens the Add-on protocol boundary.

## 11. SonicForge / MediaForge relationship

No direct imports and no shared venv/database/runtime registry.

Allowed reuse:

- generic architectural patterns
- protocol vocabulary deliberately standardized
- small copied/adapted generic utilities when licensing/ownership permits
- release signing/build patterns
- Host contracts
- evidence/UX lessons

Preferred composition:

```text
ControlDeck Workflow / Agent
 -> MediaForge visual asset
 -> Host asset/grant/project context
 -> SonicForge dialogue/SFX/BGM
 -> scoped project outputs
```

No private shared-directory shortcut.

## 12. Release-signature Host compatibility rule

MediaForge has already moved its release process to an Ed25519 publisher-signed canonical manifest. The ControlDeck `main` inspected on 2026-08-25 still showed the older SHA-pin verifier path.

SonicForge therefore targets the **generic signature-aware feature provider** and treats old-Host support as a compatibility gate.

If Host work is required:

- separate ControlDeck PR;
- generic publisher-key/signature verification;
- retain capability allowlist, downgrade protection, bounded downloads, safe extraction, package identity, smoke/health and rollback;
- no `if feature_id == "sonic-forge"` verifier logic;
- do not fall back to requiring a permanent ControlDeck source change for every SonicForge release.

## 13. Host-change rule

Any ControlDeck change requires all of:

1. cannot be solved safely within the current generic contract;
2. useful for future Add-ons, not SonicForge-only;
3. documented threat model/version/backward compatibility;
4. separate ControlDeck PR;
5. SonicForge records unavailable/degraded compatibility until Host support exists rather than bypassing the boundary.

## 14. Contract compatibility policy

- reject unsupported Add-on major versions;
- validate against current Host source/schema, not copied stale examples;
- public SonicForge v1 evolution is additive by default;
- keep engine/model-native details behind capability/Expert extensions;
- never couple clients to worker process names/paths;
- signature validation and runtime capability authorization remain separate;
- contract-test Add-on manifest/runtime APIs against current ControlDeck reference/fake Add-on;
- test bilingual labels under both Host locales;
- test optional missing packs do not incorrectly degrade core service health.