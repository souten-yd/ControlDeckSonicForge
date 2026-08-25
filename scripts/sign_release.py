from __future__ import annotations
import argparse, base64, hashlib, json, re
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
SCHEMA=1
ARTIFACT_RE=re.compile(r"^(?P<stem>[a-z0-9-]+)-(?P<version>[0-9][0-9A-Za-z.+-]*)-(?P<platform>[a-z0-9]+)-(?P<arch>[a-z0-9_]+)\.tar\.gz$")
def canonical_bytes(m): return json.dumps(m,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
def sha(path):
    h=hashlib.sha256(); size=0
    with path.open('rb') as f:
        while b:=f.read(1024*1024): h.update(b); size+=len(b)
    return h.hexdigest(),size
def keygen(path:Path):
    if path.exists(): raise SystemExit("private key already exists")
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700); key=Ed25519PrivateKey.generate(); path.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())); path.chmod(0o600)
    print(base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)).decode())
def sign(artifact:Path,feature_id:str,version:str,key_path:Path):
    m=ARTIFACT_RE.fullmatch(artifact.name)
    if not m or m.group('version')!=version: raise SystemExit("artifact identity mismatch")
    digest,size=sha(artifact); manifest={"schema_version":SCHEMA,"feature_id":feature_id,"version":version,"platform":m.group('platform'),"architecture":m.group('arch'),"artifact_name":artifact.name,"sha256":digest,"size_bytes":size}
    key=serialization.load_pem_private_key(key_path.read_bytes(),password=None)
    if not isinstance(key,Ed25519PrivateKey): raise SystemExit("signing key must be Ed25519")
    message=canonical_bytes(manifest); sig=key.sign(message)
    mp=artifact.with_name(artifact.name+'.manifest.json'); sp=artifact.with_name(artifact.name+'.manifest.json.sig'); mp.write_bytes(message); sp.write_text(base64.b64encode(sig).decode()+'\n')
    Ed25519PublicKey.from_public_bytes(key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)).verify(sig,message)
    print(json.dumps({"manifest":str(mp),"signature":str(sp),**manifest}))
def main():
    p=argparse.ArgumentParser(); s=p.add_subparsers(dest='cmd',required=True); k=s.add_parser('keygen'); k.add_argument('--private-key',required=True); x=s.add_parser('sign'); x.add_argument('--artifact',required=True); x.add_argument('--feature-id',default='sonic-forge'); x.add_argument('--version',required=True); x.add_argument('--private-key',required=True); a=p.parse_args()
    if a.cmd=='keygen': keygen(Path(a.private_key).expanduser())
    else: sign(Path(a.artifact).resolve(),a.feature_id,a.version,Path(a.private_key).expanduser())
if __name__=='__main__': main()
