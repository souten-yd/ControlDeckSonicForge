"""Browser-supplied audio input.

ControlDeck's file picker hands SonicForge an opaque grant, and that is the
right path when the operator is choosing audio that already lives in a project.
It is the wrong path for audio that only exists in the browser: a microphone
recording, or a file chosen with the phone's own picker. Those bytes arrive
here instead.

Two rules keep this safe and useful:

* the stored name is a server-generated UUID, never anything the client sent,
  so a crafted filename cannot escape the uploads directory;
* everything is normalised to mono 16-bit WAV with ffmpeg before a worker sees
  it. Browsers record WebM/Opus and phones hand over m4a/mp3; the ASR and
  voice-clone workers read audio through libraries that expect a plain
  waveform, so accepting the container variety here is what makes the browser
  path work at all.
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import uuid
from pathlib import Path

from .config import Settings

UPLOAD_ID_RE = re.compile(r"^upload:[0-9a-f]{32}$")
MAX_UPLOAD_BYTES = 200 * 1024 * 1024
# Speech, not music: one channel at 48 kHz serves both transcription and voice
# cloning, and bounds what an unattended upload can cost in disk.
NORMALISED_RATE = "48000"
CHUNK_BYTES = 1024 * 1024


class UploadError(ValueError):
    pass


def uploads_dir(settings: Settings) -> Path:
    target = settings.data_dir / "tmp" / "uploads"
    target.mkdir(parents=True, exist_ok=True)
    return target


def _ffmpeg() -> str:
    found = shutil.which("ffmpeg")
    if found is None:
        raise UploadError("ffmpeg is required to accept browser audio uploads")
    return found


async def _normalise(source: Path, target: Path) -> None:
    proc = await asyncio.create_subprocess_exec(
        _ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "error",
        "-i", str(source), "-vn", "-ac", "1", "-ar", NORMALISED_RATE,
        "-c:a", "pcm_s16le", "-f", "wav", str(target),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=os.name != "nt",
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0 or not target.is_file():
        # ffmpeg names the staging path it failed on. SonicForge does not put
        # its own filesystem layout in API responses, so keep the detail in the
        # log and hand the caller something it can act on.
        print(
            "upload normalisation failed: "
            + (stderr or b"").decode(errors="replace").strip()[-600:],
            flush=True,
        )
        raise UploadError("that file could not be read as audio")


async def store(settings: Settings, stream, *, filename: str | None = None) -> dict:
    """Persist an uploaded audio stream and return its reference."""
    directory = uploads_dir(settings)
    token = uuid.uuid4().hex
    staged = directory / f"{token}.upload"
    target = directory / f"{token}.wav"
    size = 0
    try:
        with staged.open("wb") as sink:
            while True:
                chunk = await stream.read(CHUNK_BYTES)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise UploadError("the uploaded audio is too large")
                sink.write(chunk)
        if size == 0:
            raise UploadError("the uploaded audio is empty")
        await _normalise(staged, target)
    except BaseException:
        staged.unlink(missing_ok=True)
        target.unlink(missing_ok=True)
        raise
    finally:
        staged.unlink(missing_ok=True)
    return {
        "upload_id": f"upload:{token}",
        "filename": Path(filename or "audio").name[:120] or "audio",
        "size_bytes": target.stat().st_size,
        "source_bytes": size,
    }


def resolve(settings: Settings, upload_id: str) -> Path:
    """Return the stored file for an upload reference, or raise."""
    if not isinstance(upload_id, str) or UPLOAD_ID_RE.fullmatch(upload_id) is None:
        raise UploadError("an upload reference is required")
    directory = uploads_dir(settings).resolve()
    target = (directory / f"{upload_id.split(':', 1)[1]}.wav").resolve()
    if not target.is_relative_to(directory) or not target.is_file():
        raise UploadError("the uploaded audio is no longer available")
    return target


def discard(settings: Settings, upload_id: str) -> None:
    try:
        resolve(settings, upload_id).unlink(missing_ok=True)
    except UploadError:
        return
