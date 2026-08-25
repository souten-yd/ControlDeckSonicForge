import asyncio
import time

import pytest

from sonicforge.config import ensure_directories, load_settings
from sonicforge.db import Asset, Job, Provenance, make_session_factory
from sonicforge.events import EventBus
from sonicforge.host.client import HostIdentity
from sonicforge.job_extensions import install_job_extensions
from sonicforge.jobs import HostedExecution, JobManager


class FakeHost:
    def __init__(self):
        self.order = []

    async def ai_capabilities(self, _identity):
        return {"text.generate": {"available": True}, "vision.analyze": {"available": False}}

    async def ai_complete(self, _identity, messages, **_kwargs):
        self.order.append("ai.complete")
        assert messages[-1]["content"] == "古い木の扉がゆっくり軋んで開く"
        return {"content": "an old wooden door slowly creaks open", "capability": "text.generate"}

    async def ai_release(self, _identity):
        self.order.append("ai.release")
        return {"released": True, "reason": "released", "freed_bytes": 1}

    async def update_job(self, _identity, _job_id, _payload):
        return {"ok": True}

    async def job_control(self, _identity, _job_id):
        return {"status": "running", "cancel_requested": False}


@pytest.mark.asyncio
async def test_direct_sfx_job_normalizes_before_worker_and_persists_provenance(env):
    settings = load_settings()
    ensure_directories(settings)
    factory = make_session_factory(settings)
    host = FakeHost()
    manager = JobManager(settings, factory, EventBus(), host_client=host)
    install_job_extensions(manager)
    identity = HostIdentity(
        authorization="Bearer test",
        addon_id="sonic-forge",
        subject="job:host-sfx",
        expires_at=int(time.time()) + 300,
        granted_capabilities=frozenset({"jobs.write", "ai.inference"}),
    )
    request = {
        "task": "audio.sfx.generate",
        "input": {"prompt": "古い木の扉がゆっくり軋んで開く", "duration_sec": 2},
        "profile": "default",
        "quality": "balanced",
        "content_language": "ja",
        "output": {"format": "wav", "sample_rate": None, "channels": None},
        # engine=None exercises real orchestration while SONICFORGE_ENABLE_FAKE=1
        # keeps the worker itself lightweight.
        "routing": {"engine": None, "model": None, "device": "auto"},
        "seed": None,
        "project_output_grant": None,
    }
    row = manager.create(
        request,
        hosted=HostedExecution(identity=identity, host_job_id="host-sfx"),
    )

    for _ in range(150):
        await asyncio.sleep(0.03)
        with factory() as session:
            terminal = session.get(Job, row.id)
            if terminal is not None and terminal.state not in {"queued", "running"}:
                state = terminal.state
                error = terminal.error_message
                result = dict(terminal.result or {})
                break
    else:
        raise AssertionError("SFX job did not finish")

    assert state == "succeeded", error
    assert host.order[:2] == ["ai.complete", "ai.release"]
    asset_id = result["asset_id"]
    with factory() as session:
        asset = session.get(Asset, asset_id)
        assert asset is not None
        normalization = asset.metadata_json["prompt_normalization"]
        assert normalization["state"] == "normalized"
        assert normalization["user_prompt"] == "古い木の扉がゆっくり軋んで開く"
        assert normalization["engine_prompt"] == "an old wooden door slowly creaks open"
        provenance = session.get(Provenance, asset.provenance_id)
        assert provenance is not None
        assert provenance.parameters["prompt_normalization"] == normalization
