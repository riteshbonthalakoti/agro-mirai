"""Unit tests for ExplanationService — plumbing only.

Modules 06/07 explanations mock shap.TreeExplainer entirely so these
tests don't require the trained artifacts; the disease path needs no
mocking since it has no model to mock. See
decisions/0010-explainability.md for why the disease path is exact
weight x signal decomposition, not SHAP.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from agro_mirai.models.explanation import Explanation
from agro_mirai.models.explanation_service import ExplanationService
from agro_mirai.persistence.models import (
    CropRecommendation,
    DiseaseRiskAlert,
    IrrigationAdvice,
)
from agro_mirai.processing.feature_builder import FeatureVector

try:
    import shap  # noqa: F401

    _SHAP_AVAILABLE = True
except ImportError:
    _SHAP_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _SHAP_AVAILABLE,
    reason="shap not installed — pip install shap to run these tests",
)


def _vector(**overrides) -> FeatureVector:
    defaults = dict(
        field_id="ff000001-0000-4000-8000-000000000001",
        as_of=date(2026, 8, 24),
        rainfall_mm_sum_7d=10.0,
        temp_c_mean_7d=26.0,
        humidity_pct_mean_7d=70.0,
        rainfall_mm_sum_14d=20.0,
        temp_c_mean_14d=25.5,
        humidity_pct_mean_14d=68.0,
        rainfall_mm_sum_30d=120.0,
        temp_c_mean_30d=25.0,
        humidity_pct_mean_30d=65.0,
        soil_data_available=True,
        soil_ph=6.8,
        soil_nitrogen_mg_per_kg=80.0,
        soil_phosphorus_mg_per_kg=40.0,
        soil_potassium_mg_per_kg=45.0,
        soil_moisture_pct=18.0,
        ndvi_data_available=True,
        ndvi_latest=0.55,
        ndvi_trend=-0.03,
        season="kharif",
        days_since_sowing=70,
    )
    defaults.update(overrides)
    return FeatureVector(**defaults)


class _FakeSklearnModel:
    """Minimal stand-in with just the attributes ExplanationService touches."""

    def __init__(self, classes):
        self.classes_ = np.array(classes)

    def predict(self, x):
        return np.array([self.classes_[0]])


def _fake_tree_explainer(n_features: int, n_classes: int, as_list: bool):
    explainer = MagicMock()
    if as_list:
        explainer.shap_values.return_value = [
            np.full((1, n_features), 0.0) + i * 0.1 for i in range(n_classes)
        ]
    else:
        arr = np.zeros((1, n_features, n_classes))
        for c in range(n_classes):
            arr[0, :, c] = c * 0.1
        explainer.shap_values.return_value = arr
    return explainer


@pytest.mark.parametrize("as_list", [True, False])
def test_explain_crop_shape(as_list):
    classes = ["rice", "maize", "cotton"]
    model_wrapper = MagicMock()
    model_wrapper._model = _FakeSklearnModel(classes)

    service = ExplanationService(crop_model=model_wrapper)
    recommendation = CropRecommendation(
        id=str(uuid.uuid4()),
        field_id="ff000001-0000-4000-8000-000000000001",
        created_at=datetime.now(timezone.utc),
        recommended_crop="rice",
        confidence=0.9,
        alternatives=["maize"],
        season="kharif",
    )

    with patch("shap.TreeExplainer") as mock_cls:
        mock_cls.return_value = _fake_tree_explainer(7, 3, as_list)
        explanation = service.explain_crop(recommendation, _vector())

    assert isinstance(explanation, Explanation)
    assert explanation.method == "shap_tree"
    assert explanation.subject_type == "crop_recommendation"
    assert explanation.subject_id == recommendation.id
    assert 1 <= len(explanation.top_contributions) <= 3
    assert all(c.direction in ("increases", "decreases") for c in explanation.top_contributions)
    assert explanation.summary_kn is None


def test_explain_crop_no_caveat_when_in_region():
    classes = ["rice", "maize", "cotton"]
    model_wrapper = MagicMock()
    model_wrapper._model = _FakeSklearnModel(classes)

    service = ExplanationService(crop_model=model_wrapper)
    recommendation = CropRecommendation(
        id=str(uuid.uuid4()),
        field_id="ff000001-0000-4000-8000-000000000001",
        created_at=datetime.now(timezone.utc),
        recommended_crop="rice",
        confidence=0.9,
        alternatives=["maize"],
        season="kharif",
        out_of_region=False,
        regional_alternative=None,
    )

    with patch("shap.TreeExplainer") as mock_cls:
        mock_cls.return_value = _fake_tree_explainer(7, 3, as_list=True)
        explanation = service.explain_crop(recommendation, _vector())

    assert "caveat" not in explanation.summary_en.lower()


def test_explain_crop_caveat_with_regional_alternative():
    classes = ["rice", "maize", "grapes"]
    model_wrapper = MagicMock()
    model_wrapper._model = _FakeSklearnModel(classes)

    service = ExplanationService(crop_model=model_wrapper)
    recommendation = CropRecommendation(
        id=str(uuid.uuid4()),
        field_id="ff000001-0000-4000-8000-000000000001",
        created_at=datetime.now(timezone.utc),
        recommended_crop="grapes",
        confidence=0.7,
        alternatives=["rice", "maize"],
        season="kharif",
        out_of_region=True,
        regional_alternative="rice",
    )

    with patch("shap.TreeExplainer") as mock_cls:
        mock_cls.return_value = _fake_tree_explainer(7, 3, as_list=True)
        explanation = service.explain_crop(recommendation, _vector())

    summary = explanation.summary_en.lower()
    assert "caveat" in summary
    assert "grapes" in summary
    assert "rice" in summary


def test_explain_crop_caveat_with_no_regional_alternative():
    classes = ["papaya", "banana", "grapes"]
    model_wrapper = MagicMock()
    model_wrapper._model = _FakeSklearnModel(classes)

    service = ExplanationService(crop_model=model_wrapper)
    recommendation = CropRecommendation(
        id=str(uuid.uuid4()),
        field_id="ff000001-0000-4000-8000-000000000001",
        created_at=datetime.now(timezone.utc),
        recommended_crop="grapes",
        confidence=0.6,
        alternatives=["papaya", "banana"],
        season="kharif",
        out_of_region=True,
        regional_alternative=None,
    )

    with patch("shap.TreeExplainer") as mock_cls:
        mock_cls.return_value = _fake_tree_explainer(7, 3, as_list=True)
        explanation = service.explain_crop(recommendation, _vector())

    summary = explanation.summary_en.lower()
    assert "caveat" in summary
    assert "none" in summary


def test_explain_irrigation_shape():
    model_wrapper = MagicMock()
    model_wrapper._model = _FakeSklearnModel(["Low", "Medium", "High"])

    service = ExplanationService(irrigation_model=model_wrapper)
    advice = IrrigationAdvice(
        id=str(uuid.uuid4()),
        field_id="ff000001-0000-4000-8000-000000000001",
        created_at=datetime.now(timezone.utc),
        recommended_depth_mm=25.0,
        window_start_at=datetime.now(timezone.utc),
        window_end_at=datetime.now(timezone.utc),
        urgency="moderate",
        rationale="test",
    )

    with patch("shap.TreeExplainer") as mock_cls:
        mock_cls.return_value = _fake_tree_explainer(8, 3, as_list=True)
        explanation = service.explain_irrigation(advice, _vector())

    assert explanation.method == "shap_tree"
    assert explanation.subject_type == "irrigation_advice"
    assert len(explanation.top_contributions) == 3


def test_explain_disease_labels_contributing_factor_not_shap():
    service = ExplanationService()
    alert = DiseaseRiskAlert(
        id=str(uuid.uuid4()),
        field_id="ff000001-0000-4000-8000-000000000001",
        created_at=datetime.now(timezone.utc),
        disease="Generic fungal disease risk",
        risk_level="high",
        confidence=0.9,
        window_start_at=datetime.now(timezone.utc),
        window_end_at=datetime.now(timezone.utc),
        recommended_action="scout",
    )

    explanation = service.explain_disease(alert, _vector())

    assert explanation.method == "rule_weight"
    assert "shap" not in explanation.summary_en.lower()
    assert "contributing factor" in explanation.summary_en.lower()
    assert len(explanation.top_contributions) == 3


def test_summary_kn_populated_when_voice_service_injected():
    voice = MagicMock()
    voice.translate.return_value = "ಕನ್ನಡ ಸಾರಾಂಶ"
    service = ExplanationService(voice_service=voice)
    alert = DiseaseRiskAlert(
        id=str(uuid.uuid4()),
        field_id="ff000001-0000-4000-8000-000000000001",
        created_at=datetime.now(timezone.utc),
        disease="Generic fungal disease risk",
        risk_level="low",
        confidence=0.5,
        window_start_at=datetime.now(timezone.utc),
        window_end_at=datetime.now(timezone.utc),
        recommended_action="monitor",
    )

    explanation = service.explain_disease(alert, _vector())

    voice.translate.assert_called_once_with(explanation.summary_en, "en", "kn")
    assert explanation.summary_kn == "ಕನ್ನಡ ಸಾರಾಂಶ"
    # Module 25, additive: default target_lang="kn" means the new field
    # mirrors summary_kn exactly, no extra translate() call.
    assert explanation.summary_translated == "ಕನ್ನಡ ಸಾರಾಂಶ"
    assert explanation.summary_translated_lang == "kn"


def test_summary_translated_uses_target_lang_when_given():
    voice = MagicMock()
    voice.translate.side_effect = lambda text, src, tgt: f"[{tgt}] {text}"
    service = ExplanationService(voice_service=voice)
    alert = DiseaseRiskAlert(
        id=str(uuid.uuid4()),
        field_id="ff000001-0000-4000-8000-000000000001",
        created_at=datetime.now(timezone.utc),
        disease="Generic fungal disease risk",
        risk_level="low",
        confidence=0.5,
        window_start_at=datetime.now(timezone.utc),
        window_end_at=datetime.now(timezone.utc),
        recommended_action="monitor",
    )

    explanation = service.explain_disease(alert, _vector(), target_lang="te")

    # summary_kn is frozen at en->kn regardless of target_lang.
    assert explanation.summary_kn == f"[kn] {explanation.summary_en}"
    assert explanation.summary_translated == f"[te] {explanation.summary_en}"
    assert explanation.summary_translated_lang == "te"
    assert voice.translate.call_count == 2


def test_summary_translated_none_when_no_voice_service():
    service = ExplanationService()
    alert = DiseaseRiskAlert(
        id=str(uuid.uuid4()),
        field_id="ff000001-0000-4000-8000-000000000001",
        created_at=datetime.now(timezone.utc),
        disease="Generic fungal disease risk",
        risk_level="low",
        confidence=0.5,
        window_start_at=datetime.now(timezone.utc),
        window_end_at=datetime.now(timezone.utc),
        recommended_action="monitor",
    )

    explanation = service.explain_disease(alert, _vector(), target_lang="hi")

    assert explanation.summary_translated is None
    assert explanation.summary_translated_lang is None


def test_explain_crop_degrades_when_model_artifact_missing_and_no_tabular_service(monkeypatch):
    """Main API process on Render has no model files; with the tabular service
    unreachable, explanations must degrade to method='unavailable', never raise."""
    from datetime import datetime, timezone

    from agro_mirai.models.explanation_service import ExplanationService
    from agro_mirai.persistence.models import CropRecommendation

    monkeypatch.delenv("TABULAR_SERVICE_URL", raising=False)

    class _NoModel:
        @property
        def _model(self):
            raise FileNotFoundError("crop_rf.joblib not found")

    rec = CropRecommendation(
        id="r1", field_id="f1", created_at=datetime.now(timezone.utc),
        recommended_crop="rice", confidence=0.9, alternatives=["maize"], rationale="x", season="kharif",
    )
    exp = ExplanationService(crop_model=_NoModel()).explain_crop(rec, features=None)  # features unused on this path
    assert exp.method == "unavailable"
    assert exp.top_contributions == []
    assert "unavailable" in exp.summary_en
