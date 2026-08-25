import asyncio
import time

import httpx
import pytest

from sonicforge.audio import write_tone_wav
from sonicforge.config import ensure_directories, load_settings
from sonicforge.db import Job, make_session_factory
from sonicforge.events import EventBus
from sonicforge.host.client import ControlDeckHostClient, HostIdentity
from sonicforge.jobs import HostedExecution, JobManager
from sonicforge.pipeline_runtime import PipelineRuntime
from sonicforge.pipeline_schema import PipelineRequest


@pytest.mark.asyncio
async def test_asr_ai_tts_releases_between_stages(env, monkeypatch):
    wav = env / 'input.wav'
    write_tone_wav(wav)
    audio_bytes = wav.read_bytes()
    order = []

    async def handler(request):
        path = request.url.path
        if path.endswith('/gateway/capabilities'):
            return httpx.Response(200, json={
                'protocol_version': '1.0',
                'addon_id': 'sonic-forge',
                'control_plane': {
                    'jobs': {'write': True},
                    'resources': {'acquire': True},
                    'files': {'pick': True},
                    'ai': {
                        'inference': True,
                        'release': True,
                        'capabilities': {'text.generate': True, 'vision.analyze': False},
                    },
                },
                'transports': {'runtime_http': {'available': True}, 'device_session': {'available': False}},
            })
        if path.endswith('/grants/grant:audio'):
            return httpx.Response(200, json={
                'grant_id': 'grant:audio', 'kind': 'read', 'name': 'input.wav', 'size': len(audio_bytes)
            })
        if path.endswith('/grants/grant:audio/content'):
            return httpx.Response(200, content=audio_bytes)
        if path.endswith('/ai/complete'):
            order.append('ai.complete')
            return httpx.Response(200, json={'content': 'AI reply', 'capability': 'text.generate'})
        if path.endswith('/ai/release'):
            order.append('ai.release')
            return httpx.Response(200, json={'released': True, 'reason': 'released', 'freed_bytes': 1})
        if '/jobs/' in path and request.method == 'PATCH':
            return httpx.Response(200, json={'ok': True})
        if path.endswith('/control'):
            return httpx.Response(200, json={'status': 'running', 'cancel_requested': False})
        return httpx.Response(404, json={'detail': 'missing'})

    settings = load_settings()
    ensure_directories(settings)
    factory = make_session_factory(settings)
    host = ControlDeckHostClient('http://127.0.0.1:8765', transport=httpx.MockTransport(handler))
    manager = JobManager(settings, factory, EventBus(), host_client=host)

    def gpu_required(_request):
        return True

    async def acquire(_job_id, request, _execution):
        order.append('acquire:' + request['task'])
        return None

    async def release(_execution):
        order.append('release')

    monkeypatch.setattr(manager, '_gpu_required', gpu_required)
    monkeypatch.setattr(manager, '_acquire_resource', acquire)
    monkeypatch.setattr(manager, '_release_resource', release)

    runtime = PipelineRuntime(jobs=manager, session_factory=factory, host_client=host)
    identity = HostIdentity(
        authorization='Bearer test',
        addon_id='sonic-forge',
        subject='job:host-test',
        expires_at=int(time.time()) + 300,
        granted_capabilities=frozenset({'jobs.write', 'resources.acquire', 'files.pick', 'ai.inference'}),
    )
    pipeline = PipelineRequest.model_validate({
        'pipeline': 'voice-agent-turn',
        'input': {'kind': 'audio_grant', 'grant_id': 'grant:audio'},
        'stages': [
            {'id': 'asr', 'kind': 'speech.asr', 'routing': {'engine': 'fake', 'model': None, 'device': 'auto'}},
            {'id': 'llm', 'kind': 'host.ai.text'},
            {'id': 'tts', 'kind': 'speech.tts', 'routing': {'engine': 'fake', 'model': None, 'device': 'auto'}},
        ],
        'delivery': {'mode': 'asset', 'profile': 'test'},
    })
    row = runtime.create(pipeline, hosted=HostedExecution(identity=identity, host_job_id='host-test'))

    for _ in range(150):
        await asyncio.sleep(0.03)
        with factory() as session:
            terminal = session.get(Job, row.id)
            if terminal is not None and terminal.state not in {'queued', 'running'}:
                state = terminal.state
                error = terminal.error_message
                break
    else:
        raise AssertionError('pipeline did not finish')

    assert state == 'succeeded', error
    assert order[:6] == [
        'acquire:speech.asr.transcribe',
        'release',
        'ai.complete',
        'ai.release',
        'acquire:speech.tts.synthesize',
        'release',
    ]
    await host.close()
