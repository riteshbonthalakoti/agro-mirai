"""Integration: real round trips through AI4BharatVoiceService — no
mocking of translate/ASR/TTS. Proves the actual models work end to end,
not just that the interface compiles.

Skipped automatically when the voice-stack dependencies (torch,
transformers, piper, soundfile, indic-nlp-library, sacremoses,
sentencepiece) or the downloaded model weights under models/voice/
aren't present in the current interpreter — same "auto-skip, never fail
for absence" pattern as tests/models/test_crop_model_integration.py.

Run with the project venv, which has the full stack installed:

    .venv/Scripts/python.exe -m pytest tests/voice/test_ai4bharat_integration.py -v

A single module-scoped AI4BharatVoiceService is shared across tests so
the ~2 minute cold-load of the IndicConformer ASR model only happens
once per test run.
"""
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_DIR = REPO_ROOT / "models" / "voice"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

try:
    import torch  # noqa: F401
    import transformers
    import piper  # noqa: F401
    import soundfile  # noqa: F401
    import sacremoses  # noqa: F401
    import indicnlp  # noqa: F401

    # AI4Bharat's trust_remote_code models (IndicTrans2, vits_rasa_13)
    # were written against transformers 4.x internals removed or changed
    # in 5.x (transformers.onnx deleted, PreTrainedTokenizerBase special-
    # token bookkeeping stricter, PreTrainedModel.tie_weights() signature
    # changed) — see docs/architecture.md "AI4Bharat model / transformers
    # version pin" for the full list of breakages hit during development.
    # .venv/ pins transformers==4.49.0; a transformers 5.x install (e.g.
    # this project's own non-venv global interpreter) will import fine
    # but fail deep inside these tests, so gate on major version too
    # rather than just importability.
    _TRANSFORMERS_COMPATIBLE = transformers.__version__.startswith("4.")
    _DEPS_AVAILABLE = _TRANSFORMERS_COMPATIBLE
except ImportError:
    _DEPS_AVAILABLE = False

_MODELS_PRESENT = (
    (MODEL_DIR / "indictrans2-en-indic-dist-200M" / "config.json").exists()
    and (MODEL_DIR / "indictrans2-indic-en-dist-200M" / "config.json").exists()
    and (MODEL_DIR / "piper" / "en" / "en_US" / "lessac" / "medium" / "en_US-lessac-medium.onnx").exists()
)

#: Module 25: Telugu TTS reuses the same vits_rasa_13 weights the kn
#: tests already require (just a different speaker id), so no extra
#: model-presence gate is needed for `te` beyond `_MODELS_PRESENT`.
#: Hindi TTS is a genuinely new Piper voice download
#: (rhasspy/piper-voices' hi_IN-rohan-medium) — gated separately so the
#: en/kn/te tests still run on a machine that hasn't fetched it yet, same
#: "auto-skip, never fail for absence" pattern as the rest of this file.
_HINDI_PIPER_VOICE_PRESENT = (
    MODEL_DIR / "piper" / "hi" / "hi_IN" / "rohan" / "medium" / "hi_IN-rohan-medium.onnx"
).exists()

pytestmark = pytest.mark.skipif(
    not (_DEPS_AVAILABLE and _MODELS_PRESENT),
    reason=(
        "voice-stack deps not present/compatible (needs transformers 4.x, "
        "not 5.x — see docs/architecture.md) and/or models/voice/ weights "
        "not downloaded — run with .venv/Scripts/python.exe per "
        "docs/TOOLING.md"
    ),
)

_requires_hindi_voice = pytest.mark.skipif(
    not _HINDI_PIPER_VOICE_PRESENT,
    reason="Hindi Piper voice (hi_IN-rohan-medium) not downloaded under models/voice/piper/hi/",
)


@pytest.fixture(scope="module")
def voice_service():
    from agro_mirai.voice import AI4BharatVoiceService

    return AI4BharatVoiceService(model_dir=MODEL_DIR)


def test_translate_round_trip_en_kn_en(voice_service):
    original = "Apply irrigation to your field today because soil moisture is low."

    kannada = voice_service.translate(original, "en", "kn")
    assert kannada != original
    assert any("ಀ" <= c <= "೿" for c in kannada)  # Kannada Unicode block

    back_to_english = voice_service.translate(kannada, "kn", "en")
    assert "irrigation" in back_to_english.lower()
    assert "soil" in back_to_english.lower() or "moisture" in back_to_english.lower()


def test_tts_then_stt_round_trip_en(voice_service):
    text = "Apply irrigation now."
    audio = voice_service.text_to_speech(text, "en")
    assert len(audio) > 1000  # not empty/near-empty

    transcript, detected_lang = voice_service.speech_to_text(audio, expected_lang="en")
    assert detected_lang == "en"
    assert "irrigation" in transcript.lower()


def test_tts_then_stt_round_trip_kn(voice_service):
    text = "ಈಗ ನೀರಾವರಿ ಮಾಡಿ."  # "Apply irrigation now."
    audio = voice_service.text_to_speech(text, "kn")
    assert len(audio) > 1000

    transcript, detected_lang = voice_service.speech_to_text(audio, expected_lang="kn")
    assert detected_lang == "kn"
    assert len(transcript.strip()) > 0
    assert any("ಀ" <= c <= "೿" for c in transcript)


def test_stt_on_checked_in_en_fixture(voice_service):
    audio = (FIXTURES_DIR / "en_sample.wav").read_bytes()
    transcript, detected_lang = voice_service.speech_to_text(audio, expected_lang="en")
    assert detected_lang == "en"
    assert "irrigation" in transcript.lower()


def test_stt_on_checked_in_kn_fixture(voice_service):
    audio = (FIXTURES_DIR / "kn_sample.wav").read_bytes()
    transcript, detected_lang = voice_service.speech_to_text(audio, expected_lang="kn")
    assert detected_lang == "kn"
    assert any("ಀ" <= c <= "೿" for c in transcript)


def test_language_identification_without_expected_lang(voice_service):
    en_audio = voice_service.text_to_speech("Apply irrigation now.", "en")
    _, detected = voice_service.speech_to_text(en_audio, expected_lang=None)
    assert detected == "en"


# -- Module 25: te/hi, same shape as the en/kn tests above ------------


def test_translate_round_trip_en_te_en(voice_service):
    original = "Apply irrigation to your field today because soil moisture is low."

    telugu = voice_service.translate(original, "en", "te")
    assert telugu != original
    assert any("ఀ" <= c <= "౿" for c in telugu)  # Telugu Unicode block

    back_to_english = voice_service.translate(telugu, "te", "en")
    assert "irrigation" in back_to_english.lower()
    assert "soil" in back_to_english.lower() or "moisture" in back_to_english.lower()


def test_translate_round_trip_en_hi_en(voice_service):
    original = "Apply irrigation to your field today because soil moisture is low."

    hindi = voice_service.translate(original, "en", "hi")
    assert hindi != original
    assert any("ऀ" <= c <= "ॿ" for c in hindi)  # Devanagari Unicode block

    back_to_english = voice_service.translate(hindi, "hi", "en")
    assert "irrigation" in back_to_english.lower()
    assert "soil" in back_to_english.lower() or "moisture" in back_to_english.lower()


def test_tts_then_stt_round_trip_te(voice_service):
    text = "ఇప్పుడు నీటిపారుదల చేయండి."  # "Apply irrigation now."
    audio = voice_service.text_to_speech(text, "te")
    assert len(audio) > 1000

    transcript, detected_lang = voice_service.speech_to_text(audio, expected_lang="te")
    assert detected_lang == "te"
    assert len(transcript.strip()) > 0
    assert any("ఀ" <= c <= "౿" for c in transcript)


@_requires_hindi_voice
def test_tts_then_stt_round_trip_hi(voice_service):
    text = "अभी सिंचाई करें।"  # "Apply irrigation now."
    audio = voice_service.text_to_speech(text, "hi")
    assert len(audio) > 1000

    transcript, detected_lang = voice_service.speech_to_text(audio, expected_lang="hi")
    assert detected_lang == "hi"
    assert len(transcript.strip()) > 0
    assert any("ऀ" <= c <= "ॿ" for c in transcript)


def test_language_identification_te_vs_en(voice_service):
    te_audio = voice_service.text_to_speech("ఇప్పుడు నీటిపారుదల చేయండి.", "te")
    _, detected = voice_service.speech_to_text(te_audio, expected_lang=None)
    assert detected == "te"


@_requires_hindi_voice
def test_language_identification_hi_vs_en(voice_service):
    hi_audio = voice_service.text_to_speech("अभी सिंचाई करें।", "hi")
    _, detected = voice_service.speech_to_text(hi_audio, expected_lang=None)
    assert detected == "hi"
