# Engine and Model Strategy

Status: Evaluation baseline, not a public API commitment  
Date: 2026-08-25

## 1. Principle

Engines are replaceable adapters. Public APIs use capabilities and languages. This document defines **evaluation/adoption order**, not permanent engine coupling.

Japanese and English are first-class product languages, but they do not have to use the same ASR engine. Routing should choose the best verified language/task route rather than force architectural symmetry.

Every promoted engine must pass:

- license/terms review
- supported platform/runtime review
- clean setup install
- actual target-hardware smoke test
- language-specific quality measurement
- latency/RAM/VRAM measurement
- cancellation/recovery test
- output validation/provenance
- adapter contract test

## 2. Classification correction

**GPT-SoVITS and Style-Bert-VITS2 are TTS/voice synthesis systems, not ASR systems.**

They belong in TTS/voice worker packs. ASR uses dedicated recognition adapters.

## 3. TTS strategy

### 3.1 Qwen3-TTS — general bilingual first candidate

Upstream: https://github.com/QwenLM/Qwen3-TTS

The current official Qwen3-TTS family explicitly advertises both **Japanese and English** among ten supported major languages, 0.6B/1.7B models, streaming, CustomVoice, VoiceDesign and rapid voice cloning.

Why evaluate first:

- Japanese + English first-class engine support
- 0.6B and 1.7B families
- Base voice-clone variants
- CustomVoice and VoiceDesign variants
- natural-language voice/style control
- streaming-oriented architecture
- useful fit for both ordinary TTS and Localization Studio

Initial routing intent, subject to real measurement:

```text
fast          -> smaller measured route
balanced      -> best measured quality/latency route for language/profile
quality       -> higher-quality measured route
clone         -> Base/reference-capable route
voice-design  -> VoiceDesign route when installed
```

Do not expose these mappings as immutable API behavior.

### 3.2 Qwen bilingual acceptance

Japanese fixtures:

- kana/kanji
- numerals/units/dates
- English acronyms/product names inside Japanese
- punctuation/pauses
- proper nouns via dictionary
- emotional character dialogue
- long-form stability

English fixtures:

- conversational English
- game/UI short lines
- numbers/dates/abbreviations
- Japanese names/terms inside English
- emotional/style instructions
- long-form narration

Mixed fixtures:

- code-switching sentences
- product/character names shared across languages
- same character profile rendered in JP and EN

Measure voice consistency separately from simple intelligibility.

### 3.3 Style-Bert-VITS2 — Japanese character/style specialist

Upstream: https://github.com/litagin02/Style-Bert-VITS2  
User reference: https://github.com/souten-yd/StyleBertVITS2WithFileManager

Role:

- Japanese character voices
- style-controlled dialogue
- imported/custom Japanese voice assets
- potential CPU-capable fallback for some scenarios

Do not force it to become the English default merely because it is installed. English should route to a verified English-capable adapter.

Security rule: do not copy the reference repository's broad root/workspace file-manager assumptions. SonicForge uses scoped model libraries and non-root workers by default.

Licensing:

- upstream package/code licensing and individual voice/model terms are tracked separately
- every imported voice model carries its own license/rights state

### 3.4 GPT-SoVITS — reference/few-shot/custom voice route

Upstream: https://github.com/RVC-Boss/GPT-SoVITS  
User reference: https://github.com/souten-yd/GPTSoVITS

Use cases:

- reference/few-shot voice generation
- multilingual/custom voice workflows when locally verified
- trained model assets

Model/data/voice rights are separate from repository code licensing.

Integrate as a worker adapter; do not embed the historical deployment UI as SonicForge's product architecture.

### 3.5 TTS routing examples

| Task | Evaluation direction |
|---|---|
| general Japanese narration | Qwen3-TTS -> measured Japanese specialist fallback/profile |
| general English narration | Qwen3-TTS bilingual route -> measured English-capable alternative if better |
| bilingual same-character dialogue | Qwen voice/profile consistency first; specialist per-language routing only when consistency remains acceptable |
| low-latency preview | smallest measured acceptable route |
| expressive Japanese character dialogue | Style-Bert-VITS2 / Qwen style route |
| authorized quick voice clone | Qwen Base / GPT-SoVITS after comparison |
| custom trained character voice | adapter matching imported asset type |
| voice from description | Qwen VoiceDesign candidate |

## 4. ASR strategy

### 4.1 Do not require one model for both languages

Japanese-specialized ASR can outperform/operate more efficiently for Japanese, while a multilingual route may be better for English and mixed speech.

Speech Essentials may therefore install:

```text
Japanese-specialist ASR
+ multilingual/English-capable ASR
```

only when the disk/runtime cost is justified. If one verified multilingual route is good enough for both languages on the target hardware, the planner may choose it instead.

### 4.2 Kotoba-Whisper v2.0 — Japanese quality/speed candidate

Model: https://huggingface.co/kotoba-tech/kotoba-whisper-v2.0

Why evaluate:

- Japanese-distilled Whisper large-v3 lineage
- strong Japanese-specific deployment motivation
- Transformers ecosystem
- alternative Whisper-compatible runtimes may be possible

Evaluate real target behavior rather than copying upstream speed/accuracy claims.

### 4.3 ReazonSpeech K2/current suitable successor — Japanese CPU/efficient candidate

Upstream: https://github.com/reazon-research/ReazonSpeech  
Models: https://huggingface.co/reazon-research

Why evaluate:

- Japanese-focused project
- efficient deployment direction
- potential small always-available CPU route
- useful comparison against Kotoba for streaming/startup/resource use

Benchmark:

- Japanese CER
- real-time factor
- RAM
- startup
- timestamps/segmentation
- noisy/casual speech
- streaming suitability

### 4.4 English/multilingual ASR candidate

Evaluate a current **Whisper large-v3-turbo / faster-whisper / whisper.cpp compatible multilingual route or measured successor** for:

- English transcription
- Japanese/English mixed speech
- segment timestamps
- GPU and CPU/Vulkan/other practical backends
- long-form stability

This remains a candidate family until the exact runtime/model revision is pinned and benchmarked.

Do not use Kotoba merely for English because it shares a Whisper lineage; route by measured language quality.

### 4.5 ASR routing policy

Conceptual:

```text
Japanese fast/cpu      -> measured Reazon/efficient route if quality passes
Japanese recommended   -> measured Kotoba/current Japanese route
English recommended    -> measured multilingual English-capable route
Mixed ja/en            -> multilingual route unless segmented language routing proves better
Streaming              -> route with proven low-latency session behavior
```

Never select from marketing claims alone.

## 5. Localization engine considerations

Localization Studio values **cross-language voice consistency**, not only independent best-in-language scores.

Benchmark a bilingual voice/profile on:

- character identity similarity JP vs EN
- speaking-rate consistency
- emotional style consistency
- pronunciation of shared names
- batch stability

A slightly lower single-language quality score may be preferable when it gives materially better cross-language character consistency. Record that tradeoff in project/voice profile routing evidence.

## 6. Music strategy

### 6.1 ACE-Step 1.5 — first music candidate

Upstream: https://github.com/ace-step/ACE-Step-1.5

Initial capability evaluation:

```text
music.generate
music.variations
music.remix
music.extend
music.loop
music.stems / accompaniment when verified
```

Acceptance focus:

- instrumental game-BGM usefulness
- prompt adherence in Japanese and English prompts where applicable
- duration behavior
- loop usability
- BPM control
- coherence
- latency
- peak VRAM on target hardware
- recovery after load/unload

Do not leak engine-native LM/DiT concepts into the stable API.

## 7. SFX/audio generation strategy

### 7.1 Stable Audio 3 Small-SFX — first candidate

Upstream: https://github.com/Stability-AI/stable-audio-3

Evaluate:

- UI confirm/cancel/error packs
- impacts
- ambience
- mechanical sounds
- magic/fantasy/sci-fi cues
- loopable beds
- variation consistency
- Japanese and English prompt usability

Repository code license and distributed model license/terms remain distinct records.

### 7.2 TangoFlux — alternative evaluator

Upstream: https://github.com/declare-lab/TangoFlux

Adopt only if it measurably improves prompt fidelity, speed, hardware compatibility or a missing capability. Engine count itself is not a goal.

## 8. Deterministic audio processing

Prefer conventional tooling for:

- decoding/encoding
- resampling
- trim/silence detection
- fade
- loudness/normalization
- channel conversion
- loop point/seam analysis
- waveform/spectrogram previews

A practical implementation may use ffmpeg/ffprobe via validated argv plus Python libraries. `doctor` detects required binaries; no arbitrary shell strings.

## 9. Optional later adapters

- source separation/stems
- speech enhancement/noise reduction
- voice conversion
- singing synthesis
- video-to-audio/foley
- audio inpainting
- music personalization/LoRA

Only add when the task fits the stable capability architecture and has real use/evidence.

## 10. Engine descriptor

Example:

```json
{
  "id": "tts.qwen3",
  "version": "adapter-version",
  "state": "available",
  "capabilities": ["speech.tts.synthesize", "speech.tts.voice_clone"],
  "languages": ["ja", "en"],
  "mixed_language": true,
  "runtime_id": "...",
  "installed_models": [],
  "hardware": ["gpu"],
  "license": {
    "code": "...",
    "models": []
  }
}
```

Engine descriptors are Expert/diagnostic data. Ordinary callers consume capability descriptors.

## 11. Model catalog requirements

Every model record includes:

- internal model id
- engine id
- immutable source revision where possible
- local artifact location internally only
- digests/size
- capabilities
- tested/supported languages
- hardware/dtype requirements
- license/source/terms
- gated acceptance state
- install state
- smoke-test state
- local benchmark summary
- promotion state: experimental/supported/recommended

Unknown imported model assets remain clearly `unverified` until source/license and adapter behavior are known.

## 12. Bilingual benchmark suite

Use legally redistributable or purpose-generated fixtures.

### Japanese TTS/ASR

- kana/kanji
- Latin words/acronyms
- numbers/dates/units
- proper names
- casual/fast/noisy speech
- character emotion
- long text/audio

### English TTS/ASR

- conversational/narration
- short game barks
- abbreviations/numbers
- Japanese names inside English
- noisy/fast speech
- long-form

### Mixed

- Japanese with English technical terms
- English with Japanese names
- rapid code switching
- same localization line/character rendered in both languages

Track CER/WER/RTF where applicable and human listening notes for TTS. Automated metrics are not a substitute for listening quality.

## 13. Promotion policy

An engine becomes `recommended` for a language/task only after:

1. clean SonicForge setup succeeds;
2. license state is understood;
3. target hardware smoke test passes;
4. representative language/task benchmark exists;
5. cancellation/crash recovery are tested;
6. output validation/provenance pass;
7. UI can use it through Easy/Customize without exposing engine jargon;
8. resource estimates are measured rather than guessed when routing depends on them.

A model may be `recommended` for Japanese and only `experimental` for English, or vice versa. Promotion is capability/language-specific rather than one global badge.