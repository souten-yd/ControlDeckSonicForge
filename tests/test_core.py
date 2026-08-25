import importlib, sys, time
from fastapi.testclient import TestClient

def load_app():
    for n in list(sys.modules):
        if n.startswith('sonicforge.app'): sys.modules.pop(n,None)
    return importlib.import_module('sonicforge.app')

def test_health_and_capabilities(env):
    m=load_app()
    with TestClient(m.app) as c:
        h=c.get('/health').json(); assert h['contract_version']=='2.0'; assert h['status']=='healthy'
        caps=c.get('/addon/v1/capabilities').json(); ids={x['id'] for x in caps['capabilities']}; assert 'speech.tts.synthesize' in ids; assert 'music.generate' in ids

def test_fake_generation_persists_asset(env):
    m=load_app()
    with TestClient(m.app) as c:
        req={"task":"speech.tts.synthesize","input":{"text":"こんにちは"},"profile":"default","quality":"balanced","content_language":"ja","output":{"format":"wav","sample_rate":None,"channels":None},"routing":{"engine":"fake","model":None,"device":"auto"},"seed":None,"project_output_grant":None}
        jid=c.post('/addon/v1/tasks',json=req).json()['job_id']
        for _ in range(100):
            j=c.get('/addon/v1/jobs/'+jid.replace(':','%3A')).json()
            if j['state'] not in {'queued','running'}: break
            time.sleep(.03)
        assert j['state']=='succeeded',j
        assets=c.get('/addon/v1/assets').json()['assets']; assert assets and assets[0]['duration_ms']>0

def test_voice_rights_gate(env):
    m=load_app()
    with TestClient(m.app) as c:
        r=c.post('/addon/v1/voices',json={"name":"clone","source_type":"clone","languages":["ja"],"engine_id":None,"recipe":{},"rights_confirmed":False})
        assert r.status_code==400

def test_localization_batch(env):
    m=load_app()
    with TestClient(m.app) as c:
        r=c.post('/addon/v1/localization/batches',json={"name":"demo","profile":{},"lines":[{"line_id":"1","character":"A","ja_text":"はい","en_text":"Yes","voice_id":None}]})
        assert r.status_code==200 and r.json()['lines']==1
