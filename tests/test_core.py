import importlib, sys, time
from fastapi.testclient import TestClient

def load_app():
    for n in list(sys.modules):
        if n.startswith('sonicforge.bootstrap') or n.startswith('sonicforge.app'):
            sys.modules.pop(n,None)
    return importlib.import_module('sonicforge.bootstrap')

def test_health_and_capabilities(env):
    m=load_app()
    with TestClient(m.app) as c:
        h=c.get('/health').json(); assert h['contract_version']=='2.0'; assert h['status']=='healthy'
        caps=c.get('/addon/v1/capabilities').json(); ids={x['id'] for x in caps['capabilities']}; assert 'speech.tts.synthesize' in ids; assert 'music.generate' in ids

def test_embedded_frontend_routes(env):
    m=load_app()
    with TestClient(m.app) as c:
        root=c.get('/'); assert root.status_code==200 and 'localization.js' in root.text
        settings=c.get('/settings/'); assert settings.status_code==200 and '<base href="../">' in settings.text and 'data-view="runtime"' in settings.text
        localization=c.get('/localization.js'); assert localization.status_code==200 and 'renderLocalizationBatch' in localization.text

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
        asset_id=assets[0]['id'].replace(':','%3A')
        assert c.get('/addon/v1/assets/'+asset_id).status_code==200
        content=c.get('/addon/v1/assets/'+asset_id+'/content')
        assert content.status_code==200 and content.headers['content-type']=='audio/wav'

def test_agent_generate_unwraps_control_deck_envelope(env):
    m=load_app()
    with TestClient(m.app) as c:
        response=c.post('/addon/v1/agent/generate',json={
            "input":{"task":"speech.tts.synthesize","input":{"text":"MCP envelope"},"routing":{"engine":"fake","model":None,"device":"auto"}},
            "correlation":{"job_id":"host-job"},
        })
        assert response.status_code==200,response.text
        job_id=response.json()['job_id']
        for _ in range(100):
            job=c.get('/addon/v1/jobs/'+job_id.replace(':','%3A')).json()
            if job['state'] not in {'queued','running'}: break
            time.sleep(.03)
        assert job['state']=='succeeded',job

def test_pipeline_routes_precede_spa_mount(env):
    m=load_app()
    with TestClient(m.app) as c:
        req={
            "input":{"kind":"text","text":"短い確認音"},
            "stages":[{"id":"tts","kind":"speech.tts","routing":{"engine":"fake","model":None,"device":"auto"}}],
            "delivery":{"mode":"asset","profile":"test"},
        }
        compiled=c.post('/addon/v1/pipelines/compile',json=req)
        assert compiled.status_code==200,compiled.text
        assert compiled.json()['stage_ids']==['tts']

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

def test_serve_has_bounded_graceful_shutdown(env, monkeypatch):
    from sonicforge import __main__
    captured={}
    def run(*args,**kwargs): captured.update({"args":args,"kwargs":kwargs})
    monkeypatch.setattr(__main__.uvicorn,'run',run)
    monkeypatch.setattr(sys,'argv',['sonic-forge','serve'])
    assert __main__.main()==0
    assert captured['kwargs']['timeout_graceful_shutdown']==15
