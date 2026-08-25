import asyncio
import json
import time

import httpx

from sonicforge.host.client import ControlDeckHostClient, HostIdentity


def identity(token: str = "old-token") -> HostIdentity:
    return HostIdentity(
        authorization=f"Bearer {token}",
        addon_id="sonic-forge",
        subject="workflow:42",
        expires_at=int(time.time()) + 60,
        granted_capabilities=frozenset({"jobs.write", "ai.inference"}),
    )


def test_job_credential_refresh_preserves_scope():
    now = int(time.time())

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/jobs/job:abc/credential/refresh"):
            return httpx.Response(
                200,
                json={
                    "access_token": "new-token",
                    "token_type": "Bearer",
                    "expires_at": now + 600,
                },
            )
        if request.url.path.endswith("/token/introspect"):
            assert request.headers["authorization"] == "Bearer new-token"
            return httpx.Response(
                200,
                json={
                    "active": True,
                    "addon_id": "sonic-forge",
                    "subject": "workflow:42",
                    "expires_at": now + 600,
                    "granted_capabilities": ["jobs.write", "ai.inference"],
                },
            )
        raise AssertionError(request.url.path)

    async def scenario():
        client = ControlDeckHostClient(
            "http://control.test", transport=httpx.MockTransport(handler)
        )
        try:
            refreshed = await client.refresh_job_identity(identity(), "job:abc")
            assert refreshed.authorization == "Bearer new-token"
            assert refreshed.subject == "workflow:42"
            assert refreshed.granted_capabilities == frozenset(
                {"jobs.write", "ai.inference"}
            )
            assert refreshed.expires_at == now + 600
        finally:
            await client.close()

    asyncio.run(scenario())


def test_residency_hold_rolls_service_identity_without_changing_scope():
    now = int(time.time())

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/ai/residency/holds"):
            return httpx.Response(
                201,
                json={
                    "held": True,
                    "hold_id": "hold:1",
                    "heartbeat_interval_seconds": 30,
                    "expires_at": now + 120,
                    "access_token": "hold-token",
                    "token_type": "Bearer",
                    "token_expires_at": now + 600,
                },
            )
        if request.url.path.endswith("/token/introspect"):
            return httpx.Response(
                200,
                json={
                    "active": True,
                    "addon_id": "sonic-forge",
                    "subject": "workflow:42",
                    "expires_at": now + 600,
                    "granted_capabilities": ["jobs.write", "ai.inference"],
                },
            )
        raise AssertionError(request.url.path)

    async def scenario():
        client = ControlDeckHostClient(
            "http://control.test", transport=httpx.MockTransport(handler)
        )
        try:
            value, refreshed = await client.ai_residency_create(identity())
            assert value["hold_id"] == "hold:1"
            assert refreshed.authorization == "Bearer hold-token"
            assert refreshed.subject == "workflow:42"
        finally:
            await client.close()

    asyncio.run(scenario())


def test_ai_stream_consumes_provider_neutral_sse_incrementally():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/ai/stream")
        body = json.loads(request.content)
        assert body["capability"] == "text.generate"
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=(
                'data: {"type":"content","content":"こんにちは"}\n\n'
                'data: {"type":"content","content":"。"}\n\n'
                'data: {"type":"usage","usage":{"completion_tokens":2}}\n\n'
                'data: {"type":"done"}\n\n'
            ).encode(),
        )

    async def scenario():
        client = ControlDeckHostClient(
            "http://control.test", transport=httpx.MockTransport(handler)
        )
        try:
            events = [
                event
                async for event in client.ai_stream(
                    identity(), [{"role": "user", "content": "hello"}]
                )
            ]
            assert [event["type"] for event in events] == [
                "content",
                "content",
                "usage",
                "done",
            ]
            assert "".join(
                event.get("content", "") for event in events
            ) == "こんにちは。"
        finally:
            await client.close()

    asyncio.run(scenario())
