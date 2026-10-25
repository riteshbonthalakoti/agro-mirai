"""LLM tier added to CropRecommendationModel.predict (AI cascade
restructure): mocked at agro_mirai.api.crop_llm.llm_recommend_crop -- no
live Gemini key or quota used. The rule-based fallback is unchanged and
already covered by tests/models/test_crop_recommendation_model.py."""
from datetime import date, datetime, timezone
from unittest.mock import MagicMock

from agro_mirai.models.crop_recommendation_model import CropRecommendationModel
from agro_mirai.persistence.models import CropRecommendation
from agro_mirai.processing.feature_builder import FeatureVector


def _features(**overrides):
    defaults = dict(
        field_id="f1", as_of=date(2026, 8, 24),
        rainfall_mm_sum_7d=10.0, temp_c_mean_7d=26.0, humidity_pct_mean_7d=70.0,
        rainfall_mm_sum_14d=20.0, temp_c_mean_14d=26.0, humidity_pct_mean_14d=70.0,
        rainfall_mm_sum_30d=40.0, temp_c_mean_30d=26.0, humidity_pct_mean_30d=70.0,
        soil_data_available=True, soil_ph=6.5, soil_type="loam",
        latitude=15.1, longitude=76.9,
    )
    defaults.update(overrides)
    return FeatureVector(**defaults)


def _llm_crop_recommendation():
    return CropRecommendation(
        id="llm1", field_id="f1", created_at=datetime.now(timezone.utc),
        recommended_crop="cotton", confidence=0.8, source="llm",
    )


def test_llm_success_short_circuits_rule_engine(monkeypatch):
    monkeypatch.setattr(
        "agro_mirai.api.crop_llm.llm_recommend_crop", lambda *a, **k: _llm_crop_recommendation()
    )
    result = CropRecommendationModel().predict(_features())
    assert result.source == "llm"
    assert result.recommended_crop == "cotton"


def test_llm_none_falls_through_to_rule_engine(monkeypatch):
    monkeypatch.setattr(
        "agro_mirai.api.crop_llm.llm_recommend_crop", lambda *a, **k: None
    )
    result = CropRecommendationModel().predict(_features())
    assert result.source == "ecocrop_rules"


def test_llm_exception_never_raises(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr("agro_mirai.api.crop_llm.llm_recommend_crop", boom)
    result = CropRecommendationModel().predict(_features())  # must not raise
    assert result.source == "ecocrop_rules"


def test_keep_current_skips_llm_tier_entirely(monkeypatch):
    called = []
    monkeypatch.setattr(
        "agro_mirai.api.crop_llm.llm_recommend_crop",
        lambda *a, **k: called.append(1),
    )
    CropRecommendationModel().predict(_features(crop_type="cotton"), keep_current=True)
    assert called == []
