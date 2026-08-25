import pytest

from sonicforge.config import load_settings
from sonicforge.workers import WorkerError, route


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
