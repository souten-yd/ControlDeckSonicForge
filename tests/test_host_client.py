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
