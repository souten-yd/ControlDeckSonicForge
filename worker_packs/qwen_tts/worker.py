from __future__ import annotations

import ctypes
from contextlib import redirect_stdout
import json
import os
import signal
import sys
from pathlib import Path


def _parent_death_guard() -> None:
    if sys.platform != "linux":
        return
    parent = os.getppid()
    try:
        libc = ctypes.CDLL(None)
        if libc.prctl(1, signal.SIGTERM, 0, 0, 0) != 0:  # PR_SET_PDEATHSIG
            return
    except Exception:
        return
    if os.getppid() != parent:
        os.kill(os.getpid(), signal.SIGTERM)


_parent_death_guard()
_MODELS: dict[tuple[str, str], object] = {}


def _emit(value: dict) -> None:
    print(json.dumps(value, ensure_ascii=False), flush=True)


def _model(model_id: str):
    with redirect_stdout(sys.stderr):
        import torch
        from qwen_tts import Qwen3TTSModel

    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    dtype = torch.bfloat16 if device.startswith("cuda") else torch.float32
    key = (model_id, device)
    cached = _MODELS.get(key)
    if cached is not None:
        return cached
    _emit({"type": "progress", "progress": 0.1, "message": "Loading Qwen3-TTS"})
    with redirect_stdout(sys.stderr):
        value = Qwen3TTSModel.from_pretrained(
            model_id,
            device_map=device,
            dtype=dtype,
        )
    _MODELS[key] = value
    return value


def _default_speaker(content_language: str | None) -> str:
    # Qwen3-TTS' official speaker catalog contains native Japanese Ono_Anna and
    # native English Ryan. Prefer the language-native default instead of always
    # using an English speaker for Japanese content.
    return "Ono_Anna" if content_language == "ja" else "Ryan"


def handle(payload: dict) -> None:
    import soundfile as sf

    request = payload["request"]
    work = Path(payload["work_dir"])
    work.mkdir(parents=True, exist_ok=True)

    inp = request.get("input", {})
    text = str(inp.get("text") or "").strip()
    if not text:
        raise ValueError("TTS input.text is required")

    content_language = request.get("content_language")
    language = {"ja": "Japanese", "en": "English"}.get(
        content_language, "Auto"
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
        ref_audio = recipe.get("reference_audio") or inp.get("_internal_reference_audio")
        ref_text = recipe.get("reference_text") or inp.get("reference_text")
        if not ref_audio:
            raise ValueError("voice clone requires a SonicForge-managed reference audio")
        tts = _model(model_id)
        _emit({"type": "progress", "progress": 0.55, "message": "Synthesizing cloned voice"})
        kwargs = {"text": text, "language": language, "ref_audio": ref_audio}
        if ref_text:
            kwargs["ref_text"] = str(ref_text)
        elif recipe.get("x_vector_only_mode", False):
            kwargs["x_vector_only_mode"] = True
        else:
            raise ValueError(
                "voice clone requires reference_text unless x_vector_only_mode is enabled"
            )
        wavs, sr = tts.generate_voice_clone(**kwargs)
        mode = "clone"
        speaker = voice.get("name")
    elif source_type == "design":
        model_id = (
            requested_model
            or recipe.get("model_id")
            or os.environ.get(
                "SONICFORGE_QWEN_TTS_DESIGN_MODEL",
                "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
            )
        )
        design_instruction = str(recipe.get("design_instruction") or instruct).strip()
        if not design_instruction:
            raise ValueError("voice design profile requires design_instruction")
        tts = _model(model_id)
        _emit({"type": "progress", "progress": 0.55, "message": "Designing and synthesizing voice"})
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
            or os.environ.get("SONICFORGE_QWEN_TTS_SPEAKER")
            or _default_speaker(content_language)
        )
        tts = _model(model_id)
        _emit({"type": "progress", "progress": 0.55, "message": "Synthesizing"})
        wavs, sr = tts.generate_custom_voice(
            text=text,
            language=language,
            speaker=str(speaker),
            instruct=instruct,
        )
        mode = "custom_voice"

    output = work / "output.wav"
    sf.write(output, wavs[0], sr)
    _emit(
        {
            "type": "result",
            "engine_id": "tts.qwen3",
            "engine_version": "0.1.1",
            "model_id": model_id,
            "model_license_id": "Apache-2.0",
            "output_path": str(output),
            "payload": {
                "language": content_language,
                "voice_mode": mode,
                "voice_id": voice.get("id") if voice else None,
                "speaker": speaker,
                "filename": "speech.wav",
                "warm_model_cache": False,
            },
        }
    )


def main() -> None:
    for raw in sys.stdin:
        if not raw.strip():
            continue
        try:
            payload = json.loads(raw)
            if payload.get("type") == "shutdown":
                return
            handle(payload)
        except Exception as exc:
            _emit({"type": "error", "message": str(exc)})


if __name__ == "__main__":
    main()
