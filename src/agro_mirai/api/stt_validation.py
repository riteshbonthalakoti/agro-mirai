"""Upload validation for ``POST /v2/stt`` (Module 23).

Mirrors ``image_validation.py``'s real-content-sniffing approach rather
than trusting the client's filename/Content-Type — checks the file's
magic bytes against the three formats the mobile client and
``services/voice`` are expected to exchange (WAV, OGG, MP3). This is
weaker than ``image_validation.py``'s full Pillow decode-and-verify (no
equivalent lightweight, dependency-free audio-decoding library is already
in this project's stack, and adding one — e.g. ``pydub``/``ffmpeg-python``
— to the main API process would cut against the Render-free-tier /
no-heavy-deps-in-the-main-process constraint decisions/0019 sets out for
exactly this reason); a magic-byte check catches "this isn't audio at
all," not "this WAV is truncated/corrupt mid-stream" — an honest,
documented gap, not a silent one.
"""
from __future__ import annotations

from agro_mirai.api.errors import ApiError

MAX_AUDIO_BYTES = 10 * 1024 * 1024  # 10MB — several minutes of compressed speech audio.

_MAX_CLIP_NOTE = "10MB cap; no separate duration check (see module docstring)."


def _looks_like_audio(data: bytes) -> bool:
    if data.startswith(b"RIFF") and data[8:12] == b"WAVE":
        return True  # WAV
    if data.startswith(b"OggS"):
        return True  # OGG
    if data.startswith(b"ID3"):
        return True  # MP3 with an ID3v2 tag
    if len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        return True  # MP3 without ID3 — MPEG frame sync bits (also ADTS AAC)
    if len(data) >= 12 and data[4:8] == b"ftyp":
        # Module 39: MP4/M4A (AAC). expo-audio on Android cannot record WAV or
        # OGG at all -- MPEG-4/AAC is its native format -- so without this the
        # mobile app's "ask by voice" was rejected 400 before reaching STT.
        # services/voice transcodes it to WAV with ffmpeg before decoding.
        return True
    return False


def validate_audio_upload(file_storage) -> bytes:
    """Reads and validates an uploaded audio ``FileStorage``. Returns the
    raw bytes on success. Raises ``ApiError`` (400) on any violation."""
    if file_storage is None or file_storage.filename == "":
        raise ApiError(400, "BAD_REQUEST", "audio file is required")

    data = file_storage.read()
    if not data:
        raise ApiError(400, "BAD_REQUEST", "audio file is empty")
    if len(data) > MAX_AUDIO_BYTES:
        raise ApiError(
            400,
            "BAD_REQUEST",
            f"audio exceeds the {MAX_AUDIO_BYTES // (1024 * 1024)}MB size limit",
        )
    if not _looks_like_audio(data):
        raise ApiError(400, "BAD_REQUEST", "file is not a recognised audio format (wav/ogg/mp3)")

    return data
