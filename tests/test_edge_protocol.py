import pytest

from sonicforge.edge_protocol import (
    AudioFrame,
    BoundedAudioQueue,
    EdgeProtocolError,
    SequenceTracker,
    STREAM_MIC,
    STREAM_SPEAKER,
)


def test_audio_frame_roundtrip():
    frame = AudioFrame(
        stream=STREAM_MIC,
        sequence=7,
        sample_clock=2240,
        payload=b"\x01\x02" * 320,
    )
    decoded = AudioFrame.decode(frame.encode())
    assert decoded == frame


def test_audio_frame_rejects_truncation_and_size_mismatch():
    frame = AudioFrame(
        stream=STREAM_SPEAKER,
        sequence=1,
        sample_clock=0,
        payload=b"x" * 640,
    ).encode()
    with pytest.raises(EdgeProtocolError):
        AudioFrame.decode(frame[:-1])
    with pytest.raises(EdgeProtocolError):
        AudioFrame.decode(b"bad")


def test_sequence_tracker_detects_gap_and_old_frame():
    tracker = SequenceTracker()
    first = tracker.observe(AudioFrame(STREAM_MIC, 10, 0, b"a"))
    assert first.expected is None
    gap = tracker.observe(AudioFrame(STREAM_MIC, 12, 640, b"b"))
    assert gap.expected == 11
    assert gap.gap == 1
    old = tracker.observe(AudioFrame(STREAM_MIC, 11, 320, b"c"))
    assert old.duplicate_or_old is True


def test_bounded_audio_queue_fails_closed_on_overflow():
    queue = BoundedAudioQueue(max_bytes=1280, max_frames=2)
    queue.push(AudioFrame(STREAM_MIC, 1, 0, b"a" * 640))
    queue.push(AudioFrame(STREAM_MIC, 2, 320, b"b" * 640))
    assert queue.high_water_bytes == 1280
    with pytest.raises(EdgeProtocolError, match="overflow"):
        queue.push(AudioFrame(STREAM_MIC, 3, 640, b"c" * 640))
    assert queue.pop().sequence == 1
    assert queue.frames_queued == 1
