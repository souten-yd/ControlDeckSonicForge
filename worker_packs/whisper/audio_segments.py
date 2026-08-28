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


def speech_level(source: Path) -> tuple[float, float]:
    """Return (rms, peak) of a 16-bit WAV as fractions of full scale.

    Whisper is trained to always produce text. Handed silence or room tone it
    invents a caption - "Thank you." and "ご視聴ありがとうございました。" are
    the ones it reaches for most, because they end so many of its training
    clips. No decoding threshold catches that reliably, but the level of the
    audio does: nobody spoke, so there is nothing to transcribe.
    """
    try:
        with wave.open(str(source), "rb") as stream:
            if stream.getsampwidth() != 2 or stream.getcomptype() != "NONE":
                return (1.0, 1.0)
            channels = max(1, stream.getnchannels())
            raw = stream.readframes(stream.getnframes())
    except (OSError, EOFError, wave.Error):
        return (1.0, 1.0)

    samples = array("h")
    samples.frombytes(raw[: len(raw) - (len(raw) % (2 * channels))])
    if struct.pack("=H", 1) != struct.pack("<H", 1):
        samples.byteswap()
    if not samples:
        return (0.0, 0.0)

    total = 0
    peak = 0
    for value in samples:
        total += value * value
        if abs(value) > peak:
            peak = abs(value)
    rms = (total / len(samples)) ** 0.5
    return (rms / 32768.0, peak / 32768.0)


# 無音でwhisperが出しがちな決まり文句。実際に話していれば普通に通したいので、
# これらは音が十分に小さいときだけ捨てる。
HALLUCINATION_PHRASES = frozenset(
    {
        "thank you",
        "thank you.",
        "thanks for watching",
        "thanks for watching!",
        "thank you for watching",
        "you",
        "ご視聴ありがとうございました",
        "ご視聴ありがとうございました。",
        "ご清聴ありがとうございました",
        "ご清聴ありがとうございました。",
        "おやすみなさい",
        "本日はご覧いただきありがとうございます",
    }
)


def looks_like_silence_caption(text: str) -> bool:
    stripped = text.strip().strip("♪♬〜~").strip()
    return not stripped or stripped.lower() in HALLUCINATION_PHRASES
