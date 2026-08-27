# UX and Workflows

Status: Normative product UX baseline  
Date: 2026-08-28

## 1. UX principle

SonicForge exposes powerful speech/audio/music workflows without requiring users to understand model families, Python environments, sampling parameters or worker topology.

The product is **Japanese/English bilingual**, task-oriented and recommended-by-default.

Settings use two levels, shown as one switch in the header — the same control, in the
same place, as MediaForge:

```text
シンプル / Simple
詳細 / Advanced
```

Complexity is revealed by need, not shown all at once. Advanced reaches every public
capability, but presents it as named choices rather than raw engine knobs.

## 2. Information architecture

Single ControlDeck navigation entry:

**Audio**

Inside SonicForge:

```text
Studio
Library
Activity
Pipeline        (Advanced only)
```

Runtime setup, Voices, device pairing and diagnostics live behind the Settings entry in
the header, which is where MediaForge puts the equivalent material.

Studio task tabs:

```text
Speech
Transcribe
SFX             (includes ambience as a preset)
Music
Localization    (Advanced only)
Meeting         (Advanced only)
```

This replaces the earlier redundant pattern where Create/Speech/Transcribe/Game Audio/Music all appeared as separate top-level destinations.

Mobile target: the same navigation becomes a fixed bottom tab bar; there is no separate
mobile-only information architecture and no `More` bucket to get lost in. When setup is
still required, the Settings entry carries a visible mark, because the header state pill
is folded away at phone widths.

## 3. Localization / UI language

Primary UI locales:

```text
auto
日本語
English
```

- `auto` follows ControlDeck locale from the Host bridge.
- SonicForge override is stored server-side.
- UI locale is independent of speech content language.
- all strings use localization keys; no code-level Japanese fragment concatenation.
- errors have stable machine codes and localized display messages.
- task examples/help text also switch locale.

## 4. First launch

When lightweight core is installed but speech runtimes are absent, show `setup_required`, not a blank workspace.

Primary Japanese copy:

```text
音声基本環境をセットアップ
日本語・英語の音声合成と文字起こしに必要な環境を自動で準備します。
[ 音声基本環境をセットアップ ]
```

English:

```text
Set up Speech Essentials
Automatically prepare Japanese/English speech synthesis and transcription.
[ Set up Speech Essentials ]
```

Secondary summary:

```text
ダウンロード / Download      <estimated>
必要容量 / Disk               <estimated>
ハードウェア / Hardware        <summary>
利用可能になる機能 / Enables   <capabilities>
[ 詳細 / Details ]
```

Do not ask the user to select models/runtimes during ordinary first use.

Game Audio/Music are installed later with contextual one-button actions or by choosing Full Studio in Details.

## 5. Setup progress

Setup is a durable Host Job and survives page closure/backgrounding.

Speech Essentials user phases:

```text
1/4 環境を準備 / Preparing environment
2/4 音声合成を準備 / Preparing TTS
3/4 文字起こしを準備 / Preparing ASR
4/4 動作確認 / Verifying
```

Game Audio/Music use their own short phase sets rather than making all users watch irrelevant steps.

Technical logs are collapsed by default.

Actions:

- cancel safely
- retry failed component
- repair
- copy diagnostic summary

Do not claim success before real smoke validation.

## 6. Studio landing

Show concise intent cards:

```text
Speak text / セリフ・ナレーション
Transcribe / 文字起こし
Sound effect / 効果音
Music / BGM・音楽
Localize dialogue / 台詞ローカライズ
```

Selecting a card changes the Studio task tab; it does not create a second duplicate route/navigation item.

Recent/running work can appear below as a small section with `View all` rather than dominating creation.

## 7. Two-level settings pattern

Simple carries what the earlier Easy level carried. Advanced carries the earlier Customize
and Expert material, split into a per-task block and a shared block, so the number of
switch positions matches MediaForge without hiding anything from people who need it.

### 7.1 Simple

Show only the decisions necessary for a good result.

Speech:

```text
Text
Voice
Language: Auto
Style
[ Preview ] [ Generate ]
```

Transcribe:

```text
Audio
Language: Auto
Timestamps on/off
[ Transcribe ]
```

SFX:

```text
Description
Type preset
Length
Variations
[ Create ]
```

Music:

```text
Description
Length
BGM/Instrumental
Loop
[ Create ]
```

### 7.2 Advanced — task block

Show normalized outcome controls:

- Fast / Recommended / High quality
- speech speed
- emotion/style strength
- pronunciation dictionary
- variation count
- BPM/mood
- loop options
- output/game profile
- loudness target/profile

These should remain understandable without knowing the engine.

### 7.3 Advanced — shared block

May show:

- engine/model pin
- seed
- engine-native options
- device/runtime selection
- chunking/VAD thresholds
- detailed codec/sample settings
- model residency/resource diagnostics

These options are grouped and namespaced; they do not contaminate the stable normal
settings schema. Each is offered as a named choice where one exists — output format, sample
rate, channels, device and tempo are selects or chips, not bare numbers — so reaching a
capability never requires knowing an engine's vocabulary.

## 8. Contextual controls

A control is visible only when it is relevant and supported.

Do not show a disabled wall of controls for capabilities that the active route does not implement.

Examples:

- hide Voice Design when no installed route supports it;
- show BPM only for music engines/profile paths that accept it;
- show diarization only when installed;
- show loop tuning only when a task/profile is loop-oriented.

## 9. Speech Studio

### Simple

- text
- voice
- language `Auto / 日本語 / English`
- simple style preset when supported
- Preview / Generate

### Advanced — task block

- quality
- speed
- emotion/style strength
- pronunciation dictionary
- output profile

### Advanced — shared block

- engine/model
- detailed natural-language instruction
- pitch/intonation if meaningfully normalized
- seed/generation parameters
- chunking/long-form behavior
- sample/codec details

### Mixed language

`Auto` can support Japanese/English code switching where the route can handle it. When the target language is known, encourage explicit selection for predictable pronunciation.

## 10. Voice Library

Voice cards show:

- display name
- source: built-in / imported model / clone recipe / voice design
- preferred/supported languages
- preview
- default style/profile
- rights/consent state
- model/license warning if any

Never use a checkpoint path as the primary identity.

### Voice consistency profile

A character profile can store:

- voice identity/recipe
- preferred routing
- per-language behavior
- default style
- speed range
- pronunciation dictionary
- rights/license metadata

This keeps hundreds of dialogue lines consistent without repeating advanced settings.

## 11. Voice clone flow

1. choose/import reference through scoped picker/upload;
2. confirm necessary rights/permission;
3. optionally provide reference transcript/language;
4. choose logical voice name;
5. Preview;
6. save voice profile.

The confirmation is an auditable user statement, not legal certification by the product.

## 12. Transcribe UX

Simple:

- audio
- language Auto/Japanese/English
- timestamps toggle
- Transcribe

Advanced — task block:

- quality
- punctuation/normalization
- output: text/subtitle
- segmentation mode

Advanced — shared block:

- engine/model
- VAD/chunking thresholds
- diarization/alignment when available

Live transcription clearly shows microphone permission/state, connection, detected language when reliable, latency status and Stop.

## 13. Game Audio UX

Task presets:

```text
UI
Impact
Mechanical
Magic / Sci-Fi
Footstep / Foley-like
Environment / Ambience
Loop
Custom
```

Simple:

- description
- type
- approximate length
- 2–3 variations default
- loop yes/no when relevant

Advanced — task block:

- variation count
- intensity/mood tags
- loudness/export profile
- loop policy

Advanced — shared block:

- engine/model/seed
- model-native prompt/control options

### Sound-pack workflow

Example brief:

```text
Create matching futuristic Confirm / Cancel / Warning UI sounds.
```

One durable job can create a variation group with consistent metadata and scoped project export.

## 14. Music UX

Simple:

- description
- duration
- BGM/instrumental
- loop
- Create

Advanced — task block:

- Fast/Recommended/High quality
- BPM
- mood/style tags
- candidate count
- output profile

Advanced — shared block:

- model/engine
- key/time signature when supported
- sections/lyrics/repaint/extension options only if the capability route supports them

## 15. Preview and candidate comparison

Where useful:

```text
Preview      low-cost/shorter/faster representation, clearly labeled
Render Final production request; never overwrites preview
```

Subjective tasks can return a bounded A/B candidate strip:

```text
Play | Favorite | Use this | Variations | Details
```

Default candidate count remains small to control GPU use.

## 16. Localization Studio

Purpose: produce consistent Japanese/English dialogue assets without manually repeating voice/settings for every line.

Table columns:

```text
Line ID
Character
Japanese
English
Voice/Profile
Style/Context
Status
JP asset
EN asset
QA
```

Workflow:

```text
import CSV/JSON or edit rows
 -> assign voices by character
 -> preview representative rows
 -> batch render JP/EN as durable jobs
 -> optional round-trip QA
 -> filter flagged rows
 -> export using a Project Profile
```

Project Profile can store:

- `{line_id}_{locale}.wav` naming
- `ja/` and `en/` directory convention
- sample rate/channels
- loudness target
- preferred quality
- character -> voice mapping
- pronunciation dictionary

Do not hard-code a specific game engine's absolute path into the core contract.

## 17. Automatic QA

### Deterministic

- decode validity
- duration
- clipping/peak/loudness
- silence bounds
- sample/container consistency
- loop points/seam metric

### Speech heuristic

Optional:

```text
TTS -> ASR -> normalized text comparison
```

This can flag omitted/repeated/severely mismatched speech, but does not prove naturalness or correct emotion.

Anything not actually checked is `not_checked`.

## 18. Asset Library

Supports:

- generated/imported audio
- waveform preview
- language
- duration/format
- tags
- generation task/profile
- voice/project association
- provenance/license
- variation groups
- localization line linkage
- export/download
- regenerate/variation actions

Destructive deletion requires confirmation when referenced by lineage/voice/localization records.

## 19. Runtime screen

Default capability-oriented view:

```text
Speech Essentials    Ready
Game Audio           Not installed   [Set up]
Music                Optional        [Set up]
```

Expanded details can show:

```text
Japanese TTS         Available
English TTS          Available
Japanese ASR         Available
English ASR          Available/Degraded
```

Advanced mode's Diagnostics section reveals engine/runtime/model details.

Actions:

- setup optional pack
- update
- repair
- disable worker pack
- remove after impact/size preview
- doctor

Never present package-manager internals as the normal UI.

## 20. State vocabulary

User states stay small and distinct:

```text
Available / 利用可能
Preparing / 準備中
Waiting / 待機中
Partially available / 一部利用不可
Setup required / セットアップが必要
Unavailable / 利用不可
Failed / 失敗
```

Catalog/install/runtime terms must not be collapsed:

```text
Listed in catalog
Installed on this device
Available for routing
Loaded in memory
Running now
Recommended / Experimental
```

Every unavailable state answers what, why, and next action.

## 21. Resource wait UX

Example:

```text
GPUを待っています / Waiting for GPU
別のAI処理がGPUを使用中です。順番が来ると自動で開始します。
Another AI task is using the GPU. This will start automatically when resources are available.
```

Never fake time remaining. Show queue information only when reliable.

Actions:

- Cancel
- use a faster/lower-resource alternative only when routing can genuinely offer one

Queued cancellation should settle immediately if nothing has started and there is no work to unwind; running cancellation is handled by the owning worker/job.

## 22. Durable progress and reconnection

Expensive preparation belongs in the server-owned job, not browser memory.

On boot/visibility return:

- inspect active job state
- replace dead WebSocket/session connections
- reconnect with bounded backoff
- restore progress/result display
- avoid polling while push is healthy

Closing/reopening a mobile browser must not create a permanently blank Studio or lose a generation that is still running.

## 23. ControlDeck Jobs

Examples:

```text
Speech — Character A — Japanese
Speech — Character A — English
Transcribe — meeting.wav
Localize dialogue — 48 lines
Generate SFX pack — Futuristic UI
Generate BGM — Cyberpunk Exploration
Set up Speech Essentials
```

ControlDeck Job is the canonical global status; SonicForge provides richer detail/deep links.

## 24. Project integration

From Project Lab/context actions users/agents can:

- transcribe selected audio
- open in SonicForge
- generate/replace audio for current project
- export a chosen asset or localization pack

Host supplies opaque grants/logical destination information; SonicForge never learns raw project paths.

## 25. Workflow/agent UX

Show task-level names:

```text
Synthesize Speech
Transcribe Audio
Generate Audio
Generate Music
```

Keep the stable executor set small. Model pinning belongs to optional fields and Advanced-mode policy.

Unavailable saved nodes remain visible with an actionable reason; do not delete them.

## 26. Theme and iframe rules

- wait for Host theme/locale/safe-area handshake where needed
- react without reload
- no Host cookie assumptions
- no shared-origin localStorage dependency
- important state is server-side
- route synchronization through Host bridge
- prompt disable/drain handling

## 27. Accessibility and mobile

- keyboard-accessible actions
- visible focus
- localized accessible labels
- status not color-only
- playback never unexpectedly autoplays
- explicit play/stop/volume controls
- labels avoid wrapping into unusable vertical text at supported mobile widths
- compact visual abbreviations preserve `aria-label`/title meaning
- one dominant primary action per task view

## 28. Copy policy

Japanese and English are equal product UI locales.

Model/vendor jargon stays in Advanced mode and Diagnostics unless required for license/source attribution.