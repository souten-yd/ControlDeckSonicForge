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
