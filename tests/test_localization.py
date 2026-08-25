import importlib
import sys
import time

from fastapi.testclient import TestClient


def load_app():
    for name in list(sys.modules):
        if name.startswith("sonicforge.app"):
            sys.modules.pop(name, None)
    return importlib.import_module("sonicforge.app")


def wait_job(client: TestClient, job_id: str):
    job = None
    for _ in range(200):
        job = client.get("/addon/v1/jobs/" + job_id.replace(":", "%3A")).json()
        if job["state"] not in {"queued", "running"}:
            return job
        time.sleep(0.02)
    raise AssertionError(f"job did not finish: {job}")


def localization_task(batch_id: str, mode: str = "pending"):
    return {
        "task": "speech.localization.batch",
        "input": {
            "batch_id": batch_id,
            "locales": ["ja", "en"],
            "mode": mode,
            "line_ids": [],
        },
        "profile": "localization-default",
        "quality": "balanced",
        "content_language": "auto",
        "output": {"format": "wav", "sample_rate": None, "channels": None},
        "routing": {"engine": "fake", "model": None, "device": "auto"},
        "seed": None,
        "project_output_grant": None,
    }


def test_localization_batch_renders_and_changed_mode_skips_unchanged(env):
    module = load_app()
    with TestClient(module.app) as client:
        created = client.post(
            "/addon/v1/localization/batches",
            json={
                "name": "dialogue",
                "profile": {"filename": "{line_id}_{locale}.wav"},
                "lines": [
                    {
                        "line_id": "hello",
                        "character": "A",
                        "ja_text": "こんにちは",
                        "en_text": "Hello",
                        "voice_id": None,
                    },
                    {
                        "line_id": "bye",
                        "character": "A",
                        "ja_text": "またね",
                        "en_text": "See you",
                        "voice_id": None,
                    },
                ],
            },
        ).json()
        batch_id = created["id"]

        submitted = client.post(
            "/addon/v1/tasks", json=localization_task(batch_id)
        )
        assert submitted.status_code == 200, submitted.text
        first = wait_job(client, submitted.json()["job_id"])
        assert first["state"] == "succeeded", first
        assert first["result"]["generated"] == 4
        assert first["result"]["failed"] == 0

        batch = client.get(
            "/addon/v1/localization/batches/" + batch_id.replace(":", "%3A")
        ).json()
        assert batch["state"] == "complete"
        assert all(line["outputs"].get("ja") for line in batch["lines"])
        assert all(line["outputs"].get("en") for line in batch["lines"])
        assert all(line["qa"]["state"] == "passed" for line in batch["lines"])

        second_submit = client.post(
            "/addon/v1/tasks", json=localization_task(batch_id, "changed")
        )
        second = wait_job(client, second_submit.json()["job_id"])
        assert second["state"] == "succeeded"
        assert second["result"]["generated"] == 0
        assert second["result"]["failed"] == 0
