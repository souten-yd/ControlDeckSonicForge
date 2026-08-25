import time, httpx, pytest
from sonicforge.host.client import ControlDeckHostClient

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
