from __future__ import annotations

import re
from typing import Awaitable, Callable

from .host.client import ControlDeckHostClient, HostApiError, HostIdentity

ProgressCallback = Callable[[float, str], Awaitable[None]]
_JAPANESE_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
_SPACE_RE = re.compile(r"\s+")


def likely_japanese(text: str) -> bool:
    return bool(_JAPANESE_RE.search(text))


def _clean_engine_prompt(value: str) -> str:
    prompt = _SPACE_RE.sub(" ", value.strip())
    if prompt.startswith("```") and prompt.endswith("```"):
        prompt = prompt[3:-3].strip()
    prompt = prompt.strip(" \t\r\n`\"'")
    prompt = _SPACE_RE.sub(" ", prompt)
    if not prompt or len(prompt) > 600:
        raise ValueError("normalized audio prompt is empty or too long")
    return prompt


async def normalize_sfx_prompt(
    request: dict,
    *,
    identity: HostIdentity | None,
    host_client: ControlDeckHostClient | None,
    progress: ProgressCallback | None = None,
) -> dict:
    """Normalize Japanese SFX descriptions for English-conditioned engines.

    This is intentionally a durable-job helper, not browser state. The public
    prompt remains untouched; the worker receives a private engine prompt and
    provenance metadata records both forms.
    """

    if not str(request.get("task") or "").startswith("audio."):
        return request
    if request.get("routing", {}).get("engine") == "fake":
        return request

    updated = dict(request)
    inp = dict(updated.get("input") or {})
    user_prompt = str(inp.get("prompt") or inp.get("description") or "").strip()
    if not user_prompt:
        return request

    if not likely_japanese(user_prompt):
        inp["_internal_engine_prompt"] = user_prompt
        inp["_internal_prompt_normalization"] = {
            "state": "not_required",
            "user_prompt": user_prompt,
            "user_prompt_language": "en",
            "engine_prompt": user_prompt,
            "engine_prompt_language": "en",
            "normalizer": "none",
        }
        updated["input"] = inp
        return updated

    metadata = {
        "state": "unavailable",
        "user_prompt": user_prompt,
        "user_prompt_language": "ja",
        "engine_prompt": user_prompt,
        "engine_prompt_language": "unknown",
        "normalizer": "none",
    }

    if (
        identity is None
        or host_client is None
        or "ai.inference" not in identity.granted_capabilities
    ):
        inp["_internal_engine_prompt"] = user_prompt
        inp["_internal_prompt_normalization"] = metadata
        updated["input"] = inp
        if progress is not None:
            await progress(
                0.03,
                "Japanese SFX prompt normalization unavailable; using the original prompt",
            )
        return updated

    attempted = False
    try:
        capabilities = await host_client.ai_capabilities(identity)
        text_cap = capabilities.get("text.generate")
        if not isinstance(text_cap, dict) or text_cap.get("available") is not True:
            raise HostApiError(
                "ai_target_unavailable",
                "ControlDeck text.generate is unavailable",
                status_code=503,
            )
        if progress is not None:
            await progress(0.03, "Normalizing Japanese SFX prompt")
        attempted = True
        response = await host_client.ai_complete(
            identity,
            [
                {
                    "role": "system",
                    "content": (
                        "Translate and rewrite the user's Japanese sound-effect description "
                        "into one concise English acoustic prompt for a text-to-audio model. "
                        "Preserve the requested events, materials, order, intensity, environment, "
                        "and timing. Do not add music, speech, explanations, labels, quotes, or "
                        "formatting. Return only the English prompt."
                    ),
                },
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            max_tokens=160,
            timeout_seconds=60,
        )
        content = response.get("content")
        if not isinstance(content, str):
            raise ValueError("ControlDeck AI did not return prompt text")
        engine_prompt = _clean_engine_prompt(content)
        metadata = {
            "state": "normalized",
            "user_prompt": user_prompt,
            "user_prompt_language": "ja",
            "engine_prompt": engine_prompt,
            "engine_prompt_language": "en",
            "normalizer": "controldeck.ai.text.generate",
        }
        inp["_internal_engine_prompt"] = engine_prompt
    except (HostApiError, ValueError) as exc:
        metadata["state"] = "failed"
        metadata["reason"] = str(exc)[:200]
        inp["_internal_engine_prompt"] = user_prompt
        if progress is not None:
            await progress(
                0.04,
                "Japanese SFX prompt normalization failed; using the original prompt",
            )
    finally:
        if attempted:
            try:
                await host_client.ai_release(identity)
            except HostApiError:
                pass

    inp["_internal_prompt_normalization"] = metadata
    updated["input"] = inp
    return updated
