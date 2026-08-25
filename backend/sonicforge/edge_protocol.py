from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import struct

MAGIC = b"SFA1"
VERSION = 1
STREAM_MIC = 1
STREAM_SPEAKER = 2
MAX_AUDIO_PAYLOAD = 8192
_HEADER = struct.Struct("!4sBBBBIIH")


class EdgeProtocolError(ValueError):
    pass


@dataclass(frozen=True)
class AudioFrame:
    stream: int
    sequence: int
    sample_clock: int
    payload: bytes
    flags: int = 0

    def encode(self) -> bytes:
        if self.stream not in {STREAM_MIC, STREAM_SPEAKER}:
            raise EdgeProtocolError("unsupported edge audio stream")
        if not 0 <= self.flags <= 0xFF:
            raise EdgeProtocolError("edge audio flags out of range")
        if not 0 <= self.sequence <= 0xFFFFFFFF:
            raise EdgeProtocolError("edge audio sequence out of range")
        if not 0 <= self.sample_clock <= 0xFFFFFFFF:
            raise EdgeProtocolError("edge audio sample clock out of range")
        if not 0 < len(self.payload) <= MAX_AUDIO_PAYLOAD:
            raise EdgeProtocolError("edge audio payload size is invalid")
        return _HEADER.pack(
            MAGIC,
            VERSION,
            self.stream,
            self.flags,
            0,
            self.sequence,
            self.sample_clock,
            len(self.payload),
        ) + self.payload

    @classmethod
    def decode(cls, value: bytes) -> "AudioFrame":
        if len(value) < _HEADER.size:
            raise EdgeProtocolError("edge audio frame is truncated")
        magic, version, stream, flags, reserved, sequence, sample_clock, size = _HEADER.unpack_from(value)
        if magic != MAGIC or version != VERSION:
            raise EdgeProtocolError("edge audio frame version is unsupported")
        if reserved != 0:
            raise EdgeProtocolError("edge audio reserved bits must be zero")
        if stream not in {STREAM_MIC, STREAM_SPEAKER}:
            raise EdgeProtocolError("unsupported edge audio stream")
        if not 0 < size <= MAX_AUDIO_PAYLOAD:
            raise EdgeProtocolError("edge audio payload size is invalid")
        if len(value) != _HEADER.size + size:
            raise EdgeProtocolError("edge audio payload length mismatch")
        return cls(
            stream=stream,
            sequence=sequence,
            sample_clock=sample_clock,
            payload=value[_HEADER.size :],
            flags=flags,
        )


@dataclass(frozen=True)
class SequenceObservation:
    expected: int | None
    received: int
    gap: int
    duplicate_or_old: bool


class SequenceTracker:
    def __init__(self) -> None:
        self._next: dict[int, int] = {}

    def observe(self, frame: AudioFrame) -> SequenceObservation:
        expected = self._next.get(frame.stream)
        duplicate_or_old = False
        gap = 0
        if expected is not None:
            delta = (frame.sequence - expected) & 0xFFFFFFFF
            if delta == 0:
                pass
            elif delta < 0x80000000:
                gap = delta
            else:
                duplicate_or_old = True
        if not duplicate_or_old:
            self._next[frame.stream] = (frame.sequence + 1) & 0xFFFFFFFF
        return SequenceObservation(
            expected=expected,
            received=frame.sequence,
            gap=gap,
            duplicate_or_old=duplicate_or_old,
        )


class BoundedAudioQueue:
    """A fixed-duration/byte queue for live audio.

    This helper deliberately drops nothing by itself. Callers decide whether an
    overflow terminates microphone input or drops stale playback. That policy is
    semantically different for uplink and downlink.
    """

    def __init__(self, *, max_bytes: int, max_frames: int) -> None:
        if max_bytes <= 0 or max_frames <= 0:
            raise ValueError("edge audio queue bounds must be positive")
        self.max_bytes = max_bytes
        self.max_frames = max_frames
        self._frames: deque[AudioFrame] = deque()
        self._bytes = 0
        self.high_water_bytes = 0

    def can_push(self, frame: AudioFrame) -> bool:
        return (
            len(self._frames) + 1 <= self.max_frames
            and self._bytes + len(frame.payload) <= self.max_bytes
        )

    def push(self, frame: AudioFrame) -> None:
        if not self.can_push(frame):
            raise EdgeProtocolError("edge audio queue overflow")
        self._frames.append(frame)
        self._bytes += len(frame.payload)
        self.high_water_bytes = max(self.high_water_bytes, self._bytes)

    def pop(self) -> AudioFrame | None:
        if not self._frames:
            return None
        frame = self._frames.popleft()
        self._bytes -= len(frame.payload)
        return frame

    @property
    def bytes_queued(self) -> int:
        return self._bytes

    @property
    def frames_queued(self) -> int:
        return len(self._frames)
