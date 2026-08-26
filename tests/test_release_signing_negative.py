import base64
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from scripts.sign_release import canonical_bytes, sign
from scripts.verify_release import verify


def make_signed(tmp_path: Path):
    artifact = tmp_path / "control-deck-sonic-forge-0.1.0-linux-x86_64.tar.gz"
    artifact.write_bytes(b"abc")
    key = Ed25519PrivateKey.generate()
    key_path = tmp_path / "publisher.pem"
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    sign(artifact, "sonic-forge", "0.1.0", key_path)
    public_key = base64.b64encode(
        key.public_key().public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )
    ).decode()
    manifest_path = Path(str(artifact) + ".manifest.json")
    signature_path = Path(str(artifact) + ".manifest.json.sig")
    return artifact, key, public_key, manifest_path, signature_path


def resign(manifest_path: Path, signature_path: Path, key: Ed25519PrivateKey, manifest: dict):
    message = canonical_bytes(manifest)
    manifest_path.write_bytes(message + b"\n")
    signature_path.write_text(base64.b64encode(key.sign(message)).decode() + "\n")


def test_context_fields_are_bound_even_with_valid_signature(tmp_path):
    artifact, key, public_key, manifest_path, signature_path = make_signed(tmp_path)
    baseline = json.loads(manifest_path.read_text())

    mutations = [
        {"feature_id": "other-feature"},
        {"version": "0.2.0"},
        {"platform": "windows"},
        {"architecture": "aarch64"},
        {"artifact_name": "control-deck-sonic-forge-0.1.0-linux-aarch64.tar.gz"},
        {"size_bytes": baseline["size_bytes"] + 1},
        {"sha256": "0" * 64},
    ]
    for change in mutations:
        manifest = {**baseline, **change}
        resign(manifest_path, signature_path, key, manifest)
        with pytest.raises(ValueError):
            verify(artifact, manifest_path, signature_path, public_key)


def test_wrong_key_and_malformed_signature_fail_closed(tmp_path):
    artifact, _key, public_key, manifest_path, signature_path = make_signed(tmp_path)
    wrong_key = Ed25519PrivateKey.generate()
    wrong_public = base64.b64encode(
        wrong_key.public_key().public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )
    ).decode()
    with pytest.raises(ValueError):
        verify(artifact, manifest_path, signature_path, wrong_public)

    signature_path.write_text("not-base64!\n")
    with pytest.raises(ValueError):
        verify(artifact, manifest_path, signature_path, public_key)


def test_noncanonical_manifest_is_rejected(tmp_path):
    artifact, key, public_key, manifest_path, signature_path = make_signed(tmp_path)
    manifest = json.loads(manifest_path.read_text())
    signature_path.write_text(
        base64.b64encode(key.sign(canonical_bytes(manifest))).decode() + "\n"
    )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    with pytest.raises(ValueError):
        verify(artifact, manifest_path, signature_path, public_key)
