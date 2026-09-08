from __future__ import annotations

import json
import os
import shutil
import sys
from contextlib import redirect_stdout
from pathlib import Path

# 読み込んだモデルを持ち続ける。
#
# 1 要求ごとにプロセスを起こし直すと ACE-Step の DiT と LM を毎回読み直す。
# 続けて何曲も作るときは、その読み直しがそのまま待ち時間になる。呼び出し側が
# stdin を開いたままにしている間は、ここで抱えたものを使い回す。
_HANDLERS: dict[tuple, tuple[object, object]] = {}


def _emit(event: dict) -> None:
    print(json.dumps(event, ensure_ascii=False), flush=True)


def _handlers(project_root: str, checkpoints: str, device: str, dit_model: str, lm_model: str, lm_backend: str):
    key = (project_root, checkpoints, device, dit_model, lm_model, lm_backend)
    cached = _HANDLERS.get(key)
    if cached is not None:
        return cached

    # import そのものが stdout へ書くことがある。stdout は JSON-lines の通信路
    # なので、import ごと stderr へ寄せる。
    with redirect_stdout(sys.stderr):
        from acestep.handler import AceStepHandler
        from acestep.llm_inference import LLMHandler

        dit = AceStepHandler()
        status, ok = dit.initialize_service(
            project_root=project_root,
            config_path=dit_model,
            device=device,
        )
    if not ok:
        raise RuntimeError(f"ACE-Step DiT initialization failed: {status}")

    with redirect_stdout(sys.stderr):
        llm = LLMHandler()
        status, ok = llm.initialize(
            checkpoint_dir=checkpoints,
            lm_model_path=lm_model,
            backend=lm_backend,
            device=device,
        )
    if not ok:
        raise RuntimeError(f"ACE-Step LM initialization failed: {status}")
    _HANDLERS[key] = (dit, llm)
    return dit, llm


def handle(payload: dict) -> None:
    request = payload["request"]
    work = Path(payload["work_dir"])
    work.mkdir(parents=True, exist_ok=True)
    _emit({"type": "progress", "progress": 0.05, "message": "Loading ACE-Step"})

    with redirect_stdout(sys.stderr):
        import acestep
        from acestep.inference import GenerationConfig, GenerationParams, generate_music

    # ACE-Step's upstream resolver gives ACESTEP_CHECKPOINTS_DIR precedence over
    # project_root/checkpoints. SonicForge sets that variable to its own model
    # cache before starting this worker, so model downloads never leak into an
    # unrelated ~/.cache/ace-step tree.
    project_root = os.environ.get("SONICFORGE_ACESTEP_ROOT") or str(
        Path(acestep.__file__).resolve().parents[1]
    )
    checkpoints = os.environ.get("ACESTEP_CHECKPOINTS_DIR") or str(
        Path.home() / ".cache" / "ace-step" / "checkpoints"
    )
    device = os.environ.get("SONICFORGE_MUSIC_DEVICE", "auto")
    dit_model = os.environ.get("SONICFORGE_ACESTEP_DIT", "acestep-v15-turbo")
    lm_model = os.environ.get("SONICFORGE_ACESTEP_LM", "acestep-5Hz-lm-0.6B")
    lm_backend = os.environ.get("SONICFORGE_ACESTEP_LM_BACKEND", "pt")

    dit, llm = _handlers(
        project_root, checkpoints, device, dit_model, lm_model, lm_backend
    )

    inp = request.get("input", {})
    caption = str(inp.get("prompt") or inp.get("description") or "").strip()
    if not caption:
        raise ValueError("music generation requires input.prompt or input.description")

    params = GenerationParams(
        caption=caption,
        instrumental=bool(inp.get("instrumental", True)),
        bpm=inp.get("bpm"),
        duration=float(inp.get("duration_sec") or 30),
        seed=request.get("seed") if request.get("seed") is not None else -1,
        shift=3.0,
    )
    config = GenerationConfig(batch_size=1, audio_format="wav")
    _emit({"type": "progress", "progress": 0.45, "message": "Generating music"})
    with redirect_stdout(sys.stderr):
        result = generate_music(dit, llm, params, config, save_dir=str(work))
    if not result.success or not result.audios:
        raise RuntimeError(result.error or "ACE-Step returned no audio")
    source_value = result.audios[0].get("path")
    if not source_value:
        raise RuntimeError("ACE-Step result did not contain an audio path")
    src = Path(source_value)
    if not src.is_file():
        raise RuntimeError("ACE-Step result audio is missing")
    out = work / "output.wav"
    if src.resolve() != out.resolve():
        shutil.copy2(src, out)
    _emit(
        {
            "type": "result",
            "engine_id": "music.ace-step-1.5",
            "engine_version": "1.5.0",
            "model_id": dit_model,
            "model_license_id": "MIT/review-model-terms",
            "output_path": str(out),
            "payload": {
                "bpm": inp.get("bpm"),
                "duration_requested": inp.get("duration_sec"),
                "lm_model": lm_model,
                "lm_backend": lm_backend,
            },
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
