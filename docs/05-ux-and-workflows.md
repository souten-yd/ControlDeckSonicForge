# UX and Workflows

Status: Normative product UX baseline  
Date: 2026-08-25

## 1. UX principle

SonicForge should expose powerful audio tooling without requiring the user to understand model families, Python environments, sampling parameters or worker topology.

The default experience is task-oriented and uses recommended settings. Advanced settings remain reachable, but are not presented as the first decision.

## 2. Primary navigation

Single ControlDeck navigation entry:

**Audio**

Inside SonicForge:

```text
Create
Speech
Transcribe
Game Audio
Music
Library
Runtime & Settings
```

On narrow/mobile layouts use a compact/companion layout. Do not force a desktop multicolumn audio workstation into 320 px.

## 3. First launch

### 3.1 Lightweight core available, heavy environment absent

The main view renders `setup_required`, not a blank page.

Primary card:

```text
SonicForge をセットアップ
日本語音声合成・文字起こし・効果音・音楽生成に必要な環境を自動で準備します。
[ 推奨環境をセットアップ ]
```

Secondary:

```text
予定: <components>
ダウンロード: <estimated>
必要容量: <estimated>
検出ハードウェア: <summary>
[詳細を見る]
```

Advanced choices are hidden until requested.

### 3.2 Preflight blockers

Examples:

- insufficient disk -> show required/free amount and destination settings
- missing supported Python -> show exact requirement
- GPU runtime unsupported -> offer CPU-capable subset if useful
- gated model -> show terms step; never auto-accept
- network unavailable -> explain which already-installed capabilities remain usable

## 4. Setup progress

Setup runs as a durable job. Closing the browser does not lose it.

Show human phases, not package-manager noise:

```text
1/5 環境を準備
2/5 音声合成を導入
3/5 日本語文字起こしを導入
4/5 効果音/音楽モデルを準備
5/5 動作確認
```

Expandable technical log is available for diagnosis.

Actions:

- cancel when safe
- retry failed component
- copy diagnostic summary

Do not claim setup success until smoke tests complete.

## 5. Create home

The first screen favors intent cards:

- セリフ・ナレーション
- 音声から文字起こし
- 効果音を作る
- 環境音・ループを作る
- BGM・音楽を作る

A prompt box may also accept natural-language intent and route to a task.

Recent assets/jobs appear below but should not dominate first use.

## 6. Speech Studio

### Simple mode

Required visible controls:

- text
- voice
- style preset when supported
- quality: fast / balanced / quality
- generate button

Optional compact controls:

- speed
- emotion/style strength

### Advanced mode

May reveal:

- engine/model pin
- detailed style instruction
- pitch/intonation parameters
- seed/generation options
- chunking/long-form policy
- output sample settings

Only show controls supported by the selected/auto-routed capability.

### Voice Library

Voice cards show:

- user-facing name
- source type: built-in / clone recipe / trained model / voice design
- language
- engine compatibility
- rights/consent state
- model/license warning if any
- preview action

Raw checkpoint paths are never shown as the primary identity.

## 7. Voice clone flow

Voice cloning is explicit, not hidden inside ordinary generation.

Flow:

1. select/import reference audio through scoped picker/upload
2. confirm the user has the necessary rights/permission
3. optionally provide/reference transcript
4. choose voice name
5. preview
6. save logical voice profile

Store consent/rights metadata. Do not imply that software can determine legal ownership automatically.

## 8. Transcribe UX

Simple mode:

- drop/select audio
- Japanese selected/recommended automatically
- `文字起こし` button
- transcript editor/view
- timestamp toggle
- export text/subtitle when supported

Advanced:

- engine pin
- Japanese/English mode
- VAD/segmentation
- chunking
- punctuation/normalization
- diarization/alignment when installed

For live transcription, show microphone state, latency/connection state and stop control clearly.

## 9. Game Audio UX

Use task presets rather than generic prompt-only generation.

Initial categories:

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

Simple inputs:

- description
- approximate duration
- number of variations
- loop yes/no where meaningful

Preset output policies may normalize loudness, trim silence and name variations consistently.

### Pack generation

Example:

```text
"近未来UIの決定/キャンセル/警告を同じ世界観で"
```

SonicForge creates a variation group with coherent metadata and can package it into project-relative directories only via Host output grant.

## 10. Music UX

Simple mode:

- description
- instrumental/BGM toggle
- duration
- loop toggle
- quality

Useful optional controls:

- BPM
- mood/style tags

Advanced engine-specific capabilities such as key, sections, lyrics, cover/repaint or stems appear only when capability metadata says they are supported.

## 11. Asset Library

Library supports:

- generated/imported audio
- waveform preview
- duration/format
- tags
- generation task/profile
- voice association
- project association (logical)
- provenance/license info
- variation groups
- export/download
- regenerate/variation actions

Destructive deletion requires confirmation when the asset is referenced by another SonicForge asset/voice/provenance record.

## 12. Runtime & Settings

Default screen is capability-oriented:

```text
日本語音声合成       利用可能
日本語文字起こし     利用可能
効果音生成           未導入      [導入]
音楽生成             更新あり    [更新]
```

Advanced section reveals engine/runtime details.

Actions:

- install recommended
- install optional component
- update
- repair
- disable worker pack
- remove model/runtime after impact/size preview
- doctor

Never present a wall of pip packages as the normal settings UI.

## 13. State language

User-facing states are intentionally small:

```text
利用可能
準備中
待機中
一部利用不可
セットアップが必要
停止中/利用不可
失敗
```

Internal detailed states remain in diagnostics.

Every non-available state should answer:

1. what is happening?
2. why?
3. what can the user do?

## 14. Resource wait UX

When waiting for GPU:

```text
GPUを待っています
別のAI処理がGPUを使用中です。順番が来ると自動で開始します。
```

Show queue/wait information only when Host provides reliable data. Never fake countdown times.

Actions:

- cancel
- lower-quality/faster alternative when routing can safely offer one

## 15. ControlDeck Jobs integration

Each durable operation deep-links to SonicForge detail.

Examples:

```text
Japanese TTS — Character A
Transcribe — meeting.wav
Generate SFX pack — Futuristic UI
Generate BGM — Cyberpunk Exploration
Install SonicForge recommended environment
```

Host Job status is the canonical global progress surface; SonicForge may show richer local detail.

## 16. Project integration

From Project Lab/context actions, users/agents can:

- transcribe selected audio
- open audio in SonicForge
- generate audio for current project
- place a SonicForge asset into an authorized output directory

The UI can display project-relative destination labels supplied/derived by the Host without learning the absolute host path.

## 17. Workflow/agent UX

Workflow and agent users should see task-level names, not model names.

Good:

- Generate Speech
- Transcribe Audio
- Generate Sound/Music

Advanced model pinning belongs to optional node/tool fields.

Unavailable saved workflow nodes remain visible with a clear "SonicForge capability unavailable" reason; they are not deleted.

## 18. Theme and iframe rules

SonicForge embedded UI follows ControlDeck's isolated view contract:

- wait for theme/token handshake before final paint where needed
- react to theme/locale/safe-area changes
- do not use Host cookies
- do not depend on shared-origin localStorage/sessionStorage
- persist important state server-side
- synchronize internal route with Host bridge where supported
- handle disable/drain notification promptly

## 19. Accessibility/basic media behavior

- keyboard-accessible primary actions
- visible focus
- controls labelled in Japanese UI
- playback does not autoplay unexpectedly
- volume/play buttons are explicit
- long waveforms do not block basic navigation
- status is not communicated by color alone

## 20. Default Japanese copy policy

User-facing primary language is Japanese, with English localization keys available from the start.

Model/vendor jargon should be confined to Advanced/Diagnostics unless required for license/terms attribution.