from __future__ import annotations

import json
import os
import sys
from pathlib import Path

payload = json.loads(sys.stdin.readline())
request = payload["request"]
work = Path(payload["work_dir"]); work.mkdir(parents=True, exist_ok=True)
print(json.dumps({"type": "progress", "progress": 0.08, "message": "Loading Stable Audio 3 Small-SFX"}), flush=True)

try:
    import soundfile as sf
    from stable_audio_3 import StableAudioModel

    inp = request.get("input", {})
    user_prompt = str(inp.get("prompt") or inp.get("description") or "").strip()
    prompt = str(inp.get("_internal_engine_prompt") or user_prompt).strip()
    if not prompt: raise ValueError("SFX generation requires input.prompt or input.description")
    duration = float(inp.get("duration_sec") or 3.0)
    if not 0.1 <= duration <= 120: raise ValueError("duration_sec must be between 0.1 and 120 seconds")
    model_name = request.get("routing", {}).get("model") or os.environ.get("SONICFORGE_STABLE_AUDIO_MODEL", "small-sfx")
    requested_device = request.get("routing", {}).get("device") or "auto"
    # Small-SFX is the supported conservative baseline. Upstream documents it as a CPU model;
    # do not silently promote an unmeasured ROCm path merely because torch exposes HIP as cuda.
    device = "cpu" if requested_device in {"auto", "cpu"} else requested_device
    if device != "cpu" and model_name == "small-sfx" and os.environ.get("SONICFORGE_ALLOW_EXPERIMENTAL_AUDIO_GPU") != "1":
        raise ValueError("GPU Small-SFX is experimental; use CPU or explicitly enable the experimental route")
    model = StableAudioModel.from_pretrained(model_name, device=device)
    print(json.dumps({"type": "progress", "progress": 0.5, "message": "Generating sound effect"}), flush=True)
    audio = model.generate(prompt=prompt, duration=duration, steps=8, seed=request.get("seed", -1) if request.get("seed") is not None else -1, batch_size=1)
    if hasattr(audio, "detach"): audio = audio.detach().float().cpu().numpy()
    if getattr(audio, "ndim", 0) == 3: audio = audio[0]
    if getattr(audio, "ndim", 0) == 2 and audio.shape[0] <= 2: audio = audio.T
    sample_rate = int(getattr(model, "sample_rate", 44100) or 44100); out = work / "output.wav"; sf.write(out, audio, sample_rate)
    normalization = inp.get("_internal_prompt_normalization")
    result_payload = {"duration_requested": duration, "device": device, "filename": "sfx.wav"}
    if isinstance(normalization, dict): result_payload["prompt_normalization"] = normalization
    print(json.dumps({"type": "result", "engine_id": "audio.stable-audio-3", "engine_version": "0.1.0", "model_id": model_name, "model_license_id": "Stability-AI-Community", "output_path": str(out), "payload": result_payload}, ensure_ascii=False), flush=True)
except Exception as exc:
    print(json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False), flush=True)
    raise
