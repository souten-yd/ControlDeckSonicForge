import asyncio
from pathlib import Path

from sonicforge.config import Settings
from sonicforge.live_host_session import LiveHostSession
from sonicforge.live_workers import LiveWorkerPool


class DummyJobs:
    @staticmethod
    def _gpu_required(request):
        return False


class DummyHostClient:
    pass


def settings(tmp_path: Path) -> Settings:
    root = Path(__file__).resolve().parents[1]
    return Settings(
        host="127.0.0.1",
        port=9140,
        data_dir=tmp_path / "data",
        cache_dir=tmp_path / "cache",
        repo_root=root,
        ui_locale="auto",
        enable_fake_worker=True,
        setup_test_mode=True,
        control_deck_url="http://127.0.0.1:8765",
    )


def asr_request():
    return {
        "task": "speech.asr.transcribe",
        "content_language": "ja",
        "routing": {"engine": "fake", "model": None, "device": "auto"},
        "input": {"_internal_staged_input": "/tmp/not-used-by-fake"},
    }


def tts_request(text: str):
    return {
        "task": "speech.tts.synthesize",
        "content_language": "ja",
        "routing": {"engine": "fake", "model": None, "device": "auto"},
        "input": {"text": text},
    }


def test_persistent_worker_process_is_reused_and_terminated_on_session_close(tmp_path):
    async def scenario():
        cfg = settings(tmp_path)
        host_session = LiveHostSession(
            host_client=DummyHostClient(),
            jobs=DummyJobs(),
            identity=None,
            title="test",
        )
        pool = LiveWorkerPool(settings=cfg, host_session=host_session)

        async def progress(_fraction, _message):
            return None

        first = await pool.execute(asr_request(), tmp_path / "asr-1", progress)
        asr_pid = pool._workers["asr"].proc.pid
        second = await pool.execute(asr_request(), tmp_path / "asr-2", progress)
        assert pool._workers["asr"].proc.pid == asr_pid
        assert first.payload["text"] == "fake transcription"
        assert second.payload["text"] == "fake transcription"

        tts_first = await pool.execute(tts_request("one"), tmp_path / "tts-1", progress)
        tts_pid = pool._workers["tts"].proc.pid
        tts_second = await pool.execute(tts_request("two"), tmp_path / "tts-2", progress)
        assert pool._workers["tts"].proc.pid == tts_pid
        assert tts_first.output_path is not None
        assert tts_second.output_path is not None

        asr_proc = pool._workers["asr"].proc
        tts_proc = pool._workers["tts"].proc
        await pool.close()
        assert asr_proc.returncode is not None
        assert tts_proc.returncode is not None

    asyncio.run(scenario())
