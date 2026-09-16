"""場所が要ると言われたら、時計を待たずに退く。

遊休の掃除（WARM_IDLE_SEC）は「誰も欲しがっていない間に片付ける」ためのもので、
時計で決めるしかない。短くすれば連続生成のたびにモデルを読み直し、長くすれば
他（画像生成・LLM）の枠を削る。どちらに振っても片方が痛む。

引き金を需要にすれば、その板挟みが消える。誰も欲しがらない間は抱えたままで良く、
欲しがられた瞬間に降りる。**走っている処理は切らない** のは掃除と同じである。
"""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from sonicforge import workers

from test_core import load_app


class _Proc:
    returncode = 0
    pid = -1
    stdin = None


def test_what_is_held_is_declared():
    key = ("music.ace-step-1.5", ("x",), "{}")
    workers._warm[key] = _Proc()
    try:
        held = workers.held_engines()
        assert held["music.ace-step-1.5"] > 0
    finally:
        workers._warm.pop(key, None)


def test_nothing_held_means_nothing_declared():
    """抱えていないのに空でない申告をすると、頼む相手を探す側が空回りする。"""
    assert workers.held_engines() == {}


def test_an_idle_engine_is_released_without_waiting_for_the_clock():
    key = ("music.ace-step-1.5", ("x",), "{}")
    workers._warm[key] = _Proc()
    # 使ったばかり。掃除の時計から見ればまだ降ろす番ではない。
    workers._warm_used_at[key] = float("inf")
    try:
        engines, freed = asyncio.run(workers.release_idle_now())
        assert engines == ["music.ace-step-1.5"]
        assert freed > 0
        assert key not in workers._warm
    finally:
        workers._warm.pop(key, None)
        workers._warm_used_at.pop(key, None)


def test_a_running_engine_is_not_taken_away():
    """使用中のものを取り上げても、取り上げられた側が落ちるだけで取り合いは解決しない。"""
    key = ("music.ace-step-1.5", ("x",), "{}")
    workers._warm[key] = _Proc()
    workers._warm_busy.add(key)
    try:
        engines, freed = asyncio.run(workers.release_idle_now())
        assert engines == [] and freed == 0
        assert key in workers._warm, "走っている処理を切ってはいけない"
    finally:
        workers._warm.pop(key, None)
        workers._warm_busy.discard(key)


def test_a_declared_batch_is_left_alone():
    """続きがあると宣言されている最中に降ろすと、次の 1 件がまた読み直す。"""
    key = ("music.ace-step-1.5", ("x",), "{}")
    workers._warm[key] = _Proc()
    workers._hold_all_warm = 1
    try:
        engines, _freed = asyncio.run(workers.release_idle_now())
        assert engines == []
        assert key in workers._warm
    finally:
        workers._hold_all_warm = 0
        workers._warm.pop(key, None)


def test_the_host_can_ask_over_http(env):
    m = load_app()
    with TestClient(m.app) as c:
        residency = c.get("/addon/v1/resources/residency").json()
        assert residency["device_id"] == "gpu0"
        assert residency["estimated"] is True
        assert residency["reserved_bytes"] == 0

        key = ("music.ace-step-1.5", ("x",), "{}")
        workers._warm[key] = _Proc()
        try:
            residency = c.get("/addon/v1/resources/residency").json()
            assert residency["reserved_bytes"] > 0
            answer = c.post("/addon/v1/resources/step-aside").json()
            assert answer["released"] is True
            assert answer["engines"] == ["music.ace-step-1.5"]
            assert answer["freed_bytes"] > 0
        finally:
            workers._warm.pop(key, None)

        # 空けるものが無いときは、そう答える。頼んだ側は待ち直す。
        answer = c.post("/addon/v1/resources/step-aside").json()
        assert answer["released"] is False
        assert answer["reason"] == "in_use_or_empty"
