from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .audio import inspect_wav
from .config import Settings
from .db import Asset, Job, LocalizationBatch, LocalizationLine, Provenance, Voice
from .events import EventBus
from .host.client import ControlDeckHostClient, HostApiError, HostIdentity
from .host.files import commit_file
from .workers import WorkerError, WorkerResult, execute, route


@dataclass
class HostedExecution:
    identity: HostIdentity
    host_job_id: str
    resource_request_id: str | None = None
    lease_id: str | None = None
    last_host_progress_at: float = 0.0
    last_host_progress: float = 0.0


class JobManager:
    def __init__(
        self,
        settings: Settings,
        session_factory,
        events: EventBus,
        *,
        host_client: ControlDeckHostClient | None = None,
    ):
        self.settings = settings
        self.session_factory = session_factory
        self.events = events
        self.host_client = host_client
        self.tasks: dict[str, asyncio.Task] = {}
        self.hosted: dict[str, HostedExecution] = {}
        # Heavy workers are intentionally serialized in the first production baseline.
        # Cross-application admission still belongs to ControlDeck Resource Broker.
        self.process_lock = asyncio.Semaphore(1)

    def create(self, request: dict, *, hosted: HostedExecution | None = None) -> Job:
        job = Job(
            id=f"job:{uuid.uuid4()}",
            task=request["task"],
            state="queued",
            request=request,
        )
        with self.session_factory() as session:
            session.add(job)
            session.commit()
            session.refresh(job)
        if hosted is not None:
            self.hosted[job.id] = hosted
        self.tasks[job.id] = asyncio.create_task(
            self._run(job.id), name=f"sonicforge-job-{job.id}"
        )
        return job

    async def cancel(self, job_id: str) -> bool:
        with self.session_factory() as session:
            job = session.get(Job, job_id)
            if not job or job.state in {"succeeded", "failed", "canceled"}:
                return False
            job.cancel_requested = True
            if job.state == "queued":
                job.state = "canceled"
                session.commit()
                task = self.tasks.get(job_id)
                if task:
                    task.cancel()
                await self.events.publish(
                    {"type": "job", "job_id": job_id, "state": "canceled"}
                )
                return True
            session.commit()
        execution = self.hosted.get(job_id)
        if (
            execution
            and self.host_client
            and execution.resource_request_id
            and not execution.lease_id
        ):
            try:
                await self.host_client.cancel_resource(
                    execution.identity, execution.resource_request_id
                )
            except HostApiError:
                pass
        task = self.tasks.get(job_id)
        if task:
            task.cancel()
        return True

    async def shutdown(self) -> None:
        tasks = list(self.tasks.values())
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self.tasks.clear()
        self.hosted.clear()

    async def _set(self, job_id: str, **values) -> None:
        with self.session_factory() as session:
            job = session.get(Job, job_id)
            if not job:
                return
            for key, value in values.items():
                setattr(job, key, value)
            session.commit()
        await self.events.publish({"type": "job", "job_id": job_id, **values})
        await self._report_host(job_id, values)

    async def _report_host(self, job_id: str, values: dict[str, Any]) -> None:
        execution = self.hosted.get(job_id)
        if execution is None or self.host_client is None:
            return
        progress = float(values.get("progress", execution.last_host_progress))
        now = time.monotonic()
        state = values.get("state")
        terminal = state in {"succeeded", "failed", "canceled"}
        if not terminal and now - execution.last_host_progress_at < 0.65:
            return
        progress = max(progress, execution.last_host_progress)
        payload: dict[str, Any] = {
            "phase": self._phase(values, state),
            "progress": {"completed": round(progress * 1000), "total": 1000},
        }
        result = values.get("result")
        message = result.get("message") if isinstance(result, dict) else None
        if message:
            payload["message"] = str(message)[:300]
        if terminal:
            payload["status"] = {
                "succeeded": "succeeded",
                "failed": "failed",
                "canceled": "canceled",
            }[str(state)]
            if state == "succeeded":
                bounded: dict[str, Any] = {}
                if isinstance(result, dict):
                    for key in (
                        "asset_id",
                        "batch_id",
                        "generated",
                        "failed",
                        "partial",
                        "language",
                        "text",
                        "segments",
                        "output",
                    ):
                        if key in result:
                            bounded[key] = result[key]
                payload["result"] = bounded
            elif values.get("error_message"):
                payload["error"] = str(values["error_message"])[:2000]
        try:
            await self.host_client.update_job(
                execution.identity, execution.host_job_id, payload
            )
        except HostApiError as exc:
            if exc.status_code not in {409, 429}:
                raise
        execution.last_host_progress = progress
        execution.last_host_progress_at = now

    @staticmethod
    def _phase(values: dict[str, Any], state: Any) -> str:
        if state == "queued":
            return "queued"
        if state == "succeeded":
            return "complete"
        if state in {"failed", "canceled"}:
            return str(state)
        return (
            "generating"
            if isinstance(values.get("result"), dict)
            and values["result"].get("message")
            else "running"
        )

    def _resource_estimate(
        self, request: dict, host_job_id: str
    ) -> dict[str, Any]:
        # 申告は実測（2026-09-05、gfx1201 / R9700、GPU 占有で測定）。多めに言うと、
        # LLM が載っている間は空きがあっても弾かれる。実測+余裕にとどめる。
        task = request["task"]
        if task in {"speech.tts.synthesize", "speech.localization.batch"}:
            peak = 4 * 1024**3          # 実測 2.49 GiB（bfloat16）
            runtime = 120 if task == "speech.tts.synthesize" else 1800
            residency = "sonicforge:qwen3-tts"
        elif task == "speech.asr.transcribe":
            peak = 3 * 1024**3          # 実測 1.84 GiB
            runtime = 180
            residency = "sonicforge:whisper"
        elif task.startswith("audio."):
            peak = 4 * 1024**3          # CPU 経路なので lease は取らない
            runtime = 180
            residency = "sonicforge:stable-audio-3"
        else:
            peak = 13 * 1024**3         # 実測 11.78 GiB（ACE-Step DiT 読み込み）
            runtime = 300
            residency = "sonicforge:ace-step-1.5"
        return {
            "job_id": host_job_id,
            "device": request.get("routing", {}).get("device") or "auto",
            "vram": {
                "resident_bytes": 0,
                "execution_peak_bytes": peak,
                "cold_load_peak_bytes": peak,
                "headroom_bytes": 512 * 1024**2,
                "confidence": "low",
            },
            # LLM と場所を分け合う。exclusive は「その device に他の lease も
            # provider 予約も無いこと」を求めるので、LLM が載っている間は VRAM の
            # 空きに関係なく device_busy_exclusive で断られる。実測（2026-09-05、
            # 31.86GiB のカードに 21.42GiB の LLM 常駐、空き 10.4GiB）:
            #   exclusive-preferred → 通らない
            #   shared-safe         → 通る
            # バイトの勘定は broker の admitted_free_bytes が見ている。
            "compute_mode": "shared-safe",
            "priority": 20,
            "class": "interactive",
            "residency_key": residency,
            "estimated_runtime_sec": runtime,
            "max_wait_sec": 300,
            "on_insufficient": "queue",
        }

    def _gpu_required(self, request: dict) -> bool:
        if self.settings.enable_fake_worker or request.get("routing", {}).get("engine") == "fake":
            return False
        if request.get("task") == "speech.localization.batch":
            return (self.settings.runtime_dir / "speech-rocm" / "bin/python").exists()
        try:
            _engine, python, _script = route(
                self.settings,
                request["task"],
                request.get("content_language", "auto"),
                request.get("routing", {}).get("engine"),
            )
        except WorkerError:
            return False
        return "rocm" in str(python).lower()

    async def _watch_host_cancel(
        self, job_id: str, execution: HostedExecution
    ) -> None:
        if self.host_client is None:
            return
        while True:
            await asyncio.sleep(1.0)
            try:
                control = await self.host_client.job_control(
                    execution.identity, execution.host_job_id
                )
            except HostApiError as exc:
                if exc.status_code in {401, 403, 409}:
                    return
                continue
            if control.get("cancel_requested") or control.get("status") == "canceled":
                task = self.tasks.get(job_id)
                if task and not task.done():
                    task.cancel()
                return

    async def _acquire_resource(
        self, job_id: str, request: dict, execution: HostedExecution
    ) -> asyncio.Task | None:
        if not self._gpu_required(request):
            return None
        if self.host_client is None:
            raise WorkerError("ControlDeck Resource Broker is not configured")
        if "resources.acquire" not in execution.identity.granted_capabilities:
            raise WorkerError(
                "ControlDeck resources.acquire capability is required for GPU work"
            )
        status = await self.host_client.request_resource(
            execution.identity,
            self._resource_estimate(request, execution.host_job_id),
        )
        request_id = status.get("request_id")
        if not isinstance(request_id, str):
            raise WorkerError("ControlDeck did not return a resource request ID")
        execution.resource_request_id = request_id
        while True:
            if status.get("state") == "granted":
                lease_id = status.get("lease_id")
                if not isinstance(lease_id, str):
                    raise WorkerError(
                        "ControlDeck granted resource without a lease ID"
                    )
                execution.lease_id = lease_id
                await self.host_client.lease_action(
                    execution.identity, lease_id, "activate"
                )
                return asyncio.create_task(
                    self._renew_lease(execution),
                    name=f"sonicforge-lease-{job_id}",
                )
            if status.get("state") in {"rejected", "canceled", "expired"}:
                raise WorkerError(
                    f"GPU resource request ended: {status.get('state')}"
                )
            await self._set(
                job_id,
                progress=0.02,
                result={
                    "message": f"Waiting for GPU: {status.get('reason') or 'queue'}"
                },
            )
            await asyncio.sleep(1.0)
            status = await self.host_client.resource_status(
                execution.identity, request_id
            )

    async def _renew_lease(self, execution: HostedExecution) -> None:
        assert self.host_client is not None
        while execution.lease_id:
            await asyncio.sleep(10)
            try:
                if execution.identity.expires_at - int(time.time()) < 120:
                    execution.identity = (
                        await self.host_client.refresh_lease_identity(
                            execution.identity, execution.lease_id
                        )
                    )
                await self.host_client.lease_action(
                    execution.identity, execution.lease_id, "renew"
                )
            except HostApiError:
                return

    async def _release_resource(self, execution: HostedExecution) -> None:
        if self.host_client is None:
            return
        if execution.lease_id:
            try:
                await self.host_client.lease_action(
                    execution.identity, execution.lease_id, "release"
                )
            except HostApiError:
                pass
            execution.lease_id = None
        elif execution.resource_request_id:
            try:
                await self.host_client.cancel_resource(
                    execution.identity, execution.resource_request_id
                )
            except HostApiError:
                pass

    def _resolve_voice(self, request: dict) -> dict:
        request = dict(request)
        inp = dict(request.get("input") or {})
        voice_id = inp.get("voice_id")
        if not (isinstance(voice_id, str) and voice_id.startswith("voice:")):
            request["input"] = inp
            return request
        with self.session_factory() as session:
            voice = session.get(Voice, voice_id)
            if voice is None:
                raise WorkerError("Selected logical voice does not exist")
            recipe = dict(voice.recipe or {})
            reference = recipe.get("reference_audio")
            if isinstance(reference, str):
                candidate = (self.settings.data_dir / reference).resolve()
                voices_root = (self.settings.data_dir / "voices").resolve()
                if (
                    not candidate.is_relative_to(voices_root)
                    or not candidate.is_file()
                ):
                    raise WorkerError(
                        "Voice reference audio is missing or outside SonicForge storage"
                    )
                recipe["reference_audio"] = str(candidate)
            inp["_internal_voice"] = {
                "id": voice.id,
                "name": voice.name,
                "source_type": voice.source_type,
                "languages": voice.languages or [],
                "engine_id": voice.engine_id,
                "recipe": recipe,
                "rights_confirmed": bool(voice.rights_confirmed),
            }
        request["input"] = inp
        return request

    def _persist_audio_result(
        self,
        job_id: str,
        request: dict,
        result: WorkerResult,
        *,
        metadata_extra: dict[str, Any] | None = None,
    ) -> tuple[str, Path, dict[str, Any]]:
        if result.output_path is None:
            raise WorkerError("audio generation returned no output")
        meta = inspect_wav(result.output_path)
        prov_id = f"prov:{uuid.uuid4()}"
        asset_id = f"asset:{uuid.uuid4()}"
        target = self.settings.assets_dir / f"{asset_id.split(':', 1)[1]}.wav"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(result.output_path), target)
        relative = str(target.relative_to(self.settings.data_dir))
        metadata = dict(result.payload or {})
        if metadata_extra:
            metadata.update(metadata_extra)
        with self.session_factory() as session:
            provenance = Provenance(
                id=prov_id,
                operation=request["task"],
                engine_id=result.engine_id,
                engine_version=result.engine_version,
                model_id=result.model_id,
                model_revision=result.model_revision,
                model_license_id=result.model_license_id,
                parameters={
                    "profile": request.get("profile"),
                    "quality": request.get("quality"),
                    "content_language": request.get("content_language"),
                    "seed": request.get("seed"),
                },
                qa=meta["qa"],
            )
            asset = Asset(
                id=asset_id,
                kind="audio",
                mime_type=meta["mime_type"],
                relative_path=relative,
                size_bytes=meta["size_bytes"],
                sha256=meta["sha256"],
                duration_ms=meta["duration_ms"],
                sample_rate=meta["sample_rate"],
                channels=meta["channels"],
                job_id=job_id,
                provenance_id=prov_id,
                metadata_json=metadata,
            )
            session.add_all([provenance, asset])
            session.commit()
        return asset_id, target, meta

    @staticmethod
    def _localization_hash(
        *,
        text: str,
        locale: str,
        voice_id: str | None,
        request: dict,
    ) -> str:
        material = {
            "text": text,
            "locale": locale,
            "voice_id": voice_id,
            "profile": request.get("profile"),
            "quality": request.get("quality"),
            "routing": request.get("routing"),
            "seed": request.get("seed"),
        }
        return hashlib.sha256(
            json.dumps(
                material,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode()
        ).hexdigest()

    async def _run_localization_batch(
        self,
        job_id: str,
        request: dict,
        work_dir: Path,
        progress,
    ) -> dict[str, Any]:
        inp = request.get("input") or {}
        batch_id = str(inp["batch_id"])
        locales = list(inp.get("locales") or ["ja", "en"])
        mode = str(inp.get("mode") or "pending")
        requested_line_ids = set(inp.get("line_ids") or [])
        with self.session_factory() as session:
            batch = session.get(LocalizationBatch, batch_id)
            if batch is None:
                raise WorkerError("Localization batch does not exist")
            batch.state = "rendering"
            snapshot = []
            for line in batch.lines:
                if requested_line_ids and line.line_id not in requested_line_ids:
                    continue
                outputs = dict(line.outputs or {})
                qa = dict(line.qa or {})
                locale_states = dict(qa.get("locales") or {})
                input_hashes = dict(qa.get("input_hashes") or {})
                for locale in locales:
                    text = line.ja_text if locale == "ja" else line.en_text
                    if not text:
                        continue
                    current_hash = self._localization_hash(
                        text=text,
                        locale=locale,
                        voice_id=line.voice_id,
                        request=request,
                    )
                    previous_state = (
                        locale_states.get(locale, {}).get("state")
                        if isinstance(locale_states.get(locale), dict)
                        else None
                    )
                    previous_hash = input_hashes.get(locale)
                    has_output = bool(outputs.get(locale))
                    should_render = (
                        mode == "all"
                        or (mode == "failed" and previous_state == "failed")
                        or (
                            mode == "changed"
                            and (not has_output or previous_hash != current_hash)
                        )
                        or (
                            mode == "pending"
                            and (not has_output or previous_state != "succeeded")
                        )
                    )
                    if should_render:
                        snapshot.append(
                            {
                                "row_id": line.id,
                                "line_id": line.line_id,
                                "locale": locale,
                                "text": text,
                                "voice_id": line.voice_id,
                                "input_hash": current_hash,
                            }
                        )
            session.commit()

        generated = 0
        failed = 0
        total = len(snapshot)
        for index, item in enumerate(snapshot):
            line_dir = work_dir / f"{item['row_id']}-{item['locale']}"
            child_request = {
                **request,
                "task": "speech.tts.synthesize",
                "content_language": item["locale"],
                "project_output_grant": None,
                "input": {
                    "text": item["text"],
                    "voice_id": item["voice_id"],
                },
            }
            child_request = self._resolve_voice(child_request)

            async def child_progress(value: float, message: str) -> None:
                base = index / max(total, 1)
                span = 1.0 / max(total, 1)
                await progress(
                    min(0.98, base + span * max(0.0, min(1.0, value))),
                    f"{item['line_id']} [{item['locale']}]: {message}",
                )

            try:
                result = await execute(
                    self.settings,
                    child_request,
                    line_dir,
                    child_progress,
                )
                asset_id, _target, meta = self._persist_audio_result(
                    job_id,
                    child_request,
                    result,
                    metadata_extra={
                        "localization_batch_id": batch_id,
                        "line_id": item["line_id"],
                        "locale": item["locale"],
                    },
                )
                with self.session_factory() as session:
                    line = session.get(LocalizationLine, item["row_id"])
                    if line is None:
                        raise WorkerError(
                            "Localization line disappeared during rendering"
                        )
                    outputs = dict(line.outputs or {})
                    outputs[item["locale"]] = asset_id
                    qa = dict(line.qa or {})
                    locale_states = dict(qa.get("locales") or {})
                    input_hashes = dict(qa.get("input_hashes") or {})
                    locale_states[item["locale"]] = {
                        "state": "succeeded",
                        "asset_id": asset_id,
                        "decode": meta["qa"].get("decode", "not_checked"),
                        "semantic": "not_checked",
                    }
                    input_hashes[item["locale"]] = item["input_hash"]
                    qa["locales"] = locale_states
                    qa["input_hashes"] = input_hashes
                    qa["state"] = (
                        "failed"
                        if any(
                            isinstance(value, dict)
                            and value.get("state") == "failed"
                            for value in locale_states.values()
                        )
                        else "passed"
                    )
                    line.outputs = outputs
                    line.qa = qa
                    line.status = (
                        "failed" if qa["state"] == "failed" else "succeeded"
                    )
                    session.commit()
                generated += 1
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                with self.session_factory() as session:
                    line = session.get(LocalizationLine, item["row_id"])
                    if line is not None:
                        qa = dict(line.qa or {})
                        locale_states = dict(qa.get("locales") or {})
                        input_hashes = dict(qa.get("input_hashes") or {})
                        locale_states[item["locale"]] = {
                            "state": "failed",
                            "error": str(exc)[:300],
                            "semantic": "not_checked",
                        }
                        input_hashes[item["locale"]] = item["input_hash"]
                        qa["locales"] = locale_states
                        qa["input_hashes"] = input_hashes
                        qa["state"] = "failed"
                        line.qa = qa
                        line.status = "failed"
                        session.commit()
                failed += 1
            await progress(
                (index + 1) / max(total, 1),
                f"Rendered {index + 1}/{total}",
            )

        with self.session_factory() as session:
            batch = session.get(LocalizationBatch, batch_id)
            if batch is None:
                raise WorkerError("Localization batch disappeared")
            any_failed = any(
                (line.qa or {}).get("state") == "failed" for line in batch.lines
            )
            batch.state = "partial" if any_failed else "complete"
            session.commit()
        return {
            "batch_id": batch_id,
            "mode": mode,
            "locales": locales,
            "generated": generated,
            "failed": failed,
            "skipped": max(0, total - generated - failed),
            "partial": failed > 0,
        }

    async def _run(self, job_id: str) -> None:
        await self._set(job_id, state="running", progress=0.01)
        with self.session_factory() as session:
            job = session.get(Job, job_id)
            if job is None:
                return
            request = dict(job.request)
        if request.get("task") != "speech.localization.batch":
            request = self._resolve_voice(request)

        work_dir = self.settings.data_dir / "tmp" / job_id.replace(":", "_")
        execution = self.hosted.get(job_id)
        lease_renew: asyncio.Task | None = None
        control_watch: asyncio.Task | None = None

        async def progress(value: float, message: str):
            await self._set(
                job_id,
                progress=max(0.0, min(0.98, value)),
                result={"message": message},
            )

        try:
            if execution is not None:
                control_watch = asyncio.create_task(
                    self._watch_host_cancel(job_id, execution),
                    name=f"sonicforge-host-control-{job_id}",
                )
            if execution is not None:
                lease_renew = await self._acquire_resource(
                    job_id, request, execution
                )

            if request.get("task") == "speech.localization.batch":
                async with self.process_lock:
                    batch_result = await self._run_localization_batch(
                        job_id, request, work_dir, progress
                    )
                if batch_result["generated"] == 0 and batch_result["failed"] > 0:
                    raise WorkerError(
                        f"Localization batch failed for {batch_result['failed']} render(s)"
                    )
                await self._set(
                    job_id,
                    state="succeeded",
                    progress=1.0,
                    result=batch_result,
                )
                return

            async with self.process_lock:
                result = await execute(
                    self.settings, request, work_dir, progress
                )
            output_asset = None
            output_commit = None
            if result.output_path:
                output_asset, target, meta = self._persist_audio_result(
                    job_id, request, result
                )
                grant_id = request.get("project_output_grant")
                if grant_id:
                    if execution is None or self.host_client is None:
                        raise WorkerError(
                            "project output grants require a ControlDeck-managed execution"
                        )
                    output_commit = await commit_file(
                        self.host_client,
                        execution.identity,
                        host_job_id=execution.host_job_id,
                        grant_id=str(grant_id),
                        source=target,
                        filename=str(
                            result.payload.get("filename") or target.name
                        ),
                        mime_type=meta["mime_type"],
                        sha256=meta["sha256"],
                    )
            final_result = {"asset_id": output_asset, **result.payload}
            if output_commit is not None:
                final_result["output"] = output_commit
            await self._set(
                job_id,
                state="succeeded",
                progress=1.0,
                result=final_result,
            )
        except asyncio.CancelledError:
            await self._set(
                job_id,
                state="canceled",
                progress=1.0,
                error_code="canceled",
                error_message="Canceled",
            )
        except WorkerError as exc:
            await self._set(
                job_id,
                state="failed",
                progress=1.0,
                error_code="worker_failed",
                error_message=str(exc)[:500],
            )
        except HostApiError as exc:
            await self._set(
                job_id,
                state="failed",
                progress=1.0,
                error_code=exc.code,
                error_message=str(exc)[:500],
            )
        except Exception as exc:
            await self._set(
                job_id,
                state="failed",
                progress=1.0,
                error_code="internal_error",
                error_message=str(exc)[:500],
            )
        finally:
            for task in (lease_renew, control_watch):
                if task is not None:
                    task.cancel()
            await asyncio.gather(
                *[
                    task
                    for task in (lease_renew, control_watch)
                    if task is not None
                ],
                return_exceptions=True,
            )
            if execution is not None:
                await self._release_resource(execution)
            inp = request.get("input", {}) if "request" in locals() else {}
            for key in (
                "_internal_staged_input",
                "_internal_reference_audio",
            ):
                staged = inp.get(key)
                if staged:
                    try:
                        Path(staged).unlink(missing_ok=True)
                    except OSError:
                        pass
            shutil.rmtree(work_dir, ignore_errors=True)
            self.tasks.pop(job_id, None)
            self.hosted.pop(job_id, None)
