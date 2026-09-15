"""内蔵話者の一覧と、キャラクターの声を確定させる手順。

Qwen3-TTS には声の出し方が三つある。どれを選ぶかで「同じキャラクターの声が
毎回同じか」が変わるので、そこを表にしておく。

  preset  公式の名前つき話者を使う。名前が identity なので毎回同じになる。
          ただし選べるのは 9 人で、言語ごとに 1〜2 人しか居ない。
  design  声を自然文で注文する（`generate_voice_design`）。作れる声の幅は
          広いが、identity を決めるのは **注文文と本文と乱数の三つ** である。
          どれか一つでも変わると別人になる。
  clone   参照音声から複製する（`generate_voice_clone`）。参照が同じなら
          同じ声になる。identity は参照の波形そのものである。

したがって「キャラクターの声を決めて、あとは同じ声で喋らせる」を成り立たせる
には、design を **ちょうど一度だけ・一本だけ** 呼んで見本を掴み、以後は clone
で回す。これが本モジュールが標準とする手順で、以下の実測に基づく。

seed を置けば design は再現する
-------------------------------
`torch.manual_seed()` を呼んでから `generate_voice_design()` すると、同じ
注文文・同じ本文・同じ seed は **バイト単位で同じ音** を返す。実測（本文と
注文文を固定し、seed=777 で 2 回）:

  seed なし 2 回  長さ 6.08s / 7.04s、波形の相関 0.0073 —— 別人
  seed=777 2 回   長さ 6.64s / 6.64s、sha256 一致、相関 1.0000 —— 同一

以前ここには「再現性の保証が無く seed も無い」と書いてあったが、それは seed を
渡していなかったときの挙動であって、モデルの限界ではない。声の定義には seed を
必ず残す。見本の音が失われても作り直せる。

本文が変われば seed を固定しても別人になる
-------------------------------------------
seed が固定しているのは乱数の系列であって、話者ではない。本文が変わると入力の
並びが変わるので、消費される乱数も変わる。実測（注文文と seed を固定し、本文
だけを差し替えて 4 本）:

  基本周波数の中央値  189 〜 228 Hz（同一人物なら動かない幅ではない）
  MFCC 平均の余弦     最小 0.695

**1 回の呼び出しに batch でまとめても同じである。** 感情別の見本を 4 本
まとめて 1 回で作っても、余弦は最小 0.703 で、別々に呼んだとき（0.695）と
変わらなかった。batch の各要素は独立した系列なので、本文が違えば話者も別に
落ちる。ここを取り違えると「感情ごとに別人のキャラクター」が出来る。

したがって design で作ってよい見本は **一本だけ** である。

見本は切り分けられない
----------------------
一本の長い見本を感情ごとに切り出す道は無い。このモデルは文の切れ目でも無音を
置かずに喋り続ける。実測で、29.52 秒の見本に対し -30dB / 0.10 秒でも無音区間は
0 箇所だった。

clone は ICL で使う。長さより本文の一致が効く
---------------------------------------------
`create_voice_clone_prompt` には二つの道がある。`x_vector_only_mode=True` は
話者埋め込みだけを使い、False なら参照音声とその書き起こしを両方渡す ICL に
なる。実測（同じ見本から同じ台詞を複製し、基準との MFCC 余弦で比較）:

  参照 3 秒   x-vector のみ  0.968
  参照 10 秒  x-vector のみ  0.959
  参照 30 秒  x-vector のみ  0.983
  参照 30 秒  ICL            0.983 〜 0.992

長さ単体の効きは小さい（3 秒で既に 0.968 に届き、10 秒はむしろ下がる）。効いて
いるのは ICL のほうである。見本はこちらが喋らせた文そのものが書き起こしなので、
ICL の条件が完全に揃う——人の録音を持ち込むときにはまず得られない条件である。

構造上の上限は約 2600 秒（43 分）で、実質どこにも当たらない。12Hz のコーデックが
参照 1 秒あたり 12.5 位置を使い、talker の max_position_embeddings が 32768 で
あることから出る（実測: 6.64 秒 → 83 フレーム × 16 codebook）。モデルカードの
"3-second voice cloning" は推奨であって上限ではない。

見本を長くする理由は、長さそのものではなく **状況の振れ幅を一本に収めるため**
である。平静から緊迫までを通した見本から複製すると、感情の乗った台詞でも
identity が保った（余弦 0.978 〜 0.993）。

感情は見本からの複製で作る
--------------------------
design を感情ごとに呼ぶことはできない（上記のとおり別人になる）。そこで感情別の
見本は、確定した identity の見本から **clone で** 作る。複製は喋り方も写すので、
感情の乗った文を複製の本文に渡せば、その口調の見本が手に入り、identity は
複製経路が保つ。

実測で確かめたこと（耳で判定。話者埋め込みの cos 類似度は物差しとして使えな
かった——別人でも 0.92 出る一方、同一人物が 0.99 で、差が 0.07 しかない。
MFCC 平均の余弦は別人 0.70 / 同一人物 0.98 と開くので、こちらを使う）:

  preset は instruct を変えても同じ人物のままだった。台詞を一字も変えずに
  「落ち着いて」「強い怒りをこめて」「悲しげに」と指示を振ったが、どれも同一
  人物に聞こえた。**preset だけが感情と同一性を instruct で両立する。**

  非母語の話者でも日本語を喋る。Ryan / Aiden（英語）と Dylan / Uncle_Fu
  （中国語）に日本語を読ませたところ、4 人とも日本語になった。公式話者に
  日本語の男性が居ないという欠けは、これで埋められる。母語で使うのが最も
  良いという公式の推奨は残るので、女性なら Ono_Anna を優先する。

  複製は喋り方も写す。怒った見本から複製すると、中立の台詞でも怒った口調に
  なった。これが design / clone の声に感情を与える唯一の道である。

  最も自然だったのは見本と台詞の感情を揃えたときだった。中立の見本に怒った
  台詞、怒った見本に中立の台詞と食い違わせると抑揚が崩れる。
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

# design で identity を確定させるときに読ませる文。**この一本が声そのものになる。**
#
# design は一度しか呼べない（本文が変われば別人になるため）ので、この一本で
# キャラクターの声域を決める。平静・注意・緊迫・安堵を通してあるのは、あとで
# 感情の乗った台詞を複製するときに、複製元が持っていない喋り方を要求しないため
# である。実測で、この形の見本から複製すると感情の乗った台詞でも identity が
# 保った（MFCC 余弦 0.978 〜 0.993）。
#
# 読みの割れる固有名詞と数字を避けてある。ICL では書き起こしと音が一致している
# ことが効くので、読みが揺れる語を入れると条件が崩れる。
ANCHOR_TEXT: dict[str, str] = {
    "ja": (
        "こんにちは。今日はよろしくお願いします。少しお話をさせてください。"
        "ここから先は、足元に気をつけて進んでください。"
        "待って。今、何か聞こえました。息を止めて、そのまま動かないで。"
        "……大丈夫、行ってしまったようです。"
        "よかった、本当によかった。これで先へ進めます。"
        "今日はここまでにしましょう。ゆっくり休んでください。"
    ),
    "en": (
        "Hello there. It is good to meet you. Let me tell you a little about today. "
        "From here on, watch your footing and keep close to the wall. "
        "Wait. I heard something just now. Hold your breath and do not move. "
        "It is all right. Whatever it was, it has gone. "
        "That is a relief, a real relief. We can go on from here. "
        "Let us stop for today. Get some rest, you have earned it."
    ),
    "zh": (
        "你好，很高兴见到你。让我来介绍一下今天的情况。"
        "从这里往前走，注意脚下，靠着墙走。"
        "等一下。我刚才听到了什么。屏住呼吸，别动。"
        "没事了，不管是什么，已经走远了。"
        "太好了，真是太好了。我们可以继续往前走。"
        "今天就到这里吧。好好休息一下。"
    ),
    "ko": (
        "안녕하세요. 만나서 반갑습니다. 오늘 이야기를 조금 해보겠습니다. "
        "여기서부터는 발밑을 조심하면서 벽을 따라 걸어 주세요. "
        "잠깐만요. 방금 무슨 소리가 들렸어요. 숨을 참고, 움직이지 마세요. "
        "괜찮아요. 무엇이었든 이미 지나갔어요. "
        "다행이에요, 정말 다행이에요. 이제 앞으로 나아갈 수 있어요. "
        "오늘은 여기까지 하죠. 푹 쉬세요."
    ),
}
DEFAULT_ANCHOR_LANGUAGE = "en"

# design を呼ぶときの既定の seed。
#
# seed を置けば design はバイト単位で再現する（実測: 同じ注文文・同じ本文・
# seed=777 で 2 回、sha256 一致）。声の定義には必ず seed を残す——見本の音が
# 失われても、注文文と本文と seed があれば同じ声を作り直せる。
DEFAULT_DESIGN_SEED = 777

# seed として受け付ける範囲。torch.manual_seed が受ける範囲に収める。
DESIGN_SEED_MIN = 0
DESIGN_SEED_MAX = 2**31 - 1

# 感情別の見本を作るときに、**複製に読ませる**文。
#
# design を感情ごとに呼ぶことはできない。本文が変われば別人になり、1 回の呼び出しに
# batch でまとめても変わらない（実測: 平静/喜/怒/哀を 1 回でまとめて作り、MFCC 余弦は
# 最小 0.703。別々に呼んだとき 0.695 と同じ水準）。
#
# そこで identity を決める見本を design で一本だけ作り、感情別の見本は **その見本から
# clone で** 作る。複製は喋り方も写すので、感情の乗った文を複製の本文に渡せば、その
# 口調の見本が手に入る。identity は複製経路が保つ（実測: 余弦 0.978 〜 0.993）。
#
# neutral は identity の見本そのものを使う。切り分けではなく、複製もしない。
#
# 読みの割れる固有名詞や数字を避けてある。ICL は書き起こしと音の一致で効くため。
EMOTIONS: tuple[str, ...] = ("neutral", "joy", "anger", "sorrow")

EMOTION_ANCHOR_TEXT: dict[str, dict[str, str]] = {
    "ja": {
        "neutral": ANCHOR_TEXT["ja"],
        "joy": "やった、ついにできた。本当に嬉しいよ、ずっと待っていたんだ。",
        "anger": "ふざけるな。何度言えば分かるんだ、いい加減にしてくれ。",
        "sorrow": "もう、どうしようもないんだ。全部、僕のせいだったんだよ。",
    },
    "en": {
        "neutral": ANCHOR_TEXT["en"],
        "joy": "We did it, we finally did it. I am so happy, I have waited so long for this.",
        "anger": "That is enough. How many times do I have to say it before you listen to me?",
        "sorrow": "There is nothing left to do. All of it was my fault, and I knew it.",
    },
    "zh": {
        "neutral": ANCHOR_TEXT["zh"],
        "joy": "太好了，终于成功了。我真的很开心，等了这么久。",
        "anger": "别开玩笑了。我说了多少遍你才明白，够了。",
        "sorrow": "已经没有办法了。全都是我的错，我一直都知道。",
    },
    "ko": {
        "neutral": ANCHOR_TEXT["ko"],
        "joy": "해냈어요, 드디어 해냈어요. 정말 기뻐요, 오래 기다렸거든요.",
        "anger": "장난치지 마세요. 몇 번을 말해야 알아듣나요, 이제 그만하세요.",
        "sorrow": "이제 어쩔 수가 없어요. 전부 제 잘못이었어요.",
    },
}

# 使う側が書いてくる言い方を、持っている見本に寄せる。preset は instruct に何でも
# 書けるが、design と clone は「持っている見本の分だけ」しか出せない。当たらな
# かったものは neutral に落とす——黙って別の感情を出すより、平静に読むほうがよい。
_EMOTION_SYNONYMS: dict[str, str] = {
    "neutral": "neutral", "平静": "neutral", "普通": "neutral", "calm": "neutral",
    "落ち着": "neutral", "淡々": "neutral", "flat": "neutral", "normal": "neutral",
    "joy": "joy", "happy": "joy", "喜": "joy", "嬉": "joy", "楽し": "joy",
    "明る": "joy", "excited": "joy", "cheerful": "joy",
    "anger": "anger", "angry": "anger", "怒": "anger", "激": "anger",
    "furious": "anger", "mad": "anger",
    "sorrow": "sorrow", "sad": "sorrow", "哀": "sorrow", "悲": "sorrow",
    "沈ん": "sorrow", "寂し": "sorrow", "depressed": "sorrow",
}


def emotion_anchor_text(language: str | None, emotion: str) -> str:
    table = EMOTION_ANCHOR_TEXT.get(str(language or ""), EMOTION_ANCHOR_TEXT[DEFAULT_ANCHOR_LANGUAGE])
    return table.get(emotion, table["neutral"])


def normalize_emotion(value: str | None, available: list[str] | tuple[str, ...]) -> str:
    """書かれた言い方を、その声が持っている見本の名前に寄せる。

    当たらなければ neutral。available に neutral すら無ければ最初の一つ。
    """
    text = str(value or "").strip().lower()
    matched = ""
    if text:
        for needle, label in _EMOTION_SYNONYMS.items():
            if needle in text:
                matched = label
                break
    if matched and matched in available:
        return matched
    if "neutral" in available:
        return "neutral"
    return available[0] if available else "neutral"


def anchor_text(language: str | None) -> str:
    return ANCHOR_TEXT.get(str(language or ""), ANCHOR_TEXT[DEFAULT_ANCHOR_LANGUAGE])


def catalog() -> list[dict[str, Any]]:
    return [dict(item) for item in BUILT_IN_SPEAKERS]
