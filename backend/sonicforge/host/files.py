from __future__ import annotations
import re
from pathlib import Path
from .client import ControlDeckHostClient, HostIdentity
OPAQUE_GRANT=re.compile(r'^grant:[A-Za-z0-9._:-]{1,256}$')
def require_grant_id(value:str)->str:
    if not OPAQUE_GRANT.fullmatch(value): raise ValueError('a scoped grant ID is required; host paths are never accepted')
    return value
async def read_grant(client:ControlDeckHostClient,identity:HostIdentity,grant_id:str,*,max_bytes:int=1024*1024*1024):
    scoped=require_grant_id(grant_id); meta=await client.grant_metadata(identity,scoped); content=await client.grant_content(identity,scoped,max_bytes=max_bytes)
    if meta.get('kind')!='read' or meta.get('size')!=len(content): raise ValueError('ControlDeck read grant metadata does not match content')
    return meta,content
async def commit_file(client:ControlDeckHostClient,identity:HostIdentity,*,host_job_id:str,grant_id:str,source:Path,filename:str,mime_type:str,sha256:str):
    scoped=require_grant_id(grant_id); content=source.read_bytes(); created=await client.create_output(identity,{'job_id':host_job_id,'grant_id':scoped,'filename':filename,'size':len(content),'sha256':sha256,'content_type':mime_type}); oid=created.get('output_id')
    if not isinstance(oid,str) or not oid: raise ValueError('ControlDeck did not return an output ID')
    await client.upload_output(identity,oid,content); return await client.commit_output(identity,oid)
