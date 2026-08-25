from __future__ import annotations

import asyncio
import json
import shutil
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .access import websocket_peer_is_trusted
from .db import MeetingSegment, MeetingSession, utcnow
from .edge_protocol import AudioFrame, EdgeProtocolError, SequenceTracker, STREAM_MIC
from .host.client import HostApiError, HostIdentity
from .live_api import _pcm_file_to_wav
from .live_host_session import LiveHostSession
from .live_workers import LiveWorkerPool
from .pipeline_schema import AudioFormat
from .spool import AdaptiveSpoolFile, AudioSpoolManager
from .workers import WorkerError

MAX_CONTROL_BYTES = 64 * 1024


class MeetingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(default="Meeting", min_length=1, max_length=200)
    source_language: Literal["auto", "ja", "en"] = "auto"
    target_language: Literal["ja", "en"] | None = None
    translate: bool = False
    summarize: bool = False
    chunk_seconds: int = Field(default=20, ge=5, le=60)
    audio: AudioFormat = Field(
        default_factory=lambda: AudioFormat(
            codec="pcm_s16le", rate=16000, channels=1, frame_ms=20
        )
    )

    @model_validator(mode="after")
    def validate_meeting(self):
        if self.audio.codec != "pcm_s16le" or self.audio.channels != 1:
            raise ValueError("meeting v1 requires mono pcm_s16le")
        if self.translate and self.target_language is None:
            raise ValueError("meeting translation requires target_language")
        return self


def _meeting_dict(row: MeetingSession) -> dict:
    return {
        "id": row.id,
        "title": row.title,
        "state": row.state,
        "source_language": row.source_language,
        "target_language": row.target_language,
        "translate": row.translate,
        "summarize": row.summarize,
        "profile": row.profile or {},
        "summary": row.summary or {},
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "ended_at": row.ended_at.isoformat() if row.ended_at else None,
        "segments": [
            {
                "id": item.id,
                "sequence": item.sequence,
                "start_ms": item.start_ms,
                "end_ms": item.end_ms,
                "source_language": item.source_language,
                "source_text": item.source_text,
                "target_language": item.target_language,
                "translated_text": item.translated_text,
                "state": item.state,
                "asr_metadata": item.asr_metadata or {},
                "translation_metadata": item.translation_metadata or {},
            }
            for item in row.segments
        ],
    }


async def _host_identity(base, websocket: WebSocket) -> HostIdentity | None:
    has_host = bool(
        websocket.headers.get("authorization")
        or websocket.headers.get("x-control-deck-addon-id")
    )
    if not has_host:
        if not websocket_peer_is_trusted(websocket, bind_host=base.settings.host):
            raise HostApiError(
                "trusted_local_peer_required",
                "Unauthenticated meeting capture is limited to trusted local-network peers",
                status_code=403,
            )
        return None
    return await base.host_client.authenticate(websocket.headers)


def create_meeting_router(base) -> APIRouter:
    router = APIRouter(prefix="/addon/v1/meetings", tags=["meetings"])
    spool_manager = AudioSpoolManager(base.settings)

    @router.get("")
    async def list_meetings():
        with base.session_factory() as db:
            rows = (
                db.query(MeetingSession)
                .order_by(MeetingSession.created_at.desc())
                .limit(100)
                .all()
            )
            return {"meetings": [_meeting_dict(row) for row in rows]}

    @router.get("/{meeting_id}")
    async def get_meeting(meeting_id: str):
        with base.session_factory() as db:
            row = db.get(MeetingSession, meeting_id)
            if row is None:
                raise HTTPException(status_code=404, detail="meeting not found")
            return _meeting_dict(row)

    @router.get("/{meeting_id}/transcript.txt", response_class=PlainTextResponse)
    async def meeting_transcript(meeting_id: str):
        with base.session_factory() as db:
            row = db.get(MeetingSession, meeting_id)
            if row is None:
                raise HTTPException(status_code=404, detail="meeting not found")
            lines = []
            for item in row.segments:
                if not item.source_text:
                    continue
                start = item.start_ms / 1000
                end = item.end_ms / 1000
                lines.append(f"[{start:0.1f}-{end:0.1f}] {item.source_text.strip()}")
                if item.translated_text:
                    lines.append(f"  -> {item.translated_text.strip()}")
            return "\n".join(lines) + ("\n" if lines else "")

    @router.websocket("/ws")
    async def meeting_ws(websocket: WebSocket):
        try:
            identity = await _host_identity(base, websocket)
        except HostApiError as exc:
            await websocket.close(code=4403 if exc.status_code == 403 else 4401)
            return
        await websocket.accept()
        host_session: LiveHostSession | None = None
        worker_pool: LiveWorkerPool | None = None
        processor: asyncio.Task | None = None
        queue: asyncio.Queue[tuple[int, Path, int, int] | None] = asyncio.Queue()
        send_lock = asyncio.Lock()
        meeting_id: str | None = None
        current_spool: AdaptiveSpoolFile | None = None
        failed = False
        transport_open = True

        async def send_json(value: dict) -> None:
            nonlocal transport_open
            if not transport_open:
                return
            try:
                async with send_lock:
                    await websocket.send_json(value)
            except (RuntimeError, WebSocketDisconnect):
                transport_open = False

        try:
            first = await websocket.receive_text()
            if len(first.encode("utf-8")) > MAX_CONTROL_BYTES:
                raise EdgeProtocolError("meeting hello is too large")
            hello = json.loads(first)
            if not isinstance(hello, dict) or hello.get("type") != "hello":
                raise EdgeProtocolError("first meeting message must be hello")
            config = MeetingConfig.model_validate(hello.get("meeting") or {})
            if (config.translate or config.summarize) and identity is None:
                raise EdgeProtocolError(
                    "ControlDeck Host AI is required for translation/summarization; local unauthenticated meeting ASR remains available"
                )

            meeting_id = f"meeting:{uuid.uuid4()}"
            with base.session_factory() as db:
                row = MeetingSession(
                    id=meeting_id,
                    title=config.title,
                    state="recording",
                    source_language=config.source_language,
                    target_language=config.target_language,
                    translate=config.translate,
                    summarize=config.summarize,
                    profile={
                        "chunk_seconds": config.chunk_seconds,
                        "audio": config.audio.model_dump(mode="json"),
                        "spool_policy": "ram-first-disk-fallback",
                    },
                )
                db.add(row)
                db.commit()

            host_session = LiveHostSession(
                host_client=base.host_client,
                jobs=base.jobs,
                identity=identity,
                title=f"SonicForge meeting: {config.title}",
            )
            await host_session.start(
                keep_llm_warm=bool(config.translate or config.summarize)
            )
            worker_pool = LiveWorkerPool(
                settings=base.settings,
                host_session=host_session,
            )

            async def translate_text(text: str) -> tuple[str | None, dict]:
                if not config.translate or not text.strip():
                    return None, {}
                current = await host_session.identity()
                if current is None:
                    return None, {"state": "unavailable"}
                target = "Japanese" if config.target_language == "ja" else "English"
                result = await base.host_client.ai_complete(
                    current,
                    [
                        {
                            "role": "system",
                            "content": (
                                f"Translate the transcript into {target}. Output only the translation. "
                                "Preserve names, numbers and technical terms faithfully."
                            ),
                        },
                        {"role": "user", "content": text},
                    ],
                    temperature=0.0,
                    max_tokens=1024,
                    timeout_seconds=120,
                )
                value = result.get("content")
                if not isinstance(value, str) or not value.strip():
                    return None, {"state": "empty"}
                return value.strip(), {
                    "state": "succeeded",
                    "provider": "control-deck-ai",
                }

            async def process_chunks() -> None:
                assert worker_pool is not None
                while True:
                    item = await queue.get()
                    if item is None:
                        queue.task_done()
                        return
                    sequence, raw_path, start_ms, end_ms = item
                    wav_path = raw_path.with_suffix(".wav")
                    work_dir = spool_manager.work_dir(
                        "meeting-work",
                        f"{meeting_id.replace(':', '_')}-segment-{sequence:06d}",
                    )
                    try:
                        _pcm_file_to_wav(raw_path, wav_path, config.audio)
                        request = {
                            "task": "speech.asr.transcribe",
                            "profile": "meeting",
                            "quality": "balanced",
                            "content_language": config.source_language,
                            "output": {
                                "format": "json",
                                "sample_rate": None,
                                "channels": None,
                            },
                            "routing": {
                                "engine": None,
                                "model": None,
                                "device": None,
                            },
                            "seed": None,
                            "project_output_grant": None,
                            "input": {"_internal_staged_input": str(wav_path)},
                        }

                        async def progress(fraction: float, message: str) -> None:
                            await send_json(
                                {
                                    "type": "meeting.segment.progress",
                                    "meeting_id": meeting_id,
                                    "sequence": sequence,
                                    "progress": max(0.0, min(1.0, fraction)),
                                    "message": message,
                                }
                            )

                        result = await worker_pool.execute(request, work_dir, progress)
                        source_text = result.payload.get("text")
                        if not isinstance(source_text, str):
                            raise WorkerError("meeting ASR returned no text")
                        translated_text, translation_meta = await translate_text(source_text)
                        with base.session_factory() as db:
                            db.add(
                                MeetingSegment(
                                    meeting_id=meeting_id,
                                    sequence=sequence,
                                    start_ms=start_ms,
                                    end_ms=end_ms,
                                    source_language=config.source_language,
                                    source_text=source_text,
                                    target_language=config.target_language,
                                    translated_text=translated_text,
                                    state="final",
                                    asr_metadata={
                                        "engine_id": result.engine_id,
                                        "model_id": result.model_id,
                                        "segments": result.payload.get("segments") or [],
                                    },
                                    translation_metadata=translation_meta,
                                )
                            )
                            db.commit()
                        await send_json(
                            {
                                "type": "meeting.segment.final",
                                "meeting_id": meeting_id,
                                "sequence": sequence,
                                "start_ms": start_ms,
                                "end_ms": end_ms,
                                "source_text": source_text,
                                "translated_text": translated_text,
                            }
                        )
                    except Exception as exc:
                        with base.session_factory() as db:
                            db.add(
                                MeetingSegment(
                                    meeting_id=meeting_id,
                                    sequence=sequence,
                                    start_ms=start_ms,
                                    end_ms=end_ms,
                                    source_language=config.source_language,
                                    source_text="",
                                    target_language=config.target_language,
                                    translated_text=None,
                                    state="failed",
                                    asr_metadata={"error": str(exc)[:1000]},
                                    translation_metadata={},
                                )
                            )
                            db.commit()
                        await send_json(
                            {
                                "type": "meeting.segment.error",
                                "meeting_id": meeting_id,
                                "sequence": sequence,
                                "message": str(exc)[:500],
                            }
                        )
                    finally:
                        raw_path.unlink(missing_ok=True)
                        wav_path.unlink(missing_ok=True)
                        shutil.rmtree(work_dir, ignore_errors=True)
                        queue.task_done()

            processor = asyncio.create_task(
                process_chunks(),
                name=f"sonicforge-meeting-processor-{meeting_id}",
            )
            await send_json(
                {
                    "type": "ready",
                    "protocol": "sonic-meeting/1",
                    "meeting_id": meeting_id,
                    "chunk_seconds": config.chunk_seconds,
                    "audio": config.audio.model_dump(mode="json"),
                    "duration_limit_seconds": None,
                    "spool": {
                        "policy": "ram-first-disk-fallback",
                        "ram_available": spool_manager.ram_available,
                    },
                }
            )

            tracker = SequenceTracker()
            sequence = 0
            total_bytes = 0
            chunk_bytes = 0
            bytes_per_second = config.audio.rate * config.audio.channels * 2
            chunk_target = bytes_per_second * config.chunk_seconds

            def open_chunk() -> AdaptiveSpoolFile:
                return spool_manager.open("meeting-input", suffix=".pcm")

            current_spool = open_chunk()

            async def flush_chunk(*, notify: bool = True) -> None:
                nonlocal sequence, current_spool, chunk_bytes
                if current_spool is None or chunk_bytes <= 0:
                    return
                path = current_spool.finalize()
                start_bytes = total_bytes - chunk_bytes
                start_ms = start_bytes * 1000 // bytes_per_second
                end_ms = total_bytes * 1000 // bytes_per_second
                await queue.put((sequence, path, start_ms, end_ms))
                if notify:
                    await send_json(
                        {
                            "type": "meeting.segment.queued",
                            "meeting_id": meeting_id,
                            "sequence": sequence,
                            "start_ms": start_ms,
                            "end_ms": end_ms,
                            "backlog": queue.qsize(),
                            "memory_backed": path.is_relative_to(spool_manager.memory_root)
                            if spool_manager.memory_root is not None
                            else False,
                        }
                    )
                sequence += 1
                chunk_bytes = 0
                current_spool = open_chunk()

            disconnected = False
            while True:
                message = await websocket.receive()
                if message.get("type") == "websocket.disconnect":
                    disconnected = True
                    transport_open = False
                    await flush_chunk(notify=False)
                    break
                if message.get("text") is not None:
                    text = message["text"]
                    if len(text.encode("utf-8")) > MAX_CONTROL_BYTES:
                        raise EdgeProtocolError("meeting control message is too large")
                    control = json.loads(text)
                    kind = control.get("type") if isinstance(control, dict) else None
                    if kind == "ping":
                        await send_json({"type": "pong"})
                        continue
                    if kind == "stop":
                        await flush_chunk()
                        break
                    raise EdgeProtocolError(f"unsupported meeting control message: {kind}")
                binary = message.get("bytes")
                if binary is None:
                    continue
                frame = AudioFrame.decode(binary)
                if frame.stream != STREAM_MIC:
                    raise EdgeProtocolError("meeting client may only send microphone frames")
                observation = tracker.observe(frame)
                if observation.duplicate_or_old:
                    continue
                if observation.gap:
                    await send_json(
                        {
                            "type": "audio.warning",
                            "code": "sequence_gap",
                            "missing_frames": observation.gap,
                            "sequence": frame.sequence,
                        }
                    )
                if len(frame.payload) % 2:
                    raise EdgeProtocolError("PCM payload must be 16-bit aligned")
                assert current_spool is not None
                current_spool.write(frame.payload)
                total_bytes += len(frame.payload)
                chunk_bytes += len(frame.payload)
                if chunk_bytes >= chunk_target:
                    await flush_chunk()

            if current_spool is not None:
                if chunk_bytes <= 0:
                    current_spool.cleanup()
                else:
                    await flush_chunk(notify=not disconnected)
                current_spool = None
            with base.session_factory() as db:
                row = db.get(MeetingSession, meeting_id)
                if row is not None:
                    row.state = "processing"
                    db.commit()
            await queue.join()
            await queue.put(None)
            if processor is not None:
                await processor
                processor = None

            summary: dict = {}
            if config.summarize:
                current = await host_session.identity()
                if current is not None:
                    with base.session_factory() as db:
                        row = db.get(MeetingSession, meeting_id)
                        transcript = (
                            "\n".join(
                                segment.source_text
                                for segment in row.segments
                                if segment.state == "final" and segment.source_text
                            )
                            if row is not None
                            else ""
                        )
                    pieces = [
                        transcript[i : i + 8000]
                        for i in range(0, len(transcript), 8000)
                    ] or [""]
                    partials = []
                    for piece in pieces:
                        if not piece.strip():
                            continue
                        current = await host_session.identity()
                        if current is None:
                            break
                        result = await base.host_client.ai_complete(
                            current,
                            [
                                {
                                    "role": "system",
                                    "content": "Summarize this meeting transcript chunk. Extract facts, decisions, unresolved questions and action items. Be concise.",
                                },
                                {"role": "user", "content": piece},
                            ],
                            temperature=0.1,
                            max_tokens=1200,
                            timeout_seconds=180,
                        )
                        if isinstance(result.get("content"), str):
                            partials.append(result["content"])
                    combined = "\n\n".join(partials)
                    if combined:
                        current = await host_session.identity()
                        if current is not None:
                            final = await base.host_client.ai_complete(
                                current,
                                [
                                    {
                                        "role": "system",
                                        "content": "Create final meeting minutes from the partial summaries. Return concise Markdown with Summary, Decisions, Action Items, Open Questions.",
                                    },
                                    {"role": "user", "content": combined[:24000]},
                                ],
                                temperature=0.1,
                                max_tokens=1600,
                                timeout_seconds=180,
                            )
                            if isinstance(final.get("content"), str):
                                summary = {
                                    "state": "succeeded",
                                    "markdown": final["content"].strip(),
                                    "provider": "control-deck-ai",
                                }

            with base.session_factory() as db:
                row = db.get(MeetingSession, meeting_id)
                if row is not None:
                    row.state = "completed" if not disconnected else "interrupted"
                    row.ended_at = utcnow()
                    row.summary = summary
                    db.commit()
            if not disconnected:
                await send_json(
                    {
                        "type": "meeting.complete",
                        "meeting_id": meeting_id,
                        "summary": summary,
                    }
                )
                try:
                    await websocket.close(code=1000)
                except RuntimeError:
                    pass
                transport_open = False
        except WebSocketDisconnect:
            failed = False
            transport_open = False
        except Exception as exc:
            failed = True
            if meeting_id is not None:
                with base.session_factory() as db:
                    row = db.get(MeetingSession, meeting_id)
                    if row is not None:
                        row.state = "interrupted"
                        row.ended_at = utcnow()
                        db.commit()
            await send_json(
                {
                    "type": "error",
                    "code": "meeting_failed",
                    "message": str(exc)[:500],
                }
            )
        finally:
            if current_spool is not None:
                current_spool.cleanup()
            if processor is not None:
                processor.cancel()
                await asyncio.gather(processor, return_exceptions=True)
            if worker_pool is not None:
                await worker_pool.close()
            if host_session is not None:
                await host_session.close(failed=failed)

    return router
