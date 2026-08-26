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
