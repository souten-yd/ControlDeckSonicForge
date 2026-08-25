from __future__ import annotations

import ctypes
import json
import os
import signal
import sys
from pathlib import Path


def _parent_death_guard() -> None:
    """Ensure a persistent GPU worker cannot outlive a killed SonicForge parent."""
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
_PIPELINES: dict[tuple[str, str], object] = {}


def _emit(value: dict) -> None:
    print(json.dumps(value, ensure_ascii=False), flush=True)


def _pipeline(model_id: str):
    import torch
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

    device = 0 if torch.cuda.is_available() else -1
    dtype = torch.float16 if device >= 0 else torch.float32
    key = (model_id, "gpu" if device >= 0 else "cpu")
    cached = _PIPELINES.get(key)
    if cached is not None:
        return cached
    _emit({"type": "progress", "progress": 0.1, "message": "Loading ASR model"})
    model = AutoModelForSpeechSeq2Seq.from_pretrained(
        model_id,
        torch_dtype=dtype,
        low_cpu_mem_usage=True,
        use_safetensors=True,
    )
    processor = AutoProcessor.from_pretrained(model_id)
    value = pipeline(
        "automatic-speech-recognition",
        model=model,
        tokenizer=processor.tokenizer,
        feature_extractor=processor.feature_extractor,
        torch_dtype=dtype,
        device=device,
    )
    _PIPELINES[key] = value
    return value


def handle(payload: dict) -> None:
    request = payload["request"]
    inp = request.get("input", {})
    audio = inp.get("_internal_staged_input")
    if not audio:
        raise ValueError("ASR requires a staged SonicForge input")
    audio_path = Path(str(audio)).resolve()
    if not audio_path.is_file():
        raise ValueError("staged ASR input is missing")

    lang = request.get("content_language", "auto")
    explicit_model = request.get("routing", {}).get("model")
    if lang == "ja":
        model_id = explicit_model or os.environ.get(
            "SONICFORGE_JA_ASR_MODEL", "kotoba-tech/kotoba-whisper-v2.0"
        )
    else:
        model_id = explicit_model or os.environ.get(
            "SONICFORGE_MULTILINGUAL_ASR_MODEL", "openai/whisper-large-v3-turbo"
        )

    pipe = _pipeline(model_id)
    generate_kwargs = {}
    if lang in {"ja", "en"} and "whisper" in model_id.lower():
        generate_kwargs["language"] = {"ja": "japanese", "en": "english"}[lang]

    _emit({"type": "progress", "progress": 0.55, "message": "Transcribing"})
    call_kwargs = {"return_timestamps": True}
    if generate_kwargs:
        call_kwargs["generate_kwargs"] = generate_kwargs
    result = pipe(str(audio_path), **call_kwargs)
    chunks = []
    for item in result.get("chunks", []) or []:
        timestamp = item.get("timestamp") or (None, None)
        chunks.append(
            {
                "text": item.get("text", ""),
                "start": timestamp[0],
                "end": timestamp[1],
            }
        )
    _emit(
        {
            "type": "result",
            "engine_id": "asr.whisper",
            "engine_version": "transformers",
            "model_id": model_id,
            "model_license_id": "model-card",
            "payload": {
                "text": result.get("text", ""),
                "segments": chunks,
                "language": lang,
                "warm_model_cache": True,
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
            # In persistent mode a bad request must not poison future requests.
            # Fatal interpreter/model errors still terminate the process naturally.


if __name__ == "__main__":
    main()
