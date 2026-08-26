import importlib
import shutil
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

from sonicforge.audio_delivery import PROFILES, ffmpeg_argv


def load_app():
    for name in list(sys.modules):
        if name.startswith("sonicforge.bootstrap") or name.startswith("sonicforge.app"):
            sys.modules.pop(name, None)
    return importlib.import_module("sonicforge.bootstrap")


def wait_job(client: TestClient, job_id: str) -> dict:
    terminal = None
    for _ in range(150):
        terminal = client.get("/addon/v1/jobs/" + job_id.replace(":", "%3A")).json()
        if terminal["state"] not in {"queued", "running"}:
            return terminal
        time.sleep(0.03)
    raise AssertionError(terminal)


def make_asset(client: TestClient) -> str:
    req = {
        "task": "speech.tts.synthesize",
        "input": {"text": "delivery test"},
        "profile": "default",
        "quality": "balanced",
        "content_language": "en",
        "output": {"format": "wav", "sample_rate": None, "channels": None},
        "routing": {"engine": "fake", "model": None, "device": "auto"},
        "seed": None,
        "project_output_grant": None,
    }
    created = client.post("/addon/v1/tasks", json=req).json()
    terminal = wait_job(client, created["job_id"])
    assert terminal["state"] == "succeeded", terminal
    return terminal["result"]["asset_id"]


def test_delivery_profiles_build_direct_ffmpeg_argv(tmp_path):
    source = tmp_path / "source.wav"
    target = tmp_path / "target.ogg"
    argv = ffmpeg_argv("/usr/bin/ffmpeg", source, target, PROFILES["unity-bgm"])
    assert argv[0] == "/usr/bin/ffmpeg"
    assert "-i" in argv
    assert "libvorbis" in argv
    assert str(source) in argv and str(target) in argv
    assert not any(value in {"sh", "bash", "-c"} for value in argv)


def test_delivery_profiles_cover_pc_game_mobile_and_m5():
    assert {
        "master-wav",
        "voice-wav",
        "unity-sfx",
        "unity-bgm",
        "unreal-sfx",
        "godot-sfx",
        "godot-bgm",
        "web-mobile",
        "m5-wav",
    }.issubset(PROFILES)
    assert PROFILES["m5-wav"].ffmpeg_args[:4] == ("-ar", "16000", "-ac", "1")


def test_durable_wav_export_creates_derived_asset(env, monkeypatch):
    import sonicforge.audio_delivery as delivery

    async def fake_run(argv, *, timeout=180.0):
        source = Path(argv[argv.index("-i") + 1])
        target = Path(argv[-1])
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        return b""

    monkeypatch.setattr(delivery.shutil, "which", lambda name: f"/fake/{name}")
    monkeypatch.setattr(delivery, "_run_bounded", fake_run)

    module = load_app()
    with TestClient(module.app) as client:
        source_id = make_asset(client)
        profiles = client.get("/addon/v1/delivery/audio/profiles")
        assert profiles.status_code == 200
        assert any(item["id"] == "voice-wav" for item in profiles.json()["profiles"])

        created = client.post(
            "/addon/v1/assets/" + source_id.replace(":", "%3A") + "/export",
            json={"profile": "voice-wav", "filename": "hero_voice.wav"},
        )
        assert created.status_code == 200, created.text
        terminal = wait_job(client, created.json()["job_id"])
        assert terminal["state"] == "succeeded", terminal
        derived_id = terminal["result"]["asset_id"]
        asset = client.get("/addon/v1/assets/" + derived_id.replace(":", "%3A"))
        assert asset.status_code == 200
        metadata = asset.json()["metadata"]
        assert metadata["derived_from"] == source_id
        assert metadata["delivery_profile"] == "voice-wav"
        assert metadata["filename"] == "hero_voice.wav"


def test_project_export_requires_host_execution(env):
    module = load_app()
    with TestClient(module.app) as client:
        source_id = make_asset(client)
        response = client.post(
            "/addon/v1/assets/" + source_id.replace(":", "%3A") + "/export",
            json={
                "profile": "unity-sfx",
                "project_output_grant": "grant:project-audio",
            },
        )
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "host_grant_required"
