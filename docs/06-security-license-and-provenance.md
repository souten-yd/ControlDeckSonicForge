# Security, Licensing and Provenance

Status: Normative  
Date: 2026-08-25

## 1. Threat model

SonicForge handles unusually sensitive and risky inputs:

- user voice recordings
- voice-clone reference material
- arbitrary uploaded audio
- generated audio that may resemble copyrighted/person-specific material
- third-party model files
- large local model downloads
- GPU execution
- project file exports

Local execution does not eliminate security or rights concerns.

## 2. Trust boundaries

```text
Browser embedded view
   | opaque Host proxy/bridge
ControlDeck host
   | short-lived Add-on token + grants
SonicForge core
   | validated worker protocol
Heavy workers / third-party ML code
   | private SonicForge staging/models
Generated/imported audio assets
```

Treat each boundary as potentially faulty or compromised.

## 3. ControlDeck identity boundary

When used as an Add-on:

- ControlDeck is identity authority
- SonicForge never receives raw ControlDeck session cookies
- Host Authorization/CSRF headers are not propagated as Add-on credentials
- service/request tokens are short-lived and audience-bound
- SonicForge verifies Host request tokens through supported introspection rather than sharing Host signing secrets
- add-on id/header/path/audience must agree
- disable/revocation behavior follows Host contract

## 4. File boundary

Host-originated file access uses only scoped IDs/grants.

SonicForge must reject raw absolute Host paths arriving through Add-on endpoints even if they happen to exist locally.

For every local path used internally:

- resolve realpath
- validate containment under an allowed SonicForge root
- reject symlink escape
- use private staging permissions
- do not derive filenames by directly concatenating user prompts

Archive/model imports require traversal/symlink/bomb-size protections.

## 5. Subprocess boundary

Forbidden:

- `shell=True`
- untrusted shell strings
- prompt text in shell command lines when avoidable
- unvalidated executable paths from browser requests

Allowed:

- fixed/registered executables
- argv arrays
- bounded environment variables
- explicit cwd under permitted roots
- timeout/cancellation
- captured bounded logs

## 6. Worker isolation

Heavy third-party engine code runs outside the core process.

Worker rules:

- non-root by default
- no Host credentials except the minimal task/resource context required
- no direct ControlDeck DB access
- no project-root mount/path if a scoped staging copy/grant can be used
- bounded input/output directories
- explicit health/version handshake
- process termination on cancel/timeout when graceful cancel fails
- crash does not terminate SonicForge core

Containerization may be used for a worker when it materially improves dependency/security isolation, but containers are an implementation option rather than the public runtime contract.

## 7. Network policy

Default inference is local-first.

Workers should not make arbitrary outbound requests during inference.

Network access is expected for:

- explicit model/package installation
- update metadata
- user-configured sources

Model/package download domains should come from a configured allowlist/catalog rather than arbitrary URLs supplied by normal task requests.

Future remote inference providers require an explicit data-egress policy and separate user-facing configuration.

## 8. Voice cloning rights and consent

SonicForge cannot determine legal ownership of a voice. It must instead create an auditable workflow.

Before saving a reusable cloned/reference voice profile, require a confirmation such as:

```text
I have permission/right to use this reference voice for the intended purpose.
```

Store:

- consent confirmation timestamp
- confirmation version/text id
- creator/user identity reference when available through the local app context
- source asset id/hash
- optional notes/source attribution
- intended-use notes if the user supplies them

Do not store unnecessary identity claims about the speaker.

A rights confirmation is evidence of a user action, not a legal certification.

## 9. Voice profile safety UX

Visibly distinguish:

- built-in licensed voice
- user-owned/custom-trained voice
- reference/cloned voice
- voice-design synthetic profile
- imported unverified model

For cloned/imported voices, surface rights/license status in the library and export details.

## 10. Model licensing

Code license and model-weight license are separate fields.

Every engine/model catalog entry records:

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

SonicForge must not infer that model weights use the repository's code license.

Examples motivating this rule:

- Stable Audio code repository can be MIT while distributed model weights are governed by Stability AI model/community terms.
- Style-Bert-VITS2 code licensing does not automatically define the terms of a separately distributed voice model.
- custom GPT-SoVITS/Style-Bert models may inherit dataset/voice-specific obligations.

## 11. License acceptance

For gated/terms-required models:

- setup plan identifies the requirement
- UI shows source and terms link/reference
- user must explicitly accept where required by the source workflow
- acceptance is stored with terms/model revision
- setup resumes only after acceptance

Never fabricate or auto-submit an acceptance on behalf of the user.

## 12. Imported model policy

Imported custom model assets may have unknown provenance.

The import flow asks for/records:

- engine/type
- model files
- source/reference URL optional
- license/terms optional
- author/attribution optional
- rights note optional

If unknown, mark:

```text
license_status = unverified
provenance_status = unverified
```

Do not silently label it safe for commercial use.

## 13. Generated asset provenance

Every generated asset gets a provenance record before it becomes `succeeded`.

Required provenance:

```text
operation/capability
SonicForge version
adapter id/version
engine id/version
model id/revision
model-license record id
input asset ids/hashes
voice profile id when applicable
normalized generation parameters
seed when supported
created_at
Host job id when present
```

Prompt storage policy may be configurable for privacy, but a stable hash should be recorded if raw prompt text is omitted.

## 14. Lineage

Transform/edit/remix operations form a lineage graph:

```text
asset A -> remix -> asset B
asset B -> normalize -> asset C
voice reference X + text -> TTS -> asset D
```

Do not overwrite a source asset and erase lineage as the default behavior.

## 15. Export metadata

When exporting to a project, SonicForge may optionally write a sidecar manifest/profile when requested, e.g.:

```text
sound.wav
sound.sonicforge.json
```

Sidecar contains portable provenance/license attribution but no local absolute paths, tokens or private Host IDs that are meaningless outside the system.

## 16. Secrets

Potential secrets include:

- Hugging Face tokens
- gated model source credentials
- future remote provider keys
- ControlDeck service/request tokens

Rules:

- never store in repository/config examples
- use secret storage/env mechanism appropriate to deployment
- redact from logs/exceptions
- do not include in command-line arguments when safer alternatives exist
- never embed in model URLs

## 17. Logs

Logs may include:

- engine/runtime ids
- job/task ids
- durations/resource estimates
- status/error codes

Avoid logging by default:

- full spoken/transcribed text
- raw prompt text when privacy setting disables it
- voice reference content
- access tokens
- absolute Host project paths

Diagnostics can provide opt-in expanded context with clear warning.

## 18. Resource abuse controls

Enforce server-side limits:

- max request/body sizes
- max audio duration for synchronous endpoints
- max generation duration per profile
- max batch/variation count
- max active jobs/sessions per user/Add-on policy
- max setup operation concurrency = 1 per installation unless explicitly designed otherwise
- worker timeouts and cancellation

Do not rely solely on disabled browser controls.

## 19. Audio parser safety

Uploaded/generated audio is untrusted until validated.

Use bounded decoders/probers. Validate:

- file/container type
- duration
- channel/sample-rate sanity
- decoded size limits
- malformed metadata handling

Prefer running complex third-party decoders out-of-process where practical.

## 20. Dependency/supply-chain policy

- pin critical runtime versions
- lock runtime dependency sets
- prefer official upstream sources
- record engine source commit/tag/release
- review install scripts before adoption
- do not execute arbitrary `curl | sh` in automated setup
- Git repositories used as dependencies should be pinned to a revision, not floating main, in production lock state
- verify downloaded model artifact metadata/hashes where supported

## 21. Security review gates

Before enabling a new engine by default, review:

1. license/terms
2. install behavior
3. network behavior
4. filesystem assumptions
5. privilege assumptions
6. dependency conflicts
7. model loading safety
8. cancellation/termination
9. output validation
10. provenance coverage

## 22. No security regression for convenience

A setup button does not justify:

- executing arbitrary manifest commands in ControlDeck
- sharing ControlDeck's venv
- mounting full project roots into third-party workers
- passing Host cookies to embedded content
- running the whole service as root

If convenience conflicts with these boundaries, redesign the setup mechanism rather than weakening the boundary.