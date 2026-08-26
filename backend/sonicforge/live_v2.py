from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
import wave
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .db import Job
from .edge_protocol import AudioFrame, EdgeProtocolError, SequenceTracker, STREAM_MIC, STREAM_SPEAKER
from .host.ai_stream import stream_text
from .host.client import HostApiError, HostIdentity
from .live_api import _select_format, _wav_mono_pcm
from .live_session_resources import LiveSessionResources
from .pipeline_schema import AudioFormat, EdgeDeviceDescriptor, PipelineStage
from .streaming_text import speech_chunks
from .workers import WorkerError


MAX_HELLO_BYTES = 64 * 1024
MIN_SEGMENT_MS = 120


class LiveV2Hello(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preset: Literal["voice-chat", "translate", "dictation", "meeting"] = "voice-chat"
    source_language: Literal["auto", "ja", "en"] = "auto"
    target_language: Literal["ja", "en"] | None = None
    response_language: Literal["auto", "ja", "en"] = "auto"
    tts_enabled: bool = True
    voice_id: str | None = Field(default=None, max_length=128)
    system_prompt: str | None = Field(default=None, max_length=8000)
    glossary: dict[str, str] = Field(default_factory=dict, max_length=256)
    device: EdgeDeviceDescriptor | None = None
    meeting_auto_segment_seconds: float | None = Field(default=12.0, ge=2.0, le=600.0)
    save_transcript: bool = True

    @model_validator(mode="after")
    def coherent(self):
        if self.preset == "translate" and self.target_language is None:
            raise ValueError("translate preset requires target_language")
        if any(len(str(key)) > 120 or len(str(value)) > 500 for key, value in self.glossary.items()):
            raise ValueError("glossary entry is too large")
        if self.preset == "meeting":
            self.tts_enabled = False
        return self


class WavSpool:
    def __init__(self, path: Path, fmt: AudioFormat) -> None:
        if fmt.codec != "pcm_s16le" or fmt.channels != 1:
            raise EdgeProtocolError("sonic-live/2 currently requires mono pcm_s16le input")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.fmt = fmt
        self.samples = 0
        self._stream = wave.open(str(path), "wb")
        self._stream.setnchannels(1)
        self._stream.setsampwidth(2)
        self._stream.setframerate(fmt.rate)
        self.closed = False

    def write(self, payload: bytes) -> None:
        if self.closed:
            raise EdgeProtocolError("audio spool is already closed")
        if len(payload) % 2:
            raise EdgeProtocolError("PCM frame payload must be 16-bit aligned")
        self._stream.writeframesraw(payload)
        self.samples += len(payload) // 2

    @property
    def duration_ms(self) -> int:
        return self.samples * 1000 // max(1, self.fmt.rate)

    def close(self) -> Path:
        if not self.closed:
            self._stream.close()
            self.closed = True
        return self.path

    def discard(self) -> None:
        self.close()
        self.path.unlink(missing_ok=True)


def _formats(hello: LiveV2Hello) -> tuple[AudioFormat, AudioFormat]:
    if hello.device is None:
        return (
            AudioFormat(codec="pcm_s16le", rate=16000, channels=1, frame_ms=20),
            AudioFormat(codec="pcm_s16le", rate=24000, channels=1, frame_ms=20),
        )
    return (
        _select_format(hello.device.audio.input, output=False),
        _select_format(hello.device.audio.output, output=True),
    )


def _stages(hello: LiveV2Hello) -> list[PipelineStage]:
    values = [PipelineStage(id="asr", kind="speech.asr", language=hello.source_language)]
    if hello.preset in {"voice-chat", "translate"} or (
        hello.preset == "meeting" and hello.target_language is not None
    ):
        values.append(PipelineStage(id="llm", kind="host.ai.text"))
    if hello.tts_enabled and hello.preset in {"voice-chat", "translate"}:
        values.append(
            PipelineStage(
                id="tts",
                kind="speech.tts",
                language=hello.target_language or hello.response_language,
                voice_id=hello.voice_id,
            )
        )
    return values


def _translation_system(hello: LiveV2Hello) -> str:
    target = "Japanese" if hello.target_language == "ja" else "English"
    glossary = "\n".join(f"{key} => {value}" for key, value in hello.glossary.items())
    return (
        f"Translate the user's speech faithfully into {target}. Output only the translation. "
        "Preserve names, numbers, units, code, and technical terms. Do not add commentary."
        + (f"\nUse this glossary when applicable:\n{glossary}" if glossary else "")
    )


def _voice_system(hello: LiveV2Hello) -> str:
    if hello.system_prompt and hello.system_prompt.strip():
        return hello.system_prompt.strip()
    language = {
        "ja": "Reply naturally in Japanese.",
        "en": "Reply naturally in English.",
    }.get(hello.response_language, "Reply naturally in the user's language.")
    return f"You are a concise voice assistant. {language} Keep spoken answers clear and reasonably brief."


async def _send_pcm_chunk(
    websocket: WebSocket,
    send_lock: asyncio.Lock,
    path: Path,
    fmt: AudioFormat,
    *,
    chunk_index: int,
    sequence: int,
    sample_clock: int,
) -> tuple[int, int]:
    pcm = _wav_mono_pcm(path, fmt.rate)
    samples_per_frame = max(1, round(fmt.rate * fmt.frame_ms / 1000))
    bytes_per_frame = samples_per_frame * 2
    async with send_lock:
        await websocket.send_json(
            {
                "type": "tts.chunk.ready",
                "chunk": chunk_index,
                "format": fmt.model_dump(mode="json"),
                "bytes": len(pcm),
            }
        )
        for offset in range(0, len(pcm), bytes_per_frame):
            payload = pcm[offset : offset + bytes_per_frame]
            if not payload:
                continue
            await websocket.send_bytes(
                AudioFrame(
                    stream=STREAM_SPEAKER,
                    sequence=sequence,
                    sample_clock=sample_clock,
                    payload=payload,
                ).encode()
            )
            sequence = (sequence + 1) & 0xFFFFFFFF
            sample_clock = (sample_clock + len(payload) // 2) & 0xFFFFFFFF
        await websocket.send_json({"type": "tts.chunk.end", "chunk": chunk_index})
    return sequence, sample_clock


def create_live_v2_router(base) -> APIRouter:
    router = APIRouter(prefix="/addon/v2/live", tags=["live-v2"])

    async def authenticate(websocket: WebSocket) -> HostIdentity | None:
        has_host = bool(
            websocket.headers.get("authorization")
            or websocket.headers.get("x-control-deck-addon-id")
        )
        if not has_host:
            # Trusted-local mode: basic ASR/TTS/live speech does not require a
            # ControlDeck login. Host-only LLM/project operations are still
            # unavailable until a Host identity is present.
            return None
        return await base.host_client.authenticate(websocket.headers)

    def new_job(preset: str, kind: str) -> str:
        job_id = f"job:{uuid.uuid4()}"
        with base.session_factory() as db:
            db.add(
                Job(
                    id=job_id,
                    task=kind,
                    state="queued",
                    progress=0.0,
                    request={"preset": preset, "protocol": "sonic-live/2"},
                )
            )
            db.commit()
        return job_id

    async def set_job(job_id: str, **values) -> None:
        await base.jobs._set(job_id, **values)

    @router.websocket("/ws")
    async def live_v2(websocket: WebSocket):
        resources: LiveSessionResources | None = None
        meeting_task: asyncio.Task | None = None
        meeting_queue: asyncio.Queue | None = None
        spool: WavSpool | None = None
        status = "succeeded"
        send_lock = asyncio.Lock()
        meeting_id: str | None = None
        meeting_dir: Path | None = None
        meeting_started = time.monotonic()
        transcript_items: list[dict[str, Any]] = []
        try:
            identity = await authenticate(websocket)
            await websocket.accept()
            first = await websocket.receive_text()
            if len(first.encode("utf-8")) > MAX_HELLO_BYTES:
                raise EdgeProtocolError("live hello is too large")
            raw = json.loads(first)
            if not isinstance(raw, dict) or raw.get("type") != "hello":
                raise EdgeProtocolError("first live message must be hello")
            hello = LiveV2Hello.model_validate(raw.get("session") or {})
            input_format, output_format = _formats(hello)
            stages = _stages(hello)
            if any(stage.kind == "host.ai.text" for stage in stages) and identity is None:
                raise EdgeProtocolError(
                    "This preset uses the ControlDeck LLM router; connect through ControlDeck or use dictation/basic ASR-TTS"
                )

            resources = LiveSessionResources(
                jobs=base.jobs,
                host_client=base.host_client,
                identity=identity,
                stages=stages,
                label=hello.preset,
            )
            await resources.start()

            if hello.preset == "meeting":
                meeting_id = f"meeting:{uuid.uuid4()}"
                meeting_dir = base.settings.data_dir / "meetings" / meeting_id.removeprefix("meeting:")
                meeting_dir.mkdir(parents=True, exist_ok=True)
                (meeting_dir / "session.json").write_text(
                    json.dumps(
                        {
                            "meeting_id": meeting_id,
                            "source_language": hello.source_language,
                            "target_language": hello.target_language,
                            "started_at": time.time(),
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                meeting_queue = asyncio.Queue(maxsize=8)

            await websocket.send_json(
                {
                    "type": "ready",
                    "protocol": "sonic-live/2",
                    "preset": hello.preset,
                    "input_format": input_format.model_dump(mode="json"),
                    "output_format": output_format.model_dump(mode="json"),
                    "meeting_id": meeting_id,
                    "worker_stats": resources.worker_stats(),
                    "ai_residency_held": bool(resources.ai_hold and resources.ai_hold.held),
                }
            )

            async def send_json(value: dict[str, Any]) -> None:
                async with send_lock:
                    await websocket.send_json(value)

            async def run_asr(path: Path, job_id: str) -> tuple[str, dict]:
                assert resources is not None
                request = {
                    "task": "speech.asr.transcribe",
                    "input": {"_internal_staged_input": str(path)},
                    "profile": "live",
                    "quality": "fast",
                    "content_language": hello.source_language,
                    "output": {"format": "wav", "sample_rate": None, "channels": None},
                    "routing": {"engine": None, "model": None, "device": "auto"},
                    "seed": None,
                    "project_output_grant": None,
                }

                async def progress(fraction: float, message: str) -> None:
                    await set_job(job_id, state="running", progress=min(0.45, max(0.02, fraction * 0.45)), result={"message": message})

                result = await resources.execute_asr(
                    request,
                    base.settings.data_dir / "tmp" / f"live2-{job_id.replace(':', '-')}-asr",
                    progress,
                )
                text = str(result.payload.get("text") or "").strip()
                if not text:
                    raise WorkerError("ASR returned empty text")
                return text, result.payload

            async def llm_stream_text(source_text: str) -> tuple[str, list[str]]:
                assert resources is not None and resources.identity is not None
                if hello.preset in {"translate", "meeting"} and hello.target_language:
                    system = _translation_system(hello)
                    event_prefix = "translation"
                    speech_language = hello.target_language
                else:
                    system = _voice_system(hello)
                    event_prefix = "llm"
                    speech_language = hello.response_language if hello.response_language != "auto" else hello.source_language
                messages = [
                    {"role": "system", "content": system},
                    {"role": "user", "content": source_text},
                ]
                events = stream_text(
                    base.host_client,
                    resources.identity,
                    messages,
                    temperature=0.2 if event_prefix == "llm" else 0.0,
                    max_tokens=1024,
                    timeout_seconds=120,
                )
                chunks: list[str] = []
                full = ""
                async for chunk in speech_chunks(events, language=speech_language):
                    chunks.append(chunk)
                    full += chunk
                    await send_json({"type": f"{event_prefix}.chunk", "text": chunk, "index": len(chunks) - 1})
                await send_json({"type": f"{event_prefix}.final", "text": full})
                return full, chunks

            async def synthesize_chunks(chunks: list[str]) -> None:
                assert resources is not None
                sequence = 0
                sample_clock = 0
                for index, chunk in enumerate(chunks):
                    request = {
                        "task": "speech.tts.synthesize",
                        "input": {"text": chunk, "voice_id": hello.voice_id},
                        "profile": "live",
                        "quality": "fast",
                        "content_language": hello.target_language or hello.response_language,
                        "output": {"format": "wav", "sample_rate": None, "channels": None},
                        "routing": {"engine": None, "model": None, "device": "auto"},
                        "seed": None,
                        "project_output_grant": None,
                    }

                    async def progress(_fraction: float, _message: str) -> None:
                        return None

                    result = await resources.execute_tts(
                        request,
                        base.settings.data_dir / "tmp" / f"live2-tts-{uuid.uuid4().hex}",
                        progress,
                    )
                    if result.output_path is None:
                        raise WorkerError("TTS returned no audio")
                    sequence, sample_clock = await _send_pcm_chunk(
                        websocket,
                        send_lock,
                        result.output_path,
                        output_format,
                        chunk_index=index,
                        sequence=sequence,
                        sample_clock=sample_clock,
                    )
                    try:
                        result.output_path.unlink()
                        result.output_path.parent.rmdir()
                    except OSError:
                        pass

            async def process_segment(path: Path, start_ms: int, end_ms: int, *, meeting: bool) -> dict[str, Any]:
                job_id = new_job(hello.preset, "meeting.segment" if meeting else "live.turn.v2")
                started = time.monotonic()
                try:
                    await set_job(job_id, state="running", progress=0.01)
                    transcript, asr_payload = await run_asr(path, job_id)
                    asr_done = time.monotonic()
                    await send_json(
                        {
                            "type": "asr.final",
                            "job_id": job_id,
                            "text": transcript,
                            "start_ms": start_ms,
                            "end_ms": end_ms,
                        }
                    )
                    response_text: str | None = None
                    chunks: list[str] = []
                    if hello.preset in {"voice-chat", "translate"} or (
                        meeting and hello.target_language is not None
                    ):
                        response_text, chunks = await llm_stream_text(transcript)
                    llm_done = time.monotonic()
                    if hello.tts_enabled and chunks:
                        await synthesize_chunks(chunks)
                    completed = time.monotonic()
                    item = {
                        "job_id": job_id,
                        "start_ms": start_ms,
                        "end_ms": end_ms,
                        "text": transcript,
                        "translation" if hello.preset in {"translate", "meeting"} and hello.target_language else "response": response_text,
                        "segments": asr_payload.get("segments") or [],
                    }
                    await set_job(
                        job_id,
                        state="succeeded",
                        progress=1.0,
                        result={
                            "message": "Live segment complete",
                            "text": transcript,
                            "response_text": response_text,
                            "metrics": {
                                "asr_seconds": round(asr_done - started, 4),
                                "llm_seconds": round(llm_done - asr_done, 4),
                                "total_seconds": round(completed - started, 4),
                            },
                            "worker_stats": resources.worker_stats(),
                        },
                    )
                    await send_json(
                        {
                            "type": "segment.complete" if meeting else "turn.complete",
                            **item,
                            "worker_stats": resources.worker_stats(),
                            "metrics": {
                                "asr_seconds": round(asr_done - started, 4),
                                "llm_seconds": round(llm_done - asr_done, 4),
                                "total_seconds": round(completed - started, 4),
                            },
                        }
                    )
                    return item
                except Exception as exc:
                    await set_job(
                        job_id,
                        state="failed",
                        progress=1.0,
                        error_code="live_v2_failed",
                        error_message=str(exc)[:1000],
                    )
                    await send_json({"type": "turn.error", "job_id": job_id, "message": str(exc)[:500]})
                    raise
                finally:
                    path.unlink(missing_ok=True)

            async def meeting_processor() -> None:
                assert meeting_queue is not None and meeting_dir is not None
                transcript_path = meeting_dir / "transcript.jsonl"
                while True:
                    item = await meeting_queue.get()
                    try:
                        if item is None:
                            return
                        path, start_ms, end_ms = item
                        result = await process_segment(path, start_ms, end_ms, meeting=True)
                        transcript_items.append(result)
                        line = json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n"
                        with transcript_path.open("a", encoding="utf-8") as output:
                            output.write(line)
                            output.flush()
                            os.fsync(output.fileno())
                    finally:
                        meeting_queue.task_done()

            if meeting_queue is not None:
                meeting_task = asyncio.create_task(meeting_processor(), name=f"sonicforge-{meeting_id}")

            tracker = SequenceTracker()
            recording = False
            segment_start_ms = 0

            def start_spool() -> WavSpool:
                return WavSpool(
                    base.settings.data_dir / "tmp" / "live2-input" / f"{uuid.uuid4().hex}.wav",
                    input_format,
                )

            async def commit_current(*, continue_recording: bool) -> None:
                nonlocal spool, segment_start_ms
                if spool is None:
                    return
                duration = spool.duration_ms
                path = spool.close()
                spool = None
                if duration < MIN_SEGMENT_MS:
                    path.unlink(missing_ok=True)
                else:
                    end_ms = segment_start_ms + duration
                    if hello.preset == "meeting":
                        assert meeting_queue is not None
                        await meeting_queue.put((path, segment_start_ms, end_ms))
                    else:
                        await process_segment(path, segment_start_ms, end_ms, meeting=False)
                    segment_start_ms = end_ms
                if continue_recording:
                    spool = start_spool()

            async def finish_meeting() -> None:
                nonlocal recording
                if hello.preset != "meeting" or meeting_queue is None or meeting_dir is None:
                    return
                if spool is not None:
                    await commit_current(continue_recording=False)
                recording = False
                await meeting_queue.join()
                summary: dict[str, Any] | None = None
                if resources is not None and resources.identity is not None and transcript_items:
                    transcript = "\n".join(
                        f"[{item['start_ms']/1000:.1f}-{item['end_ms']/1000:.1f}] {item['text']}"
                        + (f" / {item.get('translation')}" if item.get("translation") else "")
                        for item in transcript_items
                    )
                    messages = [
                        {
                            "role": "system",
                            "content": "Create concise meeting minutes as JSON with keys summary, decisions, action_items, open_questions. Do not invent facts.",
                        },
                        {"role": "user", "content": transcript},
                    ]
                    value = await base.host_client.ai_complete(
                        resources.identity,
                        messages,
                        temperature=0.0,
                        max_tokens=2048,
                        timeout_seconds=180,
                        response_format={"type": "json_object"},
                    )
                    raw_summary = value.get("content")
                    try:
                        summary = json.loads(raw_summary) if isinstance(raw_summary, str) else None
                    except json.JSONDecodeError:
                        summary = {"summary": raw_summary}
                    if summary is not None:
                        (meeting_dir / "minutes.json").write_text(
                            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
                        )
                await send_json(
                    {
                        "type": "meeting.finished",
                        "meeting_id": meeting_id,
                        "segments": len(transcript_items),
                        "minutes": summary,
                    }
                )

            while True:
                message = await websocket.receive()
                if message.get("type") == "websocket.disconnect":
                    return
                text = message.get("text")
                binary = message.get("bytes")
                if text is not None:
                    control = json.loads(text)
                    if not isinstance(control, dict):
                        raise EdgeProtocolError("control message must be an object")
                    kind = control.get("type")
                    if kind == "ping":
                        await send_json({"type": "pong", "worker_stats": resources.worker_stats()})
                        continue
                    if kind in {"ptt.start", "input.start", "meeting.start"}:
                        if recording:
                            raise EdgeProtocolError("input is already recording")
                        tracker = SequenceTracker()
                        spool = start_spool()
                        recording = True
                        segment_start_ms = int((time.monotonic() - meeting_started) * 1000) if hello.preset == "meeting" else 0
                        await send_json({"type": "input.started"})
                        continue
                    if kind in {"ptt.stop", "input.commit", "segment.commit"}:
                        if not recording or spool is None:
                            raise EdgeProtocolError("input is not recording")
                        await commit_current(continue_recording=hello.preset == "meeting")
                        if hello.preset != "meeting":
                            recording = False
                        continue
                    if kind == "meeting.finish":
                        await finish_meeting()
                        continue
                    if kind == "close":
                        if hello.preset == "meeting":
                            await finish_meeting()
                        await websocket.close(code=1000)
                        return
                    raise EdgeProtocolError(f"unsupported live v2 control message: {kind}")

                if binary is not None:
                    if not recording or spool is None:
                        raise EdgeProtocolError("audio frame received outside recording")
                    frame = AudioFrame.decode(binary)
                    if frame.stream != STREAM_MIC:
                        raise EdgeProtocolError("client may only send microphone frames")
                    observation = tracker.observe(frame)
                    if observation.duplicate_or_old:
                        await send_json({"type": "audio.warning", "code": "duplicate_or_old", "sequence": frame.sequence})
                        continue
                    if observation.gap:
                        await send_json({"type": "audio.warning", "code": "sequence_gap", "missing_frames": observation.gap, "sequence": frame.sequence})
                    spool.write(frame.payload)
                    if (
                        hello.preset == "meeting"
                        and hello.meeting_auto_segment_seconds is not None
                        and spool.duration_ms >= int(hello.meeting_auto_segment_seconds * 1000)
                    ):
                        await commit_current(continue_recording=True)
        except WebSocketDisconnect:
            status = "canceled"
        except (EdgeProtocolError, ValueError, json.JSONDecodeError, HostApiError, WorkerError) as exc:
            status = "failed"
            try:
                await websocket.send_json({"type": "error", "code": "live_v2_error", "message": str(exc)[:500]})
                await websocket.close(code=4400)
            except RuntimeError:
                pass
        finally:
            if spool is not None:
                spool.discard()
            if meeting_queue is not None and meeting_task is not None:
                try:
                    await meeting_queue.put(None)
                    await asyncio.wait_for(meeting_task, timeout=5)
                except (TimeoutError, asyncio.CancelledError):
                    meeting_task.cancel()
                    await asyncio.gather(meeting_task, return_exceptions=True)
            if resources is not None:
                await resources.close(status=status)

    return router
