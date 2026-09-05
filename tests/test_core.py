import importlib, io, json, shutil, sys, time, wave
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

def test_tts_engine_preference_and_gpt_sample_voice_are_persistent(env, monkeypatch):
    from sonicforge import uploads

    async def copy_normalised(source, target):
        shutil.copyfile(source, target)

    monkeypatch.setattr(uploads, '_normalise', copy_normalised)
    m=load_app()
    with TestClient(m.app) as c:
        assert c.get('/addon/v1/tts/preferences').json() == {
            'engine_id': 'tts.qwen3',
            'gpt_sovits_model_id': 'lj1995/GPT-SoVITS',
            'gpt_sovits_voice_id': None,
        }
        changed=c.put('/addon/v1/tts/preferences', json={
            'engine_id': 'tts.gpt-sovits',
            'gpt_sovits_model_id': 'lj1995/GPT-SoVITS',
        })
        assert changed.status_code == 200
        assert c.get('/addon/v1/tts/preferences').json()['engine_id'] == 'tts.gpt-sovits'

        audio=io.BytesIO()
        with wave.open(audio, 'wb') as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000)
            wav.writeframes(b'\0\0' * 16000)
        uploaded=c.post('/addon/v1/uploads', files={
            'file': ('sample.wav', audio.getvalue(), 'audio/wav'),
        })
        assert uploaded.status_code == 200
        voice=c.post('/addon/v1/voices', json={
            'name': 'GPT sample',
            'source_type': 'clone',
            'languages': ['ja'],
            'engine_id': 'tts.gpt-sovits',
            'recipe': {
                'reference_upload': uploaded.json()['upload_id'],
                'reference_text': '参照音声です。',
            },
            'rights_confirmed': True,
        })
        assert voice.status_code == 200
        assert voice.json()['engine_id'] == 'tts.gpt-sovits'
        assert voice.json()['recipe']['reference_audio'].startswith('voices/')
        voice_id=voice.json()['id']
        selected=c.put('/addon/v1/tts/preferences', json={
            'engine_id': 'tts.gpt-sovits',
            'gpt_sovits_model_id': 'lj1995/GPT-SoVITS',
            'gpt_sovits_voice_id': voice_id,
        })
        assert selected.status_code == 200
        assert selected.json()['gpt_sovits_voice_id'] == voice_id
        routed=m.base.jobs._apply_tts_preferences({
            'task': 'speech.tts.synthesize', 'input': {'text': 'こんにちは'},
            'routing': {'engine': None, 'model': None, 'device': 'auto'},
        })
        assert routed['input']['voice_id'] == voice_id
        assert c.delete(f"/addon/v1/voices/{voice.json()['id']}").status_code == 200
        assert c.get('/addon/v1/tts/preferences').json()['gpt_sovits_voice_id'] is None

        markup=c.get('/settings/').text
        for element_id in ('tts-model-upload', 'gpt-sample-preset', 'gpt-sample-file', 'gpt-sample-add'):
            assert f'id="{element_id}"' in markup
        app_js=c.get('/app.js').text
        assert 'saveTtsPreference' in app_js
        assert 'engine_id: "tts.gpt-sovits"' in app_js
        assert 'gpt_sovits_voice_id' in app_js and '/tts/samples/' in app_js
        assert 'speech-style-fields' in markup


def test_managed_gpt_sample_install_is_consent_gated_and_persistent(env, monkeypatch):
    from sonicforge import tts_samples, uploads

    async def copy_normalised(source, target):
        shutil.copyfile(source, target)

    audio=io.BytesIO()
    with wave.open(audio, 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000)
        wav.writeframes(b'\0\0' * 16000 * 4)
    monkeypatch.setattr(uploads, '_normalise', copy_normalised)
    monkeypatch.setattr(tts_samples, '_download_zundamon', audio.getvalue)
    m=load_app()
    with TestClient(m.app) as c:
        catalog=c.get('/addon/v1/tts/samples')
        assert catalog.status_code == 200
        assert {item['id'] for item in catalog.json()['samples']} == {
            'amitaro-ita-yofukashi', 'zundamon-reference',
        }
        denied=c.post('/addon/v1/tts/samples/zundamon-reference/install', json={'accepted_terms': False})
        assert denied.status_code == 400
        installed=c.post('/addon/v1/tts/samples/zundamon-reference/install', json={'accepted_terms': True})
        assert installed.status_code == 200
        assert installed.json()['name'] == 'ずんだもん'
        prefs=c.get('/addon/v1/tts/preferences').json()
        assert prefs['engine_id'] == 'tts.gpt-sovits'
        assert prefs['gpt_sovits_voice_id'] == installed.json()['id']
        repeated=c.post('/addon/v1/tts/samples/zundamon-reference/install', json={'accepted_terms': True})
        assert repeated.json()['id'] == installed.json()['id']

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

def test_models_are_offered_by_name_not_typed_from_memory(env):
    """使えるモデルが、作るものごとに名前で並ぶこと。

    routing.model は前から効いていたが、UI は Hugging Face のリポジトリ名を
    打ち込む自由入力欄だった。暗記していない人には選べないので、機能ではない。
    """
    m=load_app()
    with TestClient(m.app) as c:
        doc=c.get('/addon/v1/models').json()
        by_task={item['task']: item for item in doc['tasks']}
        assert 'kotoba-tech/kotoba-whisper-v2.0' in [
            x['id'] for x in by_task['speech.asr.transcribe']['models']]
        assert by_task['speech.asr.transcribe']['engine'] == 'asr.whisper'
        assert [item['id'] for item in by_task['speech.tts.synthesize']['engines']] == [
            'tts.qwen3', 'tts.gpt-sovits']
        assert by_task['speech.tts.synthesize']['engines'][1]['models'][0]['id'] == \
            'lj1995/GPT-SoVITS'
        assert by_task['music.generate']['engine'] == 'music.ace-step-1.5'
        markup=c.get('/').text
        assert '<select id="advanced-model">' in markup
        assert '<input id="advanced-model"' not in markup
        app_js=c.get('/app.js').text
        assert 'loadModels()' in app_js and 'renderRoutingChoices()' in app_js
        # 知らない id が来ても、消えずに id のまま並ぶこと。
        assert 't(MODEL_LABELS[item.id]) || item.id' in app_js

def test_task_switch_is_an_icon_that_still_opens_the_native_list(env):
    """作るものの切り替えは絵にする。ただし select のままで、読み上げにも届くこと。"""
    m=load_app()
    with TestClient(m.app) as c:
        markup=c.get('/').text
        assert '<select id="task-select">' in markup and 'id="task-icon"' in markup
        assert 'aria-label="作るもの"' in markup
        styles=c.get('/styles.css').text
        switch=styles[styles.index('.function-switch select {'):styles.index('.function-switch-icon')]
        # つまみは透明にして絵にかぶせる。当たり判定は絵の大きさのまま。
        assert 'opacity: 0' in switch and 'position: absolute' in switch
        app_js=c.get('/app.js').text
        assert 'const TASK_ICONS' in app_js
        icons=app_js[app_js.index('const TASK_ICONS'):app_js.index('function renderTaskChoices(')]
        for task in ('speech', 'transcribe', 'sfx', 'music', 'localization', 'meeting'):
            assert f'{task}:' in icons, task

def test_meeting_transcript_reads_like_one_utterance_per_card(env):
    """会議の書き起こしは KasaneCore の Echo と同じ形にする。

    1 発言 1 枚。上に言語と時刻と状態、本文の下に訳。文字が来る前の枠も
    潰さず、いま聞き取っていることが分かるようにする。
    """
    m=load_app()
    with TestClient(m.app) as c:
        app_js=c.get('/app.js').text
        render=app_js[app_js.index('function renderSegment('):app_js.index('function followLatestSegment(')]
        for part in ('"meta"', '"flag"', '"time"', '"state"', '"src"', '"dst"'):
            assert part in render, part
        assert 't("segmentWaiting")' in render
        # 過去を読み返している最中に最新へ引き戻さないこと。
        follow=app_js[app_js.index('function followLatestSegment('):app_js.index('async function loadMeetings(')]
        assert 'atBottom' in follow
        styles=c.get('/styles.css').text
        card=styles[styles.index('.segment {'):styles.index('.segment .meta')]
        assert 'border:' in card and 'border-radius' in card

def test_meeting_shows_a_segment_before_it_is_finished(env):
    """話してから文字が出るまで、画面が止まって見えないこと。

    確定だけを待つと、区切りの長さぶん何も起きない。受付と処理中でも同じ枠を
    出し、届いた分から書き換える。翻訳が入っているときは原文と訳を両方残す。
    """
    m=load_app()
    with TestClient(m.app) as c:
        app_js=c.get('/app.js').text
        assert 'message.type?.startsWith("meeting.segment.")' in app_js
        handler=app_js[app_js.index('message.type?.startsWith("meeting.segment.")'):]
        handler=handler[:handler.index('meeting.complete')]
        # 同じ区切りは同じ枠を書き換える。並べ足すと同じ発言が何度も出る。
        assert 'item.sequence === sequence' in handler
        # 原文と訳のどちらも、後続の知らせで消えないこと。
        assert 'source_text: message.source_text ??' in handler
        assert 'translated_text: message.translated_text ??' in handler

def test_tasks_with_their_own_screen_hide_the_generation_form(env):
    """会話・会議・ローカライズでは、生成用のフォームと結果欄を出さないこと。

    会話の最中に「作る」や「最近作ったもの」やプロンプト未入力のエラーが
    並ぶと、いま何の画面なのか読めなくなる。
    """
    m=load_app()
    with TestClient(m.app) as c:
        styles=c.get('/styles.css').text
        for task in ("localization", "meeting", "chat"):
            assert f'#app[data-task="{task}"] #studio-form' in styles, task
            assert f'#app[data-task="{task}"] #stage' in styles, task

def test_meeting_puts_the_transcript_above_the_controls(env):
    """話し始めたら、読むもの（書き起こし）が先に来ること。

    会議名や区切りの長さは始める前に一度触るだけなので、その下に文字が
    流れると、読むために毎回スクロールすることになる。
    """
    m=load_app()
    with TestClient(m.app) as c:
        app_js=c.get('/app.js').text
        body=app_js[app_js.index('function renderMeetingPanel('):]
        body=body[:body.index('function renderSegment(')]
        assert body.index('panel.append(live)') < body.index('panel.append(card)')

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

def test_agent_inspect_accepts_job_or_asset_reference(env):
    m=load_app()
    with TestClient(m.app) as c:
        request={"task":"speech.tts.synthesize","input":{"text":"inspect"},"profile":"default","quality":"balanced","content_language":"en","output":{"format":"wav","sample_rate":None,"channels":None},"routing":{"engine":"fake","model":None,"device":"auto"},"seed":None,"project_output_grant":None}
        created=c.post('/addon/v1/tasks',json=request)
        job_id=created.json()['job_id']
        for _ in range(100):
            job=c.get('/addon/v1/jobs/'+job_id.replace(':','%3A')).json()
            if job['state'] not in {'queued','running'}: break
            time.sleep(.03)
        inspected_job=c.post('/addon/v1/agent/inspect',json={"job_id":job_id})
        assert inspected_job.status_code==200,inspected_job.text
        assert inspected_job.json()['id']==job_id
        asset_id=job['result']['asset_id']
        inspected_asset=c.post('/addon/v1/agent/inspect',json={"asset_id":asset_id})
        assert inspected_asset.status_code==200,inspected_asset.text
        assert inspected_asset.json()['id']==asset_id

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
