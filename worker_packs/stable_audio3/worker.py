from __future__ import annotations
import json, os, sys
from pathlib import Path
payload=json.loads(sys.stdin.readline()); request=payload['request']; work=Path(payload['work_dir']); work.mkdir(parents=True,exist_ok=True)
print(json.dumps({'type':'progress','progress':0.08,'message':'Loading Stable Audio 3'}),flush=True)
try:
    import soundfile as sf
    from stable_audio_3 import StableAudioModel
    inp=request.get('input',{}); prompt=inp.get('prompt') or inp.get('description') or ''
    duration=float(inp.get('duration_sec') or 3.0); model_name=os.environ.get('SONICFORGE_STABLE_AUDIO_MODEL','small-sfx')
    model=StableAudioModel.from_pretrained(model_name,device='cuda' if os.environ.get('SONICFORGE_AUDIO_DEVICE','auto')!='cpu' else 'cpu')
    print(json.dumps({'type':'progress','progress':0.5,'message':'Generating audio'}),flush=True)
    audio=model.generate(prompt=prompt,duration=duration,steps=8,seed=request.get('seed',-1) if request.get('seed') is not None else -1,batch_size=1)
    if hasattr(audio,'detach'): audio=audio.detach().float().cpu().numpy()
    if getattr(audio,'ndim',0)==3: audio=audio[0]
    if getattr(audio,'ndim',0)==2 and audio.shape[0] <= 2: audio=audio.T
    sr=int(getattr(model,'sample_rate',44100) or 44100); out=work/'output.wav'; sf.write(out,audio,sr)
    print(json.dumps({'type':'result','engine_id':'audio.stable-audio-3','engine_version':'0.1.0','model_id':model_name,'model_license_id':'stability-model-license','output_path':str(out),'payload':{'duration_requested':duration}}),flush=True)
except Exception as exc:
    print(json.dumps({'type':'error','message':str(exc)}),flush=True); raise
