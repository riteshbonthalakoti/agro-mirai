"""Crop-recommendation LLM tier: mocked at
agro_mirai.api.gemini_client.ask_gemini_structured -- no live Gemini key
or quota used."""
from unittest.mock import MagicMock

from agro_mirai.api.crop_llm import llm_recommend_crop
from agro_mirai.processing.feature_builder import FeatureVector


def _features(crop_type=None):
    return FeatureVector(
        field_id="f1", as_of=None,
        rainfall_mm_sum_7d=0, temp_c_mean_7d=25, humidity_pct_mean_7d=60,
        rainfall_mm_sum_14d=0, temp_c_mean_14d=25, humidity_pct_mean_14d=60,
        rainfall_mm_sum_30d=0, temp_c_mean_30d=25, humidity_pct_mean_30d=60,
        soil_data_available=False, crop_type=crop_type,
    )


def test_valid_response_returns_recommendation(monkeypatch):
    monkeypatch.setattr(
        "agro_mirai.api.gemini_client.ask_gemini_structured",
        lambda *a, **k: {"recommended_crop": "Cotton", "confidence": 0.75,
                          "alternatives": ["Maize", "not_a_real_crop"], "rationale": "fits the soil"},
    )
    result = llm_recommend_crop(_features())
    assert result is not None
    assert result.recommended_crop == "cotton"
    assert result.confidence == 0.75
    assert result.alternatives == ["maize"]  # unknown crop filtered out
    assert result.source == "llm"


def test_unknown_crop_rejected(monkeypatch):
    monkeypatch.setattr(
        "agro_mirai.api.gemini_client.ask_gemini_structured",
        lambda *a, **k: {"recommended_crop": "dragonfruit", "confidence": 0.9},
    )
    assert llm_recommend_crop(_features()) is None


def test_none_reply_returns_none(monkeypatch):
    monkeypatch.setattr(
        "agro_mirai.api.gemini_client.ask_gemini_structured", lambda *a, **k: None
    )
    assert llm_recommend_crop(_features()) is None


def test_missing_field_returns_none(monkeypatch):
    monkeypatch.setattr(
        "agro_mirai.api.gemini_client.ask_gemini_structured",
        lambda *a, **k: {"confidence": 0.5},  # no recommended_crop
    )
    assert llm_recommend_crop(_features()) is None


def test_exception_never_raises(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr("agro_mirai.api.gemini_client.ask_gemini_structured", boom)
    assert llm_recommend_crop(_features()) is None
