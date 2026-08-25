import pytest
from pydantic import ValidationError

from sonicforge.pipeline_schema import LiveSessionCreate, PipelineRequest, compile_pipeline


def test_text_llm_tts_start_stop_compiles():
    request = PipelineRequest.model_validate({
        "pipeline": "voice-assistant",
        "input": {"kind": "text", "text": "今日の作業をまとめて"},
        "stages": [
            {"id": "asr", "kind": "speech.asr"},
            {"id": "llm", "kind": "host.ai.text"},
            {"id": "tts", "kind": "speech.tts"},
        ],
        "start_at": "llm",
        "stop_after": "tts",
        "delivery": {"mode": "asset", "profile": "voice-wav"},
    })
    compiled = compile_pipeline(request)
    assert compiled.stage_ids == ("llm", "tts")
    assert compiled.input_type == "text"
    assert compiled.output_type == "audio"


def test_audio_asr_llm_text_stop_compiles():
    request = PipelineRequest.model_validate({
        "input": {"kind": "audio_grant", "grant_id": "grant:audio"},
        "stages": [
            {"id": "asr", "kind": "speech.asr"},
            {"id": "llm", "kind": "host.ai.text"},
            {"id": "tts", "kind": "speech.tts"},
        ],
        "stop_after": "llm",
        "delivery": {"mode": "text", "profile": "plain"},
    })
    compiled = compile_pipeline(request)
    assert compiled.output_type == "text"
    assert compiled.stage_ids == ("asr", "llm")


def test_llm_to_asr_is_rejected():
    with pytest.raises(ValidationError, match="type mismatch"):
        PipelineRequest.model_validate({
            "input": {"kind": "text", "text": "hello"},
            "stages": [
                {"id": "llm", "kind": "host.ai.text"},
                {"id": "asr", "kind": "speech.asr"},
            ],
            "delivery": {"mode": "text"},
        })


def test_websocket_allows_text_dictation_output():
    request = PipelineRequest.model_validate({
        "pipeline": "m5-dictation",
        "input": {"kind": "audio_stream", "stream_id": "mic"},
        "stages": [{"id": "asr", "kind": "speech.asr"}],
        "delivery": {"mode": "websocket", "profile": "plain"},
    })
    compiled = compile_pipeline(request)
    assert compiled.output_type == "text"
    assert compiled.stage_ids == ("asr",)


def test_asset_delivery_rejects_text_output():
    with pytest.raises(ValidationError, match="asset delivery requires audio output"):
        PipelineRequest.model_validate({
            "input": {"kind": "text", "text": "hello"},
            "stages": [{"id": "llm", "kind": "host.ai.text"}],
            "delivery": {"mode": "asset"},
        })


def test_m5_voice_agent_contract():
    session = LiveSessionCreate.model_validate({
        "preset": "m5-voice-agent",
        "pipeline": {
            "input": {"kind": "audio_stream", "stream_id": "mic"},
            "stages": [
                {"id": "asr", "kind": "speech.asr", "language": "auto"},
                {"id": "llm", "kind": "host.ai.text"},
                {"id": "tts", "kind": "speech.tts", "voice_id": "voice:default"},
            ],
            "delivery": {"mode": "websocket", "profile": "m5-pcm"},
        },
        "device": {
            "protocol": "sonic-edge/1",
            "device_class": "m5",
            "model": "core-s3",
            "firmware": "0.1.0",
            "audio": {
                "input": [{"codec": "pcm_s16le", "rate": 16000, "channels": 1, "frame_ms": 20}],
                "output": [{"codec": "pcm_s16le", "rate": 24000, "channels": 1, "frame_ms": 20}],
                "aec": True,
                "vad": True,
                "wake": True,
            },
            "ui": {"display": True, "touch": True, "buttons": 2},
            "psram_bytes": 8388608,
        },
        "transport": "websocket",
    })
    assert session.device is not None
    assert session.device.audio.vad is True
    assert compile_pipeline(session.pipeline).output_type == "audio"
