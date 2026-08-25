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


def test_meeting_spools_audio_and_persists_final_segments_without_duration_limit(env):
    module = load_app()
    with TestClient(module.app) as client:
        with client.websocket_connect("/addon/v1/meetings/ws") as socket:
            socket.send_json(
                {
                    "type": "hello",
                    "meeting": {
                        "title": "pytest meeting",
                        "source_language": "ja",
                        "translate": False,
                        "summarize": False,
                        "chunk_seconds": 5,
                    },
                }
            )
            ready = socket.receive_json()
            assert ready["type"] == "ready"
            assert ready["protocol"] == "sonic-meeting/1"
            assert ready["duration_limit_seconds"] is None
            assert ready["spool"]["policy"] == "ram-first-disk-fallback"
            meeting_id = ready["meeting_id"]

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
            socket.send_json({"type": "stop"})

            final = None
            complete = None
            while complete is None:
                message = socket.receive()
                text = message.get("text")
                assert text is not None
                event = json.loads(text)
                if event["type"] == "meeting.segment.final":
                    final = event
                elif event["type"] == "meeting.complete":
                    complete = event
                elif event["type"] in {"meeting.segment.error", "error"}:
                    raise AssertionError(event)

            assert final is not None
            assert final["sequence"] == 0
            assert final["source_text"] == "fake transcription"
            assert complete["meeting_id"] == meeting_id

        stored = client.get(f"/addon/v1/meetings/{meeting_id}")
        assert stored.status_code == 200
        body = stored.json()
        assert body["state"] == "completed"
        assert len(body["segments"]) == 1
        assert body["segments"][0]["state"] == "final"
        assert body["segments"][0]["source_text"] == "fake transcription"

        transcript = client.get(f"/addon/v1/meetings/{meeting_id}/transcript.txt")
        assert transcript.status_code == 200
        assert "fake transcription" in transcript.text
