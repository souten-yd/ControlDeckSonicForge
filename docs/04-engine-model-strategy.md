# Engine and Model Strategy

Status: Evaluation baseline, not a public API commitment  
Date: 2026-08-25

## 1. Principle

Engines are replaceable adapters. Public APIs use capabilities. This document defines **initial evaluation/adoption order**, not permanent engine coupling.

Every engine must pass:

- license/terms review
- supported platform/runtime review
- actual target-hardware smoke test
- latency/quality/memory measurement
- cancellation/recovery test
- output validation
- adapter contract test

## 2. Classification correction

**GPT-SoVITS and Style-Bert-VITS2 are TTS/voice synthesis systems, not ASR systems.**

They belong in the TTS worker family. SonicForge ASR uses dedicated speech-recognition engines.

## 3. TTS strategy

### 3.1 Qwen3-TTS — recommended general default

Upstream: https://github.com/QwenLM/Qwen3-TTS

Why evaluate first:

- current open Qwen TTS family released in 2026
- explicit Japanese support
- 0.6B and 1.7B families
- voice cloning through Base models
- CustomVoice and VoiceDesign variants
- natural-language style/control features
- streaming-oriented capabilities
- aligns with the TTS functionality previously used in the ControlDeck lineage

Initial SonicForge routing intent:

```text
fast       -> 0.6B family where quality is acceptable
balanced   -> engine/profile benchmark decides
quality    -> 1.7B family
clone      -> Base family
voice-design -> VoiceDesign family where installed
```

Do not expose those mappings as immutable API behavior.

Japanese-specific acceptance tests:

- kana/kanji mixed text
- numerals, units, English acronyms in Japanese sentences
- punctuation and pauses
- long sentences
- names/proper nouns via pronunciation override
- emotional dialogue
- reference-voice similarity
- repeated generation stability

### 3.2 Style-Bert-VITS2 — Japanese character/style specialist

Upstream: https://github.com/litagin02/Style-Bert-VITS2
User reference: https://github.com/souten-yd/StyleBertVITS2WithFileManager

Strengths for SonicForge:

- Japanese-oriented ecosystem / JP-Extra lineage
- controllable speaking styles
- suitable for character voices and game dialogue
- CPU inference is possible for some synthesis use cases
- API/server patterns already exist
- existing user reference repository demonstrates model-file management and `/voice` integration

Important integration rule:

The referenced custom repository's historical container/file-manager setup includes broad filesystem/root assumptions. **Do not copy that security model into SonicForge.** SonicForge provides its own scoped model library and runs workers non-root by default.

Licensing:

- upstream package metadata is AGPL-3.0
- individual voice models have their own terms/licenses
- model terms must be stored per voice/model record and surfaced before export/use when required

### 3.3 GPT-SoVITS — reference/few-shot voice workflow

Upstream: https://github.com/RVC-Boss/GPT-SoVITS
User reference: https://github.com/souten-yd/GPTSoVITS

Use cases:

- few-shot / reference-audio voice generation
- multilingual/reference workflows including Japanese
- trained/custom voice model assets

Repository code is MIT upstream, but model/data/voice rights are independent and must be tracked.

The user's reference repository contains useful audio tooling/deployment material, but SonicForge should integrate through a worker adapter rather than embedding its existing UI/container as the product surface.

### 3.4 TTS routing policy

Default routing is not "one best model". It is task based:

| Task | Preferred evaluation order |
|---|---|
| general Japanese narration | Qwen3-TTS -> Style-Bert-VITS2 fallback/profile |
| low-latency preview | benchmarked small Qwen/SBV2 path |
| expressive character dialogue | Style-Bert-VITS2 / Qwen style-capable variant |
| authorized quick voice clone | Qwen3-TTS Base / GPT-SoVITS |
| custom trained character model | Style-Bert-VITS2 / GPT-SoVITS based on asset type |
| voice-from-description | Qwen3-TTS VoiceDesign |

Actual order is chosen from measured quality/latency on supported hardware.

## 4. ASR strategy

### 4.1 Kotoba-Whisper v2.0 — preferred first quality/speed evaluation

Model: https://huggingface.co/kotoba-tech/kotoba-whisper-v2.0

Reasons:

- distilled specifically for Japanese ASR
- teacher lineage Whisper large-v3
- model card reports significant speedup while retaining low error rate
- Transformers integration
- published faster-whisper / whisper.cpp related weights or ecosystem compatibility is useful for alternative runtimes
- Apache-2.0 model card license

Evaluate:

- PyTorch/Transformers worker
- optional faster-whisper runtime if it materially improves target hardware support
- optional whisper.cpp-compatible runtime as a CPU/Vulkan path when quality parity is acceptable

### 4.2 ReazonSpeech K2 — preferred CPU/efficient alternative evaluation

Upstream: https://github.com/reazon-research/ReazonSpeech
Models: https://huggingface.co/reazon-research

Reasons:

- Japanese-focused project
- K2 ASR is described upstream as fast/accurate
- roughly 159M parameter K2 family in upstream documentation
- sherpa-onnx-based deployment path
- Japanese and Japanese-English variants exist
- promising for a smaller always-available CPU ASR pack

SonicForge should benchmark it against Kotoba-Whisper for:

- CER on representative Japanese speech
- real-time factor
- CPU RAM
- startup time
- streaming friendliness
- timestamps/segmentation quality

### 4.3 ASR fallback philosophy

The recommended installation should attempt to leave at least one Japanese transcription path usable without monopolizing GPU resources.

Potential routing:

```text
fast/cpu       -> ReazonSpeech K2 if benchmark validates quality
balanced       -> Kotoba-Whisper v2.0
quality        -> Kotoba-Whisper or future measured successor
stream         -> engine with proven low-latency streaming adapter
```

Never select by marketing description alone; store benchmark evidence.

## 5. Music strategy

### 5.1 ACE-Step 1.5 — first music engine candidate

Upstream: https://github.com/ace-step/ACE-Step-1.5

Reasons as of 2026-08-25:

- active 2026-generation project
- local music generation focus
- repository advertises AMD/Intel/Mac/CUDA support
- generation, remix/repaint/edit, reference and track-oriented capabilities
- relatively low-VRAM options are part of the project direction
- project repository license is MIT

Initial SonicForge capability mapping:

```text
music.generate
music.variations
music.remix
music.extend
music.loop
music.stems / accompaniment when verified
```

Do not expose ACE-specific LM/DiT internals through the stable API.

Acceptance focus for game BGM:

- instrumental prompt adherence
- exact/near duration behavior
- loop usability
- BPM control
- long-term coherence
- generation latency
- peak VRAM on target AMD GPU
- failure recovery after model load/unload

## 6. SFX/audio generation strategy

### 6.1 Stable Audio 3 Small-SFX — first SFX candidate

Upstream: https://github.com/Stability-AI/stable-audio-3

As of 2026, upstream exposes a `small-sfx` family intended for lightweight SFX generation, with CPU-oriented support documented by the project. This is attractive for keeping SFX available without evicting a large GPU model.

Use cases to evaluate:

- UI clicks/confirm/error packs
- impacts
- ambience
- short mechanical sounds
- magic/fantasy cues
- loopable beds
- batch variations

License caution:

- repository code is MIT
- model weights are governed by Stability AI model/community terms rather than automatically inheriting the code license
- SonicForge must store and display the actual model-license identifier/source

### 6.2 TangoFlux — alternate text-to-audio evaluator

Upstream: https://github.com/declare-lab/TangoFlux

Useful as a benchmark/alternative for text-to-audio prompt fidelity and speed. Do not adopt by default until platform, license and target-hardware behavior are measured.

## 7. Audio processing engines

Deterministic processing should prefer stable conventional tools/libraries over generative models:

- decoding/encoding
- resampling
- trim/silence detection
- fade
- normalization/loudness measurement
- channel conversion
- loop point handling
- waveform/spectrogram preview generation

A practical implementation may use ffmpeg/ffprobe through validated argv subprocesses plus Python audio libraries, but exact dependencies are implementation decisions.

System binaries must be detected by `doctor`; do not invoke arbitrary shell strings.

## 8. Optional later engine classes

Potential future adapters:

- source separation/stems
- speech enhancement/noise reduction
- voice conversion
- singing synthesis
- video-to-audio/foley
- audio inpainting
- music personalization/LoRA

Add only after the stable capability namespace can represent the task without leaking engine internals.

## 9. Engine descriptor

Each engine adapter exposes metadata like:

```json
{
  "id": "tts.qwen3",
  "version": "adapter-version",
  "state": "available",
  "capabilities": ["speech.tts.synthesize", "speech.tts.voice_clone"],
  "languages": ["ja", "en"],
  "runtime_id": "...",
  "installed_models": [],
  "hardware": ["gpu"],
  "license": {
    "code": "Apache-2.0",
    "models": []
  }
}
```

Engine descriptors are diagnostic/advanced surfaces. General callers consume capability descriptors instead.

## 10. Model catalog requirements

Every model record includes:

- stable internal model id
- engine id
- source repository/model URI
- immutable revision when possible
- local artifact location (internal only)
- hashes where practical
- size
- supported capabilities/languages
- hardware/dtype requirements
- license id and source
- gated/terms-accepted state
- install status
- smoke-test status
- benchmark summary

A bare `.pth`, `.ckpt` or `.safetensors` file with unknown origin/license should be importable only through an explicit "unverified custom model" flow and must remain visibly marked as such.

## 11. Japanese quality benchmark suite

Create a versioned local test corpus containing text/audio that is legally safe to redistribute or generated specifically for tests.

TTS categories:

- kana
- kanji
- mixed Latin/Japanese
- numerals/dates/currency/units
- punctuation/quotes
- names
- emotion/style
- long text
- short UI/character lines

ASR categories:

- clean speech
- casual speech
- fast speech
- background noise
- game/stream microphone-like input
- English terms inside Japanese
- long-form segments

Track objective metrics when meaningful and retain human listening notes as evidence, not as automated truth.

## 12. Promotion policy

An engine becomes `recommended` only after:

1. clean install succeeds through SonicForge setup;
2. license state is understood;
3. target hardware smoke test passes;
4. representative task benchmark exists;
5. cancellation and worker crash recovery are tested;
6. outputs pass validation/provenance checks;
7. UI can explain required inputs without exposing engine jargon by default.

Until then it is `experimental`.