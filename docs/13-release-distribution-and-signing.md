# Release Distribution and Publisher Signing

Status: Normative target contract  
Date: 2026-08-25

## 1. Decision

SonicForge adopts the **publisher-signature release model used by current MediaForge** rather than a per-release SHA-256 pin in ControlDeck.

The trust anchor is the SonicForge publisher's **Ed25519 public key**. SHA-256 remains important, but only as the artifact-integrity value bound inside a signed release manifest.

This removes the old operational coupling where every SonicForge release would otherwise require editing ControlDeck merely to replace a trusted checksum.

## 2. Important Host compatibility note

During the 2026-08-25 review:

- current MediaForge `main` contains `scripts/sign_release.py` and its v0.6.7 release is documented as the first publisher-signature release;
- the currently inspected ControlDeck `main` still contains the older per-artifact `sha256` trusted-catalog verifier.

Therefore SonicForge targets the **signature-aware generic Release Bundle Feature contract**. Do not reintroduce a permanent SonicForge per-release SHA pin as a workaround. Until the signature-aware Host verifier is present, signed-release installation is a Host compatibility blocker and must be recorded as such.

## 3. Signed manifest

Mirror MediaForge's canonical manifest schema unless the generic ControlDeck contract evolves before implementation:

```json
{
  "schema_version": 1,
  "feature_id": "sonic-forge",
  "version": "0.1.0",
  "platform": "linux",
  "architecture": "x86_64",
  "artifact_name": "control-deck-sonic-forge-0.1.0-linux-x86_64.tar.gz",
  "sha256": "<64 hex characters>",
  "size_bytes": 12345678
}
```

The signed message is the **canonical JSON manifest**, not only the digest.

Canonical encoding follows the MediaForge precedent:

```python
json.dumps(
    manifest,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=True,
).encode("utf-8")
```

This encoding is part of the wire contract. The verifier must verify the exact canonical bytes rather than reformatting arbitrarily.

## 4. Why the identity fields are signed

Signing only a tarball digest proves possession of the signing key for those bytes but does not by itself bind the bytes to the expected product/release context.

The signed manifest binds:

- `feature_id`
- `version`
- `platform`
- `architecture`
- `artifact_name`
- `sha256`
- `size_bytes`

The Host must also reject downgrades according to its generic feature policy. A valid signature is not permission to install an unexpected old version, another feature's bundle, or another platform's artifact.

## 5. Release assets

A SonicForge release should publish at least:

```text
control-deck-sonic-forge-<version>-<platform>-<arch>.tar.gz
control-deck-sonic-forge-<version>-<platform>-<arch>.tar.gz.manifest.json
control-deck-sonic-forge-<version>-<platform>-<arch>.tar.gz.manifest.json.sig
```

An adjacent `.sha256` may still be published for human/debugging/tool interoperability, but it is **not the publisher trust anchor**.

## 6. Key lifecycle

### Private key

- Ed25519 private key.
- Generated once for the publisher identity.
- Never committed to this repository.
- Never bundled into SonicForge.
- Stored with restrictive permissions and preferably in a dedicated release-signing secret/system.
- Build/test jobs that do not publish a release do not receive the key.
- Signing dependency belongs to the release-build environment, not SonicForge core runtime.

### Public key

- Raw Ed25519 public key encoded as Base64, matching the generic ControlDeck trusted publisher contract.
- Registered in ControlDeck's trusted catalog/publisher metadata once, not changed for every release.
- Public key changes are an explicit trust-rotation event, not an ordinary release.

### Rotation

Do not invent a SonicForge-only key-id protocol. Until the generic Host contract supports multi-key rotation, rotate through an explicit coordinated ControlDeck trusted-publisher update with a documented transition/recovery process.

## 7. Bundle identity

The release bundle itself still contains the generic ControlDeck feature package manifest such as `control-deck-feature.json` plus SonicForge `addon.json`.

The following versions must agree before a release can be signed/published:

```text
release tag/version
signed manifest version
control-deck-feature.json version
addon.json version
SonicForge package __version__
```

A mismatch is a build failure.

## 8. Installation verification order

Target Host flow:

```text
resolve trusted release metadata
  -> choose exact platform/architecture artifact
  -> download bounded signed manifest + signature
  -> validate manifest schema and expected identity
  -> verify Ed25519 signature using trusted publisher public key
  -> reject forbidden downgrade
  -> download bounded artifact
  -> verify size_bytes
  -> verify SHA-256 from the signed manifest
  -> safe archive extraction into staging
  -> validate control-deck-feature.json
  -> validate addon.json identity/version/capability allowlist
  -> bounded provision/smoke test
  -> side-by-side version install
  -> health check
  -> atomic current switch
```

No code from the bundle is executed before publisher signature, identity and artifact-integrity checks pass.

## 9. Capability trust remains separate

Publisher signing means "this bundle was signed by the trusted SonicForge publisher". It does **not** mean the Add-on receives every Host privilege.

ControlDeck still owns a generic allowlist for SonicForge's permitted Host capabilities. A newly signed SonicForge release that asks for a capability outside that allowlist must fail closed until a deliberate generic Host trust update is made.

## 10. Provisioning separation

The release bundle should contain the lightweight SonicForge core and setup orchestrator, not multi-gigabyte model/runtime environments.

After signed bundle installation:

```text
signed lightweight SonicForge bundle verified and extracted to staging
  -> ControlDeck invokes SonicForge `provision`
  -> default Speech Essentials converges in persistent feature data
  -> ControlDeck runs `doctor` and atomically selects the staged version
  -> ControlDeck starts the service and checks health
  -> ControlDeck registers the Add-on; failure restores the previous version
  -> optional Game Audio / Music packs
```

Heavy runtimes/models remain SonicForge-managed, independently versioned and recoverable.
They are downloaded by SonicForge's provisioner and are not embedded in or
trusted merely because of the signed lightweight bundle. Provision failure
must prevent activation/registration and preserve the previous known-good
version, matching the MediaForge Release Bundle lifecycle.

## 11. Model/runtime artifact integrity

Publisher signing of the SonicForge release does not automatically authenticate third-party models or packages.

For runtime/model acquisition SonicForge records and verifies, where available:

- immutable upstream revision
- expected file digest
- source/repository identity
- model license/terms record
- download size
- runtime lock/fingerprint

For SonicForge-authored runtime-pack metadata distributed separately in the future, prefer the same publisher-signature pattern instead of an untrusted mutable JSON catalog.

## 12. Failure behavior

Fail closed for:

- unknown/untrusted publisher key
- malformed or invalid Base64 signature
- signature mismatch
- unsupported manifest schema
- wrong `feature_id`
- wrong version/platform/architecture/artifact name
- artifact size mismatch
- artifact SHA-256 mismatch
- downgrade rejected by Host policy
- unsafe archive entries
- package/Add-on identity mismatch
- excessive Host capability request
- provision/smoke/health failure

The previous active version remains current until the new version is fully validated.

## 13. Required tests

At minimum:

```text
valid signed release succeeds
single-byte manifest tamper fails
single-byte artifact tamper fails
wrong feature id fails
wrong version fails
wrong platform/architecture fails
wrong artifact name/size fails
signature by another key fails
malformed signature fails
old valid signed release is rejected as downgrade when policy requires
capability escalation still fails despite valid signature
failed provision leaves previous current version active
```

Also test release signing itself against a generated disposable test key. Never use the real publisher private key in unit tests.

## 14. Release CI

Recommended release pipeline:

```text
test/build
  -> build lightweight release bundle
  -> verify package/addon version identity
  -> generate canonical manifest
  -> sign manifest with protected Ed25519 publisher key
  -> self-verify signature
  -> publish artifact + manifest + signature
  -> verify published assets from a clean consumer path
```

The signing step runs only for an authorized release event.

## 15. Critical design conclusion

The old per-release SHA pin provided strong integrity for one exact file but created unnecessary ControlDeck/Add-on release coupling. Publisher signatures retain content integrity through the signed SHA-256 while moving release authorization to a stable publisher identity. For independently evolving Add-ons such as MediaForge and SonicForge, this is the better long-term contract.
