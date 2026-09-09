from __future__ import annotations

import asyncio
import logging
import shutil
import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from sqlalchemy import and_, or_
from sqlalchemy.orm import selectinload

from .capabilities import capability_document
from .models_catalog import model_document
from .config import ensure_directories, load_settings
from .db import Asset, Job, LocalizationBatch, LocalizationLine, Provenance, Voice, make_session_factory
from .events import EventBus
from .host.client import ControlDeckHostClient, HostApiError, HostIdentity
from .host.files import read_grant
from .jobs import HostedExecution, JobManager, ProgressGate
from .legacy_data import LegacyDataError, migrate_discovered_legacy_data
from .schemas import LocalizationBatchCreate, SetupApplyRequest, SetupCredentials, TaskRequest, TtsPreferenceUpdate, TtsSampleInstall, VoiceCreate
from .workers import (
    keep_engines_warm,
    retire_warm_workers,
    start_idle_sweeper,
    stop_idle_sweeper,
)
from . import uploads
from . import voice_catalog
from . import setup as setup_service
from . import tts_models
from . import tts_samples
from . import __version__

settings = load_settings()
ensure_directories(settings)
session_factory = make_session_factory(settings)
try:
    legacy_data_imports = migrate_discovered_legacy_data(settings)
except (LegacyDataError, OSError, sqlite3.Error) as exc:
    # A failed import must never make the already usable managed data unavailable.
    # The untouched legacy source and the pre-import backup remain available for repair.
    logging.getLogger(__name__).error("legacy SonicForge data import failed: %s", exc)
    legacy_data_imports = []
events = EventBus()
host_client = ControlDeckHostClient(settings.control_deck_url)
jobs = JobManager(settings, session_factory, events, host_client=host_client)
setup_tasks: dict[str, asyncio.Task[None]] = {}


def _job_dict(job: Job) -> dict[str, Any]:
    return {"id": job.id, "task": job.task, "state": job.state, "progress": job.progress, "result": job.result or {}, "error_code": job.error_code, "error_message": job.error_message, "cancel_requested": bool(job.cancel_requested), "created_at": job.created_at.isoformat() if job.created_at else None, "updated_at": job.updated_at.isoformat() if job.updated_at else None}


def _asset_dict(asset: Asset) -> dict[str, Any]:
    return {"id": asset.id, "kind": asset.kind, "mime_type": asset.mime_type, "size_bytes": asset.size_bytes, "sha256": asset.sha256, "duration_ms": asset.duration_ms, "sample_rate": asset.sample_rate, "channels": asset.channels, "job_id": asset.job_id, "provenance_id": asset.provenance_id, "metadata": asset.metadata_json or {}, "created_at": asset.created_at.isoformat() if asset.created_at else None}


def _voice_dict(voice: Voice) -> dict[str, Any]:
    return {"id": voice.id, "name": voice.name, "source_type": voice.source_type, "languages": voice.languages or [], "engine_id": voice.engine_id, "recipe": voice.recipe or {}, "rights_confirmed": bool(voice.rights_confirmed), "created_at": voice.created_at.isoformat() if voice.created_at else None}


def _host_headers_present(request: Request) -> bool:
    return bool(request.headers.get("authorization") or request.headers.get("x-control-deck-addon-id"))


def _agent_arguments(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    nested = value.get("input")
    if isinstance(value.get("correlation"), dict) and isinstance(nested, dict):
        return nested
    return value


async def _host_identity(request: Request) -> HostIdentity | None:
    if not _host_headers_present(request): return None
    try: return await host_client.authenticate(request.headers)
    except HostApiError as exc: raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc


async def _stage_read_grant(identity: HostIdentity, grant_id: str, *, max_bytes: int, suffix: str = ".bin") -> str:
    metadata, content = await read_grant(host_client, identity, grant_id, max_bytes=max_bytes)
    staging = settings.data_dir / "tmp" / "imports"; staging.mkdir(parents=True, exist_ok=True)
    filename = str(metadata.get("filename") or ""); guessed = Path(filename).suffix if filename else ""; extension = guessed if guessed and len(guessed) <= 12 else suffix
    target = staging / f"{uuid.uuid4().hex}{extension}"; target.write_bytes(content); return str(target)


async def _prepare_task(
    request: Request, body: TaskRequest, *, detached_host_job: bool = False
) -> tuple[dict[str, Any], HostedExecution | None]:
    payload = body.model_dump(mode="json"); identity = await _host_identity(request); hosted: HostedExecution | None = None
    # Uploaded audio is already on this machine, so it resolves without a Host
    # round trip. Copy it into the job's staging area so the durable job owns a
    # file whose lifetime it controls, and the upload can be replayed.
    upload_input = payload.get("input", {}).get("upload_id")
    if upload_input:
        try: source = uploads.resolve(settings, str(upload_input))
        except uploads.UploadError as exc: raise HTTPException(status_code=400, detail={"code": "invalid_upload", "message": str(exc)}) from exc
        staging = settings.data_dir / "tmp" / "imports"; staging.mkdir(parents=True, exist_ok=True)
        staged = staging / f"{uuid.uuid4().hex}.wav"; shutil.copyfile(source, staged)
        payload["input"]["_internal_staged_input"] = str(staged)
    if identity is not None:
        if "jobs.write" not in identity.granted_capabilities: raise HTTPException(status_code=403, detail={"code": "capability_not_granted", "message": "jobs.write is required"})
        created = await host_client.create_or_attach_job(identity, title=f"SonicForge: {body.task}", detached=detached_host_job); identity = await host_client.identity_from_job_response(identity, created, required=detached_host_job); host_job = created.get("job") if isinstance(created, dict) else None; host_job_id = host_job.get("id") if isinstance(host_job, dict) else None
        if not isinstance(host_job_id, str) or not host_job_id: raise HTTPException(status_code=502, detail={"code": "invalid_host_response", "message": "ControlDeck did not return a Host Job"})
        hosted = HostedExecution(identity=identity, host_job_id=host_job_id, owns_terminal=bool(isinstance(created, dict) and created.get("created") is True)); inp = payload.setdefault("input", {})
        if body.task == "speech.asr.transcribe":
            grant_id = inp.get("audio_grant") or inp.get("grant_id")
            if grant_id: inp["_internal_staged_input"] = await _stage_read_grant(identity, str(grant_id), max_bytes=1024 * 1024 * 1024, suffix=".wav")
        reference_grant = inp.get("reference_grant")
        if reference_grant: inp["_internal_reference_audio"] = await _stage_read_grant(identity, str(reference_grant), max_bytes=256 * 1024 * 1024, suffix=".wav")
    return payload, hosted


def _health_item(component: dict[str, Any]) -> dict[str, Any]:
    state = str(component.get("state") or "missing")
    mapped = "ok" if state == "available" else "checking" if state == "installing" else "error" if state == "error" else "missing"
    labels = {"core": "SonicForge core", "speech-essentials": "Speech Essentials", "gpt-sovits": "GPT-SoVITS", "game-audio": "Game Audio", "music": "Music"}
    detail = component.get("detail") or None
    return {"id": str(component["id"]), "label": labels.get(str(component["id"]), str(component["id"])), "state": mapped, "detail": str(detail)[:300] if detail else None}


async def _run_setup_job(job_id: str, body: SetupApplyRequest, hosted: HostedExecution | None) -> None:
    if hosted is not None: jobs.hosted[job_id] = hosted
    async def progress(value: float, message: str) -> None:
        if hosted is not None:
            control = await host_client.job_control(hosted.identity, hosted.host_job_id)
            if control.get("cancel_requested") or control.get("status") == "canceled": raise asyncio.CancelledError
        await jobs._set(job_id, state="running", progress=min(max(value, 0.0), 0.99), result={"message": message, "profile": body.profile})
    try:
        with session_factory() as session: result = await setup_service.apply(settings, session, body.profile, body.components or None, progress=progress, accepted_terms=body.accepted_terms)
        await jobs._set(job_id, state="succeeded", progress=1.0, result=result)
        await events.publish({"type": "setup", "job_id": job_id, "state": "succeeded", "progress": 1.0})
    except asyncio.CancelledError:
        await jobs._set(job_id, state="canceled", progress=1.0, error_code="canceled", error_message="Setup canceled")
        await events.publish({"type": "setup", "job_id": job_id, "state": "canceled"})
    except Exception as exc:
        await jobs._set(job_id, state="failed", progress=1.0, error_code="setup_failed", error_message=str(exc)[-1200:])
        await events.publish({"type": "setup", "job_id": job_id, "state": "failed"})
    finally:
        setup_tasks.pop(job_id, None); jobs.hosted.pop(job_id, None)


async def _start_setup(body: SetupApplyRequest, request: Request) -> dict[str, Any]:
    identity = await _host_identity(request); hosted: HostedExecution | None = None
    if identity is not None:
        if "jobs.write" not in identity.granted_capabilities: raise HTTPException(status_code=403, detail={"code": "capability_not_granted", "message": "jobs.write is required"})
        created = await host_client.create_or_attach_job(identity, title=f"SonicForge setup: {body.profile}"); identity = await host_client.identity_from_job_response(identity, created); host_job_id = (created.get("job") or {}).get("id")
        if not isinstance(host_job_id, str) or not host_job_id: raise HTTPException(status_code=502, detail="ControlDeck did not return a Host Job")
        hosted = HostedExecution(identity=identity, host_job_id=host_job_id)
    job_id = f"job:{uuid.uuid4()}"
    with session_factory() as session:
        row = Job(id=job_id, task="system.setup", state="queued", progress=0.0, request={"profile": body.profile, "components": body.components, "accepted_terms": body.accepted_terms}); session.add(row); session.commit()
    task = asyncio.create_task(_run_setup_job(job_id, body, hosted), name=f"sonicforge-setup-{job_id}"); setup_tasks[job_id] = task
    return {"setup_id": job_id, "job_id": job_id, "state": "queued", "host_job_id": hosted.host_job_id if hosted else None}


@asynccontextmanager
async def lifespan(app: FastAPI):
    with session_factory() as session:
        for row in session.query(Job).filter(Job.state.in_(["queued", "running"])).all(): row.state = "failed"; row.error_code = "service_restarted"; row.error_message = "Service restarted before the job completed"
        session.commit()
    # 使われなくなった常駐を降ろす見張り。抱えたままにすると、31.9GiB の
    # カードでは画像や音楽の枠を削る。
    start_idle_sweeper()
    yield
    await stop_idle_sweeper()
    for task in list(setup_tasks.values()): task.cancel()
    if setup_tasks: await asyncio.gather(*setup_tasks.values(), return_exceptions=True)
    await jobs.shutdown()
    # 常駐させた worker は自分で終わらせる。プロセスを残したまま抜けると、
    # 載せたモデルもそのまま残る。
    await retire_warm_workers()
    await host_client.close()


app = FastAPI(title="SonicForge", version=__version__, lifespan=lifespan)


@app.get("/health")
async def health():
    with session_factory() as session: setup = setup_service.status(session)
    ready = setup["state"] == "available" or settings.enable_fake_worker
    response: dict[str, Any] = {"status": "healthy" if ready else "setup_required", "contract_version": "2.0", "setup": [_health_item(item) for item in setup["components"]]}
    if not ready: response.update({"reason_code": "setup_incomplete", "message": "Speech Essentials is not installed", "action": {"kind": "open_route", "route": "/x/sonic-forge/workspace"}})
    return response


@app.get("/addon/v1/capabilities")
async def capabilities():
    with session_factory() as session: return capability_document(session, fake_enabled=settings.enable_fake_worker)


@app.get("/addon/v1/setup/status")
async def setup_status():
    with session_factory() as session: return setup_service.status(session)


@app.post("/addon/v1/uploads")
async def create_upload(file: UploadFile = File(...)):
    """Accept audio recorded or picked in the browser.

    The ControlDeck picker is the right path for audio that already lives in a
    project. It cannot reach a microphone recording, and on a phone it is not
    the picker the person expects, so browser-side audio arrives here instead.
    """
    try:
        return await uploads.store(settings, file, filename=file.filename)
    except uploads.UploadError as exc:
        raise HTTPException(status_code=400, detail={"code": "invalid_upload", "message": str(exc)}) from exc


@app.get("/addon/v1/setup/credentials")
async def setup_credentials_state(): return setup_service.credential_state(settings)


@app.put("/addon/v1/setup/credentials")
async def set_setup_credentials(body: SetupCredentials):
    token = body.huggingface_token
    setup_service.write_credentials(settings, {"huggingface_token": (token.strip() or None) if isinstance(token, str) else None})
    return setup_service.credential_state(settings)


@app.get("/addon/v1/models")
async def models():
    with session_factory() as session:
        return model_document(
            session, settings=settings, fake_enabled=settings.enable_fake_worker
        )


@app.get("/addon/v1/tts/preferences")
async def tts_preferences():
    with session_factory() as session:
        return tts_models.preferences(session)


@app.put("/addon/v1/tts/preferences")
async def set_tts_preferences(body: TtsPreferenceUpdate):
    try:
        with session_factory() as session:
            return tts_models.set_preference(
                session,
                engine_id=body.engine_id,
                model_id=body.gpt_sovits_model_id,
                voice_id=body.gpt_sovits_voice_id,
            )
    except tts_models.ModelPackError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/addon/v1/tts/models")
async def tts_model_packs():
    with session_factory() as session:
        return tts_models.model_document(settings, session)


@app.get("/addon/v1/tts/samples")
async def tts_sample_catalog():
    with session_factory() as session:
        return tts_samples.catalog(session)


@app.post("/addon/v1/tts/samples/{sample_id}/install")
async def install_tts_sample(sample_id: str, body: TtsSampleInstall):
    try:
        with session_factory() as session:
            voice = await tts_samples.install(
                settings, session, sample_id, accepted_terms=body.accepted_terms
            )
            tts_models.set_preference(
                session,
                engine_id="tts.gpt-sovits",
                model_id=tts_models.BASE_GPT_MODEL,
                voice_id=voice.id,
            )
            return _voice_dict(voice)
    except tts_samples.SampleCatalogError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/addon/v1/tts/models/upload")
async def upload_tts_model(file: UploadFile = File(...)):
    try:
        with session_factory() as session:
            return await tts_models.install(settings, session, file)
    except tts_models.ModelPackError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/addon/v1/tts/models/{model_id:path}/activate")
async def activate_tts_model(model_id: str):
    try:
        with session_factory() as session:
            current = tts_models.preferences(session)
            return tts_models.set_preference(
                session,
                engine_id=current["engine_id"],
                model_id=model_id,
                voice_id=None,
            )
    except tts_models.ModelPackError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/addon/v1/tts/models/{model_id:path}")
async def delete_tts_model(model_id: str):
    try:
        with session_factory() as session:
            tts_models.delete(settings, session, model_id)
        return {"deleted": True, "model_id": model_id}
    except tts_models.ModelPackError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/addon/v1/setup/plan")
async def setup_plan(profile: str = "speech-essentials"): return setup_service.plan(settings, profile)


@app.post("/addon/v1/setup/apply")
async def setup_apply(body: SetupApplyRequest, request: Request): return await _start_setup(body, request)


@app.post("/addon/v1/setup/cancel/{job_id:path}")
async def setup_cancel(job_id: str):
    task = setup_tasks.get(job_id)
    if task is None: raise HTTPException(status_code=404, detail="setup job not found")
    task.cancel(); return {"job_id": job_id, "cancel_requested": True}


@app.post("/addon/v1/setup/repair")
async def setup_repair(body: SetupApplyRequest, request: Request): return await _start_setup(body, request)
@app.post("/addon/v1/setup/update")
async def setup_update(body: SetupApplyRequest, request: Request): return await _start_setup(body, request)


@app.post("/addon/v1/tasks")
async def create_task(body: TaskRequest, request: Request):
    payload, hosted = await _prepare_task(request, body)
    try: job = jobs.create(payload, hosted=hosted)
    except Exception:
        for key in ("_internal_staged_input", "_internal_reference_audio"):
            value = payload.get("input", {}).get(key)
            if value: Path(value).unlink(missing_ok=True)
        raise
    return {"job_id": job.id, "state": job.state, "host_job_id": hosted.host_job_id if hosted else None}


@app.get("/addon/v1/jobs")
async def list_jobs(limit: int = 50):
    limit = min(max(limit, 1), 200)
    with session_factory() as session: return {"jobs": [_job_dict(row) for row in session.query(Job).order_by(Job.created_at.desc()).limit(limit).all()]}


@app.get("/addon/v1/jobs/{job_id:path}")
async def get_job(job_id: str):
    with session_factory() as session:
        row = session.get(Job, job_id)
        if row is None: raise HTTPException(status_code=404, detail="job not found")
        return _job_dict(row)


@app.delete("/addon/v1/jobs/{job_id:path}")
async def cancel_job(job_id: str):
    if job_id in setup_tasks: setup_tasks[job_id].cancel(); return {"job_id": job_id, "cancel_requested": True}
    if not await jobs.cancel(job_id): raise HTTPException(status_code=409, detail="job cannot be canceled")
    return {"job_id": job_id, "cancel_requested": True}


@app.get("/addon/v1/assets")
async def list_assets(limit: int = 100, before: str | None = None, task: str | None = None):
    """新しい順に、要求されたぶんだけ返す。

    一覧は以前 limit だけで、画面側は 200 件を一度に取っていた。件数に比例して
    待ち時間が伸びるうえ、200 件を超えると超えたぶんが黙って出なくなる。
    続きの位置を返して、少しずつ取れるようにする。

    位置は created_at と id の組で持つ。created_at だけだと、同じ時刻の素材が
    あったときに境目で取りこぼす。種類での絞り込みは Job.task を見るので、
    画面側で読み込み済みのぶんだけ絞る形にならずに済む。
    """
    limit = min(max(limit, 1), 500)
    with session_factory() as session:
        query = session.query(Asset)
        if task:
            # 画面の「効果音」は audio. で始まる task をまとめて指す。前方一致で受ける。
            query = query.join(Job, Asset.job_id == Job.id).filter(
                Job.task.like(task.replace("%", "") + "%")
            )
        if before:
            created, _, marker = before.partition("|")
            try:
                moment = datetime.fromisoformat(created)
            except ValueError:
                raise HTTPException(status_code=422, detail={"code": "invalid_cursor"}) from None
            query = query.filter(
                or_(
                    Asset.created_at < moment,
                    and_(Asset.created_at == moment, Asset.id < marker),
                )
            )
        rows = query.order_by(Asset.created_at.desc(), Asset.id.desc()).limit(limit + 1).all()
        more = len(rows) > limit
        rows = rows[:limit]
        return {
            "assets": [_asset_dict(row) for row in rows],
            "next_before": f"{rows[-1].created_at.isoformat()}|{rows[-1].id}" if more and rows else None,
        }


@app.get("/addon/v1/assets/{asset_id}")
async def get_asset(asset_id: str):
    with session_factory() as session:
        row = session.get(Asset, asset_id)
        if row is None: raise HTTPException(status_code=404, detail="asset not found")
        provenance = session.get(Provenance, row.provenance_id); value = _asset_dict(row)
        value["provenance"] = {"operation": provenance.operation, "engine_id": provenance.engine_id, "engine_version": provenance.engine_version, "model_id": provenance.model_id, "model_revision": provenance.model_revision, "model_license_id": provenance.model_license_id, "parameters": provenance.parameters, "qa": provenance.qa} if provenance else None
        return value


@app.get("/addon/v1/assets/{asset_id}/content")
async def asset_content(asset_id: str):
    with session_factory() as session:
        row = session.get(Asset, asset_id)
        if row is None: raise HTTPException(status_code=404, detail="asset not found")
        target = (settings.data_dir / row.relative_path).resolve()
        if not target.is_relative_to(settings.data_dir.resolve()) or not target.is_file(): raise HTTPException(status_code=404, detail="asset content missing")
        return FileResponse(target, media_type=row.mime_type, filename=target.name)


@app.get("/addon/v1/voices")
async def list_voices():
    with session_factory() as session: return {"voices": [_voice_dict(row) for row in session.query(Voice).order_by(Voice.created_at.desc()).all()]}


@app.post("/addon/v1/voices")
async def create_voice(body: VoiceCreate, request: Request):
    if body.source_type in {"clone", "trained", "imported"} and not body.rights_confirmed: raise HTTPException(status_code=400, detail={"code": "voice_rights_confirmation_required", "message": "Voice rights confirmation is required"})
    recipe = dict(body.recipe); identity = await _host_identity(request)
    if body.source_type == "clone":
        # Reference audio recorded or picked in the browser is already here.
        upload_id = recipe.pop("reference_upload", None)
        if upload_id:
            try: source = uploads.resolve(settings, str(upload_id))
            except uploads.UploadError as exc: raise HTTPException(status_code=400, detail={"code": "invalid_upload", "message": str(exc)}) from exc
            voices_dir = settings.data_dir / "voices"; voices_dir.mkdir(parents=True, exist_ok=True)
            target = voices_dir / f"{uuid.uuid4().hex}.wav"; shutil.copyfile(source, target)
            recipe["reference_audio"] = str(target.relative_to(settings.data_dir))
        grant_id = recipe.pop("reference_grant", None)
        if grant_id:
            if identity is None: raise HTTPException(status_code=401, detail="ControlDeck grant requires Host authentication")
            staged = await _stage_read_grant(identity, str(grant_id), max_bytes=256 * 1024 * 1024, suffix=".wav"); voices_dir = settings.data_dir / "voices"; voices_dir.mkdir(parents=True, exist_ok=True); target = voices_dir / f"{uuid.uuid4().hex}{Path(staged).suffix or '.wav'}"; Path(staged).replace(target); recipe["reference_audio"] = str(target.relative_to(settings.data_dir))
    row = Voice(id=f"voice:{uuid.uuid4()}", name=body.name, source_type=body.source_type, languages=body.languages, engine_id=body.engine_id, recipe=recipe, rights_confirmed=body.rights_confirmed)
    with session_factory() as session: session.add(row); session.commit(); session.refresh(row)
    return _voice_dict(row)


@app.delete("/addon/v1/voices/{voice_id:path}")
async def delete_voice(voice_id: str):
    with session_factory() as session:
        row = session.get(Voice, voice_id)
        if row is None: raise HTTPException(status_code=404, detail="voice not found")
        reference = (row.recipe or {}).get("reference_audio")
        if isinstance(reference, str):
            target = (settings.data_dir / reference).resolve()
            if target.is_relative_to((settings.data_dir / "voices").resolve()): target.unlink(missing_ok=True)
        current = tts_models.preferences(session)
        if current["gpt_sovits_voice_id"] == voice_id:
            tts_models.set_preference(
                session,
                engine_id=current["engine_id"],
                model_id=current["gpt_sovits_model_id"],
                voice_id=None,
            )
        session.delete(row); session.commit()
    return {"deleted": True}


@app.post("/addon/v1/localization/batches")
async def create_localization_batch(body: LocalizationBatchCreate):
    batch = LocalizationBatch(id=f"loc:{uuid.uuid4()}", name=body.name, state="draft", profile=body.profile); seen: set[str] = set()
    for item in body.lines:
        if item.line_id in seen: raise HTTPException(status_code=400, detail=f"duplicate line_id: {item.line_id}")
        seen.add(item.line_id)
        if not item.ja_text and not item.en_text: raise HTTPException(status_code=400, detail=f"line {item.line_id} has no text")
        batch.lines.append(LocalizationLine(line_id=item.line_id, character=item.character, ja_text=item.ja_text, en_text=item.en_text, voice_id=item.voice_id, status="pending", qa={"state": "not_checked"}))
    with session_factory() as session: session.add(batch); session.commit(); count = len(batch.lines)
    return {"id": batch.id, "state": batch.state, "lines": count}


@app.get("/addon/v1/localization/batches/{batch_id:path}")
async def get_localization_batch(batch_id: str):
    with session_factory() as session:
        batch = session.query(LocalizationBatch).options(selectinload(LocalizationBatch.lines)).filter(LocalizationBatch.id == batch_id).one_or_none()
        if batch is None: raise HTTPException(status_code=404, detail="batch not found")
        return {"id": batch.id, "name": batch.name, "state": batch.state, "profile": batch.profile, "lines": [{"line_id": line.line_id, "character": line.character, "ja_text": line.ja_text, "en_text": line.en_text, "voice_id": line.voice_id, "status": line.status, "qa": line.qa, "outputs": line.outputs} for line in batch.lines]}


@app.websocket("/addon/v1/events")
async def event_stream(websocket: WebSocket):
    await websocket.accept()
    try:
        await websocket.send_json({"type": "hello", "service": "sonic-forge"})
        async for event in events.subscribe(): await websocket.send_json(event)
    except WebSocketDisconnect: return


def _workflow_body(task: str, value: dict[str, Any]) -> TaskRequest:
    body = dict(value); body["task"] = task; body.setdefault("input", {}); body.setdefault("profile", "default"); body.setdefault("quality", "balanced"); body.setdefault("content_language", "auto"); body.setdefault("output", {"format": "wav", "sample_rate": None, "channels": None}); body.setdefault("routing", {"engine": None, "model": None, "device": "auto"}); body.setdefault("seed", None); body.setdefault("project_output_grant", None); return TaskRequest.model_validate(body)


async def _run_task(
    body: TaskRequest,
    request: Request,
    *,
    detached_host_job: bool = False,
    wait: bool = False,
    gate: ProgressGate | None = None,
    progress_window: tuple[float, float] | None = None,
) -> dict[str, Any]:
    payload, hosted = await _prepare_task(request, body, detached_host_job=detached_host_job)
    if hosted is not None:
        if gate is not None:
            hosted.gate = gate
        if progress_window is not None:
            hosted.progress_offset, hosted.progress_span = progress_window
    job = jobs.create(payload, hosted=hosted)
    if not wait:
        return {"job_id": job.id, "host_job_id": hosted.host_job_id if hosted else None}
    finished = await jobs.wait(job.id)
    result: dict[str, Any] = {
        "job_id": job.id,
        "host_job_id": hosted.host_job_id if hosted else None,
        "state": finished.state if finished is not None else "unknown",
        "result": finished.result if finished is not None else None,
        "asset_id": (finished.result or {}).get("asset_id") if finished is not None and isinstance(finished.result, dict) else None,
    }
    if finished is not None and finished.error_code:
        result["error"] = {"code": finished.error_code, "message": finished.error_message}
    return result


async def _workflow_submit(
    task: str,
    request: Request,
    value: dict[str, Any] | None = None,
    *,
    detached_host_job: bool = False,
    wait: bool = False,
) -> dict[str, Any]:
    raw = value if value is not None else await request.json(); body = _workflow_body(task, raw if isinstance(raw, dict) else {})
    return await _run_task(body, request, detached_host_job=detached_host_job, wait=wait)


@app.post("/addon/v1/workflow/speech/synthesize")
async def workflow_tts(request: Request): return await _workflow_submit("speech.tts.synthesize", request)
@app.post("/addon/v1/workflow/speech/transcribe")
async def workflow_asr(request: Request): return await _workflow_submit("speech.asr.transcribe", request)
@app.post("/addon/v1/workflow/audio/generate")
async def workflow_audio(request: Request): return await _workflow_submit("audio.sfx.generate", request)
@app.post("/addon/v1/workflow/music/generate")
async def workflow_music(request: Request): return await _workflow_submit("music.generate", request)
@app.post("/addon/v1/agent/capabilities")
async def agent_capabilities(): return await capabilities()


# Agent 経路は終わるまで待って結果を返す。投げっぱなしにすると、呼び出し側は
# 状態を見るために何度も往復し、その往復ごとに Host は言語モデルを降ろして
# 載せ直し、会話の文脈を読み直す（実測で 40〜350 秒）。20 秒の音楽 1 曲に 30 回
# の確認が要っていた。
#
# Host job は切り離さず、agent tool の job へぶら下げる。進捗がそこへ流れる
# ことで、Host は「進んでいる」と分かる——Host が打ち切るのは進捗が止まった
# ときだけなので、長い生成もそのまま待てる（ControlDeck の
# wait_agent_tool_job）。
@app.post("/addon/v1/agent/generate")
async def agent_generate(request: Request):
    value = _agent_arguments(await request.json()); return await _workflow_submit(str(value.get("task") or "speech.tts.synthesize"), request, value, wait=True)
# batch で受ける task。生成だけを並べる。書き起こしは元の音があるかどうかで
# 話が変わるので sonic.transcribe に残し、ローカライズ一括は自前の入口を持つ。
BATCH_TASKS = frozenset({
    "speech.tts.synthesize",
    "audio.sfx.generate",
    "audio.ambience.generate",
    "music.generate",
})
# 1 コールで受ける件数の上限。MediaForge と揃える。
BATCH_MAX_ITEMS = 50


def _batch_bodies(value: object) -> list[TaskRequest]:
    """batch の中身を、1 件も走らせる前に全部読む。

    読めない指示を混ぜたまま半分だけ実行しない。走り出してからの失敗（資源が
    取れない、worker が落ちる）だけを件ごとに扱う。
    """
    value = _agent_arguments(value)
    items = value.get("items") if isinstance(value, dict) else None
    if not isinstance(items, list) or not items:
        raise HTTPException(status_code=422, detail={"code": "invalid_generation_batch", "message": "items must be a non-empty array"})
    if len(items) > BATCH_MAX_ITEMS:
        raise HTTPException(status_code=422, detail={"code": "too_many_items", "message": f"a batch accepts at most {BATCH_MAX_ITEMS} items"})
    bodies: list[TaskRequest] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise HTTPException(status_code=422, detail={"code": "invalid_generation_batch", "message": f"item {index} is not an object"})
        task = str(item.get("task") or "speech.tts.synthesize")
        if task not in BATCH_TASKS:
            raise HTTPException(status_code=422, detail={"code": "unsupported_task", "message": f"item {index}: {task} cannot be batched"})
        try:
            bodies.append(_workflow_body(task, item))
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail={"code": "invalid_generation_batch", "message": f"item {index}: {exc.errors()[0].get('msg', 'invalid item')}"}) from exc
    return bodies


@app.post("/addon/v1/agent/generate/batch")
async def agent_generate_batch(request: Request):
    """N 件を 1 コールで順に作る。

    1 件ずつ呼ぶと、その都度 Host は言語モデルを降ろして載せ直し、会話の文脈を
    丸ごと読み直す。実測では 12 万トークンの会話の読み直しに 6 分かかる一方、
    音声 1 本は 5.5 秒、効果音は 8.7 秒である。往復の回数そのものを減らすために
    この入口がある。

    走る順は 1 件ずつで変わらない。GPU も worker も 1 つなので、並べても速く
    ならない。並べれば 1 つの worker プロセスへ同時に書き込むことになる。

    時計での打ち切りは置かない。何件だろうと、生成が進んでいる限り進める。

    1 件の失敗で残りを捨てない。結果は件ごとに返し、全部か無かではないことを
    応答自身が名乗る。
    """
    bodies = _batch_bodies(await request.json())
    span = 1.0 / len(bodies)
    # 進捗の門は batch で 1 つにする。件ごとに作ると、前の件の最後の報告と次の件
    # の最初の報告が同じ 0.5 秒に入り、Host の間隔制限に掛かる。
    gate = ProgressGate()
    outcomes: list[dict[str, Any]] = []
    # batch の間は engine を降ろさない。抜けるときに、そのために抱えていたぶんは
    # keep_engines_warm 自身が降ろす——「終わった」と言う前に降ろす順序である。
    async with keep_engines_warm():
        for index, body in enumerate(bodies):
            try:
                finished = await _run_task(
                    body,
                    request,
                    wait=True,
                    gate=gate,
                    progress_window=(index * span, span),
                )
            except HTTPException as exc:
                detail = exc.detail if isinstance(exc.detail, dict) else {}
                outcomes.append({
                    "index": index,
                    "task": body.task,
                    "status": "failed",
                    "asset_id": None,
                    "error": {"code": str(detail.get("code") or "job_failed"), "message": str(detail.get("message") or "")[:500]},
                })
                continue
            state = str(finished.get("state") or "unknown")
            outcome: dict[str, Any] = {
                "index": index,
                "task": body.task,
                "status": state,
                "job_id": finished.get("job_id"),
                "asset_id": finished.get("asset_id"),
                "result": finished.get("result"),
            }
            if state != "succeeded":
                error = finished.get("error") or {}
                outcome["error"] = {"code": str(error.get("code") or "job_failed"), "message": str(error.get("message") or "")[:500]}
            outcomes.append(outcome)
    succeeded = sum(1 for item in outcomes if item["status"] == "succeeded")
    return {
        "items": outcomes,
        "succeeded_count": succeeded,
        "requested_count": len(bodies),
        "partial": succeeded != len(bodies),
        # 1 件ずつ独立した job である。全部か無かではない。
        "atomic": False,
    }


VOICE_METHODS = frozenset({"preset", "design", "clone"})


def _voice_summary(voice: Voice) -> dict[str, Any]:
    """agent へ返す声の姿。recipe の中身（file 経路など）は出さない。"""
    recipe = voice.recipe or {}
    method = str(recipe.get("method") or (
        "preset" if voice.source_type == "built-in" else
        "design" if recipe.get("design_instruction") else "clone"
    ))
    return {
        "voice_id": voice.id,
        "name": voice.name,
        "method": method,
        "languages": voice.languages or [],
        "speaker": recipe.get("speaker"),
        "description": recipe.get("design_instruction"),
        "anchored": bool(recipe.get("reference_audio")),
        # この声で出せる感情。preset は instruct に何でも書けるので空で、
        # design と clone は「持っている見本の分だけ」しか出せない。
        "emotion_choices": sorted(recipe.get("references") or {}),
        # 感情の指示（input.emotion）が効くかどうか。効き方は二通りある。
        #
        # preset は複製経路を通らないので言い方を自然文で書ける。感情を指定しても
        # 同じ人物のままであることは実測で確かめた（台詞を固定して指示だけ振り、
        # 耳で判定）。ここが崩れていたら、感情を指定した途端にキャラが別人になる。
        #
        # design と clone は複製経路を通り、そこは指示を受け付けない。代わりに
        # 感情別の見本を持たせてあり、そこから選ぶ形で効く。見本が平静の 1 本
        # しか無い声（感情別に作る前のもの、持ち込みの複製）は、指定しても何も
        # 起きないので効かないと言う。
        "supports_emotion": (
            voice.source_type == "built-in" or len(recipe.get("references") or {}) > 1
        ),
        "created_at": voice.created_at.isoformat() if voice.created_at else None,
    }


async def _store_voice_reference(source: Path, suffix: str = ".wav") -> str:
    """参照音声を SonicForge の持ち物にする。data_dir からの相対で返す。"""
    voices_dir = settings.data_dir / "voices"
    voices_dir.mkdir(parents=True, exist_ok=True)
    target = voices_dir / f"{uuid.uuid4().hex}{suffix or '.wav'}"
    shutil.copyfile(source, target)
    return str(target.relative_to(settings.data_dir))


def _save_voice(name: str, source_type: str, languages: list[str],
                recipe: dict[str, Any], *, rights_confirmed: bool) -> Voice:
    row = Voice(
        id=f"voice:{uuid.uuid4()}", name=name, source_type=source_type,
        languages=languages, engine_id=tts_models.QWEN_ENGINE,
        recipe=recipe, rights_confirmed=rights_confirmed,
    )
    with session_factory() as session:
        session.add(row)
        session.commit()
        session.refresh(row)
        session.expunge(row)
    return row


async def _create_voice(
    method: str, name: str, languages: list[str],
    value: dict[str, Any], request: Request, identity: HostIdentity | None,
) -> dict[str, Any]:
    if method == "preset":
        speaker = str(value.get("speaker") or "")
        if speaker not in voice_catalog.SPEAKER_NAMES:
            raise HTTPException(status_code=422, detail={
                "code": "unknown_speaker",
                "message": "speaker は sonic.voice.list の built_in_speakers から選びます",
            })
        row = _save_voice(name, "built-in", languages,
                          {"method": "preset", "speaker": speaker}, rights_confirmed=False)
        return _voice_summary(row)

    if method == "clone":
        if not bool(value.get("rights_confirmed")):
            raise HTTPException(status_code=422, detail={
                "code": "voice_rights_confirmation_required",
                "message": "人の声を複製するには rights_confirmed が要ります",
            })
        reference_text = str(value.get("reference_text") or "").strip()
        if not reference_text:
            raise HTTPException(status_code=422, detail={
                "code": "reference_text_required",
                "message": "参照音声の書き起こしが要ります。無いと声質が落ちます",
            })
        grant_id = value.get("reference_grant")
        upload_id = value.get("upload_id")
        if grant_id:
            if identity is None:
                raise HTTPException(status_code=401, detail={"code": "host_authentication_required"})
            staged = await _stage_read_grant(
                identity, str(grant_id), max_bytes=256 * 1024 * 1024, suffix=".wav")
            stored = await _store_voice_reference(Path(staged), Path(staged).suffix)
            Path(staged).unlink(missing_ok=True)
        elif upload_id:
            try:
                source = uploads.resolve(settings, str(upload_id))
            except uploads.UploadError as exc:
                raise HTTPException(status_code=400, detail={"code": "invalid_upload"}) from exc
            stored = await _store_voice_reference(Path(source))
        else:
            raise HTTPException(status_code=422, detail={
                "code": "reference_audio_required",
                "message": "reference_grant か upload_id で参照音声を渡します",
            })
        row = _save_voice(name, "clone", languages, {
            "method": "clone", "reference_audio": stored,
            "reference_text": reference_text, "rights_basis": "user_confirmed",
        }, rights_confirmed=True)
        return _voice_summary(row)

    description = str(value.get("description") or "").strip()
    if not description:
        raise HTTPException(status_code=422, detail={
            "code": "description_required",
            "message": "design には声の説明（性別・年齢・声質・訛りなど）が要ります",
        })
    language = languages[0] if languages else None
    emotions = _resolve_emotions(value.get("emotions"))
    sample_text = str(value.get("sample_text") or "").strip() or voice_catalog.emotion_anchor_text(
        language, "neutral")
    sample_texts = [
        sample_text if label == "neutral" else voice_catalog.emotion_anchor_text(language, label)
        for label in emotions
    ]
    # 注文どおりの声で、感情別の見本をまとめて喋らせる。**1 回の呼び出しで作る**の
    # が肝心で、design は呼び直すと別人になるため、感情ごとに呼び分けると感情ごとに
    # 別のキャラができる。この見本が以後の identity になる。
    # 見本文は下書きの声に載せて運ぶ。`_internal_*` は外から渡せない決まりで、
    # ここは外向きの入口と同じ検証を通るためである。
    draft = _save_voice(name, "design", languages, {
        "method": "design", "design_instruction": description,
        "sample_texts": sample_texts,
    }, rights_confirmed=False)
    try:
        finished = await _run_task(
            _workflow_body("speech.tts.synthesize", {
                "input": {"text": sample_text, "voice_id": draft.id},
                "content_language": languages[0] if languages else "auto",
            }),
            request, wait=True,
        )
    except HTTPException:
        _drop_voice(draft.id)
        raise
    if finished.get("state") != "succeeded" or not finished.get("asset_id"):
        _drop_voice(draft.id)
        error = finished.get("error") or {}
        raise HTTPException(status_code=502, detail={
            "code": str(error.get("code") or "voice_design_failed"),
            "message": str(error.get("message") or "声を作れませんでした")[:300],
        })
    with session_factory() as session:
        asset = session.get(Asset, str(finished["asset_id"]))
        if asset is None:
            _drop_voice(draft.id)
            raise HTTPException(status_code=502, detail={"code": "voice_sample_missing"})
        sample_path = (settings.data_dir / asset.relative_path).resolve()
        segments = list((asset.metadata_json or {}).get("segments") or [])
    # 見本は 1 本に繋がって返る（仕事の出力は 1 ファイルという約束のため）。
    # どこで切るかは worker が標本位置で添えてくるので、無音を探さずに切れる。
    try:
        cuts = _split_wav(sample_path, segments) if len(segments) > 1 else [sample_path]
    except Exception:
        _drop_voice(draft.id)
        raise HTTPException(status_code=502, detail={"code": "voice_sample_unreadable"})
    references: dict[str, dict[str, str]] = {}
    for label, piece, spoken in zip(emotions, cuts, sample_texts):
        references[label] = {
            "audio": await _store_voice_reference(piece),
            "text": spoken,
        }
        if piece != sample_path:
            piece.unlink(missing_ok=True)
    # 見本が取れたので、以後は複製で回す。design を呼び直さない——同じ注文文でも
    # 同じ声が出る保証が無いため、呼び直した時点で別人になりうる。
    with session_factory() as session:
        row = session.get(Voice, draft.id)
        row.source_type = "clone"
        row.rights_confirmed = True
        row.recipe = {
            "method": "design",
            "design_instruction": description,
            # 単一の参照しか見ない古い経路のために、平静の見本を今までの場所にも置く。
            "reference_audio": references["neutral"]["audio"],
            "reference_text": references["neutral"]["text"],
            "references": references,
            # 参照はこちらが作った音で、実在の人の声ではない。何を根拠に
            # 複製してよいと判じたかを残す。
            "rights_basis": "synthetic",
        }
        session.commit()
        session.refresh(row)
        session.expunge(row)
    return {**_voice_summary(row), "sample_asset_id": finished["asset_id"]}


def _resolve_emotions(requested: Any) -> list[str]:
    """どの感情の見本を作るかを決める。

    neutral は必ず入れる——identity の基準であり、当たらなかった指定の落とし先
    でもある。知らない名前は受け流さずに断る。見本は 1 回の呼び出しでまとめて
    作るのであとから足せず、黙って平静で作ると、使う側は「怒りの見本がある」と
    思ったまま進んでしまう。
    """
    if requested is None:
        return list(voice_catalog.EMOTIONS)
    if not isinstance(requested, list) or not requested:
        raise HTTPException(status_code=422, detail={
            "code": "invalid_emotions",
            "message": f"emotions は {', '.join(voice_catalog.EMOTIONS)} から選びます",
        })
    unknown = [item for item in requested if item not in voice_catalog.EMOTIONS]
    if unknown:
        raise HTTPException(status_code=422, detail={
            "code": "invalid_emotions",
            "message": f"知らない感情です: {', '.join(str(item) for item in unknown)}",
        })
    return ["neutral"] + [item for item in requested if item != "neutral"]


def _split_wav(source: Path, segments: list[dict]) -> list[Path]:
    """繋がった見本を、worker が添えた切れ目で切り分ける。

    無音を探して切る作りにはしない。探すとずれ、ずれると書き起こしと音が食い
    違って複製の質が落ちる。切れ目は作った側が正確に知っている。
    """
    import wave

    pieces: list[Path] = []
    with wave.open(str(source), "rb") as handle:
        params = handle.getparams()
        frames = handle.readframes(params.nframes)
    width = params.sampwidth * params.nchannels
    for index, segment in enumerate(segments):
        start = int(segment.get("start") or 0)
        end = int(segment.get("end") or 0)
        if end <= start:
            raise ValueError("segment boundaries are not usable")
        target = source.parent / f"{source.stem}.part{index}.wav"
        with wave.open(str(target), "wb") as out:
            out.setparams(params)
            out.writeframes(frames[start * width:end * width])
        pieces.append(target)
    return pieces


def _drop_voice(voice_id: str) -> None:
    with session_factory() as session:
        row = session.get(Voice, voice_id)
        if row is not None:
            session.delete(row)
            session.commit()


@app.post("/addon/v1/agent/voice/list")
async def agent_voice_list(request: Request):
    """作った声と、選べる内蔵話者を返す。

    内蔵話者も返すのは、`preset` を選ぶのに名前を知っている必要があるからで
    ある。名前を知らないまま `speaker` を書かせると、当たるまで試すことになる。
    """
    del request
    with session_factory() as session:
        rows = session.query(Voice).order_by(Voice.created_at.desc()).all()
        voices = [_voice_summary(row) for row in rows]
    return {
        "voices": voices,
        "built_in_speakers": voice_catalog.catalog(),
        "built_in_speakers_note": voice_catalog.NON_NATIVE_NOTE,
        "languages": list(voice_catalog.SUPPORTED_LANGUAGES),
    }


@app.post("/addon/v1/agent/voice/delete")
async def agent_voice_delete(request: Request):
    value = _agent_arguments(await request.json())
    voice_id = str(value.get("voice_id") or "")
    with session_factory() as session:
        row = session.get(Voice, voice_id)
        if row is None:
            raise HTTPException(status_code=404, detail={"code": "voice_not_found"})
        reference = (row.recipe or {}).get("reference_audio")
        session.delete(row)
        session.commit()
    if isinstance(reference, str):
        target = (settings.data_dir / reference).resolve()
        if target.is_relative_to((settings.data_dir / "voices").resolve()):
            target.unlink(missing_ok=True)
    return {"voice_id": voice_id, "deleted": True}


@app.post("/addon/v1/agent/voice/create")
async def agent_voice_create(request: Request):
    """キャラクターの声を作る。以後その声で喋らせる。

    `design` は自然文で声を注文できるが、Qwen3-TTS の voice design には**再現性の
    保証が無く seed も無い**。同じ注文文で呼び直しても同じ声が出るとは限らない。
    そこで、注文した声をその場で一度喋らせて見本を掴み、以後はその見本からの
    複製（voice clone）で回す。identity は見本の波形そのものになる。

    この作りは品質の上でも良い。clone は参照音声と書き起こしが合っているほど
    良く、書き起こしを省くと品質が落ちると公式が書いている。こちらが喋らせた
    見本なら書き起こしが完全に一致する。
    """
    identity = await _host_identity(request)
    value = _agent_arguments(await request.json())
    method = str(value.get("method") or "")
    if method not in VOICE_METHODS:
        raise HTTPException(status_code=422, detail={
            "code": "invalid_voice_method",
            "message": f"method は {', '.join(sorted(VOICE_METHODS))} のいずれかです",
        })
    name = str(value.get("name") or "").strip()
    if not name or len(name) > 120:
        raise HTTPException(status_code=422, detail={"code": "invalid_voice_name"})
    languages = value.get("languages") or ["ja"]
    if not isinstance(languages, list) or not all(
        isinstance(item, str) and item in voice_catalog.SUPPORTED_LANGUAGES for item in languages
    ):
        raise HTTPException(status_code=422, detail={
            "code": "unsupported_language",
            "message": f"languages は {', '.join(voice_catalog.SUPPORTED_LANGUAGES)} から選びます",
        })
    return await _create_voice(method, name, languages, value, request, identity)


@app.post("/addon/v1/agent/transcribe")
async def agent_transcribe(request: Request):
    value = _agent_arguments(await request.json()); return await _workflow_submit("speech.asr.transcribe", request, value, wait=True)


@app.post("/addon/v1/agent/inspect")
async def agent_inspect(request: Request):
    value = _agent_arguments(await request.json())
    job_id = value.get("job_id")
    if isinstance(job_id, str) and job_id:
        return await get_job(job_id)
    return await get_asset(str(value.get("asset_id") or ""))


@app.post("/addon/v1/agent/pack")
async def agent_pack(request: Request):
    value = _agent_arguments(await request.json()); asset_id = str(value.get("asset_id") or ""); grant_id = str(value.get("project_output_grant") or value.get("grant_id") or value.get("output_grant") or ""); identity = await _host_identity(request)
    if identity is None: raise HTTPException(status_code=401, detail="ControlDeck Host authentication is required")
    with session_factory() as session:
        asset = session.get(Asset, asset_id)
        if asset is None: raise HTTPException(status_code=404, detail="asset not found")
        source = (settings.data_dir / asset.relative_path).resolve()
        if not source.is_relative_to(settings.data_dir.resolve()) or not source.is_file(): raise HTTPException(status_code=404, detail="asset content missing")
    created = await host_client.create_or_attach_job(identity, title="SonicForge asset placement"); identity = await host_client.identity_from_job_response(identity, created); host_job_id = (created.get("job") or {}).get("id")
    if not isinstance(host_job_id, str) or not host_job_id: raise HTTPException(status_code=502, detail="ControlDeck did not return a Host Job")
    from .host.files import commit_file
    result = await commit_file(host_client, identity, host_job_id=host_job_id, grant_id=grant_id, source=source, filename=str(value.get("filename") or source.name), mime_type=asset.mime_type, sha256=asset.sha256)
    await host_client.update_job(identity, host_job_id, {"phase": "complete", "status": "succeeded", "result": {"asset_id": asset_id}})
    return {"asset_id": asset_id, "output": result}


@app.post("/addon/v1/commands/create")
async def command_create(): return {"route": "/x/sonic-forge/workspace", "task": "choose"}
@app.post("/addon/v1/context/transcribe-audio")
async def context_transcribe(request: Request):
    value = await request.json(); body = _workflow_body("speech.asr.transcribe", {"input": {"audio_grant": value.get("grant_id")}, "content_language": value.get("content_language", "auto")}); payload, hosted = await _prepare_task(request, body); job = jobs.create(payload, hosted=hosted); return {"job_id": job.id, "host_job_id": hosted.host_job_id if hosted else None}
@app.post("/addon/v1/context/open-audio")
async def context_open_audio(): return {"route": "/x/sonic-forge/workspace", "task": "library"}


@app.exception_handler(HostApiError)
async def host_error_handler(_request: Request, exc: HostApiError): return JSONResponse(status_code=exc.status_code, content={"error": {"code": exc.code, "message": str(exc)}})

frontend = settings.repo_root / "frontend"; schemas_dir = settings.repo_root / "schemas"
BASE_MARKER = "<!-- SONIC_FORGE_BASE -->"


def _inlined_frontend(entry: str) -> str:
    """Return a self-contained initial document for the opaque Host iframe.

    ControlDeck intentionally gives embedded Add-ons an opaque origin. As a
    result, initial external stylesheet/script requests cannot depend on the
    frame bootstrap cookie. Keep the first document self-contained, following
    the established MediaForge integration pattern; subsequent API and socket
    traffic is authenticated with the Browser Bridge session nonce.
    """
    document = (frontend / entry).read_text(encoding="utf-8")
    styles = (frontend / "styles.css").read_text(encoding="utf-8")
    application = (frontend / "app.js").read_text(encoding="utf-8")
    localization = (frontend / "localization.js").read_text(encoding="utf-8")
    if "</style" in styles.lower() or "</script" in application.lower() or "</script" in localization.lower():
        raise RuntimeError("frontend assets contain an unsafe inline closing tag")
    replacements = {
        '<link rel="stylesheet" href="styles.css">': f"<style>\n{styles}\n</style>",
        '<script src="app.js"></script>': f"<script>\n{application}\n</script>",
        '<script src="localization.js"></script>': f"<script>\n{localization}\n</script>",
    }
    for marker, content in replacements.items():
        if document.count(marker) != 1:
            raise RuntimeError(f"frontend entry point has an unexpected marker count: {marker}")
        document = document.replace(marker, content)
    return document


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def embedded_workspace() -> HTMLResponse:
    return HTMLResponse(_inlined_frontend("index.html").replace(BASE_MARKER, "", 1))


@app.get("/settings/", response_class=HTMLResponse, include_in_schema=False)
async def embedded_settings() -> HTMLResponse:
    """Serve the same workspace shell, opened on the settings view.

    The settings entry point used to be a second hand-maintained copy of the
    shell, which drifted from the workspace whenever a view was added. It is
    the same application; only the entry view and the relative base differ.
    """
    document = _inlined_frontend("index.html")
    document = document.replace(BASE_MARKER, '<base href="../">', 1)
    return HTMLResponse(
        document.replace('data-start-view="studio"', 'data-start-view="settings"', 1)
    )


if schemas_dir.is_dir(): app.mount("/schemas", StaticFiles(directory=schemas_dir), name="schemas")
if frontend.is_dir(): app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
