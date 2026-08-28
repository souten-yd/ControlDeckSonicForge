import wave
from pathlib import Path

from worker_packs.whisper.audio_segments import merge_transcripts, split_on_long_silence


def _write_fixture(path: Path) -> None:
    rate = 1000
    tone = (1000).to_bytes(2, "little", signed=True) * rate
    silence = b"\x00\x00" * rate
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(rate)
        stream.writeframes(tone + silence + tone)


def test_long_silence_segments_pcm_wav_and_offsets_timestamps(tmp_path):
    source = tmp_path / "mixed.wav"
    _write_fixture(source)
    segments = split_on_long_silence(source, tmp_path / "segments")
    assert len(segments) == 2
    assert segments[0][1] == 0.0
    assert 1.4 < segments[1][1] < 1.6

    merged = merge_transcripts(
        [
            ({"text": "こんにちは", "chunks": [{"text": "こんにちは", "timestamp": (0.1, 0.8)}]}, segments[0][1]),
            ({"text": "hello", "chunks": [{"text": "hello", "timestamp": (0.2, 0.9)}]}, segments[1][1]),
        ]
    )
    assert merged["text"] == "こんにちは hello"
    assert merged["chunks"][1]["start"] > 1.6


def _wav(path, samples, rate=16000):
    import struct, wave
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(rate)
        stream.writeframes(b"".join(struct.pack("<h", int(v)) for v in samples))
    return path


def test_silence_and_room_tone_are_not_transcribed(tmp_path):
    """話していない録音は、モデルに渡さず空で返せること。

    whisper は黙らない。無音や暗騒音を渡すと "Thank you." や
    「ご視聴ありがとうございました」といった学習データの締めの言葉を出す。
    実機の暗騒音では「ごめん」も出た。文言を数え上げても切りがないので、
    判定は音の大きさで行う。
    """
    import math, random
    from worker_packs.whisper.audio_segments import speech_level

    silent = _wav(tmp_path / "silence.wav", [0] * 16000)
    assert speech_level(silent) == (0.0, 0.0)

    random.seed(7)
    tone = _wav(tmp_path / "room.wav", [random.uniform(-100, 100) for _ in range(16000)])
    rms, peak = speech_level(tone)
    assert peak < 0.02 or rms < 0.002, (rms, peak)

    # 実際の声は山が高い。同じ判定で通らなければならない。
    voice = _wav(
        tmp_path / "voice.wav",
        [9000 * math.sin(2 * math.pi * 220 * i / 16000) for i in range(16000)],
    )
    rms, peak = speech_level(voice)
    assert not (peak < 0.02 or rms < 0.002), (rms, peak)


def test_known_silence_captions_are_recognised():
    from worker_packs.whisper.audio_segments import looks_like_silence_caption

    for value in ("Thank you.", "ご視聴ありがとうございました", "♪", "  "):
        assert looks_like_silence_caption(value), value
    assert not looks_like_silence_caption("今日の会議は10時から始めます")
