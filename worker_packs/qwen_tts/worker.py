from __future__ import annotations

import json
import os
import sys
from pathlib import Path

payload = json.loads(sys.stdin.readline())
request = payload["request"]
work = Path(payload["work_dir"])
work.mkdir(parents=True, exist_ok=True)
print(json.dumps({"type": "progress", "progress": 0.1, "message": "Loading Qwen3-TTS"}), flush=True)

try:
    import torch
    import soundfile as sf
    from qwen_tts import Qwen3TTSModel

    inp = request.get("input", {})
    text = str(inp.get("text") or "").strip()
    if not text:
        raise ValueError("TTS input.text is required")

    language = {"ja": "Japanese", "en": "English"}.get(request.get("content_language"), "Auto")
    voice = inp.get("_internal_voice") if isinstance(inp.get("_internal_voice"), dict) else None
    recipe = dict(voice.get("recipe") or {}) if voice else {}
    source_type = str(voice.get("source_type") or "built-in") if voice else "built-in"

    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    dtype = torch.bfloat16 if device.startswith("cuda") else torch.float32
    load_kwargs = {"device_map": device, "dtype": dtype}

    requested_model = request.get("routing", {}).get("model")
    style = inp.get("style") or {}
    instruct = str(style.get("instruction") or style.get("preset") or recipe.get("instruct") or "")

    if source_type == "clone":
        if not voice.get("rights_confirmed"):
            raise ValueError("voice clone profile has no rights confirmation")
        model_id = requested_model or recipe.get("model_id") or os.environ.get("SONICFORGE_QWEN_TTS_CLONE_MODEL", "Qwen/Qwen3-TTS-12Hz-0.6B-Base")
        ref_audio = recipe.get("reference_audio") or inp.get("_internal_reference_audio")
        ref_text = recipe.get("reference_text") or inp.get("reference_text")
        if not ref_audio:
            raise ValueError("voice clone requires a SonicForge-managed reference audio")
        tts = Qwen3TTSModel.from_pretrained(model_id, **load_kwargs)
        print(json.dumps({"type": "progress", "progress": 0.55, "message": "Synthesizing cloned voice"}), flush=True)
        kwargs = {"text": text, "language": language, "ref_audio": ref_audio}
        if ref_text:
            kwargs["ref_text"] = str(ref_text)
        elif recipe.get("x_vector_only_mode", False):
            kwargs["x_vector_only_mode"] = True
        else:
            raise ValueError("voice clone requires reference_text unless x_vector_only_mode is enabled")
        wavs, sr = tts.generate_voice_clone(**kwargs)
        mode = "clone"
        speaker = voice.get("name")
    elif source_type == "design":
        model_id = requested_model or recipe.get("model_id") or os.environ.get("SONICFORGE_QWEN_TTS_DESIGN_MODEL", "Qwen/Qwen3-TTS-12Hz-0.6B-VoiceDesign")
        design_instruction = str(recipe.get("design_instruction") or instruct).strip()
        if not design_instruction:
            raise ValueError("voice design profile requires design_instruction")
        tts = Qwen3TTSModel.from_pretrained(model_id, **load_kwargs)
        print(json.dumps({"type": "progress", "progress": 0.55, "message": "Designing and synthesizing voice"}), flush=True)
        wavs, sr = tts.generate_voice_design(text=text, language=language, instruct=design_instruction)
        mode = "design"
        speaker = voice.get("name")
    else:
        model_id = requested_model or recipe.get("model_id") or os.environ.get("SONICFORGE_QWEN_TTS_MODEL", "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice")
        speaker = recipe.get("speaker") or inp.get("speaker") or (inp.get("voice_id") if not str(inp.get("voice_id") or "").startswith("voice:") else None) or os.environ.get("SONICFORGE_QWEN_TTS_SPEAKER", "Ryan")
        tts = Qwen3TTSModel.from_pretrained(model_id, **load_kwargs)
        print(json.dumps({"type": "progress", "progress": 0.55, "message": "Synthesizing"}), flush=True)
        wavs, sr = tts.generate_custom_voice(text=text, language=language, speaker=str(speaker), instruct=instruct)
        mode = "custom_voice"

    output = work / "output.wav"
    sf.write(output, wavs[0], sr)
    print(json.dumps({"type": "result", "engine_id": "tts.qwen3", "engine_version": "0.1.1", "model_id": model_id, "model_license_id": "Apache-2.0", "output_path": str(output), "payload": {"language": request.get("content_language"), "voice_mode": mode, "voice_id": voice.get("id") if voice else None, "speaker": speaker, "filename": "speech.wav"}}, ensure_ascii=False), flush=True)
except Exception as exc:
    print(json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False), flush=True)
    raise
