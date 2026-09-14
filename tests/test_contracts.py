import json
from pathlib import Path
from jsonschema import Draft202012Validator

def test_addon_manifest_shape():
    m=json.loads(Path('addon.json').read_text()); assert m['api_version']=='2'; assert m['id']=='sonic-forge'; assert [x['id'] for x in m['contributions']['setup_checklist']]==['core','speech-essentials','game-audio','music']; assert len(m['contributions']['workflow_executors'])==4; assert len(m['contributions']['agent_tools'])==10; assert {'sonic.pipeline','sonic.generate.batch','sonic.voice.create','sonic.voice.list','sonic.voice.delete'} <= {x['id'] for x in m['contributions']['agent_tools']}; assert m['contributions']['embedded_views'][0]['mobile']=='embedded'

def test_json_schemas_are_valid():
    for p in Path('schemas').glob('*.json'):
        Draft202012Validator.check_schema(json.loads(p.read_text()))

def test_agent_inspect_schema_accepts_exactly_one_reference_kind():
    schema=json.loads(Path('schemas/asset-reference.json').read_text())
    validator=Draft202012Validator(schema)
    assert not list(validator.iter_errors({"asset_id":"asset:abc"}))
    assert not list(validator.iter_errors({"job_id":"job:abc"}))
    assert list(validator.iter_errors({}))
    assert list(validator.iter_errors({"asset_id":"asset:abc","job_id":"job:abc"}))


def test_the_generate_schema_tells_agents_what_music_takes():
    """input の中身を説明していなかったので、呼び出し側は曲調も長さも BPM も
    指定できることを知りようがなかった（実機の OpenCode は task と quality だけを
    送っていた）。契約に書いておく。"""
    import json
    from pathlib import Path

    schema = json.loads(
        (Path(__file__).resolve().parents[1] / "schemas/generate-request.json").read_text(
            encoding="utf-8"
        )
    )
    fields = schema["properties"]["input"]["properties"]

    assert {"prompt", "duration_sec", "bpm", "instrumental"} <= set(fields)
    assert "曲調" in fields["prompt"]["description"]
    assert "30 秒" in fields["duration_sec"]["description"]
    # 読まない項目は受け取らない。名前を間違えた要求が既定値で作られない。
    assert schema["properties"]["input"]["additionalProperties"] is False


def test_unknown_input_fields_are_refused_instead_of_ignored():
    """duration_seconds と書いた 20 秒の依頼が duration_sec と読まれず、既定の
    30 秒で作られた。頼んだ側からは違いが見えない。"""
    import pytest

    from sonicforge.schemas import TaskRequest

    ok = TaskRequest.model_validate({
        "task": "music.generate",
        "input": {"prompt": "8-bit inn theme", "bpm": 95, "duration_sec": 20},
    })
    assert ok.input["bpm"] == 95

    with pytest.raises(Exception) as error:
        TaskRequest.model_validate({
            "task": "music.generate",
            "input": {"prompt": "x", "duration_seconds": 20},
        })
    assert "duration_seconds" in str(error.value)


def test_vocal_music_requires_lyrics_instead_of_silently_dropping_the_vocal():
    """instrumental=false だけで歌を頼むと、歌わずに伴奏が返る。

    ACE-Step の lyrics 既定は空文字で、空のまま歌えと言われたモデルは伴奏だけを
    返す。ジョブは成功し長さも合っているので、頼んだ側からは「歌を頼んだのに
    歌っていない」としか見えない（実測 2026-09-14: instrumental=false で作った
    30 秒を聴いて「歌に聞こえない。音楽だけ」）。黙って伴奏を返さず、何が
    足りないかを言って断る。
    """
    import pytest

    from sonicforge.schemas import TaskRequest

    sung = TaskRequest.model_validate({
        "task": "music.generate",
        "input": {"prompt": "boss theme", "instrumental": False,
                  "lyrics": "[chorus]\nrise into the light", "vocal_language": "en"},
    })
    assert sung.input["lyrics"].startswith("[chorus]")

    with pytest.raises(Exception) as error:
        TaskRequest.model_validate({
            "task": "music.generate",
            "input": {"prompt": "boss theme", "instrumental": False},
        })
    assert "lyrics" in str(error.value)


def test_lyrics_without_instrumental_false_are_refused_too():
    """逆向きの取り違えも黙って捨てない。

    歌詞を書いたのに instrumental が既定の true のままだと、ACE-Step は
    歌詞を無視する。こちらも「書いたのに歌わない」に見える。
    """
    import pytest

    from sonicforge.schemas import TaskRequest

    with pytest.raises(Exception) as error:
        TaskRequest.model_validate({
            "task": "music.generate",
            "input": {"prompt": "boss theme", "lyrics": "la la la"},
        })
    assert "instrumental" in str(error.value)


def test_vocal_language_is_limited_to_values_the_model_can_sing():
    """対応表の外の言語は歌わせ方を壊すので、入口で断る。"""
    import pytest

    from sonicforge.schemas import TaskRequest

    ok = TaskRequest.model_validate({
        "task": "music.generate",
        "input": {"prompt": "theme", "instrumental": False,
                  "lyrics": "夜を駆けて", "vocal_language": "ja"},
    })
    assert ok.input["vocal_language"] == "ja"

    with pytest.raises(Exception) as error:
        TaskRequest.model_validate({
            "task": "music.generate",
            "input": {"prompt": "theme", "instrumental": False,
                      "lyrics": "x", "vocal_language": "klingon"},
        })
    assert "vocal_language" in str(error.value)


def test_music_schema_publishes_the_lyrics_contract():
    """契約に出ていない項目は、呼ぶ側からは存在しないのと同じである。"""
    import json
    from pathlib import Path

    schema = json.loads(
        (Path(__file__).resolve().parents[1] / "schemas" / "generate-request.json")
        .read_text(encoding="utf-8")
    )
    fields = schema["properties"]["input"]["properties"]
    assert {"lyrics", "vocal_language"} <= set(fields)
    # 「instrumental を false にするだけでは歌にならない」ことが説明に要る。
    assert "instrumental" in fields["lyrics"]["description"]
    assert "auto" in fields["vocal_language"]["enum"]
    assert "ja" in fields["vocal_language"]["enum"]


def test_loop_is_reachable_everywhere_it_is_claimed():
    """申告だけある機能は、使う側からは「頼める」と読める。

    loop は capabilities に出ていたのに、受け取る入口（INPUT_FIELDS）も、繋ぎ目を
    作る処理も無かった。実測 2026-09-14: ループ前提の BGM を 30 曲頼まれて、
    ループにならないまま出来上がった。申告する以上は端まで通す。
    """
    from sonicforge.schemas import INPUT_FIELDS

    for task in ("audio.sfx.generate", "audio.ambience.generate", "music.generate"):
        assert "loop" in INPUT_FIELDS[task]


def test_pipeline_only_forwards_fields_the_request_validator_accepts():
    """pipeline が組み立てた要求が、自分の検証に弾かれない。

    SFX 段は loop と category を通していたが、どちらも INPUT_FIELDS に無かったので、
    その段を含む pipeline は未知項目として全体が止まる。
    """
    import inspect

    from sonicforge import pipeline_runtime
    from sonicforge.schemas import INPUT_FIELDS

    source = inspect.getsource(pipeline_runtime)
    start = source.index('"task": "audio.sfx.generate"')
    forwarded = set(
        item.strip().strip('"')
        for item in source[start:start + 700].split("if key in {", 1)[1].split("}", 1)[0].split(",")
        if item.strip()
    )
    assert forwarded <= INPUT_FIELDS["audio.sfx.generate"], (
        f"pipeline が通す {sorted(forwarded)} は受け取れる項目の外にある"
    )


def test_loop_crossfade_shortens_the_material_and_says_by_how_much():
    """重ねたぶんだけ短くなる。長さの決め方を数字で固定する。"""
    import pytest

    from sonicforge import audio_loop
    from sonicforge.workers import WorkerError

    # 30 秒なら既定の 1.5 秒を重ねる。
    assert audio_loop.crossfade_seconds(30.0) == pytest.approx(1.5)
    # 短い素材では全体の 1/4 で頭打ち。溶かしすぎて輪郭を失わせない。
    assert audio_loop.crossfade_seconds(2.0) == pytest.approx(0.5)

    argv = audio_loop.loop_argv(
        "/usr/bin/ffmpeg", Path("in.wav"), Path("out.wav"), 30.0
    )
    graph = argv[argv.index("-filter_complex") + 1]
    assert "[0:a][1:a]acrossfade" in graph
    # 切り出しは入力側で行う。filter の atrim から acrossfade へ渡すと出力が
    # 0 秒になる（実測: 30 秒の素材から 0.0 秒）。
    assert "atrim" not in graph
    assert argv.count("-i") == 2 and argv.count("-ss") == 2
    # shell を通さない。引数は 1 つずつ渡す。
    assert all(isinstance(item, str) for item in argv)

    # 重ねる余地の無い素材は断る。元の断片を返さない。
    with pytest.raises(WorkerError):
        audio_loop.loop_argv("/usr/bin/ffmpeg", Path("in.wav"), Path("out.wav"), 0.2)


def test_loop_contract_warns_that_the_result_gets_shorter():
    """頼んだ長さと違うものが返るなら、契約にそう書く。"""
    import json
    from pathlib import Path as P

    schema = json.loads(
        (P(__file__).resolve().parents[1] / "schemas" / "generate-request.json")
        .read_text(encoding="utf-8")
    )
    description = schema["properties"]["input"]["properties"]["loop"]["description"]
    assert "短くなる" in description


def test_transcription_accepts_an_asset_sonicforge_already_holds():
    """自分で作った音も書き起こせる。

    sonic.inspect は長さと状態しか返さず「言葉は sonic.transcribe で」と案内するのに、
    その transcribe が asset を受け取らなかった。
    """
    import pytest

    from sonicforge.schemas import TaskRequest

    ok = TaskRequest.model_validate({
        "task": "speech.asr.transcribe",
        "input": {"asset_id": "asset:4b6d01c2-c941-4fa3-8048-368c3a930a33"},
    })
    assert ok.input["asset_id"].startswith("asset:")

    with pytest.raises(Exception) as error:
        TaskRequest.model_validate({
            "task": "speech.asr.transcribe", "input": {"asset_id": "not-an-asset"},
        })
    assert "asset" in str(error.value)


def test_transcribe_schema_publishes_where_the_audio_comes_from():
    """input が {"type": "object"} だけでは、呼ぶ側は当てるしかない。"""
    import json
    from pathlib import Path

    schema = json.loads(
        (Path(__file__).resolve().parents[1] / "schemas" / "speech-transcribe-request.json")
        .read_text(encoding="utf-8")
    )
    fields = schema["properties"]["input"]["properties"]
    assert {"asset_id", "upload_id", "grant_id"} <= set(fields)
    assert schema["properties"]["input"]["additionalProperties"] is False
