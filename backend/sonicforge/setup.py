from __future__ import annotations

import asyncio
import hashlib
import json
import os
import platform
import shutil
import signal
import stat
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

STABILITY_TERMS = "stability-ai-community-license"
QWEN_CUSTOM_VOICE = "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"
QWEN_CLONE_BASE = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"
QWEN_VOICE_DESIGN = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
KOTOBA_WHISPER = "kotoba-tech/kotoba-whisper-v2.0"
WHISPER_TURBO = "openai/whisper-large-v3-turbo"
STABLE_AUDIO_SMALL_SFX = "stabilityai/stable-audio-3-small-sfx"
ACESTEP_DIT = "acestep-v15-turbo"
ACESTEP_LM = "acestep-5Hz-lm-0.6B"


class SetupError(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimeSpec:
    component: str
    runtime_id: str
    requirements: Path
    estimated_bytes: int
    extra_install: tuple[str, ...] = ()
    smoke_imports: tuple[str, ...] = ()
    prefetch_models: tuple[str, ...] = ()
    engine_models: tuple[str, ...] = ()
    required_terms: tuple[str, ...] = ()


def _relocate_virtualenv(runtime: Path, target: Path) -> int:
    bin_dir = runtime / "bin"
    if not bin_dir.is_dir():
        return 0
    stale_roots: set[bytes] = set()
    for path in bin_dir.iterdir():
        try:
            info = path.lstat()
        except FileNotFoundError:
            continue
        if not stat.S_ISREG(info.st_mode) or info.st_size > 1024 * 1024:
            continue
        with path.open("rb") as stream:
            first_line = stream.readline(4096)
        if not first_line.startswith(b"#!"):
            continue
        try:
            interpreter = Path(first_line[2:].strip().decode("utf-8"))
        except UnicodeDecodeError:
            continue
        root = interpreter.parent.parent
        if root != target and root.parent.name == ".staging":
            stale_roots.add(str(root).encode("utf-8"))
    if runtime.parent.name == ".staging":
        stale_roots.add(str(runtime).encode("utf-8"))
    if not stale_roots:
        return 0

    replacement = str(target).encode("utf-8")
    changed = 0
    candidates = list(bin_dir.iterdir())
    pyvenv = runtime / "pyvenv.cfg"
    if pyvenv.exists():
        candidates.append(pyvenv)
    for path in candidates:
        try:
            info = path.lstat()
        except FileNotFoundError:
            continue
        if not stat.S_ISREG(info.st_mode) or info.st_size > 1024 * 1024:
            continue
        if path != pyvenv and not path.name.startswith("activate"):
            with path.open("rb") as stream:
                if stream.read(2) != b"#!":
                    continue
        original = path.read_bytes()
        updated = original
        for stale in stale_roots:
            updated = updated.replace(stale, replacement)
        if updated == original:
            continue
        temporary = path.with_name(f".{path.name}.relocate-{uuid.uuid4().hex[:8]}")
        try:
            temporary.write_bytes(updated)
            temporary.chmod(stat.S_IMODE(info.st_mode))
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        changed += 1
    return changed


def detect_backend() -> str:
    if platform.system() == "Linux" and (
        Path("/dev/kfd").exists() or shutil.which("rocminfo")
    ):
        return "rocm"
    return "cpu"


def runtime_specs(
    settings: Settings, profile: str, explicit: list[str] | None = None
) -> list[RuntimeSpec]:
    components = list(explicit or PROFILE_COMPONENTS.get(profile, []))
    backend = detect_backend()
    specs: list[RuntimeSpec] = []

    if "speech-essentials" in components:
        runtime_id = "speech-rocm" if backend == "rocm" else "speech-cpu"
        specs.append(
            RuntimeSpec(
                "speech-essentials",
                runtime_id,
                settings.repo_root / "runtimes" / runtime_id / "requirements.txt",
                # Runtime + all models exposed by initial Speech/Voices UI.
                # This remains an intentionally conservative free-space estimate.
                18_000_000_000,
                smoke_imports=("torch", "qwen_tts", "transformers"),
                prefetch_models=(
                    QWEN_CUSTOM_VOICE,
                    QWEN_CLONE_BASE,
                    QWEN_VOICE_DESIGN,
                    KOTOBA_WHISPER,
                    WHISPER_TURBO,
                ),
            )
        )

    if "game-audio" in components:
        specs.append(
            RuntimeSpec(
                "game-audio",
                "game-audio-cpu",
                settings.repo_root
                / "runtimes"
                / "game-audio-cpu"
                / "requirements.txt",
                8_000_000_000,
                extra_install=(
                    "git+https://github.com/Stability-AI/stable-audio-3@a0b57f5483c4588f827f3552b7d5c6ca2a9687be",
                ),
                smoke_imports=("torch", "stable_audio_3"),
                prefetch_models=(STABLE_AUDIO_SMALL_SFX,),
                required_terms=(STABILITY_TERMS,),
            )
        )

    if "music" in components:
        specs.append(
            RuntimeSpec(
                "music",
                "music-rocm",
                settings.repo_root / "runtimes" / "music-rocm" / "requirements.txt",
                14_000_000_000,
                extra_install=(
                    "git+https://github.com/ace-step/ACE-Step-1.5@14c0211d5a0653b0f63e27686f4c3f151b4d8629",
                ),
                smoke_imports=("torch", "acestep"),
                engine_models=(ACESTEP_DIT, ACESTEP_LM),
            )
        )
    return specs


def _blockers(specs: list[RuntimeSpec]) -> list[str]:
    result: list[str] = []
    for spec in specs:
        if not spec.requirements.is_file():
            result.append(f"missing runtime requirements: {spec.runtime_id}")
        if spec.component == "music" and detect_backend() != "rocm":
            result.append(
                "Music pack currently requires the experimental Linux ROCm route"
            )
        if spec.component == "music" and not (3, 11) <= sys.version_info[:2] < (3, 13):
            result.append("ACE-Step runtime requires Python 3.11 or 3.12")
    return result


def status(session: Session) -> dict:
    rows = {row.id: row for row in session.query(SetupComponent).all()}
    return {
        "state": (
            "available"
            if rows.get("speech-essentials")
            and rows["speech-essentials"].state == "available"
            else "setup_required"
        ),
        "components": [
            {
                "id": cid,
                "state": (
                    rows[cid].state
                    if cid in rows
                    else ("available" if cid == "core" else "missing")
                ),
                "detail": rows[cid].detail if cid in rows else {},
            }
            for cid in ["core", "speech-essentials", "game-audio", "music"]
        ],
    }


def plan(
    settings: Settings, profile: str, explicit: list[str] | None = None
) -> dict:
    specs = runtime_specs(settings, profile, explicit)
    free = shutil.disk_usage(settings.data_dir).free
    terms = sorted({term for spec in specs for term in spec.required_terms})
    return {
        "profile": profile,
        "backend": detect_backend(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "free_bytes": free,
        "required_bytes_estimate": sum(s.estimated_bytes for s in specs),
        "components": [
            {
                "id": s.component,
                "runtime_id": s.runtime_id,
                "requirements": s.requirements.name,
                "estimated_bytes": s.estimated_bytes,
                "models": [*s.prefetch_models, *s.engine_models],
                "terms": list(s.required_terms),
            }
            for s in specs
        ],
        "warnings": (
            ["Music on ROCm is experimental until target-hardware evidence is recorded."]
            if any(s.component == "music" for s in specs)
            else []
        ),
        "blockers": _blockers(specs),
        "terms": terms,
    }


def _upsert(
    session: Session, component: str, state: str, detail: dict | None = None
) -> None:
    row = session.get(SetupComponent, component) or SetupComponent(id=component)
    row.state = state
    row.detail = detail or {}
    session.add(row)
    session.commit()


async def _run_process(
    argv: list[str],
    *,
    env: dict[str, str],
    cwd: Path | None = None,
    capture: bool = False,
) -> str:
    proc = await asyncio.create_subprocess_exec(
        *argv,
        cwd=str(cwd) if cwd else None,
        env=env,
        stdout=asyncio.subprocess.PIPE if capture else asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=os.name != "nt",
    )
    try:
        stdout, stderr = await proc.communicate()
    except asyncio.CancelledError:
        if proc.returncode is None:
            try:
                if os.name != "nt":
                    os.killpg(proc.pid, signal.SIGTERM)
                else:
                    proc.terminate()
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(proc.wait(), timeout=3)
            except TimeoutError:
                try:
                    if os.name != "nt":
                        os.killpg(proc.pid, signal.SIGKILL)
                    else:
                        proc.kill()
                except ProcessLookupError:
                    pass
                await proc.wait()
        raise
    if proc.returncode != 0:
        tail = (stderr or b"").decode(errors="replace")[-2000:]
        raise SetupError(
            tail or f"command failed with exit code {proc.returncode}: {argv[0]}"
        )
    return (stdout or b"").decode(errors="replace")[-65536:] if capture else ""


def _fingerprint(spec: RuntimeSpec) -> str:
    h = hashlib.sha256()
    h.update(spec.requirements.read_bytes())
    for item in spec.extra_install:
        h.update(b"\0")
        h.update(item.encode())
    for model in (*spec.prefetch_models, *spec.engine_models):
        h.update(b"\0model\0")
        h.update(model.encode())
    h.update(sys.version.encode())
    h.update(detect_backend().encode())
    return h.hexdigest()


def _runtime_bootstrap_python() -> str:
    """Select the host interpreter used to create heavyweight worker venvs.

    In a PyInstaller Release Bundle ``sys.executable`` is the SonicForge
    launcher, not a general-purpose Python interpreter.  Invoking it with
    ``-m venv`` therefore re-enters the SonicForge CLI.  MediaForge solves the
    same packaging boundary by locating the host's explicit ``python3``
    executable; keep that precedent here without sharing either product's
    environment.
    """
    executable = shutil.which("python3")
    if executable is None:
        raise SetupError("python3 is required to provision SonicForge runtimes")
    return executable


async def _prefetch_models(
    settings: Settings,
    python: Path,
    spec: RuntimeSpec,
    env: dict[str, str],
) -> list[dict]:
    if (
        not spec.prefetch_models
        or os.environ.get("SONICFORGE_SETUP_SKIP_MODEL_PREFETCH") == "1"
    ):
        return []
    code = (
        "import json,sys\n"
        "from pathlib import Path\n"
        "from huggingface_hub import snapshot_download\n"
        "out=[]\n"
        "for repo in json.loads(sys.argv[1]):\n"
        " p=Path(snapshot_download(repo_id=repo)).resolve()\n"
        " out.append({'repo':repo,'snapshot':str(p),'revision':p.name})\n"
        "print(json.dumps(out))"
    )
    raw = await _run_process(
        [str(python), "-c", code, json.dumps(list(spec.prefetch_models))],
        env=env,
        capture=True,
    )
    try:
        value = json.loads(raw.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError) as exc:
        raise SetupError("model prefetch returned invalid metadata") from exc
    return value if isinstance(value, list) else []


async def _prepare_engine_models(
    settings: Settings,
    python: Path,
    spec: RuntimeSpec,
    env: dict[str, str],
) -> list[dict]:
    if (
        not spec.engine_models
        or os.environ.get("SONICFORGE_SETUP_SKIP_MODEL_PREFETCH") == "1"
    ):
        return []
    if spec.component != "music":
        raise SetupError(f"unsupported engine model preparation: {spec.component}")
    checkpoint_dir = settings.models_dir / "ace-step"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    code = (
        "import json,sys\n"
        "from pathlib import Path\n"
        "from acestep.api.model_download import ensure_model_downloaded\n"
        "root=Path(sys.argv[1]).resolve()\n"
        "out=[]\n"
        "for model in json.loads(sys.argv[2]):\n"
        " p=Path(ensure_model_downloaded(model,str(root))).resolve()\n"
        " if not p.exists(): raise RuntimeError(f'model preparation returned missing path: {p}')\n"
        " out.append({'model':model,'path':str(p),'source':'acestep.model_download'})\n"
        "print(json.dumps(out))"
    )
    raw = await _run_process(
        [
            str(python),
            "-c",
            code,
            str(checkpoint_dir),
            json.dumps(list(spec.engine_models)),
        ],
        env=env,
        capture=True,
    )
    try:
        value = json.loads(raw.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError) as exc:
        raise SetupError("ACE-Step model preparation returned invalid metadata") from exc
    return value if isinstance(value, list) else []


async def _build_runtime(settings: Settings, spec: RuntimeSpec) -> dict:
    active = settings.runtime_dir / spec.runtime_id
    fingerprint = _fingerprint(spec)
    metadata_file = active / "sonicforge-runtime.json"
    if (active / "bin/python").exists() and metadata_file.exists():
        value = json.loads(metadata_file.read_text(encoding="utf-8"))
        if value.get("fingerprint") == fingerprint:
            _relocate_virtualenv(active, active)
            return value
    if settings.setup_test_mode:
        active.mkdir(parents=True, exist_ok=True)
        (active / "bin").mkdir(exist_ok=True)
        (active / "bin/python").write_text("test-mode\n" * 8, encoding="utf-8")
        meta = {
            "runtime_id": spec.runtime_id,
            "test_mode": True,
            "installed": True,
            "fingerprint": fingerprint,
            "models": [],
        }
        metadata_file.write_text(json.dumps(meta), encoding="utf-8")
        return meta

    op = uuid.uuid4().hex[:12]
    staging = settings.runtime_dir / ".staging" / f"{spec.runtime_id}-{op}"
    staging.parent.mkdir(parents=True, exist_ok=True)
    if staging.exists():
        shutil.rmtree(staging)
    env = os.environ.copy()
    env.setdefault("PIP_CACHE_DIR", str(settings.cache_dir / "pip"))
    env["HF_HOME"] = str(settings.models_dir / "huggingface")
    if spec.component == "music":
        env["ACESTEP_CHECKPOINTS_DIR"] = str(settings.models_dir / "ace-step")
    try:
        await _run_process([_runtime_bootstrap_python(), "-m", "venv", str(staging)], env=env)
        pip = staging / "bin/pip"
        python = staging / "bin/python"
        await _run_process([str(pip), "install", "--upgrade", "pip"], env=env)
        await _run_process([str(pip), "install", "-r", str(spec.requirements)], env=env)
        for package in spec.extra_install:
            await _run_process([str(pip), "install", "--no-deps", package], env=env)
        if spec.smoke_imports:
            code = "import importlib,sys; [importlib.import_module(x) for x in sys.argv[1:]]"
            await _run_process([str(python), "-c", code, *spec.smoke_imports], env=env)
        models = await _prefetch_models(settings, python, spec, env)
        models.extend(await _prepare_engine_models(settings, python, spec, env))
        meta = {
            "runtime_id": spec.runtime_id,
            "backend": detect_backend(),
            "requirements_sha256": hashlib.sha256(spec.requirements.read_bytes()).hexdigest(),
            "fingerprint": fingerprint,
            "sources": list(spec.extra_install),
            "models": models,
            "installed": True,
        }
        _relocate_virtualenv(staging, active)
        (staging / "sonicforge-runtime.json").write_text(
            json.dumps(meta, indent=2), encoding="utf-8"
        )
        backup = settings.runtime_dir / f".{spec.runtime_id}.previous"
        if backup.exists():
            shutil.rmtree(backup)
        if active.exists():
            active.rename(backup)
        staging.rename(active)
        return meta
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


async def apply(
    settings: Settings,
    session: Session,
    profile: str,
    explicit: list[str] | None = None,
    progress=None,
    accepted_terms: list[str] | None = None,
) -> dict:
    specs = runtime_specs(settings, profile, explicit)
    blockers = _blockers(specs)
    if blockers:
        raise SetupError("; ".join(blockers))
    accepted = set(accepted_terms or [])
    required = {term for spec in specs for term in spec.required_terms}
    missing_terms = sorted(required - accepted)
    if missing_terms:
        raise SetupError("terms_required:" + ",".join(missing_terms))
    if not specs:
        return {"profile": profile, "components": []}
    required_bytes = sum(spec.estimated_bytes for spec in specs)
    if shutil.disk_usage(settings.data_dir).free < required_bytes:
        raise SetupError("insufficient_disk_space")
    results = []
    for index, spec in enumerate(specs):
        _upsert(
            session,
            spec.component,
            "installing",
            {"runtime_id": spec.runtime_id},
        )
        if progress:
            await progress(index / len(specs), f"Installing {spec.component}")
        try:
            result = await _build_runtime(settings, spec)
        except asyncio.CancelledError:
            _upsert(
                session,
                spec.component,
                "missing",
                {"runtime_id": spec.runtime_id, "canceled": True},
            )
            raise
        except Exception as exc:
            _upsert(session, spec.component, "error", {"error": str(exc)[:300]})
            raise
        _upsert(session, spec.component, "available", result)
        results.append({"component": spec.component, **result})
    if progress:
        await progress(1.0, "Setup complete")
    return {"profile": profile, "components": results}
