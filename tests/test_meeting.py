import importlib
import json
import sys

from fastapi.testclient import TestClient

from sonicforge.edge_protocol import AudioFrame, STREAM_MIC
from sonicforge.host.client import HostIdentity
from sonicforge.workers import WorkerResult


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


def test_hosted_meeting_keeps_asr_loaded_across_segments(env, monkeypatch):
    from sonicforge import meeting_api

    events = []

    class FakeHostSession:
        def __init__(self, *, identity, **_kwargs):
            self.current = identity

        async def start(self, *, keep_llm_warm):
            assert keep_llm_warm is True

        async def identity(self):
            return self.current

        async def ensure_llm_hold(self):
            events.append("ensure-ai")

        async def release_llm_hold(self, *, stop_runtime=False):
            events.append(f"release-ai:{stop_runtime}")

        async def close(self, *, failed=False):
            events.append(f"close:{failed}")

    class FakeWorkerPool:
        def __init__(self, **_kwargs):
            pass

        async def execute(self, _request, _work_dir, progress):
            events.append("asr")
            await progress(1.0, "done")
            return WorkerResult(
                engine_id="fake-asr",
                engine_version="1",
                model_id="fake-asr",
                model_revision=None,
                model_license_id=None,
                output_path=None,
                payload={"text": "Meeting transcript", "segments": []},
            )

        async def evict(self, key):
            events.append(f"evict:{key}")

        async def close(self):
            events.append("pool-close")

    monkeypatch.setattr(meeting_api, "LiveHostSession", FakeHostSession)
    monkeypatch.setattr(meeting_api, "LiveWorkerPool", FakeWorkerPool)
    module = load_app()

    identity = HostIdentity(
        "Bearer test",
        subject="18",
        expires_at=2_000_000_000,
        granted_capabilities=frozenset({"jobs.write", "ai.inference"}),
    )

    async def authenticate(_headers):
        return identity

    async def ai_complete(_identity, messages, **_kwargs):
        instruction = messages[0]["content"]
        if instruction.startswith("Translate"):
            events.append("ai:translate")
            return {"content": "会議の文字起こし"}
        if instruction.startswith("Summarize"):
            events.append("ai:summary-chunk")
            return {"content": "Partial summary"}
        events.append("ai:summary-final")
        return {"content": "# Summary\nDone"}

    monkeypatch.setattr(module.base.host_client, "authenticate", authenticate)
    monkeypatch.setattr(module.base.host_client, "ai_complete", ai_complete)

    with TestClient(module.app) as client:
        with client.websocket_connect(
            "/addon/v1/meetings/ws",
            headers={
                "Authorization": "Bearer test",
                "X-Control-Deck-Addon-ID": "sonic-forge",
            },
        ) as socket:
            socket.send_json(
                {
                    "type": "hello",
                    "meeting": {
                        "source_language": "en",
                        "target_language": "ja",
                        "translate": True,
                        "summarize": True,
                        "chunk_seconds": 5,
                    },
                }
            )
            assert socket.receive_json()["type"] == "ready"
            socket.send_bytes(
                AudioFrame(
                    stream=STREAM_MIC,
                    sequence=0,
                    sample_clock=0,
                    payload=b"\x00\x00" * 320,
                ).encode()
            )
            socket.send_json({"type": "stop"})
            while True:
                event = socket.receive_json()
                if event["type"] == "meeting.complete":
                    break

    # 区切りごとに ASR を捨てて LLM を止め直していたので、翻訳つきの会議は
    # 毎回モデルの読み込みを待たされていた。同居できるかは Broker が握って
    # いて、無理なときは worker pool が要求時に相手を降ろす。載る機材では
    # 両方載せたままにする。
    assert "release-ai:True" not in events[: events.index("ai:translate")]
    assert "evict:asr" not in events[: events.index("ai:translate")]
    assert events.index("asr") < events.index("ai:translate")

    # 会議が終わったら話は別で、議事録を書く LLM に場所を空ける。
    evicted = events.index("evict:asr")
    assert events.index("ai:translate") < evicted
    assert evicted < events.index("ai:summary-chunk")
    assert "ensure-ai" in events[evicted : events.index("ai:summary-chunk")]
    assert events.index("ai:summary-chunk") < events.index("ai:summary-final")
