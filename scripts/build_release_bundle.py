from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import re
import shutil
import subprocess
import sys
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


def _pyinstaller_argv(requested: Path | None) -> list[str]:
    current_prefix = Path(sys.prefix).resolve()
    if requested is not None and requested.resolve().parent.parent != current_prefix:
        raise SystemExit("--pyinstaller must belong to the active SonicForge environment")
    if importlib.util.find_spec("PyInstaller") is None:
        raise SystemExit("PyInstaller is missing; install the SonicForge release extra")
    return [sys.executable, "-m", "PyInstaller"]


# 出来上がりが小さすぎたら、途中で終わっている。
#
# 実際に起きた: PyInstaller が OOM killer に落とされ、それでも exit code は 0 で
# 返り、2.4MB の tar.gz ができた（正常なら 30MB）。署名はマニフェストと実物が
# 一致するかしか見ないので、そのまま署名すれば**壊れた状態が正しいと証明される**。
# 気づかなければ公開して、適用時に壊れる。
#
# 数字は「明らかにおかしい」を弾くためのもので、正常値に張り付けない。
MIN_EXECUTABLE_BYTES = 10 * 1024 * 1024
MIN_ARTIFACT_BYTES = 10 * 1024 * 1024


def _check_executable(path: Path) -> None:
    """出来上がった実行ファイルが、大きさを持ち、実際に起動することを確かめる。

    大きさだけでは足りない。ビルド環境を取り違えると、大きさはあっても依存が
    欠けたものができる（実際に起きた: 別の venv で建てて `No module named
    'pydantic'` になった）。起動させるのが最も確かで、smoke は依存を全部踏む。
    """
    size = path.stat().st_size
    if size < MIN_EXECUTABLE_BYTES:
        raise SystemExit(
            f"built executable is only {size} bytes; the build did not finish"
        )
    smoke = [str(path), *_feature_manifest("0.0.0")["smoke_args"]]
    finished = subprocess.run(smoke, capture_output=True, timeout=300)
    if finished.returncode != 0:
        tail = finished.stderr.decode("utf-8", "replace")[-2000:]
        raise SystemExit(f"built executable failed its smoke run:\n{tail}")


def _check_artifact(path: Path, name: str) -> None:
    size = path.stat().st_size
    if size < MIN_ARTIFACT_BYTES:
        raise SystemExit(f"archive is only {size} bytes; the build did not finish")
    with tarfile.open(path, "r:gz") as archive:
        members = set(archive.getnames())
    required = {
        f"{name}/bin/sonicforge-core",
        f"{name}/control-deck-addon.json",
        f"{name}/control-deck-feature.json",
    }
    missing = sorted(required - members)
    if missing:
        raise SystemExit(f"archive is missing: {', '.join(missing)}")


def _feature_manifest(version: str) -> dict[str, object]:
    """Use the generic Release Bundle lifecycle shared with MediaForge.

    ControlDeck runs ``provision`` before selecting the new version, starting
    its service, and registering the Add-on manifest.  SonicForge's provision
    command converges the default Speech Essentials profile in the persistent
    feature-data directory, so a successful Feature install is immediately
    usable while optional Game Audio and Music packs remain explicit.
    """
    return {
        "schema_version": 1,
        "feature_id": "sonic-forge",
        "version": version,
        "platform": "linux",
        "architecture": "x86_64",
        "entrypoint": "bin/sonicforge-core",
        "addon_manifest": "control-deck-addon.json",
        "provision_args": ["provision"],
        "smoke_args": ["doctor"],
        "service_args": ["serve"],
        "health_url": "http://127.0.0.1:9140/health",
    }


# starlette は python_multipart を try 付きの遅延 import で読む。静的解析が拾い損ねると、
# 音声の取り込みだけが frozen build で 400 になる。明示的に取り込んでおく。
def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--version", required=True); parser.add_argument("--output-dir", type=Path, required=True); parser.add_argument("--pyinstaller", type=Path); args = parser.parse_args()
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}: raise SystemExit("only linux-x86_64 release bundles are currently supported")
    if VERSION_RE.fullmatch(args.version) is None: raise SystemExit("invalid bundle version")
    addon = json.loads((ROOT / "addon.json").read_text(encoding="utf-8")); package_text = (ROOT / "backend/sonicforge/__init__.py").read_text(encoding="utf-8"); match = re.search(r'__version__ = "([^"]+)"', package_text)
    if match is None or args.version != addon.get("version") or args.version != match.group(1): raise SystemExit("version mismatch between --version, addon.json and sonicforge.__version__")
    for required in (ROOT / "frontend", ROOT / "schemas", ROOT / "worker_packs", ROOT / "runtimes"):
        if not required.is_dir(): raise SystemExit(f"required bundle directory is missing: {required.name}")
    args.output_dir.mkdir(parents=True, exist_ok=True); name = f"control-deck-sonic-forge-{args.version}-linux-x86_64"
    with tempfile.TemporaryDirectory(prefix="sonicforge-bundle-") as temporary:
        work = Path(temporary); dist = work / "dist"; pyinstaller_argv = _pyinstaller_argv(args.pyinstaller)
        command = [*pyinstaller_argv, "--noconfirm", "--clean", "--onefile", "--name", "sonicforge-core", "--paths", str(ROOT / "backend"), "--collect-submodules", "sonicforge", "--collect-submodules", "python_multipart", "--distpath", str(dist), "--workpath", str(work / "build"), "--specpath", str(work), "--add-data", f"{ROOT / 'frontend'}:frontend", "--add-data", f"{ROOT / 'schemas'}:schemas", "--add-data", f"{ROOT / 'worker_packs'}:worker_packs", "--add-data", f"{ROOT / 'runtimes'}:runtimes", str(ROOT / "scripts/bundle_entrypoint.py")]
        subprocess.run(command, check=True, cwd=ROOT)
        bundle = work / name; _copy(dist / "sonicforge-core", bundle / "bin/sonicforge-core", 0o755)
        _check_executable(bundle / "bin/sonicforge-core")
        (bundle / "control-deck-addon.json").write_text(json.dumps(addon, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        feature = _feature_manifest(args.version)
        (bundle / "control-deck-feature.json").write_text(json.dumps(feature, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        artifact = args.output_dir / f"{name}.tar.gz"
        with tarfile.open(artifact, "w:gz", compresslevel=9) as archive: archive.add(bundle, arcname=name, recursive=True)
        _check_artifact(artifact, name)
        digest = _sha256(artifact); checksum = artifact.with_name(artifact.name + ".sha256"); checksum.write_text(f"{digest}  {artifact.name}\n", encoding="ascii")
        print(json.dumps({"artifact": str(artifact), "sha256": digest, "bytes": artifact.stat().st_size}))
    return 0


if __name__ == "__main__": raise SystemExit(main())
