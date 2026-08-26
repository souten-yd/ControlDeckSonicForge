from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator


_STRONG = "。！？!?\n"
_WEAK = "、，,;；:："


def _limits(language: str) -> tuple[int, int, int]:
    if language == "ja":
        return 8, 28, 72
    return 16, 56, 140


def _boundary(buffer: str, language: str) -> int | None:
    minimum, target, maximum = _limits(language)
    if len(buffer) < minimum:
        return None
    for index, char in enumerate(buffer):
        position = index + 1
        if position >= minimum and char in _STRONG:
            return position
    if len(buffer) >= target:
        candidates = [index + 1 for index, char in enumerate(buffer[:maximum]) if char in _WEAK]
        if candidates:
            return candidates[-1]
    if len(buffer) >= maximum:
        if language != "ja":
            split = buffer.rfind(" ", minimum, maximum)
            if split > 0:
                return split + 1
        return maximum
    return None


async def speech_chunks(
    events: AsyncIterator[dict],
    *,
    language: str,
    idle_flush_seconds: float = 0.35,
) -> AsyncIterator[str]:
    """Convert token/delta events into bounded speech-ready text chunks.

    A producer task keeps consuming the Host AI stream while the consumer waits
    for a punctuation boundary or a short quiet interval. This avoids cancelling
    the underlying HTTP/SSE stream merely because TTS wants to flush early.
    """
    queue: asyncio.Queue[dict | None] = asyncio.Queue(maxsize=128)

    async def produce() -> None:
        try:
            async for event in events:
                await queue.put(event)
        finally:
            await queue.put(None)

    producer = asyncio.create_task(produce(), name="sonicforge-llm-stream-reader")
    buffer = ""
    done = False
    try:
        while not done:
            timeout = idle_flush_seconds if buffer else None
            try:
                item = await asyncio.wait_for(queue.get(), timeout=timeout) if timeout else await queue.get()
            except TimeoutError:
                text = buffer.strip()
                if text:
                    yield text
                    buffer = ""
                continue
            if item is None:
                done = True
            else:
                kind = item.get("type")
                if kind == "content":
                    buffer += str(item.get("content") or "")
                elif kind == "done":
                    done = True
                elif kind == "error":
                    raise RuntimeError(str(item.get("code") or "LLM stream failed"))
            while True:
                cut = _boundary(buffer, language)
                if cut is None:
                    break
                chunk = buffer[:cut].strip()
                buffer = buffer[cut:]
                if chunk:
                    yield chunk
        tail = buffer.strip()
        if tail:
            yield tail
    finally:
        if not producer.done():
            producer.cancel()
        await asyncio.gather(producer, return_exceptions=True)
