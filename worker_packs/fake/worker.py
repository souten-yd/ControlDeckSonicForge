from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from backend.sonicforge.audio import write_tone_wav


def emit(value: dict) -> None:
    print(json.dumps(value, ensure_ascii=False), flush=True)


def handle(payload: dict) -> None:
    request = payload["request"]
    work = Path(payload["work_dir"])
    work.mkdir(parents=True, exist_ok=True)
    for progress, message in [(0.15, "Preparing"), (0.55, "Generating"), (0.9, "Validating")]:
        emit({"type": "progress", "progress": progress, "message": message})
        time.sleep(0.01)
    if request["task"] == "speech.asr.transcribe":
        emit(
            {
                "type": "result",
                "engine_id": "fake",
                "engine_version": "1",
                "payload": {
                    "text": "fake transcription",
                    "language": request.get("content_language", "auto"),
                    "segments": [],
                    "warm_model_cache": True,
                },
            }
        )
        return
    output = work / "output.wav"
    write_tone_wav(output)
    result_payload = {"preview": True, "warm_model_cache": True}
    normalization = (request.get("input") or {}).get("_internal_prompt_normalization")
    if isinstance(normalization, dict):
        result_payload["prompt_normalization"] = normalization
    emit(
        {
            "type": "result",
            "engine_id": "fake",
            "engine_version": "1",
            "model_id": "fake-tone",
            "model_license_id": "test-only",
            "output_path": str(output),
            "payload": result_payload,
        }
    )


def main() -> None:
    for raw in sys.stdin:
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
            if value.get("type") == "shutdown":
                return
            handle(value)
        except Exception as exc:
            emit({"type": "error", "message": str(exc)})


if __name__ == "__main__":
    main()
