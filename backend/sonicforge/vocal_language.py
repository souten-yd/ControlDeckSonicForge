"""歌詞の文字から、歌わせる言語を決める。

`vocal_language` を渡さないと ACE-Step は `unknown` を受け取り、**日本語の歌詞では
歌わない**（2026-09-14 実測: 同じ歌詞・同じ prompt で 30 秒を 2 本作り、
`ja` を指定したほうだけが歌った。指定しないほうは伴奏だけ）。

歌詞を書いた人は言語を知っている。書かれた文字を見れば分かるものを、モデルに
当てさせる理由が無い。ただし**確実に分かるときだけ**名乗る。ラテン文字は
英語・スペイン語・フランス語などを見分けられないので、そこは触らない。
"""
from __future__ import annotations

# 文字の範囲で言語が一意に決まるもの。曖昧なものは入れない。
_HIRAGANA = range(0x3040, 0x30A0)
_KATAKANA = range(0x30A0, 0x3100)
_HANGUL = range(0xAC00, 0xD7A4)
_HANGUL_JAMO = range(0x1100, 0x1200)
_CJK = range(0x4E00, 0xA000)
_CYRILLIC = range(0x0400, 0x0500)


def detect(lyrics: str) -> str | None:
    """歌詞の言語。決められなければ None。

    仮名があれば日本語。ハングルがあれば朝鮮語。仮名の無い漢字だけなら中国語。
    キリル文字ならロシア語。それ以外（ラテン文字など）は決めない。
    """
    kana = hangul = cjk = cyrillic = 0
    for character in lyrics:
        code = ord(character)
        if code in _HIRAGANA or code in _KATAKANA:
            kana += 1
        elif code in _HANGUL or code in _HANGUL_JAMO:
            hangul += 1
        elif code in _CJK:
            cjk += 1
        elif code in _CYRILLIC:
            cyrillic += 1
    if kana:
        return "ja"
    if hangul:
        return "ko"
    if cjk:
        # 仮名の無い漢字だけ。日本語の可能性も残るが、中国語のほうが確からしい。
        return "zh"
    if cyrillic:
        return "ru"
    return None
