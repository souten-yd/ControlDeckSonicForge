"""内蔵話者の一覧と、声を作る三つの道筋。

Qwen3-TTS には声の出し方が三つある。どれを選ぶかで「同じキャラクターの声が
毎回同じか」が変わるので、そこを表にしておく。

  preset  公式の名前つき話者を使う。名前が identity なので毎回同じになる。
          ただし選べるのは 9 人で、言語ごとに 1〜2 人しか居ない。
  design  声を自然文で注文する（`generate_voice_design`）。作れる声の幅は
          広いが、**公式に再現性の保証が無く seed も無い**。同じ注文文で
          呼び直しても同じ声が出るとは限らない。
  clone   参照音声から複製する（`generate_voice_clone`）。参照が同じなら
          同じ声になる。identity は参照の波形そのものである。

したがって「キャラクターの声を決めて、あとは同じ声で喋らせる」を成り立たせる
には、design で一度作った声を **その場で掴んで参照にし、以後は clone で回す**。
design を毎回呼ぶ作りにすると、台詞ごとに別人になりうる。

この作りにはもう一つ利点がある。clone の品質は参照音声とその書き起こしが
合っているほど良い（ref_text を省くと x_vector_only_mode になり品質が落ちると
公式が書いている）。design で作った見本は、こちらが喋らせた文そのものが
書き起こしなので、書き起こしが完全に一致する。人の録音を持ち込むときには
まず得られない条件である。

実測で確かめたこと（耳で判定。話者埋め込みの cos 類似度は物差しとして使えな
かった——別人でも 0.92 出る一方、同一人物が 0.99 で、差が 0.07 しかない）:

  preset は instruct を変えても同じ人物のままだった。台詞を一字も変えずに
  「落ち着いて」「強い怒りをこめて」「悲しげに」と指示を振ったが、どれも同一
  人物に聞こえた。design が注文文を変えると別人になるのとは対照的で、名前
  つきの identity は感情の指示から独立している。**preset だけが感情と同一性を
  両立する。**

  非母語の話者でも日本語を喋る。Ryan / Aiden（英語）と Dylan / Uncle_Fu
  （中国語）に日本語を読ませたところ、4 人とも日本語になった。公式話者に
  日本語の男性が居ないという欠けは、これで埋められる。母語で使うのが最も
  良いという公式の推奨は残るので、女性なら Ono_Anna を優先する。

  台詞の意味だけで感情を出す道（instruct を空にして「ふざけるな！」と書く）
  は、感情自体は乗るが不自然になる。preset で感情を出すなら instruct を使う。
"""

from __future__ import annotations

from typing import Any

# 公式の話者一覧（model card）。母語で使うのが最も良い、と公式が書いている。
BUILT_IN_SPEAKERS: tuple[dict[str, str], ...] = (
    {"speaker": "Vivian", "language": "zh", "gender": "female", "description": "明るい若い女性の声"},
    {"speaker": "Serena", "language": "zh", "gender": "female", "description": "温かく穏やかな若い女性の声"},
    {"speaker": "Uncle_Fu", "language": "zh", "gender": "male", "description": "落ち着いた男性の声、まろやかな声質"},
    {"speaker": "Dylan", "language": "zh", "gender": "male", "description": "若い北京訛りの男性の声"},
    {"speaker": "Eric", "language": "zh", "gender": "male", "description": "快活な成都訛りの男性の声"},
    {"speaker": "Ryan", "language": "en", "gender": "male", "description": "抑揚のある力強い男性の声"},
    {"speaker": "Aiden", "language": "en", "gender": "male", "description": "明るいアメリカ英語の男性の声"},
    {"speaker": "Ono_Anna", "language": "ja", "gender": "female", "description": "快活な日本語の女性の声"},
    {"speaker": "Sohee", "language": "ko", "gender": "female", "description": "温かい韓国語の女性の声"},
)

SPEAKER_NAMES = frozenset(item["speaker"] for item in BUILT_IN_SPEAKERS)

# 話者の language は「母語」であって、話せる言語の全部ではない。実測で、英語や
# 中国語の話者に日本語を読ませても日本語になった。公式話者に日本語の男性が
# 居ないので、この事実が無いと日本語の男性キャラが立たない。
NON_NATIVE_NOTE = (
    "language は母語です。他の言語も喋れます（英語・中国語の話者に日本語を"
    "読ませて日本語になることを実測しました）。母語で使うのが最も良いと公式が"
    "推奨しているので、母語話者が居る組み合わせはそちらを優先してください。"
    "日本語の男性など母語話者が居ない場合は、非母語の話者を選んでください。"
)

# 公式が挙げている対応言語。ここに無いものは母語話者が居ない。
SUPPORTED_LANGUAGES = (
    "zh", "en", "ja", "ko", "de", "fr", "ru", "pt", "es", "it",
)

# design で声を確定させるときに読ませる文。
#
# 短すぎると声の特徴が乗らず、長すぎると確定に時間がかかる。公式は 3 秒の音声で
# 複製できるとしているので、それを超える長さの文を言語ごとに置く。内容は感情に
# 寄らないものにする——見本が怒っていると、その怒りごと複製される。
ANCHOR_TEXT: dict[str, str] = {
    "ja": "こんにちは。今日はよろしくお願いします。少しお話をさせてください。",
    "en": "Hello there. It is good to meet you. Let me tell you a little about today.",
    "zh": "你好，很高兴见到你。让我来介绍一下今天的情况。",
    "ko": "안녕하세요. 만나서 반갑습니다. 오늘 이야기를 조금 해보겠습니다.",
}
DEFAULT_ANCHOR_LANGUAGE = "en"


def anchor_text(language: str | None) -> str:
    return ANCHOR_TEXT.get(str(language or ""), ANCHOR_TEXT[DEFAULT_ANCHOR_LANGUAGE])


def catalog() -> list[dict[str, Any]]:
    return [dict(item) for item in BUILT_IN_SPEAKERS]
