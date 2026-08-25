import pytest

from sonicforge.host.client import HostIdentity
from sonicforge.prompting import likely_japanese, normalize_sfx_prompt


class FakeHostAI:
    def __init__(self):
        self.released = False
        self.completed = False

    async def ai_capabilities(self, _identity):
        return {"text.generate": {"available": True}}

    async def ai_complete(self, _identity, messages, **_kwargs):
        self.completed = True
        assert messages[-1]["content"] == "古い木の扉がゆっくり軋んで開く"
        return {"content": "an old wooden door slowly creaks open"}

    async def ai_release(self, _identity):
        self.released = True
        return {"released": True}


@pytest.mark.asyncio
async def test_japanese_sfx_prompt_uses_host_ai_and_releases():
    host = FakeHostAI()
    identity = HostIdentity(
        authorization="Bearer x",
        subject="user:test",
        expires_at=9999999999,
        granted_capabilities=frozenset({"ai.inference"}),
    )
    request = {
        "task": "audio.sfx.generate",
        "input": {"prompt": "古い木の扉がゆっくり軋んで開く"},
        "routing": {"engine": None},
    }
    result = await normalize_sfx_prompt(
        request, identity=identity, host_client=host
    )
    inp = result["input"]
    assert inp["_internal_engine_prompt"] == "an old wooden door slowly creaks open"
    assert inp["_internal_prompt_normalization"]["state"] == "normalized"
    assert inp["_internal_prompt_normalization"]["user_prompt_language"] == "ja"
    assert host.completed is True
    assert host.released is True


@pytest.mark.asyncio
async def test_english_sfx_prompt_is_noop_without_host():
    request = {
        "task": "audio.sfx.generate",
        "input": {"prompt": "metal sword impact on stone"},
        "routing": {"engine": None},
    }
    result = await normalize_sfx_prompt(request, identity=None, host_client=None)
    meta = result["input"]["_internal_prompt_normalization"]
    assert meta["state"] == "not_required"
    assert meta["engine_prompt"] == "metal sword impact on stone"


@pytest.mark.asyncio
async def test_japanese_sfx_prompt_degrades_explicitly_without_host_ai():
    request = {
        "task": "audio.sfx.generate",
        "input": {"prompt": "爆発音"},
        "routing": {"engine": None},
    }
    result = await normalize_sfx_prompt(request, identity=None, host_client=None)
    meta = result["input"]["_internal_prompt_normalization"]
    assert meta["state"] == "unavailable"
    assert meta["user_prompt"] == "爆発音"
    assert result["input"]["_internal_engine_prompt"] == "爆発音"


def test_likely_japanese_detection():
    assert likely_japanese("古い扉が開く") is True
    assert likely_japanese("laser impact") is False
