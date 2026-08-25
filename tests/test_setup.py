from sonicforge.config import load_settings, ensure_directories
from sonicforge.db import make_session_factory
from sonicforge import setup

def test_setup_plan_and_idempotent_apply(env):
    import asyncio
    s=load_settings(); ensure_directories(s); f=make_session_factory(s)
    p=setup.plan(s,'speech-essentials'); assert p['components'][0]['id']=='speech-essentials'
    with f() as session: a=asyncio.run(setup.apply(s,session,'speech-essentials'))
    with f() as session: b=asyncio.run(setup.apply(s,session,'speech-essentials')); st=setup.status(session)
    assert st['state']=='available'; assert a['components'][0]['installed']; assert b['components'][0]['installed']
