"""LLM tier added to DecisionEngine.recommend (AI cascade restructure):
mocked at agro_mirai.api.advisory_llm.llm_recommend_advisory -- no live
Gemini key or quota used. The rule-based compositor fallback is unchanged
and already covered by tests/models/test_decision_engine.py."""
from datetime import date, datetime, timezone
from unittest.mock import MagicMock

from agro_mirai.models.decision_engine import DecisionEngine
from agro_mirai.persistence.models import (
    Advisory,
    CropRecommendation,
    DiseaseRiskAlert,
    IrrigationAdvice,
)
from agro_mirai.processing.feature_builder import FeatureVector


def _vector(**overrides) -> FeatureVector:
    defaults = dict(
        field_id="f1", as_of=date(2026, 8, 24),
        rainfall_mm_sum_7d=10.0, temp_c_mean_7d=26.0, humidity_pct_mean_7d=70.0,
        rainfall_mm_sum_14d=20.0, temp_c_mean_14d=25.5, humidity_pct_mean_14d=68.0,
        rainfall_mm_sum_30d=120.0, temp_c_mean_30d=25.0, humidity_pct_mean_30d=65.0,
        soil_data_available=False,
    )
    defaults.update(overrides)
    return FeatureVector(**defaults)


def _llm_advisory():
    return Advisory(
        id="a1", field_id="f1", created_at=datetime.now(timezone.utc),
        language="en", title="t", body="b", severity="moderate", source="llm",
    )


def _engine():
    return DecisionEngine(
        crop_model=MagicMock(), irrigation_model=MagicMock(),
        disease_model=MagicMock(), explanation_service=MagicMock(),
    )


def _rule_based_mocks(engine):
    now = datetime.now(timezone.utc)
    engine._crop_model.predict.return_value = CropRecommendation(
        id="c1", field_id="f1", created_at=now, recommended_crop="cotton", confidence=0.8,
    )
    engine._irrigation_model.predict.return_value = IrrigationAdvice(
        id="i1", field_id="f1", created_at=now, recommended_depth_mm=10.0,
        window_start_at=now, window_end_at=now, urgency="low",
    )
    engine._disease_model.predict.return_value = DiseaseRiskAlert(
        id="d1", field_id="f1", created_at=now, disease="none", risk_level="low", confidence=0.1,
    )
    engine._explanation_service.explain_crop.return_value = MagicMock(summary_en="x")
    engine._explanation_service.explain_irrigation.return_value = MagicMock(summary_en="y")
    engine._explanation_service.explain_disease.return_value = MagicMock(summary_en="z")


def test_llm_success_short_circuits_rule_based_compositor(monkeypatch):
    monkeypatch.setattr(
        "agro_mirai.api.advisory_llm.llm_recommend_advisory", lambda *a, **k: _llm_advisory()
    )
    engine = _engine()
    result = engine.recommend(field=MagicMock(), features=_vector())
    assert result.source == "llm"
    engine._crop_model.predict.assert_not_called()  # rule-based legs never ran


def test_llm_none_falls_through_to_rule_based(monkeypatch):
    monkeypatch.setattr(
        "agro_mirai.api.advisory_llm.llm_recommend_advisory", lambda *a, **k: None
    )
    engine = _engine()
    _rule_based_mocks(engine)

    result = engine.recommend(field=MagicMock(), features=_vector())

    assert result.source == "rule_based"
    engine._crop_model.predict.assert_called_once()


def test_llm_exception_never_raises(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr("agro_mirai.api.advisory_llm.llm_recommend_advisory", boom)
    engine = _engine()
    _rule_based_mocks(engine)

    result = engine.recommend(field=MagicMock(), features=_vector())  # must not raise
    assert result.source == "rule_based"
