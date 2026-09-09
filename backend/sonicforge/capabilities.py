from __future__ import annotations

from sqlalchemy.orm import Session

from . import __version__
from .db import SetupComponent


def _state(session: Session, component: str) -> str:
    row = session.get(SetupComponent, component)
    return row.state if row else "missing"


def capability_document(session: Session, *, fake_enabled: bool = False) -> dict:
    speech = _state(session, "speech-essentials") == "available" or fake_enabled
    game = _state(session, "game-audio") == "available" or fake_enabled
    music = _state(session, "music") == "available" or fake_enabled
    def entry(cid: str, available: bool, features: dict, optional: bool = False) -> dict:
        return {
            "id": cid,
            "state": "available" if available else "setup_required",
            "quality_tier": "recommended" if available else "experimental",
            "reason_code": None if available else "component_not_installed",
            "reason": None if available else ("Optional pack is not installed" if optional else "Speech Essentials is not installed"),
            "features": features,
            "limits": {},
        }
    return {
        "api_version": "1",
        "service": {"id": "sonic-forge", "version": __version__, "state": "available" if speech else "setup_required"},
        "setup": {
            "state": "available" if speech else "setup_required",
            "profile": "speech-essentials" if speech else None,
            "components": [
                {"id":"core","state":"available"},
                {"id":"speech-essentials","state":"available" if speech else "setup_required"},
                {"id":"game-audio","state":"available" if game else "setup_required"},
                {"id":"music","state":"available" if music else "setup_required"},
            ],
        },
        "capabilities": [
            entry("speech.tts.synthesize", speech, {"languages":["ja","en"],"streaming":False,"voice_clone":True,"style_control":True}),
            entry("speech.asr.transcribe", speech, {"languages":["ja","en"],"timestamps":["segment"],"streaming":False}),
            entry("speech.localization.batch", speech, {"languages":["ja","en"],"paired_lines":True}),
            entry("audio.sfx.generate", game, {"variations":True,"loop":True}, optional=True),
            entry("audio.ambience.generate", game, {"variations":True,"loop":True}, optional=True),
            entry("music.generate", music, {"instrumental":True,"bpm_hint":True,"loop":True}, optional=True),
        ],
        "routing": {"default_language":"auto","default_quality":"balanced","advanced_engine_pinning":True},
        # 使う側は道具の一覧しか見ずに選ぶことがある。一覧に出るのは一行の説明だけ
        # なので、順番（声を作ってから喋らせる）と、声を作らないと台詞ごとに別人に
        # なることが読み取れない。迷ったら最初に叩かれるのがここなので、手順を置く。
        "character_voices": {
            "why": (
                "台詞ごとに sonic.generate を呼ぶと、そのたびに別の声で読まれうる。"
                "同じ人物が喋り続けるようにするには、先に声を作って voice_id を得る。"
            ),
            "steps": [
                "sonic.voice.list で、既にある声と公式話者を見る",
                "無ければ sonic.voice.create でキャラクターの声を作り、voice_id を受け取る",
                "sonic.generate.batch の各項目に voice_id と emotion を渡して台詞をまとめて作る",
            ],
            "methods": {
                "preset": (
                    "公式の名前つき話者 9 名から選ぶ。言い方を自然文で指定できる。"
                    "language は母語であって話せる言語の全部ではなく、非母語の話者にも"
                    "その言語を喋らせられる（日本語の男性など母語話者が居ない場合に使う）。"
                ),
                "design": (
                    "声を自然文で注文する。キャラクターごとに違う声が要るならこちら。"
                    "感情は作るときに用意した見本から選ぶ形になる。"
                ),
                "clone": "手元の音声から複製する。権利の確認と書き起こしが要る。",
            },
            "emotion": (
                "preset の声は input.emotion に自然文を書ける。design と clone の声は"
                "sonic.voice.list の emotion_choices にある名前から選ぶ。どちらの形かは"
                "supports_emotion で分かる。台詞の書き方も感情に揃えると最も自然になる"
                "——見本と台詞が食い違うと抑揚が崩れる。"
            ),
            "constraints": [
                "声の感情の見本は作るときに決まる。あとから足せないので、足すには作り直す",
                "design で作った声は注文文を覚えているが、呼び直しはしない。呼び直すと別人になる",
            ],
        },
    }
