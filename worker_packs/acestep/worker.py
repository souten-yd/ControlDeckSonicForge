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


# 枠がこれ以上あれば、そのまま GPU へ載せて最速で作る。下回ったら DiT を int8 に
# して部品ごとに送り出す形へ落とす。
#
# 実測 2026-09-14（AMD Radeon AI PRO R9700）:
#   そのまま          VRAM 約 21 GiB   30 秒の曲を 80 秒
#   int8 + 送り出し   VRAM  8.47 GiB   同じ曲を 132 秒（LLM が 22.9 GiB 常駐のまま）
# LLM を降ろせるなら前者が速い。降ろせないなら後者しか道がない。
FULL_RESIDENCY_BYTES = 20 * 1024**3


def _free_vram_bytes(device: str) -> int:
    """いま実際に空いている VRAM。分からなければ 0。

    枠を渡されない経路がある（画面から直に頼んだとき、ホストの身元が付かない
    とき）。そのとき「枠の指定が無い ＝ 全部使ってよい」と読むのは誤りで、
    device には他人が載っていることがある。実測 2026-09-15、LLM が 22.9 GiB を
    持っている状態で画面から音楽を頼むと、そのまま載せに行って HIP out of
    memory で落ちた（10.18 GiB まで取ったところで空き 0）。頼んだ側からは
    「VRAM が使われないまま失敗した」としか見えない。

    申告が無いなら、こちらで見る。
    """
    if device not in ("auto", "cuda") and not str(device).startswith("cuda"):
        return 0
    try:
        with redirect_stdout(sys.stderr):
            import torch

            if not torch.cuda.is_available():
                return 0
            index = 0
            if str(device).startswith("cuda:"):
                index = int(str(device).split(":", 1)[1])
            free, _total = torch.cuda.mem_get_info(index)
        return int(free)
    except Exception:
        # 見られないなら、見えなかったことにする。ここで落とすと、GPU の無い
        # 機械で音楽が作れなくなる。
        return 0

# int8 にするのは decoder の線形層だけ。ACE-Step 自身の量子化もこの範囲で、
# 広げると遅くなる（実測: tokenizer まで含めると 30 秒の曲が 147 秒 → 344 秒）。
QUANT_INCLUDE = ["decoder*"]
QUANT_EXCLUDE = ["*tokenizer*", "*detokenizer*"]


def _int8_cache_dir(checkpoints: str, dit_model: str) -> Path:
    return Path(checkpoints) / f"{dit_model}-int8"


def _build_int8(handler, cache: Path) -> None:
    """DiT を int8 にして書き出す。CPU の上で行うので GPU は要らない。

    生成のたびに量子化すると、その前に bf16/fp32 のまま GPU へ載せる段が要る。
    LLM が居ると、そこで OOM する（実測: 載せる前に 0 bytes free）。先に作って
    置いておけば、次からは int8 を載せるだけで済む（読み込み 2.0 秒）。
    """
    from optimum.quanto import freeze, qint8, quantization_map, quantize
    from safetensors.torch import save_file
    import torch

    quantize(handler.model, weights=qint8, include=QUANT_INCLUDE, exclude=QUANT_EXCLUDE)
    freeze(handler.model)
    staging = cache.with_name(cache.name + ".partial")
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)
    state = {
        name: value.contiguous()
        for name, value in handler.model.state_dict().items()
        if isinstance(value, torch.Tensor)
    }
    save_file(state, str(staging / "model.safetensors"))
    (staging / "quantization_map.json").write_text(
        json.dumps(quantization_map(handler.model)), encoding="utf-8"
    )
    shutil.rmtree(cache, ignore_errors=True)
    staging.rename(cache)


def _load_int8(handler, cache: Path, target: str, *, offloading: bool) -> None:
    """保存済みの int8 を当てて、置き場所を整える。

    送り出し（offload）を使うときは **DiT だけ** を GPU へ移す。VAE や text
    encoder まで手で移すと、ACE-Step 自身の出し入れと衝突して
    「mat2 is on cpu」で落ちる（実測 2026-09-14）。残りの部品は ACE-Step が
    要るときだけ送る。

    送り出しを使わないときは逆で、一式まとめて移さないと CPU に残った部品と
    噛み合わない（Expected all tensors to be on the same device）。
    """
    from optimum.quanto import requantize
    from safetensors.torch import load_file
    import torch

    state = load_file(str(cache / "model.safetensors"))
    qmap = json.loads((cache / "quantization_map.json").read_text(encoding="utf-8"))
    requantize(handler.model, state, qmap, device=torch.device("cpu"))
    moved = ("model",) if offloading else ("model", "vae", "text_encoder", "reward_model")
    for attr in moved:
        part = getattr(handler, attr, None)
        if part is not None and hasattr(part, "to"):
            part.to(target)
    if offloading:
        return
    for attr in ("device", "_device"):
        if hasattr(handler, attr):
            try:
                setattr(handler, attr, target)
            except Exception:  # noqa: BLE001 - 属性が読み取り専用でも進む
                pass


def _handlers(project_root: str, checkpoints: str, device: str, dit_model: str, lm_model: str, lm_backend: str, small_budget: bool = False):
    key = (project_root, checkpoints, device, dit_model, lm_model, lm_backend, small_budget)
    cached = _HANDLERS.get(key)
    if cached is not None:
        return cached

    # import そのものが stdout へ書くことがある。stdout は JSON-lines の通信路
    # なので、import ごと stderr へ寄せる。
    with redirect_stdout(sys.stderr):
        from acestep.handler import AceStepHandler
        from acestep.llm_inference import LLMHandler

        dit = AceStepHandler()
        cache = _int8_cache_dir(checkpoints, dit_model)
        if not small_budget:
            status, ok = dit.initialize_service(
                project_root=project_root,
                config_path=dit_model,
                device=device,
            )
        else:
            # 枠が小さい。bf16/fp32 のまま GPU へ載せると、そこで OOM する。
            # CPU で読んでから int8 を当て、そのあとで GPU へ移す。
            status, ok = dit.initialize_service(
                project_root=project_root,
                config_path=dit_model,
                device="cpu",
                offload_to_cpu=True,
                offload_dit_to_cpu=True,
            )
            if ok:
                # 無ければ作って保存し、あれば読むだけ。
                #
                # 作るのは一度きりで、CPU の上で 9 秒前後（実測）。以後は読むだけの
                # 2.0 秒で済む。作った直後も **file から読み直す**——初回だけ別の道を
                # 通ると、そこだけ挙動が違っても気づけない。
                if not (cache / "model.safetensors").is_file():
                    _emit({"type": "progress", "progress": 0.03,
                           "message": "Building the int8 model (first run only)"})
                    _build_int8(dit, cache)
                    # 量子化済みの handler は捨て、素の状態から読み直す。
                    dit = AceStepHandler()
                    status, ok = dit.initialize_service(
                        project_root=project_root,
                        config_path=dit_model,
                        device="cpu",
                        offload_to_cpu=True,
                        offload_dit_to_cpu=True,
                    )
                if ok:
                    _load_int8(dit, cache,
                               "cuda" if device in ("auto", "cuda") else device,
                               offloading=True)
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


def prepare_int8(payload: dict) -> None:
    """int8 を作って置いておくだけ。GPU は触らない。

    生成のときに作ると、その 1 本だけ待ち時間が伸びる（CPU で読んで量子化して
    書き出すので実測 9 秒前後）。先に作っておけば、生成は読むだけで済む。
    """
    import time

    checkpoints = os.environ.get("ACESTEP_CHECKPOINTS_DIR") or str(
        Path.home() / ".cache" / "ace-step" / "checkpoints"
    )
    dit_model = os.environ.get("SONICFORGE_ACESTEP_DIT", "acestep-v15-turbo")
    cache = _int8_cache_dir(checkpoints, dit_model)
    if (cache / "model.safetensors").is_file() and not payload.get("force"):
        _emit({"type": "result", "payload": {"int8_dir": str(cache), "built": False}})
        return
    started = time.time()
    with redirect_stdout(sys.stderr):
        import acestep
        from acestep.handler import AceStepHandler

        project_root = os.environ.get("SONICFORGE_ACESTEP_ROOT") or str(
            Path(acestep.__file__).resolve().parents[1]
        )
        handler = AceStepHandler()
        status, ok = handler.initialize_service(
            project_root=project_root, config_path=dit_model, device="cpu",
        )
        if not ok:
            raise RuntimeError(f"ACE-Step DiT initialization failed: {status}")
        _build_int8(handler, cache)
    _emit({"type": "result", "payload": {
        "int8_dir": str(cache), "built": True,
        "bytes": sum(item.stat().st_size for item in cache.iterdir()),
        "elapsed_sec": round(time.time() - started, 1),
    }})


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

    # broker が貸してくれた枠。全部載る量に届かないときは、DiT を int8 にして
    # 部品ごとに送り出す形へ落とす。載せ方は結果に残す——同じ頼みでも速さが
    # 変わるので、あとから「なぜ遅かったのか」を追えるようにする。
    granted = request.get("_internal_granted_vram_bytes")
    if granted:
        small_budget = int(granted) < FULL_RESIDENCY_BYTES
        budget_source = "granted"
    else:
        # 枠を渡されていない。全部空いている前提で載せに行くと、他人が載って
        # いる device では OOM で落ちる。実際の空きで決める。
        free = _free_vram_bytes(device)
        small_budget = bool(free) and free < FULL_RESIDENCY_BYTES
        budget_source = "measured" if free else "unknown"
    dit, llm = _handlers(
        project_root, checkpoints, device, dit_model, lm_model, lm_backend, small_budget
    )

    inp = request.get("input", {})
    caption = str(inp.get("prompt") or inp.get("description") or "").strip()
    if not caption:
        raise ValueError("music generation requires input.prompt or input.description")

    # 歌詞は ACE-Step 側の既定が空文字で、空のまま instrumental=False を渡すと
    # 歌わずに伴奏だけが返る。歌ありを頼まれたのに歌詞が無いという組み合わせは
    # 要求の検証で弾いてあるので、ここでは渡すことに徹する。
    lyrics = str(inp.get("lyrics") or "")
    language = str(inp.get("vocal_language") or "auto")

    params = GenerationParams(
        caption=caption,
        lyrics=lyrics,
        # 対応表の外の値は歌わせ方を壊すので、決めていないときは推定に任せる。
        vocal_language="unknown" if language == "auto" else language,
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
                # 歌ったかどうかは聴かないと分からない。何を渡して作ったのかは
                # 結果に残す（歌詞そのものは長いので、有無と言語だけ）。
                "has_lyrics": bool(lyrics.strip()),
                "vocal_language": language,
                "placement": "int8_offload" if small_budget else "full_device",
                # 枠を誰が決めたのか。同じ頼みでも速さが変わるので、あとから
                # 「なぜ遅かったのか」「なぜ落ちたのか」を追えるようにする。
                "placement_decided_by": budget_source,
                "granted_vram_bytes": int(granted) if granted else None,
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
            if payload.get("type") == "prepare_int8":
                prepare_int8(payload)
                continue
            handle(payload)
        except Exception as exc:
            _emit({"type": "error", "message": str(exc)[:2000]})


if __name__ == "__main__":
    main()
