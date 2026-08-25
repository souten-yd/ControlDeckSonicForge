from __future__ import annotations

import time


class SpeakableTextChunker:
    """Turn streaming LLM text into stable TTS-sized clauses.

    The chunker favors natural strong punctuation, then softer punctuation once
    enough context exists, and finally a bounded latency/length fallback. It does
    not revise already-emitted text, which is important for simultaneous playback.
    """

    STRONG = "。！？!?\n"
    SOFT = "、，,；;：:"

    def __init__(
        self,
        *,
        min_chars: int = 8,
        soft_chars: int = 22,
        max_chars: int = 64,
        max_wait_seconds: float = 0.45,
        clock=time.monotonic,
    ) -> None:
        self.min_chars = min_chars
        self.soft_chars = soft_chars
        self.max_chars = max_chars
        self.max_wait_seconds = max_wait_seconds
        self.clock = clock
        self.buffer = ""
        self.last_emit = clock()

    def feed(self, fragment: str) -> list[str]:
        if fragment:
            self.buffer += fragment
        chunks: list[str] = []
        while True:
            boundary = self._boundary()
            if boundary is None:
                break
            chunk = self.buffer[:boundary].strip()
            self.buffer = self.buffer[boundary:]
            if chunk:
                chunks.append(chunk)
                self.last_emit = self.clock()
        return chunks

    def _boundary(self) -> int | None:
        if not self.buffer.strip():
            return None
        for index, char in enumerate(self.buffer, start=1):
            if char in self.STRONG and index >= self.min_chars:
                return index
        if len(self.buffer) >= self.soft_chars:
            for index in range(min(len(self.buffer), self.max_chars), self.min_chars - 1, -1):
                if self.buffer[index - 1] in self.SOFT:
                    return index
        if len(self.buffer) >= self.max_chars:
            # Prefer whitespace near the cap for English; Japanese commonly has
            # no whitespace, so the hard bound is still valid.
            window = self.buffer[: self.max_chars]
            split = max(window.rfind(" "), window.rfind("\t"))
            if split + 1 >= self.min_chars:
                return split + 1
            return self.max_chars
        if (
            len(self.buffer.strip()) >= self.min_chars
            and self.clock() - self.last_emit >= self.max_wait_seconds
        ):
            return len(self.buffer)
        return None

    def flush(self) -> list[str]:
        value = self.buffer.strip()
        self.buffer = ""
        if not value:
            return []
        self.last_emit = self.clock()
        return [value]
