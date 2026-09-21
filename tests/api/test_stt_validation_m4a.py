"""Module 39: expo-audio on Android records MPEG-4/AAC (M4A), so the STT
upload validator must recognise the ``ftyp`` box."""
from agro_mirai.api.stt_validation import _looks_like_audio


def test_m4a_ftyp_accepted():
    assert _looks_like_audio(b"\x00\x00\x00\x20ftypM4A \x00\x00\x00\x00" + b"\x00" * 16)


def test_random_bytes_still_rejected():
    assert not _looks_like_audio(b"not audio at all, just text")
