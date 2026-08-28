from __future__ import annotations

import ctypes
import json
import os
import signal
import sys
from pathlib import Path

from worker_packs.whisper.audio_segments import (
    looks_like_silence_caption,
    merge_transcripts,
    speech_level,
    split_on_long_silence,
)


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

    # 誰も話していない録音を渡されたとき、whisper は黙らず作り話をする。
    # 先に音の大きさを見て、話し声が無いなら model を呼ばずに空で返す。
    # 声は山が高く谷が深い。暗騒音は平らなまま小さい。どちらか一方ではなく、
    # 「一度も大きくならない」か「全体が極端に小さい」ときを話し声なしとみなす。
    rms, peak = speech_level(audio_path)
    if peak < 0.02 or rms < 0.002:
        _emit(
            {
                "type": "result",
                "engine_id": "asr.whisper",
                "engine_version": "transformers",
                "model_id": model_id,
                "model_license_id": "model-card",
                "payload": {
                    "text": "",
                    "language": lang,
                    "segments": [],
                    "silent": True,
                    "level_rms": round(rms, 5),
                    "warm_model_cache": False,
                },
            }
        )
        return

    pipe = _pipeline(model_id)
    generate_kwargs = {}
    if lang in {"ja", "en"} and "whisper" in model_id.lower():
        generate_kwargs["language"] = {"ja": "japanese", "en": "english"}[lang]
    # 直前の出力に引きずられると、一度出た作り話が延々と繰り返される。
    if "whisper" in model_id.lower():
        generate_kwargs["condition_on_prev_tokens"] = False

    _emit({"type": "progress", "progress": 0.55, "message": "Transcribing"})
    call_kwargs = {"return_timestamps": True}
    if generate_kwargs:
        call_kwargs["generate_kwargs"] = generate_kwargs
    segments = (
        split_on_long_silence(audio_path, Path(payload["work_dir"]) / "asr-segments")
        if lang == "auto"
        else [(audio_path, 0.0)]
    )
    def transcribe(path: Path):
        try:
            return pipe(str(path), **call_kwargs)
        except (TypeError, ValueError):
            # 生成側の引数はモデルによって受け付けが違う。文字起こし自体を
            # 落とすよりは、抑制なしでも結果を返すほうがまだ役に立つ。
            fallback = dict(call_kwargs)
            fallback.pop("generate_kwargs", None)
            if generate_kwargs.get("language"):
                fallback["generate_kwargs"] = {"language": generate_kwargs["language"]}
            return pipe(str(path), **fallback)

    result = merge_transcripts(
        [(transcribe(segment), offset) for segment, offset in segments]
    )
    # 静かな録音では、whisper の決まり文句は話者の言葉ではなく埋め草である。
    # 実際に話しているときの "Thank you." は残したいので、音が小さいときだけ捨てる。
    quiet = rms < 0.01
    if quiet and looks_like_silence_caption(str(result.get("text") or "")):
        result = {"text": "", "chunks": []}
    chunks = []
    for item in result.get("chunks", []) or []:
        text = item.get("text", "")
        if quiet and looks_like_silence_caption(text):
            continue
        chunks.append(
            {
                "text": text,
                "start": item.get("start"),
                "end": item.get("end"),
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
            # In persistent mode a bad request must not poison future requests.
            # Fatal interpreter/model errors still terminate the process naturally.


if __name__ == "__main__":
    main()
