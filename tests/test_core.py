import importlib, json, sys, time
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

def _compact(value: str) -> str:
    """Compare source invariants without pinning the authoring whitespace."""
    return ''.join(value.split())

def test_embedded_frontend_routes(env):
    m=load_app()
    with TestClient(m.app) as c:
        root=c.get('/'); assert root.status_code==200
        assert '<style>' in root.text and 'renderLocalizationBatch' in root.text and 'control-deck-addon.connect' in root.text
        assert '<link rel="stylesheet" href="styles.css">' not in root.text and '<script src="app.js"></script>' not in root.text and '<script src="localization.js"></script>' not in root.text
        assert '<base href="../">' not in root.text and 'data-start-view="studio"' in root.text
        settings=c.get('/settings/'); assert settings.status_code==200 and '<base href="../">' in settings.text and 'data-start-view="settings"' in settings.text
        assert '<style>' in settings.text and 'control-deck-addon.connect' in settings.text
        assert '<link rel="stylesheet" href="styles.css">' not in settings.text and '<script src="app.js"></script>' not in settings.text and '<script src="localization.js"></script>' not in settings.text
        localization=c.get('/localization.js'); assert localization.status_code==200 and 'renderLocalizationBatch' in localization.text
        app_js=c.get('/app.js'); assert app_js.status_code==200
        assert "X-Control-Deck-Bridge-Session" in app_js.text and _compact("credentials = 'include'") in _compact(app_js.text)
        assert "control-deck-bridge.${state.nonce}" in app_js.text
        assert "#shell-nav button" in app_js.text and "loadActiveJobs" in app_js.text
        styles=c.get('/styles.css'); assert styles.status_code==200
        # モバイルの下端と、指で押せる大きさ。どちらも欠けると実機で使えなくなる。
        assert "safe-area-inset-bottom" in styles.text and _compact("min-height: 44px") in _compact(styles.text)
        assert _compact("--tabbar: 60px") in _compact(styles.text)

def test_simple_and_advanced_modes_are_wired(env):
    """シンプル/詳細の切り替えと、詳細だけの断片が実際に存在すること。"""
    m=load_app()
    with TestClient(m.app) as c:
        root=c.get('/').text
        assert 'id="mode-simple"' in root and 'id="mode-advanced"' in root
        for name in ('common', 'task-speech', 'task-transcribe', 'task-sfx', 'task-music'):
            assert f'data-adv-template="{name}"' in root
        assert 'data-adv-slot="task"' in root and 'data-adv-slot="common"' in root
        # 詳細でしか出さないものは、シンプルの初期状態で hidden になっている。
        assert 'data-advanced-only hidden' in root

def test_switching_mode_redraws_the_task_choices(env):
    """詳細だけの作るもの（ローカライズ・会議）へ、モードを変えた直後に行けること。

    setMode が選択肢を描き直さないと、詳細にしても作るものの一覧が
    シンプルのままで、再読み込みするまで会議へ行けなかった。
    """
    m=load_app()
    with TestClient(m.app) as c:
        app_js=c.get('/app.js').text
        set_mode=app_js[app_js.index('function setMode('):app_js.index('function remember(')]
        assert 'renderTaskChoices()' in set_mode
        choices=app_js[app_js.index('function taskChoices('):app_js.index('function taskLabel(')]
        assert 'ADVANCED_TASKS' in choices
        # 会議はシンプルからも使える。詳細だけに閉じ込めない。
        advanced=app_js[app_js.index('const ADVANCED_TASKS'):app_js.index('\n', app_js.index('const ADVANCED_TASKS'))]
        assert '"meeting"' not in advanced and '"localization"' in advanced

def test_recording_goes_through_the_host_inside_control_deck(env):
    """埋め込み枠ではマイクを開けないので、録音は host に頼ること。

    add-on frame は allow-same-origin なしの sandbox、つまり不透明 origin で動く。
    ブラウザはそこでの getUserMedia を SecurityError で拒み、iframe に
    allow="microphone" を足しても変わらない。録音・会議のどちらも、bridge が
    あるときは host が開いたマイクの PCM を受け取る経路を通る。
    """
    m=load_app()
    with TestClient(m.app) as c:
        app_js=c.get('/app.js').text
        assert 'host.audio.record.start' in app_js and 'host.audio.record.stop' in app_js
        assert 'value.event === "audio.frame"' in app_js
        start=app_js[app_js.index('async function startRecording('):app_js.index('async function startHostRecording(')]
        assert 'hostCaptureAvailable()' in start
        meeting=app_js[app_js.index('async function startMeeting('):app_js.index('function startMeetingCapture(')]
        assert 'hostCaptureAvailable()' in meeting
        # host は 16kHz モノラルの Int16 を送る。会議の frame と同じ形にしておく。
        assert 'const HOST_CAPTURE_RATE = 16000' in app_js
        assert 'const MEETING_RATE = 16000' in app_js
        manifest=json.loads((__import__('pathlib').Path(m.__file__).parents[2] / 'addon.json').read_text(encoding='utf-8'))
        assert 'audio.capture' in manifest['host_capabilities']

def test_pipeline_ai_instruction_reaches_the_runtime(env):
    """パイプラインの自由文の指示が、runtime が読むキーで届くこと。

    UI は parameters.instruction を送っていたが runtime は system_prompt を読む。
    指示は黙って捨てられ、翻訳もチャットも既定の振る舞いになっていた。
    """
    m=load_app()
    with TestClient(m.app) as c:
        app_js=c.get('/app.js').text
        body=app_js[app_js.index('function pipelineBody('):app_js.index('byId("pipeline-validate")')]
        assert 'item.parameters.system_prompt = stage.instruction' in body
        assert 'parameters.instruction' not in body
        # 音声チャットは 文字起こし → AI → 読み上げ の 1 往復で、音として返る。
        presets=app_js[app_js.index('const PIPELINE_PRESETS'):app_js.index('/* ── 状態')]
        assert '"chat"' in presets and 'presetChat' in presets
        chat=presets[presets.index('id: "chat"'):]
        for kind in ('speech.asr', 'host.ai.text', 'speech.tts'):
            assert kind in chat
        assert 'delivery: "asset"' in chat
    from sonicforge import pipeline_runtime
    src=(__import__('pathlib').Path(pipeline_runtime.__file__)).read_text(encoding='utf-8')
    assert 'stage.parameters.get("system_prompt")' in src

def test_advanced_surfaces_every_public_capability(env):
    """詳細モードから到達できる先が、公開APIの機能を取りこぼしていないこと。"""
    m=load_app()
    with TestClient(m.app) as c:
        app_js=c.get('/app.js').text
        for path in ('/pipelines/compile', '/pipelines', '/delivery/audio/profiles',
                     '/devices/pairings', '/meetings', '/setup/plan', '/voices',
                     '/localization/batches', '/assets/'):
            assert path in app_js or path in c.get('/localization.js').text
        for task in ('speech.tts.synthesize', 'speech.asr.transcribe',
                     'audio.sfx.generate', 'audio.ambience.generate', 'music.generate'):
            assert task in app_js
        assert 'speech.localization.batch' in c.get('/localization.js').text

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


def test_setup_plan_cli_is_read_only(env, monkeypatch, capsys):
    from sonicforge import __main__

    captured = {}

    def plan(_settings, profile, components):
        captured.update(profile=profile, components=components)
        return {"profile": profile, "components": components or []}

    monkeypatch.setattr(__main__.setup_service, "plan", plan)
    monkeypatch.setattr(
        sys,
        "argv",
        ["sonic-forge", "setup", "plan", "game-audio"],
    )

    assert __main__.main() == 0
    assert captured == {"profile": "game-audio", "components": None}
    assert json.loads(capsys.readouterr().out)["profile"] == "game-audio"


def test_setup_apply_cli_passes_explicit_terms(env, monkeypatch, capsys):
    from sonicforge import __main__

    captured = {}

    class SessionContext:
        def __enter__(self):
            return object()

        def __exit__(self, *_args):
            return None

    async def apply(_settings, _session, profile, components, *, accepted_terms):
        captured.update(
            profile=profile,
            components=components,
            accepted_terms=accepted_terms,
        )
        return {"profile": profile, "components": components or []}

    monkeypatch.setattr(
        __main__, "make_session_factory", lambda _settings: SessionContext
    )
    monkeypatch.setattr(__main__.setup_service, "apply", apply)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "sonic-forge",
            "setup",
            "apply",
            "game-audio",
            "--accept-term",
            "stability-ai-community-license",
        ],
    )

    assert __main__.main() == 0
    assert captured == {
        "profile": "game-audio",
        "components": None,
        "accepted_terms": ["stability-ai-community-license"],
    }
    assert json.loads(capsys.readouterr().out)["profile"] == "game-audio"


def test_provision_cli_defaults_to_speech_essentials(env, monkeypatch, capsys):
    from sonicforge import __main__

    captured = {}

    class SessionContext:
        def __enter__(self):
            return object()

        def __exit__(self, *_args):
            return None

    async def apply(_settings, _session, profile, components, *, accepted_terms):
        captured.update(
            profile=profile,
            components=components,
            accepted_terms=accepted_terms,
        )
        return {"profile": profile, "components": [{"component": profile}]}

    monkeypatch.setattr(
        __main__, "make_session_factory", lambda _settings: SessionContext
    )
    monkeypatch.setattr(__main__.setup_service, "apply", apply)
    monkeypatch.setattr(sys, "argv", ["sonic-forge", "provision"])

    assert __main__.main() == 0
    assert captured == {
        "profile": "speech-essentials",
        "components": None,
        "accepted_terms": [],
    }
    assert json.loads(capsys.readouterr().out)["profile"] == "speech-essentials"


def test_setup_apply_cli_reports_setup_error_without_traceback(
    env, monkeypatch, capsys
):
    from sonicforge import __main__

    async def apply(*_args, **_kwargs):
        raise __main__.setup_service.SetupError(
            "terms_required:stability-ai-community-license"
        )

    class SessionContext:
        def __enter__(self):
            return object()

        def __exit__(self, *_args):
            return None

    monkeypatch.setattr(
        __main__, "make_session_factory", lambda _settings: SessionContext
    )
    monkeypatch.setattr(__main__.setup_service, "apply", apply)
    monkeypatch.setattr(
        sys,
        "argv",
        ["sonic-forge", "setup", "apply", "game-audio"],
    )

    assert __main__.main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "ok": False,
        "error": "terms_required:stability-ai-community-license",
    }
