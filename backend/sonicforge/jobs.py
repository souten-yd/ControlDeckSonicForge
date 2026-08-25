from __future__ import annotations

import asyncio
import shutil
import uuid
from pathlib import Path

from .audio import inspect_wav
from .config import Settings
from .db import Asset, Job, Provenance
from .events import EventBus
from .workers import WorkerError, execute


class JobManager:
    def __init__(self, settings: Settings, session_factory, events: EventBus):
        self.settings = settings
        self.session_factory = session_factory
        self.events = events
        self.tasks: dict[str, asyncio.Task] = {}

    def create(self, request: dict) -> Job:
        job = Job(id=f"job:{uuid.uuid4()}", task=request["task"], state="queued", request=request)
        with self.session_factory() as session:
            session.add(job); session.commit(); session.refresh(job)
        self.tasks[job.id] = asyncio.create_task(self._run(job.id))
        return job

    async def cancel(self, job_id: str) -> bool:
        with self.session_factory() as session:
            job = session.get(Job, job_id)
            if not job or job.state in {"succeeded","failed","canceled"}:
                return False
            job.cancel_requested = True
            if job.state == "queued":
                job.state = "canceled"
                session.commit()
                task = self.tasks.get(job_id)
                if task:
                    task.cancel()
                await self.events.publish({"type":"job","job_id":job_id,"state":"canceled"})
                return True
            session.commit()
        task = self.tasks.get(job_id)
        if task:
            task.cancel()
        return True

    async def _set(self, job_id: str, **values) -> None:
        with self.session_factory() as session:
            job = session.get(Job, job_id)
            if not job:
                return
            for key, value in values.items():
                setattr(job, key, value)
            session.commit()
        await self.events.publish({"type":"job","job_id":job_id,**values})

    async def _run(self, job_id: str) -> None:
        await self._set(job_id, state="running", progress=0.01)
        with self.session_factory() as session:
            job = session.get(Job, job_id)
            request = dict(job.request)
        work_dir = self.settings.data_dir / "tmp" / job_id.replace(":", "_")
        async def progress(value: float, message: str):
            await self._set(job_id, progress=max(0.0, min(0.98, value)), result={"message": message})
        try:
            result = await execute(self.settings, request, work_dir, progress)
            output_asset = None
            if result.output_path:
                meta = inspect_wav(result.output_path)
                prov_id = f"prov:{uuid.uuid4()}"
                asset_id = f"asset:{uuid.uuid4()}"
                target = self.settings.assets_dir / f"{asset_id.split(':',1)[1]}.wav"
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(result.output_path), target)
                relative = str(target.relative_to(self.settings.data_dir))
                with self.session_factory() as session:
                    provenance = Provenance(
                        id=prov_id, operation=request["task"], engine_id=result.engine_id,
                        engine_version=result.engine_version, model_id=result.model_id,
                        model_revision=result.model_revision, model_license_id=result.model_license_id,
                        parameters={"profile":request.get("profile"),"quality":request.get("quality"),"content_language":request.get("content_language"),"seed":request.get("seed")},
                        qa=meta["qa"],
                    )
                    asset = Asset(
                        id=asset_id, kind="audio", mime_type=meta["mime_type"], relative_path=relative,
                        size_bytes=meta["size_bytes"], sha256=meta["sha256"], duration_ms=meta["duration_ms"],
                        sample_rate=meta["sample_rate"], channels=meta["channels"], job_id=job_id,
                        provenance_id=prov_id, metadata_json=result.payload,
                    )
                    session.add_all([provenance, asset]); session.commit()
                output_asset = asset_id
            await self._set(job_id, state="succeeded", progress=1.0, result={"asset_id":output_asset, **result.payload})
        except asyncio.CancelledError:
            await self._set(job_id, state="canceled", error_code="canceled", error_message="Canceled")
        except WorkerError as exc:
            await self._set(job_id, state="failed", error_code="worker_failed", error_message=str(exc)[:500])
        except Exception as exc:
            await self._set(job_id, state="failed", error_code="internal_error", error_message=str(exc)[:500])
        finally:
            staged=request.get("input",{}).get("_internal_staged_input") if "request" in locals() else None
            if staged:
                try: Path(staged).unlink(missing_ok=True)
                except OSError: pass
            shutil.rmtree(work_dir, ignore_errors=True)
            self.tasks.pop(job_id, None)
