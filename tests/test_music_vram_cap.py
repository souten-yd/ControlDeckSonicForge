"""ACE-Step に伝える VRAM の枠。

ACE-Step はこの値でカードの段（tier）を決め、段ごとに offload・量子化・同時に
載せる部品まで変える。**ここが実際の空きと食い違うと、こちらがどれだけ offload を
指定しても効かない。** 決め打ちの 20 が入っていたため、LLM が 22.9 GiB を持って
いても 20 GiB 使える前提で構成を組み、読み込みの途中で OOM していた。
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_worker():
    spec = importlib.util.spec_from_file_location(
        "acestep_worker", ROOT / "worker_packs/acestep/worker.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_cap_follows_the_budget(monkeypatch: pytest.MonkeyPatch):
    """枠を伝える。伝えないと既定の 20 GiB 前提で組まれる。

    実測 2026-09-15（同じ 20 秒の曲、どちらも offload 指定つき）:
      MAX_CUDA_VRAM=20  カード全体で 29.21 GiB（GPU 独占で単独実行）
      MAX_CUDA_VRAM=9   LLM が 21.28 GiB 常駐のまま、上乗せ 7.4 GiB で完走
    """
    worker = load_worker()
    # setenv で入れてから消す。delenv だけだと monkeypatch がこの鍵を覚えないので、
    # 試験の中で os.environ へ直に入った値が後の試験まで残る（実測でそうなった）。
    monkeypatch.setenv("MAX_CUDA_VRAM", "")
    monkeypatch.delenv("MAX_CUDA_VRAM", raising=False)
    assert worker._apply_vram_cap(9 * 1024**3) == 9
    assert os.environ["MAX_CUDA_VRAM"] == "9"
    assert worker._apply_vram_cap(20 * 1024**3) == 20
    assert os.environ["MAX_CUDA_VRAM"] == "20"


def test_a_budget_below_the_smallest_tier_is_left_alone(monkeypatch: pytest.MonkeyPatch):
    """ACE-Step の最下段より下は、伝えても意味が無い。触らない。"""
    worker = load_worker()
    monkeypatch.setenv("MAX_CUDA_VRAM", "")
    monkeypatch.delenv("MAX_CUDA_VRAM", raising=False)
    assert worker._apply_vram_cap(3 * 1024**3) is None
    assert "MAX_CUDA_VRAM" not in os.environ


def test_the_warm_handler_is_not_reused_across_tiers():
    """段が変われば構成が変わる。載せたものを使い回してよいのは段が同じときだけ。

    使い回すと、20 GiB 前提で載せたものを 9 GiB の要求がそのまま使うことになる。
    """
    import inspect

    worker = load_worker()
    source = inspect.getsource(worker._handlers)
    # key に段が入っていること。入っていないと、前の段のものが返る。
    assert "vram_cap_gib" in source.split("key = ", 1)[1].split("\n", 1)[0]
