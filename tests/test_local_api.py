import importlib
import io
import sys
import time
import wave

from fastapi.testclient import TestClient


def load_app():
    for name in list(sys.modules):
        if name.startswith("sonicforge.bootstrap") or name.startswith("sonicforge.app"):
            sys.modules.pop(name, None)
    return importlib.import_module("sonicforge.bootstrap")


def wav_bytes() -> bytes:
    value = io.BytesIO()
    with wave.open(value, "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16000)
        stream.writeframes(b"\x00\x00" * 1600)
    return value.getvalue()


def wait_job(client: TestClient, job_id: str) -> dict:
    for _ in range(150):
        job = client.get(
            "/addon/v1/jobs/" + job_id.replace(":", "%3A")
        ).json()
        if job["state"] not in {"queued", "running"}:
            return job
        time.sleep(0.02)
    raise AssertionError(f"job did not settle: {job_id}")


def test_trusted_local_asr_needs_no_control_deck_auth(env, monkeypatch):
    monkeypatch.setenv("SONICFORGE_SPOOL_DIR", str(env / "ram-spool"))
    module = load_app()
    with TestClient(module.app) as client:
        response = client.post(
            "/local/v1/asr?language=ja",
            content=wav_bytes(),
            headers={"Content-Type": "audio/wav"},
        )
        assert response.status_code == 200, response.text
        job = wait_job(client, response.json()["job_id"])
        assert job["state"] == "succeeded", job
        assert job["result"]["text"] == "fake transcription"


def test_trusted_local_tts_needs_no_control_deck_auth(env, monkeypatch):
    from sonicforge.jobs import JobManager

    monkeypatch.setattr(JobManager, "_gpu_required", lambda self, request: True)
    module = load_app()
    with TestClient(module.app) as client:
        response = client.post(
            "/local/v1/tts",
            json={"text": "こんにちは", "language": "ja"},
        )
        assert response.status_code == 200, response.text
        job = wait_job(client, response.json()["job_id"])
        assert job["state"] == "succeeded", job
        assert job["result"]["asset_id"].startswith("asset:")


def test_local_music_preserves_duration_and_music_controls(env, monkeypatch):
    from sonicforge.jobs import JobManager

    captured = {}
    original_create = JobManager.create

    def capture(self, request, *, hosted=None):
        captured.update(request)
        return original_create(self, request, hosted=hosted)

    monkeypatch.setattr(JobManager, "create", capture)
    module = load_app()
    with TestClient(module.app) as client:
        response = client.post(
            "/local/v1/music",
            json={
                "prompt": "gentle menu theme",
                "language": "en",
                "duration_sec": 10,
                "bpm": 96,
                "instrumental": True,
            },
        )
        assert response.status_code == 200, response.text
        job = wait_job(client, response.json()["job_id"])
        assert job["state"] == "succeeded", job
        assert captured["input"] == {
            "prompt": "gentle menu theme",
            "duration_sec": 10.0,
            "instrumental": True,
            "bpm": 96,
        }
