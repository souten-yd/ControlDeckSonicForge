import importlib
import json
import sys

from fastapi.testclient import TestClient

from sonicforge.edge_protocol import AudioFrame, STREAM_MIC
from sonicforge.live_api import _legacy_m5_session


def load_app():
    for name in list(sys.modules):
        if name.startswith("sonicforge.bootstrap") or name.startswith("sonicforge.app"):
            sys.modules.pop(name, None)
    return importlib.import_module("sonicforge.bootstrap")


def live_contract():
    return {
        "preset": "m5-dictation",
        "pipeline": {
            "pipeline": "test-live-echo",
            "input": {"kind": "audio_stream", "stream_id": "mic"},
            "stages": [
                {
                    "id": "asr",
                    "kind": "speech.asr",
                    "routing": {"engine": "fake", "model": None, "device": "auto"},
                },
                {
                    "id": "tts",
                    "kind": "speech.tts",
                    "routing": {"engine": "fake", "model": None, "device": "auto"},
                },
            ],
            "delivery": {"mode": "websocket", "profile": "m5-pcm"},
        },
        "device": {
            "protocol": "sonic-edge/1",
            "device_class": "simulator",
            "model": "pytest",
            "firmware": "0.1.0",
            "audio": {
                "input": [{"codec": "pcm_s16le", "rate": 16000, "channels": 1, "frame_ms": 20}],
                "output": [{"codec": "pcm_s16le", "rate": 24000, "channels": 1, "frame_ms": 20}],
                "aec": False,
                "vad": False,
                "wake": False,
            },
            "ui": {"display": False, "touch": False, "buttons": 1},
        },
        "transport": "websocket",
        "save_transcript": False,
        "save_input_audio": False,
        "save_output_audio": False,
    }


def test_half_duplex_ptt_runs_as_durable_turn_and_streams_audio(env):
    module = load_app()
    with TestClient(module.app) as client:
        with client.websocket_connect("/addon/v1/live/ws") as socket:
            socket.send_json({"type": "hello", "session": live_contract()})
            ready = socket.receive_json()
            assert ready["type"] == "ready"
            assert ready["protocol"] == "sonic-live/1"
            assert ready["mode"] == "half_duplex_ptt"
            assert ready["input_format"]["rate"] == 16000
            assert ready["output_format"]["rate"] == 24000

            socket.send_json({"type": "ptt.start"})
            assert socket.receive_json()["type"] == "ptt.started"
            # 10 x 20 ms, 16 kHz, mono, signed 16-bit PCM silence.
            payload = b"\x00\x00" * 320
            for sequence in range(10):
                socket.send_bytes(
                    AudioFrame(
                        stream=STREAM_MIC,
                        sequence=sequence,
                        sample_clock=sequence * 320,
                        payload=payload,
                    ).encode()
                )
            socket.send_json({"type": "ptt.stop"})

            transcript = None
            complete = None
            speaker_bytes = 0
            saw_audio_start = False
            while complete is None:
                message = socket.receive()
                if message.get("bytes") is not None:
                    speaker_bytes += len(message["bytes"])
                    continue
                text = message.get("text")
                assert text is not None
                event = json.loads(text)
                if event["type"] == "turn.transcript":
                    transcript = event["text"]
                elif event["type"] == "turn.audio.start":
                    saw_audio_start = True
                elif event["type"] == "turn.complete":
                    complete = event
                elif event["type"] == "turn.error":
                    raise AssertionError(event)

            assert transcript == "fake transcription"
            assert saw_audio_start is True
            assert speaker_bytes > 0
            assert complete["job_id"].startswith("job:")
            assert complete["timing"]["basis"] == "ptt.stop"
            assert (
                complete["timing"]["end_of_speech_to_asr_final_ms"] >= 0
            )
            assert complete["timing"]["full_response_completion_ms"] >= 0
            job = client.get(
                "/addon/v1/jobs/" + complete["job_id"].replace(":", "%3A")
            ).json()
            assert job["task"] == "live.turn"
            assert job["state"] == "succeeded"
            assert job["result"]["timing"] == complete["timing"]
            socket.send_json({"type": "close"})
            assert socket.receive()["type"] == "websocket.close"


def test_live_v1_rejects_host_ai_without_control_deck_identity(env):
    module = load_app()
    contract = live_contract()
    contract["preset"] = "voice-assistant"
    contract["pipeline"]["stages"].insert(1, {"id": "llm", "kind": "host.ai.text"})
    with TestClient(module.app) as client:
        with client.websocket_connect("/addon/v1/live/ws") as socket:
            socket.send_json({"type": "hello", "session": contract})
            error = socket.receive_json()
            assert error["type"] == "error"
            assert error["code"] == "protocol_error"
            assert "Host AI" in error["message"]


def test_existing_m5companion_v2_raw_pcm_contract(env):
    module = load_app()
    with TestClient(module.app) as client:
        with client.websocket_connect("/addon/v1/live/ws") as socket:
            socket.send_json(
                {
                    "type": "hello",
                    "device": "m5cores3",
                    "name": "pytest-m5",
                    "protocol": 2,
                    "fw": "0.3.0",
                    "audio_format": "pcm_s16le",
                    "audio_rate": 16000,
                    "chunk_samples": 320,
                }
            )
            ready = socket.receive_json()
            assert ready["protocol"] == "m5companion/2"
            assert ready["output_format"]["rate"] == 16000
            assert ready["sequence_tracking"] is False
            assert socket.receive_json()["state"] == "idle"

            socket.send_json(
                {"type": "device.state", "state": "idle", "expression": "happy"}
            )
            socket.send_json(
                {
                    "type": "device.telemetry",
                    "battery": 80,
                    "charging": False,
                    "heap": 100000,
                    "fps": 30.0,
                    "rssi": -50,
                    "dropped": 0,
                }
            )

            socket.send_json(
                {"type": "listen.begin", "format": "pcm_s16le", "rate": 16000}
            )
            assert socket.receive_json()["state"] == "listening"
            payload = b"\x00\x00" * 320
            for _ in range(10):
                socket.send_bytes(payload)
            socket.send_json({"type": "listen.end"})

            saw_thinking = False
            saw_speech_begin = False
            saw_speech_end = False
            speaker_bytes = 0
            idle = False
            while not idle:
                message = socket.receive()
                if message.get("bytes") is not None:
                    assert not message["bytes"].startswith(b"SFA1")
                    speaker_bytes += len(message["bytes"])
                    continue
                event = json.loads(message["text"])
                if event["type"] == "state" and event["state"] == "thinking":
                    saw_thinking = True
                elif event["type"] == "speech.begin":
                    saw_speech_begin = True
                elif event["type"] == "speech.end":
                    saw_speech_end = True
                elif event["type"] == "state" and event["state"] == "idle":
                    idle = True

            assert saw_thinking is True
            assert saw_speech_begin is True
            assert saw_speech_end is True
            assert speaker_bytes > 0
            jobs = client.get("/addon/v1/jobs").json()["jobs"]
            assert jobs[0]["task"] == "live.turn"
            assert jobs[0]["state"] == "succeeded"
            socket.send_json({"type": "close"})
            assert socket.receive()["type"] == "websocket.close"


def test_existing_m5companion_host_voice_reply_is_bounded():
    session = _legacy_m5_session(object())
    llm = session.pipeline.stages[1]
    assert llm.kind == "host.ai.text"
    assert llm.parameters["max_tokens"] == 96
    assert llm.parameters["timeout_seconds"] == 120
    assert "under 80 characters" in llm.parameters["system_prompt"]
