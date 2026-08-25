from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import BinaryIO

from .config import Settings


def _int_env(name: str, default: int, *, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        return default
    return max(minimum, min(maximum, value))


def _writable_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / f".probe-{uuid.uuid4().hex}"
        probe.write_bytes(b"")
        probe.unlink()
        return True
    except OSError:
        return False


class AudioSpoolManager:
    """RAM-first ephemeral storage with transparent disk spill.

    `/dev/shm` is preferred on Linux because live audio is temporary and should
    not create avoidable SSD writes. This is deliberately a soft policy rather
    than a duration limit: when RAM-backed storage gets tight, new/in-flight
    spools migrate to the ordinary SonicForge temp directory instead of failing.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        mode = os.environ.get("SONICFORGE_SPOOL_MODE", "auto").strip().lower()
        self.mode = mode if mode in {"auto", "memory", "disk"} else "auto"
        self.disk_root = settings.data_dir / "tmp" / "spool"
        self.disk_root.mkdir(parents=True, exist_ok=True)
        explicit = os.environ.get("SONICFORGE_SPOOL_DIR")
        candidates: list[Path] = []
        if explicit:
            candidates.append(Path(explicit).expanduser())
        if os.name != "nt":
            candidates.append(Path("/dev/shm") / f"sonicforge-{os.getuid()}")
            runtime = os.environ.get("XDG_RUNTIME_DIR")
            if runtime:
                candidates.append(Path(runtime) / "sonicforge-spool")
        self.memory_root: Path | None = None
        if self.mode != "disk":
            for candidate in candidates:
                candidate = candidate.resolve()
                if _writable_dir(candidate):
                    self.memory_root = candidate
                    break
        if self.mode == "memory" and self.memory_root is None:
            # Explicit memory mode must not silently claim RAM storage while using
            # disk. Auto mode, in contrast, is intentionally portable.
            raise RuntimeError("SONICFORGE_SPOOL_MODE=memory requested but no RAM-backed spool directory is available")

        self.per_stream_soft_bytes = _int_env(
            "SONICFORGE_SPOOL_STREAM_MB", 64, minimum=4, maximum=4096
        ) * 1024**2
        self.ram_reserve_bytes = _int_env(
            "SONICFORGE_SPOOL_RAM_RESERVE_MB", 128, minimum=16, maximum=16384
        ) * 1024**2

    @property
    def ram_available(self) -> bool:
        return self.memory_root is not None

    def _memory_has_room(self, incoming: int = 0) -> bool:
        if self.memory_root is None:
            return False
        try:
            free = shutil.disk_usage(self.memory_root).free
        except OSError:
            return False
        return free - incoming >= self.ram_reserve_bytes

    def preferred_root(self, category: str) -> Path:
        if self.memory_root is not None and self._memory_has_room():
            root = self.memory_root / category
        else:
            root = self.disk_root / category
        root.mkdir(parents=True, exist_ok=True)
        return root

    def work_dir(self, category: str, name: str) -> Path:
        root = self.preferred_root(category)
        target = root / name
        target.mkdir(parents=True, exist_ok=True)
        return target

    def open(self, category: str, *, suffix: str = ".pcm") -> "AdaptiveSpoolFile":
        return AdaptiveSpoolFile(self, category=category, suffix=suffix)


class AdaptiveSpoolFile:
    def __init__(self, manager: AudioSpoolManager, *, category: str, suffix: str) -> None:
        self.manager = manager
        self.category = category
        self.suffix = suffix
        self.bytes_written = 0
        self._closed = False
        self._memory = bool(
            manager.memory_root is not None and manager._memory_has_room()
        )
        self.path = self._new_path(memory=self._memory)
        self._stream: BinaryIO = self.path.open("wb")

    def _new_path(self, *, memory: bool) -> Path:
        if memory and self.manager.memory_root is not None:
            root = self.manager.memory_root / self.category
        else:
            root = self.manager.disk_root / self.category
        root.mkdir(parents=True, exist_ok=True)
        return root / f"{uuid.uuid4().hex}{self.suffix}"

    @property
    def memory_backed(self) -> bool:
        return self._memory

    def _should_spill(self, incoming: int) -> bool:
        if not self._memory:
            return False
        if self.bytes_written + incoming > self.manager.per_stream_soft_bytes:
            return True
        return not self.manager._memory_has_room(incoming)

    def _spill(self) -> None:
        if not self._memory:
            return
        self._stream.flush()
        self._stream.close()
        old_path = self.path
        new_path = self._new_path(memory=False)
        try:
            with old_path.open("rb") as source, new_path.open("wb") as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)
            self.path = new_path
            self._stream = new_path.open("ab")
            self._memory = False
        finally:
            old_path.unlink(missing_ok=True)

    def write(self, data: bytes) -> int:
        if self._closed:
            raise ValueError("spool is closed")
        if self._should_spill(len(data)):
            self._spill()
        written = self._stream.write(data)
        self.bytes_written += written
        return written

    def flush(self) -> None:
        if not self._closed:
            self._stream.flush()

    def finalize(self) -> Path:
        if not self._closed:
            self._stream.flush()
            self._stream.close()
            self._closed = True
        return self.path

    def cleanup(self) -> None:
        if not self._closed:
            self._stream.close()
            self._closed = True
        self.path.unlink(missing_ok=True)

    def __enter__(self) -> "AdaptiveSpoolFile":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.finalize()
