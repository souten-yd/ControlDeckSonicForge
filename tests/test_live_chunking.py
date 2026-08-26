from sonicforge.live_chunking import SpeakableTextChunker


def test_japanese_strong_punctuation_emits_stable_clause():
    chunker = SpeakableTextChunker(min_chars=4)
    assert chunker.feed("これは") == []
    assert chunker.feed("テストです。次") == ["これはテストです。"]
    assert chunker.flush() == ["次"]


def test_soft_punctuation_and_hard_length_bound_reduce_tts_latency():
    chunker = SpeakableTextChunker(min_chars=4, soft_chars=8, max_chars=12)
    assert chunker.feed("abcdef、ghij") == ["abcdef、"]
    assert chunker.flush() == ["ghij"]

    bounded = SpeakableTextChunker(min_chars=4, soft_chars=20, max_chars=8)
    chunks = bounded.feed("abcdefghijk")
    assert chunks == ["abcdefgh"]
    assert bounded.flush() == ["ijk"]


def test_elapsed_time_can_emit_without_waiting_for_full_sentence():
    now = [0.0]
    chunker = SpeakableTextChunker(
        min_chars=4,
        soft_chars=20,
        max_chars=64,
        max_wait_seconds=0.4,
        clock=lambda: now[0],
    )
    assert chunker.feed("短い応答") == []
    now[0] = 0.5
    assert chunker.feed("") == ["短い応答"]
