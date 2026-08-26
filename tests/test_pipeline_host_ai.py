import asyncio
import time

import httpx
import pytest

from sonicforge.config import ensure_directories, load_settings
from sonicforge.db import Job, make_session_factory
from sonicforge.events import EventBus
from sonicforge.host.client import ControlDeckHostClient, HostIdentity
from sonicforge.jobs import HostedExecution, JobManager
from sonicforge.pipeline_runtime import PipelineRuntime
from sonicforge.pipeline_schema import PipelineRequest


@pytest.mark.asyncio
async def test_text_host_ai_tts_pipeline(env):
    calls = []

    async def handler(request):
        calls.append((request.method, request.url.path))
        if request.url.path.endswith('/gateway/capabilities'):
            return httpx.Response(200, json={
                'protocol_version': '1.0',
                'addon_id': 'sonic-forge',
                'control_plane': {
                    'jobs': {'write': True},
                    'resources': {'acquire': True},
                    'files': {},
                    'ai': {
                        'inference': True,
                        'release': True,
                        'capabilities': {'text.generate': True, 'vision.analyze': False},
                    },
                },
                'transports': {
                    'runtime_http': {'available': True},
                    'embedded_websocket_proxy': {'available': True},
                    'device_session': {'available': False},
                },
            })
        if request.url.path.endswith('/ai/complete'):
            return httpx.Response(200, json={
                'content': 'Hello from ControlDeck AI',
                'capability': 'text.generate',
            })
        if request.url.path.endswith('/ai/release'):
            return httpx.Response(200, json={
                'released': True,
                'reason': 'released',
                'freed_bytes': 1024,
            })
        if '/jobs/' in request.url.path and request.method == 'PATCH':
            return httpx.Response(200, json={'ok': True})
        if request.url.path.endswith('/control'):
            return httpx.Response(200, json={'status': 'running', 'cancel_requested': False})
        return httpx.Response(404, json={'detail': 'missing'})

    settings = load_settings()
    ensure_directories(settings)
    factory = make_session_factory(settings)
    host = ControlDeckHostClient(
        'http://127.0.0.1:8765',
        transport=httpx.MockTransport(handler),
    )
    manager = JobManager(settings, factory, EventBus(), host_client=host)
    runtime = PipelineRuntime(jobs=manager, session_factory=factory, host_client=host)
    identity = HostIdentity(
        authorization='Bearer test',
        addon_id='sonic-forge',
        subject='job:host-test',
        expires_at=int(time.time()) + 300,
        granted_capabilities=frozenset({'jobs.write', 'resources.acquire', 'ai.inference'}),
    )
    request = PipelineRequest.model_validate({
        'pipeline': 'text-reply-audio',
        'input': {'kind': 'text', 'text': '挨拶して'},
        'stages': [
            {'id': 'llm', 'kind': 'host.ai.text'},
            {
                'id': 'tts',
                'kind': 'speech.tts',
                'routing': {'engine': 'fake', 'model': None, 'device': 'auto'},
            },
        ],
        'delivery': {'mode': 'asset', 'profile': 'test'},
    })
    row = runtime.create(
        request,
        hosted=HostedExecution(identity=identity, host_job_id='host-test'),
    )
    terminal = None
    for _ in range(150):
        await asyncio.sleep(0.03)
        with factory() as session:
            terminal = session.get(Job, row.id)
            if terminal is not None and terminal.state not in {'queued', 'running'}:
                result = dict(terminal.result or {})
                state = terminal.state
                break
    else:
        raise AssertionError('pipeline did not finish')

    assert state == 'succeeded', terminal.error_message if terminal else None
    assert result['asset_id'].startswith('asset:')
    assert result['pipeline']['stages'][0]['kind'] == 'host.ai.text'
    assert result['pipeline']['stages'][1]['kind'] == 'speech.tts'
    assert ('POST', '/api/v1/addon-runtime/sonic-forge/ai/complete') in calls
    assert ('POST', '/api/v1/addon-runtime/sonic-forge/ai/release') in calls
    await host.close()
