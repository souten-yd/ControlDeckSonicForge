from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from .client import ADDON_ID, ControlDeckHostClient, HostApiError, HostIdentity

MAX_STREAM_EVENT_BYTES = 1024 * 1024


async def stream_text(
    client: ControlDeckHostClient,
    identity: HostIdentity,
    messages: list[dict],
    *,
    temperature: float = 0.2,
    max_tokens: int = 1024,
    timeout_seconds: int = 120,
) -> AsyncIterator[dict]:
    """Consume provider-neutral text streaming from the ControlDeck gateway."""
    if "ai.inference" not in identity.granted_capabilities:
        raise HostApiError(
            "capability_not_granted",
            "ControlDeck ai.inference capability is required",
            status_code=403,
        )
    payload = {
        "capability": "text.generate",
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "timeout_seconds": timeout_seconds,
        "response_format": None,
    }
    path = f"/api/v1/addon-runtime/{ADDON_ID}/ai/stream"
    try:
        async with client._client.stream(
            "POST",
            path,
            headers=client._headers(identity.authorization, identity.addon_id),
            json=payload,
            timeout=None,
        ) as response:
            if response.status_code >= 400:
                raise HostApiError(
                    "host_request_rejected",
                    f"ControlDeck rejected HTTP {response.status_code}",
                    status_code=response.status_code,
                )
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if not raw:
                    continue
                if len(raw.encode("utf-8")) > MAX_STREAM_EVENT_BYTES:
                    raise HostApiError(
                        "host_response_too_large",
                        "ControlDeck AI stream event exceeds bound",
                    )
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise HostApiError(
                        "invalid_host_response",
                        "ControlDeck AI stream emitted invalid JSON",
                    ) from exc
                if not isinstance(event, dict):
                    raise HostApiError(
                        "invalid_host_response",
                        "ControlDeck AI stream event is not an object",
                    )
                if event.get("type") == "error":
                    raise HostApiError(
                        str(event.get("code") or "host_ai_stream_failed"),
                        "ControlDeck AI streaming generation failed",
                    )
                yield event
                if event.get("type") == "done":
                    return
    except HostApiError:
        raise
    except httpx.HTTPError as exc:
        raise HostApiError(
            "host_unreachable",
            "ControlDeck Host AI stream is unreachable",
        ) from exc
