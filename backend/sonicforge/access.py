from __future__ import annotations

import ipaddress
import os
from typing import Literal

from fastapi import HTTPException, Request, WebSocket

LocalAccessMode = Literal["trusted-network", "strict", "open"]


def local_access_mode() -> LocalAccessMode:
    raw = os.environ.get("SONICFORGE_LOCAL_ACCESS", "trusted-network").strip().lower()
    if raw in {"trusted-network", "strict", "open"}:
        return raw  # type: ignore[return-value]
    return "trusted-network"


def _is_local_host(value: str | None) -> bool:
    if not value:
        return False
    value = value.strip().strip("[]")
    if value.lower() == "localhost":
        return True
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        # Test clients and local Unix/reverse-proxy adapters can expose a
        # non-address peer name. They are trusted only when the server itself is
        # loopback-bound; callers on a public bind must provide a real address.
        return False
    if address.is_loopback or address.is_link_local or address.is_private:
        return True
    # Tailscale CGNAT (100.64/10) and other explicitly non-global local fabrics
    # are useful for this local-first product even though ipaddress does not mark
    # all of them as is_private.
    return not address.is_global and not address.is_unspecified


def _is_loopback_bind(value: str) -> bool:
    value = value.strip().strip("[]")
    if value.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def peer_is_trusted(*, peer_host: str | None, bind_host: str) -> bool:
    mode = local_access_mode()
    if mode == "open":
        return True
    bind_local = _is_loopback_bind(bind_host)
    peer_local = _is_local_host(peer_host)
    if mode == "strict":
        return bind_local and (peer_local or peer_host in {None, "testclient"})
    # Default: trusted-network. A loopback-bound service is local regardless of
    # adapter naming; otherwise require a non-global/local peer address.
    return bind_local or peer_local


def require_trusted_request(request: Request, *, bind_host: str) -> None:
    peer = request.client.host if request.client is not None else None
    if not peer_is_trusted(peer_host=peer, bind_host=bind_host):
        raise HTTPException(
            status_code=403,
            detail="SonicForge local API only accepts trusted local-network peers by default",
        )


def websocket_peer_is_trusted(websocket: WebSocket, *, bind_host: str) -> bool:
    peer = websocket.client.host if websocket.client is not None else None
    return peer_is_trusted(peer_host=peer, bind_host=bind_host)
