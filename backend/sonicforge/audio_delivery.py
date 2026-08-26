from __future__ import annotations

import asyncio
import hashlib
import json
import mimetypes
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .audio import inspect_wav
from .db import Asset, Job, Provenance
from .host.client import ControlDeckHostClient, HostApiError
from .host.files import commit_file
from .jobs import HostedExecution, JobManager

GRANT_PATTERN = r"^grant:[A-Za-z0-9._:-]{1,256}$"
MAX_DERIVED_AUDIO_BYTES = 1024 * 1024 * 1024
MAX_PROBE_BYTES = 64 * 1024


@dataclass(frozen=True)
class DeliveryProfile:
    id: str
    label: str
    extension: str
    mime_type: str
    ffmpeg_args: tuple[str, ...]
    purpose: str


PROFILES: dict[str, DeliveryProfile] = {
    "master-wav": DeliveryProfile(
        "master-wav", "Master WAV 48 kHz / 24-bit", ".wav", "audio/wav",
        ("-ar", "48000", "-c:a", "pcm_s24le"), "editing/master archive",
    ),
    "voice-wav": DeliveryProfile(
        "voice-wav", "Voice WAV 48 kHz mono / 16-bit", ".wav", "audio/wav",
        ("-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le"), "game dialogue/voice",
    ),
    "unity-sfx": DeliveryProfile(
        "unity-sfx", "Unity SFX WAV 48 kHz / 16-bit", ".wav", "audio/wav",
        ("-ar", "48000", "-c:a", "pcm_s16le"), "Unity source SFX asset",
    ),
    "unity-bgm": DeliveryProfile(
        "unity-bgm", "Unity BGM OGG 48 kHz", ".ogg", "audio/ogg",
        ("-ar", "48000", "-c:a", "libvorbis", "-q:a", "5"), "Unity compressed BGM asset",
    ),
    "unreal-sfx": DeliveryProfile(
        "unreal-sfx", "Unreal WAV 48 kHz / 16-bit", ".wav", "audio/wav",
        ("-ar", "48000", "-c:a", "pcm_s16le"), "Unreal import/source audio",
    ),
    "godot-sfx": DeliveryProfile(
        "godot-sfx", "Godot SFX WAV 48 kHz / 16-bit", ".wav", "audio/wav",
        ("-ar", "48000", "-c:a", "pcm_s16le"), "Godot source SFX asset",
    ),
    "godot-bgm": DeliveryProfile(
        "godot-bgm", "Godot BGM OGG 48 kHz", ".ogg", "audio/ogg",
        ("-ar", "48000", "-c:a", "libvorbis", "-q:a", "5"), "Godot streaming BGM asset",
    ),
    "web-mobile": DeliveryProfile(
        "web-mobile", "Web / Mobile MP3 160 kbps", ".mp3", "audio/mpeg",
        ("-ar", "48000", "-c:a", "libmp3lame", "-b:a", "160k"), "broad browser/mobile playback",
    ),
    "m5-wav": DeliveryProfile(
        "m5-wav", "M5 WAV 16 kHz mono / 16-bit", ".wav", "audio/wav",
        ("-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le"), "M5 offline/turn playback",
    ),
}


class AudioExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile: Literal[
        "master-wav", "voice-wav", "unity-sfx", "unity-bgm",
        "unreal-sfx", "godot-sfx", "godot-bgm", "web-mobile", "m5-wav",
    ]
    filename: str | None = Field(default=None, min_length=1, max_length=240)
    project_output_grant: str | None = Field(default=None, pattern=GRANT_PATTERN)


def profile_document() -> list[dict[str, str]]:
    return [
        {
            "id": value.id,
            "label": value.label,
            "extension": value.extension,
            "mime_type": value.mime_type,
            "purpose": value.purpose,
        }
        for value in PROFILES.values()
    ]


def _safe_filename(value: str | None, profile: DeliveryProfile, source_asset_id: str) -> str:
    if value:
        name = Path(value).name
        if name != value or name in {".", ".."} or "\x00" in name:
            raise ValueError("filename must be a plain file name")
        stem = Path(name).stem[:180] or "audio"
    else:
        stem = source_asset_id.split(":", 1)[-1][:80]
    return f"{stem}{profile.extension}"


def ffmpeg_argv(ffmpeg: str, source: Path, target: Path, profile: DeliveryProfile) -> list[str]:
    return [
        ffmpeg,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-vn",
        *profile.ffmpeg_args,
        str(target),
    ]


async def _run_bounded(argv: list[str], *, timeout: float = 180.0) -> bytes:
    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=os.name != "nt",
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except (asyncio.CancelledError, TimeoutError):
        if proc.returncode is None:
            proc.kill()
        await proc.wait()
        raise
    if proc.returncode != 0:
        raise RuntimeError(stderr.decode(errors="replace")[-2000:] or f"command exited {proc.returncode}")
    return stdout


async def _inspect_derived(path: Path, profile: DeliveryProfile) -> dict[str, Any]:
    if path.stat().st_size <= 0 or path.stat().st_size > MAX_DERIVED_AUDIO_BYTES:
        raise RuntimeError("derived audio size is invalid")
    if profile.extension == ".wav":
        return inspect_wav(path)
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        data = path.read_bytes()
        return {
            "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "duration_ms": None,
            "sample_rate": None,
            "channels": None,
            "mime_type": profile.mime_type,
            "qa": {"decode": "not_checked", "duration": "not_checked", "semantic": "not_checked"},
        }
    stdout = await _run_bounded([
        ffprobe, "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=sample_rate,channels:format=duration",
        "-of", "json", str(path),
    ], timeout=30.0)
    if len(stdout) > MAX_PROBE_BYTES:
        raise RuntimeError("ffprobe output is oversized")
    try:
        value = json.loads(stdout)
        stream = (value.get("streams") or [{}])[0]
        duration = float((value.get("format") or {}).get("duration") or 0)
        rate = int(stream.get("sample_rate") or 0) or None
        channels = int(stream.get("channels") or 0) or None
    except (ValueError, TypeError, IndexError, json.JSONDecodeError) as exc:
        raise RuntimeError("ffprobe returned invalid metadata") from exc
    data = path.read_bytes()
    return {
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "duration_ms": round(duration * 1000) if duration > 0 else None,
        "sample_rate": rate,
        "channels": channels,
        "mime_type": profile.mime_type,
        "qa": {
            "decode": "passed" if rate and channels else "not_checked",
            "duration": "passed" if duration > 0 else "not_checked",
            "semantic": "not_checked",
        },
    }


class AudioDeliveryService:
    def __init__(self, jobs: JobManager, session_factory, host_client: ControlDeckHostClient) -> None:
        self.jobs = jobs
        self.settings = jobs.settings
        self.session_factory = session_factory
        self.host_client = host_client

    def create(
        self,
        source_asset_id: str,
        request: AudioExportRequest,
        *,
        hosted: HostedExecution | None = None,
    ) -> Job:
        profile = PROFILES[request.profile]
        filename = _safe_filename(request.filename, profile, source_asset_id)
        row = Job(
            id=f"job:{uuid.uuid4()}",
            task="audio.export",
            state="queued",
            progress=0.0,
            request={
                "source_asset_id": source_asset_id,
                "profile": profile.id,
                "filename": filename,
                "project_output_grant": request.project_output_grant,
            },
        )
        with self.session_factory() as session:
            session.add(row)
            session.commit()
            session.refresh(row)
        if hosted is not None:
            self.jobs.hosted[row.id] = hosted
        task = asyncio.create_task(self._run(row.id), name=f"sonicforge-export-{row.id}")
        self.jobs.tasks[row.id] = task
        return row

    async def _run(self, job_id: str) -> None:
        await self.jobs._set(job_id, state="running", progress=0.02, result={"message": "Preparing audio export"})
        with self.session_factory() as session:
            job = session.get(Job, job_id)
            if job is None:
                return
            request = dict(job.request or {})
            source = session.get(Asset, str(request.get("source_asset_id") or ""))
            if source is None or source.kind != "audio":
                await self.jobs._set(job_id, state="failed", progress=1.0, error_code="asset_not_found", error_message="Source audio asset does not exist")
                self.jobs.tasks.pop(job_id, None)
                self.jobs.hosted.pop(job_id, None)
                return
            source_path = (self.settings.data_dir / source.relative_path).resolve()
        execution = self.jobs.hosted.get(job_id)
        work_dir = self.settings.data_dir / "tmp" / job_id.replace(":", "_")
        profile = PROFILES[str(request["profile"])]
        target = work_dir / str(request["filename"])
        try:
            if not source_path.is_relative_to(self.settings.data_dir.resolve()) or not source_path.is_file():
                raise RuntimeError("Source audio content is missing")
            ffmpeg = shutil.which("ffmpeg")
            if ffmpeg is None:
                raise RuntimeError("ffmpeg is required for this audio export profile")
            work_dir.mkdir(parents=True, exist_ok=True)
            await self.jobs._set(job_id, progress=0.15, result={"message": f"Exporting {profile.label}"})
            await _run_bounded(ffmpeg_argv(ffmpeg, source_path, target, profile))
            meta = await _inspect_derived(target, profile)
            asset_id = f"asset:{uuid.uuid4()}"
            prov_id = f"prov:{uuid.uuid4()}"
            destination = self.settings.assets_dir / f"{asset_id.split(':', 1)[1]}{profile.extension}"
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(target), destination)
            relative = str(destination.relative_to(self.settings.data_dir))
            with self.session_factory() as session:
                session.add(Provenance(
                    id=prov_id,
                    operation="audio.export",
                    engine_id="ffmpeg",
                    engine_version=None,
                    model_id=None,
                    model_revision=None,
                    model_license_id=None,
                    parameters={
                        "source_asset_id": source.id,
                        "delivery_profile": profile.id,
                        "filename": request["filename"],
                    },
                    qa=meta["qa"],
                ))
                session.add(Asset(
                    id=asset_id,
                    kind="audio",
                    mime_type=profile.mime_type,
                    relative_path=relative,
                    size_bytes=meta["size_bytes"],
                    sha256=meta["sha256"],
                    duration_ms=meta["duration_ms"],
                    sample_rate=meta["sample_rate"],
                    channels=meta["channels"],
                    job_id=job_id,
                    provenance_id=prov_id,
                    metadata_json={
                        "derived_from": source.id,
                        "delivery_profile": profile.id,
                        "filename": request["filename"],
                    },
                ))
                session.commit()
            result: dict[str, Any] = {
                "asset_id": asset_id,
                "source_asset_id": source.id,
                "profile": profile.id,
                "filename": request["filename"],
            }
            grant_id = request.get("project_output_grant")
            if grant_id:
                if execution is None:
                    raise RuntimeError("Project export requires ControlDeck Host execution")
                result["output"] = await commit_file(
                    self.host_client,
                    execution.identity,
                    host_job_id=execution.host_job_id,
                    grant_id=str(grant_id),
                    source=destination,
                    filename=str(request["filename"]),
                    mime_type=profile.mime_type,
                    sha256=meta["sha256"],
                )
            await self.jobs._set(job_id, state="succeeded", progress=1.0, result=result)
        except asyncio.CancelledError:
            await self.jobs._set(job_id, state="canceled", progress=1.0, error_code="canceled", error_message="Audio export canceled")
        except HostApiError as exc:
            await self.jobs._set(job_id, state="failed", progress=1.0, error_code=exc.code, error_message=str(exc)[:500])
        except Exception as exc:
            await self.jobs._set(job_id, state="failed", progress=1.0, error_code="audio_export_failed", error_message=str(exc)[:500])
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)
            self.jobs.tasks.pop(job_id, None)
            self.jobs.hosted.pop(job_id, None)
