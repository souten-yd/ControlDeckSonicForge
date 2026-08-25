import asyncio

from sonicforge import setup
from sonicforge.config import ensure_directories, load_settings
from sonicforge.db import make_session_factory


def test_setup_plan_and_idempotent_apply(env):
    settings = load_settings()
    ensure_directories(settings)
    factory = make_session_factory(settings)
    plan = setup.plan(settings, "speech-essentials")
    assert plan["components"][0]["id"] == "speech-essentials"
    assert plan["components"][0]["models"] == [
        setup.QWEN_CUSTOM_VOICE,
        setup.QWEN_CLONE_BASE,
        setup.QWEN_VOICE_DESIGN,
        setup.KOTOBA_WHISPER,
        setup.WHISPER_TURBO,
    ]
    assert setup.QWEN_VOICE_DESIGN == "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"

    with factory() as session:
        first = asyncio.run(setup.apply(settings, session, "speech-essentials"))
    with factory() as session:
        second = asyncio.run(setup.apply(settings, session, "speech-essentials"))
        state = setup.status(session)

    assert state["state"] == "available"
    assert first["components"][0]["installed"]
    assert second["components"][0]["installed"]


def test_game_audio_plan_prefetches_gated_small_sfx_after_terms(env):
    settings = load_settings()
    ensure_directories(settings)
    plan = setup.plan(settings, "game-audio")

    component = plan["components"][0]
    assert component["id"] == "game-audio"
    assert component["runtime_id"] == "game-audio-cpu"
    assert component["models"] == [setup.STABLE_AUDIO_SMALL_SFX]
    assert component["terms"] == [setup.STABILITY_TERMS]
    assert setup.STABLE_AUDIO_SMALL_SFX == "stabilityai/stable-audio-3-small-sfx"


def test_music_plan_prepares_upstream_ace_step_models(env, monkeypatch):
    settings = load_settings()
    ensure_directories(settings)
    monkeypatch.setattr(setup, "detect_backend", lambda: "rocm")

    plan = setup.plan(settings, "music")
    component = plan["components"][0]
    assert component["id"] == "music"
    assert component["runtime_id"] == "music-rocm"
    assert component["models"] == [setup.ACESTEP_DIT, setup.ACESTEP_LM]
    assert setup.ACESTEP_DIT == "acestep-v15-turbo"
    assert setup.ACESTEP_LM == "acestep-5Hz-lm-0.6B"
