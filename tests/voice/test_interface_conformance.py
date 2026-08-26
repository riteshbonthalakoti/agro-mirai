"""Unit: both VoiceService adapters conform to the interface and reject
unsupported languages without needing any model weights loaded — the
language check runs before any model I/O in both adapters, so these
tests run in any Python env with just the base package importable (no
torch/transformers/piper required).
"""
import pytest

from agro_mirai.voice import (
    AI4BharatVoiceService,
    BhashiniVoiceAdapter,
    UnsupportedLanguageError,
    VoiceService,
)

ADAPTERS = [AI4BharatVoiceService, BhashiniVoiceAdapter]


@pytest.mark.parametrize("adapter_cls", ADAPTERS)
def test_adapter_implements_voice_service_protocol(adapter_cls):
    adapter = adapter_cls()
    assert isinstance(adapter, VoiceService)


@pytest.mark.parametrize("adapter_cls", ADAPTERS)
def test_translate_rejects_unsupported_source_language(adapter_cls):
    adapter = adapter_cls()
    with pytest.raises(UnsupportedLanguageError) as exc_info:
        adapter.translate("hello", "hi", "en")
    assert exc_info.value.language_code == "hi"
    assert exc_info.value.supported == frozenset({"en", "kn"})


@pytest.mark.parametrize("adapter_cls", ADAPTERS)
def test_translate_rejects_unsupported_target_language(adapter_cls):
    adapter = adapter_cls()
    with pytest.raises(UnsupportedLanguageError) as exc_info:
        adapter.translate("hello", "en", "ta")
    assert exc_info.value.language_code == "ta"


@pytest.mark.parametrize("adapter_cls", ADAPTERS)
def test_speech_to_text_rejects_unsupported_expected_lang(adapter_cls):
    adapter = adapter_cls()
    with pytest.raises(UnsupportedLanguageError) as exc_info:
        adapter.speech_to_text(b"not-real-audio", expected_lang="te")
    assert exc_info.value.language_code == "te"


@pytest.mark.parametrize("adapter_cls", ADAPTERS)
def test_text_to_speech_rejects_unsupported_language(adapter_cls):
    adapter = adapter_cls()
    with pytest.raises(UnsupportedLanguageError) as exc_info:
        adapter.text_to_speech("hello", "gu")
    assert exc_info.value.language_code == "gu"


@pytest.mark.parametrize("adapter_cls", ADAPTERS)
@pytest.mark.parametrize("method_name", ["translate", "speech_to_text", "text_to_speech"])
def test_adapter_exposes_all_interface_methods(adapter_cls, method_name):
    assert hasattr(adapter_cls, method_name)
    assert callable(getattr(adapter_cls, method_name))
