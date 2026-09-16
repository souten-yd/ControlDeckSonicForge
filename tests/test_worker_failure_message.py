"""worker が落ちたときに、何が起きたのかが記録に残ること。

以前は stderr の末尾 1000 文字をそのまま返し、job には 500 文字で切って
保存していた。ACE-Step は生成の間じゅう INFO を書き続けるので、例外が出ていても
その後ろのログに押し出されて消える。実測 2026-09-16: 音楽生成の失敗 12 件を
調べたところ、記録に残っていたのはどれも「model を cpu へ読み込んだ」という
INFO 行だけで、何が起きたのかは一行も分からなかった。直す側は毎回あてずっぽう
になる。
"""

from __future__ import annotations

import signal

from sonicforge.workers import _failure_message


NOISE = "\n".join(f"2026-09-16 09:50:{index:02d} | INFO | loading something" for index in range(60))


def test_a_traceback_survives_the_log_that_follows_it():
    """例外の後ろにログが続いても、例外のほうを残す。末尾ではなく原因を残す。"""
    stderr = (
        NOISE
        + "\nTraceback (most recent call last):\n"
        + '  File "worker.py", line 1, in handle\n'
        + "RuntimeError: mat2 must be on the same device\n"
        + NOISE
    ).encode()
    message = _failure_message(1, stderr)
    assert "RuntimeError: mat2 must be on the same device" in message
    assert message.startswith("worker exited 1:")


def test_being_killed_is_said_out_loud():
    """signal で殺されたなら traceback は出ない。

    出ないこと自体が「例外ではなく殺された」という情報である。それが分からないと、
    無い例外を探し続けることになる。
    """
    message = _failure_message(-signal.SIGKILL, NOISE.encode())
    assert message.startswith("worker was killed by SIGKILL")
    message = _failure_message(-signal.SIGTERM, b"")
    assert message == "worker was killed by SIGTERM"


def test_ending_without_a_result_is_not_reported_as_success():
    """終了の仕方が 0 でも、結果を出さずに終われば失敗である。"""
    message = _failure_message(0, NOISE.encode())
    assert message.startswith("worker ended without a result")


def test_the_explanation_is_long_enough_to_hold_a_traceback():
    """500 文字では ACE-Step のログ 1〜2 行で埋まる。"""
    from sonicforge.jobs import FAILURE_MESSAGE_CHARS

    assert FAILURE_MESSAGE_CHARS >= 2000
    deep = "\n".join(f'  File "f{index}.py", line {index}, in run' for index in range(40))
    stderr = (NOISE + "\nTraceback (most recent call last):\n" + deep + "\nValueError: 最後の行\n").encode()
    message = _failure_message(1, stderr)
    assert "ValueError: 最後の行" in message, "深い traceback の結論が切り落とされている"
