from __future__ import annotations

import struct
import wave
from array import array
from pathlib import Path


def split_on_long_silence(
    source: Path,
    work_dir: Path,
    *,
    minimum_silence_seconds: float = 0.65,
    minimum_segment_seconds: float = 1.0,
) -> list[tuple[Path, float]]:
    try:
        with wave.open(str(source), "rb") as stream:
            channels = stream.getnchannels()
            width = stream.getsampwidth()
            rate = stream.getframerate()
            frames = stream.getnframes()
            compression = stream.getcomptype()
            raw = stream.readframes(frames)
    except (OSError, EOFError, wave.Error):
        return [(source, 0.0)]
    if width != 2 or channels not in {1, 2} or rate <= 0 or compression != "NONE":
        return [(source, 0.0)]

    samples = array("h")
    samples.frombytes(raw)
    if struct.pack("=H", 1) != struct.pack("<H", 1):
        samples.byteswap()
    frame_count = len(samples) // channels
    window_frames = max(1, round(rate * 0.02))
    minimum_silent_windows = max(1, round(minimum_silence_seconds * rate / window_frames))
    peak = max((abs(value) for value in samples), default=0)
    threshold = max(64, round(peak * 0.01))
    silent_windows: list[bool] = []
    for start in range(0, frame_count, window_frames):
        stop = min(frame_count, start + window_frames)
        begin_sample = start * channels
        end_sample = stop * channels
        silent_windows.append(
            max((abs(value) for value in samples[begin_sample:end_sample]), default=0)
            <= threshold
        )

    boundaries: list[int] = []
    index = 0
    while index < len(silent_windows):
        if not silent_windows[index]:
            index += 1
            continue
        end = index + 1
        while end < len(silent_windows) and silent_windows[end]:
            end += 1
        if end - index >= minimum_silent_windows:
            boundary = min(frame_count, ((index + end) * window_frames) // 2)
            if minimum_segment_seconds * rate <= boundary <= frame_count - minimum_segment_seconds * rate:
                boundaries.append(boundary)
        index = end
    if not boundaries:
        return [(source, 0.0)]

    work_dir.mkdir(parents=True, exist_ok=True)
    points = [0, *boundaries, frame_count]
    segments: list[tuple[Path, float]] = []
    for number, (start, stop) in enumerate(zip(points, points[1:])):
        target = work_dir / f"asr-segment-{number:03d}.wav"
        with wave.open(str(target), "wb") as stream:
            stream.setnchannels(channels)
            stream.setsampwidth(width)
            stream.setframerate(rate)
            stream.writeframes(raw[start * channels * width : stop * channels * width])
        segments.append((target, start / rate))
    return segments


def merge_transcripts(results: list[tuple[dict, float]]) -> dict:
    texts: list[str] = []
    chunks: list[dict] = []
    for result, offset in results:
        text = str(result.get("text") or "").strip()
        if text:
            texts.append(text)
        for item in result.get("chunks", []) or []:
            timestamp = item.get("timestamp") or (None, None)
            start = timestamp[0]
            end = timestamp[1]
            chunks.append(
                {
                    "text": item.get("text", ""),
                    "start": start + offset if isinstance(start, (int, float)) else None,
                    "end": end + offset if isinstance(end, (int, float)) else None,
                }
            )
    return {"text": " ".join(texts), "chunks": chunks}
