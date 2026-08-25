# Architecture and Lifecycle Diagrams

Status: Explanatory; normative rules live in the referenced design documents  
Date: 2026-08-25

## 1. System ownership

```mermaid
flowchart TB
    U[User / Agent / Workflow]
    CD[ControlDeck Host]
    SF[SonicForge lightweight core]
    TTS[TTS worker packs]
    ASR[ASR worker packs]
    SFX[SFX / audio workers]
    MUS[Music workers]
    DB[(SonicForge DB / Assets / Voices)]
    GPU[ControlDeck AI Resource Broker]
    FS[ControlDeck scoped file/project grants]

    U --> CD
    CD -->|Add-on v2 / scoped token| SF
    SF --> TTS
    SF --> ASR
    SF --> SFX
    SF --> MUS
    SF --> DB
    TTS -->|lease request| GPU
    ASR -->|lease if needed| GPU
    SFX -->|lease if needed| GPU
    MUS -->|lease if needed| GPU
    SF -->|grant/content/output APIs| FS
```

Key rule: ControlDeck hosts generic platform capabilities; SonicForge owns all audio-specific behavior and heavy environments.

## 2. Repository/environment boundary

```mermaid
flowchart LR
    subgraph C[ControlDeck]
      CV[ControlDeck .venv]
      CJ[Jobs / Broker / Add-on Host]
    end

    subgraph S[SonicForge]
      SC[.venv lightweight core]
      SR1[runtime A .venv]
      SR2[runtime B .venv]
      SD[(SonicForge data/models/assets)]
    end

    subgraph M[MediaForge]
      MC[MediaForge .venv]
      MR[MediaForge runtimes]
      MD[(MediaForge data/assets)]
    end

    CJ <-->|HTTP declarative contract| SC
    SC --> SR1
    SC --> SR2
    SC --> SD

    CV -. no sharing .- SC
    SC -. no imports / venv / DB sharing .- MC
    SR1 -. no runtime sharing .- MR
```

## 3. First-use setup

```mermaid
sequenceDiagram
    participant User
    participant CD as ControlDeck
    participant SF as SonicForge core
    participant Job as ControlDeck Job
    participant Setup as SonicForge setup orchestrator
    participant Worker as Runtime/model smoke test

    User->>CD: Open Audio
    CD->>SF: Proxied embedded view
    SF-->>User: setup_required
    User->>SF: 推奨環境をセットアップ
    SF->>Setup: Build preflight plan
    Setup-->>User: disk/hardware/download/license plan
    User->>SF: Confirm / accept required terms
    SF->>Job: Create/attach setup job
    SF->>Setup: Apply recommended profile
    Setup->>Setup: Download/build into staging
    Setup->>Worker: Smoke test staged runtime/model
    Worker-->>Setup: Pass/fail
    alt pass
      Setup->>Setup: Atomic activate
      Setup->>Job: succeeded
      SF-->>User: capabilities available/degraded
    else fail
      Setup->>Setup: Keep last known-good active runtime
      Setup->>Job: failed with actionable reason
      SF-->>User: Retry/repair guidance
    end
```

The button runs SonicForge's own setup API. ControlDeck does not execute an arbitrary command supplied by the Add-on manifest.

## 4. GPU-backed generation

```mermaid
sequenceDiagram
    participant Caller as UI / Workflow / Agent
    participant CD as ControlDeck Host
    participant SF as SonicForge core
    participant RB as Resource Broker
    participant W as SonicForge worker

    Caller->>CD: Invoke SonicForge contribution
    CD->>SF: Scoped request token + validated input
    SF->>CD: Attach/update Host Job
    SF->>RB: Resource request (VRAM/mode/residency estimate)
    alt resource waiting
      RB-->>SF: waiting
      SF->>CD: Job waiting_resource
    end
    RB-->>SF: lease granted
    SF->>RB: activate lease
    SF->>W: execute task
    W-->>SF: progress
    SF->>CD: normalized progress
    alt cancel
      CD-->>SF: control = cancel
      SF->>W: cancel
      SF->>RB: release lease
      SF->>CD: canceled
    else success
      W-->>SF: generated audio
      SF->>SF: validate + provenance
      SF->>RB: release lease
      SF->>CD: succeeded + bounded asset reference
    end
```

Waiting for a GPU must not be implemented as a hidden busy loop that bypasses the Host broker.

## 5. Host file input/output

```mermaid
sequenceDiagram
    participant User
    participant CD as ControlDeck
    participant SF as SonicForge
    participant W as Worker

    User->>CD: Select project/audio file
    CD-->>SF: grant:<id> metadata
    SF->>CD: GET grant content
    CD-->>SF: bounded content stream
    SF->>W: private SonicForge staging input
    W-->>SF: generated/processed audio
    SF->>SF: validate + provenance
    SF->>CD: Create Host output staging
    CD-->>SF: output_id
    SF->>CD: PUT output content
    SF->>CD: Commit output under export grant
    CD-->>User: project result
```

At no point does SonicForge need the absolute ControlDeck project path.

## 6. Capability routing

```mermaid
flowchart TD
    R[Task request<br/>speech.tts.synthesize]
    C{Required capability/features}
    L{Japanese / language}
    V{Voice/profile requirement}
    H{Installed & healthy engines}
    Q{Quality/latency policy}
    P{Explicit advanced pin?}
    E[Selected engine adapter]

    R --> C --> L --> V --> H --> Q --> P --> E
```

Model names are routing details. Stable callers should not need to know them.

## 7. Capability degradation

```mermaid
flowchart LR
    Core[SonicForge core healthy]
    TTS[TTS available]
    ASR[ASR available]
    SFX[SFX setup_required]
    Music[Music unavailable]
    Addon[Add-on state: degraded]

    Core --> Addon
    TTS --> Addon
    ASR --> Addon
    SFX --> Addon
    Music --> Addon
```

An optional music worker failure must not make Japanese transcription disappear.

## 8. ControlDeck TTS migration

```mermaid
flowchart LR
    Old[Historical ControlDeck TTS]
    Inv[Inventory exact source/settings/callers]
    New[SonicForge speech.tts]
    Import[Explicit non-destructive migration]
    Calls[Generic Add-on invocation]
    Cut[Cutover]
    Remove[Remove obsolete TTS-specific Host code]

    Old --> Inv
    Inv --> New
    Inv --> Import --> New
    New --> Calls --> Cut --> Remove
```

Do not delete historical data or invent a compatibility shim before the historical source is located.

## 9. MediaForge + SonicForge composition

```mermaid
flowchart LR
    Agent[Agent / Workflow]
    CD[ControlDeck]
    MF[MediaForge]
    Visual[Visual asset / project grant]
    SF[SonicForge]
    Audio[Speech / SFX / Music asset]
    Project[Project outputs]

    Agent --> CD
    CD --> MF --> Visual --> CD
    CD --> SF --> Audio --> CD
    CD --> Project
```

Composition happens through ControlDeck contracts and logical assets/grants, not a shared directory shortcut or Python import.

## 10. Document pointers

- ownership/boundaries: `01-boundaries-and-contracts.md`
- setup/runtime lifecycle: `02-runtime-environment-and-setup.md`
- API/capabilities: `03-audio-capabilities-and-api.md`
- engines/models: `04-engine-model-strategy.md`
- UX: `05-ux-and-workflows.md`
- security/license/provenance: `06-security-license-and-provenance.md`
- TTS migration: `07-controldeck-tts-migration.md`
- development gates: `08-development-process-and-quality-gates.md`
- implementation order: `09-roadmap.md`
