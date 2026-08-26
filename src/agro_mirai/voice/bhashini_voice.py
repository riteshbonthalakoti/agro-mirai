"""``BhashiniVoiceAdapter`` — stub ``VoiceService`` implementation for
the Digital India Bhashini API.

Bhashini API access has been requested but has not cleared yet (see
``docs/TOOLING.md``). Per the module scope, this adapter is not blocked
on that: it implements the same ``VoiceService`` contract so swapping it
in later is a config change, not a rewrite, but every method raises
``VoiceUnavailableError`` until real credentials are wired in via
``BHASHINI_API_KEY`` / ``BHASHINI_USER_ID`` / ``BHASHINI_ULCA_API_KEY``
(the three credentials the Bhashini pipeline API requires — see
https://bhashini.gitbook.io/bhashini-apis).
"""
from __future__ import annotations

import os

from agro_mirai.voice.interface import UnsupportedLanguageError, V1_LANGUAGES, VoiceUnavailableError

_REQUIRED_ENV_VARS = ("BHASHINI_API_KEY", "BHASHINI_USER_ID", "BHASHINI_ULCA_API_KEY")


class BhashiniVoiceAdapter:
    def __init__(self):
        self._credentials = {name: os.environ.get(name) for name in _REQUIRED_ENV_VARS}

    def _check_supported(self, lang: str) -> None:
        if lang not in V1_LANGUAGES:
            raise UnsupportedLanguageError(lang, V1_LANGUAGES)

    def _require_credentials(self) -> None:
        missing = [name for name, value in self._credentials.items() if not value]
        if missing:
            raise VoiceUnavailableError(
                "bhashini_credentials_missing: set " + ", ".join(missing)
            )
        # Credentials are present but no HTTP client is implemented yet —
        # the seam exists, the wiring doesn't. Nothing is hand-faked here:
        # this always raises rather than pretending to call the API.
        raise VoiceUnavailableError(
            "bhashini_not_implemented: credentials are configured but the "
            "Bhashini pipeline HTTP client has not been implemented yet"
        )

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        self._check_supported(source_lang)
        self._check_supported(target_lang)
        self._require_credentials()
        raise AssertionError("unreachable")  # pragma: no cover

    def speech_to_text(
        self, audio_bytes: bytes, expected_lang: str | None = None
    ) -> tuple[str, str]:
        if expected_lang is not None:
            self._check_supported(expected_lang)
        self._require_credentials()
        raise AssertionError("unreachable")  # pragma: no cover

    def text_to_speech(self, text: str, lang: str) -> bytes:
        self._check_supported(lang)
        self._require_credentials()
        raise AssertionError("unreachable")  # pragma: no cover
