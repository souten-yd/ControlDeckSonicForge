"""生成した音を、繋ぎ目の分からないループ素材にする。

ゲームの BGM や環境音は端から端まで繰り返し流す。生成したものをそのまま繰り返すと、
終わりと始まりが合わずに毎周「ブツッ」と鳴る。ここでやるのは、終わりの数秒を
始まりの数秒へ重ねて渡す（cross-fade）ことで、繰り返しても切れ目が聞こえない
1 本にすること。

L 秒の素材と重ね幅 C 秒から、L - C 秒の 1 本を作る:

    本体 = 素材[C:L]          （L-C 秒。最後の C 秒が終わりの余韻）
    頭   = 素材[0:C]          （C 秒）
    出力 = 本体の終わりに頭を重ねて渡す（acrossfade）

繰り返し再生すると、出力の終わり（頭が現れ切ったところ＝素材[C] の直前に相当）から
出力の頭（素材[C]）へ戻るので、波形が続く。

切り出しは `-ss` / `-t` で入力側に指定する。filter の `atrim` で切ってから
`acrossfade` へ渡すと、出力が 0 秒になる（実測: 30 秒の素材から 0.0 秒）。
"""
from __future__ import annotations

from pathlib import Path

from .workers import WorkerError

# 重ねる長さ（秒）。短いと繋ぎ目が残り、長いと曲の頭と尻が溶けて輪郭を失う。
# 効果音のような短いものでは、全体の 1/4 を超えないところで頭打ちにする。
DEFAULT_CROSSFADE_SEC = 1.5
MIN_CROSSFADE_SEC = 0.05
# これより短い素材はループにしない。重ねる余地が無く、残るのは元の断片だけになる。
MIN_SOURCE_SEC = 0.5


def crossfade_seconds(duration_sec: float, requested: float | None = None) -> float:
    """この長さの素材に重ねてよい幅を返す。"""
    wanted = DEFAULT_CROSSFADE_SEC if requested is None else float(requested)
    return max(MIN_CROSSFADE_SEC, min(wanted, duration_sec / 4))


def loop_argv(ffmpeg: str, source: Path, target: Path, duration_sec: float,
              crossfade_sec: float | None = None) -> list[str]:
    """繋ぎ目を作る ffmpeg の引数を返す。argv は固定で、shell を通さない。"""
    if duration_sec < MIN_SOURCE_SEC:
        raise WorkerError("audio is too short to loop")
    fade = crossfade_seconds(duration_sec, crossfade_sec)
    body_end = duration_sec - fade
    if body_end <= fade:
        raise WorkerError("audio is too short to loop")
    graph = (
        # 本体の終わりへ頭を重ねる。等電力（tri）にすると、重なったところで
        # 音量がへこまない。
        f"[0:a][1:a]acrossfade=d={fade:.6f}:c1=tri:c2=tri[out]"
    )
    return [
        ffmpeg, "-nostdin", "-y",
        # 本体: 頭のぶんを飛ばした残り全部。
        "-ss", f"{fade:.6f}", "-i", str(source),
        # 頭: 重ねるぶんだけ。
        "-ss", "0", "-t", f"{fade:.6f}", "-i", str(source),
        "-filter_complex", graph,
        "-map", "[out]",
        "-c:a", "pcm_s16le",
        str(target),
    ]
