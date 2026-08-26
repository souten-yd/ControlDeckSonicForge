from __future__ import annotations

import hashlib, math, struct, wave
from pathlib import Path
from typing import Any


def write_tone_wav(path: Path, duration_sec: float = 0.35, frequency: float = 440.0, sample_rate: int = 24000) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True); frames=max(1,int(duration_sec*sample_rate))
    with wave.open(str(path),"wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(sample_rate)
        for i in range(frames):
            amp=int(32767*0.08*math.sin(2*math.pi*frequency*i/sample_rate)); wav.writeframesraw(struct.pack("<h",amp))
    return inspect_wav(path)


def inspect_wav(path: Path) -> dict[str, Any]:
    with wave.open(str(path),"rb") as wav:
        channels=wav.getnchannels(); sample_rate=wav.getframerate(); frames=wav.getnframes(); duration_ms=round(frames*1000/sample_rate) if sample_rate else 0
    data=path.read_bytes()
    if duration_ms<=0: raise ValueError("audio duration is zero")
    return {"size_bytes":len(data),"sha256":hashlib.sha256(data).hexdigest(),"duration_ms":duration_ms,"sample_rate":sample_rate,"channels":channels,"mime_type":"audio/wav","qa":{"decode":"passed","duration":"passed","semantic":"not_checked"}}
