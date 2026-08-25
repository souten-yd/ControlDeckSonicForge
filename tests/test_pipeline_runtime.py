import importlib
import sys
import time

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


def test_agent_pipeline_uses_same_durable_runner(env):
    module = load_app()
    with TestClient(module.app) as client:
        created = client.post("/addon/v1/agent/pipeline", json=pipeline("speech.tts", "こんにちは"))
        assert created.status_code == 200, created.text
        terminal = wait_job(client, created.json()["job_id"])
        assert terminal["state"] == "succeeded"


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
