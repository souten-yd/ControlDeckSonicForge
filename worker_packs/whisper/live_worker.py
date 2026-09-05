from __future__ import annotations

import ctypes
import json
import os
import signal
import sys
from pathlib import Path

from worker_packs.whisper.audio_segments import merge_transcripts, split_on_long_silence


def _parent_death_guard() -> None:
    if sys.platform != "linux":
        return
    try:
        libc = ctypes.CDLL(None)
        parent = os.getppid()
        if libc.prctl(1, signal.SIGTERM) != 0:
            return
        if os.getppid() != parent:
            os.kill(os.getpid(), signal.SIGTERM)
    except Exception:
        pass


_parent_death_guard()

import torch  # noqa: E402
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline  # noqa: E402

PIPES: dict[str, object] = {}


def emit(request_id: str, payload: dict) -> None:
    print(json.dumps({"request_id": request_id, **payload}, ensure_ascii=False), flush=True)


def asr_pipe(model_id: str):
    cached = PIPES.get(model_id)
    if cached is not None:
        return cached
    device = 0 if torch.cuda.is_available() else -1
    # bfloat16 にする。float16 は指数部が狭く、logits が溢れると確率に NaN が
    # 入る。その NaN を torch.multinomial が踏むと、ROCm では assert カーネルが
    # HIP 719（unspecified launch failure）で落ちる（2026-09-05 に単体再現）。
    # ASR は貪欲デコードなので今は multinomial を通らないが、同じ桁溢れの上に
    # 乗っている。TTS 側は既に bfloat16 で、そちらは実機で正常に生成できている。
    dtype = torch.bfloat16 if device >= 0 else torch.float32
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
    PIPES[model_id] = value
    return value


def run(request_id: str, request: dict, work_dir: Path) -> None:
    inp = request.get("input", {})
    audio = inp.get("_internal_staged_input")
    if not audio:
        raise ValueError("ASR requires a SonicForge-staged audio input")
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
    emit(request_id, {"type": "progress", "progress": 0.12, "message": "Loading ASR model"})
    pipe = asr_pipe(str(model_id))
    generate_kwargs = {}
    if lang in {"ja", "en"} and "whisper" in str(model_id).lower():
        generate_kwargs["language"] = {"ja": "japanese", "en": "english"}[lang]
    call_kwargs = {"return_timestamps": True}
    if generate_kwargs:
        call_kwargs["generate_kwargs"] = generate_kwargs
    emit(request_id, {"type": "progress", "progress": 0.55, "message": "Transcribing"})
    segments = (
        split_on_long_silence(audio_path, work_dir / "asr-segments")
        if lang == "auto"
        else [(audio_path, 0.0)]
    )
    result = merge_transcripts(
        [(pipe(str(segment), **call_kwargs), offset) for segment, offset in segments]
    )
    chunks = []
    for item in result.get("chunks", []) or []:
        chunks.append(
            {
                "text": item.get("text", ""),
                "start": item.get("start"),
                "end": item.get("end"),
            }
        )
    emit(
        request_id,
        {
            "type": "result",
            "engine_id": "asr.whisper",
            "engine_version": "transformers-live",
            "model_id": str(model_id),
            "model_license_id": "model-card",
            "payload": {
                "text": result.get("text", ""),
                "segments": chunks,
                "language": lang,
                "persistent_worker": True,
            },
        },
    )


for line in sys.stdin:
    try:
        envelope = json.loads(line)
        request_id = str(envelope["request_id"])
        run(request_id, envelope["request"], Path(envelope["work_dir"]).resolve())
    except Exception as exc:
        request_id = str(locals().get("request_id") or "unknown")
        emit(request_id, {"type": "error", "message": str(exc)[:1000]})
