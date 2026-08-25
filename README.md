# ControlDeck SonicForge

SonicForge is an out-of-process ControlDeck Add-on for speech, audio and music generation.
It is deliberately isolated from ControlDeck core and from MediaForge runtime environments.

## Goals

- Japanese-first TTS and ASR
- voice cloning, voice design and expressive dialogue rendering
- game-oriented SFX, ambience, UI sound and voice-pack generation
- local music generation, remix, extension and loop workflows
- durable jobs, cancellation, progress and provenance
- ControlDeck Add-on Platform v2 / AI Resource Broker integration
- simple default UX with progressive disclosure for advanced controls
- one-click provisioning of SonicForge-owned runtime/model environments after the lightweight service is available

## Non-goals

- importing SonicForge Python/JavaScript into ControlDeck
- sharing a Python virtual environment with ControlDeck or MediaForge
- turning ControlDeck's LLM gateway into an audio protocol gateway
- hard-coding model names into public high-level APIs
- unrestricted filesystem access
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
12. [Draft Add-on manifest](docs/contracts/addon.example.json)
13. [Draft capability document](docs/contracts/capabilities.example.json)

`AGENTS.md` is normative for developers and coding agents.

## Canonical upstream contracts

SonicForge must track the actual ControlDeck contract rather than copying stale examples:

- `souten-yd/ControlDeck/docs/design-addon-platform-v2.md`
- `souten-yd/ControlDeck/docs/plugin-sdk.md`
- `souten-yd/ControlDeck/backend/app/addons/schema.py`
- `souten-yd/ControlDeck/tools/fake-addon/`
- `souten-yd/ControlDeckMediaForge/docs/controldeck-integration-plan.md`
- `souten-yd/ControlDeckMediaForge/AGENTS.md`

When these disagree with this repository, stop implementation, identify which contract changed, and update the SonicForge design before adapting code.

## Initial technical decisions

- Add-on id: `sonic-forge`
- service origin: `http://127.0.0.1:9140` by default
- core: Python 3.11+ / FastAPI / Pydantic v2 / SQLAlchemy / httpx
- heavy ML engines: separate worker processes and SonicForge-owned runtime packs
- data directory: `~/.local/share/control-deck-sonic-forge/` by default
- cache directory: `~/.cache/control-deck-sonic-forge/` by default
- local-first; remote providers are outside v1 scope
- GPU jobs must obtain a ControlDeck Resource Broker lease when running as a ControlDeck Add-on

## Status

This repository currently contains the architecture/specification baseline. Implementation should start from `docs/09-roadmap.md` and follow `AGENTS.md`.