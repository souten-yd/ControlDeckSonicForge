from __future__ import annotations

import ctypes
import gc
from collections import OrderedDict
from contextlib import redirect_stdout
import json
import os
import re
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
# 載せたモデルの置き場。**上限を設けて古いものから降ろす。**
#
# Qwen3-TTS は用途ごとにモデルが分かれている（声を注文する VoiceDesign 1.7B、
# 複製する Base 0.6B、公式話者で読む CustomVoice 0.6B）。上限が無いと、
# キャラクターの声を作ってから喋らせるだけで 3 つが同時に載ったままになり、
# worker が idle で降ろされるまで VRAM を握り続ける。実機の VRAM は 34GB 中
# 24.8GB が既に使われていた。
#
# 2 にしてあるのは、台詞ごとに載せ替えないためである。preset の声と design の
# 声が混ざった batch は CustomVoice と Base を交互に使うので、1 にすると台詞
# ごとに載せ直すことになる。VoiceDesign は声を作るときにしか要らないので、
# 生成が始まれば最も古いものとして降りる。
_MODEL_CACHE_MAX = max(1, int(os.environ.get("SONICFORGE_QWEN_TTS_MAX_MODELS", "2")))
_MODELS: "OrderedDict[tuple[str, str], object]" = OrderedDict()


def make_room(cache: "OrderedDict", limit: int, release) -> int:
    """置き場に空きを作る。降ろした数を返す。

    載せたものを黙って持ち続けない。Qwen3-TTS は用途ごとにモデルが分かれて
    いるので、上限が無いと声を作って喋らせるだけで 3 つが同時に載る。降ろす
    のは最も長く使っていないもので、preset と design が混ざった batch でも
    台詞ごとの載せ替えにならないようにする。
    """
    dropped = 0
    while len(cache) >= limit:
        cache.popitem(last=False)
        dropped += 1
    if dropped:
        release()
    return dropped


def _seed_everything(seed) -> None:
    """乱数を置く。置かないと design は同じ注文文でも別人を返す。

    実測: 注文文と本文を固定して 2 回呼び、seed 無しでは長さ 6.08s / 7.04s・
    波形の相関 0.0073（別人）、seed=777 では sha256 が一致した。声の定義に
    seed を残しておけば、見本の音が失われても同じ声を作り直せる。
    """
    if seed is None:
        return
    with redirect_stdout(sys.stderr):
        import torch

        torch.manual_seed(int(seed))
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(int(seed))


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
        _MODELS.move_to_end(key)
        return cached
    def release() -> None:
        with redirect_stdout(sys.stderr):
            gc.collect()
            if device.startswith("cuda"):
                torch.cuda.empty_cache()

    make_room(_MODELS, _MODEL_CACHE_MAX, release)
    _emit({"type": "progress", "progress": 0.1, "message": "Loading Qwen3-TTS"})
    with redirect_stdout(sys.stderr):
        value = Qwen3TTSModel.from_pretrained(
            model_id,
            device_map=device,
            dtype=dtype,
        )
    _MODELS[key] = value
    return value


_JAPANESE_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")


def _default_speaker(content_language: str | None, text: str = "") -> str:
    # Qwen3-TTS' official speaker catalog contains native Japanese Ono_Anna and
    # native English Ryan. Prefer the language-native default instead of always
    # using an English speaker for Japanese content.
    #
    # "auto" is the UI default, and it used to fall through to the English
    # speaker, so Japanese text was read aloud by an English male voice. The
    # script says which language it is, so read it rather than giving up.
    if content_language == "ja":
        return "Ono_Anna"
    if content_language in {None, "", "auto"} and _JAPANESE_RE.search(text or ""):
        return "Ono_Anna"
    return "Ryan"


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
    # 感情や言い方の指示。Qwen3-TTS は自然文を取る（"用特别愤怒的语气说" が公式の
    # 例）。`emotion` を正とし、`style` は以前の形（辞書、または素の文字列）も
    # 受ける——契約では文字列と書いてあったのに実装は辞書しか読めておらず、
    # 文字列を渡すと落ちていた。
    style = inp.get("style")
    if isinstance(style, dict):
        style_text = str(style.get("instruction") or style.get("preset") or "")
    else:
        style_text = str(style or "")
    instruct = str(inp.get("emotion") or "").strip() or style_text or str(recipe.get("instruct") or "")
    # 見本づくりのときだけレシピに載っている。1 回の design 呼び出しで複数本を作る。
    sample_texts = recipe.get("sample_texts")

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
        # 感情ごとの見本を持っているなら、指定に近いものを選ぶ。持っていなければ
        # 従来どおり単一の参照を使う。
        references = recipe.get("references")
        ref_audio = recipe.get("reference_audio") or inp.get("_internal_reference_audio")
        ref_text = recipe.get("reference_text") or inp.get("reference_text")
        if isinstance(references, dict) and references:
            chosen = str(inp.get("_internal_emotion_label") or "")
            picked = references.get(chosen) or references.get("neutral")
            if picked is None:
                picked = next(iter(references.values()))
            ref_audio = picked.get("audio") or ref_audio
            ref_text = picked.get("text") or ref_text
        if not ref_audio:
            raise ValueError("voice clone requires a SonicForge-managed reference audio")
        tts = _model(model_id)
        _emit({"type": "progress", "progress": 0.55, "message": "Synthesizing cloned voice"})
        # clone は instruct を取らない（上流の generate_voice_clone は
        # _build_instruct_text を通らない）。渡すと生成の引数として解釈され、
        # 効かないか落ちる。言い方は参照音声の喋り方と本文の中身が決める。
        kwargs = {"text": text, "language": language, "ref_audio": ref_audio}
        if ref_text:
            kwargs["ref_text"] = str(ref_text)
        elif recipe.get("x_vector_only_mode", False):
            kwargs["x_vector_only_mode"] = True
        else:
            raise ValueError(
                "voice clone requires reference_text unless x_vector_only_mode is enabled"
            )
        # 声を作ったときの seed を台詞にも置く。同じ声・同じ台詞なら同じ音が
        # 返るので、作り直しても素材が入れ替わらない。
        _seed_everything(recipe.get("seed"))
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
        # identity を決める見本は **一本だけ** 作る。
        #
        # design の identity は注文文と本文と乱数で決まる。本文を変えれば別人になり、
        # 1 回の呼び出しに batch でまとめても変わらない（実測: 感情別の 4 本を 1 回で
        # まとめて作り、MFCC 平均の余弦は最小 0.703。別々に呼んだとき 0.695 と同じ
        # 水準だった）。以前ここは batch で感情別に作っていたので、感情ごとに別人の
        # キャラクターが出来ていた。
        anchor_text = str(recipe.get("anchor_text") or "").strip() or text
        seed = recipe.get("seed")
        tts = _model(model_id)
        _emit({"type": "progress", "progress": 0.4, "message": "Designing voice"})
        _seed_everything(seed)
        wavs, sr = tts.generate_voice_design(
            text=[anchor_text],
            language=language,
            instruct=[design_instruction],
        )
        # 感情別の見本は、確定した identity の見本からの複製で作る。design を
        # 呼び直さない——呼び直した時点で別人になる。複製は喋り方も写すので、
        # 感情の乗った文を渡せばその口調の見本になり、identity は複製経路が保つ
        # （実測: 基準との MFCC 余弦 0.978 〜 0.993）。
        emotion_texts = [
            (str(item[0]), str(item[1]))
            for item in (recipe.get("emotion_texts") or [])
            if isinstance(item, (list, tuple)) and len(item) == 2
        ]
        if emotion_texts:
            import numpy as np

            clone_model_id = (
                recipe.get("clone_model_id")
                or os.environ.get(
                    "SONICFORGE_QWEN_TTS_CLONE_MODEL",
                    "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
                )
            )
            anchor_wav = np.asarray(wavs[0]).reshape(-1)
            clone = _model(clone_model_id)
            # 参照は ICL で渡す。x_vector_only_mode より一致が良く（実測 0.983〜0.992
            # 対 0.959〜0.983）、見本はこちらが喋らせた文そのものなので書き起こしが
            # 完全に一致する。
            prompt = clone.create_voice_clone_prompt(
                ref_audio=(anchor_wav, sr),
                ref_text=anchor_text,
                x_vector_only_mode=False,
            )
            for index, (label, spoken) in enumerate(emotion_texts):
                _emit({
                    "type": "progress",
                    "progress": 0.55 + 0.35 * (index / max(1, len(emotion_texts))),
                    "message": f"Deriving {label} reference",
                })
                _seed_everything(seed)
                extra, extra_sr = clone.generate_voice_clone(
                    text=[spoken],
                    language=language,
                    voice_clone_prompt=prompt,
                )
                if extra_sr != sr:
                    raise ValueError(
                        f"clone sample rate {extra_sr} does not match design {sr}"
                    )
                wavs = list(wavs) + [extra[0]]
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
            or _default_speaker(content_language, text)
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
    # 仕事の出力は 1 ファイルという約束なので、複数本は無音を挟んで繋いで返す。
    # どこで切ればよいかは worker が正確に知っているので、境目を標本位置で
    # 添える。呼んだ側は無音を探さずに切れる——探すとずれ、ずれると書き起こしと
    # 音が食い違って複製の質が落ちる。
    segments: list[dict] = []
    if len(wavs) > 1:
        import numpy as np

        gap = np.zeros(int(sr * 0.4), dtype=np.asarray(wavs[0]).dtype)
        pieces = []
        cursor = 0
        for index, wav in enumerate(wavs):
            array = np.asarray(wav)
            if index:
                pieces.append(gap)
                cursor += len(gap)
            segments.append({"start": cursor, "end": cursor + len(array)})
            pieces.append(array)
            cursor += len(array)
        sf.write(output, np.concatenate(pieces), sr)
    else:
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
                # 声の定義のうち、作り直しに要るもの。見本の音が失われても
                # 注文文・本文・seed があれば同じ声に戻せる。
                "seed": recipe.get("seed"),
                "segments": segments,
                "sample_rate": sr,
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
            _emit({"type": "error", "message": str(exc)})


if __name__ == "__main__":
    main()
