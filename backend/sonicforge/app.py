from __future__ import annotations

import asyncio
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import selectinload

from .capabilities import capability_document
from .config import ensure_directories, load_settings
from .db import Asset, Job, LocalizationBatch, LocalizationLine, Provenance, Voice, make_session_factory
from .events import EventBus
from .host.client import ControlDeckHostClient, HostApiError, HostIdentity
from .host.files import read_grant
from .jobs import HostedExecution, JobManager
from .schemas import LocalizationBatchCreate, SetupApplyRequest, SetupCredentials, TaskRequest, VoiceCreate
from . import uploads
from . import setup as setup_service
from . import __version__

settings = load_settings()
ensure_directories(settings)
session_factory = make_session_factory(settings)
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
        hosted = HostedExecution(identity=identity, host_job_id=host_job_id); inp = payload.setdefault("input", {})
        if body.task == "speech.asr.transcribe":
            grant_id = inp.get("audio_grant") or inp.get("grant_id")
            if grant_id: inp["_internal_staged_input"] = await _stage_read_grant(identity, str(grant_id), max_bytes=1024 * 1024 * 1024, suffix=".wav")
        reference_grant = inp.get("reference_grant")
        if reference_grant: inp["_internal_reference_audio"] = await _stage_read_grant(identity, str(reference_grant), max_bytes=256 * 1024 * 1024, suffix=".wav")
    return payload, hosted


def _health_item(component: dict[str, Any]) -> dict[str, Any]:
    state = str(component.get("state") or "missing")
    mapped = "ok" if state == "available" else "checking" if state == "installing" else "error" if state == "error" else "missing"
    labels = {"core": "SonicForge core", "speech-essentials": "Speech Essentials", "game-audio": "Game Audio", "music": "Music"}
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
    yield
    for task in list(setup_tasks.values()): task.cancel()
    if setup_tasks: await asyncio.gather(*setup_tasks.values(), return_exceptions=True)
    await jobs.shutdown()
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
async def list_assets(limit: int = 100):
    limit = min(max(limit, 1), 500)
    with session_factory() as session: return {"assets": [_asset_dict(row) for row in session.query(Asset).order_by(Asset.created_at.desc()).limit(limit).all()]}


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


async def _workflow_submit(
    task: str,
    request: Request,
    value: dict[str, Any] | None = None,
    *,
    detached_host_job: bool = False,
) -> dict[str, Any]:
    raw = value if value is not None else await request.json(); body = _workflow_body(task, raw if isinstance(raw, dict) else {}); payload, hosted = await _prepare_task(request, body, detached_host_job=detached_host_job); job = jobs.create(payload, hosted=hosted); return {"job_id": job.id, "host_job_id": hosted.host_job_id if hosted else None}


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


@app.post("/addon/v1/agent/generate")
async def agent_generate(request: Request):
    value = _agent_arguments(await request.json()); return await _workflow_submit(str(value.get("task") or "speech.tts.synthesize"), request, value, detached_host_job=True)
@app.post("/addon/v1/agent/transcribe")
async def agent_transcribe(request: Request):
    value = _agent_arguments(await request.json()); return await _workflow_submit("speech.asr.transcribe", request, value, detached_host_job=True)


@app.post("/addon/v1/agent/inspect")
async def agent_inspect(request: Request):
    value = _agent_arguments(await request.json()); return await get_asset(str(value.get("asset_id") or ""))


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
