from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import re
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from scripts.sign_release import ARTIFACT_RE, canonical_bytes

EXPECTED_KEYS = {
    "schema_version",
    "feature_id",
    "version",
    "platform",
    "architecture",
    "artifact_name",
    "sha256",
    "size_bytes",
}
FEATURE_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _decode_exact_base64(value: str, size: int, label: str) -> bytes:
    try:
        decoded = base64.b64decode(value.strip(), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"{label} is not valid base64") from exc
    if len(decoded) != size:
        raise ValueError(f"{label} has an invalid length")
    return decoded


def _load_manifest(path: Path) -> tuple[dict, bytes]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("release manifest is invalid") from exc
    if not isinstance(value, dict) or set(value) != EXPECTED_KEYS:
        raise ValueError("release manifest schema is invalid")
    canonical = canonical_bytes(value)
    if raw not in {canonical, canonical + b"\n"}:
        raise ValueError("release manifest is not canonical JSON")
    if value["schema_version"] != 1:
        raise ValueError("unsupported release manifest schema")
    if not isinstance(value["feature_id"], str) or FEATURE_RE.fullmatch(value["feature_id"]) is None:
        raise ValueError("release feature_id is invalid")
    if not isinstance(value["version"], str) or VERSION_RE.fullmatch(value["version"]) is None:
        raise ValueError("release version is invalid")
    if not isinstance(value["platform"], str) or not value["platform"]:
        raise ValueError("release platform is invalid")
    if not isinstance(value["architecture"], str) or not value["architecture"]:
        raise ValueError("release architecture is invalid")
    if not isinstance(value["artifact_name"], str) or Path(value["artifact_name"]).name != value["artifact_name"]:
        raise ValueError("release artifact_name is invalid")
    if not isinstance(value["sha256"], str) or SHA256_RE.fullmatch(value["sha256"]) is None:
        raise ValueError("release sha256 is invalid")
    if isinstance(value["size_bytes"], bool) or not isinstance(value["size_bytes"], int) or value["size_bytes"] < 0:
        raise ValueError("release size_bytes is invalid")
    return value, canonical


def verify(
    artifact: Path,
    manifest_path: Path,
    signature_path: Path,
    public_b64: str,
    expected_feature: str = "sonic-forge",
    *,
    expected_version: str | None = None,
    expected_platform: str | None = None,
    expected_architecture: str | None = None,
):
    artifact = artifact.resolve()
    if not artifact.is_file():
        raise ValueError("release artifact is missing")
    manifest, message = _load_manifest(manifest_path)

    public_raw = _decode_exact_base64(public_b64, 32, "publisher public key")
    try:
        signature_raw = _decode_exact_base64(
            signature_path.read_text(encoding="ascii"), 64, "release signature"
        )
    except OSError as exc:
        raise ValueError("release signature is missing") from exc
    try:
        Ed25519PublicKey.from_public_bytes(public_raw).verify(signature_raw, message)
    except (InvalidSignature, ValueError) as exc:
        raise ValueError("release signature verification failed") from exc

    match = ARTIFACT_RE.fullmatch(artifact.name)
    if match is None:
        raise ValueError("release artifact filename is invalid")
    filename_feature = match.group("stem")
    expected_stem = f"control-deck-{expected_feature}"
    if filename_feature != expected_stem:
        raise ValueError("release artifact filename does not match feature")
    inferred = {
        "feature_id": expected_feature,
        "version": match.group("version"),
        "platform": match.group("platform"),
        "architecture": match.group("arch"),
        "artifact_name": artifact.name,
    }
    if any(manifest[key] != value for key, value in inferred.items()):
        raise ValueError("signed release context does not match the selected artifact")
    if expected_version is not None and manifest["version"] != expected_version:
        raise ValueError("signed release version does not match expected version")
    if expected_platform is not None and manifest["platform"] != expected_platform:
        raise ValueError("signed release platform does not match expected platform")
    if (
        expected_architecture is not None
        and manifest["architecture"] != expected_architecture
    ):
        raise ValueError("signed release architecture does not match expected architecture")

    digest = hashlib.sha256()
    size = 0
    with artifact.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    if size != manifest["size_bytes"] or digest.hexdigest() != manifest["sha256"]:
        raise ValueError("release artifact integrity check failed")
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--signature", required=True)
    parser.add_argument("--public-key-base64", required=True)
    parser.add_argument("--feature-id", default="sonic-forge")
    parser.add_argument("--version")
    parser.add_argument("--platform")
    parser.add_argument("--architecture")
    args = parser.parse_args()
    print(
        json.dumps(
            verify(
                Path(args.artifact),
                Path(args.manifest),
                Path(args.signature),
                args.public_key_base64,
                args.feature_id,
                expected_version=args.version,
                expected_platform=args.platform,
                expected_architecture=args.architecture,
            ),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
