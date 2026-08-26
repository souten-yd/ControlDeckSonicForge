from __future__ import annotations

import json
import sys
from pathlib import Path

from backend.sonicforge.audio import write_tone_wav


def emit(request_id: str, payload: dict) -> None:
    print(json.dumps({"request_id": request_id, **payload}, ensure_ascii=False), flush=True)


for line in sys.stdin:
    request_id = "unknown"
    try:
        envelope = json.loads(line)
        request_id = str(envelope["request_id"])
        request = envelope["request"]
        work = Path(envelope["work_dir"])
        work.mkdir(parents=True, exist_ok=True)
        emit(request_id, {"type": "progress", "progress": 0.2, "message": "Persistent fake worker ready"})
        if request["task"] == "speech.asr.transcribe":
            emit(
                request_id,
                {
                    "type": "result",
                    "engine_id": "fake-live",
                    "engine_version": "1",
                    "payload": {
                        "text": "fake transcription",
                        "language": request.get("content_language", "auto"),
                        "segments": [],
                        "persistent_worker": True,
                    },
                },
            )
        else:
            output = work / "output.wav"
            write_tone_wav(output)
            emit(
                request_id,
                {
                    "type": "result",
                    "engine_id": "fake-live",
                    "engine_version": "1",
                    "model_id": "fake-tone",
                    "model_license_id": "test-only",
                    "output_path": str(output),
                    "payload": {"persistent_worker": True},
                },
            )
    except Exception as exc:
        emit(request_id, {"type": "error", "message": str(exc)[:1000]})
