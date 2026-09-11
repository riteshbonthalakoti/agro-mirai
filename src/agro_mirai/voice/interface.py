"""``VoiceService`` — the voice/translation interface, per
``specs/core/voice-interface.md``.

Every module that needs translation, speech-to-text, or text-to-speech
depends on this ``Protocol``, never on a specific vendor SDK. Both
``AI4BharatVoiceService`` and ``BhashiniVoiceAdapter`` implement it in
full; a shared conformance test suite (``tests/voice/test_conformance.py``)
runs the same assertions against both.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

#: v1 scope — see specs/core/voice-interface.md "Supported language set
#: for v1". Adapters may support a subset of this; they must not support
#: more than the full enums.md language_code list. Widened from {en, kn}
#: to {en, kn, te, hi} in Module 25 — every one of translation/STT/TTS
#: was individually verified against the real AI4Bharat model cards
#: before this widened, not assumed; see
#: decisions/0021-language-expansion-te-hi.md for the evidence and the
#: one real per-language TTS-backend asymmetry it documents (kn/te use
#: ai4bharat/vits_rasa_13, en/hi use Piper — vits_rasa_13 has no Hindi
#: voice, Piper has no Kannada/Telugu voice).
V1_LANGUAGES = frozenset({"en", "kn", "te", "hi"})

#: Full enums.md language_code list, for validating adapter-declared
#: supported sets and building clear "not yet implemented" errors.
ALL_KNOWN_LANGUAGES = frozenset(
    {"en", "hi", "kn", "ta", "te", "mr", "bn", "gu"}
)


class VoiceServiceError(Exception):
    """Base class for all VoiceService errors."""


class UnsupportedLanguageError(VoiceServiceError):
    """Raised when a requested language_code is not in the adapter's
    supported set."""

    def __init__(self, language_code: str, supported: frozenset[str]):
        self.language_code = language_code
        self.supported = supported
        super().__init__(
            f"language {language_code!r} is not supported by this "
            f"adapter (supported: {sorted(supported)})"
        )


class VoiceUnavailableError(VoiceServiceError):
    """Raised when the underlying model/API is not usable right now
    (not downloaded, credentials missing, backend unreachable)."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"voice backend unavailable: {reason}")


@runtime_checkable
class VoiceService(Protocol):
    """Engine-neutral translation/ASR/TTS contract. See
    voice-interface.md for the full method contract."""

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        ...

    def speech_to_text(
        self, audio_bytes: bytes, expected_lang: str | None = None
    ) -> tuple[str, str]:
        ...

    def text_to_speech(self, text: str, lang: str) -> bytes:
        ...
