from __future__ import annotations

import asyncio
import time
from pathlib import Path

from sonicforge.live_runtime import LiveTurnRunner, LiveTurnTiming
from sonicforge.live_streaming_extensions import install_live_streaming_extensions
from sonicforge.pipeline_schema import LiveSessionCreate
from sonicforge.workers import WorkerError, WorkerResult


class FakeJobs:
    def _resolve_voice(self, request):
        return request

    async def _set(self, *_args, **_kwargs):
        return None


class FakeRuntime:
    @staticmethod
    def _number(_value, default, _low, _high):
        return default

    @staticmethod
    def _integer(_value, default, _low, _high):
        return default

    @staticmethod
    def _worker_request(_stage, value):
        return {
            "task": "speech.tts.synthesize",
            "input": {"text": value.text},
            "routing": {"engine": "fake"},
        }


class FakeHostSession:
    hold_id = "hold:test"

    async def identity(self):
        return object()


class FakeHostClient:
    def __init__(self):
        self.releases = 0

    async def gateway_capabilities(self, _identity):
        return {"control_plane": {"ai": {"stream": True}}}

    async def ai_stream(self, *_args, **_kwargs):
        yield {"type": "content", "content": "これは最初の十分に長い文です。"}
        await asyncio.sleep(0)
        yield {"type": "content", "content": "これは二番目の十分に長い文です。"}
        yield {"type": "done"}

    async def ai_release(self, _identity):
        self.releases += 1


class FakeWorkerPool:
    def __init__(self, tmp_path: Path):
        self.tmp_path = tmp_path
        self.calls = 0
        self.evictions = []
        self.fail_fast = []
        self.second_started = asyncio.Event()

    async def evict(self, key):
        self.evictions.append(key)

    async def execute(self, request, work_dir, progress, *, fail_fast=False):
        self.calls += 1
        self.fail_fast.append(fail_fast)
        index = self.calls - 1
        if index == 1:
            self.second_started.set()
        await progress(1.0, "done")
        path = self.tmp_path / f"chunk-{index}.wav"
        path.write_bytes(b"fake")
        return WorkerResult(
            engine_id="fake",
            engine_version="1",
            model_id="fake-tts",
            model_revision=None,
            model_license_id=None,
            output_path=path,
            payload={"text": request["input"]["text"]},
        )


def session_contract() -> LiveSessionCreate:
    return LiveSessionCreate.model_validate(
        {
            "preset": "voice-assistant",
            "pipeline": {
                "pipeline": "stream-overlap-test",
                "input": {"kind": "audio_stream", "stream_id": "mic"},
                "stages": [
                    {"id": "asr", "kind": "speech.asr"},
                    {"id": "llm", "kind": "host.ai.text"},
                    {"id": "tts", "kind": "speech.tts"},
                ],
                "delivery": {"mode": "websocket", "profile": "m5-pcm"},
            },
            "save_output_audio": False,
            "streaming_response": True,
            "keep_warm": True,
        }
    )


def test_live_turn_timing_reports_required_intervals():
    timing = LiveTurnTiming(10.0)
    timing.milestones = {
        "asr_final": 11.0,
        "first_llm_token": 11.25,
        "first_speakable_chunk": 11.5,
        "first_audio": 12.0,
        "response_complete": 13.0,
    }

    assert timing.report() == {
        "basis": "ptt.stop",
        "milestones_ms": {
            "asr_final": 1000.0,
            "first_llm_token": 1250.0,
            "first_speakable_chunk": 1500.0,
            "first_audio": 2000.0,
            "response_complete": 3000.0,
        },
        "end_of_speech_to_asr_final_ms": 1000.0,
        "asr_final_to_first_llm_token_ms": 250.0,
        "asr_final_to_first_speakable_chunk_ms": 500.0,
        "first_speakable_chunk_to_first_audio_ms": 500.0,
        "end_of_speech_to_first_audio_ms": 2000.0,
        "full_response_completion_ms": 3000.0,
    }


def test_next_tts_chunk_starts_while_previous_audio_is_still_delivering(tmp_path):
    async def scenario():
        install_live_streaming_extensions()
        runner = object.__new__(LiveTurnRunner)
        runner.jobs = FakeJobs()
        runner.runtime = FakeRuntime()
        runner.host_session = FakeHostSession()
        runner.host_client = FakeHostClient()
        runner.worker_pool = FakeWorkerPool(tmp_path)

        session = session_contract()
        ai_stage = session.pipeline.stages[1]
        tts_stage = session.pipeline.stages[2]
        events = []
        first_audio_entered = asyncio.Event()
        timing = LiveTurnTiming(time.monotonic())

        async def emit(event):
            events.append(event)

        async def emit_audio(_path, index):
            if index == 0:
                first_audio_entered.set()
                # Old sequential code deadlocks here because chunk 2 cannot be
                # synthesized until chunk 1 delivery returns. The overlapped
                # pipeline must start chunk 2 while this delivery is blocked.
                await asyncio.wait_for(runner.worker_pool.second_started.wait(), 0.5)

        result = await asyncio.wait_for(
            runner._stream_ai_to_tts(
                "job:test",
                session,
                ai_stage,
                tts_stage,
                "hello",
                None,
                tmp_path / "work",
                emit,
                emit_audio,
                timing,
            ),
            2.0,
        )
        assert first_audio_entered.is_set()
        assert runner.worker_pool.evictions == ["asr"]
        assert runner.worker_pool.second_started.is_set()
        assert runner.worker_pool.calls == 2
        assert runner.worker_pool.fail_fast == [True, True]
        assert set(timing.milestones) == {
            "first_llm_token",
            "first_speakable_chunk",
            "first_audio",
        }
        assert (
            timing.milestones["first_llm_token"]
            <= timing.milestones["first_speakable_chunk"]
            <= timing.milestones["first_audio"]
        )
        assert result[0].endswith("二番目の十分に長い文です。")
        assert result[1].payload["delivery_overlap"] is True
        assert result[1].payload["sequential_fallback"] is False
        deltas = [event["text"] for event in events if event["type"] == "turn.response_text.delta"]
        assert deltas == [
            "これは最初の十分に長い文です。",
            "これは二番目の十分に長い文です。",
        ]

    asyncio.run(scenario())


def test_rejected_overlap_drains_llm_then_runs_sequential_tts(tmp_path):
    class RejectFirstWorkerPool(FakeWorkerPool):
        def __init__(self, tmp_path):
            super().__init__(tmp_path)
            self.third_started = asyncio.Event()

        async def execute(self, request, work_dir, progress, *, fail_fast=False):
            if not self.calls:
                self.calls += 1
                self.fail_fast.append(fail_fast)
                raise WorkerError("Live GPU admission ended: rejected")
            result = await super().execute(
                request, work_dir, progress, fail_fast=fail_fast
            )
            if self.calls == 3:
                self.third_started.set()
            return result

    class NoHoldHostSession(FakeHostSession):
        hold_id = None

    async def scenario():
        install_live_streaming_extensions()
        runner = object.__new__(LiveTurnRunner)
        runner.jobs = FakeJobs()
        runner.runtime = FakeRuntime()
        runner.host_session = NoHoldHostSession()
        runner.host_client = FakeHostClient()
        runner.worker_pool = RejectFirstWorkerPool(tmp_path)
        events = []
        audio = []
        timing = LiveTurnTiming(time.monotonic())

        async def emit(event):
            events.append(event)

        async def emit_audio(path, index):
            audio.append((path, index))
            if index == 0:
                await asyncio.wait_for(runner.worker_pool.third_started.wait(), 0.5)

        session = session_contract()
        result = await runner._stream_ai_to_tts(
            "job:fallback",
            session,
            session.pipeline.stages[1],
            session.pipeline.stages[2],
            "hello",
            None,
            tmp_path / "fallback-work",
            emit,
            emit_audio,
            timing,
        )

        assert runner.worker_pool.evictions == ["asr"]
        assert runner.worker_pool.fail_fast == [True, False, False]
        assert runner.host_client.releases == 1
        assert runner.worker_pool.calls == 3
        assert len(audio) == 2
        assert set(timing.milestones) == {
            "first_llm_token",
            "first_speakable_chunk",
            "first_audio",
        }
        assert result[0].endswith("二番目の十分に長い文です。")
        assert result[1].payload["delivery_overlap"] is False
        assert result[1].payload["sequential_fallback"] is True
        deltas = [
            event["text"]
            for event in events
            if event["type"] == "turn.response_text.delta"
        ]
        assert deltas == [
            "これは最初の十分に長い文です。",
            "これは二番目の十分に長い文です。",
        ]

    asyncio.run(scenario())
