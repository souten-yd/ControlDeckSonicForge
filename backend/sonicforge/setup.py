from __future__ import annotations

import asyncio
import json
import os
import platform
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from .config import Settings
from .db import SetupComponent

PROFILE_COMPONENTS = {
    "speech-essentials": ["speech-essentials"],
    "game-audio": ["game-audio"],
    "music": ["music"],
    "full-studio": ["speech-essentials", "game-audio", "music"],
    "cpu-essentials": ["speech-essentials"],
    "custom": [],
}


@dataclass(frozen=True)
class RuntimeSpec:
    component: str
    runtime_id: str
    requirements: Path
    estimated_bytes: int
    extra_install: tuple[str, ...] = ()


def detect_backend() -> str:
    if platform.system() == "Linux" and (Path("/dev/kfd").exists() or shutil.which("rocminfo")):
        return "rocm"
    return "cpu"


def runtime_specs(settings: Settings, profile: str, explicit: list[str] | None = None) -> list[RuntimeSpec]:
    components = list(explicit or PROFILE_COMPONENTS.get(profile, []))
    backend = detect_backend()
    specs: list[RuntimeSpec] = []
    if "speech-essentials" in components:
        req = settings.repo_root / "runtimes" / ("speech-rocm" if backend == "rocm" else "speech-cpu") / "requirements.txt"
        specs.append(RuntimeSpec("speech-essentials", f"speech-{backend}", req, 9_000_000_000 if backend == "rocm" else 6_000_000_000))
    if "game-audio" in components:
        req=settings.repo_root/"runtimes"/"game-audio-rocm"/"requirements.txt"
        specs.append(RuntimeSpec("game-audio", "game-audio-rocm", req, 5_000_000_000, ("git+https://github.com/Stability-AI/stable-audio-3@a0b57f5483c4588f827f3552b7d5c6ca2a9687be",)))
    if "music" in components:
        req=settings.repo_root/"runtimes"/"music-rocm"/"requirements.txt"
        specs.append(RuntimeSpec("music", "music-rocm", req, 12_000_000_000, ("git+https://github.com/ace-step/ACE-Step-1.5@14c0211d5a0653b0f63e27686f4c3f151b4d8629",)))
    return specs


def status(session: Session) -> dict:
    rows = {row.id: row for row in session.query(SetupComponent).all()}
    return {
        "state": "available" if rows.get("speech-essentials") and rows["speech-essentials"].state == "available" else "setup_required",
        "components": [
            {"id": cid, "state": rows[cid].state if cid in rows else ("available" if cid == "core" else "missing"), "detail": rows[cid].detail if cid in rows else {}}
            for cid in ["core", "speech-essentials", "game-audio", "music"]
        ],
    }


def plan(settings: Settings, profile: str, explicit: list[str] | None = None) -> dict:
    specs = runtime_specs(settings, profile, explicit)
    free = shutil.disk_usage(settings.data_dir).free
    return {
        "profile": profile,
        "backend": detect_backend(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "free_bytes": free,
        "required_bytes_estimate": sum(s.estimated_bytes for s in specs),
        "components": [
            {"id": s.component, "runtime_id": s.runtime_id, "requirements": s.requirements.name, "estimated_bytes": s.estimated_bytes}
            for s in specs
        ],
        "warnings": ["Game Audio and Music use pluggable external worker commands until a verified local engine pack is installed."] if any(s.component in {"game-audio","music"} for s in specs) else [],
        "terms": [],
    }


def _upsert(session: Session, component: str, state: str, detail: dict | None = None) -> None:
    row = session.get(SetupComponent, component) or SetupComponent(id=component)
    row.state = state
    row.detail = detail or {}
    session.add(row)
    session.commit()


def _build_runtime(settings: Settings, spec: RuntimeSpec) -> dict:
    active = settings.runtime_dir / spec.runtime_id
    if (active / "bin/python").exists() and (active / "sonicforge-runtime.json").exists():
        return json.loads((active / "sonicforge-runtime.json").read_text(encoding="utf-8"))
    if settings.setup_test_mode:
        active.mkdir(parents=True, exist_ok=True)
        (active / "bin").mkdir(exist_ok=True)
        (active / "bin/python").write_text("test-mode\n", encoding="utf-8")
        meta = {"runtime_id": spec.runtime_id, "test_mode": True, "installed": True}
        (active / "sonicforge-runtime.json").write_text(json.dumps(meta), encoding="utf-8")
        return meta
    op = uuid.uuid4().hex[:12]
    staging = settings.runtime_dir / ".staging" / f"{spec.runtime_id}-{op}"
    staging.parent.mkdir(parents=True, exist_ok=True)
    if staging.exists():
        shutil.rmtree(staging)
    subprocess.run([sys.executable, "-m", "venv", str(staging)], check=True)
    pip = staging / "bin/pip"
    env = os.environ.copy()
    env.setdefault("PIP_CACHE_DIR", str(settings.cache_dir / "pip"))
    subprocess.run([str(pip), "install", "--upgrade", "pip"], check=True, env=env)
    subprocess.run([str(pip), "install", "-r", str(spec.requirements)], check=True, env=env)
    for package in spec.extra_install:
        subprocess.run([str(pip), "install", "--no-deps", package], check=True, env=env)
    meta = {"runtime_id": spec.runtime_id, "backend": detect_backend(), "requirements": str(spec.requirements.name), "installed": True}
    (staging / "sonicforge-runtime.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    backup = settings.runtime_dir / f".{spec.runtime_id}.previous"
    if backup.exists():
        shutil.rmtree(backup)
    if active.exists():
        active.rename(backup)
    staging.rename(active)
    return meta


async def apply(settings: Settings, session: Session, profile: str, explicit: list[str] | None = None, progress=None) -> dict:
    specs = runtime_specs(settings, profile, explicit)
    if not specs:
        return {"profile": profile, "components": []}
    results = []
    for index, spec in enumerate(specs):
        _upsert(session, spec.component, "installing", {"runtime_id": spec.runtime_id})
        if progress:
            await progress(index / len(specs), f"Installing {spec.component}")
        try:
            result = await asyncio.to_thread(_build_runtime, settings, spec)
        except Exception as exc:
            _upsert(session, spec.component, "error", {"error": str(exc)[:300]})
            raise
        _upsert(session, spec.component, "available", result)
        results.append({"component": spec.component, **result})
    if progress:
        await progress(1.0, "Setup complete")
    return {"profile": profile, "components": results}
