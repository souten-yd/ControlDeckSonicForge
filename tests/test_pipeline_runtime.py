import importlib
import io
import json
import shutil
import sys
import time
import zipfile

from fastapi.testclient import TestClient


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


def pipeline(stage_kind: str, prompt: str = "短い確認音") -> dict:
    return {
        "pipeline": f"test-{stage_kind}",
        "input": {"kind": "text", "text": prompt},
        "stages": [
            {
                "id": "generate",
                "kind": stage_kind,
                "routing": {"engine": "fake", "model": None, "device": "auto"},
            }
        ],
        "delivery": {"mode": "asset", "profile": "test"},
    }


def test_tts_pipeline_creates_durable_asset(env):
    module = load_app()
    with TestClient(module.app) as client:
        created = client.post("/addon/v1/pipelines", json=pipeline("speech.tts"))
        assert created.status_code == 200, created.text
        terminal = wait_job(client, created.json()["job_id"])
        assert terminal["state"] == "succeeded", terminal
        asset_id = terminal["result"]["asset_id"]
        asset = client.get("/addon/v1/assets/" + asset_id.replace(":", "%3A"))
        assert asset.status_code == 200
        assert asset.json()["duration_ms"] > 0
        assert asset.json()["metadata"]["pipeline"]["stages"][0]["kind"] == "speech.tts"


def test_sfx_and_music_pipeline_share_same_runner(env):
    module = load_app()
    with TestClient(module.app) as client:
        for kind in ("audio.sfx", "music.generate"):
            created = client.post("/addon/v1/pipelines", json=pipeline(kind))
            assert created.status_code == 200, created.text
            terminal = wait_job(client, created.json()["job_id"])
            assert terminal["state"] == "succeeded", terminal
            assert terminal["result"]["asset_id"].startswith("asset:")


def test_audio_process_stage_runs_real_ffmpeg(env):
    if shutil.which("ffmpeg") is None:
        return
    module = load_app()
    request = pipeline("speech.tts", "audio process integration")
    request["stages"].append(
        {
            "id": "process",
            "kind": "audio.process",
            "parameters": {
                "duration_sec": 0.2,
                "gain_db": -3,
                "normalize": True,
                "sample_rate": 48000,
                "channels": 2,
            },
        }
    )
    with TestClient(module.app) as client:
        created = client.post("/addon/v1/pipelines", json=request)
        assert created.status_code == 200, created.text
        terminal = wait_job(client, created.json()["job_id"])
        assert terminal["state"] == "succeeded", terminal
        asset_id = terminal["result"]["asset_id"]
        asset = client.get("/addon/v1/assets/" + asset_id.replace(":", "%3A"))
        assert asset.status_code == 200
        assert asset.json()["sample_rate"] == 48000
        assert asset.json()["channels"] == 2
        assert asset.json()["metadata"]["pipeline"]["stages"][-1]["kind"] == "audio.process"


def test_package_delivery_persists_zip_asset_and_manifest(env):
    module = load_app()
    request = pipeline("speech.tts", "package integration")
    request["delivery"] = {
        "mode": "package",
        "profile": "voice-wav",
        "filename": "voice-bundle.zip",
    }
    with TestClient(module.app) as client:
        created = client.post("/addon/v1/pipelines", json=request)
        assert created.status_code == 200, created.text
        terminal = wait_job(client, created.json()["job_id"])
        assert terminal["state"] == "succeeded", terminal
        result = terminal["result"]
        package = client.get(
            "/addon/v1/assets/" + result["asset_id"].replace(":", "%3A")
        )
        assert package.status_code == 200
        package_body = package.json()
        assert package_body["kind"] == "package"
        assert package_body["mime_type"] == "application/zip"
        assert package_body["provenance"]["operation"] == "asset.package"
        assert package_body["metadata"]["source_audio_asset_id"] == result["audio_asset_id"]

        content = client.get(result["content_url"])
        assert content.status_code == 200
        assert content.headers["content-type"].startswith("application/zip")
        with zipfile.ZipFile(io.BytesIO(content.content)) as archive:
            assert archive.namelist()[1] == "manifest.json"
            manifest = json.loads(archive.read("manifest.json"))
            assert manifest["type"] == "sonicforge.pipeline-package"
            assert manifest["audio"]["asset_id"] == result["audio_asset_id"]
            assert archive.read(archive.namelist()[0])


def test_agent_pipeline_uses_same_durable_runner(env):
    module = load_app()
    with TestClient(module.app) as client:
        created = client.post("/addon/v1/agent/pipeline", json=pipeline("speech.tts", "こんにちは"))
        assert created.status_code == 200, created.text
        terminal = wait_job(client, created.json()["job_id"])
        assert terminal["state"] == "succeeded"


def test_agent_pipeline_unwraps_control_deck_envelope(env):
    module = load_app()
    with TestClient(module.app) as client:
        created = client.post(
            "/addon/v1/agent/pipeline",
            json={
                "input": pipeline("speech.tts", "wrapped pipeline"),
                "correlation": {"job_id": "host-job"},
            },
        )
        assert created.status_code == 200, created.text
        terminal = wait_job(client, created.json()["job_id"])
        assert terminal["state"] == "succeeded", terminal


def test_host_ai_pipeline_is_rejected_without_control_deck_execution(env):
    module = load_app()
    with TestClient(module.app) as client:
        request = {
            "pipeline": "text-reply",
            "input": {"kind": "text", "text": "挨拶して"},
            "stages": [
                {"id": "llm", "kind": "host.ai.text"},
                {
                    "id": "tts",
                    "kind": "speech.tts",
                    "routing": {"engine": "fake", "model": None, "device": "auto"},
                },
            ],
            "delivery": {"mode": "asset", "profile": "test"},
        }
        response = client.post("/addon/v1/pipelines", json=request)
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "host_ai_required"
