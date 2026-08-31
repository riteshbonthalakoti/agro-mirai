"""``RemoteVoiceService`` — implements the ``VoiceService`` Protocol by
calling the standalone ``services/voice`` container over HTTP (Module 21).

A third adapter alongside ``AI4BharatVoiceService`` (real, local/in-
process) and ``BhashiniVoiceAdapter`` (stub). This one is real too, but
"local" in a different sense: the AI4Bharat models actually run in the
``services/voice`` container, and this class is a thin HTTP client so
callers elsewhere in this codebase (``ExplanationService`` etc.) don't
need to change to consume it — same Protocol shape, different transport.

Uses ``requests``, consistent with ``agro_mirai.api.cnn_client`` and the
Module 03 acquisition adapters.
"""
from __future__ import annotations

import os

import requests

from agro_mirai.voice.interface import VoiceUnavailableError

DEFAULT_TIMEOUT_S = 30


class RemoteVoiceService:
    def __init__(self, base_url: str | None = None, timeout: float | None = None):
        self._base_url = (base_url or os.environ.get("VOICE_SERVICE_URL", "")).rstrip("/")
        if not self._base_url:
            raise VoiceUnavailableError("VOICE_SERVICE_URL is not configured")
        self._timeout = timeout or float(os.environ.get("VOICE_SERVICE_TIMEOUT_S", DEFAULT_TIMEOUT_S))

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        try:
            resp = requests.post(
                f"{self._base_url}/translate",
                json={"text": text, "source_lang": source_lang, "target_lang": target_lang},
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            raise VoiceUnavailableError(f"voice service unreachable: {exc}") from exc
        if resp.status_code != 200:
            raise VoiceUnavailableError(f"voice service returned {resp.status_code}: {resp.text}")
        return resp.json()["text"]

    def speech_to_text(self, audio_bytes: bytes, expected_lang: str | None = None) -> tuple[str, str]:
        data = {"expected_lang": expected_lang} if expected_lang else {}
        try:
            resp = requests.post(
                f"{self._base_url}/speech-to-text",
                files={"audio": ("audio.wav", audio_bytes)},
                data=data,
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            raise VoiceUnavailableError(f"voice service unreachable: {exc}") from exc
        if resp.status_code != 200:
            raise VoiceUnavailableError(f"voice service returned {resp.status_code}: {resp.text}")
        body = resp.json()
        return body["text"], body["detected_lang"]

    def text_to_speech(self, text: str, lang: str) -> bytes:
        try:
            resp = requests.post(
                f"{self._base_url}/text-to-speech",
                json={"text": text, "lang": lang},
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            raise VoiceUnavailableError(f"voice service unreachable: {exc}") from exc
        if resp.status_code != 200:
            raise VoiceUnavailableError(f"voice service returned {resp.status_code}: {resp.text}")
        return resp.content
