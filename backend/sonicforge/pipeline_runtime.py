from __future__ import annotations

import asyncio
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .audio_process import process_audio
from .db import Asset, Job, Provenance
from .host.client import ControlDeckHostClient, HostApiError
from .host.files import commit_file, read_grant
from .jobs import HostedExecution, JobManager
from .pipeline_package import create_package, package_filename
from .pipeline_schema import PipelineRequest, PipelineStage, compile_pipeline
from .workers import WorkerError, WorkerResult, execute


@dataclass
class PipelineValue:
    kind: Literal["text", "audio"]
    text: str | None = None
    audio_path: Path | None = None


class PipelineRuntime:
    """Durable server-owned typed media pipeline execution.

    The runtime deliberately reuses JobManager's Host Job reporting, worker
    supervision, asset persistence and Resource Broker helpers. Resource leases
    are acquired per local stage rather than around the whole pipeline so Host
    AI inference can perform its own ControlDeck admission without deadlock.
    """

    def __init__(
        self,
        *,
        jobs: JobManager,
        session_factory,
        host_client: ControlDeckHostClient,
    ) -> None:
        self.jobs = jobs
        self.settings = jobs.settings
        self.session_factory = session_factory
        self.host_client = host_client

    def create(
        self,
        request: PipelineRequest,
        *,
        hosted: HostedExecution | None = None,
    ) -> Job:
        compiled = compile_pipeline(request)
        row = Job(
            id=f"job:{uuid.uuid4()}",
            task="pipeline.execute",
            state="queued",
            progress=0.0,
            request={
                "pipeline": request.model_dump(mode="json"),
                "compiled": {
                    "start_index": compiled.start_index,
                    "stop_index": compiled.stop_index,
                    "input_type": compiled.input_type,
                    "output_type": compiled.output_type,
                    "stage_ids": list(compiled.stage_ids),
                },
            },
        )
        with self.session_factory() as session:
            session.add(row)
            session.commit()
            session.refresh(row)
        if hosted is not None:
            self.jobs.hosted[row.id] = hosted
        task = asyncio.create_task(
            self._run(row.id), name=f"sonicforge-pipeline-{row.id}"
        )
        # Register in the existing manager so ordinary /jobs cancel, service
        # shutdown and Host cancel polling work for pipeline jobs too.
        self.jobs.tasks[row.id] = task
        return row

    async def _source_value(
        self,
        request: PipelineRequest,
        execution: HostedExecution | None,
        work_dir: Path,
    ) -> PipelineValue:
        source = request.input
        if source.kind == "text":
            return PipelineValue(kind="text", text=str(source.text))
        if source.kind == "audio_stream":
            raise WorkerError("audio_stream input requires a live session, not a durable pipeline job")
        if source.kind == "audio_asset":
            with self.session_factory() as session:
                asset = session.get(Asset, source.asset_id)
                if asset is None:
                    raise WorkerError("pipeline audio asset does not exist")
                target = (self.settings.data_dir / asset.relative_path).resolve()
            if not target.is_relative_to(self.settings.data_dir.resolve()) or not target.is_file():
                raise WorkerError("pipeline audio asset content is missing")
            return PipelineValue(kind="audio", audio_path=target)
        if source.kind == "audio_grant":
            if execution is None:
                raise WorkerError("audio_grant pipeline input requires ControlDeck Host execution")
            metadata, content = await read_grant(
                self.host_client,
                execution.identity,
                str(source.grant_id),
                max_bytes=1024 * 1024 * 1024,
            )
            name = str(metadata.get("name") or metadata.get("filename") or "input.wav")
            suffix = Path(name).suffix
            if not suffix or len(suffix) > 12:
                suffix = ".bin"
            target = work_dir / f"input{suffix}"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            return PipelineValue(kind="audio", audio_path=target)
        raise WorkerError("unsupported pipeline input")

    @staticmethod
    def _number(value: object, default: float, low: float, high: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        return min(high, max(low, number))

    @staticmethod
    def _integer(value: object, default: int, low: int, high: int) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return default
        return min(high, max(low, number))

    async def _host_ai_stage(
        self,
        job_id: str,
        stage: PipelineStage,
        value: PipelineValue,
        execution: HostedExecution | None,
        progress_base: float,
    ) -> tuple[PipelineValue, dict[str, Any]]:
        if value.kind != "text" or value.text is None:
            raise WorkerError("Host AI stage requires text input")
        if execution is None:
            raise WorkerError("Host AI pipeline stage requires ControlDeck execution")
        gateway = await self.host_client.gateway_capabilities(execution.identity)
        ai = (gateway.get("control_plane") or {}).get("ai") or {}
        capabilities = ai.get("capabilities") or {}
        if capabilities.get("text.generate") is not True:
            raise WorkerError("ControlDeck text.generate is unavailable")

        messages: list[dict[str, str]] = []
        system_prompt = stage.parameters.get("system_prompt")
        if system_prompt is not None:
            system_text = str(system_prompt).strip()
            if len(system_text) > 8000:
                raise WorkerError("pipeline system_prompt is too large")
            if system_text:
                messages.append({"role": "system", "content": system_text})
        messages.append({"role": "user", "content": value.text})
        await self.jobs._set(
            job_id,
            progress=progress_base,
            result={"message": f"Pipeline {stage.id}: ControlDeck AI"},
        )
        try:
            result = await self.host_client.ai_complete(
                execution.identity,
                messages,
                temperature=self._number(stage.parameters.get("temperature"), 0.2, 0.0, 2.0),
                max_tokens=self._integer(stage.parameters.get("max_tokens"), 1024, 1, 8192),
                timeout_seconds=self._integer(stage.parameters.get("timeout_seconds"), 120, 1, 300),
            )
            content = result.get("content")
            if not isinstance(content, str) or not content.strip():
                raise WorkerError("ControlDeck AI returned empty text")
            return PipelineValue(kind="text", text=content.strip()), {
                "id": stage.id,
                "kind": stage.kind,
                "state": "succeeded",
                "output": "text",
                "provider": "control-deck-ai",
            }
        finally:
            try:
                await self.host_client.ai_release(execution.identity)
            except HostApiError as exc:
                # Explicit release is an optimization/coordination request. Older
                # Hosts may not expose it; inference success must not be rewritten
                # as failure solely because release is unavailable/refused.
                if exc.status_code not in {404, 409, 503}:
                    raise

    def _worker_request(self, stage: PipelineStage, value: PipelineValue) -> dict[str, Any]:
        common = {
            "profile": stage.profile or "default",
            "quality": stage.quality,
            "content_language": stage.language,
            "output": {"format": "wav", "sample_rate": None, "channels": None},
            "routing": stage.routing.model_dump(mode="json"),
            "seed": stage.parameters.get("seed"),
            "project_output_grant": None,
        }
        if stage.kind == "speech.asr":
            if value.kind != "audio" or value.audio_path is None:
                raise WorkerError("ASR pipeline stage requires audio input")
            return {
                **common,
                "task": "speech.asr.transcribe",
                "input": {"_internal_staged_input": str(value.audio_path)},
            }
        if stage.kind == "speech.tts":
            if value.kind != "text" or value.text is None:
                raise WorkerError("TTS pipeline stage requires text input")
            return {
                **common,
                "task": "speech.tts.synthesize",
                "input": {"text": value.text, "voice_id": stage.voice_id},
            }
        if stage.kind == "audio.sfx":
            if value.kind != "text" or value.text is None:
                raise WorkerError("SFX pipeline stage requires text input")
            return {
                **common,
                "task": "audio.sfx.generate",
                "input": {
                    "prompt": value.text,
                    **{
                        key: item
                        for key, item in stage.parameters.items()
                        if key in {"duration_sec", "loop", "category"}
                    },
                },
            }
        if stage.kind == "music.generate":
            if value.kind != "text" or value.text is None:
                raise WorkerError("music pipeline stage requires text input")
            return {
                **common,
                "task": "music.generate",
                "input": {
                    "prompt": value.text,
                    **{
                        key: item
                        for key, item in stage.parameters.items()
                        if key in {"duration_sec", "bpm", "instrumental", "lyrics"}
                    },
                },
            }
        if stage.kind == "audio.process":
            if value.kind != "audio" or value.audio_path is None:
                raise WorkerError("audio.process pipeline stage requires audio input")
            return {
                **common,
                "task": "audio.process",
                "input": {"_internal_staged_input": str(value.audio_path)},
            }
        raise WorkerError(f"unsupported local pipeline stage: {stage.kind}")

    async def _worker_stage(
        self,
        job_id: str,
        stage: PipelineStage,
        value: PipelineValue,
        execution: HostedExecution | None,
        stage_dir: Path,
        stage_index: int,
        total_stages: int,
    ) -> tuple[PipelineValue, dict[str, Any], WorkerResult, dict[str, Any]]:
        request = self._worker_request(stage, value)
        if stage.kind == "speech.tts":
            request = self.jobs._resolve_voice(request)

        lease_renew: asyncio.Task | None = None
        needs_gpu = stage.kind != "audio.process" and self.jobs._gpu_required(request)
        if needs_gpu and execution is None:
            raise WorkerError(
                f"Pipeline stage {stage.id} requires a ControlDeck Resource Broker lease"
            )
        if execution is not None:
            # Each stage starts with a clean lease/request identity. Holding a
            # previous stage lease across Host AI or another worker is forbidden.
            execution.resource_request_id = None
            execution.lease_id = None
            lease_renew = await self.jobs._acquire_resource(job_id, request, execution)

        start = 0.05 + (stage_index / max(total_stages, 1)) * 0.85
        span = 0.85 / max(total_stages, 1)

        async def progress(value_fraction: float, message: str) -> None:
            fraction = max(0.0, min(1.0, value_fraction))
            await self.jobs._set(
                job_id,
                progress=min(0.94, start + span * fraction),
                result={"message": f"Pipeline {stage.id}: {message}"},
            )

        try:
            async with self.jobs.process_lock:
                if stage.kind == "audio.process":
                    assert value.audio_path is not None
                    result = await process_audio(
                        value.audio_path,
                        stage_dir / "output.wav",
                        stage.parameters,
                        progress,
                    )
                else:
                    result = await execute(
                        self.settings,
                        request,
                        stage_dir,
                        progress,
                    )
        finally:
            if lease_renew is not None:
                lease_renew.cancel()
                await asyncio.gather(lease_renew, return_exceptions=True)
            if execution is not None:
                await self.jobs._release_resource(execution)
                execution.resource_request_id = None
                execution.lease_id = None

        trace = {
            "id": stage.id,
            "kind": stage.kind,
            "state": "succeeded",
        }
        if stage.kind == "speech.asr":
            text = result.payload.get("text")
            if not isinstance(text, str):
                raise WorkerError("ASR pipeline stage returned no text")
            trace["output"] = "text"
            return PipelineValue(kind="text", text=text), trace, result, request
        if result.output_path is None:
            raise WorkerError(f"Pipeline stage {stage.id} returned no audio")
        trace["output"] = "audio"
        return PipelineValue(kind="audio", audio_path=result.output_path), trace, result, request

    async def _deliver(
        self,
        job_id: str,
        request: PipelineRequest,
        value: PipelineValue,
        execution: HostedExecution | None,
        trace: list[dict[str, Any]],
        final_worker: WorkerResult | None,
    ) -> dict[str, Any]:
        mode = request.delivery.mode
        if mode == "text":
            if value.kind != "text" or value.text is None:
                raise WorkerError("text delivery requires pipeline text output")
            return {"text": value.text, "pipeline": {"stages": trace}}
        if mode == "websocket":
            raise WorkerError("websocket delivery requires a live session")
        if value.kind != "audio" or value.audio_path is None or final_worker is None:
            raise WorkerError("audio delivery requires generated audio output")

        provenance_request = {
            "task": "pipeline.execute",
            "profile": request.delivery.profile,
            "quality": "balanced",
            "content_language": "auto",
            "seed": None,
        }
        asset_id, target, meta = self.jobs._persist_audio_result(
            job_id,
            provenance_request,
            final_worker,
            metadata_extra={
                "pipeline": {
                    "name": request.pipeline,
                    "start_at": request.start_at,
                    "stop_after": request.stop_after,
                    "stages": trace,
                },
                "delivery_profile": request.delivery.profile,
            },
        )
        result: dict[str, Any] = {
            "asset_id": asset_id,
            "pipeline": {"stages": trace},
        }
        if mode == "package":
            package_name = package_filename(request.delivery.filename)
            package_target = (
                self.settings.data_dir
                / "tmp"
                / job_id.replace(":", "_")
                / "delivery"
                / package_name
            )
            package_manifest = {
                "schema_version": 1,
                "type": "sonicforge.pipeline-package",
                "audio": {
                    "asset_id": asset_id,
                    "filename": target.name,
                    "mime_type": meta["mime_type"],
                    "size_bytes": meta["size_bytes"],
                    "sha256": meta["sha256"],
                    "duration_ms": meta["duration_ms"],
                    "sample_rate": meta["sample_rate"],
                    "channels": meta["channels"],
                },
                "pipeline": {
                    "name": request.pipeline,
                    "start_at": request.start_at,
                    "stop_after": request.stop_after,
                    "stages": trace,
                },
            }
            package_meta = create_package(
                source_audio=target,
                target=package_target,
                audio_name=target.name,
                manifest=package_manifest,
            )
            package_asset_id = f"asset:{uuid.uuid4()}"
            package_provenance_id = f"prov:{uuid.uuid4()}"
            package_destination = (
                self.settings.assets_dir
                / f"{package_asset_id.split(':', 1)[1]}.zip"
            )
            package_destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(package_target), package_destination)
            with self.session_factory() as session:
                session.add(
                    Provenance(
                        id=package_provenance_id,
                        operation="asset.package",
                        engine_id="python.zipfile",
                        engine_version=None,
                        model_id=None,
                        model_revision=None,
                        model_license_id=None,
                        parameters={
                            "source_audio_asset_id": asset_id,
                            "filename": package_name,
                            "schema_version": 1,
                        },
                        qa={
                            "archive": "passed",
                            "semantic": "not_checked",
                        },
                    )
                )
                session.add(
                    Asset(
                        id=package_asset_id,
                        kind="package",
                        mime_type=package_meta["mime_type"],
                        relative_path=str(
                            package_destination.relative_to(self.settings.data_dir)
                        ),
                        size_bytes=package_meta["size_bytes"],
                        sha256=package_meta["sha256"],
                        duration_ms=None,
                        sample_rate=None,
                        channels=None,
                        job_id=job_id,
                        provenance_id=package_provenance_id,
                        metadata_json={
                            "filename": package_name,
                            "source_audio_asset_id": asset_id,
                            "manifest": package_manifest,
                        },
                    )
                )
                session.commit()
            return {
                "asset_id": package_asset_id,
                "audio_asset_id": asset_id,
                "content_url": f"/addon/v1/assets/{package_asset_id}/content",
                "filename": package_name,
                "pipeline": {"stages": trace},
            }
        if mode == "http":
            result["content_url"] = f"/addon/v1/assets/{asset_id}/content"
        if mode == "project":
            if execution is None:
                raise WorkerError("project delivery requires ControlDeck Host execution")
            grant_id = request.delivery.project_output_grant
            if not grant_id:
                raise WorkerError("project delivery is missing its output grant")
            filename = request.delivery.filename or target.name
            result["output"] = await commit_file(
                self.host_client,
                execution.identity,
                host_job_id=execution.host_job_id,
                grant_id=grant_id,
                source=target,
                filename=filename,
                mime_type=meta["mime_type"],
                sha256=meta["sha256"],
            )
        return result

    async def _run(self, job_id: str) -> None:
        await self.jobs._set(job_id, state="running", progress=0.01)
        with self.session_factory() as session:
            row = session.get(Job, job_id)
            if row is None:
                return
            raw = dict(row.request or {})
        try:
            request = PipelineRequest.model_validate(raw.get("pipeline"))
            compiled = compile_pipeline(request)
        except Exception as exc:
            await self.jobs._set(
                job_id,
                state="failed",
                progress=1.0,
                error_code="invalid_pipeline",
                error_message=str(exc)[:500],
            )
            self.jobs.tasks.pop(job_id, None)
            self.jobs.hosted.pop(job_id, None)
            return

        execution = self.jobs.hosted.get(job_id)
        work_dir = self.settings.data_dir / "tmp" / job_id.replace(":", "_")
        work_dir.mkdir(parents=True, exist_ok=True)
        control_watch: asyncio.Task | None = None
        trace: list[dict[str, Any]] = []
        final_worker: WorkerResult | None = None

        try:
            if execution is not None:
                control_watch = asyncio.create_task(
                    self.jobs._watch_host_cancel(job_id, execution),
                    name=f"sonicforge-pipeline-host-control-{job_id}",
                )
            current = await self._source_value(request, execution, work_dir)
            active = request.stages[compiled.start_index : compiled.stop_index + 1]
            for index, stage in enumerate(active):
                if stage.kind == "host.ai.text":
                    current, stage_trace = await self._host_ai_stage(
                        job_id,
                        stage,
                        current,
                        execution,
                        0.05 + (index / max(len(active), 1)) * 0.85,
                    )
                    final_worker = None
                else:
                    current, stage_trace, final_worker, _worker_request = await self._worker_stage(
                        job_id,
                        stage,
                        current,
                        execution,
                        work_dir / f"stage-{index:02d}-{stage.id}",
                        index,
                        len(active),
                    )
                trace.append(stage_trace)

            result = await self._deliver(
                job_id,
                request,
                current,
                execution,
                trace,
                final_worker,
            )
            await self.jobs._set(
                job_id,
                state="succeeded",
                progress=1.0,
                result=result,
            )
        except asyncio.CancelledError:
            await self.jobs._set(
                job_id,
                state="canceled",
                progress=1.0,
                error_code="canceled",
                error_message="Pipeline canceled",
            )
        except WorkerError as exc:
            await self.jobs._set(
                job_id,
                state="failed",
                progress=1.0,
                error_code="pipeline_failed",
                error_message=str(exc)[:500],
            )
        except HostApiError as exc:
            await self.jobs._set(
                job_id,
                state="failed",
                progress=1.0,
                error_code=exc.code,
                error_message=str(exc)[:500],
            )
        except Exception as exc:
            await self.jobs._set(
                job_id,
                state="failed",
                progress=1.0,
                error_code="pipeline_internal_error",
                error_message=str(exc)[:500],
            )
        finally:
            if control_watch is not None:
                control_watch.cancel()
                await asyncio.gather(control_watch, return_exceptions=True)
            if execution is not None and (execution.lease_id or execution.resource_request_id):
                await self.jobs._release_resource(execution)
            shutil.rmtree(work_dir, ignore_errors=True)
            self.jobs.tasks.pop(job_id, None)
            self.jobs.hosted.pop(job_id, None)
