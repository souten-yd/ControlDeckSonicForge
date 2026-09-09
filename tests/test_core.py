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
        assert "jobsLoaded" in app_js.text and "assetsLoaded" in app_js.text
        assert "setupLoaded" in app_js.text and 'state.setupError ? "unavailable" : "checking"' in app_js.text
        assert 'id="activity-error"' in root.text
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

def test_agent_generate_returns_the_finished_result_in_one_call(env):
    """投げっぱなしにすると、呼び出し側は状態を見るために何度も往復する。その
    往復ごとに Host は言語モデルを降ろして載せ直し、会話の文脈を読み直す
    （実測 40〜350 秒）。20 秒の音楽 1 曲に 30 回の確認が要っていた。"""
    m=load_app()
    with TestClient(m.app) as c:
        response=c.post('/addon/v1/agent/generate',json={
            "input":{"task":"speech.tts.synthesize","input":{"text":"one call"},"routing":{"engine":"fake","model":None,"device":"auto"}},
            "correlation":{"job_id":"host-job"},
        })
        assert response.status_code==200,response.text
        body=response.json()
        # 確認の往復なしで、そのまま使える。
        assert body['state']=='succeeded',body
        assert body['asset_id'],body
        asset=c.get('/addon/v1/assets/'+body['asset_id'].replace(':','%3A'))
        assert asset.status_code==200,asset.text

def test_agent_generate_reports_a_failure_instead_of_raising(env, monkeypatch):
    """失敗も 1 回で返す。呼び出し側から見て、失敗は結果の一種である。"""
    m=load_app()

    from sonicforge import jobs as jobs_module

    async def explode(*_args, **_kwargs):
        raise jobs_module.WorkerError("worker exploded")

    monkeypatch.setattr(jobs_module, "execute", explode)
    with TestClient(m.app) as c:
        response=c.post('/addon/v1/agent/generate',json={
            "input":{"task":"speech.tts.synthesize","input":{"text":"boom"},"routing":{"engine":"fake","model":None,"device":"auto"}},
            "correlation":{"job_id":"host-job"},
        })
        assert response.status_code==200,response.text
        body=response.json()
        assert body['state']=='failed',body
        assert body['error']['code'],body

def test_an_attached_host_job_is_not_terminated_by_the_addon(env,monkeypatch):
    """agent tool の job へぶら下がったとき、こちらが succeeded を送ると tool
    呼び出しそのものが終わったことになり、結果も上書きされる。終わりを決める
    のは、その Host Job を作った側である。"""
    from sonicforge.jobs import HostedExecution
    load_app()
    import sonicforge.app as app_module
    sent=[]

    class Client:
        async def update_job(self,identity,host_job_id,payload):
            sent.append(payload); return {}

    manager=app_module.jobs
    previous=manager.host_client
    manager.host_client=Client()
    execution=HostedExecution(identity=object(),host_job_id="host-job",owns_terminal=False)
    manager.hosted["job:attached"]=execution
    try:
        import asyncio
        asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            manager._report_host("job:attached",{"state":"succeeded","progress":1.0,"result":{"asset_id":"asset:1"}})
        )
    finally:
        manager.host_client=previous
        manager.hosted.pop("job:attached",None)

    assert sent,"進捗すら送っていない"
    assert "status" not in sent[-1],sent[-1]
    assert "result" not in sent[-1],sent[-1]
    assert sent[-1]["progress"]=={"completed":1000,"total":1000},sent[-1]

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


def test_assets_are_paged_and_filtered_on_the_server(env):
    """一覧は少しずつ返す。

    以前は limit だけで、画面側は 200 件を一度に取っていた。件数に比例して待ち
    時間が伸びるうえ、200 件を超えると超えたぶんが黙って出なくなる。絞り込みも
    画面側で行っていたため、読み込み済みのぶんに該当が無いと「0 件」に見えた。
    """
    m = load_app()
    with TestClient(m.app) as c:
        for index in range(5):
            req = {"task": "speech.tts.synthesize", "input": {"text": f"おと{index}"},
                   "profile": "default", "quality": "balanced", "content_language": "ja"}
            jid = c.post('/addon/v1/tasks', json=req).json()['job_id']
            for _ in range(100):
                job = c.get('/addon/v1/jobs/' + jid.replace(':', '%3A')).json()
                if job['state'] not in {'queued', 'running'}:
                    break
                time.sleep(.03)
            assert job['state'] == 'succeeded', job

        first = c.get('/addon/v1/assets?limit=2').json()
        assert len(first['assets']) == 2
        assert first['next_before'], "続きがあるのに位置を返していない"

        second = c.get('/addon/v1/assets?limit=2&before=' + first['next_before']).json()
        assert len(second['assets']) == 2
        # 境目で取りこぼしも重複もしないこと
        seen = [item['id'] for item in first['assets']] + [item['id'] for item in second['assets']]
        assert len(seen) == len(set(seen)), seen

        everything = c.get('/addon/v1/assets?limit=500').json()
        assert everything['next_before'] is None, "全部返したのに続きがあることになっている"
        assert [item['id'] for item in everything['assets']][:4] == seen

        # 種類での絞り込みはサーバが行う。手元にある分だけ絞る形にしない。
        speech = c.get('/addon/v1/assets?limit=500&task=speech.tts.synthesize').json()
        speech_ids = {item['id'] for item in speech['assets']}
        assert speech_ids and speech_ids <= {item['id'] for item in everything['assets']}
        music = c.get('/addon/v1/assets?limit=500&task=music.generate').json()
        assert music['assets'] == []

        assert c.get('/addon/v1/assets?before=not-a-time').status_code == 422


def test_library_does_not_fetch_audio_until_play_is_pressed(env):
    """一覧を開いただけで音声を取りに行かない。

    preload="none" は「取らない」の保証にならない。iOS の Safari は指定を
    尊重しないことがあり、一覧を開いた時点で全件を取りに行く。1 件 238KB
    なので携帯回線では数 MB になり、ライブラリが出るまで待たされる。
    src を最初から持たせなければ、どのブラウザでも取りようがない。
    """
    m = load_app()
    with TestClient(m.app) as c:
        app_js = c.get('/app.js').text
        # src を渡すのは 1 箇所だけで、それは押されたときのハンドラの中にある
        assert app_js.count("player.src = apiUrl") == 1
        handler = app_js[app_js.index("play.onclick"):]
        handler = handler[:handler.index("};")]
        assert "player.src = apiUrl" in handler, "押す前に src を渡している"
        assert "player.play()" in handler
        # 作った直後は src を持たない
        made = app_js[app_js.index('const player = document.createElement("audio")'):]
        made = made[:made.index("play.onclick")]
        assert "player.src" not in made, "作った時点で src を持たせている"

def test_gpt_sovits_provisioning_fetches_the_english_g2p_resources(env):
    """英語の読み付けは g2p_en を通り、そこが NLTK の品詞タグと発音辞書を要る。
    pip では入らないので、整備の時点で揃えないと日本語だけ通って英語が
    worker_failed で落ちる（実機で起きた）。"""
    from sonicforge import setup as setup_module
    from sonicforge.config import load_settings

    specs=setup_module.runtime_specs(load_settings(),"speech-essentials",["gpt-sovits"])
    if not specs:  # ROCm の無い機械では gpt-sovits の spec 自体が立たない
        return
    spec=specs[0]
    assert spec.runtime_id=="speech-gpt-sovits-rocm",spec
    assert "averaged_perceptron_tagger_eng" in spec.nltk_resources,spec.nltk_resources
    assert "cmudict" in spec.nltk_resources,spec.nltk_resources

def test_nltk_resources_land_inside_the_runtime(env,monkeypatch):
    """利用者の home へ書かない。ランタイムを捨てたときに一緒に消える場所へ置く。"""
    import asyncio
    from pathlib import Path
    from sonicforge import setup as setup_module

    calls=[]

    async def fake_run(command,env=None,**kwargs):
        calls.append(command); return ""

    monkeypatch.setattr(setup_module,"_run_process",fake_run)
    spec=setup_module.RuntimeSpec("x","x",Path("/tmp/req.txt"),1,nltk_resources=("cmudict",))
    python=Path(env["runtime"] if isinstance(env,dict) and "runtime" in env else "/tmp/sf-runtime")/"bin"/"python"
    python.parent.mkdir(parents=True,exist_ok=True)
    asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
        setup_module._fetch_nltk_resources(python,spec,{})
    )
    assert calls,"取りに行っていない"
    target=calls[0][3]
    assert target.endswith("share/nltk_data"),target
    assert str(Path.home()) not in target or target.startswith(str(python.parent.parent)),target
    assert Path(target).is_dir()

def test_agent_batch_generates_every_kind_in_one_call(env):
    """1 件ずつ呼ぶと、その都度 Host は言語モデルを降ろして載せ直し、会話の文脈を
    読み直す（実測で 12 万トークンの読み直しに 6 分）。台詞も効果音も曲も、まとめて
    1 回で受ける。"""
    m=load_app()
    with TestClient(m.app) as c:
        response=c.post('/addon/v1/agent/generate/batch',json={
            "input":{"items":[
                {"task":"speech.tts.synthesize","input":{"text":"はじめまして"},"routing":{"engine":"fake","model":None,"device":"auto"}},
                {"task":"audio.sfx.generate","input":{"prompt":"扉が閉まる音","duration_sec":2},"routing":{"engine":"fake","model":None,"device":"auto"}},
                {"task":"audio.ambience.generate","input":{"prompt":"雨だれ","duration_sec":4},"routing":{"engine":"fake","model":None,"device":"auto"}},
                {"task":"music.generate","input":{"prompt":"宿屋のテーマ","duration_sec":5,"bpm":90},"routing":{"engine":"fake","model":None,"device":"auto"}},
            ]},
            "correlation":{"job_id":"host-job"},
        })
        assert response.status_code==200,response.text
        body=response.json()
        assert body['requested_count']==4 and body['succeeded_count']==4,body
        assert body['partial'] is False and body['atomic'] is False,body
        assert [item['index'] for item in body['items']]==[0,1,2,3],body
        assert [item['task'] for item in body['items']]==[
            'speech.tts.synthesize','audio.sfx.generate','audio.ambience.generate','music.generate'],body
        for item in body['items']:
            assert item['status']=='succeeded',item
            # 確認の往復なしで、そのまま使える。
            assert c.get('/addon/v1/assets/'+item['asset_id'].replace(':','%3A')).status_code==200,item

def test_agent_batch_refuses_a_malformed_item_before_running_anything(env):
    """読めない指示を混ぜたまま半分だけ実行しない。"""
    m=load_app()
    with TestClient(m.app) as c:
        before=len(c.get('/addon/v1/assets').json()['assets'])
        response=c.post('/addon/v1/agent/generate/batch',json={"items":[
            {"task":"speech.tts.synthesize","input":{"text":"ちゃんとした依頼"},"routing":{"engine":"fake","model":None,"device":"auto"}},
            {"task":"music.generate","input":{"prompt":"曲","duration_seconds":20}},
        ]})
        assert response.status_code==422,response.text
        assert response.json()['detail']['code']=='invalid_generation_batch',response.text
        # duration_seconds は読まない項目である。1 件目も走らせずに断っている。
        assert len(c.get('/addon/v1/assets').json()['assets'])==before

def test_agent_batch_refuses_a_task_it_cannot_batch(env):
    m=load_app()
    with TestClient(m.app) as c:
        response=c.post('/addon/v1/agent/generate/batch',json={"items":[
            {"task":"speech.asr.transcribe","input":{}},
        ]})
        assert response.status_code==422,response.text
        assert response.json()['detail']['code']=='unsupported_task',response.text

def test_agent_batch_accepts_up_to_fifty_items(env):
    import sonicforge.app as app_module
    m=load_app()
    with TestClient(m.app) as c:
        item={"task":"speech.tts.synthesize","input":{"text":"多い"},"routing":{"engine":"fake","model":None,"device":"auto"}}
        assert app_module.BATCH_MAX_ITEMS==50
        response=c.post('/addon/v1/agent/generate/batch',json={"items":[item]*51})
        assert response.status_code==422,response.text
        assert response.json()['detail']['code']=='too_many_items',response.text

def test_agent_batch_keeps_going_after_one_item_fails(env,monkeypatch):
    """1 件の失敗で残りを捨てない。結果は件ごとに返る。"""
    m=load_app()
    from sonicforge import jobs as jobs_module
    real=jobs_module.execute
    calls={"n":0}

    async def flaky(settings,request,work_dir,progress):
        calls["n"]+=1
        if calls["n"]==2:
            raise jobs_module.WorkerError("worker exploded")
        return await real(settings,request,work_dir,progress)

    monkeypatch.setattr(jobs_module,"execute",flaky)
    with TestClient(m.app) as c:
        response=c.post('/addon/v1/agent/generate/batch',json={"items":[
            {"task":"speech.tts.synthesize","input":{"text":"一つめ"},"routing":{"engine":"fake","model":None,"device":"auto"}},
            {"task":"speech.tts.synthesize","input":{"text":"二つめ"},"routing":{"engine":"fake","model":None,"device":"auto"}},
            {"task":"speech.tts.synthesize","input":{"text":"三つめ"},"routing":{"engine":"fake","model":None,"device":"auto"}},
        ]})
        assert response.status_code==200,response.text
        body=response.json()
        assert [item['status'] for item in body['items']]==['succeeded','failed','succeeded'],body
        assert body['succeeded_count']==2 and body['partial'] is True,body
        assert body['items'][1]['error']['code'],body['items'][1]

def test_batch_progress_is_monotonic_and_does_not_claim_completion_midway(env):
    """N 件を 1 つの Host Job にぶら下げる。件ごとに 0 から報告し直すと後戻りに
    なり、途中で complete と名乗ると次の件が始まった途端に phase が戻る。"""
    from sonicforge.jobs import HostedExecution, ProgressGate
    load_app()
    import sonicforge.app as app_module
    import asyncio
    sent=[]

    class Client:
        async def update_job(self,identity,host_job_id,payload):
            sent.append(payload); return {}

    manager=app_module.jobs
    previous=manager.host_client
    manager.host_client=Client()
    gate=ProgressGate()
    loop=asyncio.get_event_loop_policy().new_event_loop()
    try:
        for index in range(3):
            job_id=f"job:batch-{index}"
            manager.hosted[job_id]=HostedExecution(
                identity=object(),host_job_id="host-job",owns_terminal=False,
                gate=gate,progress_offset=index/3,progress_span=1/3)
            for values in ({"state":"running","progress":0.01},{"state":"succeeded","progress":1.0}):
                gate.last_sent_at=0.0  # 間隔ではなく順序だけを見る
                loop.run_until_complete(manager._report_host(job_id,values))
            manager.hosted.pop(job_id,None)
    finally:
        manager.host_client=previous
        loop.close()

    completed=[payload["progress"]["completed"] for payload in sent]
    assert completed==sorted(completed),completed
    assert completed[-1]==1000,completed
    # 最後の 1 件が終わるまで complete とは名乗らない。
    phases=[payload["phase"] for payload in sent]
    assert "complete" not in phases[:-1],phases

def test_batch_keeps_the_audio_engine_loaded_and_drops_it_before_reporting_done(env,monkeypatch):
    """batch の間はモデルを降ろさない。抜けるときは、抱えていたぶんを自分で降ろす
    ——抱えたまま「終わった」と言うと、次に来た要求は空いていない GPU を待つ。"""
    m=load_app()
    from sonicforge import jobs as jobs_module
    from sonicforge import workers
    real=jobs_module.execute
    resident=[]

    async def watched(settings,request,work_dir,progress):
        result=await real(settings,request,work_dir,progress)
        resident.append(len(workers._warm))
        return result

    monkeypatch.setattr(jobs_module,"execute",watched)
    with TestClient(m.app) as c:
        item={"task":"audio.sfx.generate","input":{"prompt":"足音","duration_sec":1},"routing":{"engine":"fake","model":None,"device":"auto"}}
        response=c.post('/addon/v1/agent/generate/batch',json={"items":[item,item,item]})
        assert response.status_code==200,response.text
        assert response.json()['succeeded_count']==3,response.text
    # 3 件とも同じ 1 本を使い回している。
    assert resident==[1,1,1],resident
    # 終わったら降ろしてから申告する。
    assert workers._warm=={},workers._warm

def test_a_single_call_does_not_leave_a_transient_engine_loaded(env,monkeypatch):
    """1 件だけなら抱える利点が無い。batch のときだけ抱える。"""
    m=load_app()
    from sonicforge import jobs as jobs_module
    from sonicforge import workers
    real=jobs_module.execute
    resident=[]

    async def watched(settings,request,work_dir,progress):
        result=await real(settings,request,work_dir,progress)
        resident.append(len(workers._warm))
        return result

    monkeypatch.setattr(jobs_module,"execute",watched)
    with TestClient(m.app) as c:
        response=c.post('/addon/v1/agent/generate',json={
            "input":{"task":"audio.sfx.generate","input":{"prompt":"足音","duration_sec":1},"routing":{"engine":"fake","model":None,"device":"auto"}},
            "correlation":{"job_id":"host-job"},
        })
        assert response.status_code==200,response.text
        assert response.json()['state']=='succeeded',response.text
    assert resident==[0],resident

def test_a_worker_nobody_is_using_is_put_down(monkeypatch):
    """常駐が効くのは「続けて話させる」間だけである。そのあとも抱えていると、
    31.9GiB のカードでは画像や音楽の枠を削る。実機では GPT-SoVITS が 2.2GB を
    抱えたまま、画像生成が GPU を空けられず 21 件連続で落ちた。"""
    import asyncio, time

    from sonicforge import workers

    class Ended:
        """終わっている process。_retire は表から外すだけで済む。"""
        returncode = 0

    monkeypatch.setattr(workers, "WARM_IDLE_SEC", 60.0)
    key = ("tts.qwen3", ("python",), "{}")
    now = time.monotonic()
    workers._warm[key] = Ended()
    workers._warm_used_at[key] = now
    try:
        # まだ使われた直後。降ろさない。
        assert asyncio.run(workers.retire_idle_workers(now)) == []
        assert key in workers._warm, "使った直後に降ろされた"
        # 誰も使わないまま間が空いたら降ろす。
        assert asyncio.run(workers.retire_idle_workers(now + 61)) == ["tts.qwen3"]
        assert key not in workers._warm
        assert key not in workers._warm_used_at
    finally:
        workers._warm.pop(key, None)
        workers._warm_used_at.pop(key, None)


def test_a_batch_keeps_its_workers_even_while_idle(env,monkeypatch):
    """続きがあると宣言されている間は、間が空いていても抱えたままにする。"""
    import asyncio, time
    load_app()
    from sonicforge import workers
    monkeypatch.setattr(workers, "WARM_IDLE_SEC", 0.0)
    monkeypatch.setattr(workers, "_hold_all_warm", 1)
    workers._warm[("fake",)]=object()
    try:
        assert asyncio.run(workers.retire_idle_workers(time.monotonic()+9999))==[]
        assert workers._warm, "batch の最中に降ろされた"
    finally:
        workers._warm.clear()

# ── キャラクターの声 ────────────────────────────────────────────────────
#
# Qwen3-TTS の voice design には再現性の保証も seed も無い。同じ注文文で呼び
# 直しても同じ声が出るとは限らないので、台詞ごとに design を呼ぶ作りにすると
# キャラが台詞ごとに別人になりうる。注文した声を一度喋らせて見本を掴み、以後は
# その見本からの複製で回す。identity は見本の波形そのものになる。

def test_the_voice_list_shows_what_can_be_chosen(env):
    m=load_app()
    with TestClient(m.app) as c:
        response=c.post('/addon/v1/agent/voice/list',json={})
        assert response.status_code==200,response.text
        body=response.json()
        names={item['speaker'] for item in body['built_in_speakers']}
        # 名前を知らないまま preset を選ばせない。性別と言語も添える。
        assert {'Ono_Anna','Ryan','Vivian'} <= names
        assert all({'speaker','language','gender','description'} <= set(item)
                   for item in body['built_in_speakers'])
        assert 'ja' in body['languages']
        # language は母語であって、話せる言語の全部ではない。実測で、英語・中国語
        # の話者に日本語を読ませても日本語になった。公式話者に日本語の男性が居ない
        # ので、これを言わないと日本語の男性キャラが立たない。
        assert body['built_in_speakers_note']
        assert '母語' in body['built_in_speakers_note']

def test_a_japanese_male_character_can_be_built_from_a_non_native_speaker(env):
    """公式話者に日本語の男性は居ない。だが非母語の話者でも日本語を喋る。

    実測で Ryan / Aiden（英語）と Dylan / Uncle_Fu（中国語）に日本語を読ませ、
    4 人とも日本語になった。この道を塞ぐと、日本語の男性キャラは design に頼る
    しかなくなり、そちらは感情を指定できない。
    """
    m=load_app()
    with TestClient(m.app) as c:
        body=c.post('/addon/v1/agent/voice/create',json={
            'name':'日本語の男','method':'preset','speaker':'Ryan','languages':['ja']}).json()
        assert body['voice_id']
        # 感情も効く。preset である限り、母語かどうかは関係しない。
        assert body['supports_emotion'] is True

def test_a_preset_voice_needs_a_speaker_that_exists(env):
    m=load_app()
    with TestClient(m.app) as c:
        bad=c.post('/addon/v1/agent/voice/create',json={
            "name":"勇者","method":"preset","speaker":"NotAPerson","languages":["ja"]})
        assert bad.status_code==422,bad.text
        assert bad.json()['detail']['code']=='unknown_speaker'
        ok=c.post('/addon/v1/agent/voice/create',json={
            "name":"勇者","method":"preset","speaker":"Ono_Anna","languages":["ja"]})
        assert ok.status_code==200,ok.text
        body=ok.json()
        assert body['voice_id'].startswith('voice:')
        assert body['method']=='preset' and body['speaker']=='Ono_Anna'
        # preset だけが言い方の指示を受け付ける。
        assert body['supports_emotion'] is True
        listed=c.post('/addon/v1/agent/voice/list',json={}).json()['voices']
        assert body['voice_id'] in {item['voice_id'] for item in listed}

def test_cloning_a_person_needs_the_right_to_do_it(env):
    m=load_app()
    with TestClient(m.app) as c:
        response=c.post('/addon/v1/agent/voice/create',json={
            "name":"語り手","method":"clone","languages":["ja"],
            "reference_text":"こんにちは","upload_id":"upload:"+"0"*32})
        assert response.status_code==422,response.text
        assert response.json()['detail']['code']=='voice_rights_confirmation_required'

def test_cloning_needs_the_transcript_of_the_reference(env):
    """書き起こしを省くと話者埋め込みだけの複製になり、声質が落ちると公式が書いている。"""
    m=load_app()
    with TestClient(m.app) as c:
        response=c.post('/addon/v1/agent/voice/create',json={
            "name":"語り手","method":"clone","languages":["ja"],
            "rights_confirmed":True,"upload_id":"upload:"+"0"*32})
        assert response.status_code==422,response.text
        assert response.json()['detail']['code']=='reference_text_required'

def test_designing_a_voice_needs_a_description(env):
    m=load_app()
    with TestClient(m.app) as c:
        response=c.post('/addon/v1/agent/voice/create',json={
            "name":"勇者","method":"design","languages":["ja"]})
        assert response.status_code==422,response.text
        assert response.json()['detail']['code']=='description_required'

def test_an_unknown_method_or_language_is_refused(env):
    m=load_app()
    with TestClient(m.app) as c:
        assert c.post('/addon/v1/agent/voice/create',json={
            "name":"x","method":"summon"}).status_code==422
        assert c.post('/addon/v1/agent/voice/create',json={
            "name":"x","method":"preset","speaker":"Ryan",
            "languages":["klingon"]}).status_code==422

def test_a_designed_voice_is_pinned_to_the_sample_it_produced(env):
    """design を呼び直さない。呼び直した時点で別人になりうる。"""
    m=load_app()
    with TestClient(m.app) as c:
        response=c.post('/addon/v1/agent/voice/create',json={
            "input":{"name":"勇者","method":"design","languages":["ja"],
                     "description":"落ち着いた三十代の男性。低めの声。",
                     "sample_text":"はじめまして。"},
            "correlation":{"job_id":"host-job"}})
        assert response.status_code==200,response.text
        body=response.json()
        assert body['method']=='design'
        # 見本が保存され、以後はその複製で回る。
        assert body['anchored'] is True
        assert body['sample_asset_id']
        # 複製経路は言い方の指示を受けないので、感情は見本の側で持つ。試験の
        # engine は 1 本しか返さないため、持っているのは平静だけになる。指定しても
        # 何も起きない状態なので、効かないと言わなければならない。
        assert body['emotion_choices'] == ['neutral']
        assert body['supports_emotion'] is False
        listed=c.post('/addon/v1/agent/voice/list',json={}).json()['voices']
        mine=next(item for item in listed if item['voice_id']==body['voice_id'])
        assert mine['anchored'] is True and mine['method']=='design'
        assert mine['description']=="落ち着いた三十代の男性。低めの声。"

def test_the_generate_contract_says_a_character_needs_a_voice():
    """道具を一覧から選ぶ側にも、声が要ることを伝える。

    ControlDeck は道具の説明を label と契約の description から作る。label は画面に
    出す名前で 80 文字までなので、そこには書けない。契約に書いていないと、一覧から
    sonic.generate を選んだ使い手には「キャラの台詞には声が要る」が届かず、声を
    指定しないまま呼んで台詞ごとに別人の声になる。
    """
    import json
    from pathlib import Path as _Path

    root = _Path(__file__).parents[1]
    for name in ("generate-request.json", "generate-batch-request.json"):
        schema = json.loads((root / "schemas" / name).read_text(encoding="utf-8"))
        text = schema.get("description") or ""
        assert "voice_id" in text, name
        assert "sonic.voice.create" in text, name
        # 効き方が声によって違うので、確かめる先も言う。
        assert "supports_emotion" in text, name


def test_the_worker_does_not_hold_every_model_it_ever_loaded():
    """載せたものを黙って持ち続けない。

    Qwen3-TTS は用途ごとにモデルが分かれている（声を注文する VoiceDesign 1.7B、
    複製する Base 0.6B、公式話者で読む CustomVoice 0.6B）。上限が無いと、
    キャラクターの声を作ってから喋らせるだけで 3 つが同時に載ったままになり、
    worker が idle で降ろされるまで VRAM を握り続ける。GPT-SoVITS 側は 1 つだけ
    持って載せ替え時に解放しており、ここだけが例外だった。

    降ろすのは最も長く使っていないもの。preset の声と design の声が混ざった
    batch は 2 つのモデルを交互に使うので、そこで台詞ごとに載せ替えると遅い。
    """
    from collections import OrderedDict
    from worker_packs.qwen_tts.worker import make_room

    freed = []
    cache = OrderedDict([("design", 1), ("base", 2)])
    # 上限に達していれば、次を載せる前に最も古いものが降りる。
    assert make_room(cache, 2, lambda: freed.append(True)) == 1
    assert list(cache) == ["base"]
    # 降ろしたときだけ解放を呼ぶ。空きがあるのに毎回呼ばない。
    assert freed == [True]
    assert make_room(cache, 2, lambda: freed.append(True)) == 0
    assert freed == [True]
    # 使ったものは新しい側へ回る（_model が move_to_end する）ので、直前に使った
    # ものは残り、長く使っていないほうが降りる。
    cache = OrderedDict([("base", 1), ("custom", 2)])
    cache.move_to_end("base")
    make_room(cache, 2, lambda: None)
    assert list(cache) == ["base"]


def test_a_named_voice_is_spoken_by_the_engine_that_made_it(env):
    """声を指名したら、その声を作った engine で喋る。

    画面の既定は画面の都合で決まっている。実機では GPT-SoVITS が選ばれていた。
    そこへ MCP から作った Qwen3 の声を渡すと、既定の engine に回されて
    「その engine では作れない声だ」と断られていた。声は engine ごとに作り方が
    違い、別の engine には渡せない。
    """
    m=load_app()
    with TestClient(m.app) as c:
        created=c.post('/addon/v1/agent/voice/create',json={
            "input":{"name":"別engineの勇者","method":"preset","speaker":"Ryan","languages":["ja"]},
            "correlation":{"job_id":"host-job"}}).json()
        c.put('/addon/v1/tts/preferences', json={
            'engine_id': 'tts.gpt-sovits', 'gpt_sovits_model_id': 'lj1995/GPT-SoVITS'})
        from sonicforge import app as module
        request=module.jobs._apply_tts_preferences({
            "task": "speech.tts.synthesize",
            "input": {"text": "こんにちは。", "voice_id": created["voice_id"]},
        })
        assert request["routing"]["engine"] == "tts.qwen3"
        # 名指しの指定はいちばん強い。声より優先する。
        named=module.jobs._apply_tts_preferences({
            "task": "speech.tts.synthesize",
            "routing": {"engine": "tts.gpt-sovits"},
            "input": {"text": "こんにちは。", "voice_id": created["voice_id"]},
        })
        assert named["routing"]["engine"] == "tts.gpt-sovits"


def test_asking_for_an_emotion_nobody_recorded_is_refused(env):
    """持っていない感情を静かに受け流さない。

    見本は声を作るときに 1 回の呼び出しでまとめて作る。あとから足せないので、
    知らない名前を受け取った時点で言う。黙って平静で作ると、使う側は「怒りの
    見本がある」と思ったまま進んでしまう。
    """
    m=load_app()
    with TestClient(m.app) as c:
        response=c.post('/addon/v1/agent/voice/create',json={
            "input":{"name":"勇者","method":"design","languages":["ja"],
                     "description":"落ち着いた三十代の男性。",
                     "emotions":["anger","焦り"]},
            "correlation":{"job_id":"host-job"}})
        assert response.status_code==422,response.text
        assert response.json()['detail']['code']=='invalid_emotions'


def test_the_neutral_sample_is_always_recorded(env):
    """平静だけは必ず要る。

    identity の基準であり、当たらなかった指定の落とし先でもある。怒りだけを
    頼まれても平静を作り、しかも先頭に置く（先頭が identity の基準になる）。
    """
    from sonicforge.app import _resolve_emotions

    assert _resolve_emotions(["anger"]) == ["neutral", "anger"]
    assert _resolve_emotions(["anger", "neutral"]) == ["neutral", "anger"]
    assert _resolve_emotions(None) == ["neutral", "joy", "anger", "sorrow"]


def test_the_joined_samples_are_cut_where_the_worker_said(env, tmp_path):
    """繋がって返る見本を、添えられた切れ目で切る。

    無音を探して切る作りにはしない。探すとずれ、ずれると書き起こしと音が食い
    違って複製の質が落ちる。切れ目は作った側が正確に知っている。
    """
    import wave
    from sonicforge.app import _split_wav

    source = tmp_path / "joined.wav"
    with wave.open(str(source), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(b"".join(bytes([index % 256, 0]) for index in range(300)))
    pieces = _split_wav(source, [{"start": 0, "end": 100}, {"start": 200, "end": 300}])
    assert len(pieces) == 2
    with wave.open(str(pieces[0]), "rb") as handle:
        assert handle.getnframes() == 100
        assert handle.readframes(1) == bytes([0, 0])
    with wave.open(str(pieces[1]), "rb") as handle:
        assert handle.getnframes() == 100
        # 200 番目の標本から始まっている。無音の隙間を跨いで拾えている。
        assert handle.readframes(1) == bytes([200 % 256, 0])


def test_a_written_mood_is_pulled_to_a_sample_that_exists(env):
    """使う側は自然文で書いてくる。それを持っている見本の名前に寄せる。

    当たらなければ平静で読む。黙って別の感情を出すより素直である。
    """
    from sonicforge.voice_catalog import normalize_emotion

    have = ["anger", "joy", "neutral", "sorrow"]
    assert normalize_emotion("強い怒りをこめて", have) == "anger"
    assert normalize_emotion("furious", have) == "anger"
    assert normalize_emotion("悲しげに", have) == "sorrow"
    assert normalize_emotion("嬉しそうに", have) == "joy"
    # 知らない言い方は平静に落ちる。
    assert normalize_emotion("囁くように", have) == "neutral"
    assert normalize_emotion(None, have) == "neutral"
    # 持っていない感情を頼まれても、持っているものから外れない。
    assert normalize_emotion("強い怒りをこめて", ["neutral", "joy"]) == "neutral"


def test_a_voice_can_be_removed_from_opencode(env):
    m=load_app()
    with TestClient(m.app) as c:
        created=c.post('/addon/v1/agent/voice/create',json={
            "name":"端役","method":"preset","speaker":"Ryan","languages":["en"]}).json()
        gone=c.post('/addon/v1/agent/voice/delete',json={"voice_id":created['voice_id']})
        assert gone.status_code==200 and gone.json()['deleted'] is True
        remaining={item['voice_id'] for item in
                   c.post('/addon/v1/agent/voice/list',json={}).json()['voices']}
        assert created['voice_id'] not in remaining
        assert c.post('/addon/v1/agent/voice/delete',
                      json={"voice_id":created['voice_id']}).status_code==404
