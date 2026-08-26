from __future__ import annotations

from pathlib import Path

from backend.sonicforge.config import Settings
from backend.sonicforge.spool import AudioSpoolManager


def settings(tmp_path: Path) -> Settings:
    return Settings(
        host="127.0.0.1",
        port=9140,
        data_dir=tmp_path / "data",
        cache_dir=tmp_path / "cache",
        repo_root=tmp_path,
        ui_locale="auto",
        enable_fake_worker=True,
        setup_test_mode=True,
        control_deck_url="http://127.0.0.1:8765",
    )


def test_ram_first_spool_uses_explicit_ephemeral_root(monkeypatch, tmp_path):
    ram = tmp_path / "ram"
    monkeypatch.setenv("SONICFORGE_SPOOL_DIR", str(ram))
    monkeypatch.setenv("SONICFORGE_SPOOL_MODE", "auto")
    monkeypatch.setenv("SONICFORGE_SPOOL_RAM_RESERVE_MB", "16")
    manager = AudioSpoolManager(settings(tmp_path))
    # The test directory is not real tmpfs, but an explicit operator override is
    # sufficient to verify routing semantics without depending on /dev/shm in CI.
    assert manager.ram_available is True
    spool = manager.open("voice", suffix=".pcm")
    spool.write(b"\x00\x00" * 100)
    path = spool.finalize()
    assert path.is_file()
    assert path.is_relative_to(ram.resolve())
    assert path.read_bytes() == b"\x00\x00" * 100
    path.unlink()


def test_large_live_spool_spills_to_disk_without_duration_failure(monkeypatch, tmp_path):
    ram = tmp_path / "ram"
    monkeypatch.setenv("SONICFORGE_SPOOL_DIR", str(ram))
    monkeypatch.setenv("SONICFORGE_SPOOL_MODE", "auto")
    monkeypatch.setenv("SONICFORGE_SPOOL_STREAM_MB", "4")
    monkeypatch.setenv("SONICFORGE_SPOOL_RAM_RESERVE_MB", "16")
    manager = AudioSpoolManager(settings(tmp_path))
    spool = manager.open("meeting", suffix=".pcm")
    first = b"a" * (3 * 1024 * 1024)
    second = b"b" * (2 * 1024 * 1024)
    spool.write(first)
    assert spool.memory_backed is True
    spool.write(second)
    assert spool.memory_backed is False
    path = spool.finalize()
    assert path.is_relative_to((settings(tmp_path).data_dir / "tmp" / "spool").resolve())
    assert path.stat().st_size == len(first) + len(second)
    with path.open("rb") as stream:
        assert stream.read(8) == b"a" * 8
        stream.seek(-8, 2)
        assert stream.read(8) == b"b" * 8
    path.unlink()


def test_disk_mode_never_claims_memory_backing(monkeypatch, tmp_path):
    monkeypatch.setenv("SONICFORGE_SPOOL_DIR", str(tmp_path / "ram"))
    monkeypatch.setenv("SONICFORGE_SPOOL_MODE", "disk")
    manager = AudioSpoolManager(settings(tmp_path))
    assert manager.ram_available is False
    spool = manager.open("voice")
    assert spool.memory_backed is False
    path = spool.finalize()
    assert path.is_relative_to(manager.disk_root.resolve())
    path.unlink()
