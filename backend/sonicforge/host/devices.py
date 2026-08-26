from __future__ import annotations

from .client import ADDON_ID, ControlDeckHostClient, HostApiError, HostIdentity


async def create_device_pairing(
    client: ControlDeckHostClient,
    identity: HostIdentity,
    *,
    relay_id: str,
    device_label: str | None = None,
) -> dict:
    if "devices.relay" not in identity.granted_capabilities:
        raise HostApiError(
            "capability_not_granted",
            "ControlDeck devices.relay capability is required",
            status_code=403,
        )
    payload = {"relay_id": relay_id, "device_label": device_label}
    value = await client.request(
        identity,
        "POST",
        f"/{ADDON_ID}/devices/pairings",
        json=payload,
    )
    code = value.get("pairing_code")
    path = value.get("websocket_path")
    expires_at = value.get("expires_at")
    if (
        not isinstance(code, str)
        or len(code) != 8
        or not isinstance(path, str)
        or not path.startswith("/api/v1/addon-runtime/")
        or not isinstance(expires_at, int)
    ):
        raise HostApiError(
            "invalid_host_response",
            "ControlDeck returned an invalid device pairing response",
        )
    return value
