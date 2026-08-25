from __future__ import annotations

import asyncio
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .audio import inspect_wav
from .config import Settings
from .db import Asset, Job, Provenance, Voice
from .events import EventBus
from .host.client import ControlDeckHostClient, HostApiError, HostIdentity
from .host.files import commit_file
from .workers import WorkerError, execute, route


@dataclass
class HostedExecution:
    identity: HostIdentity
    host_job_id: str
    resource_request_id: str | None = None
    lease_id: str | None = None
    last_host_progress_at: float = 0.0
    last_host_progress: float = 0.0


class JobManager:
    def __init__(self, settings: Settings, session_factory, events: EventBus, *, host_client: ControlDeckHostClient | None = None):
        self.settings=settings; self.session_factory=session_factory; self.events=events; self.host_client=host_client
        self.tasks: dict[str, asyncio.Task] = {}; self.hosted: dict[str, HostedExecution] = {}; self.process_lock=asyncio.Semaphore(1)

    def create(self, request: dict, *, hosted: HostedExecution | None = None) -> Job:
        job=Job(id=f"job:{uuid.uuid4()}",task=request["task"],state="queued",request=request)
        with self.session_factory() as session: session.add(job); session.commit(); session.refresh(job)
        if hosted is not None: self.hosted[job.id]=hosted
        self.tasks[job.id]=asyncio.create_task(self._run(job.id),name=f"sonicforge-job-{job.id}")
        return job

    async def cancel(self, job_id: str) -> bool:
        with self.session_factory() as session:
            job=session.get(Job,job_id)
            if not job or job.state in {"succeeded","failed","canceled"}: return False
            job.cancel_requested=True
            if job.state=="queued":
                job.state="canceled"; session.commit(); task=self.tasks.get(job_id)
                if task: task.cancel()
                await self.events.publish({"type":"job","job_id":job_id,"state":"canceled"}); return True
            session.commit()
        execution=self.hosted.get(job_id)
        if execution and self.host_client and execution.resource_request_id and not execution.lease_id:
            try: await self.host_client.cancel_resource(execution.identity,execution.resource_request_id)
            except HostApiError: pass
        task=self.tasks.get(job_id)
        if task: task.cancel()
        return True

    async def _set(self, job_id: str, **values) -> None:
        with self.session_factory() as session:
            job=session.get(Job,job_id)
            if not job: return
            for key,value in values.items(): setattr(job,key,value)
            session.commit()
        await self.events.publish({"type":"job","job_id":job_id,**values}); await self._report_host(job_id,values)

    async def _report_host(self, job_id: str, values: dict[str,Any]) -> None:
        execution=self.hosted.get(job_id)
        if execution is None or self.host_client is None: return
        progress=float(values.get("progress",execution.last_host_progress)); now=time.monotonic(); state=values.get("state"); terminal=state in {"succeeded","failed","canceled"}
        if not terminal and now-execution.last_host_progress_at<0.65: return
        progress=max(progress,execution.last_host_progress)
        payload:dict[str,Any]={"phase":self._phase(values,state),"progress":{"completed":round(progress*1000),"total":1000}}
        result=values.get("result"); message=result.get("message") if isinstance(result,dict) else None
        if message: payload["message"]=str(message)[:300]
        if terminal:
            payload["status"]={"succeeded":"succeeded","failed":"failed","canceled":"canceled"}[str(state)]
            if state=="succeeded":
                bounded={}
                if isinstance(result,dict):
                    for key in ("asset_id","language","text","segments","output"):
                        if key in result: bounded[key]=result[key]
                payload["result"]=bounded
            elif values.get("error_message"): payload["error"]=str(values["error_message"])[:2000]
        try: await self.host_client.update_job(execution.identity,execution.host_job_id,payload)
        except HostApiError as exc:
            if exc.status_code not in {409,429}: raise
        execution.last_host_progress=progress; execution.last_host_progress_at=now

    @staticmethod
    def _phase(values:dict[str,Any],state:Any)->str:
        if state=="queued": return "queued"
        if state=="succeeded": return "complete"
        if state in {"failed","canceled"}: return str(state)
        return "generating" if isinstance(values.get("result"),dict) and values["result"].get("message") else "running"

    def _resource_estimate(self,request:dict,host_job_id:str)->dict[str,Any]:
        task=request["task"]
        if task=="speech.tts.synthesize": peak=8*1024**3; runtime=120; residency="sonicforge:qwen3-tts"
        elif task=="speech.asr.transcribe": peak=5*1024**3; runtime=180; residency="sonicforge:whisper"
        elif task.startswith("audio."): peak=4*1024**3; runtime=180; residency="sonicforge:stable-audio-3"
        else: peak=18*1024**3; runtime=300; residency="sonicforge:ace-step-1.5"
        return {"job_id":host_job_id,"device":request.get("routing",{}).get("device") or "auto","vram":{"resident_bytes":0,"execution_peak_bytes":peak,"cold_load_peak_bytes":peak,"headroom_bytes":512*1024**2,"confidence":"low"},"compute_mode":"exclusive-preferred","priority":20,"class":"interactive","residency_key":residency,"estimated_runtime_sec":runtime,"max_wait_sec":300,"on_insufficient":"queue"}

    def _gpu_required(self,request:dict)->bool:
        if self.settings.enable_fake_worker or request.get("routing",{}).get("engine")=="fake": return False
        try: _engine,python,_script=route(self.settings,request["task"],request.get("content_language","auto"),request.get("routing",{}).get("engine"))
        except WorkerError: return False
        return "rocm" in str(python).lower()

    async def _watch_host_cancel(self,job_id:str,execution:HostedExecution)->None:
        if self.host_client is None: return
        while True:
            await asyncio.sleep(1.0)
            try: control=await self.host_client.job_control(execution.identity,execution.host_job_id)
            except HostApiError as exc:
                if exc.status_code in {401,403,409}: return
                continue
            if control.get("cancel_requested") or control.get("status")=="canceled":
                task=self.tasks.get(job_id)
                if task and not task.done(): task.cancel()
                return

    async def _acquire_resource(self,job_id:str,request:dict,execution:HostedExecution)->asyncio.Task|None:
        if not self._gpu_required(request): return None
        if self.host_client is None: raise WorkerError("ControlDeck Resource Broker is not configured")
        if "resources.acquire" not in execution.identity.granted_capabilities: raise WorkerError("ControlDeck resources.acquire capability is required for GPU work")
        status=await self.host_client.request_resource(execution.identity,self._resource_estimate(request,execution.host_job_id)); request_id=status.get("request_id")
        if not isinstance(request_id,str): raise WorkerError("ControlDeck did not return a resource request ID")
        execution.resource_request_id=request_id
        while True:
            if status.get("state")=="granted":
                lease_id=status.get("lease_id")
                if not isinstance(lease_id,str): raise WorkerError("ControlDeck granted resource without a lease ID")
                execution.lease_id=lease_id; await self.host_client.lease_action(execution.identity,lease_id,"activate"); return asyncio.create_task(self._renew_lease(execution),name=f"sonicforge-lease-{job_id}")
            if status.get("state") in {"rejected","canceled","expired"}: raise WorkerError(f"GPU resource request ended: {status.get('state')}")
            await self._set(job_id,progress=0.02,result={"message":f"Waiting for GPU: {status.get('reason') or 'queue'}"}); await asyncio.sleep(1.0); status=await self.host_client.resource_status(execution.identity,request_id)

    async def _renew_lease(self,execution:HostedExecution)->None:
        assert self.host_client is not None
        while execution.lease_id:
            await asyncio.sleep(10)
            try:
                if execution.identity.expires_at-int(time.time())<120: execution.identity=await self.host_client.refresh_lease_identity(execution.identity,execution.lease_id)
                await self.host_client.lease_action(execution.identity,execution.lease_id,"renew")
            except HostApiError: return

    async def _release_resource(self,execution:HostedExecution)->None:
        if self.host_client is None: return
        if execution.lease_id:
            try: await self.host_client.lease_action(execution.identity,execution.lease_id,"release")
            except HostApiError: pass
            execution.lease_id=None
        elif execution.resource_request_id:
            try: await self.host_client.cancel_resource(execution.identity,execution.resource_request_id)
            except HostApiError: pass

    async def _run(self,job_id:str)->None:
        await self._set(job_id,state="running",progress=0.01)
        with self.session_factory() as session:
            job=session.get(Job,job_id); request=dict(job.request); inp=dict(request.get("input") or {}); voice_id=inp.get("voice_id")
            if isinstance(voice_id,str) and voice_id.startswith("voice:"):
                voice=session.get(Voice,voice_id)
                if voice is None: raise WorkerError("Selected logical voice does not exist")
                recipe=dict(voice.recipe or {}); reference=recipe.get("reference_audio")
                if isinstance(reference,str):
                    candidate=(self.settings.data_dir/reference).resolve(); voices_root=(self.settings.data_dir/"voices").resolve()
                    if not candidate.is_relative_to(voices_root) or not candidate.is_file(): raise WorkerError("Voice reference audio is missing or outside SonicForge storage")
                    recipe["reference_audio"]=str(candidate)
                inp["_internal_voice"]={"id":voice.id,"name":voice.name,"source_type":voice.source_type,"languages":voice.languages or [],"engine_id":voice.engine_id,"recipe":recipe,"rights_confirmed":bool(voice.rights_confirmed)}; request["input"]=inp
        work_dir=self.settings.data_dir/"tmp"/job_id.replace(":","_"); execution=self.hosted.get(job_id); lease_renew:asyncio.Task|None=None; control_watch:asyncio.Task|None=None
        async def progress(value:float,message:str): await self._set(job_id,progress=max(0.0,min(0.98,value)),result={"message":message})
        try:
            if execution is not None: control_watch=asyncio.create_task(self._watch_host_cancel(job_id,execution),name=f"sonicforge-host-control-{job_id}")
            if self._gpu_required(request) and execution is None: raise WorkerError("GPU work requires a ControlDeck-managed Host Job and Resource Broker lease")
            if execution is not None: lease_renew=await self._acquire_resource(job_id,request,execution)
            async with self.process_lock: result=await execute(self.settings,request,work_dir,progress)
            output_asset=None; output_commit=None
            if result.output_path:
                meta=inspect_wav(result.output_path); prov_id=f"prov:{uuid.uuid4()}"; asset_id=f"asset:{uuid.uuid4()}"; target=self.settings.assets_dir/f"{asset_id.split(':',1)[1]}.wav"; target.parent.mkdir(parents=True,exist_ok=True); shutil.move(str(result.output_path),target); relative=str(target.relative_to(self.settings.data_dir))
                with self.session_factory() as session:
                    provenance=Provenance(id=prov_id,operation=request["task"],engine_id=result.engine_id,engine_version=result.engine_version,model_id=result.model_id,model_revision=result.model_revision,model_license_id=result.model_license_id,parameters={"profile":request.get("profile"),"quality":request.get("quality"),"content_language":request.get("content_language"),"seed":request.get("seed")},qa=meta["qa"])
                    asset=Asset(id=asset_id,kind="audio",mime_type=meta["mime_type"],relative_path=relative,size_bytes=meta["size_bytes"],sha256=meta["sha256"],duration_ms=meta["duration_ms"],sample_rate=meta["sample_rate"],channels=meta["channels"],job_id=job_id,provenance_id=prov_id,metadata_json=result.payload); session.add_all([provenance,asset]); session.commit()
                output_asset=asset_id; grant_id=request.get("project_output_grant")
                if grant_id:
                    if execution is None or self.host_client is None: raise WorkerError("project output grants require a ControlDeck-managed execution")
                    output_commit=await commit_file(self.host_client,execution.identity,host_job_id=execution.host_job_id,grant_id=str(grant_id),source=target,filename=str(result.payload.get("filename") or target.name),mime_type=meta["mime_type"],sha256=meta["sha256"])
            final_result={"asset_id":output_asset,**result.payload}
            if output_commit is not None: final_result["output"]=output_commit
            await self._set(job_id,state="succeeded",progress=1.0,result=final_result)
        except asyncio.CancelledError: await self._set(job_id,state="canceled",progress=1.0,error_code="canceled",error_message="Canceled")
        except WorkerError as exc: await self._set(job_id,state="failed",progress=1.0,error_code="worker_failed",error_message=str(exc)[:500])
        except HostApiError as exc: await self._set(job_id,state="failed",progress=1.0,error_code=exc.code,error_message=str(exc)[:500])
        except Exception as exc: await self._set(job_id,state="failed",progress=1.0,error_code="internal_error",error_message=str(exc)[:500])
        finally:
            for task in (lease_renew,control_watch):
                if task is not None: task.cancel()
            await asyncio.gather(*[task for task in (lease_renew,control_watch) if task is not None],return_exceptions=True)
            if execution is not None: await self._release_resource(execution)
            inp=request.get("input",{}) if "request" in locals() else {}
            for key in ("_internal_staged_input","_internal_reference_audio"):
                staged=inp.get(key)
                if staged:
                    try: Path(staged).unlink(missing_ok=True)
                    except OSError: pass
            shutil.rmtree(work_dir,ignore_errors=True); self.tasks.pop(job_id,None); self.hosted.pop(job_id,None)
