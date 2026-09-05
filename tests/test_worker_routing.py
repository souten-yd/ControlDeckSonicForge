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
