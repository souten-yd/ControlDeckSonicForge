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
# 端の無音を落とすときの閾値。ACE-Step は曲の頭と尻をフェードで作るので、
# そのまま重ねると「無音に無音を重ねる」ことになり、継ぎ目に穴が残る
# （実測 2026-09-14: 118.5 秒のループ素材で、ループ点の手前 2 秒が RMS 0.00 倍。
# 聴いた利用者の判定は「めっちゃ継ぎ目が空いてる」）。
SILENCE_THRESHOLD_DB = -45.0
MIN_SILENCE_SEC = 0.2
# この秒数以内から始まる／で終わる無音を「端の無音」とみなす。曲の途中の休符は
# 残す——そこを削ると別の曲になる。
TRIM_EDGE_TOLERANCE_SEC = 0.05


def crossfade_seconds(duration_sec: float, requested: float | None = None) -> float:
    """この長さの素材に重ねてよい幅を返す。"""
    wanted = DEFAULT_CROSSFADE_SEC if requested is None else float(requested)
    return max(MIN_CROSSFADE_SEC, min(wanted, duration_sec / 4))


def silence_scan_argv(ffmpeg: str, source: Path) -> list[str]:
    """両端の無音を探す ffmpeg の引数を返す。結果は stderr に出る。"""
    return [
        ffmpeg, "-nostdin", "-i", str(source),
        "-af", f"silencedetect=noise={SILENCE_THRESHOLD_DB}dB:d={MIN_SILENCE_SEC}",
        "-f", "null", "-",
    ]


def content_range(scan_output: str, duration_sec: float) -> tuple[float, float]:
    """silencedetect の出力から、中身のある範囲 [start, end] を取り出す。

    端の無音だけを落とす。曲の途中の休符は残す——そこを削ると別の曲になる。
    """
    spans: list[tuple[float, float]] = []
    start: float | None = None
    for line in scan_output.splitlines():
        if "silence_start:" in line:
            try:
                start = float(line.rsplit("silence_start:", 1)[1].split()[0])
            except (IndexError, ValueError):
                start = None
        elif "silence_end:" in line and start is not None:
            try:
                spans.append((start, float(line.rsplit("silence_end:", 1)[1].split()[0])))
            except (IndexError, ValueError):
                pass
            start = None
    if start is not None:  # 終わりまで無音のまま file が終わった
        spans.append((start, duration_sec))

    head = 0.0
    tail = duration_sec
    for low, high in spans:
        if low <= TRIM_EDGE_TOLERANCE_SEC:
            head = max(head, min(high, duration_sec))
        if high >= duration_sec - TRIM_EDGE_TOLERANCE_SEC:
            tail = min(tail, max(low, 0.0))
    if tail - head < MIN_SOURCE_SEC:
        # 削りすぎた。端の判定が外れているので、元のまま扱う。
        return 0.0, duration_sec
    return head, tail


def loop_argv(ffmpeg: str, source: Path, target: Path, duration_sec: float,
              crossfade_sec: float | None = None,
              content: tuple[float, float] | None = None) -> list[str]:
    """繋ぎ目を作る ffmpeg の引数を返す。argv は固定で、shell を通さない。"""
    start, end = content or (0.0, duration_sec)
    usable = end - start
    if usable < MIN_SOURCE_SEC:
        raise WorkerError("audio is too short to loop")
    fade = crossfade_seconds(usable, crossfade_sec)
    if usable - fade <= fade:
        raise WorkerError("audio is too short to loop")
    graph = (
        # 本体の終わりへ頭を重ねる。重ねる 2 つは無関係な波形なので、等ゲイン
        # （tri）だと足したときに音量が落ちる。等電力（qsin）を使う。
        #
        # 実測 2026-09-14、継ぎ目前後の RMS（全体比、1.00 が平坦）:
        #   端が静かな素材: tri 最小 0.13 / qsin 0.18 / log 0.34
        #   端が大きい素材: tri 山 1.23 / qsin 1.70 / log 2.21
        # log は凹まないが膨らむ。素材によって最良が入れ替わるので、万能解は
        # 無い。既定は教科書どおりの等電力にしておく。効きの大きさは曲線より
        # 「端の無音を削るかどうか」のほうが桁違いに大きい（同 0.03 → 0.23）。
        f"[0:a][1:a]acrossfade=d={fade:.6f}:c1=qsin:c2=qsin[out]"
    )
    return [
        ffmpeg, "-nostdin", "-y",
        # 本体: 中身のある範囲から、頭のぶんを飛ばした残り。
        "-ss", f"{start + fade:.6f}", "-t", f"{usable - fade:.6f}", "-i", str(source),
        # 頭: 重ねるぶんだけ。
        "-ss", f"{start:.6f}", "-t", f"{fade:.6f}", "-i", str(source),
        "-filter_complex", graph,
        "-map", "[out]",
        "-c:a", "pcm_s16le",
        str(target),
    ]
