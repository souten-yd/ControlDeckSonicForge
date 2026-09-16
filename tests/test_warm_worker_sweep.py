"""走っている常駐を掃除で殺さない。

「使った時刻」は要求を送る前に一度押すだけだった。走っている間は更新されないので、
WARM_IDLE_SEC（180 秒）を超える処理は自分の worker を掃除機に殺される。音楽は
1 本が 180〜300 秒かかるので、ほぼ必ず当たる。

殺され方は stdin を閉じてからの SIGTERM で、traceback は出ない。記録には
ACE-Step のログ行だけが残り「なぜ落ちたのか分からない失敗」になる。実測
2026-09-16: 音楽の失敗 12 件が生存 215.1 秒と 245.1 秒にきれいに分かれていた
（差の 30 秒は掃除の周期）。MCP から音楽を頼むと、ほぼ毎回これで落ちていた。
"""

from __future__ import annotations

import asyncio

from sonicforge import workers


class _Proc:
    """掃除の対象になるかどうかだけを見る。

    降ろす側は「既に終わっている process」なら何もしないので、そう見せる。
    ここで確かめたいのは誰が降ろされるかであって、降ろし方ではない。
    """

    returncode = 0
    pid = -1
    stdin = None


def test_a_worker_in_the_middle_of_a_request_is_not_swept():
    key = ("music.ace-step-1.5", ("x",), "{}")
    workers._warm[key] = _Proc()
    # 送った時刻はうんと前。処理そのものはまだ走っている。
    workers._warm_used_at[key] = 0.0
    workers._warm_busy.add(key)
    try:
        retired = asyncio.run(workers.retire_idle_workers(now=workers.WARM_IDLE_SEC * 10))
        assert retired == [], "走っている処理を切ってはいけない"
        assert key in workers._warm
    finally:
        workers._warm.pop(key, None)
        workers._warm_used_at.pop(key, None)
        workers._warm_busy.discard(key)


def test_a_worker_that_finished_long_ago_is_still_swept():
    """遊休を抱え続ける理由は無い。31.9GiB のカードでは、他の枠を削るだけになる。"""
    key = ("tts.qwen3", ("x",), "{}")
    workers._warm[key] = _Proc()
    workers._warm_used_at[key] = 0.0
    try:
        retired = asyncio.run(workers.retire_idle_workers(now=workers.WARM_IDLE_SEC * 10))
        assert retired == ["tts.qwen3"]
        assert key not in workers._warm
    finally:
        workers._warm.pop(key, None)
        workers._warm_used_at.pop(key, None)


def test_the_idle_clock_starts_when_the_work_ends():
    """遊休の時計は「送った時刻」ではなく「終わった時刻」から数える。

    送った時刻から数えると、長い処理は終わった瞬間にもう満了していて、
    続けて作るために抱えている意味が無くなる。
    """
    key = ("music.ace-step-1.5", ("y",), "{}")
    workers._warm[key] = _Proc()
    workers._warm_used_at[key] = 0.0
    workers._warm_busy.add(key)
    try:
        # execute の finally と同じことをする。
        workers._warm_busy.discard(key)
        if key in workers._warm:
            workers._warm_used_at[key] = 1000.0
        # 終わった直後は掃除されない。
        retired = asyncio.run(workers.retire_idle_workers(now=1000.0 + workers.WARM_IDLE_SEC - 1))
        assert retired == []
        # 遊休が続けば降りる。
        retired = asyncio.run(workers.retire_idle_workers(now=1000.0 + workers.WARM_IDLE_SEC + 1))
        assert retired == ["music.ace-step-1.5"]
    finally:
        workers._warm.pop(key, None)
        workers._warm_used_at.pop(key, None)
        workers._warm_busy.discard(key)
