from __future__ import annotations
import json, os, sys
from pathlib import Path

payload=json.loads(sys.stdin.readline()); request=payload["request"]
print(json.dumps({"type":"progress","progress":0.1,"message":"Loading ASR model"}), flush=True)
try:
    import torch
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
    inp=request.get("input",{}); audio=inp.get("path")
    if not audio:
        raise ValueError("ASR worker requires staged input.path")
    lang=request.get("content_language","auto")
    if lang == "ja":
        model_id=request.get("routing",{}).get("model") or os.environ.get("SONICFORGE_JA_ASR_MODEL","kotoba-tech/kotoba-whisper-v2.0")
    else:
        model_id=request.get("routing",{}).get("model") or os.environ.get("SONICFORGE_EN_ASR_MODEL","openai/whisper-large-v3-turbo")
    device=0 if torch.cuda.is_available() else -1
    dtype=torch.float16 if device >= 0 else torch.float32
    model=AutoModelForSpeechSeq2Seq.from_pretrained(model_id, torch_dtype=dtype, low_cpu_mem_usage=True, use_safetensors=True)
    processor=AutoProcessor.from_pretrained(model_id)
    pipe=pipeline("automatic-speech-recognition", model=model, tokenizer=processor.tokenizer, feature_extractor=processor.feature_extractor, torch_dtype=dtype, device=device)
    print(json.dumps({"type":"progress","progress":0.55,"message":"Transcribing"}), flush=True)
    result=pipe(audio, return_timestamps=True)
    print(json.dumps({"type":"result","engine_id":"asr.whisper","engine_version":"transformers","model_id":model_id,"model_license_id":"model-card","payload":{"text":result.get("text", ""),"chunks":result.get("chunks",[]),"language":lang}}), flush=True)
except Exception as exc:
    print(json.dumps({"type":"error","message":str(exc)}), flush=True); raise
