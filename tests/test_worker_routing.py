import pytest

from sonicforge.config import load_settings
from sonicforge.workers import WorkerError, _worker_environment, route


def test_external_worker_command_rejects_unrepresented_extra_args(env, monkeypatch):
    monkeypatch.setenv("SONICFORGE_ENABLE_FAKE", "0")
    monkeypatch.setenv(
        "SONICFORGE_GAME_AUDIO_COMMAND",
        "/usr/bin/python3 /tmp/worker.py --unexpected-option",
    )
    settings = load_settings()

    with pytest.raises(WorkerError, match="optional script only"):
        route(settings, "audio.sfx.generate", "auto")


def test_external_worker_command_supports_executable_and_script(env, monkeypatch):
    monkeypatch.setenv("SONICFORGE_ENABLE_FAKE", "0")
    monkeypatch.setenv(
        "SONICFORGE_GAME_AUDIO_COMMAND",
        "/usr/bin/python3 /tmp/worker.py",
    )
    settings = load_settings()

    engine, executable, script = route(settings, "audio.sfx.generate", "auto")
    assert engine == "external"
    assert str(executable) == "/usr/bin/python3"
    assert str(script) == "/tmp/worker.py"


def test_worker_environment_keeps_ace_step_writes_out_of_source(env):
    settings = load_settings()

    worker_env = _worker_environment(settings)

    assert worker_env["ACESTEP_PROJECT_ROOT"] == str(settings.cache_dir / "ace-step")
    assert worker_env["ACESTEP_CHECKPOINTS_DIR"] == str(
        settings.models_dir / "ace-step"
    )
    assert worker_env["ACESTEP_PROJECT_ROOT"] != str(settings.repo_root)


def test_stable_audio_worker_is_cache_only_after_provisioning(env):
    settings = load_settings()

    worker_env = _worker_environment(settings, "audio.stable-audio-3")

    assert worker_env["HF_HUB_OFFLINE"] == "1"
    assert worker_env["TRANSFORMERS_OFFLINE"] == "1"


def test_gpt_sovits_worker_is_cache_only_after_provisioning(env):
    settings = load_settings()
    worker_env = _worker_environment(settings, "tts.gpt-sovits")

    assert worker_env["HF_HUB_OFFLINE"] == "1"
    assert worker_env["TRANSFORMERS_OFFLINE"] == "1"


def test_other_workers_do_not_inherit_stable_audio_offline_policy(env):
    settings = load_settings()

    worker_env = _worker_environment(settings, "music.ace-step-1.5")

    assert "HF_HUB_OFFLINE" not in worker_env
    assert "TRANSFORMERS_OFFLINE" not in worker_env


def test_gpt_sovits_uses_its_own_runtime(env, monkeypatch):
    monkeypatch.setenv("SONICFORGE_ENABLE_FAKE", "0")
    settings = load_settings()
    runtime_python = settings.runtime_dir / "speech-gpt-sovits-rocm/bin/python"
    runtime_python.parent.mkdir(parents=True)
    runtime_python.write_text("a" * 64, encoding="utf-8")

    engine, executable, script = route(
        settings, "speech.tts.synthesize", "ja", "tts.gpt-sovits"
    )

    assert engine == "tts.gpt-sovits"
    assert executable == runtime_python
    assert script.name == "worker.py"
    assert script.parent.name == "gpt_sovits"


def test_music_worker_is_told_how_much_vram_it_may_use(env):
    """ACE-Step はカード全体の容量だけを見て構成を決める。

    31.86 GiB を見ると「独占できる」と判じ、オフロードも量子化も切って青天井で
    使う。他のプロセスが載っていることは考慮されない。実測（2026-09-06、R9700、
    GPU 単独占有、30 秒の生成）で 19,663 MiB まで伸びた。上限を渡すと 16,600 MiB。
    """
    settings = load_settings()

    worker_env = _worker_environment(settings, "music.ace-step-1.5")

    assert worker_env["MAX_CUDA_VRAM"] == "20"


def test_speech_workers_are_not_capped(env):
    """音声は 1.5〜4 GiB で収まる。上限を渡す理由が無いうえ、渡すと ACE-Step 以外の
    経路にも影響しかねない。"""
    settings = load_settings()

    for engine in ("tts.gpt-sovits", "audio.stable-audio-3"):
        assert "MAX_CUDA_VRAM" not in _worker_environment(settings, engine), engine
