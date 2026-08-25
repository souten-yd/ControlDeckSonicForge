import base64
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
