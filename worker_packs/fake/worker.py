from __future__ import annotations

import json
import os
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
    # 声を作るときは、identity の見本 1 本と感情別の見本を続けて返す約束である。
    # 本物の engine は 1 ファイルに繋いで切れ目を標本位置で添えるので、ここでも
    # 同じ形にする。添えないと「頼んだ感情の見本がそろわなかった」と扱われる。
    voice = (request.get("input") or {}).get("_internal_voice")
    recipe = (voice or {}).get("recipe") or {}
    emotion_texts = recipe.get("emotion_texts") or []
    if recipe.get("method") == "design" and emotion_texts:
        import wave

        with wave.open(str(output), "rb") as handle:
            params = handle.getparams()
            frames = handle.readframes(params.nframes)
        gap = b"\x00" * (params.sampwidth * params.nchannels * int(params.framerate * 0.4))
        pieces, segments, cursor = [], [], 0
        for index in range(1 + len(emotion_texts)):
            if index:
                pieces.append(gap)
                cursor += params.nframes and len(gap) // (params.sampwidth * params.nchannels)
            segments.append({"start": cursor, "end": cursor + params.nframes})
            pieces.append(frames)
            cursor += params.nframes
        with wave.open(str(output), "wb") as handle:
            handle.setparams(params._replace(nframes=0))
            handle.writeframes(b"".join(pieces))
        # 見本が足りないまま返ってきたときに呼んだ側が気づけるかを試すための栓。
        # 足りないことは作った側にしか分からないので、試験でしか作れない。
        if os.environ.get("SONICFORGE_FAKE_VOICE_DROP_SEGMENT") == "1":
            segments = segments[:-1]
        result_payload["segments"] = segments
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
    # readline を使う。`for raw in sys.stdin` は先読みバッファが埋まるか EOF まで
    # 1 行目を返さないので、stdin を開いたまま次の要求を待つ使い方だと止まる。
    while True:
        raw = sys.stdin.readline()
        if not raw:
            return
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
