# ControlDeck SonicForge

SonicForge is an out-of-process ControlDeck Add-on for speech, audio and music generation.
It is deliberately isolated from ControlDeck core and from MediaForge runtime environments.

## Goals

- Japanese **and English** first-class TTS/ASR product support, with Japanese quality prioritized in benchmarking
- mixed Japanese/English speech and game-localization workflows
- voice cloning, voice design and expressive dialogue rendering
- game-oriented SFX, ambience, UI sound and voice-pack generation
- local music generation, remix, extension and loop workflows
- Localization Studio for bilingual dialogue batches and project export
- durable jobs, cancellation, reconnect/resume, progress and provenance
- ControlDeck Add-on Platform v2 / AI Resource Broker integration
- **Easy / Customize / Expert** progressive settings instead of exposing model knobs by default
- one-click **Speech Essentials** provisioning, with Game Audio and Music as optional one-click packs
- publisher-signed ControlDeck release bundles using the MediaForge Ed25519 manifest pattern

## Non-goals

- importing SonicForge Python/JavaScript into ControlDeck
- sharing a Python virtual environment with ControlDeck or MediaForge
- turning ControlDeck's LLM gateway into an audio protocol gateway
- hard-coding model names into public high-level APIs
- unrestricted filesystem access
- making every engine-native parameter part of the stable public contract
- forcing users to install every SFX/music model before they can use speech
- trusting a release solely because a checksum appears in mutable metadata
- hiding an unavailable Add-on instead of explaining its state

## Documentation map

Read in this order:

1. [Master specification](docs/00-master-spec.md)
2. [Architecture, ownership and boundary rules](docs/01-boundaries-and-contracts.md)
3. [Runtime environment and one-click setup](docs/02-runtime-environment-and-setup.md)
4. [Audio capabilities and public API](docs/03-audio-capabilities-and-api.md)
5. [Engine and model strategy](docs/04-engine-model-strategy.md)
6. [UX and workflows](docs/05-ux-and-workflows.md)
7. [Security, licensing and provenance](docs/06-security-license-and-provenance.md)
8. [ControlDeck TTS migration](docs/07-controldeck-tts-migration.md)
9. [Development process and quality gates](docs/08-development-process-and-quality-gates.md)
10. [Implementation roadmap](docs/09-roadmap.md)
11. [Reference repositories and research notes](docs/10-reference-repositories.md)
12. [Decisions and open questions](docs/11-decisions-and-open-questions.md)
13. [Architecture and lifecycle diagrams](docs/12-architecture-diagrams.md)
14. [Release distribution and publisher signing](docs/13-release-distribution-and-signing.md)
15. [Bilingual UX and critical design review](docs/14-bilingual-ux-and-critical-review.md)
16. [Implementation status / evidence ledger](docs/implementation-status.md)
17. [Draft Add-on manifest](docs/contracts/addon.example.json)
18. [Draft capability document](docs/contracts/capabilities.example.json)

`AGENTS.md` is normative for developers and coding agents.

## Canonical upstream contracts

SonicForge must track the actual ControlDeck contract rather than copying stale examples:

- `souten-yd/ControlDeck/docs/design-addon-platform-v2.md`
- `souten-yd/ControlDeck/docs/plugin-sdk.md`
- `souten-yd/ControlDeck/backend/app/addons/schema.py`
- `souten-yd/ControlDeck/backend/app/features/release_bundle.py`
- `souten-yd/ControlDeck/tools/fake-addon/`
- `souten-yd/ControlDeckMediaForge/docs/controldeck-integration-plan.md`
- `souten-yd/ControlDeckMediaForge/AGENTS.md`
- `souten-yd/ControlDeckMediaForge/scripts/sign_release.py` for the current publisher-signature release pattern

When these disagree with this repository, stop implementation, identify which contract changed, and update the SonicForge design before adapting code. For release trust specifically, SonicForge targets the MediaForge publisher-signature direction; the current Host compatibility status is documented in `docs/13-release-distribution-and-signing.md`.

## Initial technical decisions

- Add-on id: `sonic-forge`
- service origin: `http://127.0.0.1:9140` by default
- core: Python 3.11+ / FastAPI / Pydantic v2 / SQLAlchemy / httpx
- heavy ML engines: separate worker processes and SonicForge-owned runtime packs
- data directory: `~/.local/share/control-deck-sonic-forge/` by default
- cache directory: `~/.cache/control-deck-sonic-forge/` by default
- primary UI locales: Japanese and English
- primary speech content languages: Japanese and English, with explicit/auto language routing
- local-first; remote providers are outside v1 scope
- GPU jobs must obtain a ControlDeck Resource Broker lease when running as a ControlDeck Add-on
- release authorization uses a trusted publisher Ed25519 key; artifact SHA-256 is bound inside the signed manifest

## UX baseline

Normal users should not need to choose a model. The default pattern is:

```text
Easy       task + a few meaningful choices
Customize  common outcome controls
Expert     engine/model/seed/runtime and model-native details
```

Studio contains Speech / Transcribe / SFX / Music / Localization task tabs, while top-level in-app navigation stays small: Studio / Voices / Library / Runtime.

## First implementation slice

Start with `SF0-1 — Lightweight core` in [the roadmap](docs/09-roadmap.md): FastAPI/config/DB baseline, `/health`, capability discovery, `sf.sh`, clean core-environment bootstrap and read-only `doctor`. Do **not** add torch or production speech/music models in that first slice.

## Status

The architecture/specification baseline has been refined for bilingual operation, simpler progressive UX, staged capability installation and signed releases. Runtime/model behavior remains explicitly `NOT TESTED` until implementation and real target-hardware evidence are recorded in [docs/implementation-status.md](docs/implementation-status.md).