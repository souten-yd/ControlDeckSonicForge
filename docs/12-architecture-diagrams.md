# Architecture and Lifecycle Diagrams

Status: Explanatory; normative rules live in the referenced design documents  
Date: 2026-08-25

## 1. Distribution trust and runtime authority are separate

```mermaid
flowchart LR
    Key[Trusted SonicForge publisher public key]
    Manifest[Ed25519-signed release manifest]
    Bundle[Lightweight SonicForge bundle]
    Host[ControlDeck generic Feature installer]
    Addon[Installed SonicForge Add-on service]
    Runtime[Add-on v2 scoped runtime authority]

    Key --> Host
    Manifest --> Host
    Bundle --> Host
    Host -->|signature + identity + SHA/size + safe install| Addon
    Addon --> Runtime
```

A valid publisher signature authorizes a release from a trusted publisher; it does not bypass Add-on capability grants or Runtime API authorization.

## 2. System ownership

```mermaid
flowchart TB
    U[User / Agent / Workflow]
    CD[ControlDeck Host]
    SF[SonicForge lightweight core]
    TTS[TTS worker packs]
    ASR[ASR worker packs]
    SFX[SFX / audio workers]
    MUS[Music workers]
    DB[(SonicForge DB / Assets / Voices / Localization)]
    GPU[ControlDeck AI Resource Broker]
    FS[ControlDeck scoped file/project grants]

    U --> CD
    CD -->|Add-on v2 / scoped token| SF
    SF --> TTS
    SF --> ASR
    SF --> SFX
    SF --> MUS
    SF --> DB
    TTS -->|lease if needed| GPU
    ASR -->|lease if needed| GPU
    SFX -->|lease if needed| GPU
    MUS -->|lease if needed| GPU
    SF -->|grant/content/output APIs| FS
```

ControlDeck owns generic host/trust/resource/file boundaries; SonicForge owns audio-specific behavior and heavy environments.

## 3. Repository/environment boundary

```mermaid
flowchart LR
    subgraph C[ControlDeck]
      CV[ControlDeck environment]
      CJ[Feature Host / Jobs / Broker / Add-on Host]
    end

    subgraph S[SonicForge]
      SC[lightweight core env]
      SR1[runtime A]
      SR2[runtime B]
      SD[(models / assets / voices / localization)]
    end

    subgraph M[MediaForge]
      MC[MediaForge core env]
      MR[MediaForge runtimes]
      MD[(MediaForge data/assets)]
    end

    CJ <-->|generic HTTP contracts| SC
    SC --> SR1
    SC --> SR2
    SC --> SD

    CV -. no venv sharing .- SC
    SC -. no private imports / DB sharing .- MC
    SR1 -. no runtime sharing .- MR
```

## 4. Fresh install + Speech Essentials

```mermaid
sequenceDiagram
    participant User
    participant CD as ControlDeck Feature Host
    participant Rel as Signed Release Assets
    participant SF as SonicForge core
    participant Job as ControlDeck Job
    participant Setup as SonicForge setup orchestrator
    participant Worker as TTS/ASR smoke tests

    User->>CD: Install/Update SonicForge
    CD->>Rel: Fetch manifest + signature + bundle
    CD->>CD: Verify publisher signature, identity, downgrade, size, SHA, archive
    CD->>CD: Stage/provision/health, atomic activate
    User->>CD: Open Audio
    CD->>SF: Proxied embedded view
    SF-->>User: Speech Essentials setup required
    User->>SF: 音声基本環境をセットアップ / Set up Speech Essentials
    SF->>Setup: Build read-only preflight plan
    Setup-->>User: disk/hardware/download/license plan
    User->>SF: Confirm required terms
    SF->>Job: Create/attach durable setup job
    SF->>Setup: Apply speech-essentials
    Setup->>Setup: Download/build into staging
    Setup->>Worker: Japanese + English TTS/ASR smoke tests
    Worker-->>Setup: Pass/fail by capability/language
    alt pass
      Setup->>Setup: Atomic activate
      Setup->>Job: succeeded
      SF-->>User: Speech available; optional Game Audio/Music can be added later
    else partial or fail
      Setup->>Setup: Keep last known-good runtime
      Setup->>Job: failed/degraded with actionable reason
      SF-->>User: Retry/repair or available fallback
    end
```

The signed ControlDeck feature installer handles the lightweight product. SonicForge handles its ML capability packs. Neither path executes arbitrary Add-on-supplied shell from the manifest.

## 5. Optional capability install

```mermaid
flowchart LR
    Speech[Speech Essentials available]
    Studio[User opens SFX or Music]
    Missing{Pack installed?}
    Action[Contextual one-click setup]
    Ready[Capability available]

    Speech --> Studio --> Missing
    Missing -->|yes| Ready
    Missing -->|no| Action --> Ready
```

Not installing optional Game Audio/Music does not degrade a healthy speech service.

## 6. GPU-backed generation

```mermaid
sequenceDiagram
    participant Caller as UI / Workflow / Agent
    participant CD as ControlDeck Host
    participant SF as SonicForge core
    participant RB as Resource Broker
    participant W as SonicForge worker

    Caller->>CD: Invoke SonicForge contribution
    CD->>SF: Scoped request token + validated input
    SF->>CD: Attach/update durable Host Job
    SF->>RB: Resource request (VRAM/mode/residency estimate)
    alt waiting
      RB-->>SF: waiting
      SF->>CD: waiting_resource progress
    end
    RB-->>SF: lease granted
    SF->>RB: activate lease
    SF->>W: execute task
    W-->>SF: progress
    SF->>CD: normalized bounded progress
    alt cancel
      CD-->>SF: control = cancel
      SF->>W: cancel if running
      SF->>RB: release/cancel resource
      SF->>CD: canceled
    else success
      W-->>SF: audio/result
      SF->>SF: validate + QA + provenance
      SF->>RB: release lease
      SF->>CD: succeeded + bounded asset reference
    end
```

Queued work that has not started can settle cancellation immediately; running work is unwound by the owner.

## 7. Host file input/output

```mermaid
sequenceDiagram
    participant User
    participant CD as ControlDeck
    participant SF as SonicForge
    participant W as Worker

    User->>CD: Select project/audio file or output destination
    CD-->>SF: grant:<id>
    SF->>CD: Resolve/read scoped grant
    CD-->>SF: bounded content/metadata
    SF->>W: private SonicForge staging input
    W-->>SF: generated/processed audio
    SF->>SF: validate + provenance
    SF->>CD: Create output staging
    CD-->>SF: output_id
    SF->>CD: Upload + commit under export grant
    CD-->>User: project result
```

SonicForge never needs the absolute ControlDeck project path.

## 8. Language-aware capability routing

```mermaid
flowchart TD
    R[Task request]
    C{Required capability/features}
    L{Content language<br/>ja / en / auto}
    V{Voice/project profile}
    H{Installed and healthy routes}
    Q{Fast / Recommended / High quality}
    M{Measured language/task performance + resources}
    P{Expert engine/model pin?}
    E[Selected adapter]

    R --> C --> L --> V --> H --> Q --> M --> P --> E
```

Japanese and English can use different ASR routes. The public contract does not force one model to cover all languages.

## 9. Capability health after Speech Essentials

```mermaid
flowchart LR
    Core[Core: available]
    TTS[TTS ja/en: available]
    ASR[ASR ja/en: available]
    Loc[Localization: available]
    SFX[SFX: optional setup_required]
    Music[Music: optional setup_required]
    Addon[SonicForge service: available]

    Core --> Addon
    TTS --> Addon
    ASR --> Addon
    Loc --> Addon
    SFX -. optional, does not degrade .-> Addon
    Music -. optional, does not degrade .-> Addon
```

A missing optional pack is not a service failure.

## 10. Durable browser reconnection

```mermaid
sequenceDiagram
    participant Browser
    participant SF as SonicForge core
    participant Job as Durable Job

    Browser->>SF: Start task
    SF->>Job: Create durable ownership before expensive work
    Browser--xSF: background/network drop
    Job->>Job: work continues
    Browser->>SF: visible again / reconnect
    SF-->>Browser: authoritative active job + current state
    Browser->>Browser: reattach progress UI
```

Do not cache a dead socket forever or depend on browser memory for job ownership.

## 11. Localization Studio

```mermaid
flowchart LR
    Lines[JP/EN dialogue table]
    Profiles[Character voice + pronunciation/project profiles]
    Preview[Representative previews]
    Batch[Durable JP/EN render batch]
    QA[Deterministic QA + optional TTS->ASR flags]
    Review[Review only flagged/changed lines]
    Export[Scoped project export<br/>locale naming profile]

    Lines --> Profiles --> Preview --> Batch --> QA --> Review --> Export
```

TTS->ASR QA is a mismatch flagging heuristic, not proof of naturalness or emotion.

## 12. ControlDeck TTS migration

```mermaid
flowchart LR
    Old[Historical ControlDeck TTS]
    Inv[Inventory exact source/settings/callers]
    New[SonicForge bilingual speech]
    Import[Explicit non-destructive migration]
    Calls[Generic Add-on invocation]
    Cut[Cutover]
    Remove[Remove obsolete Host TTS-specific implementation]

    Old --> Inv
    Inv --> New
    Inv --> Import --> New
    New --> Calls --> Cut --> Remove
```

Do not delete historical data or invent a compatibility shim before locating the historical source.

## 13. MediaForge + SonicForge composition

```mermaid
flowchart LR
    Agent[Agent / Workflow]
    CD[ControlDeck]
    MF[MediaForge]
    Visual[Visual asset / project context]
    SF[SonicForge]
    Audio[Speech / SFX / Music]
    Project[Scoped project outputs]

    Agent --> CD
    CD --> MF --> Visual --> CD
    CD --> SF --> Audio --> CD
    CD --> Project
```

Composition uses generic ControlDeck contracts and logical grants/assets, not shared private code/directories.

## 14. Document pointers

- ownership/boundaries: `01-boundaries-and-contracts.md`
- setup/runtime: `02-runtime-environment-and-setup.md`
- API/languages: `03-audio-capabilities-and-api.md`
- engines/models: `04-engine-model-strategy.md`
- UX/localization/reconnect: `05-ux-and-workflows.md`
- security/license/provenance: `06-security-license-and-provenance.md`
- TTS migration: `07-controldeck-tts-migration.md`
- quality gates: `08-development-process-and-quality-gates.md`
- roadmap: `09-roadmap.md`
- decisions: `11-decisions-and-open-questions.md`
- release signing: `13-release-distribution-and-signing.md`
- critical UX review: `14-bilingual-ux-and-critical-review.md`
