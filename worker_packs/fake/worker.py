from __future__ import annotations
import json, sys, time
from pathlib import Path
from backend.sonicforge.audio import write_tone_wav

payload=json.loads(sys.stdin.readline())
request=payload["request"]
work=Path(payload["work_dir"])
for p,msg in [(0.15,"Preparing"),(0.55,"Generating"),(0.9,"Validating")]:
    print(json.dumps({"type":"progress","progress":p,"message":msg}), flush=True); time.sleep(0.03)
if request["task"] == "speech.asr.transcribe":
    print(json.dumps({"type":"result","engine_id":"fake","engine_version":"1","payload":{"text":"fake transcription","language":request.get("content_language","auto"),"segments":[]}}), flush=True)
else:
    output=work/"output.wav"; write_tone_wav(output)
    print(json.dumps({"type":"result","engine_id":"fake","engine_version":"1","model_id":"fake-tone","model_license_id":"test-only","output_path":str(output),"payload":{"preview":True}}), flush=True)
