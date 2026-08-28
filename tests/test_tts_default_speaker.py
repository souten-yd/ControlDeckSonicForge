"""読み上げの既定の声。

言語が「自動」はUIの既定である。そこが英語話者に落ちていたので、日本語を
書いても英語男性の声で読まれていた。書いてある文字がどちらの言語かは
分かるので、それを見て決める。英語は組み込みに女性がいないためRyanのまま。
"""
from __future__ import annotations

import re


def _default_speaker():
    from pathlib import Path

    source = Path(__file__).resolve().parents[1] / "worker_packs/qwen_tts/worker.py"
    text = source.read_text(encoding="utf-8")
    body = text[text.index("_JAPANESE_RE"):text.index("def handle(")]
    namespace: dict = {"re": re}
    exec(compile(body, str(source), "exec"), namespace)
    return namespace["_default_speaker"]


def test_auto_language_reads_japanese_with_the_japanese_voice():
    speaker = _default_speaker()
    assert speaker("ja", "こんにちは") == "Ono_Anna"
    assert speaker("auto", "こんにちは。今日はいい天気ですね。") == "Ono_Anna"
    assert speaker(None, "漢字だけの文") == "Ono_Anna"


def test_english_keeps_its_native_speaker():
    speaker = _default_speaker()
    assert speaker("auto", "Hello, how are you?") == "Ryan"
    assert speaker("en", "Hello") == "Ryan"
    assert speaker("auto", "") == "Ryan"
