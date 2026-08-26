from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from .host.client import HostApiError
from .jobs import HostedExecution
from .live_chunking import SpeakableTextChunker
from .live_runtime import LiveTurnRunner
from .pipeline_runtime import PipelineValue
from .pipeline_schema import LiveSessionCreate, PipelineStage
from .workers import WorkerError, WorkerResult


AudioQueueItem = tuple[int, str, WorkerResult, dict[str, Any]]


def install_live_streaming_extensions() -> None:
    """Enable overlapped LLM -> TTS -> audio delivery for live voice turns.

    LLM token intake, TTS synthesis and client audio delivery run as three
    bounded stages. Only the delivery stage emits client-facing streaming
    events, so JSON and binary WebSocket frames never race from independent
    tasks while TTS generation still overlaps current-chunk playback.
    """

    if getattr(LiveTurnRunner, "_sonicforge_streaming_overlap_installed", False):
        return

    async def stream_ai_to_tts(
        self: LiveTurnRunner,
        job_id: str,
        session: LiveSessionCreate,
        ai_stage: PipelineStage,
        tts_stage: PipelineStage,
        input_text: str,
        hosted: HostedExecution | None,
        work_dir: Path,
        emit,
        emit_audio,
    ) -> tuple[str, WorkerResult, dict[str, Any], Path | None]:
        identity = await self.host_session.identity()
        if identity is None:
            raise WorkerError("ControlDeck Host AI is required for streaming voice")
        if hosted is not None:
            hosted.identity = identity

        gateway = await self.host_client.gateway_capabilities(identity)
        ai = (gateway.get("control_plane") or {}).get("ai") or {}
        await self.worker_pool.evict("asr")
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
        text_queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=4)
        audio_queue: asyncio.Queue[AudioQueueItem | None] = asyncio.Queue(maxsize=2)
        generated: list[tuple[str, WorkerResult, dict[str, Any]]] = []
        text_parts: list[str] = []
        fallback_chunks: list[str] = []
        sequential_fallback = False

        async def produce_text() -> None:
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
                for chunk in chunker.feed(fragment):
                    await text_queue.put(chunk)
            for chunk in chunker.flush():
                await text_queue.put(chunk)
            await text_queue.put(None)

        async def synthesize() -> None:
            nonlocal sequential_fallback
            index = 0
            while True:
                chunk = await text_queue.get()
                if chunk is None:
                    await audio_queue.put(None)
                    return
                if sequential_fallback:
                    fallback_chunks.append(chunk)
                    continue
                request = self.runtime._worker_request(
                    tts_stage, PipelineValue(kind="text", text=chunk)
                )
                request = self.jobs._resolve_voice(request)
                chunk_index = index

                async def progress(fraction: float, message: str) -> None:
                    await self.jobs._set(
                        job_id,
                        progress=min(
                            0.94,
                            0.62 + 0.3 * max(0.0, min(1.0, fraction)),
                        ),
                        result={
                            "message": (
                                f"Streaming TTS chunk {chunk_index}: {message}"
                            )
                        },
                    )

                try:
                    worker = await self.worker_pool.execute(
                        request,
                        work_dir / f"tts-chunk-{chunk_index:03d}",
                        progress,
                        fail_fast=True,
                    )
                except WorkerError as exc:
                    if "admission ended: rejected" not in str(exc).lower():
                        raise
                    sequential_fallback = True
                    fallback_chunks.append(chunk)
                    continue
                if worker.output_path is None:
                    raise WorkerError("streaming TTS worker returned no audio")
                generated.append((chunk, worker, request))
                # Bounded handoff: at most two synthesized chunks may wait for
                # delivery, preventing unbounded RAM/temporary-audio growth.
                await audio_queue.put((chunk_index, chunk, worker, request))
                index += 1

        async def deliver_audio(
            queue: asyncio.Queue[AudioQueueItem | None],
        ) -> None:
            while True:
                item = await queue.get()
                if item is None:
                    return
                index, chunk, worker, _request = item
                assert worker.output_path is not None
                # This task is the single owner of incremental client output.
                # It preserves JSON/binary ordering while synthesis continues in
                # the background for the following chunk.
                await emit(
                    {
                        "type": "turn.response_text.delta",
                        "job_id": job_id,
                        "text": chunk,
                    }
                )
                await emit(
                    {
                        "type": "turn.speech.chunk.started",
                        "job_id": job_id,
                        "chunk": index,
                        "text": chunk,
                    }
                )
                await emit_audio(worker.output_path, index)
                await emit(
                    {
                        "type": "turn.speech.chunk.completed",
                        "job_id": job_id,
                        "chunk": index,
                        "text": chunk,
                    }
                )

        # Producer, synthesis and delivery overlap. TaskGroup cancellation keeps
        # a downstream failure from leaving an upstream task blocked on a full
        # bounded queue.
        async with asyncio.TaskGroup() as group:
            group.create_task(
                produce_text(), name=f"sonicforge-stream-llm-{job_id}"
            )
            group.create_task(
                synthesize(), name=f"sonicforge-stream-tts-{job_id}"
            )
            group.create_task(
                deliver_audio(audio_queue), name=f"sonicforge-stream-audio-{job_id}"
            )

        response_text = "".join(text_parts).strip()
        if not response_text:
            raise WorkerError("streaming LLM produced no text")

        if sequential_fallback:
            if self.host_session.hold_id is not None:
                await self.host_session.release_llm_hold(stop_runtime=True)
            else:
                current = await self.host_session.identity()
                if current is not None:
                    try:
                        await self.host_client.ai_release(current)
                    except HostApiError as exc:
                        if exc.status_code not in {404, 409, 503}:
                            raise
            if not fallback_chunks:
                fallback_chunks.append(response_text)
            fallback_audio: asyncio.Queue[AudioQueueItem | None] = asyncio.Queue(
                maxsize=2
            )

            async def synthesize_fallback() -> None:
                for index, chunk in enumerate(fallback_chunks):
                    request = self.runtime._worker_request(
                        tts_stage, PipelineValue(kind="text", text=chunk)
                    )
                    request = self.jobs._resolve_voice(request)

                    async def fallback_progress(
                        fraction: float, message: str, *, chunk_index: int = index
                    ) -> None:
                        await self.jobs._set(
                            job_id,
                            progress=min(
                                0.94,
                                0.65
                                + 0.25 * max(0.0, min(1.0, fraction)),
                            ),
                            result={
                                "message": (
                                    f"Sequential TTS fallback chunk {chunk_index}: "
                                    f"{message}"
                                )
                            },
                        )

                    worker = await self.worker_pool.execute(
                        request,
                        work_dir / f"tts-sequential-{index:03d}",
                        fallback_progress,
                    )
                    if worker.output_path is None:
                        raise WorkerError(
                            "sequential TTS fallback returned no audio"
                        )
                    generated.append((chunk, worker, request))
                    await fallback_audio.put((index, chunk, worker, request))
                await fallback_audio.put(None)

            async with asyncio.TaskGroup() as group:
                group.create_task(
                    synthesize_fallback(),
                    name=f"sonicforge-sequential-tts-{job_id}",
                )
                group.create_task(
                    deliver_audio(fallback_audio),
                    name=f"sonicforge-sequential-audio-{job_id}",
                )
        elif not generated:
            raise WorkerError("streaming LLM produced no speakable TTS chunks")

        await emit(
            {
                "type": "turn.response_text",
                "job_id": job_id,
                "text": response_text,
            }
        )

        if not sequential_fallback and self.host_session.hold_id is None:
            current = await self.host_session.identity()
            if current is not None:
                try:
                    await self.host_client.ai_release(current)
                except HostApiError as exc:
                    if exc.status_code not in {404, 409, 503}:
                        raise

        merged: Path | None = None
        if session.save_output_audio:
            from .live_runtime import _concat_wavs

            merged = work_dir / "streamed-response.wav"
            _concat_wavs(
                [item[1].output_path for item in generated if item[1].output_path],
                merged,
            )

        last_chunk, last_worker, last_request = generated[-1]
        last_worker = WorkerResult(
            engine_id=last_worker.engine_id,
            engine_version=last_worker.engine_version,
            model_id=last_worker.model_id,
            model_revision=last_worker.model_revision,
            model_license_id=last_worker.model_license_id,
            output_path=merged or last_worker.output_path,
            payload={
                **last_worker.payload,
                "streamed_chunks": len(generated),
                "last_chunk": last_chunk,
                "delivery_overlap": not sequential_fallback,
                "sequential_fallback": sequential_fallback,
            },
        )
        return response_text, last_worker, last_request, merged

    LiveTurnRunner._stream_ai_to_tts = stream_ai_to_tts
    LiveTurnRunner._sonicforge_streaming_overlap_installed = True
