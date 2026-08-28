"""sonic-live/2 の音声チャット。

パイプラインを毎回叩くと、そのたびに ASR と TTS のモデルを読み込んで捨てる
ので、返事までが遅い。ライブセッションはワーカーをセッション中ずっと常駐
させたまま、何ターンでも話し続けられる。書かれていたのに繋がっていなかった。
"""
from __future__ import annotations

import importlib
import json
import sys

from fastapi.testclient import TestClient

from sonicforge.edge_protocol import AudioFrame, STREAM_MIC


def load_app():
    for name in list(sys.modules):
        if name.startswith("sonicforge.bootstrap") or name.startswith("sonicforge.app"):
            sys.modules.pop(name, None)
    return importlib.import_module("sonicforge.bootstrap")


def _speak(socket, seconds: float = 0.2) -> None:
    socket.send_json({"type": "input.start"})
    assert socket.receive_json()["type"] == "input.started"
    payload = b"\x00\x00" * 320  # 20ms, 16kHz, mono
    for sequence in range(int(seconds * 50)):
        socket.send_bytes(
            AudioFrame(
                stream=STREAM_MIC,
                sequence=sequence,
                sample_clock=sequence * 320,
                payload=payload,
            ).encode()
        )
    socket.send_json({"type": "input.commit"})


def _drain_turn(socket) -> dict:
    audio_bytes = 0
    transcript = None
    while True:
        message = socket.receive()
        if message.get("bytes") is not None:
            audio_bytes += len(message["bytes"])
            continue
        event = json.loads(message["text"])
        if event["type"] == "asr.final":
            transcript = event.get("text")
        elif event["type"] == "turn.complete":
            return {"complete": event, "audio_bytes": audio_bytes, "transcript": transcript}
        elif event["type"] in {"turn.error", "error"}:
            raise AssertionError(event)


def test_live_v2_is_reachable_and_keeps_its_workers_between_turns(env):
    module = load_app()
    with TestClient(module.app) as client:
        with client.websocket_connect("/addon/v2/live/ws") as socket:
            socket.send_json({
                "type": "hello",
                "session": {"preset": "dictation", "source_language": "ja", "tts_enabled": False},
            })
            ready = socket.receive_json()
            assert ready["type"] == "ready"
            assert ready["protocol"] == "sonic-live/2"
            assert ready["preset"] == "dictation"

            _speak(socket)
            first = _drain_turn(socket)
            assert first["transcript"] == "fake transcription"

            def stats():
                socket.send_json({"type": "ping"})
                while True:
                    event = socket.receive_json()
                    if event["type"] == "pong":
                        return event["worker_stats"]

            first_stats = stats()
            assert first_stats["asr"]["process_starts"] == 1
            assert first_stats["asr"]["requests"] == 1

            _speak(socket)
            second = _drain_turn(socket)
            assert second["transcript"] == "fake transcription"

            # 2 ターン目は同じワーカーが受ける。process_starts が増えるなら
            # 毎ターン起動し直しており、そのたびにモデルの読み込みが挟まる。
            second_stats = stats()
            assert second_stats["asr"]["process_starts"] == 1
            assert second_stats["asr"]["requests"] == 2


def test_voice_chat_preset_requires_the_control_deck_llm(env):
    """会話は ControlDeck の LLM を使う。素の接続では、黙って別物にせず断ること。"""
    module = load_app()
    with TestClient(module.app) as client:
        with client.websocket_connect("/addon/v2/live/ws") as socket:
            socket.send_json({"type": "hello", "session": {"preset": "voice-chat"}})
            event = socket.receive_json()
            assert event["type"] == "error"
            assert "ControlDeck" in event["message"]
