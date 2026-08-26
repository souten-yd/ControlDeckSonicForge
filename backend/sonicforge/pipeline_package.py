from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

from .workers import WorkerError

MAX_PACKAGE_BYTES = 1024 * 1024 * 1024


def package_filename(value: str | None) -> str:
    if not value:
        return "sonicforge-package.zip"
    name = Path(value).name
    if name != value or name in {".", ".."} or "\x00" in name:
        raise WorkerError("package filename must be a plain file name")
    stem = Path(name).stem[:180] or "sonicforge-package"
    return f"{stem}.zip"


def create_package(
    *,
    source_audio: Path,
    target: Path,
    audio_name: str,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    source_audio = source_audio.resolve()
    target = target.resolve()
    if not source_audio.is_file():
        raise WorkerError("package source audio is missing")
    if Path(audio_name).name != audio_name or not audio_name:
        raise WorkerError("package audio entry name is invalid")
    target.parent.mkdir(parents=True, exist_ok=True)

    manifest_bytes = json.dumps(
        manifest,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    with zipfile.ZipFile(
        target,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6,
    ) as archive:
        archive.write(source_audio, arcname=f"audio/{audio_name}")
        archive.writestr("manifest.json", manifest_bytes)

    size = target.stat().st_size
    if size <= 0 or size > MAX_PACKAGE_BYTES:
        target.unlink(missing_ok=True)
        raise WorkerError("pipeline package size is invalid")
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    return {
        "size_bytes": size,
        "sha256": digest,
        "mime_type": "application/zip",
    }
