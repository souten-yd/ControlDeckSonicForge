from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import uuid
import wave
import zipfile
from pathlib import Path, PurePosixPath

from sqlalchemy.orm import Session

from .config import Settings
from .db import AppPreference, TtsModelPack

QWEN_ENGINE = "tts.qwen3"
GPT_SOVITS_ENGINE = "tts.gpt-sovits"
BASE_GPT_MODEL = "lj1995/GPT-SoVITS"
ENGINE_IDS = frozenset({QWEN_ENGINE, GPT_SOVITS_ENGINE})
MODEL_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
MAX_ARCHIVE_BYTES = 8 * 1024**3
MAX_EXPANDED_BYTES = 12 * 1024**3
MAX_FILES = 32
CHUNK_BYTES = 1024 * 1024


class ModelPackError(ValueError):
    pass


def _preference(session: Session, key: str, default: str) -> str:
    row = session.get(AppPreference, key)
    value = (row.value or {}).get("id") if row else None
    return str(value) if isinstance(value, str) and value else default


def preferences(session: Session) -> dict:
    return {
        "engine_id": _preference(session, "tts.engine", QWEN_ENGINE),
        "gpt_sovits_model_id": _preference(
            session, "tts.gpt_sovits.model", BASE_GPT_MODEL
        ),
    }


def set_preference(session: Session, *, engine_id: str, model_id: str | None) -> dict:
    if engine_id not in ENGINE_IDS:
        raise ModelPackError("unsupported TTS engine")
    if model_id is not None:
        if model_id != BASE_GPT_MODEL and session.get(TtsModelPack, model_id) is None:
            raise ModelPackError("GPT-SoVITS model pack does not exist")
        row = session.get(AppPreference, "tts.gpt_sovits.model") or AppPreference(
            key="tts.gpt_sovits.model"
        )
        row.value = {"id": model_id}
        session.add(row)
    row = session.get(AppPreference, "tts.engine") or AppPreference(key="tts.engine")
    row.value = {"id": engine_id}
    session.add(row)
    session.commit()
    return preferences(session)


def model_document(_settings: Settings, session: Session) -> dict:
    selected = preferences(session)["gpt_sovits_model_id"]
    base = {
        "id": BASE_GPT_MODEL,
        "name": "GPT-SoVITS v2 ProPlus",
        "engine_id": GPT_SOVITS_ENGINE,
        "license_id": "MIT",
        "source": "https://huggingface.co/lj1995/GPT-SoVITS",
        "built_in": True,
        "active": selected == BASE_GPT_MODEL,
        "size_bytes": None,
        "has_reference": False,
    }
    custom = []
    for row in session.query(TtsModelPack).order_by(TtsModelPack.created_at).all():
        manifest = dict(row.manifest or {})
        custom.append(
            {
                "id": row.id,
                "name": row.name,
                "engine_id": row.engine_id,
                "license_id": manifest.get("license_id"),
                "source": manifest.get("source"),
                "revision": manifest.get("revision"),
                "languages": manifest.get("languages", []),
                "built_in": False,
                "active": selected == row.id,
                "size_bytes": row.size_bytes,
                "archive_sha256": row.archive_sha256,
                "has_reference": bool(manifest.get("reference_audio")),
            }
        )
    return {"models": [base, *custom], "active_model_id": selected}


def _safe_member(info: zipfile.ZipInfo) -> PurePosixPath:
    if "\\" in info.filename:
        raise ModelPackError("model archive contains an unsafe path")
    name = PurePosixPath(info.filename)
    if (
        name.is_absolute()
        or not name.parts
        or any(part in {"", ".", ".."} for part in name.parts)
    ):
        raise ModelPackError("model archive contains an unsafe path")
    mode = info.external_attr >> 16
    if stat.S_ISLNK(mode):
        raise ModelPackError("model archive must not contain symbolic links")
    return name


def _manifest_path(root: Path, value: object, suffixes: set[str]) -> Path:
    if not isinstance(value, str) or not value:
        raise ModelPackError("model manifest is missing a required file")
    relative = _safe_member(zipfile.ZipInfo(value))
    target = (root / relative.as_posix()).resolve()
    if not target.is_relative_to(root.resolve()) or not target.is_file():
        raise ModelPackError("model manifest points to a missing file")
    if target.suffix.lower() not in suffixes:
        raise ModelPackError("model manifest names an unsupported file type")
    return target


def _validate_reference(path: Path) -> None:
    try:
        with wave.open(str(path), "rb") as audio:
            frame_rate = audio.getframerate()
            if frame_rate <= 0:
                raise ModelPackError("reference WAV has an invalid sample rate")
            duration = audio.getnframes() / frame_rate
            if audio.getnchannels() not in {1, 2} or not 1 <= duration <= 30:
                raise ModelPackError("reference WAV must be mono/stereo and 1 to 30 seconds")
    except (wave.Error, EOFError) as exc:
        raise ModelPackError("reference audio must be a valid PCM WAV") from exc


async def install(settings: Settings, session: Session, stream) -> dict:
    root = settings.models_dir / "gpt-sovits/custom"
    staging_root = root / ".staging"
    staging_root.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    archive = staging_root / f"{token}.zip"
    staging = staging_root / token
    digest = hashlib.sha256()
    archive_size = 0
    activated_target: Path | None = None
    committed = False
    try:
        with archive.open("wb") as sink:
            while True:
                chunk = await stream.read(CHUNK_BYTES)
                if not chunk:
                    break
                archive_size += len(chunk)
                if archive_size > MAX_ARCHIVE_BYTES:
                    raise ModelPackError("model archive is too large")
                digest.update(chunk)
                sink.write(chunk)
        if archive_size == 0:
            raise ModelPackError("model archive is empty")
        with zipfile.ZipFile(archive) as bundle:
            infos = [item for item in bundle.infolist() if not item.is_dir()]
            if not infos or len(infos) > MAX_FILES:
                raise ModelPackError("model archive has an invalid file count")
            if any(item.flag_bits & 0x1 for item in infos):
                raise ModelPackError("encrypted model archives are not supported")
            if sum(item.file_size for item in infos) > MAX_EXPANDED_BYTES:
                raise ModelPackError("expanded model archive is too large")
            normalized = [_safe_member(item).as_posix() for item in infos]
            if len(set(normalized)) != len(normalized):
                raise ModelPackError("model archive contains duplicate paths")
            staging.mkdir()
            for info in infos:
                relative = _safe_member(info)
                target = staging / relative.as_posix()
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(info) as source, target.open("wb") as sink:
                    shutil.copyfileobj(source, sink, CHUNK_BYTES)
        manifest_file = staging / "manifest.json"
        if not manifest_file.is_file() or manifest_file.stat().st_size > 64 * 1024:
            raise ModelPackError("model archive requires a small root manifest.json")
        try:
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ModelPackError("model manifest is invalid JSON") from exc
        if not isinstance(manifest, dict):
            raise ModelPackError("model manifest must be an object")
        slug = manifest.get("id")
        if not isinstance(slug, str) or MODEL_ID_RE.fullmatch(slug) is None:
            raise ModelPackError("model manifest id is invalid")
        model_id = f"gpt-sovits:{slug}"
        name = manifest.get("name")
        if not isinstance(name, str) or not name.strip() or len(name) > 160:
            raise ModelPackError("model manifest name is invalid")
        for field in ("license_id", "source"):
            value = manifest.get(field)
            if (
                not isinstance(value, str)
                or not value.strip()
                or len(value) > 1000
            ):
                raise ModelPackError(f"model manifest requires {field}")
        languages = manifest.get("languages", [])
        if (
            not isinstance(languages, list)
            or len(languages) > 2
            or any(language not in {"ja", "en"} for language in languages)
            or len(set(languages)) != len(languages)
        ):
            raise ModelPackError("model manifest languages must be unique ja/en values")
        if manifest.get("rights_confirmed") is not True:
            raise ModelPackError("model manifest requires explicit voice rights confirmation")
        if manifest.get("version") != "v2ProPlus":
            raise ModelPackError("model manifest version must be v2ProPlus")
        t2s = _manifest_path(staging, manifest.get("t2s_weights"), {".ckpt"})
        vits = _manifest_path(staging, manifest.get("vits_weights"), {".pth"})
        if t2s.stat().st_size < 1024 * 1024 or vits.stat().st_size < 1024 * 1024:
            raise ModelPackError("model weight files are unexpectedly small")
        if manifest.get("reference_audio") is not None:
            reference = _manifest_path(staging, manifest.get("reference_audio"), {".wav"})
            _validate_reference(reference)
            if not str(manifest.get("reference_text") or "").strip():
                raise ModelPackError("reference audio requires reference_text")
        if session.get(TtsModelPack, model_id) is not None:
            raise ModelPackError("a model pack with this id already exists")
        target = root / slug
        if target.exists():
            raise ModelPackError("model destination already exists")
        os.replace(staging, target)
        activated_target = target
        row = TtsModelPack(
            id=model_id,
            engine_id=GPT_SOVITS_ENGINE,
            name=name.strip(),
            relative_path=str(target.relative_to(settings.data_dir)),
            manifest=manifest,
            archive_sha256=digest.hexdigest(),
            size_bytes=sum(path.stat().st_size for path in target.rglob("*") if path.is_file()),
        )
        session.add(row)
        session.commit()
        committed = True
        return next(item for item in model_document(settings, session)["models"] if item["id"] == model_id)
    except zipfile.BadZipFile as exc:
        raise ModelPackError("uploaded model is not a valid ZIP archive") from exc
    finally:
        archive.unlink(missing_ok=True)
        shutil.rmtree(staging, ignore_errors=True)
        if activated_target is not None and not committed:
            shutil.rmtree(activated_target, ignore_errors=True)


def delete(settings: Settings, session: Session, model_id: str) -> None:
    row = session.get(TtsModelPack, model_id)
    if row is None:
        raise ModelPackError("model pack does not exist")
    if preferences(session)["gpt_sovits_model_id"] == model_id:
        raise ModelPackError("switch away from the active model before deleting it")
    root = (settings.models_dir / "gpt-sovits/custom").resolve()
    target = (settings.data_dir / row.relative_path).resolve()
    if not target.is_relative_to(root):
        raise ModelPackError("model pack path is outside managed storage")
    if not target.is_dir():
        raise ModelPackError("model pack files are missing")
    trash = root / f".delete-{target.name}-{uuid.uuid4().hex[:8]}"
    target.rename(trash)
    try:
        session.delete(row)
        session.commit()
    except BaseException:
        if trash.exists():
            trash.rename(target)
        raise
    shutil.rmtree(trash)


def worker_pack(settings: Settings, session: Session, model_id: str) -> dict | None:
    if model_id == BASE_GPT_MODEL:
        return None
    row = session.get(TtsModelPack, model_id)
    if row is None:
        raise ModelPackError("selected GPT-SoVITS model pack does not exist")
    root = (settings.data_dir / row.relative_path).resolve()
    managed = (settings.models_dir / "gpt-sovits/custom").resolve()
    if not root.is_relative_to(managed) or not root.is_dir():
        raise ModelPackError("selected GPT-SoVITS model files are missing")
    manifest = dict(row.manifest or {})
    return {
        "id": row.id,
        "name": row.name,
        "license_id": manifest["license_id"],
        "revision": manifest.get("revision") or row.archive_sha256,
        "rights_confirmed": True,
        "t2s_weights": str(_manifest_path(root, manifest["t2s_weights"], {".ckpt"})),
        "vits_weights": str(_manifest_path(root, manifest["vits_weights"], {".pth"})),
        "reference_audio": (
            str(_manifest_path(root, manifest["reference_audio"], {".wav"}))
            if manifest.get("reference_audio")
            else None
        ),
        "reference_text": manifest.get("reference_text"),
    }
