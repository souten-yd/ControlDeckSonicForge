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
    }
