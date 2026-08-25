# Bilingual Product, UX and Critical Design Review

Status: Normative product refinement  
Date: 2026-08-25

## 1. Outcome of the review

The original SonicForge baseline was directionally sound, but several parts would create unnecessary complexity or first-use friction if implemented literally.

This review makes the following product-level changes:

1. **Japanese and English become first-class supported speech languages.** Japanese remains a quality priority, not an exclusive mode.
2. UI locale and speech-content language are separate concepts.
3. Settings use **three levels**: Easy / Customize / Expert, not a binary Simple/Advanced split.
4. Recommended first setup installs **Speech Essentials** by default; SFX and Music are optional one-click packs rather than mandatory multi-GB first-run downloads.
5. The workspace is simplified to **Studio / Voices / Library / Runtime**, with task tabs inside Studio.
6. New **Localization Studio** workflows support paired Japanese/English game dialogue and batch export.
7. Preview, candidate comparison and automatic QA are first-class workflows.
8. Public API contract remains intentionally small despite a richer UI/capability matrix.

## 2. Japanese + English support

### Product policy

Initial language tier:

```text
Tier 1: Japanese, English
Tier 2: other languages exposed only when the installed engine is tested and capability metadata says supported
```

Japanese remains the primary benchmark target for pronunciation, character dialogue and ASR accuracy. English receives the same product-level UI/API support and its own benchmark fixtures.

### Separate three language concepts

Do not use one ambiguous `language` setting for everything.

```text
ui_locale        ControlDeck/SonicForge interface language: auto | ja | en
content_language language of text/audio being synthesized/transcribed: auto | ja | en initially
voice_language   preferred/native language metadata of a voice profile
```

These can differ. Example: English UI, Japanese dialogue generation.

### Locale behavior

- UI locale defaults to the ControlDeck locale/theme bridge.
- Users may override SonicForge locale in Settings.
- All user-visible strings use translation keys; do not concatenate Japanese fragments in code.
- Dates, numbers and units use locale-aware formatting.
- Error codes remain language-neutral; messages are localized at the UI/API presentation layer.

### Mixed Japanese/English content

Code-switching is common in games and technical speech.

Support:

- `content_language: auto`
- Japanese sentences containing English words/product names
- English sentences containing Japanese proper nouns where supported
- per-line language override in batch dialogue
- per-segment detected language metadata for ASR when the engine can provide it

When the language is known, explicit language should be preferred over auto-detection for predictable pronunciation and routing.

## 3. Three-level settings model

The UI should not expose every model parameter simply because an engine has it.

### Level 1 — Easy / かんたん

Target: most users and most jobs.

Show only 3–5 decisions relevant to the task.

Examples:

**Speech**

```text
Text
Voice
Style
Language (Auto by default)
[Generate]
```

**Transcribe**

```text
Audio
Language (Auto)
Timestamps on/off
[Transcribe]
```

**SFX**

```text
Description
Type/preset
Length
Variations
[Create]
```

**Music**

```text
Description
Length
BGM/Instrumental
Loop
[Create]
```

Quality uses a single recommended default and is not forced as a decision on every run.

### Level 2 — Customize / 調整

Target: users who know the outcome they want but should not need model knowledge.

Expose normalized, engine-independent controls such as:

```text
quality: fast / recommended / high
speech speed
emotion/style strength
pronunciation overrides
variation count
BPM/mood
loudness target preset
loop behavior
output format/profile
```

### Level 3 — Expert / 詳細

Target: troubleshooting, reproducibility and model-specific experimentation.

May expose:

```text
engine/model pin
seed
engine-native advanced parameters
device/runtime selection
chunking/VAD thresholds
sample rate/channel override
model residency/debug information
```

Expert settings are never required to get a normal successful result.

## 4. Settings are contextual, not a giant form

A control appears only when all are true:

1. the current task can use it;
2. the selected/auto-routed capability supports it;
3. it has a meaningful effect for the selected profile.

Do not display disabled controls for features that the engine cannot support merely to make the UI look complete.

Preserve values per task/profile, not as one global bag of parameters.

## 5. Simplified information architecture

The earlier seven-item in-app navigation (`Create / Speech / Transcribe / Game Audio / Music / Library / Runtime`) creates redundant entry points.

Adopt:

```text
Studio
Voices
Library
Runtime
```

### Studio task tabs

```text
Speech
Transcribe
SFX
Music
Localization
```

This keeps the product understandable while still letting each task have a purpose-built workspace.

Mobile primary navigation should be even smaller:

```text
Studio | Library | Jobs | More
```

Voices/Runtime live under `More` where screen space is limited.

## 6. Quick Create remains, but does not become another navigation level

At the top of Studio, offer task cards/command input:

```text
Speak text
Transcribe audio
Create sound effect
Create BGM
Localize dialogue
```

After selection, the same Studio route changes task mode. Avoid separate duplicate routes that all lead to the same editor.

This follows the MediaForge lesson that duplicate navigation + quick-action entry points create noise rather than discoverability.

## 7. Recommended setup is intentionally smaller

### Problem with the original design

Installing TTS + ASR + SFX + Music in the default profile can involve several large runtimes/models even when the user only wants speech.

That increases:

- first-use time
- disk use
- failure surface
- license/terms prompts
- GPU/runtime compatibility risk

### Adopted setup profiles

```text
Speech Essentials    default: Japanese + English TTS/ASR
Game Audio           optional one-click pack
Music                optional one-click pack
Full Studio          explicit choice; installs all supported recommended packs
CPU Essentials       fallback where useful
Custom               component-level selection
```

The first prominent button is:

```text
[ Set up Speech Essentials / 音声基本環境をセットアップ ]
```

If a user enters SFX/Music before installation, show a contextual one-button install for that capability rather than forcing them into a general package manager screen.

## 8. Smart defaults

Recommended routing should make decisions from:

- language
- task
- selected voice/profile
- installed capabilities
- hardware/resource availability
- measured engine performance
- requested quality/latency

The UI shows the **outcome policy**, not the model name:

```text
Fast
Recommended
High quality
```

`Recommended` is the default. Exact engine/model is visible in result details and Expert settings for reproducibility.

## 9. Preview then Render Final

Generation models often make users iterate. Re-running a full-quality job for every wording change wastes time and GPU resources.

Adopt a two-stage pattern where the engine supports it:

```text
[Preview]  quick/small/short generation
[Render Final] production profile
```

For speech, preview may generate the selected line/first paragraph with a faster route.
For music, preview may be a shorter candidate or lower-cost route rather than silently truncating a user's final request.

A preview must be clearly labeled and never overwrite a final asset.

## 10. Candidate comparison

For subjective generation tasks, one result is often insufficient.

Provide an A/B candidate strip for:

- TTS style/voice preview
- SFX variations
- music variations

Default candidate count stays small (usually 2 or 3) to avoid resource explosion.

Actions:

```text
Play
Favorite
Use this
Make variations
Compare details
```

The selected favorite can become the seed/reference for a later refinement when the engine supports it.

## 11. Localization Studio — adopted new feature

This is a high-value feature for game/content production and directly benefits from Japanese + English support.

### Purpose

Manage a table of dialogue lines and render both languages consistently.

Example columns:

```text
line_id
character
Japanese text
English text
voice/profile
style/context
status
JP asset
EN asset
QA
```

### Workflow

```text
import CSV/JSON or enter lines
 -> assign character voices once
 -> preview representative lines
 -> batch render JP/EN
 -> run optional audio/text QA
 -> review only flagged lines
 -> export using a project naming profile
```

### Project profiles

Store reusable rules such as:

```text
locale directories: ja / en
filename: {line_id}_{locale}.wav
sample rate / channels
loudness target
preferred quality
voice mapping per character
```

Do not hard-code Unity/Unreal/Godot paths into the core API. Provide generic project profiles and optional export templates.

## 12. Pronunciation and terminology library

Japanese/English projects need consistent names and technical terms.

Adopt a project-scoped dictionary:

```text
surface form
language
preferred reading/pronunciation
optional phoneme/engine-specific override
notes
```

Examples:

```text
ControlDeck
SonicForge
character names
fictional locations
product names
acronyms
```

Normalized dictionary entries are engine-independent. Engine-specific phoneme syntax remains an adapter detail or Expert override.

## 13. Voice consistency profiles

A game character must sound consistent across hundreds of lines.

A logical voice profile stores:

- voice identity/recipe
- preferred language behavior
- default style
- speaking-rate range
- project pronunciation dictionary reference
- recommended routing policy
- rights/license metadata

This is more stable than asking users to recreate model parameters for every line.

## 14. Automatic QA — adopted new feature

Before an asset is considered production-ready, deterministic QA can catch common failures cheaply.

### All audio

- decodes successfully
- non-zero/sane duration
- clipping/true-peak limit
- excessive leading/trailing silence
- declared format metadata matches file
- loop points valid

### Speech

Optional ASR round-trip check:

```text
TTS output -> ASR -> compare with normalized source text
```

Use it as a **flagging heuristic**, not proof that speech sounds natural. It can catch missing phrases, repeated phrases or severe pronunciation failures.

### SFX/Music

- requested duration tolerance
- loop seam metric where meaningful
- loudness/profile checks
- empty/silent/invalid output

Unverifiable semantic requirements must be recorded as `not_checked`, never reported as passed merely because no validator exists.

## 15. Jobs and progress must survive navigation

All work that can take noticeable time becomes server-owned before expensive preparation begins.

Do not place substantial LLM/VLM/audio analysis only in browser state before creating the durable job.

On reload/return:

- reconnect
- discover active job
- restore progress
- continue displaying result when complete

This follows the current MediaForge lesson that browser-owned orchestration makes expensive preparation disappear when the tab closes.

## 16. Connection resilience

Embedded mobile/web clients routinely background, sleep and return.

The client must:

- detect a closed WebSocket rather than caching it forever
- reconnect on visibility return
- reload authoritative server state
- retry boot with bounded backoff
- avoid polling while a healthy push connection exists

A transient network drop must not produce a permanently blank Studio.

## 17. Clear user vocabulary

Never collapse distinct states such as:

```text
available in catalog
installed on this machine
loaded in memory
currently running
recommended
experimental
```

Use plain localized labels and explanation.

Likewise, do not show `running` before a durable task actually exists. Use `preparing`/`checking` where appropriate.

## 18. Action placement

Primary action should remain visible near the task inputs, especially on mobile.

Rules:

- one dominant action per view
- destructive actions separated visually
- cancel remains reachable while work is pending/running
- long technical details live behind disclosure
- labels should fit one line at supported mobile widths where practical
- use `aria-label`/accessible names when compact visual labels are used

## 19. Critical contract review

### Keep: capability-first routing

Strong decision. Model-specific APIs would make the contract age quickly.

### Keep: four stable workflow executors

Do **not** create a public executor for every detailed capability. The richer runtime capability document is for discovery/routing; stable workflow contracts remain intentionally small.

### Modify: `speech.asr.ja_en`

Reject a dedicated language-pair capability name. Language support belongs in capability metadata/request language fields. Otherwise every language combination creates new API surface.

### Modify: `quality = fast / balanced / quality`

Keep stable wire values if useful, but present them to users as:

```text
Fast / Recommended / High quality
```

The UI should not force users to understand what `balanced` means.

### Reject: always-visible engine/model picker

It undermines automatic routing and makes setup feel more complex than it is. Keep it in Expert mode.

### Reject: install-everything recommended profile

Too costly for first use. Use Speech Essentials + contextual optional packs.

### Reject: dozens of per-engine settings in persistent top-level schema

Engine-native options belong in a namespaced Expert extension and must not become required stable fields.

## 20. API language direction

Initial normalized values:

```text
content_language: "auto" | "ja" | "en"
ui_locale: "auto" | "ja" | "en"
```

Internally store normalized locale/BCP-47 metadata where needed (for example `ja-JP`, `en-US`) without forcing region selection for ordinary users.

Capabilities advertise supported languages explicitly. A request for a language not supported by the selected/available route fails clearly rather than silently using the wrong language.

## 21. Success criteria added by this review

Before v1, verify that a user can:

- operate the full primary UI in Japanese or English;
- synthesize and transcribe both Japanese and English through supported routes;
- handle representative mixed Japanese/English content;
- complete normal Speech/SFX/Music tasks without opening Expert settings;
- install only the capability pack they actually need;
- return to a running job after navigation/backgrounding;
- render a small bilingual dialogue batch through Localization Studio;
- understand catalog/installed/available/running states without model knowledge.