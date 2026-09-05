from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import Settings


MIGRATION_VERSION = 1
PRIMARY_TABLES = (
    "jobs",
    "provenance",
    "voices",
    "localization_batches",
    "meeting_sessions",
)
CHILD_TABLES = {
    "localization_lines": ("batch_id", "line_id"),
    "meeting_segments": ("meeting_id", "sequence"),
}


class LegacyDataError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _contained_file(root: Path, relative: str) -> Path:
    value = Path(relative)
    if value.is_absolute():
        raise LegacyDataError(f"legacy path is absolute: {relative}")
    resolved = (root / value).resolve()
    if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
        raise LegacyDataError(f"legacy file is missing or outside its data directory: {relative}")
    return resolved


def discover_legacy_data_dirs(settings: Settings) -> list[Path]:
    """Find only explicitly configured or known pre-Feature SonicForge storage.

    Early ControlDeck installations used ``<host-data>/sonicforge``.  Current
    generic Feature installations provide ``<host-data>/feature-data/sonic-forge``.
    The inference is deliberately limited to that exact managed layout; arbitrary
    sibling directories are never scanned or imported.
    """

    candidates: list[Path] = []
    explicit = os.environ.get("SONICFORGE_LEGACY_DATA_DIR")
    if explicit:
        candidates.append(Path(explicit).expanduser().resolve())

    managed = os.environ.get("CONTROL_DECK_FEATURE_DATA_DIR")
    if managed:
        managed_path = Path(managed).expanduser().resolve()
        if managed_path == settings.data_dir.resolve() and managed_path.parent.name == "feature-data":
            candidates.append((managed_path.parent.parent / "sonicforge").resolve())

    result: list[Path] = []
    for candidate in candidates:
        if candidate == settings.data_dir.resolve() or candidate in result:
            continue
        if (candidate / "sonicforge.db").is_file():
            result.append(candidate)
    return result


def _table_columns(connection: sqlite3.Connection, table: str) -> list[str]:
    return [str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")]


def _validate_schema(source: sqlite3.Connection, destination: sqlite3.Connection) -> None:
    required = {*PRIMARY_TABLES, *CHILD_TABLES, "assets"}
    source_tables = {
        str(row[0])
        for row in source.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    destination_tables = {
        str(row[0])
        for row in destination.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    missing = sorted(required - source_tables)
    if missing:
        raise LegacyDataError(f"legacy database is missing tables: {', '.join(missing)}")
    for table in sorted(required):
        source_columns = set(_table_columns(source, table))
        destination_columns = set(_table_columns(destination, table))
        if not source_columns <= destination_columns:
            extra = ", ".join(sorted(source_columns - destination_columns))
            raise LegacyDataError(f"legacy {table} has unsupported columns: {extra}")


def _row_values(row: sqlite3.Row, columns: list[str]) -> tuple[Any, ...]:
    return tuple(row[column] for column in columns)


def _insert_primary_rows(
    source: sqlite3.Connection,
    destination: sqlite3.Connection,
    table: str,
) -> int:
    columns = _table_columns(source, table)
    placeholders = ", ".join("?" for _ in columns)
    names = ", ".join(columns)
    inserted = 0
    for row in source.execute(f"SELECT {names} FROM {table}"):
        existing = destination.execute(
            f"SELECT {names} FROM {table} WHERE id = ?", (row["id"],)
        ).fetchone()
        values = _row_values(row, columns)
        if existing is not None:
            if _row_values(existing, columns) != values:
                raise LegacyDataError(f"conflicting {table} id: {row['id']}")
            continue
        destination.execute(
            f"INSERT INTO {table} ({names}) VALUES ({placeholders})", values
        )
        inserted += 1
    return inserted


def _insert_child_rows(
    source: sqlite3.Connection,
    destination: sqlite3.Connection,
    table: str,
    logical_key: tuple[str, str],
) -> int:
    columns = [column for column in _table_columns(source, table) if column != "id"]
    names = ", ".join(columns)
    placeholders = ", ".join("?" for _ in columns)
    inserted = 0
    for row in source.execute(f"SELECT {names} FROM {table}"):
        existing = destination.execute(
            f"SELECT {names} FROM {table} WHERE {logical_key[0]} = ? AND {logical_key[1]} = ?",
            (row[logical_key[0]], row[logical_key[1]]),
        ).fetchone()
        values = _row_values(row, columns)
        if existing is not None:
            if _row_values(existing, columns) != values:
                key = f"{row[logical_key[0]]}/{row[logical_key[1]]}"
                raise LegacyDataError(f"conflicting {table} key: {key}")
            continue
        destination.execute(
            f"INSERT INTO {table} ({names}) VALUES ({placeholders})", values
        )
        inserted += 1
    return inserted


def _referenced_files(source: sqlite3.Connection, legacy_root: Path) -> list[tuple[str, Path, str]]:
    files: dict[str, tuple[Path, str]] = {}
    for row in source.execute("SELECT relative_path, size_bytes, sha256 FROM assets"):
        relative = str(row["relative_path"])
        source_path = _contained_file(legacy_root, relative)
        if source_path.stat().st_size != int(row["size_bytes"]) or _sha256(source_path) != row["sha256"]:
            raise LegacyDataError(f"legacy asset does not match its database record: {relative}")
        files[relative] = (source_path, str(row["sha256"]))
    for row in source.execute("SELECT recipe FROM voices"):
        try:
            recipe = json.loads(row["recipe"] or "{}")
        except (TypeError, json.JSONDecodeError) as exc:
            raise LegacyDataError("legacy voice recipe is invalid") from exc
        relative = recipe.get("reference_audio") if isinstance(recipe, dict) else None
        if not isinstance(relative, str) or not relative:
            continue
        source_path = _contained_file(legacy_root, relative)
        files.setdefault(relative, (source_path, _sha256(source_path)))
    return [(relative, source_path, digest) for relative, (source_path, digest) in sorted(files.items())]


def _copy_missing_files(files: list[tuple[str, Path, str]], destination_root: Path) -> int:
    copied = 0
    staging_root = Path(tempfile.mkdtemp(prefix="legacy-import-", dir=destination_root / "tmp"))
    staged: list[tuple[Path, Path]] = []
    try:
        for relative, source_path, expected_sha in files:
            target = (destination_root / relative).resolve()
            if not target.is_relative_to(destination_root.resolve()):
                raise LegacyDataError(f"destination path escapes the data directory: {relative}")
            if target.exists():
                if not target.is_file() or _sha256(target) != expected_sha:
                    raise LegacyDataError(f"destination file conflicts with legacy data: {relative}")
                continue
            staged_path = staging_root / relative
            staged_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_path, staged_path)
            staged_path.chmod(0o600)
            if _sha256(staged_path) != expected_sha:
                raise LegacyDataError(f"copied legacy file failed verification: {relative}")
            staged.append((staged_path, target))
        for staged_path, target in staged:
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged_path, target)
            copied += 1
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)
    return copied


def _marker_path(settings: Settings, legacy_root: Path) -> Path:
    key = hashlib.sha256(str(legacy_root).encode("utf-8")).hexdigest()[:16]
    return settings.data_dir / "migrations" / f"legacy-data-v{MIGRATION_VERSION}-{key}.json"


def _write_marker(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def import_legacy_data(settings: Settings, legacy_root: Path) -> dict[str, Any] | None:
    legacy_root = legacy_root.expanduser().resolve()
    marker = _marker_path(settings, legacy_root)
    if marker.is_file():
        return None
    source_db = legacy_root / "sonicforge.db"
    if not source_db.is_file():
        return None

    settings.data_dir.mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "tmp").mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "migrations").mkdir(parents=True, exist_ok=True)
    lock_path = settings.data_dir / "migrations" / "legacy-data.lock"
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if marker.is_file():
            return None

        source = sqlite3.connect(f"file:{source_db}?mode=ro", uri=True)
        destination = sqlite3.connect(settings.db_path)
        source.row_factory = sqlite3.Row
        destination.row_factory = sqlite3.Row
        try:
            if source.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise LegacyDataError("legacy database integrity check failed")
            if destination.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise LegacyDataError("current database integrity check failed")
            _validate_schema(source, destination)
            files = _referenced_files(source, legacy_root)
            copied_files = _copy_missing_files(files, settings.data_dir)

            backup_dir = settings.data_dir / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            source_key = hashlib.sha256(str(legacy_root).encode("utf-8")).hexdigest()[:8]
            backup_path = backup_dir / (
                f"sonicforge-before-legacy-v{MIGRATION_VERSION}-{stamp}-{source_key}.db"
            )
            with sqlite3.connect(backup_path) as backup:
                destination.backup(backup)
            backup_path.chmod(0o600)

            counts: dict[str, int] = {}
            destination.execute("PRAGMA foreign_keys = ON")
            destination.execute("BEGIN IMMEDIATE")
            try:
                for table in PRIMARY_TABLES:
                    counts[table] = _insert_primary_rows(source, destination, table)
                for table, key in CHILD_TABLES.items():
                    counts[table] = _insert_child_rows(source, destination, table, key)
                counts["assets"] = _insert_primary_rows(source, destination, "assets")
                destination.commit()
            except Exception:
                destination.rollback()
                raise

            report: dict[str, Any] = {
                "migration_version": MIGRATION_VERSION,
                "source": str(legacy_root),
                "source_db_sha256": _sha256(source_db),
                "imported_at": datetime.now(timezone.utc).isoformat(),
                "inserted": counts,
                "copied_files": copied_files,
                "backup": str(backup_path.relative_to(settings.data_dir)),
                "legacy_source_preserved": True,
            }
            _write_marker(marker, report)
            return report
        finally:
            source.close()
            destination.close()


def migrate_discovered_legacy_data(settings: Settings) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for legacy_root in discover_legacy_data_dirs(settings):
        report = import_legacy_data(settings, legacy_root)
        if report is not None:
            reports.append(report)
    return reports
