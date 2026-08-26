"""Voice & language services — translation, ASR, TTS.

Per ``specs/core/voice-interface.md``. Callers depend on
``VoiceService``, never on a specific vendor SDK (mirrors
``agro_mirai.persistence.store.DataStore`` for CLAUDE.md hard rule #3's
"no module talks to an engine/vendor directly" spirit).
"""
from agro_mirai.voice.ai4bharat_voice import AI4BharatVoiceService
from agro_mirai.voice.bhashini_voice import BhashiniVoiceAdapter
from agro_mirai.voice.interface import (
    UnsupportedLanguageError,
    VoiceService,
    VoiceServiceError,
    VoiceUnavailableError,
)

__all__ = [
    "VoiceService",
    "VoiceServiceError",
    "UnsupportedLanguageError",
    "VoiceUnavailableError",
    "AI4BharatVoiceService",
    "BhashiniVoiceAdapter",
]
