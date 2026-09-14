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


def test_apply_loop_actually_shortens_a_real_file(tmp_path):
    """ループ加工を、引数の組み立てではなく通しで試す。

    前はこれが無かった。ffmpeg へ渡す引数の形だけを試験していて、呼び出し側が
    素材の長さをどう取るかを見ていなかった。inspect_wav が返すのは duration_ms
    なのに duration_sec を読んでいたため、実際には**どんな長さでも 0 秒と判じて
    「短すぎる」と断って**いた。実機で 120 秒の曲を頼んだ利用者に
    `audio is too short to loop` が出た。
    """
    import asyncio
    import shutil

    import pytest

    from sonicforge.audio import write_tone_wav
    from sonicforge.config import load_settings
    from sonicforge.jobs import JobManager
    from sonicforge.workers import WorkerResult

    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg is required for the loop post-process")

    # 端に無音を足した素材にする。ACE-Step の出力と同じ形で、削らずに重ねると
    # 継ぎ目に穴が残る。
    source = tmp_path / "source.wav"
    write_tone_wav(source, duration_sec=6.0, sample_rate=24000)
    _pad_with_silence(source, head_sec=0.5, tail_sec=0.5)

    manager = JobManager.__new__(JobManager)  # 後処理だけを見る
    result = WorkerResult(
        engine_id="test", engine_version="1", model_id="test",
        model_revision=None, model_license_id="test",
        output_path=source, payload={},
    )
    looped = asyncio.run(manager._apply_loop({"input": {"loop": True}}, result))

    assert looped.output_path is not None and looped.output_path.is_file()
    assert not source.exists(), "元の file は後片付けする"
    # 端の無音 1.0 秒を落として中身は 6 秒。重ねは 1.5 秒で、残るのは 4.5 秒。
    assert looped.payload["loop"] is True
    assert looped.payload["loop_crossfade_sec"] == pytest.approx(1.5)
    assert looped.payload["loop_trimmed_sec"] == pytest.approx(1.0, abs=0.15)
    assert looped.payload["duration_sec"] == pytest.approx(4.5, abs=0.15)


def test_apply_loop_leaves_the_file_alone_when_nobody_asked(tmp_path):
    """頼まれていなければ触らない。"""
    import asyncio

    from sonicforge.audio import write_tone_wav
    from sonicforge.jobs import JobManager
    from sonicforge.workers import WorkerResult

    source = tmp_path / "source.wav"
    write_tone_wav(source, duration_sec=6.0, sample_rate=24000)
    manager = JobManager.__new__(JobManager)
    result = WorkerResult(
        engine_id="test", engine_version="1", model_id="test",
        model_revision=None, model_license_id="test",
        output_path=source, payload={},
    )
    same = asyncio.run(manager._apply_loop({"input": {}}, result))
    assert same is result and source.is_file()


def test_edge_silence_is_trimmed_before_the_crossfade():
    """端の無音を削ってから重ねる。削らないと継ぎ目に穴が残る。

    ACE-Step は曲の頭と尻をフェードで作る。そのまま重ねると無音どうしが重なり、
    2 秒近い穴がそのまま残る（実測 2026-09-14: 118.5 秒のループ素材でループ点の
    手前 2 秒が RMS 0.00 倍。聴いた利用者の判定は「めっちゃ継ぎ目が空いてる」）。
    端を削ると同じ素材で最小 0.03 倍 → 0.23 倍になった。
    """
    from pathlib import Path

    from sonicforge import audio_loop

    scan = (
        "[silencedetect @ 0x1] silence_start: 0\n"
        "[silencedetect @ 0x1] silence_end: 0.8 | silence_duration: 0.8\n"
        "[silencedetect @ 0x1] silence_start: 29.2\n"
        "[silencedetect @ 0x1] silence_end: 30 | silence_duration: 0.8\n"
    )
    assert audio_loop.content_range(scan, 30.0) == (0.8, 29.2)

    # 曲の途中の休符は残す。そこを削ると別の曲になる。
    middle = (
        "[silencedetect @ 0x1] silence_start: 12\n"
        "[silencedetect @ 0x1] silence_end: 13 | silence_duration: 1\n"
    )
    assert audio_loop.content_range(middle, 30.0) == (0.0, 30.0)

    # 終わりまで無音のまま file が終わる形も拾う。
    unterminated = "[silencedetect @ 0x1] silence_start: 28.5\n"
    assert audio_loop.content_range(unterminated, 30.0) == (0.0, 28.5)

    # 端の判定が外れて削りすぎたら、元のまま扱う。
    everything = (
        "[silencedetect @ 0x1] silence_start: 0\n"
        "[silencedetect @ 0x1] silence_end: 29.9 | silence_duration: 29.9\n"
    )
    assert audio_loop.content_range(everything, 30.0) == (0.0, 30.0)

    # 削った範囲の中だけで重ねる。
    argv = audio_loop.loop_argv(
        "/usr/bin/ffmpeg", Path("in.wav"), Path("out.wav"), 30.0, content=(0.8, 29.2),
    )
    assert argv[argv.index("-ss") + 1] == "2.300000"  # 0.8 + 1.5
    assert "1.500000" in argv


def _pad_with_silence(path, *, head_sec: float, tail_sec: float) -> None:
    """前後に無音を足す。生成モデルのフェードを模す。"""
    import wave

    with wave.open(str(path), "rb") as source:
        params = source.getparams()
        frames = source.readframes(source.getnframes())
    quiet = b"\x00" * (params.sampwidth * params.nchannels)
    with wave.open(str(path), "wb") as target:
        target.setparams(params)
        target.writeframes(quiet * int(head_sec * params.framerate))
        target.writeframes(frames)
        target.writeframes(quiet * int(tail_sec * params.framerate))
