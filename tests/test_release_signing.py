import base64
import json
import subprocess
import sys
from pathlib import Path
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from scripts.sign_release import sign
from scripts.verify_release import verify

def test_signed_release_and_tamper(tmp_path):
    artifact=tmp_path/'control-deck-sonic-forge-0.1.0-linux-x86_64.tar.gz'; artifact.write_bytes(b'abc')
    key=Ed25519PrivateKey.generate(); kp=tmp_path/'k.pem'; kp.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    sign(artifact,'sonic-forge','0.1.0',kp)
    pub=base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)).decode()
    mp=Path(str(artifact)+'.manifest.json'); sp=Path(str(artifact)+'.manifest.json.sig')
    assert verify(artifact,mp,sp,pub)['feature_id']=='sonic-forge'
    artifact.write_bytes(b'abd')
    with pytest.raises(ValueError): verify(artifact,mp,sp,pub)


def test_verify_release_cli_runs_from_repository_root(tmp_path):
    artifact = tmp_path / 'control-deck-sonic-forge-0.1.0-linux-x86_64.tar.gz'
    artifact.write_bytes(b'abc')
    key = Ed25519PrivateKey.generate()
    key_path = tmp_path / 'k.pem'
    key_path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    sign(artifact, 'sonic-forge', '0.1.0', key_path)
    public_key = base64.b64encode(key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )).decode()
    completed = subprocess.run(
        [
            sys.executable,
            'scripts/verify_release.py',
            '--artifact', str(artifact),
            '--manifest', str(artifact) + '.manifest.json',
            '--signature', str(artifact) + '.manifest.json.sig',
            '--public-key-base64', public_key,
            '--feature-id', 'sonic-forge',
            '--version', '0.1.0',
            '--platform', 'linux',
            '--architecture', 'x86_64',
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(completed.stdout)['feature_id'] == 'sonic-forge'
