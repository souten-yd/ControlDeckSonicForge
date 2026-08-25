# Security, Licensing and Provenance

Status: Normative  
Date: 2026-08-25

## 1. Threat model

SonicForge handles sensitive/high-impact inputs and dependencies:

- user voice recordings and clone references
- arbitrary uploaded audio
- generated audio that may resemble people/copyrighted material
- third-party model files
- large local package/model downloads
- signed product release bundles
- GPU execution
- project exports

Local execution does not eliminate security, supply-chain or rights concerns.

## 2. Trust boundaries

```text
ControlDeck trusted feature publisher key
   | verifies signed SonicForge lightweight release
ControlDeck installed SonicForge feature
   | Add-on v2 / scoped token + grants
SonicForge core
   | validated worker protocol
Heavy workers / third-party ML code
   | private SonicForge staging/models
Generated/imported audio assets
```

Treat every boundary as independently fallible.

## 3. Publisher-signed release trust

SonicForge follows MediaForge's current direction: **Ed25519 publisher signature over a canonical release manifest**.

The publisher trust anchor is a public key stored by ControlDeck once. The signed manifest binds:

```text
schema_version
feature_id
version
platform
architecture
artifact_name
sha256
size_bytes
```

SHA-256 remains an integrity value, but it is not the per-release authorization mechanism.

Benefits:

- a SonicForge release no longer requires a ControlDeck source edit only to pin a new checksum;
- artifact bytes are still verified using the signed digest;
- product/version/platform identity is cryptographically bound;
- downgrade policy remains a separate Host check.

Detailed contract: `13-release-distribution-and-signing.md`.

## 4. Signing-key security

Publisher private key:

- never committed
- never bundled
- not available to ordinary test/build jobs
- stored as a protected release secret/key with restrictive permissions
- used only after bundle identity/tests succeed

Public key may be distributed through ControlDeck trusted publisher/catalog metadata.

A key rotation is an explicit trust event. Do not silently regenerate a key because a release script cannot find the original.

## 5. Signed bundle does not imply unlimited trust

A valid publisher signature does not grant arbitrary ControlDeck privileges.

ControlDeck still validates:

- expected feature/add-on identity
- version/platform/architecture
- artifact size/digest
- safe extraction/package structure
- allowed Host capabilities
- lifecycle bounds
- smoke/health before activation
- downgrade policy

Likewise, a signed SonicForge bundle does **not** automatically authenticate third-party models/packages downloaded later.

## 6. ControlDeck identity boundary

When used as an Add-on:

- ControlDeck is identity authority
- SonicForge never receives raw ControlDeck session cookies
- Host Authorization/CSRF headers are not Add-on credentials
- service/request tokens are short-lived and audience-bound
- supported token introspection is used instead of importing Host signing internals
- Add-on id/header/path/audience must agree
- disable/revocation follows Host contract

## 7. File boundary

Host files arrive only through scoped identifiers/grants.

Reject raw absolute Host paths arriving through Add-on endpoints.

For internal local paths:

- resolve realpath
- validate containment
- reject symlink escape
- private staging permissions
- never derive path directly from prompt text

Archive/model imports require traversal, symlink and expansion/size protections.

## 8. Subprocess boundary

Forbidden:

- `shell=True`
- untrusted shell strings
- browser-provided executable/package names passed directly to process launch
- prompt text concatenated into command lines when avoidable

Allowed:

- fixed/registered executables
- argv arrays
- bounded environment
- approved cwd
- timeout/cancel
- bounded/redacted logs

## 9. Worker isolation

Heavy third-party engine code is outside the core process.

Workers:

- non-root by default
- receive minimal task/resource context
- no ControlDeck DB access
- no unrestricted project-root path/mount
- bounded input/output directories
- explicit health/version/capability handshake
- terminate on timeout/cancel if graceful stop fails
- may crash without killing core

Containerization is optional when it materially improves isolation/dependency compatibility; it is not the public runtime contract.

## 10. Network policy

Default inference is local-first.

Workers should not make arbitrary outbound inference-time requests.

Expected network operations:

- explicit setup/package/model downloads
- update metadata
- configured sources

Normal task requests never carry arbitrary download URLs that setup blindly fetches.

Future remote inference requires explicit data-egress policy and configuration.

## 11. Runtime/package supply chain

- lock runtime-critical dependencies
- prefer official/known upstream sources
- pin Git dependencies to immutable revisions for production
- record engine source tag/commit
- no `curl | sh`
- staged environment before activation
- verify available package/model artifact digest metadata
- separate release-signing dependencies from shipped core runtime

The signed lightweight release can describe approved SonicForge setup metadata, but runtime installers still verify their own locked sources/artifacts.

## 12. Model acquisition trust

Model catalog records:

```text
source/repository
immutable revision if available
file names/sizes
digests when available
license/terms
gated state
retrieval timestamp
adapter compatibility
tested languages/hardware
```

Moving references should be resolved to immutable revisions before marking a model reproducibly installed where the source permits it.

A custom imported model can be retained as `unverified`; do not promote it to trusted/recommended merely because it loads.

## 13. Voice cloning rights and consent

Before saving a reusable cloned/reference voice profile require explicit confirmation such as:

```text
I have permission/right to use this reference voice for the intended purpose.
```

Store:

- confirmation timestamp
- confirmation text/version id
- local user/actor reference when available
- source asset id/hash
- optional attribution/notes/intended use

Do not claim software has legally verified ownership.

## 14. Voice profile safety UX

Distinguish visibly:

- built-in licensed voice
- user-owned/custom-trained voice
- cloned/reference voice
- voice-design synthetic profile
- imported unverified model

For bilingual profiles, show tested/preferred Japanese/English behavior separately when useful.

## 15. Model licensing

Code license and model-weight/voice license are distinct records.

Every catalog entry can carry:

```text
code_license_id
code_license_url
model_license_id
model_license_url
terms_url
gated_access
gated_acceptance_required
attribution_requirements
commercial_use_note (informational, sourced)
revision/retrieved_at
```

Never infer that model weights inherit repository code licensing.

## 16. License acceptance

For gated/terms-required models:

- setup plan identifies requirement
- UI shows source/terms before acceptance
- user explicitly accepts when required
- acceptance record is bound to model/terms revision where possible
- setup resumes afterwards

Never auto-submit acceptance on the user's behalf.

## 17. Imported model policy

Ask for/record where available:

- engine/type
- files
- source URL/reference
- license/terms
- author/attribution
- rights note

Unknown state:

```text
license_status = unverified
provenance_status = unverified
```

Never label unknown assets safe for commercial use.

## 18. Generated asset provenance

Every succeeded generated asset has provenance including:

```text
operation/capability
SonicForge version
adapter id/version
engine id/version
model id/revision
model-license record id
input asset ids/hashes
voice profile id
content language
normalized generation parameters
seed when supported
created_at
Host job id when present
```

Prompt storage may be privacy-configurable; retain a stable hash if raw prompt is omitted where practical.

## 19. Lineage

Transforms create new lineage rather than overwriting sources by default:

```text
asset A -> remix -> B
B -> normalize -> C
voice X + text -> TTS -> D
D -> ASR QA -> QA record
JP/EN localization row -> two language assets
```

## 20. QA honesty

A validator may only report checks it actually performed.

Use states like:

```text
passed
warning
failed
not_checked
not_applicable
```

Do not return an empty warnings array as if semantic constraints were verified when no semantic evaluator ran.

TTS->ASR round-trip is a heuristic for missing/repeated/mismatched content, not proof of natural speech or correct identity/emotion.

## 21. Export metadata

Optional sidecar:

```text
sound.wav
sound.sonicforge.json
```

It may contain portable provenance/license/locale/profile metadata, but never local absolute paths, Host tokens or meaningless private grant IDs.

## 22. Secrets

Potential secrets:

- SonicForge Ed25519 publisher **private key**
- Hugging Face/gated source tokens
- future provider keys
- ControlDeck service/request tokens

Rules:

- never in repository/examples
- least-privilege secret store/environment
- redact from logs/exceptions
- avoid command-line exposure where safer options exist
- never embed in URLs
- publisher private key never reaches runtime installation

## 23. Logs/privacy

Logs may include:

- engine/runtime ids
- job/task ids
- duration/resource estimates
- status/error codes

Avoid by default:

- full spoken/transcribed text
- raw prompts when privacy policy disables them
- raw voice reference content
- tokens/signing key material
- absolute Host project paths

Expanded diagnostics are explicit and bounded.

## 24. Resource abuse controls

Server-side enforce:

- request/body limits
- synchronous audio-duration limits
- generation duration limits
- batch/variation limits
- active jobs/session limits
- setup operation concurrency
- worker timeout/cancel

UI disabled controls are not security enforcement.

## 25. Audio parser safety

Uploaded/generated audio is untrusted until validated:

- container/type
- duration
- sample/channel sanity
- decoded size
- malformed metadata

Complex external decoders may run out of process where practical.

## 26. Release verification tests

Required negative tests include:

- signed manifest tamper
- artifact tamper after signing
- wrong feature/version/platform/arch/name/size
- wrong publisher key
- malformed signature
- downgrade
- capability escalation despite valid signature
- failed provision preserving previous active version

Do not use the real publisher private key in unit tests.

## 27. Engine security review gate

Before an engine is recommended:

1. license/terms
2. install/network behavior
3. filesystem/privilege assumptions
4. dependency conflicts
5. model loading behavior
6. cancel/termination
7. output validation
8. provenance
9. language-specific benchmark
10. resource estimate correctness

## 28. No security regression for convenience

A setup button or signed release does not justify:

- arbitrary manifest shell execution
- shared ControlDeck/MediaForge venv
- full project-root mounts into third-party workers
- Host cookie forwarding
- root service by default
- skipping third-party model license/digest checks
- granting new Host capabilities merely because the release signature is valid

If convenience conflicts with these boundaries, redesign the mechanism.