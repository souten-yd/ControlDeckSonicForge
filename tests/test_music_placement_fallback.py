"""載らなかったら、諦めずに載せ方を落として作り直す。

空きの見立ては当てが外れることがある。他の process がちょうど載り始めた、
断片化していて連続した領域が取れない、といった理由で、見た目の空きがあっても
載らない。そこで job ごと失敗させると、頼んだ側には「音楽が作れない」としか
見えない。遅くても作れる道があるなら、そちらへ落とす。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_worker():
    spec = importlib.util.spec_from_file_location(
        "acestep_worker_fallback", ROOT / "worker_packs/acestep/worker.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REAL_OOM = (
    "ACE-Step DiT initialization failed: Error initializing model: HIP out of memory. "
    "Tried to allocate 12.00 MiB. GPU 0 has a total capacity of 31.86 GiB of which 0 bytes is free."
)


def test_a_real_out_of_memory_is_recognised():
    """実際に出ていた文面をそのまま見分けられること。"""
    worker = load_worker()
    assert worker._is_out_of_memory(RuntimeError(REAL_OOM))
    assert worker._is_out_of_memory(RuntimeError("CUDA error: out of memory"))
    assert worker._is_out_of_memory(MemoryError("cannot allocate 4 GiB"))


def test_an_unrelated_failure_is_not_mistaken_for_it():
    """関係ない失敗まで載せ方のせいにすると、本当の原因が隠れる。"""
    worker = load_worker()
    assert not worker._is_out_of_memory(RuntimeError("mat2 must be on the same device"))
    assert not worker._is_out_of_memory(ValueError("music generation requires input.prompt"))


def test_a_recent_failure_is_remembered_then_forgotten(monkeypatch: pytest.MonkeyPatch):
    """一度足りなかったなら、直後に同じ道を試しても同じところで落ちる。

    読み込みに数十秒かけてから落ちるので、続けて頼まれるほど損が積み上がる。
    しばらくは落とした載せ方から始める。ただし諦めたままにはしない——他の
    process は降りることがある。
    """
    worker = load_worker()
    clock = {"now": 1000.0}
    monkeypatch.setattr(worker.time, "monotonic", lambda: clock["now"])

    assert worker._recently_ran_out("auto") is False
    worker._note_out_of_memory("auto")
    assert worker._recently_ran_out("auto") is True

    clock["now"] += worker._OOM_MEMORY_SEC - 1
    assert worker._recently_ran_out("auto") is True, "覚えている間は試し直さない"

    clock["now"] += 2
    assert worker._recently_ran_out("auto") is False, "時間が経てばまた全部載せを試す"


def test_each_device_is_remembered_separately(monkeypatch: pytest.MonkeyPatch):
    worker = load_worker()
    monkeypatch.setattr(worker.time, "monotonic", lambda: 1000.0)
    worker._note_out_of_memory("cuda:0")
    assert worker._recently_ran_out("cuda:0") is True
    assert worker._recently_ran_out("cuda:1") is False
