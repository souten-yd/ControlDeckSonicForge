import time, httpx, pytest
from sonicforge.host.client import ControlDeckHostClient, HostApiError, HostIdentity


@pytest.mark.asyncio
async def test_ai_residency_creation_allows_host_model_cold_start(monkeypatch):
    client = ControlDeckHostClient("http://127.0.0.1:8765")
    captured = {}

    async def raw(method, path, authorization, addon_id, **kwargs):
        captured.update(kwargs)
        return {"held": False}

    monkeypatch.setattr(client, "_raw", raw)
    identity = HostIdentity(
        "Bearer abc",
        subject="18",
        expires_at=int(time.time()) + 300,
        granted_capabilities=frozenset({"ai.inference"}),
    )
    await client.ai_residency_create(identity)
    assert captured["timeout_sec"] == 190
    await client.close()


@pytest.mark.asyncio
async def test_detached_host_job_is_explicit_and_opt_in(monkeypatch):
    client = ControlDeckHostClient("http://127.0.0.1:8765")
    captured = {}

    async def raw(method, path, authorization, addon_id, **kwargs):
        captured.update(kwargs)
        return {"created": True, "job": {"id": "child-job"}}

    monkeypatch.setattr(client, "_raw", raw)
    identity = HostIdentity(
        "Bearer abc",
        subject="job:parent",
        expires_at=int(time.time()) + 300,
        granted_capabilities=frozenset({"jobs.write"}),
    )
    await client.create_or_attach_job(identity, "durable generation", detached=True)
    assert captured["json"] == {"title": "durable generation", "detached": True}
    await client.close()


@pytest.mark.asyncio
async def test_regular_host_job_request_omits_detached_for_older_hosts(monkeypatch):
    client = ControlDeckHostClient("http://127.0.0.1:8765")
    captured = {}

    async def raw(method, path, authorization, addon_id, **kwargs):
        captured.update(kwargs)
        return {"created": False, "job": {"id": "existing-job"}}

    monkeypatch.setattr(client, "_raw", raw)
    identity = HostIdentity("Bearer abc", subject="job:existing-job")
    await client.create_or_attach_job(identity, "attached generation")
    assert captured["json"] == {"title": "attached generation"}
    await client.close()


@pytest.mark.asyncio
async def test_new_host_job_adopts_exact_child_scoped_credential(monkeypatch):
    client = ControlDeckHostClient("http://127.0.0.1:8765")
    previous = HostIdentity(
        "Bearer parent",
        subject="job:parent",
        expires_at=int(time.time()) + 300,
        granted_capabilities=frozenset({"jobs.write"}),
    )
    child = HostIdentity(
        "Bearer child",
        subject="job:child",
        expires_at=int(time.time()) + 300,
        granted_capabilities=previous.granted_capabilities,
    )

    async def authenticate(headers):
        assert headers["Authorization"] == "Bearer child-token"
        return child

    monkeypatch.setattr(client, "authenticate", authenticate)
    refreshed = await client.identity_from_job_response(
        previous,
        {
            "created": True,
            "job": {"id": "child"},
            "access_token": "child-token",
            "token_type": "Bearer",
        },
    )
    assert refreshed is child
    await client.close()


@pytest.mark.asyncio
async def test_new_host_job_rejects_wrong_child_subject(monkeypatch):
    client = ControlDeckHostClient("http://127.0.0.1:8765")
    previous = HostIdentity(
        "Bearer parent",
        subject="job:parent",
        expires_at=int(time.time()) + 300,
        granted_capabilities=frozenset({"jobs.write"}),
    )

    async def authenticate(_headers):
        return HostIdentity(
            "Bearer forged",
            subject="job:other",
            expires_at=int(time.time()) + 300,
            granted_capabilities=previous.granted_capabilities,
        )

    monkeypatch.setattr(client, "authenticate", authenticate)
    with pytest.raises(HostApiError, match="changed the refreshed service token scope"):
        await client.identity_from_job_response(
            previous,
            {
                "created": True,
                "job": {"id": "child"},
                "access_token": "forged-token",
                "token_type": "Bearer",
            },
        )
    await client.close()

@pytest.mark.asyncio
async def test_host_auth_and_output_roundtrip():
    async def handler(req):
        assert req.headers['x-control-deck-addon-id']=='sonic-forge'
        if req.url.path.endswith('/token/introspect'):
            return httpx.Response(200,json={'active':True,'addon_id':'sonic-forge','subject':'user:test','expires_at':int(time.time())+300,'granted_capabilities':['files.export']})
        if req.url.path.endswith('/files/outputs'):
            return httpx.Response(200,json={'output_id':'out:1'})
        return httpx.Response(200,json={'ok':True})
    client=ControlDeckHostClient('http://127.0.0.1:8765',transport=httpx.MockTransport(handler))
    ident=await client.authenticate({'Authorization':'Bearer abc','X-Control-Deck-Addon-ID':'sonic-forge'})
    assert ident.subject=='user:test'
    out=await client.create_output(ident,{'grant_id':'grant:x','filename':'a.wav'})
    assert out['output_id']=='out:1'
    await client.close()

@pytest.mark.asyncio
async def test_host_ai_complete_and_release():
    calls=[]
    async def handler(req):
        calls.append(req.url.path)
        if req.url.path.endswith('/token/introspect'):
            return httpx.Response(200,json={'active':True,'addon_id':'sonic-forge','subject':'user:test','expires_at':int(time.time())+300,'granted_capabilities':['ai.inference']})
        if req.url.path.endswith('/ai/capabilities'):
            return httpx.Response(200,json={'text.generate':{'available':True},'vision.analyze':{'available':False}})
        if req.url.path.endswith('/ai/complete'):
            body=__import__('json').loads(req.content)
            assert body['capability']=='text.generate'
            assert body['messages'][-1]['content']=='爆発音'
            return httpx.Response(200,json={'content':'a sharp explosion','capability':'text.generate'})
        if req.url.path.endswith('/ai/release'):
            return httpx.Response(200,json={'released':True,'reason':'released','freed_bytes':1})
        return httpx.Response(404,json={'detail':'missing'})
    client=ControlDeckHostClient('http://127.0.0.1:8765',transport=httpx.MockTransport(handler))
    ident=await client.authenticate({'Authorization':'Bearer abc','X-Control-Deck-Addon-ID':'sonic-forge'})
    caps=await client.ai_capabilities(ident); assert caps['text.generate']['available'] is True
    result=await client.ai_complete(ident,[{'role':'user','content':'爆発音'}],max_tokens=32)
    assert result['content']=='a sharp explosion'
    released=await client.ai_release(ident); assert released['released'] is True
    assert any(path.endswith('/ai/complete') for path in calls)
    assert any(path.endswith('/ai/release') for path in calls)
    await client.close()

@pytest.mark.asyncio
async def test_gateway_discovery_uses_versioned_host_document():
    async def handler(req):
        if req.url.path.endswith('/token/introspect'):
            return httpx.Response(200,json={'active':True,'addon_id':'sonic-forge','subject':'user:test','expires_at':int(time.time())+300,'granted_capabilities':['jobs.write','resources.acquire','ai.inference']})
        if req.url.path.endswith('/gateway/capabilities'):
            return httpx.Response(200,json={
                'protocol_version':'1.0','addon_id':'sonic-forge',
                'control_plane':{'jobs':{'write':True},'resources':{'acquire':True},'files':{},'ai':{'inference':True,'capabilities':{'text.generate':True,'vision.analyze':False}}},
                'transports':{'runtime_http':{'available':True},'embedded_websocket_proxy':{'available':True},'device_session':{'available':False}},
            })
        return httpx.Response(404,json={'detail':'missing'})
    client=ControlDeckHostClient('http://127.0.0.1:8765',transport=httpx.MockTransport(handler))
    ident=await client.authenticate({'Authorization':'Bearer abc','X-Control-Deck-Addon-ID':'sonic-forge'})
    gateway=await client.gateway_capabilities(ident)
    assert gateway['protocol_version']=='1.0'
    assert gateway['control_plane']['resources']['acquire'] is True
    assert gateway['control_plane']['ai']['capabilities']['text.generate'] is True
    await client.close()

@pytest.mark.asyncio
async def test_gateway_discovery_projects_legacy_host_without_new_endpoint():
    calls=[]
    async def handler(req):
        calls.append(req.url.path)
        if req.url.path.endswith('/token/introspect'):
            return httpx.Response(200,json={'active':True,'addon_id':'sonic-forge','subject':'user:test','expires_at':int(time.time())+300,'granted_capabilities':['files.export','ai.inference']})
        if req.url.path.endswith('/gateway/capabilities'):
            return httpx.Response(404,json={'detail':'missing'})
        if req.url.path.endswith('/ai/capabilities'):
            return httpx.Response(200,json={'text.generate':{'available':True},'vision.analyze':{'available':False}})
        return httpx.Response(404,json={'detail':'missing'})
    client=ControlDeckHostClient('http://127.0.0.1:8765',transport=httpx.MockTransport(handler))
    ident=await client.authenticate({'Authorization':'Bearer abc','X-Control-Deck-Addon-ID':'sonic-forge'})
    gateway=await client.gateway_capabilities(ident)
    assert gateway['compatibility']['source']=='legacy_projection'
    assert gateway['control_plane']['files']['export'] is True
    assert gateway['control_plane']['ai']['capabilities']['text.generate'] is True
    assert gateway['transports']['device_session']['available'] is False
    assert any(path.endswith('/gateway/capabilities') for path in calls)
    await client.close()
