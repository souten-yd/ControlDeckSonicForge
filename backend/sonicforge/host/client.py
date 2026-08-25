from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import time

import httpx

ADDON_ID = "sonic-forge"
MAX_JSON_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_GRANT_BYTES = 1024 * 1024 * 1024


class HostApiError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 502):
        super().__init__(message); self.code = code; self.status_code = status_code


@dataclass(frozen=True)
class HostIdentity:
    authorization: str = field(repr=False)
    addon_id: str = ADDON_ID
    subject: str = ""
    expires_at: int = 0
    granted_capabilities: frozenset[str] = frozenset()


class ControlDeckHostClient:
    def __init__(self, base_url: str, *, timeout_sec: float = 10.0, transport: httpx.AsyncBaseTransport | None = None):
        self._client = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout_sec, follow_redirects=False, transport=transport)

    async def close(self) -> None: await self._client.aclose()

    @staticmethod
    def incoming_credentials(headers: Mapping[str, str]) -> tuple[str, str]:
        addon = headers.get("x-control-deck-addon-id") or headers.get("X-Control-Deck-Addon-ID", "")
        authorization = headers.get("authorization") or headers.get("Authorization", "")
        scheme, sep, token = authorization.partition(" ")
        if addon != ADDON_ID or sep != " " or scheme.lower() != "bearer" or not token or " " in token:
            raise HostApiError("host_service_token_required", "ControlDeck service token is required", status_code=401)
        return authorization, addon

    async def authenticate(self, headers: Mapping[str, str]) -> HostIdentity:
        auth, addon = self.incoming_credentials(headers)
        value = await self._raw("POST", "/api/v1/addon-runtime/token/introspect", auth, addon)
        caps = value.get("granted_capabilities"); exp = value.get("expires_at"); now = int(time.time())
        if value.get("active") is not True or value.get("addon_id") != ADDON_ID or not isinstance(value.get("subject"), str) or not value["subject"] or not isinstance(exp, int) or exp <= now or exp > now + 630 or not isinstance(caps, list) or not all(isinstance(item, str) for item in caps):
            raise HostApiError("invalid_host_service_token", "ControlDeck service token is inactive", status_code=401)
        return HostIdentity(auth, addon, value["subject"], exp, frozenset(caps))

    async def create_or_attach_job(self, identity: HostIdentity, title: str): return await self.request(identity, "POST", f"/{ADDON_ID}/jobs", json={"title": title})
    async def update_job(self, identity: HostIdentity, job_id: str, payload: dict): return await self.request(identity, "PATCH", f"/{ADDON_ID}/jobs/{job_id}", json=payload)
    async def job_control(self, identity: HostIdentity, job_id: str): return await self.request(identity, "GET", f"/{ADDON_ID}/jobs/{job_id}/control")
    async def request_resource(self, identity: HostIdentity, payload: dict): return await self.request(identity, "POST", f"/{ADDON_ID}/resources/requests", json=payload)
    async def resource_status(self, identity: HostIdentity, request_id: str): return await self.request(identity, "GET", f"/{ADDON_ID}/resources/requests/{request_id}")
    async def cancel_resource(self, identity: HostIdentity, request_id: str): return await self.request(identity, "DELETE", f"/{ADDON_ID}/resources/requests/{request_id}")

    async def lease_action(self, identity: HostIdentity, lease_id: str, action: str):
        if action not in {"activate", "renew", "release"}: raise ValueError("unsupported lease action")
        return await self.request(identity, "POST", f"/{ADDON_ID}/resources/leases/{lease_id}/{action}")

    async def refresh_lease_identity(self, identity: HostIdentity, lease_id: str) -> HostIdentity:
        value = await self.request(identity, "POST", f"/{ADDON_ID}/resources/leases/{lease_id}/credential/refresh")
        token = value.get("access_token")
        if value.get("token_type") != "Bearer" or not isinstance(token, str) or not token or " " in token:
            raise HostApiError("invalid_host_response", "ControlDeck did not return a refreshed service token")
        refreshed = await self.authenticate({"Authorization": f"Bearer {token}", "X-Control-Deck-Addon-ID": identity.addon_id})
        if refreshed.addon_id != identity.addon_id or refreshed.subject != identity.subject:
            raise HostApiError("invalid_host_response", "ControlDeck changed the service token scope")
        return refreshed

    async def grant_metadata(self, identity: HostIdentity, grant_id: str): return await self.request(identity, "GET", f"/{ADDON_ID}/grants/{grant_id}")
    async def create_output(self, identity: HostIdentity, payload: dict): return await self.request(identity, "POST", f"/{ADDON_ID}/files/outputs", json=payload)
    async def upload_output(self, identity: HostIdentity, output_id: str, content: bytes): return await self.request(identity, "PUT", f"/{ADDON_ID}/files/outputs/{output_id}/content", content=content)
    async def commit_output(self, identity: HostIdentity, output_id: str): return await self.request(identity, "POST", f"/{ADDON_ID}/files/outputs/{output_id}/commit")

    async def ai_capabilities(self, identity: HostIdentity):
        if "ai.inference" not in identity.granted_capabilities:
            raise HostApiError("capability_not_granted", "ControlDeck ai.inference capability is required", status_code=403)
        return await self.request(identity, "GET", f"/{ADDON_ID}/ai/capabilities")

    async def ai_complete(
        self,
        identity: HostIdentity,
        messages: list[dict],
        *,
        temperature: float = 0.0,
        max_tokens: int = 256,
        timeout_seconds: int = 60,
        response_format: dict | None = None,
    ):
        if "ai.inference" not in identity.granted_capabilities:
            raise HostApiError("capability_not_granted", "ControlDeck ai.inference capability is required", status_code=403)
        payload = {
            "capability": "text.generate",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout_seconds": timeout_seconds,
            "response_format": response_format,
        }
        return await self.request(identity, "POST", f"/{ADDON_ID}/ai/complete", json=payload)

    async def ai_release(self, identity: HostIdentity):
        if "ai.inference" not in identity.granted_capabilities:
            raise HostApiError("capability_not_granted", "ControlDeck ai.inference capability is required", status_code=403)
        return await self.request(identity, "POST", f"/{ADDON_ID}/ai/release", json={})

    async def grant_content(self, identity: HostIdentity, grant_id: str, *, max_bytes: int = MAX_GRANT_BYTES) -> bytes:
        if not grant_id.startswith("grant:"): raise ValueError("grant id must start with grant:")
        if not 0 < max_bytes <= MAX_GRANT_BYTES: raise ValueError("grant content bound is invalid")
        path = f"/api/v1/addon-runtime/{ADDON_ID}/grants/{grant_id}/content"; total = 0; chunks: list[bytes] = []
        try:
            async with self._client.stream("GET", path, headers=self._headers(identity.authorization, identity.addon_id)) as response:
                if response.status_code >= 400: raise HostApiError("host_request_rejected", f"ControlDeck rejected HTTP {response.status_code}", status_code=response.status_code)
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > max_bytes: raise HostApiError("host_response_too_large", "grant content exceeds bound")
                    chunks.append(chunk)
        except httpx.HTTPError as exc: raise HostApiError("host_unreachable", "ControlDeck Host API is unreachable") from exc
        return b"".join(chunks)

    async def request(self, identity: HostIdentity, method: str, path: str, *, json: dict | None = None, content: bytes | None = None):
        return await self._raw(method, f"/api/v1/addon-runtime{path}", identity.authorization, identity.addon_id, json=json, content=content)

    async def _raw(self, method: str, path: str, authorization: str, addon_id: str, *, json: dict | None = None, content: bytes | None = None):
        try: response = await self._client.request(method, path, headers=self._headers(authorization, addon_id), json=json, content=content)
        except httpx.HTTPError as exc: raise HostApiError("host_unreachable", "ControlDeck Host API is unreachable") from exc
        if response.status_code >= 400: raise HostApiError("host_request_rejected", f"ControlDeck rejected HTTP {response.status_code}", status_code=response.status_code)
        if len(response.content) > MAX_JSON_RESPONSE_BYTES: raise HostApiError("host_response_too_large", "ControlDeck response too large")
        try: value = response.json()
        except ValueError as exc: raise HostApiError("invalid_host_response", "ControlDeck response is not JSON") from exc
        if not isinstance(value, dict): raise HostApiError("invalid_host_response", "ControlDeck response is not an object")
        return value

    @staticmethod
    def _headers(authorization: str, addon_id: str) -> dict[str, str]:
        return {"Accept": "application/json", "Authorization": authorization, "X-Control-Deck-Addon-ID": addon_id}
