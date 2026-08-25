from __future__ import annotations
import json, os, shutil, sys
from pathlib import Path
payload=json.loads(sys.stdin.readline()); request=payload['request']; work=Path(payload['work_dir']); work.mkdir(parents=True,exist_ok=True)
print(json.dumps({'type':'progress','progress':0.05,'message':'Loading ACE-Step'}),flush=True)
try:
    from acestep.handler import AceStepHandler
    from acestep.llm_inference import LLMHandler
    from acestep.inference import GenerationParams, GenerationConfig, generate_music
    root=os.environ.get('SONICFORGE_ACESTEP_ROOT') or str(Path(__file__).resolve().parents[2]/'vendor/ACE-Step-1.5')
    checkpoints=os.environ.get('SONICFORGE_ACESTEP_CHECKPOINTS') or str(Path.home()/'.cache/ace-step/checkpoints')
    device='cuda' if os.environ.get('SONICFORGE_MUSIC_DEVICE','auto')!='cpu' else 'cpu'
    dit=AceStepHandler(); dit.initialize_service(project_root=root,config_path=os.environ.get('SONICFORGE_ACESTEP_DIT','acestep-v15-turbo'),device=device)
    llm=LLMHandler(); llm.initialize(checkpoint_dir=checkpoints,lm_model_path=os.environ.get('SONICFORGE_ACESTEP_LM','acestep-5Hz-lm-0.6B'),backend=os.environ.get('SONICFORGE_ACESTEP_LM_BACKEND','pt'),device=device)
    inp=request.get('input',{}); caption=inp.get('prompt') or inp.get('description') or ''
    params=GenerationParams(caption=caption,instrumental=bool(inp.get('instrumental',True)),bpm=inp.get('bpm'),duration=float(inp.get('duration_sec') or 30),seed=request.get('seed') if request.get('seed') is not None else -1,shift=3.0)
    config=GenerationConfig(batch_size=1,audio_format='wav')
    print(json.dumps({'type':'progress','progress':0.45,'message':'Generating music'}),flush=True)
    result=generate_music(dit,llm,params,config,save_dir=str(work))
    if not result.success or not result.audios: raise RuntimeError(result.error or 'ACE-Step returned no audio')
    src=Path(result.audios[0]['path']); out=work/'output.wav';
    if src.resolve()!=out.resolve(): shutil.copy2(src,out)
    print(json.dumps({'type':'result','engine_id':'music.ace-step-1.5','engine_version':'1.5.0','model_id':os.environ.get('SONICFORGE_ACESTEP_DIT','acestep-v15-turbo'),'model_license_id':'MIT/review-model-terms','output_path':str(out),'payload':{'bpm':inp.get('bpm'),'duration_requested':inp.get('duration_sec')}}),flush=True)
except Exception as exc:
    print(json.dumps({'type':'error','message':str(exc)}),flush=True); raise
