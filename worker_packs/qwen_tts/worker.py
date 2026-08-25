from __future__ import annotations
import json, os, sys
from pathlib import Path

payload=json.loads(sys.stdin.readline())
request=payload["request"]; work=Path(payload["work_dir"]); work.mkdir(parents=True,exist_ok=True)
print(json.dumps({"type":"progress","progress":0.1,"message":"Loading Qwen3-TTS"}), flush=True)
try:
    import torch
    import soundfile as sf
    from qwen_tts import Qwen3TTSModel
    model_id=request.get("routing",{}).get("model") or os.environ.get("SONICFORGE_QWEN_TTS_MODEL","Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice")
    device="cuda:0" if torch.cuda.is_available() else "cpu"
    dtype=torch.bfloat16 if device.startswith("cuda") else torch.float32
    kwargs={"device_map":device,"dtype":dtype}
    tts=Qwen3TTSModel.from_pretrained(model_id, **kwargs)
    language={"ja":"Japanese","en":"English"}.get(request.get("content_language"),"Auto")
    inp=request.get("input",{}); speaker=inp.get("speaker") or inp.get("voice_id") or "Ryan"
    style=inp.get("style") or {}; instruct=style.get("instruction") or style.get("preset") or ""
    print(json.dumps({"type":"progress","progress":0.55,"message":"Synthesizing"}), flush=True)
    wavs,sr=tts.generate_custom_voice(text=inp["text"], language=language, speaker=speaker, instruct=instruct)
    output=work/"output.wav"; sf.write(output,wavs[0],sr)
    print(json.dumps({"type":"result","engine_id":"tts.qwen3","engine_version":"0.1.1","model_id":model_id,"model_license_id":"Apache-2.0","output_path":str(output),"payload":{"language":request.get("content_language"),"speaker":speaker}}), flush=True)
except Exception as exc:
    print(json.dumps({"type":"error","message":str(exc)}), flush=True); raise
