# SonicForge Master Specification

Status: Initial architecture baseline  
Date: 2026-08-25

## 1. Product definition

SonicForge is a local-first ControlDeck Add-on dedicated to **speech, sound and music**.
It provides a single user experience and capability API over multiple replaceable local engines while preserving strict process/environment isolation.

The product has four primary pillars:

1. **Japanese-first speech synthesis (TTS)**
2. **Japanese-first speech recognition (ASR)**
3. **game/content audio asset generation and processing**
4. **music generation/editing**

SonicForge is not merely an engine launcher. It owns task-level workflows, audio asset metadata, provenance, voice profiles, presets, setup/runtime management, model routing and ControlDeck integration.

## 2. Design principles

### 2.1 Capability first, engine second

Users and agents ask for outcomes such as:

- synthesize Japanese dialogue
- clone an authorized character voice
- transcribe a Japanese recording
- generate a UI click / impact / ambience loop
- generate BGM with a target mood/BPM/duration

The public API expresses these capabilities. Engine/model selection is a routing decision unless the user explicitly pins an engine/model in advanced settings.

### 2.2 Separate process, separate environment

SonicForge is a real Add-on service and never becomes a Python package imported by ControlDeck.
Its environments are owned by SonicForge and are not shared with ControlDeck or MediaForge.

### 2.3 Simple by default

The default screen asks for the smallest useful set of inputs. Expert controls remain available through progressive disclosure.

### 2.4 Setup is a product feature

Installing Python packages and model runtimes is not a README-only activity. The lightweight SonicForge service exposes setup state and provides a one-click recommended provisioning flow with progress, resume, diagnostics and rollback safety.

### 2.5 Durable and auditable

Long work is represented as durable jobs. Generated assets carry enough provenance to identify what created them and under which engine/model/license context.

### 2.6 Local-first

Version 1 targets local engines and local model storage. Remote commercial providers are not part of the base contract. A future remote-provider extension must remain capability-compatible and explicit about data egress.

## 3. Scope

### 3.1 TTS

Required:

- Japanese text-to-speech
- expressive style/emotion control where supported
- speed/pitch/intonation controls through normalized parameters where practical
- voice selection
- voice clone/reference voice workflows
- voice design where supported
- long-form chunking and concatenation
- dialogue/batch rendering
- pronunciation dictionary / reading override
- preview versus production quality presets
- optional streaming/low-latency path
- WAV output; configurable export codecs through processing stage

### 3.2 ASR

Required:

- Japanese transcription
- file and microphone/stream input
- timestamps
- VAD/segmentation
- punctuation/normalization policy
- long audio processing
- batch transcription
- confidence/diagnostic metadata where engine supports it

Planned/optional:

- speaker diarization
- word/phoneme alignment
- bilingual Japanese/English mode
- subtitle export

GPT-SoVITS and Style-Bert-VITS2 are not ASR engines. They belong to the TTS/voice family. ASR uses dedicated Japanese ASR adapters.

### 3.3 Game/content audio asset generation

Required capability families:

- SFX: impact, UI, weapon/mechanical, magic, environment, footsteps/foley-like prompts
- ambience: beds and loops
- UI sound packs: coherent variation sets
- dialogue/voice packs
- batch variations from one brief
- loopable output and loop-point metadata
- normalization, trim/fade, resample, channel conversion
- deterministic metadata and seed recording when supported
- packaging profiles for common game/web asset layouts

Later:

- audio-to-audio restyle
- inpainting/region replacement
- source-separated stems
- procedural variation sets
- video-to-audio/foley adapters when a suitable engine is adopted

### 3.4 Music

Required initial direction:

- text-to-music
- duration/BPM/key/time-signature hints when supported
- instrumental/BGM-oriented generation
- loop-oriented generation
- remix/edit/extend when engine supports them
- multiple candidates
- export + provenance

Later:

- lyrics-to-song
- cover/reference workflows with explicit rights handling
- stems / vocal-to-BGM / accompaniment generation
- LoRA/personalization lifecycle

## 4. User-facing product modes

### Quick Create

One prompt plus task type. SonicForge chooses a recommended engine/profile.

### Speech Studio

TTS, voice library, reference voice, dialogue batch, pronunciation and long-form controls.

### Transcribe

File/mic transcription, timestamps, segmentation and export.

### Game Audio

Task-oriented presets for SFX, ambience, UI packs, dialogue packs and loops.

### Music

Generation/remix/extend/loop workflows.

### Library

Generated/imported assets, voice profiles, metadata, provenance, tags and project export.

### Settings / Runtime

Installed capabilities, engine/model packs, setup/update/repair, hardware diagnostics and advanced routing.

## 5. Integration model

```text
ControlDeck shell / Jobs / Projects / Workflows / Agents
                    |
          Add-on Contract v2
                    |
         SonicForge lightweight core
      +-------------+--------------+
      |             |              |
   TTS workers   ASR workers   Audio/Music workers
      |             |              |
      +------ SonicForge assets ---+
                    |
        scoped Host grants/outputs
```

ControlDeck owns generic host responsibilities. SonicForge owns audio-specific responsibilities. Detailed ownership is normative in `01-boundaries-and-contracts.md`.

## 6. Relationship to MediaForge

MediaForge and SonicForge are siblings, not parent/child modules.

Shared concepts may include:

- Add-on v2 lifecycle
- ControlDeck Jobs
- Resource Broker
- scoped file/project grants
- provenance vocabulary patterns
- capability-driven agent/workflow integration
- setup/health UX principles

They must not share:

- Python virtual environments
- internal Python modules
- databases
- worker implementations
- private frontend code
- model registries
- raw filesystem paths

Cross-media workflows should be orchestrated by ControlDeck workflow/agent mechanisms or stable public service contracts rather than direct internal imports.

## 7. Default engine direction

Initial preferred engine families are intentionally replaceable:

- TTS general/voice clone: Qwen3-TTS
- TTS Japanese character/style: Style-Bert-VITS2
- TTS few-shot/reference workflows: GPT-SoVITS
- ASR quality/speed default: Kotoba-Whisper v2.0 candidate
- ASR low-resource/CPU alternative: ReazonSpeech K2 candidate
- Music: ACE-Step 1.5 candidate
- SFX/audio: Stable Audio 3 Small-SFX candidate; TangoFlux as an evaluation alternative

See `04-engine-model-strategy.md`. Adoption requires actual hardware/runtime/license verification; this list is not permission to couple public schemas to these names.

## 8. Hardware philosophy

SonicForge should run in degraded form even when some GPU engines are unavailable.

Examples:

- CPU-capable ASR available, music GPU worker unavailable -> Add-on remains usable.
- Qwen TTS cannot load due to VRAM -> Style-Bert-VITS2 CPU inference may remain available.
- no compatible audio-generation runtime -> TTS/ASR still work.

Capability health is finer-grained than Add-on process health.

## 9. Setup philosophy

The expected first-use experience after the lightweight service has been registered/started is:

```text
SonicForge opens
  -> setup_required
  -> hardware/disk/network/license preflight
  -> user presses "推奨環境をセットアップ"
  -> core creates SonicForge-owned runtime packs
  -> models are downloaded only after required terms/consent
  -> smoke tests execute
  -> capabilities become available/degraded individually
```

A fully empty machine cannot safely be bootstrapped by allowing an Add-on manifest to execute arbitrary shell commands inside ControlDeck. SonicForge must not weaken that boundary. Initial service registration/start should use ControlDeck's generic external-app/service management or a separately reviewed generic bootstrap mechanism.

## 10. Success criteria for v1

V1 is successful when a user can:

1. install/register SonicForge without contaminating ControlDeck/MediaForge environments;
2. provision the recommended SonicForge runtime from the UI;
3. synthesize high-quality Japanese speech;
4. transcribe Japanese audio;
5. generate at least one useful SFX class and one useful music/BGM class;
6. see all long work in ControlDeck Jobs;
7. cancel waiting/running GPU jobs safely;
8. export generated audio to a ControlDeck project through scoped grants;
9. inspect engine/model/license/provenance metadata later;
10. use workflow and agent contributions without knowing underlying engine IDs.