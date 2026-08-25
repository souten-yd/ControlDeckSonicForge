from __future__ import annotations

import asyncio
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

from .db import Job
from .jobs import HostedExecution, JobManager
from .pipeline_runtime import PipelineRuntime, PipelineValue
from .pipeline_schema import LiveSessionCreate, compile_pipeline
from .workers import WorkerError, WorkerResult

LiveEvent = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass
class LiveTurnResult:
    job_id: str
    audio_path: Path | None
    transcript: str | None
    response_text: str | None
    asset_id: str | None
    trace: list[dict[str, Any]]
    work_dir: Path

    def cleanup(self) -> None:
        if self.audio_path is not None and self.asset_id is None:
            try:
                self.audio_path.unlink()
            except FileNotFoundError:
                pass
        shutil.rmtree(self.work_dir, ignore_errors=True)


class LiveTurnRunner:
    """Execute one half-duplex voice turn through the typed pipeline core.

    The WebSocket session is ephemeral, but each turn is represented by a durable
    Job row so progress, cancellation and Host Resource Broker admission keep the
    same semantics as normal SonicForge work. Local worker resources are acquired
    per stage; Host AI performs its own admission between those stages.
    """

    def __init__(self, *, jobs: JobManager, session_factory, host_client) -> None:
        self.jobs = jobs
        self.session_factory = session_factory
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
    ) -> LiveTurnResult:
        compiled = compile_pipeline(session.pipeline)
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
            },
        )
        with self.session_factory() as db:
            db.add(row)
            db.commit()
            db.refresh(row)
        if hosted is not None:
            self.jobs.hosted[row.id] = hosted
        task = asyncio.create_task(
            self._execute(row.id, session, audio_path, hosted, emit),
            name=f"sonicforge-live-turn-{row.id}",
        )
        self.jobs.tasks[row.id] = task
        return await task

    async def _execute(
        self,
        job_id: str,
        session: LiveSessionCreate,
        audio_path: Path,
        hosted: HostedExecution | None,
        emit: LiveEvent,
    ) -> LiveTurnResult:
        compiled = compile_pipeline(session.pipeline)
        active = session.pipeline.stages[compiled.start_index : compiled.stop_index + 1]
        work_dir = self.jobs.settings.data_dir / "tmp" / f"live_{job_id.replace(':', '_')}"
        work_dir.mkdir(parents=True, exist_ok=True)
        value = PipelineValue(kind="audio", audio_path=audio_path)
        trace: list[dict[str, Any]] = []
        transcript: str | None = None
        response_text: str | None = None
        final_worker: WorkerResult | None = None
        final_request: dict[str, Any] | None = None
        control_watch: asyncio.Task | None = None
        await self.jobs._set(job_id, state="running", progress=0.01)
        if hosted is not None:
            control_watch = asyncio.create_task(
                self.jobs._watch_host_cancel(job_id, hosted),
                name=f"sonicforge-live-control-{job_id}",
            )
        try:
            total = len(active)
            for index, stage in enumerate(active):
                await emit({"type": "stage.started", "job_id": job_id, "stage_id": stage.id, "kind": stage.kind})
                if stage.kind == "host.ai.text":
                    value, item = await self.runtime._host_ai_stage(
                        job_id,
                        stage,
                        value,
                        hosted,
                        0.05 + index / max(total, 1) * 0.85,
                    )
                    response_text = value.text
                    if response_text:
                        await emit({"type": "turn.response_text", "job_id": job_id, "text": response_text})
                else:
                    value, item, worker, worker_request = await self.runtime._worker_stage(
                        job_id,
                        stage,
                        value,
                        hosted,
                        work_dir / f"stage-{index:02d}-{stage.id}",
                        index,
                        total,
                    )
                    final_worker = worker
                    final_request = worker_request
                    if stage.kind == "speech.asr":
                        transcript = value.text
                        if transcript:
                            await emit({"type": "turn.transcript", "job_id": job_id, "text": transcript})
                trace.append(item)
                await emit({"type": "stage.completed", "job_id": job_id, "stage_id": stage.id, "kind": stage.kind})

            asset_id: str | None = None
            output_path: Path | None = value.audio_path if value.kind == "audio" else None
            if session.save_output_audio and output_path is not None and final_worker is not None:
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
                        "live_session": {"preset": session.preset, "stages": trace},
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
            }
            await self.jobs._set(job_id, state="succeeded", progress=1.0, result=result)
            return LiveTurnResult(
                job_id=job_id,
                audio_path=output_path,
                transcript=transcript,
                response_text=response_text,
                asset_id=asset_id,
                trace=trace,
                work_dir=work_dir,
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
