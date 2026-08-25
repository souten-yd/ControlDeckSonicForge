from __future__ import annotations
import argparse, base64, hashlib, json
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from scripts.sign_release import canonical_bytes

def verify(artifact:Path,manifest_path:Path,signature_path:Path,public_b64:str,expected_feature='sonic-forge'):
    manifest=json.loads(manifest_path.read_text()); message=canonical_bytes(manifest)
    Ed25519PublicKey.from_public_bytes(base64.b64decode(public_b64)).verify(base64.b64decode(signature_path.read_text().strip()),message)
    if manifest['feature_id']!=expected_feature or manifest['artifact_name']!=artifact.name: raise ValueError('identity mismatch')
    data=artifact.read_bytes()
    if len(data)!=manifest['size_bytes'] or hashlib.sha256(data).hexdigest()!=manifest['sha256']: raise ValueError('artifact mismatch')
    return manifest

def main():
    p=argparse.ArgumentParser(); p.add_argument('--artifact',required=True); p.add_argument('--manifest',required=True); p.add_argument('--signature',required=True); p.add_argument('--public-key-base64',required=True); a=p.parse_args(); print(json.dumps(verify(Path(a.artifact),Path(a.manifest),Path(a.signature),a.public_key_base64)))
if __name__=='__main__': main()
