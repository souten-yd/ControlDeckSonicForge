from __future__ import annotations

import ctypes
from contextlib import redirect_stdout
import json
import os
import signal
import sys
from pathlib import Path

import numpy as np

ENGINE_VERSION = "48b1a0169a28582a8984402f82cf438d3bfa6aca"
MODEL_ID = "lj1995/GPT-SoVITS"
MODEL_REVISION = "336b2ec4e8d4ac74740798dd40af44e74659ecaf"
_PIPELINE = None


def _parent_death_guard() -> None:
    if sys.platform != "linux":
        return
    parent = os.getppid()
    try:
        libc = ctypes.CDLL(None)
        if libc.prctl(1, signal.SIGTERM, 0, 0, 0) != 0:
            return
    except Exception:
        return
    if os.getppid() != parent:
        os.kill(os.getpid(), signal.SIGTERM)


def _emit(value: dict) -> None:
    print(json.dumps(value, ensure_ascii=False), flush=True)


def _root() -> Path:
    value = os.environ.get("SONICFORGE_GPT_SOVITS_ROOT")
    if not value:
        raise RuntimeError("SONICFORGE_GPT_SOVITS_ROOT is not configured")
    root = Path(value).resolve()
    if not (root / "sonicforge-gpt-sovits.json").is_file():
        raise RuntimeError("GPT-SoVITS model files are not provisioned")
    return root


def _pipeline():
    global _PIPELINE
    if _PIPELINE is not None:
        return _PIPELINE
    root = _root()
    source = root / "source"
    os.chdir(source)
    sys.path[:0] = [str(source), str(source / "GPT_SoVITS")]
    with redirect_stdout(sys.stderr):
        import torch
        from GPT_SoVITS.TTS_infer_pack.TTS import TTS, TTS_Config

        pretrained = source / "GPT_SoVITS/pretrained_models"
        config = TTS_Config(
            {"custom": {
                "device": "cuda:0" if torch.cuda.is_available() else "cpu",
                "is_half": torch.cuda.is_available(),
                "version": "v2ProPlus",
                "t2s_weights_path": str(pretrained / "s1v3.ckpt"),
                "vits_weights_path": str(pretrained / "v2Pro/s2Gv2ProPlus.pth"),
                "cnhuhbert_base_path": str(pretrained / "chinese-hubert-base"),
                "bert_base_path": str(pretrained / "chinese-roberta-wwm-ext-large"),
            }}
        )
        value = TTS(config)
        if torch.cuda.is_available():
            if value.precision is not torch.bfloat16:
                raise RuntimeError("GPT-SoVITS must use bfloat16 on ROCm")
            if next(value.t2s_model.parameters()).dtype is not torch.bfloat16:
                raise RuntimeError("GPT-SoVITS model is not bfloat16")
    _PIPELINE = value
    return value


def handle(payload: dict) -> None:
    import soundfile as sf

    request = payload["request"]
    inp = request.get("input", {})
    text = str(inp.get("text") or "").strip()
    if not text:
        raise ValueError("TTS input.text is required")
    voice = inp.get("_internal_voice")
    if not isinstance(voice, dict) or voice.get("source_type") != "clone":
        raise ValueError("GPT-SoVITS requires a reusable clone voice")
    if not voice.get("rights_confirmed"):
        raise ValueError("voice clone profile has no rights confirmation")
    recipe = dict(voice.get("recipe") or {})
    reference = recipe.get("reference_audio") or inp.get("_internal_reference_audio")
    prompt = str(recipe.get("reference_text") or inp.get("reference_text") or "").strip()
    if not reference or not prompt:
        raise ValueError("GPT-SoVITS requires managed reference audio and reference_text")
    requested_model = request.get("routing", {}).get("model")
    if requested_model not in {None, "", MODEL_ID}:
        raise ValueError("unsupported GPT-SoVITS model")
    language = request.get("content_language")
    lang = {"ja": "ja", "en": "en"}.get(language, "auto")
    _emit({"type": "progress", "progress": 0.1, "message": "Loading GPT-SoVITS"})
    pipeline = _pipeline()
    _emit({"type": "progress", "progress": 0.55, "message": "Synthesizing cloned voice"})
    with redirect_stdout(sys.stderr):
        generation = {
            "text": text,
            "text_lang": lang,
            "ref_audio_path": str(reference),
            "prompt_text": prompt,
            "prompt_lang": lang,
            "text_split_method": "cut5",
            "batch_size": 1,
            "split_bucket": True,
            "parallel_infer": True,
        }
        if request.get("seed") is not None:
            generation["seed"] = int(request["seed"])
        chunks = list(pipeline.run(generation))
    if not chunks:
        raise RuntimeError("GPT-SoVITS returned no audio")
    sample_rate = int(chunks[-1][0])
    audio = np.concatenate([np.asarray(chunk[1]).reshape(-1) for chunk in chunks])
    output = Path(payload["work_dir"]) / "output.wav"
    output.parent.mkdir(parents=True, exist_ok=True)
    sf.write(output, audio, sample_rate, subtype="PCM_16")
    _emit({
        "type": "result",
        "engine_id": "tts.gpt-sovits",
        "engine_version": ENGINE_VERSION,
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "model_license_id": "MIT",
        "output_path": str(output),
        "payload": {
            "language": language,
            "voice_mode": "clone",
            "voice_id": voice.get("id"),
            "filename": "speech.wav",
            "warm_model_cache": True,
        },
    })


def main() -> None:
    _parent_death_guard()
    while True:
        raw = sys.stdin.readline()
        if not raw:
            return
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
            if value.get("type") == "shutdown":
                return
            handle(value)
        except Exception as exc:
            _emit({"type": "error", "message": str(exc)})


if __name__ == "__main__":
    main()
