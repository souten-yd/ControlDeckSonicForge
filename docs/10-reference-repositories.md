# Reference Repositories and Research Notes

Status: Reference / update before major engine adoption  
Last reviewed: 2026-08-25

## 1. Purpose

This document records repositories/specifications that informed SonicForge. Their internal APIs are **not** automatically part of SonicForge's public contract.

Before implementing against a reference, verify its current revision, license and runtime behavior again.

## 2. ControlDeck — normative Host source

Repository:

- https://github.com/souten-yd/ControlDeck

Read at minimum:

- `docs/design-addon-platform-v2.md`
- `docs/plugin-sdk.md`
- `backend/app/addons/schema.py`
- `backend/app/addon_runtime/`
- `backend/app/features/release_bundle.py`
- feature trusted catalog/release tests
- `tools/fake-addon/`
- Add-on/browser E2E tests

Important rules observed during the 2026-08-25 design pass:

- Add-on v2 is out-of-process/declarative.
- ControlDeck does not import Add-on Python/JavaScript.
- embedded views are Host-proxied/isolated.
- raw Host session credentials are not Add-on credentials.
- Runtime APIs provide scoped Jobs/resources/grants/outputs.
- Host capability values are allowlisted.
- `setup_checklist` does not grant arbitrary shell execution.
- feature distribution/install trust is separate from Add-on runtime authority.

### Current release-verifier compatibility note

The ControlDeck `main` inspected on 2026-08-25 still contained the older per-artifact SHA-pin Release Bundle verifier/catalog flow. SonicForge does not adopt that as its long-term release model; see the MediaForge signing reference below and `docs/13-release-distribution-and-signing.md`.

If current Host source changes, inspect it again rather than relying on this note.

## 3. ControlDeck MediaForge — architectural and release reference

Repository:

- https://github.com/souten-yd/ControlDeckMediaForge

Read:

- `AGENTS.md`
- `addon.json`
- `docs/controldeck-integration-plan.md`
- `docs/base-plan.md`
- environment/setup implementation docs
- `docs/implementation-status.md`
- `scripts/sign_release.py`
- release-bundle tests/scripts

Useful precedent:

- strict separation from ControlDeck core
- lightweight core versus heavy runtime environments
- Host Resource Broker
- durable server-owned jobs
- scoped file grants
- provenance/lineage
- capability-driven UI and measured model promotion
- evidence-driven development
- resilient browser reconnection/progress recovery
- clear distinction between catalog-listed, installed and actually available states

### Publisher-signature release change

Current MediaForge `scripts/sign_release.py` documents the problem with the old approach: ControlDeck pinned each release bundle's SHA-256 in its own catalog, coupling every MediaForge release to a ControlDeck edit.

The replacement is:

- Ed25519 publisher key pair;
- public key trusted by ControlDeck once;
- canonical signed manifest containing `schema_version`, `feature_id`, `version`, `platform`, `architecture`, `artifact_name`, `sha256`, `size_bytes`;
- artifact SHA-256 remains an integrity value inside the signed identity;
- downgrade rejection remains a Host policy;
- private signing key is not committed/shipped.

MediaForge v0.6.7 release history explicitly describes it as the first release verified by publisher signature rather than catalog pinning.

SonicForge adopts this direction rather than inventing another release format.

SonicForge still owns independent runtimes/data/cache. Do not import MediaForge private modules or share its venv/database.

## 4. User reference — GPTSoVITS

Repository:

- https://github.com/souten-yd/GPTSoVITS

Use as reference for prior deployment/audio tooling, not as the SonicForge application architecture.

Upstream:

- https://github.com/RVC-Boss/GPT-SoVITS

Classification:

- TTS / reference/few-shot/custom voice
- **not ASR**

Code/model/data/voice rights are tracked separately.

## 5. User reference — StyleBertVITS2WithFileManager

Repository:

- https://github.com/souten-yd/StyleBertVITS2WithFileManager

Useful historical concepts:

- `/voice` TTS integration
- model/file-management experience
- custom voice-model workflows

Security warning: broad `/workspace` file management/root-container assumptions are not copied into SonicForge. Use scoped model libraries, non-root workers and Host grants.

Upstream:

- https://github.com/litagin02/Style-Bert-VITS2

Classification:

- Japanese-oriented TTS / character/style voice
- **not ASR**

Voice/model terms may differ from code/package licensing.

## 6. Qwen3-TTS

Official repository:

- https://github.com/QwenLM/Qwen3-TTS

Current official documentation reviewed on 2026-08-25 explicitly lists **Japanese and English** among ten major supported languages and describes:

- 0.6B / 1.7B families
- Base rapid voice clone
- CustomVoice
- VoiceDesign
- streaming
- natural-language control

This makes Qwen3-TTS a strong first **bilingual** TTS candidate, but local Japanese/English/mixed quality and target-hardware performance still require measurement.

Do not treat upstream latency/quality claims as SonicForge support evidence.

## 7. Kotoba-Whisper v2.0

Model:

- https://huggingface.co/kotoba-tech/kotoba-whisper-v2.0

Classification: Japanese ASR candidate.

Why evaluate:

- Japanese-distilled Whisper large-v3 lineage
- Japanese-specific speed/accuracy motivation
- standard Transformers/Whisper ecosystem

Use upstream benchmark numbers as reference only until reproduced locally.

## 8. ReazonSpeech

Repository:

- https://github.com/reazon-research/ReazonSpeech

Models:

- https://huggingface.co/reazon-research

Classification: Japanese ASR ecosystem/candidate.

Why evaluate:

- Japanese-focused
- efficient/CPU-friendly deployment direction
- useful alternate route for always-available/streaming speech

Choose the exact current model revision only after local benchmark.

## 9. English/multilingual ASR family

Initial evaluation direction:

- a current Whisper large-v3-turbo / faster-whisper / whisper.cpp-compatible multilingual route or measured successor

Purpose:

- English ASR
- Japanese/English mixed speech
- practical CPU/GPU/Vulkan-style deployment alternatives where appropriate

Do not force Japanese-specialized Kotoba/Reazon models to become English defaults merely for implementation uniformity.

## 10. ACE-Step 1.5

Official repository:

- https://github.com/ace-step/ACE-Step-1.5

Classification: local music generation/editing candidate.

Evaluate actual target AMD/ROCm compatibility, BGM usefulness, duration/loop behavior, latency/VRAM and model terms before promotion.

## 11. Stable Audio 3

Official repository:

- https://github.com/Stability-AI/stable-audio-3

Classification: audio/SFX candidate.

Evaluate `small-sfx` or current suitable family for UI sounds, impacts, ambience, loops and variations.

Repository code license and model-weight terms are separate records.

## 12. TangoFlux

Official repository:

- https://github.com/declare-lab/TangoFlux

Classification: text-to-audio/SFX alternative candidate.

Adopt only for measured benefit/capability gap, not simply to increase engine count.

## 13. Deterministic audio processing

Prefer conventional deterministic tooling for:

- decode/probe
- resample
- trim/fade
- normalization/loudness
- codec/channel conversion
- loop analysis

`ffmpeg`/`ffprobe` are practical candidates. Invoke with validated argv, never arbitrary shell strings.

## 14. Research record required for every engine/model

Record:

```text
name/source
review date/source revision
tasks/capabilities/languages
code license
model license/terms
hardware claims
actual SonicForge hardware measurements
runtime dependencies
download/disk size
known risks
promotion by capability/language: rejected | experimental | supported | recommended
```

Do not use popularity as an adoption criterion.

## 15. Evidence vocabulary

Always distinguish:

```text
UPSTREAM CLAIM   published by upstream project/model card
SOURCE INSPECTED contract/source behavior confirmed by repository inspection
LOCAL MEASURED   reproduced by SonicForge on target hardware
NOT TESTED       not yet verified
```

Only `LOCAL MEASURED` evidence may declare a SonicForge engine recommended for a specific capability/language/hardware configuration.