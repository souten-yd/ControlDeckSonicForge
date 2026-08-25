from __future__ import annotations

from dataclasses import dataclass

from .client import ADDON_ID, ControlDeckHostClient, HostApiError, HostIdentity


@dataclass(frozen=True)
class AiResidencyHold:
    held: bool
    hold_id: str | None
    expires_at: int | None
    heartbeat_interval_seconds: int
    reason: str


def _parse(value: dict) -> AiResidencyHold:
    held = bool(value.get("held"))
    hold_id = value.get("hold_id")
    expires_at = value.get("expires_at")
    heartbeat = value.get("heartbeat_interval_seconds", 0)
    reason = str(value.get("reason") or "")
    if held and (not isinstance(hold_id, str) or not hold_id.startswith("hold:")):
        raise HostApiError("invalid_host_response", "ControlDeck returned an invalid residency hold")
    if expires_at is not None and not isinstance(expires_at, int):
        raise HostApiError("invalid_host_response", "ControlDeck returned an invalid residency expiry")
    if not isinstance(heartbeat, int) or heartbeat < 0:
        raise HostApiError("invalid_host_response", "ControlDeck returned an invalid residency heartbeat")
    return AiResidencyHold(held, hold_id if isinstance(hold_id, str) else None, expires_at, heartbeat, reason)


async def create_ai_hold(client: ControlDeckHostClient, identity: HostIdentity) -> AiResidencyHold:
    value = await client.request(identity, "POST", f"/{ADDON_ID}/ai/residency/holds", json={})
    return _parse(value)


async def renew_ai_hold(
    client: ControlDeckHostClient,
    identity: HostIdentity,
    hold_id: str,
) -> AiResidencyHold:
    value = await client.request(
        identity,
        "POST",
        f"/{ADDON_ID}/ai/residency/holds/{hold_id}/renew",
        json={},
    )
    return _parse(value)


async def release_ai_hold(
    client: ControlDeckHostClient,
    identity: HostIdentity,
    hold_id: str,
) -> bool:
    value = await client.request(
        identity,
        "DELETE",
        f"/{ADDON_ID}/ai/residency/holds/{hold_id}",
    )
    return bool(value.get("released"))
