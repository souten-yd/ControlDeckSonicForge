import json
from pathlib import Path
from jsonschema import Draft202012Validator

def test_addon_manifest_shape():
    m=json.loads(Path('addon.json').read_text()); assert m['api_version']=='2'; assert m['id']=='sonic-forge'; assert [x['id'] for x in m['contributions']['setup_checklist']]==['core','speech-essentials','game-audio','music']; assert len(m['contributions']['workflow_executors'])==4; assert len(m['contributions']['agent_tools'])==5

def test_json_schemas_are_valid():
    for p in Path('schemas').glob('*.json'):
        Draft202012Validator.check_schema(json.loads(p.read_text()))
