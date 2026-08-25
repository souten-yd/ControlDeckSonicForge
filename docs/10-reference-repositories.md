# Reference Repositories and Research Notes

Status: Reference / update before major engine adoption  
Last reviewed: 2026-08-25

## 1. Purpose

This document records the repositories/specifications that informed SonicForge. It does **not** make their internal APIs part of the SonicForge public contract.

Before implementing against a reference, verify the current upstream revision, license and runtime behavior again.

## 2. ControlDeck — normative Host source

Repository:

- https://github.com/souten-yd/ControlDeck

Read at minimum:

- `docs/design-addon-platform-v2.md`
- `docs/plugin-sdk.md`
- `backend/app/addons/schema.py`
- `backend/app/addon_runtime/`
- `tools/fake-addon/`
- Add-on/browser E2E tests
- `backend/app/applications/` when reasoning about generic external-service lifecycle

Important current rules observed during the 2026-08-25 design pass:

- Add-on v2 is out-of-process and declarative.
- ControlDeck does not import Add-on Python/JavaScript.
- Embedded Add-on view is Host-proxied and isolated.
- Raw Host session credentials are not Add-on credentials.
- Runtime APIs provide scoped Jobs/resources/grants/outputs.
- Host capability names are allowlisted; SonicForge must not invent new values in its manifest.
- Add-on manifest/setup checklist does not grant arbitrary shell execution.

If current Host source changes, current Host source wins over copied examples in SonicForge.

## 3. ControlDeck MediaForge — architectural sibling/reference

Repository:

- https://github.com/souten-yd/ControlDeckMediaForge

Read:

- `AGENTS.md`
- `addon.json`
- `docs/controldeck-integration-plan.md`
- `docs/base-plan.md`
- `docs/implementation/mf0-0-environment.md`
- `docs/implementation-status.md`

Useful precedent:

- strict separation from ControlDeck core
- lightweight core versus heavy runtime environments
- Host Resource Broker usage
- durable jobs
- scoped file grants
- provenance/lineage
- capability-driven UI
- evidence-driven development

SonicForge intentionally differs in domain and owns its own runtime/data/cache defaults. Do not import MediaForge internal modules or share its venv/database.

## 4. User reference — GPTSoVITS

Repository:

- https://github.com/souten-yd/GPTSoVITS

Use as reference for:

- prior deployment/audio-tooling work
- user-specific operational patterns worth reviewing

Do not treat its historical container/UI topology as the SonicForge public architecture.

Upstream engine:

- https://github.com/RVC-Boss/GPT-SoVITS

Classification:

- TTS / reference/few-shot voice synthesis
- **not ASR**

License note at review time:

- upstream repository code is MIT; model/data/voice rights remain separate concerns.

## 5. User reference — StyleBertVITS2WithFileManager

Repository:

- https://github.com/souten-yd/StyleBertVITS2WithFileManager

Observed useful concepts:

- `/voice` FastAPI TTS integration
- model/file management experience
- custom voice-model workflows

Security warning:

The historical reference uses broad `/workspace` file management and root container operation. Those assumptions are **not** copied into SonicForge. SonicForge uses its own scoped model library, non-root worker default and Host grants for Host files.

Upstream:

- https://github.com/litagin02/Style-Bert-VITS2

Classification:

- Japanese-oriented TTS / style and character-voice synthesis
- **not ASR**

License note at review time:

- upstream code/package is AGPL-3.0; voice/model assets may have separate terms.

## 6. Qwen3-TTS

Official repository:

- https://github.com/QwenLM/Qwen3-TTS

Why it is the initial general TTS candidate:

- Japanese support
- multiple model sizes/families
- voice cloning
- custom voice / voice design variants
- style control
- streaming-oriented use cases

License note at review time:

- official repository/package is Apache-2.0; verify each distributed model card/revision before automated installation.

SonicForge must benchmark Japanese quality and target-hardware performance rather than inheriting upstream claims as product guarantees.

## 7. Kotoba-Whisper v2.0

Model:

- https://huggingface.co/kotoba-tech/kotoba-whisper-v2.0

Classification:

- Japanese ASR

Why evaluate:

- Japanese-distilled Whisper large-v3 lineage
- published speed/accuracy motivation
- standard Transformers ecosystem
- potential alternative runtimes in the Whisper ecosystem

License note at review time:

- model card reports Apache-2.0.

Upstream benchmark numbers are reference only until reproduced on SonicForge target hardware/data.

## 8. ReazonSpeech

Repository:

- https://github.com/reazon-research/ReazonSpeech

Model organization:

- https://huggingface.co/reazon-research

Classification:

- Japanese ASR corpus/model ecosystem

Why evaluate K2/Zipformer family:

- Japanese-first
- efficient/CPU-friendly deployment direction
- sherpa-onnx ecosystem
- Japanese/ja-en model variants

Choose the exact current model revision only after benchmarking; do not freeze a stale model name into the public API.

## 9. ACE-Step 1.5

Official repository:

- https://github.com/ace-step/ACE-Step-1.5

Classification:

- local music generation/editing candidate

Why evaluate:

- current 2026 project generation
- local deployment emphasis
- AMD/Intel/Mac/CUDA support advertised upstream
- music generation plus transform/edit-oriented capabilities

License note at review time:

- repository is MIT. Verify model weights and any bundled/optional model terms independently.

Target AMD/ROCm compatibility must be proven locally before marking recommended.

## 10. Stable Audio 3

Official repository:

- https://github.com/Stability-AI/stable-audio-3

Classification:

- audio/SFX generation candidate

Why evaluate `small-sfx` family:

- SFX-oriented model family
- lightweight/CPU-oriented deployment is documented upstream
- good fit for game/UI/ambience generation if quality passes local tests

License distinction:

- code repository license and model-weight license are not the same thing.
- model terms/license must be stored in SonicForge's model catalog and surfaced during setup/export as applicable.

## 11. TangoFlux

Official repository:

- https://github.com/declare-lab/TangoFlux

Classification:

- text-to-audio/SFX alternative candidate

Use only as an evaluation alternative until license, target platform, quality and performance are measured.

## 12. Audio processing references

SonicForge should prefer conventional deterministic audio tooling for:

- decoding/probing
- resampling
- normalization/loudness
- trim/fade
- codec conversion
- channel conversion

`ffmpeg`/`ffprobe` are practical candidates but remain external system dependencies unless SonicForge explicitly packages them. Invocation must use validated argv, never shell strings.

## 13. Research discipline

For every new engine/model considered, add a record with:

```text
name
source repository/model page
review date
source revision/tag
task/capabilities
code license
model license/terms
hardware claims
actual SonicForge hardware results
runtime dependencies
estimated/downloaded size
known risks
promotion state: rejected | experimental | supported | recommended
```

Do not use repository popularity as an adoption criterion.

## 14. Upstream versus local evidence

Always distinguish:

```text
UPSTREAM CLAIM   information published by an upstream project/model card
LOCAL MEASURED   result actually reproduced on SonicForge target hardware
NOT TESTED       not yet verified
```

Only `LOCAL MEASURED` evidence may be used to declare a SonicForge engine recommended for a specific supported hardware configuration.