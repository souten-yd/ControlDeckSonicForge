"""Which models a task may actually be pointed at.

The workers already accept `routing.model`, but until now the only way to use
it was to type a Hugging Face repository id from memory into a free-text box.
That is not a choice anyone can make without the source open beside them.

This module names the models that a request can legitimately select, keyed by
task, so the UI can offer them as a list. It is deliberately narrower than
"every model on disk": swapping the speech model that a saved voice was built
against produces a different voice, so voice-driven selection stays with the
voice. What is left is the choice a person actually has - which transcription
model to listen with, and which speech model to read plain text with.

The ids come from `setup` so that a pinned model can never drift away from the
list the UI offers.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from .capabilities import _state
from .setup import (
    ACESTEP_DIT,
    KOTOBA_WHISPER,
    QWEN_CUSTOM_VOICE,
    QWEN_VOICE_DESIGN,
    STABLE_AUDIO_SMALL_SFX,
    WHISPER_TURBO,
)

# task -> (component that must be installed, model ids in the order to offer)
TASK_MODELS: dict[str, tuple[str, tuple[str, ...]]] = {
    "speech.asr.transcribe": ("speech-essentials", (KOTOBA_WHISPER, WHISPER_TURBO)),
    "speech.tts.synthesize": ("speech-essentials", (QWEN_CUSTOM_VOICE, QWEN_VOICE_DESIGN)),
    "audio.sfx.generate": ("game-audio", (STABLE_AUDIO_SMALL_SFX,)),
    "audio.ambience.generate": ("game-audio", (STABLE_AUDIO_SMALL_SFX,)),
    "music.generate": ("music", (ACESTEP_DIT,)),
}

# The engine that serves each task. Named so the UI can show it instead of
# asking for a free-text engine id nobody can guess.
TASK_ENGINE: dict[str, str] = {
    "speech.asr.transcribe": "asr.whisper",
    "speech.tts.synthesize": "tts.qwen3",
    "audio.sfx.generate": "audio.stable-audio-3",
    "audio.ambience.generate": "audio.stable-audio-3",
    "music.generate": "music.ace-step-1.5",
}


def model_document(session: Session, *, fake_enabled: bool = False) -> dict:
    """The selectable models per task, with whether each is ready to use."""
    tasks = []
    for task, (component, model_ids) in TASK_MODELS.items():
        ready = fake_enabled or _state(session, component) == "available"
        tasks.append(
            {
                "task": task,
                "component": component,
                "engine": TASK_ENGINE[task],
                "installed": ready,
                "models": [
                    {"id": model_id, "installed": ready} for model_id in model_ids
                ],
            }
        )
    return {"tasks": tasks}
