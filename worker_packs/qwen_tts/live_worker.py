from __future__ import annotations

import ctypes
import json
import os
import signal
import sys
from pathlib import Path


def _parent_death_guard() -> None:
    """Terminate this model worker if the SonicForge parent disappears."""
    if sys.platform != "linux":
        return
    try:
        libc = ctypes.CDLL(None)
        parent = os.getppid()
        # PR_SET_PDEATHSIG = 1
        if libc.prctl(1, signal.SIGTERM) != 0:
            return
        if os.getppid() != parent:
            os.kill(os.getpid(), signal.SIGTERM)
    except Exception:
        pass


_parent_death_guard()

import soundfile as sf  # noqa: E402
import torch  # noqa: E402
from qwen_tts import Qwen3TTSModel  # noqa: E402

MODELS: dict[str, Qwen3TTSModel] = {}


def emit(request_id: str, payload: dict) -> None:
    print(
        json.dumps({"request_id": request_id, **payload}, ensure_ascii=False),
        flush=True,
    )


def model(model_id: str) -> Qwen3TTSModel:
    cached = MODELS.get(model_id)
    if cached is not None:
        return cached
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    dtype = torch.bfloat16 if device.startswith("cuda") else torch.float32
    value = Qwen3TTSModel.from_pretrained(
        model_id,
        device_map=device,
        dtype=dtype,
    )
    MODELS[model_id] = value
    return value


def run(request_id: str, request: dict, work_dir: Path) -> None:
    inp = request.get("input", {})
    text = str(inp.get("text") or "").strip()
    if not text:
        raise ValueError("TTS input.text is required")
    work_dir.mkdir(parents=True, exist_ok=True)
    language = {"ja": "Japanese", "en": "English"}.get(
        request.get("content_language"), "Auto"
    )
    voice = inp.get("_internal_voice") if isinstance(inp.get("_internal_voice"), dict) else None
    recipe = dict(voice.get("recipe") or {}) if voice else {}
    source_type = str(voice.get("source_type") or "built-in") if voice else "built-in"
    requested_model = request.get("routing", {}).get("model")
    style = inp.get("style") or {}
    instruct = str(
        style.get("instruction")
        or style.get("preset")
        or recipe.get("instruct")
        or ""
    )

    if source_type == "clone":
        if not voice.get("rights_confirmed"):
            raise ValueError("voice clone profile has no rights confirmation")
        model_id = (
            requested_model
            or recipe.get("model_id")
            or os.environ.get(
                "SONICFORGE_QWEN_TTS_CLONE_MODEL",
                "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
            )
        )
        emit(request_id, {"type": "progress", "progress": 0.12, "message": "Loading clone voice model"})
        tts = model(str(model_id))
        ref_audio = recipe.get("reference_audio") or inp.get("_internal_reference_audio")
        ref_text = recipe.get("reference_text") or inp.get("reference_text")
        if not ref_audio:
            raise ValueError("voice clone requires a SonicForge-managed reference audio")
        kwargs = {"text": text, "language": language, "ref_audio": ref_audio}
        if ref_text:
            kwargs["ref_text"] = str(ref_text)
        elif recipe.get("x_vector_only_mode", False):
            kwargs["x_vector_only_mode"] = True
        else:
            raise ValueError(
                "voice clone requires reference_text unless x_vector_only_mode is enabled"
            )
        emit(request_id, {"type": "progress", "progress": 0.55, "message": "Synthesizing cloned voice"})
        wavs, sr = tts.generate_voice_clone(**kwargs)
        mode = "clone"
        speaker = voice.get("name")
    elif source_type == "design":
        model_id = (
            requested_model
            or recipe.get("model_id")
            or os.environ.get(
                "SONICFORGE_QWEN_TTS_DESIGN_MODEL",
                "Qwen/Qwen3-TTS-12Hz-0.6B-VoiceDesign",
            )
        )
        design_instruction = str(recipe.get("design_instruction") or instruct).strip()
        if not design_instruction:
            raise ValueError("voice design profile requires design_instruction")
        emit(request_id, {"type": "progress", "progress": 0.12, "message": "Loading voice design model"})
        tts = model(str(model_id))
        emit(request_id, {"type": "progress", "progress": 0.55, "message": "Synthesizing designed voice"})
        wavs, sr = tts.generate_voice_design(
            text=text,
            language=language,
            instruct=design_instruction,
        )
        mode = "design"
        speaker = voice.get("name")
    else:
        model_id = (
            requested_model
            or recipe.get("model_id")
            or os.environ.get(
                "SONICFORGE_QWEN_TTS_MODEL",
                "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
            )
        )
        speaker = (
            recipe.get("speaker")
            or inp.get("speaker")
            or (
                inp.get("voice_id")
                if not str(inp.get("voice_id") or "").startswith("voice:")
                else None
            )
            or os.environ.get("SONICFORGE_QWEN_TTS_SPEAKER", "Ryan")
        )
        emit(request_id, {"type": "progress", "progress": 0.12, "message": "Loading voice model"})
        tts = model(str(model_id))
        emit(request_id, {"type": "progress", "progress": 0.55, "message": "Synthesizing"})
        wavs, sr = tts.generate_custom_voice(
            text=text,
            language=language,
            speaker=str(speaker),
            instruct=instruct,
        )
        mode = "custom_voice"

    output = work_dir / "output.wav"
    sf.write(output, wavs[0], sr)
    emit(
        request_id,
        {
            "type": "result",
            "engine_id": "tts.qwen3",
            "engine_version": "0.1.1-live",
            "model_id": str(model_id),
            "model_license_id": "Apache-2.0",
            "output_path": str(output),
            "payload": {
                "language": request.get("content_language"),
                "voice_mode": mode,
                "voice_id": voice.get("id") if voice else None,
                "speaker": speaker,
                "filename": "speech.wav",
                "persistent_worker": True,
            },
        },
    )


for line in sys.stdin:
    try:
        envelope = json.loads(line)
        request_id = str(envelope["request_id"])
        run(
            request_id,
            envelope["request"],
            Path(envelope["work_dir"]).resolve(),
        )
    except Exception as exc:
        request_id = str(locals().get("request_id") or "unknown")
        emit(request_id, {"type": "error", "message": str(exc)[:1000]})
