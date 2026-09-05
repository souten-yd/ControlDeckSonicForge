import asyncio
import io
import json
import zipfile
import wave

import pytest

from sonicforge import tts_models
from sonicforge.config import ensure_directories, load_settings
from sonicforge.db import make_session_factory
from sonicforge.events import EventBus
from sonicforge.jobs import JobManager


class Upload:
    def __init__(self, value: bytes):
        self.stream = io.BytesIO(value)

    async def read(self, size: int) -> bytes:
        return self.stream.read(size)


def model_zip(*, unsafe: bool = False) -> bytes:
    stream = io.BytesIO()
    manifest = {
        "id": "narrator-ja",
        "name": "Narrator JA",
        "license_id": "CC-BY-4.0",
        "source": "https://example.invalid/narrator",
        "revision": "sha256:test",
        "rights_confirmed": True,
        "version": "v2ProPlus",
        "languages": ["ja"],
        "t2s_weights": "weights/t2s.ckpt",
        "vits_weights": "weights/vits.pth",
        "reference_audio": "reference.wav",
        "reference_text": "参照音声です。",
    }
    wav = io.BytesIO()
    with wave.open(wav, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\0\0" * 16000)
    with zipfile.ZipFile(stream, "w") as bundle:
        bundle.writestr("manifest.json", json.dumps(manifest))
        bundle.writestr("weights/t2s.ckpt", b"t" * 1024 * 1024)
        bundle.writestr("weights/vits.pth", b"v" * 1024 * 1024)
        bundle.writestr("reference.wav", wav.getvalue())
        if unsafe:
            bundle.writestr("../escape", b"bad")
    return stream.getvalue()


def test_model_zip_install_activate_route_and_delete(env):
    settings = load_settings()
    ensure_directories(settings)
    factory = make_session_factory(settings)
    with factory() as session:
        installed = asyncio.run(
            tts_models.install(settings, session, Upload(model_zip()))
        )
        assert installed["id"] == "gpt-sovits:narrator-ja"
        selected = tts_models.set_preference(
            session,
            engine_id="tts.gpt-sovits",
            model_id=installed["id"],
        )
        assert selected["engine_id"] == "tts.gpt-sovits"

    manager = JobManager(settings, factory, EventBus())
    request = manager._apply_tts_preferences(
        {
            "task": "speech.tts.synthesize",
            "input": {"text": "こんにちは"},
            "routing": {"engine": None, "model": None, "device": "auto"},
        }
    )
    assert request["routing"]["engine"] == "tts.gpt-sovits"
    assert request["routing"]["model"] == installed["id"]
    assert "_internal_model_pack" not in request["input"]
    request = manager._resolve_voice(request)
    assert request["input"]["_internal_model_pack"]["reference_text"] == "参照音声です。"

    with factory() as session:
        with pytest.raises(tts_models.ModelPackError, match="active model"):
            tts_models.delete(settings, session, installed["id"])
        tts_models.set_preference(
            session,
            engine_id="tts.qwen3",
            model_id=tts_models.BASE_GPT_MODEL,
        )
        tts_models.delete(settings, session, installed["id"])
        assert not (settings.models_dir / "gpt-sovits/custom/narrator-ja").exists()


def test_model_zip_rejects_path_traversal(env):
    settings = load_settings()
    ensure_directories(settings)
    factory = make_session_factory(settings)
    with factory() as session:
        with pytest.raises(tts_models.ModelPackError, match="unsafe path"):
            asyncio.run(tts_models.install(settings, session, Upload(model_zip(unsafe=True))))
    assert not (settings.models_dir / "gpt-sovits/escape").exists()
