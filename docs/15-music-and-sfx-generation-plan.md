# Music and SFX Generation Plan

Status: Normative implementation plan; model promotion remains evidence-based  
Research snapshot: 2026-08-25

This document refines the shorter Music/SFX sections in `04-engine-model-strategy.md` and `09-roadmap.md`. Where this document is more specific, it is the implementation plan for SF4/SF5. It does **not** make an untested model/hardware route `recommended`.

## 1. Product goal

SonicForge should make local game audio creation feel like one product even though music and sound effects use different model families.

Normal users choose outcomes:

```text
SFX:   description + duration + variations + optional loop
Music: description + duration + instrumental/lyrics + optional BPM/loop
```

They should not need to understand DiT, LM planners, CFG, ROCm wheels, model repositories or inference-step counts. Those remain routing/runtime details and Expert diagnostics.

The stable public contract remains task/capability based:

```text
audio.sfx.generate
audio.ambience.generate
audio.processing.*
audio.qa.*
music.generate
music.variations
music.remix       only after verified
music.extend      only after verified
music.loop        product workflow, not necessarily a native-model primitive
```

## 2. Research conclusions

### 2.1 Stable Audio 3 Small-SFX — primary Game Audio engine

Official sources:

- https://github.com/Stability-AI/stable-audio-3
- https://huggingface.co/stabilityai/stable-audio-3-small-sfx
- https://stability.ai/news-updates/meet-stable-audio-3-the-model-family-built-for-artistic-experimentation-with-open-weight-models

Observed upstream properties:

- dedicated sound-effects checkpoint;
- official Stable Audio 3 repo classifies Small-SFX as a CPU model and says no GPU is required;
- up to 120 seconds in the current official implementation;
- 44.1 kHz stereo output;
- text-to-audio plus architecture-level support for audio-to-audio, inpainting and continuation;
- Small-SFX is open-weight but gated behind Stability terms;
- model is trained on English descriptions and upstream warns other prompt languages underperform;
- Stability Community License currently allows research/non-commercial use and commercial use under its stated revenue conditions; enterprise use has separate licensing.

Decision:

**Adopt Small-SFX as the default Game Audio baseline, CPU-first.** Do not require a GPU lease for the normal Small-SFX path. Do not claim AMD/ROCm acceleration merely because ROCm PyTorch exposes a CUDA-compatible API namespace.

Why:

- purpose-built for the task;
- low operational friction;
- CPU path makes Game Audio usable even while the GPU is occupied by speech/music/image workloads;
- avoids making Resource Broker admission the normal SFX latency bottleneck;
- official support story is clearer than speculative ROCm acceleration.

### 2.2 Stable Audio 3 Small-Music — CPU music fallback

Official source:

- https://github.com/Stability-AI/stable-audio-3
- https://huggingface.co/stabilityai/stable-audio-3-small-music

Observed upstream properties:

- dedicated lightweight music checkpoint;
- CPU-first according to the official repository;
- up to 120 seconds;
- same 44.1 kHz stereo Stable Audio 3 family;
- useful when no suitable GPU route is available or the Resource Broker should not block a short BGM preview.

Decision:

**Add as an optional CPU fallback inside the Music pack, not the primary music model.** It shares the Stability license/terms gate with Small-SFX and must not silently install before terms are accepted.

### 2.3 Stable Audio 3 Medium — quality comparator, not AMD default

Upstream currently describes Medium as a GPU/CUDA model and reports higher musicality/longer duration than Small.

Decision:

- keep it in the model catalog as an evaluation candidate;
- do not make it a default AMD route;
- enable only on hardware/backend combinations actually validated by SonicForge;
- do not use its availability as a reason to merge Game Audio and Music runtimes.

### 2.4 ACE-Step 1.5 — primary Music engine

Official sources:

- https://github.com/ace-step/ACE-Step-1.5
- https://huggingface.co/ACE-Step/Ace-Step1.5
- https://huggingface.co/docs/diffusers/api/pipelines/ace_step

Observed upstream properties:

- MIT-licensed project/model distribution according to the official model card;
- music generation from roughly 10 seconds to 10 minutes;
- 48 kHz stereo in the Diffusers integration;
- lyrics in 50+ languages including Japanese and English;
- Turbo/Base/SFT model families plus newer XL variants;
- reference audio, cover, repaint/edit and completion capabilities in the upstream project;
- metadata controls include BPM, key/scale and time signature;
- official installation docs explicitly support CUDA, ROCm/AMD, Intel XPU, MPS and CPU;
- official ROCm docs include Linux and Windows paths and RDNA-family troubleshooting;
- upstream states approximately >=4 GB VRAM for DiT-only and >=6 GB for LM+DiT baseline operation, while XL models have materially higher requirements.

Decision:

**ACE-Step 1.5 is the primary Music engine.** Standard v1.5 Turbo is the first route to validate. XL variants remain `experimental` until measured memory, generation latency and quality justify promotion.

Important wording:

```text
upstream-supported on ROCm != SonicForge target-hardware validated
```

The implementation status must say the former without pretending the latter has already passed.

### 2.5 TangoFlux — research-only SFX comparator

Official sources:

- https://github.com/declare-lab/TangoFlux
- https://huggingface.co/declare-lab/TangoFlux

Observed strengths:

- 515M text-to-audio model;
- up to 30 seconds, 44.1 kHz;
- strong prompt/event-order alignment in its published evaluation;
- relatively fast inference for a diffusion/flow TTA system.

Blocking issue:

The published checkpoint is explicitly described as **non-commercial research use only** and inherits additional dataset/license restrictions.

Decision:

- do not ship TangoFlux in the default Game Audio pack;
- do not automatically download it;
- allow a future opt-in `research-only` adapter only if there is a real benchmark need;
- never silently route commercial/project generation to it.

### 2.6 AudioGen / MusicGen / AudioLDM2 — benchmark-only legacy candidates

AudioCraft code is MIT, but the published AudioGen/MusicGen model weights are CC-BY-NC 4.0. AudioLDM2 Large is published under CC-BY-NC-SA 4.0.

Decision:

They may be useful as benchmark references, but are not default SonicForge production engines because their weight licenses are more restrictive for game/product workflows and there is no demonstrated runtime/quality advantage that outweighs the newer candidates above.

## 3. Final engine matrix

| Capability | Default | Fallback / alternate | State before measurement |
|---|---|---|---|
| short SFX | Stable Audio 3 Small-SFX CPU | none by default | implemented adapter / target test required |
| ambience | Stable Audio 3 Small-SFX CPU | later SA3 inpaint/continue | target test required |
| SFX variation | Small-SFX repeated seeded candidates | later native/edit route | target test required |
| short CPU BGM | Stable Audio 3 Small-Music | ACE-Step CPU only if practical | planned |
| normal local BGM | ACE-Step 1.5 Turbo | Small-Music CPU fallback | upstream ROCm-supported / target test required |
| high-quality BGM | ACE-Step standard/XL route selected by benchmark | Stable Audio 3 Medium on validated backend | experimental |
| lyrics/song | ACE-Step 1.5 | none in v1 baseline | experimental until rights/UX tests |
| cover/reference music | ACE-Step | none | later experimental |
| SFX research comparator | none | TangoFlux opt-in | research-only, not production |

Engine count is not a quality metric. A second engine is added only for a measurable capability, quality, hardware or licensing reason.

## 4. Runtime ownership and isolation

### 4.1 Game Audio runtime

Default runtime family:

```text
game-audio-cpu
  Stable Audio 3 library
  Small-SFX
  optional Small-Music shared only if dependency fingerprint is identical
  soundfile / deterministic audio helpers
```

Rules:

- CPU is the supported baseline;
- no Resource Broker lease for CPU inference;
- the worker may use bounded CPU concurrency, but default concurrency starts at 1 until measured;
- model is loaded lazily and can be unloaded after idle timeout;
- gated model terms are recorded as an explicit setup acceptance event;
- Hugging Face access token, if needed for gated download, is never written into job/provenance output.

### 4.2 Music ROCm runtime

Default accelerated runtime family:

```text
music-acestep-rocm
  ACE-Step pinned source revision
  ROCm-compatible PyTorch family
  ACE-Step dependencies
  standard v1.5 Turbo DiT
  selected LM planner (initial evaluation: 0.6B vs 1.7B)
```

Rules:

- separate from speech and Game Audio even if both happen to use PyTorch;
- source revision, torch build, ROCm build and lock hash form the runtime fingerprint;
- do not mutate a working runtime in place when ACE-Step upgrades require incompatible dependencies;
- provision a new runtime version, smoke it, then atomically activate it;
- preserve the previous working runtime for rollback;
- `doctor` reports upstream-supported vs locally-smoke-tested vs benchmarked separately.

### 4.3 CPU music fallback runtime

Prefer reusing `game-audio-cpu` for Stable Audio 3 Small-Music only when the exact dependency fingerprint is compatible. Otherwise provision a separate `music-stable3-cpu` runtime. Shared runtime is an optimization, not an architectural requirement.

## 5. Prompt-language architecture

Sound-effect generation has no spoken output language, so do not misuse `content_language` as if an SFX itself were Japanese or English.

Track three concepts:

```text
ui_locale                 ja | en
user_prompt_language      auto | ja | en
engine_conditioning_lang  e.g. en for Stable Audio 3
```

Stable Audio 3 is trained on English descriptions. Therefore Japanese UX needs an explicit normalization stage:

```text
Japanese user description
 -> PromptNormalizer
 -> concise English acoustic description
 -> Small-SFX
```

Provenance stores both:

```json
{
  "user_prompt": "古い木の扉がゆっくり軋んで開く",
  "user_prompt_language": "ja",
  "engine_prompt": "an old wooden door slowly creaks open",
  "engine_prompt_language": "en",
  "normalizer": "..."
}
```

Prompt normalization must be replaceable:

1. English input: no-op except safe normalization;
2. Japanese input: generic ControlDeck `ai.inference` rewrite when granted/available, or a later SonicForge-local lightweight translator;
3. no translator available: do not pretend the engine is Japanese-native; expose a clear limitation and allow Expert direct prompting.

The normalizer is text assistance, not the audio transport or GPU scheduler. Audio generation remains owned by SonicForge.

For ACE-Step, preserve Japanese/English lyrics verbatim. Caption/query rewriting may use ACE-Step's own planner where supported, but the original user request is retained for provenance.

## 6. Stable API and internal request model

Public request stays outcome-oriented.

### SFX

```json
{
  "task": "audio.sfx.generate",
  "input": {
    "prompt": "heavy sci-fi door closing",
    "duration_sec": 2.5,
    "loop": false,
    "variations": 3
  },
  "quality": "balanced",
  "seed": null
}
```

### Music

```json
{
  "task": "music.generate",
  "input": {
    "prompt": "energetic cyberpunk battle BGM",
    "duration_sec": 90,
    "instrumental": true,
    "bpm": 145,
    "loop": true,
    "variations": 2
  },
  "quality": "balanced",
  "seed": null
}
```

Do not put these in the stable top-level schema until needed:

- DiT shift;
- raw CFG/APG values;
- LM backend implementation;
- model checkpoint path;
- inference-step count;
- torch dtype;
- ROCm architecture overrides.

They belong in Expert routing/engine-native extension data.

## 7. Routing policy

Routing is evidence-driven and stored as policy, not hard-coded forever.

### 7.1 Game Audio

Initial policy:

```text
small SFX / UI / impact / Foley
  -> Stable Audio 3 Small-SFX CPU

ambience <= 120 sec
  -> Stable Audio 3 Small-SFX CPU

edit/inpaint/continuation
  -> unavailable until separately tested, then same family

research comparison
  -> explicit research-only engine pin only
```

### 7.2 Music

Initial evaluation policy:

```text
Fast
  -> ACE-Step standard Turbo, smallest acceptable planner route

Recommended
  -> ACE-Step standard Turbo + planner selected by quality/latency benchmark

High quality
  -> standard SFT/Base or XL only when measured advantage justifies latency/memory

CPU/no compatible GPU
  -> Stable Audio 3 Small-Music for supported durations and workflows
```

Do not promote XL merely because it is larger. Human preference and structural coherence must show a real benefit.

## 8. Resource Broker policy

### Small-SFX / Small-Music CPU

- no GPU lease;
- report CPU/RAM estimates in SonicForge diagnostics;
- queue internally if CPU concurrency limit is reached;
- do not starve ControlDeck core with unbounded workers.

### ACE-Step ROCm

A Host Job requests a GPU lease before model load or substantial GPU allocation.

Measure and later replace provisional estimates for:

- resident model VRAM;
- cold-load peak;
- generation peak by duration/model/planner;
- safe concurrency;
- idle residency value.

Initial policy is exclusive-preferred and concurrency 1. Only measured safe concurrency may increase it.

If a long music job is queued, its durable Job survives browser closure. Cancellation must terminate the worker process group and release the lease.

## 9. UX plan

### 9.1 SFX Studio

Easy:

- description;
- duration presets: One-shot / Short / Ambience;
- 1 or 3 variations;
- Generate.

Customize:

- exact duration;
- loop request;
- intensity;
- variation count;
- output profile (game/UI/ambience);
- trim/fade/loudness target.

Expert:

- engine/model pin;
- seed;
- direct engine prompt;
- inference steps if the adapter exposes them;
- device/runtime diagnostics.

### 9.2 Music Studio

Easy:

- description;
- duration;
- Instrumental / Lyrics;
- Generate.

Customize:

- BPM;
- mood/energy;
- loop;
- candidate count;
- key/time signature only where verified;
- output loudness/profile.

Expert:

- ACE-Step model/planner selection;
- seed;
- native metadata controls;
- reference/cover/repaint controls only after capability promotion;
- runtime/backend diagnostics.

Use Preview -> Render Final for expensive long-form music. A preview is a separate asset and never silently overwrites final output.

## 10. Candidate generation and selection

Subjective audio benefits from small bounded candidate sets.

Default:

```text
Easy:      1 candidate
Customize: 2-3 candidates
Expert:    bounded explicit count
```

Do not generate 8+ candidates by default merely because upstream supports batching.

Each candidate belongs to a `variation_group` with:

- common request hash;
- seed;
- engine/model revision;
- prompt/normalized prompt;
- duration;
- QA result;
- user favorite/selected state.

Automatic scoring can rank or flag, but never replaces listening for final selection.

## 11. Deterministic post-processing and QA

All generated audio passes deterministic validation before it becomes a valid asset.

Required checks:

- file decodes;
- sample rate/channels recorded;
- duration within tolerance;
- NaN/Inf rejection;
- clipping/peak analysis;
- long silence detection;
- DC-offset sanity;
- SHA-256 and size;
- optional loudness measurement.

SFX-specific:

- leading/trailing silence trim recommendation;
- one-shot tail preservation;
- loop seam delta/correlation check when loop requested;
- avoid claiming semantic prompt correctness from signal metrics.

Music-specific:

- duration tolerance;
- silence/dropout segments;
- clipping;
- loop seam check;
- optional BPM/key estimate only as measured metadata, not proof of prompt adherence.

Semantic/human quality remains either human-reviewed or `not_checked` unless a dedicated validated scorer exists.

## 12. Loop workflow

`loop=true` is a SonicForge workflow requirement, not an assumption that every model natively creates seamless loops.

Pipeline:

```text
generate slightly longer source
 -> detect usable loop region
 -> seam analysis
 -> optional crossfade / zero-crossing adjustment
 -> re-check duration/loudness
 -> export loop metadata
```

Keep the original generation as lineage. A processed loop is a derived asset.

For music, native continuation/repaint may later improve loop construction, but deterministic processing remains the fallback.

## 13. Licensing and provenance gates

Every installed model records:

- repository/source URL;
- immutable revision when possible;
- model id;
- artifact digest/size;
- code license;
- model/weights license;
- gated terms accepted timestamp/version;
- commercial-use classification used by SonicForge;
- source/training-data notes when upstream provides them.

Rules:

- Stability models require explicit terms acceptance during setup;
- never infer that MIT code implies MIT model weights;
- TangoFlux/AudioGen/MusicGen/AudioLDM2 restricted checkpoints must not be silently selected for normal production output;
- generated-asset provenance records the exact engine/model/license record used at generation time.

## 14. Benchmark plan

Benchmark on actual supported hardware. Upstream numbers are context only.

### 14.1 SFX fixture bank

At least:

- UI confirm/cancel/error;
- metallic impact;
- wooden door/creak;
- footsteps on 3 surfaces;
- engine/mechanical loop;
- wind/rain/fire ambience;
- sci-fi charge/laser;
- fantasy magic spell;
- explosion;
- multi-event ordered prompt.

For Japanese, run the same semantic fixture through the prompt normalization path and compare against the English original.

Record:

- cold/warm latency;
- real-time factor;
- RAM;
- CPU utilization;
- disk/model size;
- prompt adherence listening score;
- realism listening score;
- transient quality;
- event order;
- loop usability;
- failure rate.

### 14.2 Music fixture bank

At least:

- 30s battle BGM;
- 60s calm exploration BGM;
- 90s cyberpunk loop;
- orchestral boss theme;
- ambient/drone;
- chiptune/electronic;
- Japanese lyric sample;
- English lyric sample;
- instrumental with specified BPM;
- reference/cover case only after capability is enabled.

Record:

- cold/warm latency;
- VRAM/RAM peak;
- generation-time ratio;
- structural coherence;
- prompt/style adherence;
- melody/rhythm stability;
- BPM adherence;
- lyric intelligibility/alignment where applicable;
- loop usability;
- candidate diversity;
- crash/cancel recovery.

### 14.3 Promotion score

Do not collapse everything into one opaque score. Maintain dimensions:

```text
quality
prompt_adherence
structure
speed
memory
reliability
license_fit
hardware_fit
```

A route becomes `recommended` only when all mandatory gates pass; superior quality cannot compensate for a license or reliability failure.

## 15. Implementation slices

### SF4-A — Game Audio production baseline

- pin Stable Audio 3 library/source revision;
- pin Small-SFX model metadata;
- setup terms gate;
- CPU runtime smoke;
- generate 1 valid WAV;
- cancellation/process cleanup;
- deterministic QA;
- asset/provenance;
- SFX Studio Easy path.

Acceptance: 10-fixture smoke bank, no GPU required, clean setup/repair/uninstall.

### SF4-B — Japanese prompt normalization

- `PromptNormalizer` interface;
- English no-op path;
- Japanese rewrite path;
- provenance with original + engine prompt;
- failure/degraded behavior;
- semantic fixture comparison.

Acceptance: Japanese UI can create useful SFX without falsely advertising native Japanese conditioning.

### SF4-C — Variations, ambience and loops

- variation groups;
- 2-3 candidate UI;
- ambience presets;
- loop processing/seam QA;
- project export profiles.

### SF4-D — Editing capabilities

Only after upstream/target tests:

- audio-to-audio;
- continuation;
- inpainting.

Advertise each capability separately.

### SF5-A — ACE-Step ROCm baseline

- replace speculative dependency guesses with a pinned, reproducible ACE-Step source/runtime lock;
- preserve a dedicated ROCm runtime;
- run upstream GPU diagnostic during setup smoke without changing drivers;
- standard v1.5 Turbo first;
- compare 0.6B vs 1.7B planner;
- 30/60/90 second instrumental fixtures;
- Host Resource Broker lifecycle;
- cancel/release/idle unload;
- provenance/QA.

Acceptance: target-hardware smoke and measured memory/latency before `supported`.

### SF5-B — Music routing and CPU fallback

- add Stable Audio 3 Small-Music optional model;
- choose GPU ACE-Step vs CPU Small-Music by capability/hardware/job pressure;
- never silently substitute a route whose feature set differs materially;
- expose the chosen route in diagnostics/provenance, not normal UI.

### SF5-C — BGM/loop production workflow

- Easy/Customize/Expert UI;
- preview -> final;
- bounded candidates;
- BPM/duration;
- deterministic loop builder;
- project export.

### SF5-D — Lyrics and advanced ACE-Step

After baseline:

- JP/EN lyrics;
- lyric timestamps if verified;
- reference audio;
- cover;
- repaint/extend;
- stems/extract;
- LoRA/personalization.

Each requires a separate rights/quality/capability promotion gate.

### SF5-E — XL evaluation

Compare standard v1.5 vs XL on identical fixtures. Promote XL only when the measured quality gain is worth its extra memory/load/storage cost on a supported machine.

## 16. Setup UX

Game Audio plan screen shows:

```text
Stable Audio 3 Small-SFX
CPU runtime
model download size
Stability/Gemma terms requiring acceptance
expected capability: SFX / ambience
```

Music plan screen shows detected routes, for example:

```text
Recommended: ACE-Step 1.5 Turbo on compatible GPU
Fallback:    Stable Audio 3 Small-Music on CPU
Optional:    higher-quality experimental route after benchmark
```

SonicForge must never install drivers, kernel packages or system ROCm silently. If the existing accelerator stack is incompatible, show a diagnostic and keep CPU-capable functionality available.

## 17. Current implementation interpretation

Code already exists for:

- Stable Audio 3 Small-SFX worker;
- ACE-Step 1.5 worker;
- optional pack setup;
- durable generation Jobs;
- Resource Broker lifecycle;
- output assets/provenance.

That is an **implementation baseline**, not model validation.

Research changes the status wording as follows:

- Small-SFX CPU: matches upstream-supported architecture, still needs SonicForge target test;
- ACE-Step ROCm: upstream explicitly supports ROCm/AMD, so it is no longer an unknown upstream capability; SonicForge target compatibility/performance remains NOT TESTED;
- TangoFlux: remove from production fallback planning because of non-commercial checkpoint terms;
- Stable Audio 3 Small-Music: add to Music planning as CPU fallback;
- Stable Audio 3 Medium: do not default on AMD because official support currently says CUDA GPU.

## 18. Release gates

Game Audio cannot be called production-ready until:

1. gated terms setup works end-to-end;
2. Small-SFX CPU model actually loads and generates on a supported target;
3. SFX fixture bank is reviewed;
4. cancel/restart/repair passes;
5. Japanese prompt normalization path is validated;
6. deterministic QA and export pass.

Music cannot be called production-ready until:

1. ACE-Step pinned runtime reproduces cleanly;
2. actual ROCm target smoke succeeds;
3. GPU lease lifecycle is tested;
4. 30/60/90s fixture quality and memory are measured;
5. cancellation releases GPU/resources;
6. CPU fallback behavior is explicit;
7. loop/export workflow is validated;
8. license/provenance records are complete.

Until then the UI may expose experimental capabilities, but must label them accordingly.
