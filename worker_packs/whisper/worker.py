from __future__ import annotations

import json
import os
import sys
from pathlib import Path

payload = json.loads(sys.stdin.readline())
request = payload["request"]
print(json.dumps({"type": "progress", "progress": 0.1, "message": "Loading ASR model"}), flush=True)

try:
    import torch
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

    inp = request.get("input", {})
    audio = inp.get("_internal_staged_input")
    if not audio:
        raise ValueError("ASR requires a ControlDeck scoped read grant; raw host paths are not accepted")
    audio_path = Path(str(audio)).resolve()
    if not audio_path.is_file():
        raise ValueError("staged ASR input is missing")

    lang = request.get("content_language", "auto")
    explicit_model = request.get("routing", {}).get("model")
    if lang == "ja":
        model_id = explicit_model or os.environ.get("SONICFORGE_JA_ASR_MODEL", "kotoba-tech/kotoba-whisper-v2.0")
    else:
        model_id = explicit_model or os.environ.get("SONICFORGE_MULTILINGUAL_ASR_MODEL", "openai/whisper-large-v3-turbo")

    device = 0 if torch.cuda.is_available() else -1
    dtype = torch.float16 if device >= 0 else torch.float32
    model = AutoModelForSpeechSeq2Seq.from_pretrained(model_id, torch_dtype=dtype, low_cpu_mem_usage=True, use_safetensors=True)
    processor = AutoProcessor.from_pretrained(model_id)
    pipe = pipeline("automatic-speech-recognition", model=model, tokenizer=processor.tokenizer, feature_extractor=processor.feature_extractor, torch_dtype=dtype, device=device)
    generate_kwargs = {}
    if lang in {"ja", "en"} and "whisper" in model_id.lower():
        generate_kwargs["language"] = {"ja": "japanese", "en": "english"}[lang]

    print(json.dumps({"type": "progress", "progress": 0.55, "message": "Transcribing"}), flush=True)
    call_kwargs = {"return_timestamps": True}
    if generate_kwargs:
        call_kwargs["generate_kwargs"] = generate_kwargs
    result = pipe(str(audio_path), **call_kwargs)
    chunks = []
    for item in result.get("chunks", []) or []:
        timestamp = item.get("timestamp") or (None, None)
        chunks.append({"text": item.get("text", ""), "start": timestamp[0], "end": timestamp[1]})
    print(json.dumps({"type": "result", "engine_id": "asr.whisper", "engine_version": "transformers", "model_id": model_id, "model_license_id": "model-card", "payload": {"text": result.get("text", ""), "segments": chunks, "language": lang}}, ensure_ascii=False), flush=True)
except Exception as exc:
    print(json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False), flush=True)
    raise
