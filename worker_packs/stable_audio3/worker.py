from __future__ import annotations

import json
import os
import sys
from contextlib import redirect_stdout
from pathlib import Path

# 読み込んだモデルを持ち続ける。効果音を続けて何本も作るとき、1 本ごとに
# プロセスを起こし直すと毎回読み直すことになる。呼び出し側が stdin を開いた
# ままにしている間は、ここで抱えたものを使い回す。
_MODELS: dict[tuple[str, str], object] = {}


def _emit(event: dict) -> None:
    print(json.dumps(event, ensure_ascii=False), flush=True)


def _model(model_name: str, device: str):
    key = (model_name, device)
    cached = _MODELS.get(key)
    if cached is not None:
        return cached
    from stable_audio_3 import StableAudioModel

    with redirect_stdout(sys.stderr):
        value = StableAudioModel.from_pretrained(model_name, device=device)
    _MODELS[key] = value
    return value


def handle(payload: dict) -> None:
    request = payload["request"]
    work = Path(payload["work_dir"])
    work.mkdir(parents=True, exist_ok=True)
    _emit(
        {
            "type": "progress",
            "progress": 0.08,
            "message": "Loading Stable Audio 3 Small-SFX",
        }
    )

    # Upstream emits optional-acceleration diagnostics on stdout. Stdout is the
    # SonicForge JSON-lines protocol, so isolate all upstream chatter on stderr.
    with redirect_stdout(sys.stderr):
        import soundfile as sf

    inp = request.get("input", {})
    user_prompt = str(inp.get("prompt") or inp.get("description") or "").strip()
    prompt = str(inp.get("_internal_engine_prompt") or user_prompt).strip()
    if not prompt:
        raise ValueError("SFX generation requires input.prompt or input.description")
    duration = float(inp.get("duration_sec") or 3.0)
    if not 0.1 <= duration <= 120:
        raise ValueError("duration_sec must be between 0.1 and 120 seconds")
    model_name = request.get("routing", {}).get("model") or os.environ.get(
        "SONICFORGE_STABLE_AUDIO_MODEL", "small-sfx"
    )
    requested_device = request.get("routing", {}).get("device") or "auto"
    # Small-SFX is the conservative baseline. Upstream documents it as a CPU
    # model; do not silently treat torch HIP's `cuda` compatibility name as
    # evidence that this path is validated on ROCm.
    device = "cpu" if requested_device in {"auto", "cpu"} else requested_device
    if (
        device != "cpu"
        and model_name == "small-sfx"
        and os.environ.get("SONICFORGE_ALLOW_EXPERIMENTAL_AUDIO_GPU") != "1"
    ):
        raise ValueError(
            "GPU Small-SFX is experimental; use CPU or explicitly enable the experimental route"
        )
    model = _model(model_name, device)
    _emit(
        {
            "type": "progress",
            "progress": 0.5,
            "message": "Generating sound effect",
        }
    )
    with redirect_stdout(sys.stderr):
        audio = model.generate(
            prompt=prompt,
            duration=duration,
            steps=8,
            seed=request.get("seed", -1) if request.get("seed") is not None else -1,
            batch_size=1,
        )
    if hasattr(audio, "detach"):
        audio = audio.detach().float().cpu().numpy()
    if getattr(audio, "ndim", 0) == 3:
        audio = audio[0]
    if getattr(audio, "ndim", 0) == 2 and audio.shape[0] <= 2:
        audio = audio.T
    upstream_model = getattr(model, "model", None)
    sample_rate = int(
        getattr(upstream_model, "sample_rate", None)
        or getattr(model, "sample_rate", None)
        or 44100
    )
    out = work / "output.wav"
    sf.write(out, audio, sample_rate)
    normalization = inp.get("_internal_prompt_normalization")
    result_payload = {
        "duration_requested": duration,
        "device": device,
        "sample_rate": sample_rate,
        "filename": "sfx.wav",
    }
    if isinstance(normalization, dict):
        result_payload["prompt_normalization"] = normalization
    _emit(
        {
            "type": "result",
            "engine_id": "audio.stable-audio-3",
            "engine_version": "0.1.0",
            "model_id": model_name,
            "model_license_id": "Stability-AI-Community",
            "output_path": str(out),
            "payload": result_payload,
        }
    )


def main() -> None:
    # readline を使う。`for raw in sys.stdin` は先読みバッファが埋まるか EOF まで
    # 1 行目を返さないので、stdin を開いたまま次の要求を待つ使い方（モデルを
    # 載せたままの常駐）だと止まる。
    while True:
        raw = sys.stdin.readline()
        if not raw:
            return
        if not raw.strip():
            continue
        try:
            payload = json.loads(raw)
            if payload.get("type") == "shutdown":
                return
            handle(payload)
        except Exception as exc:
            _emit({"type": "error", "message": str(exc)[:2000]})


if __name__ == "__main__":
    main()
