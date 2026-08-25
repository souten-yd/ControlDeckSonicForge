# SonicForge Master Specification

Status: Refined architecture baseline  
Date: 2026-08-25

## 1. Product definition

SonicForge is a local-first ControlDeck Add-on dedicated to **speech, sound and music**.
It provides a single task-oriented experience and stable capability API over replaceable local engines while preserving strict process/environment isolation.

The product has five primary pillars:

1. **Japanese + English speech synthesis (TTS)**, with Japanese quality prioritized in benchmarking
2. **Japanese + English speech recognition (ASR)** and mixed-language handling
3. **game/content audio asset generation and deterministic audio processing**
4. **music/BGM generation and editing**
5. **bilingual localization workflows** for dialogue/voice assets

SonicForge is not merely an engine launcher. It owns task workflows, audio assets, provenance, voice profiles, project presets, setup/runtime management, capability routing, localization batches and ControlDeck integration.

## 2. Design principles

### 2.1 Capability first, engine second

Users and agents ask for outcomes:

- synthesize a Japanese or English line
- render the same character consistently in both languages
- clone an authorized voice/reference style
- transcribe Japanese, English or representative mixed speech
- generate a UI sound, impact, ambience or loop
- create BGM with a target mood/BPM/duration

Public APIs express outcomes. Engine/model selection is a routing decision unless explicitly pinned in Expert settings.

### 2.2 Separate process, separate environment

SonicForge is a real Add-on service and never becomes a package imported by ControlDeck.
Its core/runtime/model/data environments are SonicForge-owned and are not shared with ControlDeck or MediaForge.

### 2.3 Easy first, detail on demand

The UI uses three disclosure levels:

```text
Easy       3–5 task-level inputs and recommended defaults
Customize  common outcome controls independent of a particular engine
Expert     engine/model/seed/runtime and engine-native details
```

Expert mode must never be required for an ordinary successful job.

### 2.4 Setup is a product feature

Installing runtimes/models is not a README-only activity. SonicForge provides plan/apply/progress/cancel/repair/update from the UI and CLI, with durable state and rollback-safe activation.

The default setup is intentionally **Speech Essentials**, not every available generator. Game Audio and Music are contextual one-click optional packs.

### 2.5 Durable, reconnectable and auditable

Expensive preparation and generation are server-owned durable jobs before meaningful compute is spent. Browser navigation/backgrounding must not discard progress. Generated assets include provenance, model/license context and lineage.

### 2.6 Local-first

Version 1 targets local engines and local model storage. A future remote-provider extension must remain capability-compatible and make data egress explicit.

### 2.7 Signed publisher releases

SonicForge release authorization follows MediaForge's Ed25519 publisher-signature direction. ControlDeck trusts a publisher public key rather than requiring a new SHA pin for every release. Artifact SHA-256 remains inside the signed canonical manifest for integrity.

See `13-release-distribution-and-signing.md`.

## 3. Language model

Three distinct concepts are kept separate:

```text
ui_locale         auto | ja | en
content_language  auto | ja | en initially
voice_language    metadata/preferences on each voice profile
```

Initial first-class UI locales: Japanese and English.
Initial first-class speech content languages: Japanese and English.

Mixed Japanese/English content is supported as a product requirement. Explicit language should be used when known; auto mode is a convenience, not a guarantee that every code-switched phrase is detected correctly.

Capability metadata advertises actual installed/tested language support. Other engine-supported languages may appear later without changing the stable task APIs.

## 4. Scope

### 4.1 TTS

Required:

- Japanese and English text-to-speech
- mixed-language/code-switch representative cases
- expressive style/emotion where supported
- normalized speed/style controls
- logical voice selection
- authorized voice clone/reference workflows
- voice design where supported
- long-form chunking/concatenation
- dialogue/batch rendering
- pronunciation/terminology dictionary
- preview versus final rendering
- candidate comparison
- optional streaming/low-latency path
- WAV first; configurable export codecs through processing

### 4.2 ASR

Required:

- Japanese and English transcription
- auto/explicit language routing
- representative Japanese-English mixed speech
- file and microphone/stream input
- timestamps
- VAD/segmentation
- punctuation/normalization policy
- long audio processing
- batch transcription
- confidence/diagnostic metadata where supported
- subtitle/text export

Planned/optional:

- speaker diarization
- word/phoneme alignment
- translation as a separate capability if a suitable local route is adopted

GPT-SoVITS and Style-Bert-VITS2 are TTS/voice engines, not ASR engines.

### 4.3 Game/content audio

Required capability families:

- SFX: UI, impact, mechanical, magic/sci-fi, environment, foley-like prompts
- ambience/beds/loops
- coherent variation packs
- dialogue/voice packs
- normalization, trim/fade, resample, channel conversion
- loop metadata and seam QA
- project/export profiles
- deterministic metadata and seed recording when supported

Later:

- audio-to-audio restyle
- inpainting/region replacement
- source separation/stems
- video-to-audio/foley when a suitable adapter is verified

### 4.4 Music

Required initial direction:

- text-to-music/BGM
- duration/BPM hints when supported
- instrumental-first game BGM workflow
- loop-oriented generation
- small candidate sets
- remix/edit/extend when verified
- export + provenance + deterministic audio QA

Later:

- lyrics-to-song
- cover/reference workflows with extra rights controls
- stems/accompaniment
- personalization/LoRA lifecycle

### 4.5 Localization Studio

Required direction:

- import/enter dialogue rows with stable `line_id`
- Japanese and English text side by side
- assign character voice/profile once
- per-line language/style/context override
- preview representative lines
- durable batch render JP/EN
- optional TTS->ASR round-trip QA for omission/repetition flagging
- review only failed/flagged rows
- project profile for filenames, locale directories, output format and loudness

Localization Studio is a user workflow, not a new model-specific public protocol.

## 5. User-facing information architecture

One ControlDeck navigation contribution: **Audio**.

Inside SonicForge keep navigation small:

```text
Studio
Voices
Library
Runtime
```

Studio task tabs:

```text
Speech
Transcribe
SFX
Music
Localization
```

Quick Create is a task chooser within Studio, not another duplicate navigation destination.

Mobile can use:

```text
Studio | Library | Jobs | More
```

## 6. Primary UX patterns

### Easy

Use task presets and smart routing. Do not show model names.

### Customize

Show normalized controls that describe outcomes, such as speed, emotion strength, BPM, loop behavior, variations, quality and output profile.

### Expert

Show model/engine pins, seed, engine-native parameters, device/runtime, chunking/VAD thresholds and diagnostics.

### Preview / Render Final

Where useful, generate an inexpensive preview without overwriting the final asset. A preview is always visibly labeled.

### Candidate comparison

Subjective generation supports a bounded 2–3 candidate comparison with Play/Favorite/Use/Variation actions.

### Automatic QA

Deterministic validation is mandatory. Optional semantic/speech round-trip checks flag likely problems, but unverifiable requirements are recorded as `not_checked`, not silently passed.

## 7. Integration model

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

## 8. Relationship to MediaForge

MediaForge and SonicForge are sibling Add-ons.

Shared platform concepts:

- Add-on v2 lifecycle
- signed generic Release Bundle Features
- ControlDeck Jobs
- Resource Broker
- scoped file/project grants
- provenance patterns
- capability-driven agent/workflow integration
- setup/health UX principles
- reconnectable server-owned jobs

They do not share:

- Python virtual environments
- internal Python modules
- databases
- worker implementations
- private frontend code
- model registries
- raw filesystem paths

Cross-media composition goes through ControlDeck workflow/agent/grant contracts.

## 9. Default engine direction

Initial replaceable candidates:

- TTS general/voice clone/design: Qwen3-TTS
- TTS Japanese character/style: Style-Bert-VITS2
- TTS few-shot/reference: GPT-SoVITS
- ASR Japanese-specialist: Kotoba-Whisper v2.0 candidate
- ASR low-resource Japanese: ReazonSpeech K2 candidate
- ASR English/multilingual route: evaluate an appropriate current multilingual ASR/Whisper-family adapter; do not force a Japanese-specialized model to serve English merely for architectural uniformity
- Music: ACE-Step 1.5 candidate
- SFX/audio: Stable Audio 3 Small-SFX candidate; TangoFlux evaluation alternative

Qwen3-TTS officially advertises Japanese and English among its supported languages, so it is a strong bilingual TTS candidate; local quality/hardware evidence is still required before promotion.

See `04-engine-model-strategy.md`.

## 10. Hardware philosophy

Capability health is finer-grained than Add-on process health.

Examples:

- CPU ASR available, music GPU unavailable -> speech remains usable.
- one TTS engine cannot load -> another compatible route may remain available.
- Game Audio pack not installed -> Speech Essentials remains healthy.

Never make optional music/SFX setup a prerequisite for transcription.

## 11. Setup philosophy

Expected first use after the lightweight signed feature is installed:

```text
SonicForge opens
  -> setup_required
  -> hardware/disk/network/license preflight
  -> [音声基本環境をセットアップ / Set up Speech Essentials]
  -> SonicForge-owned TTS/ASR runtime packs
  -> required model terms/consent
  -> real smoke tests
  -> Japanese/English speech capabilities available/degraded
```

Later, entering SFX or Music offers a contextual one-click pack install.

A user who explicitly wants everything can choose **Full Studio**.

## 12. Release/install philosophy

A fresh ControlDeck should ultimately install the lightweight SonicForge feature through the same generic Release Bundle Feature model used for independently released Add-ons, with publisher-signature verification.

The signed bundle contains the lightweight product/setup orchestrator, while large ML runtimes/models remain separately provisioned by SonicForge.

The current Host/signature compatibility transition is documented in `13-release-distribution-and-signing.md`; do not solve it by adding a SonicForge arbitrary-shell exception.

## 13. Success criteria for v1

V1 is successful when a user can:

1. install/update SonicForge through the generic trusted signed feature path without contaminating other environments;
2. provision Speech Essentials from a single primary UI action;
3. synthesize useful Japanese and English speech;
4. transcribe useful Japanese and English audio and representative mixed-language cases;
5. complete normal speech/audio/music tasks without Expert settings;
6. optionally install Game Audio/Music without reinstalling Speech Essentials;
7. produce at least one useful SFX class and one useful music/BGM class;
8. navigate/background the client and return to a still-running durable job;
9. safely cancel waiting/running GPU work;
10. export through scoped project grants;
11. inspect provenance/license/voice-rights information later;
12. run a small JP/EN Localization Studio batch with consistent voice profiles and export naming;
13. use workflow/agent contributions without knowing underlying model IDs;
14. operate the main UI in Japanese or English.