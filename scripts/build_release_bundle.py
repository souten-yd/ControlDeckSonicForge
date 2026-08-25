from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")


def _copy(source: Path, destination: Path, mode: int = 0o644) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(source, destination); destination.chmod(mode)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024): h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--version", required=True); parser.add_argument("--output-dir", type=Path, required=True); parser.add_argument("--pyinstaller", type=Path, required=True); args = parser.parse_args()
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}: raise SystemExit("only linux-x86_64 release bundles are currently supported")
    if VERSION_RE.fullmatch(args.version) is None: raise SystemExit("invalid bundle version")
    addon = json.loads((ROOT / "addon.json").read_text(encoding="utf-8")); package_text = (ROOT / "backend/sonicforge/__init__.py").read_text(encoding="utf-8"); match = re.search(r'__version__ = "([^"]+)"', package_text)
    if match is None or args.version != addon.get("version") or args.version != match.group(1): raise SystemExit("version mismatch between --version, addon.json and sonicforge.__version__")
    for required in (ROOT / "frontend", ROOT / "schemas", ROOT / "worker_packs", ROOT / "runtimes"):
        if not required.is_dir(): raise SystemExit(f"required bundle directory is missing: {required.name}")
    args.output_dir.mkdir(parents=True, exist_ok=True); name = f"control-deck-sonic-forge-{args.version}-linux-x86_64"
    with tempfile.TemporaryDirectory(prefix="sonicforge-bundle-") as temporary:
        work = Path(temporary); dist = work / "dist"; pyinstaller_python = args.pyinstaller.parent / "python"; pyinstaller_argv = [str(pyinstaller_python), "-m", "PyInstaller"] if pyinstaller_python.is_file() else [str(args.pyinstaller)]
        command = [*pyinstaller_argv, "--noconfirm", "--clean", "--onefile", "--name", "sonicforge-core", "--paths", str(ROOT / "backend"), "--distpath", str(dist), "--workpath", str(work / "build"), "--specpath", str(work), "--add-data", f"{ROOT / 'frontend'}:frontend", "--add-data", f"{ROOT / 'schemas'}:schemas", "--add-data", f"{ROOT / 'worker_packs'}:worker_packs", "--add-data", f"{ROOT / 'runtimes'}:runtimes", str(ROOT / "scripts/bundle_entrypoint.py")]
        subprocess.run(command, check=True, cwd=ROOT)
        bundle = work / name; _copy(dist / "sonicforge-core", bundle / "bin/sonicforge-core", 0o755)
        (bundle / "control-deck-addon.json").write_text(json.dumps(addon, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        feature = {"schema_version": 1, "feature_id": "sonic-forge", "version": args.version, "platform": "linux", "architecture": "x86_64", "entrypoint": "bin/sonicforge-core", "addon_manifest": "control-deck-addon.json", "provision_args": ["doctor"], "smoke_args": ["doctor"], "service_args": ["serve"], "health_url": "http://127.0.0.1:9140/health"}
        (bundle / "control-deck-feature.json").write_text(json.dumps(feature, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        artifact = args.output_dir / f"{name}.tar.gz"
        with tarfile.open(artifact, "w:gz", compresslevel=9) as archive: archive.add(bundle, arcname=name, recursive=True)
        digest = _sha256(artifact); checksum = artifact.with_name(artifact.name + ".sha256"); checksum.write_text(f"{digest}  {artifact.name}\n", encoding="ascii")
        print(json.dumps({"artifact": str(artifact), "sha256": digest, "bytes": artifact.stat().st_size}))
    return 0


if __name__ == "__main__": raise SystemExit(main())
