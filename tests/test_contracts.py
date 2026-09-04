import json
from pathlib import Path
from jsonschema import Draft202012Validator

def test_addon_manifest_shape():
    m=json.loads(Path('addon.json').read_text()); assert m['api_version']=='2'; assert m['id']=='sonic-forge'; assert [x['id'] for x in m['contributions']['setup_checklist']]==['core','speech-essentials','game-audio','music']; assert len(m['contributions']['workflow_executors'])==4; assert len(m['contributions']['agent_tools'])==6; assert 'sonic.pipeline' in {x['id'] for x in m['contributions']['agent_tools']}; assert m['contributions']['embedded_views'][0]['mobile']=='embedded'

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
