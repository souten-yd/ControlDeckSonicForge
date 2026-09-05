import hashlib
import json
import os
import subprocess
import sys
from dataclasses import replace

import pytest

from sonicforge.config import ensure_directories, load_settings
from sonicforge.db import (
    Asset,
    Job,
    MeetingSegment,
    MeetingSession,
    Provenance,
    SetupComponent,
    Voice,
    make_session_factory,
)
from sonicforge.legacy_data import LegacyDataError, discover_legacy_data_dirs, import_legacy_data


def _settings(data_dir):
    value = replace(load_settings(), data_dir=data_dir)
    ensure_directories(value)
    return value


def test_discovers_only_known_managed_legacy_location(tmp_path, monkeypatch):
    managed = tmp_path / "data" / "feature-data" / "sonic-forge"
    legacy = tmp_path / "data" / "sonicforge"
    legacy.mkdir(parents=True)
    (legacy / "sonicforge.db").write_bytes(b"legacy")
    monkeypatch.setenv("CONTROL_DECK_FEATURE_DATA_DIR", str(managed))
    monkeypatch.delenv("SONICFORGE_DATA_DIR", raising=False)
    monkeypatch.delenv("SONICFORGE_LEGACY_DATA_DIR", raising=False)

    assert discover_legacy_data_dirs(load_settings()) == [legacy.resolve()]


def test_legacy_user_data_is_merged_once_without_runtime_state(env):
    current = _settings(env / "managed")
    legacy = _settings(env / "legacy")
    current_factory = make_session_factory(current)
    legacy_factory = make_session_factory(legacy)

    asset_bytes = b"RIFF legacy asset bytes"
    (legacy.assets_dir / "old.wav").write_bytes(asset_bytes)
    voice_bytes = b"RIFF legacy voice bytes"
    (legacy.data_dir / "voices" / "reference.wav").write_bytes(voice_bytes)
    with legacy_factory() as session:
        session.add_all([
            Job(id="job:legacy", task="speech.tts.synthesize", state="succeeded", progress=1.0),
            Provenance(id="prov:legacy", operation="speech.tts.synthesize", engine_id="fake"),
            Asset(
                id="asset:legacy", kind="audio", mime_type="audio/wav",
                relative_path="assets/old.wav", size_bytes=len(asset_bytes),
                sha256=hashlib.sha256(asset_bytes).hexdigest(), job_id="job:legacy",
                provenance_id="prov:legacy",
            ),
            Voice(
                id="voice:legacy", name="Legacy voice", source_type="clone",
                languages=["ja"], recipe={"reference_audio": "voices/reference.wav"},
                rights_confirmed=True,
            ),
            MeetingSession(id="meeting:legacy", title="Old meeting", state="completed"),
            SetupComponent(id="speech-essentials", state="missing", detail={"old": True}),
        ])
        session.commit()
        session.add(MeetingSegment(
            meeting_id="meeting:legacy", sequence=0, start_ms=0, end_ms=1000,
            source_language="ja", source_text="古い議事録",
        ))
        session.commit()

    with current_factory() as session:
        session.add_all([
            Job(id="job:current", task="music.generate", state="succeeded", progress=1.0),
            SetupComponent(id="speech-essentials", state="available", detail={"current": True}),
        ])
        session.commit()

    report = import_legacy_data(current, legacy.data_dir)
    assert report is not None
    assert report["inserted"]["jobs"] == 1
    assert report["inserted"]["assets"] == 1
    assert report["inserted"]["voices"] == 1
    assert report["inserted"]["meeting_sessions"] == 1
    assert report["inserted"]["meeting_segments"] == 1
    assert report["copied_files"] == 2
    assert report["legacy_source_preserved"] is True
    assert import_legacy_data(current, legacy.data_dir) is None

    with current_factory() as session:
        assert session.get(Job, "job:current") is not None
        assert session.get(Job, "job:legacy") is not None
        assert session.get(Asset, "asset:legacy") is not None
        assert session.get(Voice, "voice:legacy") is not None
        setup = session.get(SetupComponent, "speech-essentials")
        assert setup.state == "available"
        assert setup.detail == {"current": True}

    assert (current.assets_dir / "old.wav").read_bytes() == asset_bytes
    assert (current.data_dir / "voices" / "reference.wav").read_bytes() == voice_bytes
    assert (legacy.assets_dir / "old.wav").read_bytes() == asset_bytes
    marker = next((current.data_dir / "migrations").glob("legacy-data-v1-*.json"))
    assert json.loads(marker.read_text(encoding="utf-8"))["source"] == str(legacy.data_dir.resolve())
    assert list((current.data_dir / "backups").glob("sonicforge-before-legacy-v1-*.db"))


def test_invalid_legacy_asset_does_not_change_current_database(env):
    current = _settings(env / "managed-invalid")
    legacy = _settings(env / "legacy-invalid")
    current_factory = make_session_factory(current)
    legacy_factory = make_session_factory(legacy)
    with current_factory() as session:
        session.add(Job(id="job:current", task="music.generate", state="succeeded", progress=1.0))
        session.commit()
    (legacy.assets_dir / "broken.wav").write_bytes(b"wrong")
    with legacy_factory() as session:
        session.add_all([
            Job(id="job:legacy", task="speech.tts.synthesize", state="succeeded", progress=1.0),
            Provenance(id="prov:legacy", operation="speech.tts.synthesize", engine_id="fake"),
            Asset(
                id="asset:legacy", kind="audio", mime_type="audio/wav",
                relative_path="assets/broken.wav", size_bytes=5, sha256="0" * 64,
                job_id="job:legacy", provenance_id="prov:legacy",
            ),
        ])
        session.commit()

    with pytest.raises(LegacyDataError, match="does not match"):
        import_legacy_data(current, legacy.data_dir)
    with current_factory() as session:
        assert session.get(Job, "job:current") is not None
        assert session.get(Job, "job:legacy") is None
        assert session.get(Asset, "asset:legacy") is None
    assert not list((current.data_dir / "migrations").glob("legacy-data-v1-*.json"))


def test_app_startup_automatically_imports_configured_legacy_data(env):
    legacy = _settings(env / "startup-legacy")
    legacy_factory = make_session_factory(legacy)
    with legacy_factory() as session:
        session.add(Job(id="job:startup-legacy", task="music.generate", state="succeeded", progress=1.0))
        session.commit()
    process_env = os.environ.copy()
    process_env.update({
        "SONICFORGE_DATA_DIR": str(env / "data"),
        "SONICFORGE_CACHE_DIR": str(env / "cache"),
        "SONICFORGE_LEGACY_DATA_DIR": str(legacy.data_dir),
        "SONICFORGE_ENABLE_FAKE": "1",
        "SONICFORGE_SETUP_TEST_MODE": "1",
    })
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import json; import sonicforge.app as app; "
                "from sonicforge.db import Job; "
                "s=app.session_factory(); "
                "print(json.dumps({'found': s.get(Job, 'job:startup-legacy') is not None, "
                "'reports': app.legacy_data_imports})); s.close()"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=process_env,
    )
    observed = json.loads(result.stdout)
    assert observed["found"] is True
    assert observed["reports"][0]["inserted"]["jobs"] == 1
