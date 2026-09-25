"""Unit tests for ExplanationService — plumbing only.

Crop and irrigation advice are rule-based and carry their own rationale, which is
what gets reported; the disease path is an exact weight x signal decomposition
(decisions/0010, 0029). No trained model is involved anywhere.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from unittest.mock import MagicMock

from agro_mirai.models.explanation import Explanation
from agro_mirai.models.explanation_service import ExplanationService
from agro_mirai.persistence.models import (
    CropRecommendation,
    DiseaseRiskAlert,
    IrrigationAdvice,
)
from agro_mirai.processing.feature_builder import FeatureVector


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


def _rec(**kw):
    base = dict(
        id=str(uuid.uuid4()), field_id="ff000001-0000-4000-8000-000000000001",
        created_at=datetime.now(timezone.utc), recommended_crop="rice", confidence=0.9,
        alternatives=["maize"], season="kharif",
    )
    base.update(kw)
    return CropRecommendation(**base)


def test_explain_crop_reports_the_rationale_the_model_wrote():
    rec = _rec(rationale="Rice is a good fit: the temperature (26C) is in its ideal range.")
    explanation = ExplanationService().explain_crop(rec, _vector())

    assert isinstance(explanation, Explanation)
    assert explanation.method == "rule_weight"
    assert explanation.subject_type == "crop_recommendation"
    assert explanation.subject_id == rec.id
    assert explanation.summary_en == rec.rationale
    assert explanation.top_contributions == []
    assert explanation.summary_kn is None


def test_explain_crop_without_a_rationale_says_no_breakdown_and_never_raises():
    explanation = ExplanationService().explain_crop(_rec(rationale=None), features=None)
    assert explanation.method == "unavailable"
    assert "No detailed breakdown" in explanation.summary_en


def test_explain_irrigation_reports_the_water_balance_rationale():
    advice = IrrigationAdvice(
        id=str(uuid.uuid4()), field_id="ff000001-0000-4000-8000-000000000001",
        created_at=datetime.now(timezone.utc), recommended_depth_mm=25.0,
        window_start_at=datetime.now(timezone.utc), window_end_at=datetime.now(timezone.utc),
        urgency="moderate", rationale="About 60% of the soil water is gone. Water within 2 day(s).",
    )
    explanation = ExplanationService().explain_irrigation(advice, _vector())
    assert explanation.method == "rule_weight"
    assert explanation.subject_type == "irrigation_advice"
    assert explanation.summary_en == advice.rationale


def test_regional_caveat_text_variants():
    from agro_mirai.models.explanation_service import _regional_fit_note

    assert _regional_fit_note(_rec(out_of_region=False)) == ""
    with_alt = _regional_fit_note(_rec(out_of_region=True, regional_alternative="chickpea"))
    assert "caveat" in with_alt.lower() and "chickpea" in with_alt
    none_alt = _regional_fit_note(_rec(out_of_region=True, regional_alternative=None))
    assert "caveat" in none_alt.lower() and "none" in none_alt.lower()


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
