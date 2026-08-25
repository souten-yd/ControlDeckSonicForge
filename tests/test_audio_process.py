import json
import zipfile
from pathlib import Path

import pytest

from sonicforge.audio_process import process_argv
from sonicforge.pipeline_package import create_package, package_filename
from sonicforge.workers import WorkerError


def test_audio_process_builds_fixed_ffmpeg_argv_without_shell_tokens(tmp_path):
    source = tmp_path / "input.wav"
    target = tmp_path / "output.wav"
    argv = process_argv(
        "/usr/bin/ffmpeg",
        source,
        target,
        {
            "trim_start_sec": 1.25,
            "duration_sec": 3.5,
            "gain_db": -3,
            "normalize": True,
            "sample_rate": 48000,
            "channels": 1,
        },
    )
    assert argv[0] == "/usr/bin/ffmpeg"
    assert "-ss" in argv and "1.250000" in argv
    assert "-t" in argv and "3.500000" in argv
    assert "volume=-3.000dB,loudnorm=I=-16:TP=-1.5:LRA=11" in argv
    assert argv[-5:] == ["-ac", "1", "-c:a", "pcm_s16le", str(target)]
    assert not any(value in {"sh", "bash", "-c"} for value in argv)


def test_audio_process_rejects_unknown_and_out_of_range_parameters(tmp_path):
    with pytest.raises(WorkerError, match="unsupported parameters"):
        process_argv("ffmpeg", tmp_path / "in.wav", tmp_path / "out.wav", {"raw_args": "-f null"})
    with pytest.raises(WorkerError, match="channels"):
        process_argv("ffmpeg", tmp_path / "in.wav", tmp_path / "out.wav", {"channels": 8})


def test_pipeline_package_contains_audio_and_canonical_manifest(tmp_path):
    audio = tmp_path / "voice.wav"
    audio.write_bytes(b"RIFF-test-audio")
    target = tmp_path / "bundle.zip"
    manifest = {
        "schema_version": 1,
        "type": "sonicforge.pipeline-package",
        "audio": {"asset_id": "asset:1", "sha256": "abc"},
    }
    meta = create_package(
        source_audio=audio,
        target=target,
        audio_name="voice.wav",
        manifest=manifest,
    )
    assert meta["mime_type"] == "application/zip"
    assert meta["size_bytes"] == target.stat().st_size
    assert len(meta["sha256"]) == 64
    with zipfile.ZipFile(target) as archive:
        assert archive.namelist() == ["audio/voice.wav", "manifest.json"]
        assert archive.read("audio/voice.wav") == audio.read_bytes()
        decoded = json.loads(archive.read("manifest.json"))
        assert decoded == manifest


def test_package_filename_is_plain_and_forces_zip_extension():
    assert package_filename(None) == "sonicforge-package.zip"
    assert package_filename("game-audio.tar") == "game-audio.zip"
    with pytest.raises(WorkerError):
        package_filename("../escape.zip")
