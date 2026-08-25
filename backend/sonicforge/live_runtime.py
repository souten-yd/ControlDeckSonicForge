from __future__ import annotations

import asyncio
import shutil
import uuid
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

from .db import Job
from .host.client import HostApiError
from .jobs import HostedExecution, JobManager
from .live_chunking import SpeakableTextChunker
from .live_host_session import LiveHostSession
from .live_workers import LiveWorkerPool
from .pipeline_runtime import PipelineRuntime, PipelineValue
from .pipeline_schema import LiveSessionCreate, PipelineStage, compile_pipeline
from .spool import AudioSpoolManager
from .workers import WorkerError, WorkerResult

LiveEvent = Callable[[dict[str, Any]], Awaitable[None]]
LiveAudio = Callable[[Path, int], Awaitable[None]]


@dataclass
class LiveTurnResult:
    job_id: str
    audio_path: Path | None
    transcript: str | None
    response_text: str | None
    asset_id: str | None
    trace: list[dict[str, Any]]
    work_dir: Path
    streamed_audio: bool = False

    def cleanup(self) -> None:
        if self.audio_path is not None and self.asset_id is None:
            try:
                self.audio_path.unlink()
            except FileNotFoundError:
                pass
        shutil.rmtree(self.work_dir, ignore_errors=True)


def _concat_wavs(paths: list[Path], target: Path) -> None:
    if not paths:
        raise WorkerError("no TTS chunks were generated")
    params = None
    frames: list[bytes] = []
    for path in paths:
        with wave.open(str(path), "rb") as stream:
            current = (
                stream.getnchannels(),
                stream.getsampwidth(),
                stream.getframerate(),
                stream.getcomptype(),
            )
            if params is None:
                params = current
            elif current != params:
                raise WorkerError("streaming TTS chunks have incompatible WAV formats")
            frames.append(stream.readframes(stream.getnframes()))
    assert params is not None
    target.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(target), "wb") as stream:
        stream.setnchannels(params[0])
        stream.setsampwidth(params[1])
        stream.setframerate(params[2])
        stream.setcomptype(
            params[3], "not compressed" if params[3] == "NONE" else params[3]
        )
        for raw in frames:
            stream.writeframes(raw)


class LiveTurnRunner:
    """Execute durable live turns while reusing session-scoped warm workers."""

    def __init__(
        self,
        *,
        jobs: JobManager,
        session_factory,
        host_client,
        host_session: LiveHostSession,
        worker_pool: LiveWorkerPool,
    ) -> None:
        self.jobs = jobs
        self.session_factory = session_factory
        self.host_client = host_client
        self.host_session = host_session
        self.worker_pool = worker_pool
        self.spool = AudioSpoolManager(jobs.settings)
        self.runtime = PipelineRuntime(
            jobs=jobs,
            session_factory=session_factory,
            host_client=host_client,
        )

    async def run(
        self,
        session: LiveSessionCreate,
        audio_path: Path,
        *,
        hosted: HostedExecution | None,
        emit: LiveEvent,
        emit_audio: LiveAudio | None = None,
    ) -> LiveTurnResult:
        compile_pipeline(session.pipeline)
        if session.pipeline.input.kind != "audio_stream":
            raise WorkerError("PTT turn requires audio_stream input")
        row = Job(
            id=f"job:{uuid.uuid4()}",
            task="live.turn",
            state="queued",
            progress=0.0,
            request={
                "preset": session.preset,
                "pipeline": session.pipeline.model_dump(mode="json"),
                "save_input_audio": session.save_input_audio,
                "save_output_audio": session.save_output_audio,
                "streaming_response": session.streaming_response,
                "keep_warm": session.keep_warm,
            },
        )
        with self.session_factory() as db:
            db.add(row)
            db.commit()
            db.refresh(row)
        if hosted is not None:
            self.jobs.hosted[row.id] = hosted
        task = asyncio.create_task(
            self._execute(row.id, session, audio_path, hosted, emit, emit_audio),
            name=f"sonicforge-live-turn-{row.id}",
        )
        self.jobs.tasks[row.id] = task
        return await task

    async def _persistent_worker_stage(
        self,
        job_id: str,
        stage: PipelineStage,
        value: PipelineValue,
        work_dir: Path,
        *,
        progress_base: float,
        progress_span: float,
    ) -> tuple[PipelineValue, dict[str, Any], WorkerResult, dict[str, Any]]:
        request = self.runtime._worker_request(stage, value)
        if stage.kind == "speech.tts":
            request = self.jobs._resolve_voice(request)

        async def progress(fraction: float, message: str) -> None:
            await self.jobs._set(
                job_id,
                progress=min(
                    0.94,
                    progress_base
                    + progress_span * max(0.0, min(1.0, fraction)),
                ),
                result={"message": f"Live {stage.id}: {message}"},
            )

        result = await self.worker_pool.execute(request, work_dir, progress)
        trace: dict[str, Any] = {
            "id": stage.id,
            "kind": stage.kind,
            "state": "succeeded",
            "persistent_worker": True,
        }
        if stage.kind == "speech.asr":
            text = result.payload.get("text")
            if not isinstance(text, str):
                raise WorkerError("ASR live worker returned no text")
            trace["output"] = "text"
            return PipelineValue(kind="text", text=text), trace, result, request
        if result.output_path is None:
            raise WorkerError("TTS live worker returned no audio")
        trace["output"] = "audio"
        return PipelineValue(kind="audio", audio_path=result.output_path), trace, result, request

    def _messages(
        self, session: LiveSessionCreate, stage: PipelineStage, text: str
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        system_prompt = stage.parameters.get("system_prompt")
        if session.preset == "simultaneous-translation":
            target = "Japanese" if session.target_language == "ja" else "English"
            system_prompt = (
                f"Translate the user's speech into natural {target}. "
                "Output only the translation suitable for immediate speech. "
                "Preserve names, numbers and technical terms faithfully; do not add commentary."
            )
        if system_prompt is not None:
            value = str(system_prompt).strip()
            if len(value) > 8000:
                raise WorkerError("live system_prompt is too large")
            if value:
                messages.append({"role": "system", "content": value})
        messages.append({"role": "user", "content": text})
        return messages

    async def _host_ai_complete(
        self,
        session: LiveSessionCreate,
        stage: PipelineStage,
        text: str,
        hosted: HostedExecution | None,
    ) -> str:
        identity = await self.host_session.identity()
        if identity is None:
            raise WorkerError("ControlDeck Host AI is required for this live pipeline")
        if hosted is not None:
            hosted.identity = identity
        await self.host_session.ensure_llm_hold()
        identity = await self.host_session.identity()
        if identity is None:
            raise WorkerError("ControlDeck Host AI identity expired")
        if hosted is not None:
            hosted.identity = identity
        result = await self.host_client.ai_complete(
            identity,
            self._messages(session, stage, text),
            temperature=self.runtime._number(
                stage.parameters.get("temperature"), 0.2, 0.0, 2.0
            ),
            max_tokens=self.runtime._integer(
                stage.parameters.get("max_tokens"), 1024, 1, 8192
            ),
            timeout_seconds=self.runtime._integer(
                stage.parameters.get("timeout_seconds"), 120, 1, 300
            ),
        )
        content = result.get("content")
        if not isinstance(content, str) or not content.strip():
            raise WorkerError("ControlDeck AI returned empty live text")
        if self.host_session.hold_id is None:
            try:
                await self.host_client.ai_release(identity)
            except HostApiError as exc:
                if exc.status_code not in {404, 409, 503}:
                    raise
        return content.strip()

    async def _stream_ai_to_tts(
        self,
        job_id: str,
        session: LiveSessionCreate,
        ai_stage: PipelineStage,
        tts_stage: PipelineStage,
        input_text: str,
        hosted: HostedExecution | None,
        work_dir: Path,
        emit: LiveEvent,
        emit_audio: LiveAudio,
    ) -> tuple[str, WorkerResult, dict[str, Any], Path | None]:
        identity = await self.host_session.identity()
        if identity is None:
            raise WorkerError("ControlDeck Host AI is required for streaming voice")
        if hosted is not None:
            hosted.identity = identity
        gateway = await self.host_client.gateway_capabilities(identity)
        ai = (gateway.get("control_plane") or {}).get("ai") or {}
        if ai.get("stream") is not True:
            text = await self._host_ai_complete(session, ai_stage, input_text, hosted)
            await emit(
                {"type": "turn.response_text", "job_id": job_id, "text": text}
            )
            request = self.runtime._worker_request(
                tts_stage, PipelineValue(kind="text", text=text)
            )
            request = self.jobs._resolve_voice(request)

            async def progress(fraction: float, message: str) -> None:
                await self.jobs._set(
                    job_id,
                    progress=min(
                        0.94, 0.65 + 0.25 * max(0.0, min(1.0, fraction))
                    ),
                    result={"message": f"Live {tts_stage.id}: {message}"},
                )

            worker = await self.worker_pool.execute(
                request, work_dir / "tts-chunk-000", progress
            )
            if worker.output_path is None:
                raise WorkerError("TTS live worker returned no audio")
            await emit_audio(worker.output_path, 0)
            return text, worker, request, worker.output_path

        chunker = SpeakableTextChunker()
        queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=4)
        generated: list[tuple[str, WorkerResult, dict[str, Any]]] = []

        async def synthesize() -> None:
            index = 0
            while True:
                chunk = await queue.get()
                if chunk is None:
                    return
                await emit(
                    {
                        "type": "turn.speech.chunk.started",
                        "job_id": job_id,
                        "chunk": index,
                        "text": chunk,
                    }
                )
                request = self.runtime._worker_request(
                    tts_stage, PipelineValue(kind="text", text=chunk)
                )
                request = self.jobs._resolve_voice(request)

                async def progress(fraction: float, message: str) -> None:
                    await self.jobs._set(
                        job_id,
                        progress=min(
                            0.94,
                            0.62 + 0.3 * max(0.0, min(1.0, fraction)),
                        ),
                        result={
                            "message": f"Streaming TTS chunk {index}: {message}"
                        },
                    )

                worker = await self.worker_pool.execute(
                    request, work_dir / f"tts-chunk-{index:03d}", progress
                )
                if worker.output_path is None:
                    raise WorkerError("streaming TTS worker returned no audio")
                generated.append((chunk, worker, request))
                await emit_audio(worker.output_path, index)
                await emit(
                    {
                        "type": "turn.speech.chunk.completed",
                        "job_id": job_id,
                        "chunk": index,
                        "text": chunk,
                    }
                )
                index += 1

        tts_task = asyncio.create_task(
            synthesize(), name=f"sonicforge-stream-tts-{job_id}"
        )
        text_parts: list[str] = []
        stream_error: BaseException | None = None
        try:
            async for event in self.host_client.ai_stream(
                identity,
                self._messages(session, ai_stage, input_text),
                temperature=self.runtime._number(
                    ai_stage.parameters.get("temperature"), 0.2, 0.0, 2.0
                ),
                max_tokens=self.runtime._integer(
                    ai_stage.parameters.get("max_tokens"), 1024, 1, 8192
                ),
                timeout_seconds=self.runtime._integer(
                    ai_stage.parameters.get("timeout_seconds"), 120, 1, 300
                ),
            ):
                if event.get("type") != "content":
                    continue
                fragment = event.get("content")
                if not isinstance(fragment, str) or not fragment:
                    continue
                text_parts.append(fragment)
                await emit(
                    {
                        "type": "turn.response_text.delta",
                        "job_id": job_id,
                        "text": fragment,
                    }
                )
                for chunk in chunker.feed(fragment):
                    await queue.put(chunk)
            for chunk in chunker.flush():
                await queue.put(chunk)
        except BaseException as exc:
            stream_error = exc
        finally:
            await queue.put(None)
        try:
            await tts_task
        except BaseException as exc:
            if stream_error is None:
                stream_error = exc
        if stream_error is not None:
            raise stream_error
        if not generated:
            raise WorkerError("streaming LLM produced no speakable TTS chunks")
        response_text = "".join(text_parts).strip()
        await emit(
            {
                "type": "turn.response_text",
                "job_id": job_id,
                "text": response_text,
            }
        )
        if self.host_session.hold_id is None:
            current = await self.host_session.identity()
            if current is not None:
                try:
                    await self.host_client.ai_release(current)
                except HostApiError as exc:
                    if exc.status_code not in {404, 409, 503}:
                        raise

        merged: Path | None = None
        if session.save_output_audio:
            merged = work_dir / "streamed-response.wav"
            _concat_wavs(
                [item[1].output_path for item in generated if item[1].output_path],
                merged,
            )
        last_chunk, last_worker, last_request = generated[-1]
        if merged is not None:
            last_worker = WorkerResult(
                engine_id=last_worker.engine_id,
                engine_version=last_worker.engine_version,
                model_id=last_worker.model_id,
                model_revision=last_worker.model_revision,
                model_license_id=last_worker.model_license_id,
                output_path=merged,
                payload={
                    **last_worker.payload,
                    "streamed_chunks": len(generated),
                    "last_chunk": last_chunk,
                },
            )
        return response_text, last_worker, last_request, merged

    async def _execute(
        self,
        job_id: str,
        session: LiveSessionCreate,
        audio_path: Path,
        hosted: HostedExecution | None,
        emit: LiveEvent,
        emit_audio: LiveAudio | None,
    ) -> LiveTurnResult:
        compiled = compile_pipeline(session.pipeline)
        active = session.pipeline.stages[
            compiled.start_index : compiled.stop_index + 1
        ]
        work_dir = self.spool.work_dir(
            "live-work", f"live_{job_id.replace(':', '_')}"
        )
        value = PipelineValue(kind="audio", audio_path=audio_path)
        trace: list[dict[str, Any]] = []
        transcript: str | None = None
        response_text: str | None = None
        final_worker: WorkerResult | None = None
        final_request: dict[str, Any] | None = None
        streamed_audio = False
        control_watch: asyncio.Task | None = None
        await self.jobs._set(job_id, state="running", progress=0.01)
        if hosted is not None:
            control_watch = asyncio.create_task(
                self.jobs._watch_host_cancel(job_id, hosted),
                name=f"sonicforge-live-control-{job_id}",
            )
        try:
            kinds = [stage.kind for stage in active]
            if (
                session.streaming_response
                and session.preset != "simultaneous-translation"
                and emit_audio is not None
                and kinds == ["speech.asr", "host.ai.text", "speech.tts"]
            ):
                asr_stage, ai_stage, tts_stage = active
                await emit(
                    {
                        "type": "stage.started",
                        "job_id": job_id,
                        "stage_id": asr_stage.id,
                        "kind": asr_stage.kind,
                    }
                )
                value, item, _asr_worker, _asr_request = (
                    await self._persistent_worker_stage(
                        job_id,
                        asr_stage,
                        value,
                        work_dir / f"stage-00-{asr_stage.id}",
                        progress_base=0.05,
                        progress_span=0.35,
                    )
                )
                trace.append(item)
                transcript = value.text
                await emit(
                    {
                        "type": "turn.transcript",
                        "job_id": job_id,
                        "text": transcript or "",
                    }
                )
                await emit(
                    {
                        "type": "stage.completed",
                        "job_id": job_id,
                        "stage_id": asr_stage.id,
                        "kind": asr_stage.kind,
                    }
                )

                await emit(
                    {
                        "type": "stage.started",
                        "job_id": job_id,
                        "stage_id": ai_stage.id,
                        "kind": ai_stage.kind,
                    }
                )
                await emit(
                    {
                        "type": "stage.started",
                        "job_id": job_id,
                        "stage_id": tts_stage.id,
                        "kind": tts_stage.kind,
                    }
                )
                response_text, final_worker, final_request, merged = (
                    await self._stream_ai_to_tts(
                        job_id,
                        session,
                        ai_stage,
                        tts_stage,
                        transcript or "",
                        hosted,
                        work_dir,
                        emit,
                        emit_audio,
                    )
                )
                trace.extend(
                    [
                        {
                            "id": ai_stage.id,
                            "kind": ai_stage.kind,
                            "state": "succeeded",
                            "output": "text",
                            "streaming": True,
                        },
                        {
                            "id": tts_stage.id,
                            "kind": tts_stage.kind,
                            "state": "succeeded",
                            "output": "audio",
                            "persistent_worker": True,
                            "streaming": True,
                        },
                    ]
                )
                await emit(
                    {
                        "type": "stage.completed",
                        "job_id": job_id,
                        "stage_id": ai_stage.id,
                        "kind": ai_stage.kind,
                    }
                )
                await emit(
                    {
                        "type": "stage.completed",
                        "job_id": job_id,
                        "stage_id": tts_stage.id,
                        "kind": tts_stage.kind,
                    }
                )
                value = (
                    PipelineValue(kind="audio", audio_path=merged)
                    if merged
                    else PipelineValue(kind="text", text=response_text)
                )
                streamed_audio = True
            else:
                total = len(active)
                for index, stage in enumerate(active):
                    await emit(
                        {
                            "type": "stage.started",
                            "job_id": job_id,
                            "stage_id": stage.id,
                            "kind": stage.kind,
                        }
                    )
                    start = 0.05 + index / max(total, 1) * 0.85
                    span = 0.85 / max(total, 1)
                    if stage.kind in {"speech.asr", "speech.tts"}:
                        if (
                            stage.kind == "speech.tts"
                            and session.preset == "simultaneous-translation"
                            and self.host_session.hold_id is not None
                        ):
                            await self.host_session.release_llm_hold(stop_runtime=True)
                        value, item, worker, worker_request = (
                            await self._persistent_worker_stage(
                                job_id,
                                stage,
                                value,
                                work_dir / f"stage-{index:02d}-{stage.id}",
                                progress_base=start,
                                progress_span=span,
                            )
                        )
                        final_worker = worker
                        final_request = worker_request
                        if stage.kind == "speech.asr":
                            transcript = value.text
                            if transcript:
                                await emit(
                                    {
                                        "type": "turn.transcript",
                                        "job_id": job_id,
                                        "text": transcript,
                                    }
                                )
                    elif stage.kind == "host.ai.text":
                        if value.kind != "text" or value.text is None:
                            raise WorkerError("Host AI stage requires text input")
                        if session.preset == "simultaneous-translation":
                            await self.worker_pool.evict("asr")
                        response_text = await self._host_ai_complete(
                            session, stage, value.text, hosted
                        )
                        value = PipelineValue(kind="text", text=response_text)
                        item = {
                            "id": stage.id,
                            "kind": stage.kind,
                            "state": "succeeded",
                            "output": "text",
                            "provider": "control-deck-ai",
                        }
                        await emit(
                            {
                                "type": "turn.response_text",
                                "job_id": job_id,
                                "text": response_text,
                            }
                        )
                    else:
                        value, item, worker, worker_request = (
                            await self.runtime._worker_stage(
                                job_id,
                                stage,
                                value,
                                hosted,
                                work_dir / f"stage-{index:02d}-{stage.id}",
                                index,
                                total,
                            )
                        )
                        final_worker = worker
                        final_request = worker_request
                    trace.append(item)
                    await emit(
                        {
                            "type": "stage.completed",
                            "job_id": job_id,
                            "stage_id": stage.id,
                            "kind": stage.kind,
                        }
                    )

            asset_id: str | None = None
            output_path: Path | None = (
                value.audio_path if value.kind == "audio" else None
            )
            if (
                session.save_output_audio
                and output_path is not None
                and final_worker is not None
            ):
                provenance_request = final_request or {
                    "task": "live.turn",
                    "profile": session.pipeline.delivery.profile,
                    "quality": "balanced",
                    "content_language": "auto",
                    "seed": None,
                }
                asset_id, output_path, _meta = self.jobs._persist_audio_result(
                    job_id,
                    provenance_request,
                    final_worker,
                    metadata_extra={
                        "live_session": {
                            "preset": session.preset,
                            "stages": trace,
                        },
                        "transcript": transcript,
                        "response_text": response_text,
                    },
                )

            result = {
                "message": "Live turn complete",
                "transcript": transcript,
                "response_text": response_text,
                "asset_id": asset_id,
                "pipeline": {"stages": trace},
                "streamed_audio": streamed_audio,
            }
            await self.jobs._set(
                job_id, state="succeeded", progress=1.0, result=result
            )
            return LiveTurnResult(
                job_id=job_id,
                audio_path=output_path,
                transcript=transcript,
                response_text=response_text,
                asset_id=asset_id,
                trace=trace,
                work_dir=work_dir,
                streamed_audio=streamed_audio,
            )
        except asyncio.CancelledError:
            await self.jobs._set(
                job_id,
                state="canceled",
                progress=1.0,
                error_code="canceled",
                error_message="Live turn canceled",
            )
            shutil.rmtree(work_dir, ignore_errors=True)
            raise
        except Exception as exc:
            await self.jobs._set(
                job_id,
                state="failed",
                progress=1.0,
                error_code="live_turn_failed",
                error_message=str(exc)[:1000],
            )
            shutil.rmtree(work_dir, ignore_errors=True)
            raise
        finally:
            if control_watch is not None:
                control_watch.cancel()
                await asyncio.gather(control_watch, return_exceptions=True)
            self.jobs.tasks.pop(job_id, None)
            self.jobs.hosted.pop(job_id, None)
