from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from .audio_process import process_audio
from .db import Asset, Provenance
from .pipeline_package import create_package, package_filename
from .pipeline_runtime import PipelineRuntime, PipelineValue
from .workers import WorkerError


def install_pipeline_extensions() -> None:
    if getattr(PipelineRuntime, "_sonicforge_pipeline_extensions_installed", False):
        return

    original_worker_stage = PipelineRuntime._worker_stage
    original_deliver = PipelineRuntime._deliver

    async def worker_stage(
        self,
        job_id,
        stage,
        value,
        execution,
        stage_dir,
        stage_index,
        total_stages,
    ):
        if stage.kind != "audio.process":
            return await original_worker_stage(
                self,
                job_id,
                stage,
                value,
                execution,
                stage_dir,
                stage_index,
                total_stages,
            )
        if value.kind != "audio" or value.audio_path is None:
            raise WorkerError("audio.process requires audio input")
        start = 0.05 + (stage_index / max(total_stages, 1)) * 0.85
        span = 0.85 / max(total_stages, 1)

        async def progress(fraction: float, message: str) -> None:
            fraction = max(0.0, min(1.0, fraction))
            await self.jobs._set(
                job_id,
                progress=min(0.94, start + span * fraction),
                result={"message": f"Pipeline {stage.id}: {message}"},
            )

        target = Path(stage_dir) / "processed.wav"
        result = await process_audio(
            value.audio_path,
            target,
            dict(stage.parameters or {}),
            progress,
        )
        request = {
            "task": "audio.process",
            "profile": stage.profile or "default",
            "quality": stage.quality,
            "content_language": stage.language,
            "parameters": dict(stage.parameters or {}),
        }
        return (
            PipelineValue(kind="audio", audio_path=result.output_path),
            {
                "id": stage.id,
                "kind": stage.kind,
                "state": "succeeded",
                "output": "audio",
                "engine": "ffmpeg.audio-process",
            },
            result,
            request,
        )

    async def deliver(
        self,
        job_id,
        request,
        value,
        execution,
        trace,
        final_worker,
    ):
        if request.delivery.mode != "package":
            return await original_deliver(
                self,
                job_id,
                request,
                value,
                execution,
                trace,
                final_worker,
            )
        if value.kind != "audio" or value.audio_path is None or final_worker is None:
            raise WorkerError("package delivery requires audio output")

        # Reuse the canonical asset/provenance path first. The package is a
        # deterministic derived artifact, not a replacement for the audio asset.
        asset_delivery = request.delivery.model_copy(
            update={
                "mode": "asset",
                "project_output_grant": None,
                "filename": None,
            }
        )
        asset_request = request.model_copy(update={"delivery": asset_delivery})
        base_result = await original_deliver(
            self,
            job_id,
            asset_request,
            value,
            execution,
            trace,
            final_worker,
        )
        audio_asset_id = base_result.get("asset_id")
        if not isinstance(audio_asset_id, str):
            raise WorkerError("package delivery could not persist source audio")

        with self.session_factory() as db:
            source = db.get(Asset, audio_asset_id)
            if source is None:
                raise WorkerError("package source asset disappeared")
            source_path = (self.settings.data_dir / source.relative_path).resolve()
            source_sha = source.sha256
            source_mime = source.mime_type
            source_size = source.size_bytes
        if not source_path.is_relative_to(self.settings.data_dir.resolve()) or not source_path.is_file():
            raise WorkerError("package source content is missing")

        package_id = f"asset:{uuid.uuid4()}"
        prov_id = f"prov:{uuid.uuid4()}"
        filename = package_filename(request.delivery.filename)
        package_path = self.settings.assets_dir / f"{package_id.split(':', 1)[1]}.zip"
        manifest: dict[str, Any] = {
            "schema_version": 1,
            "type": "sonicforge.pipeline-package",
            "pipeline": {
                "name": request.pipeline,
                "start_at": request.start_at,
                "stop_after": request.stop_after,
                "stages": trace,
            },
            "audio": {
                "asset_id": audio_asset_id,
                "filename": source_path.name,
                "mime_type": source_mime,
                "size_bytes": source_size,
                "sha256": source_sha,
            },
        }
        meta = create_package(
            source_audio=source_path,
            target=package_path,
            audio_name=source_path.name,
            manifest=manifest,
        )
        relative = str(package_path.relative_to(self.settings.data_dir))
        with self.session_factory() as db:
            db.add(
                Provenance(
                    id=prov_id,
                    operation="pipeline.package",
                    engine_id="sonicforge.package",
                    engine_version=None,
                    model_id=None,
                    model_revision=None,
                    model_license_id=None,
                    parameters={
                        "source_asset_id": audio_asset_id,
                        "filename": filename,
                        "pipeline": manifest["pipeline"],
                    },
                    qa={"archive": "passed", "semantic": "not_checked"},
                )
            )
            db.add(
                Asset(
                    id=package_id,
                    kind="package",
                    mime_type=meta["mime_type"],
                    relative_path=relative,
                    size_bytes=meta["size_bytes"],
                    sha256=meta["sha256"],
                    duration_ms=None,
                    sample_rate=None,
                    channels=None,
                    job_id=job_id,
                    provenance_id=prov_id,
                    metadata_json={
                        "filename": filename,
                        "derived_from": audio_asset_id,
                        "package_type": "sonicforge.pipeline-package",
                    },
                )
            )
            db.commit()
        return {
            "asset_id": audio_asset_id,
            "package_asset_id": package_id,
            "package_filename": filename,
            "content_url": f"/addon/v1/assets/{package_id}/content",
            "pipeline": {"stages": trace},
        }

    PipelineRuntime._worker_stage = worker_stage
    PipelineRuntime._deliver = deliver
    PipelineRuntime._sonicforge_pipeline_extensions_installed = True
