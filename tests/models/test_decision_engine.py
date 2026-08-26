"""Unit tests for DecisionEngine — plumbing only, all four dependencies
mocked (CropRecommendationModel, IrrigationPredictionModel,
DiseaseRiskModel, ExplanationService). Confirms the assembled Advisory
is schema-valid and that the severity-as-alert-flag logic
(decisions/0011-decision-engine.md) fires for known inputs.
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from check_specs import (  # noqa: E402
    ENUMS_PATH,
    SCHEMA_PATH,
    _load_yaml,
    _parse_enum_doc,
    _validate_entity,
)

from agro_mirai.models.decision_engine import DecisionEngine  # noqa: E402
from agro_mirai.models.explanation import Explanation  # noqa: E402
from agro_mirai.persistence.models import (  # noqa: E402
    CropRecommendation,
    DiseaseRiskAlert,
    IrrigationAdvice,
)
from agro_mirai.processing.feature_builder import FeatureVector  # noqa: E402


def _vector(**overrides) -> FeatureVector:
    defaults = dict(
        field_id="7d00c345-dffa-4c63-8401-7b8faab62664",
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


def _explanation(subject_type: str, subject_id: str, summary: str) -> Explanation:
    return Explanation(
        id="4b1d1283-ea85-4630-b6dd-754d99e9ae59",
        field_id="7d00c345-dffa-4c63-8401-7b8faab62664",
        created_at=datetime.now(timezone.utc),
        subject_type=subject_type,
        subject_id=subject_id,
        method="shap_tree",
        top_contributions=[],
        summary_en=summary,
    )


def _build_engine(urgency: str, risk_level: str):
    crop_model = MagicMock()
    crop_model.predict.return_value = CropRecommendation(
        id="f0c81727-96bb-46f4-8fd3-f8cb485c81c8",
        field_id="7d00c345-dffa-4c63-8401-7b8faab62664",
        created_at=datetime.now(timezone.utc),
        recommended_crop="rice",
        confidence=0.9,
        alternatives=["maize"],
        season="kharif",
    )

    irrigation_model = MagicMock()
    irrigation_model.predict.return_value = IrrigationAdvice(
        id="33ec0c81-d98c-45ce-8cba-875c65efef4a",
        field_id="7d00c345-dffa-4c63-8401-7b8faab62664",
        created_at=datetime.now(timezone.utc),
        recommended_depth_mm=25.0,
        window_start_at=datetime.now(timezone.utc),
        window_end_at=datetime.now(timezone.utc),
        urgency=urgency,
    )

    disease_model = MagicMock()
    disease_model.predict.return_value = DiseaseRiskAlert(
        id="f5fd0804-f207-40be-80db-b03596898e3b",
        field_id="7d00c345-dffa-4c63-8401-7b8faab62664",
        created_at=datetime.now(timezone.utc),
        disease="fungal leaf spot",
        risk_level=risk_level,
        confidence=0.8,
    )

    explanation_service = MagicMock()
    explanation_service.explain_crop.return_value = _explanation(
        "crop_recommendation", "f0c81727-96bb-46f4-8fd3-f8cb485c81c8", "Rice looks best."
    )
    explanation_service.explain_irrigation.return_value = _explanation(
        "irrigation_advice", "33ec0c81-d98c-45ce-8cba-875c65efef4a", "Irrigation summary."
    )
    explanation_service.explain_disease.return_value = _explanation(
        "disease_risk_alert", "f5fd0804-f207-40be-80db-b03596898e3b", "Disease summary."
    )

    engine = DecisionEngine(
        crop_model=crop_model,
        irrigation_model=irrigation_model,
        disease_model=disease_model,
        explanation_service=explanation_service,
    )
    return engine


def test_recommend_produces_schema_valid_advisory():
    engine = _build_engine(urgency="low", risk_level="low")
    advisory = engine.recommend(field=None, features=_vector())

    schema = _load_yaml(SCHEMA_PATH)
    enums = _parse_enum_doc(ENUMS_PATH.read_text(encoding="utf-8"))
    known_ids = {"Field": {advisory.field_id}}

    import dataclasses

    record = dataclasses.asdict(advisory)
    record["created_at"] = advisory.created_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    problems = _validate_entity("Advisory", record, schema, enums, known_ids, {}, 0)
    assert problems == []

    assert advisory.title == "Advisory for rice"
    assert "Rice looks best." in advisory.body
    assert "Irrigation summary." in advisory.body
    assert "Disease summary." in advisory.body
    assert advisory.source_refs == [
        "f0c81727-96bb-46f4-8fd3-f8cb485c81c8",
        "33ec0c81-d98c-45ce-8cba-875c65efef4a",
        "f5fd0804-f207-40be-80db-b03596898e3b",
    ]


@pytest.mark.parametrize(
    "urgency,risk_level,expected_severity",
    [
        ("low", "low", "low"),
        ("moderate", "low", "moderate"),
        ("low", "moderate", "moderate"),
        ("high", "low", "high"),
        ("low", "severe", "severe"),
        ("severe", "high", "severe"),
    ],
)
def test_severity_is_max_of_irrigation_and_disease(urgency, risk_level, expected_severity):
    engine = _build_engine(urgency=urgency, risk_level=risk_level)
    advisory = engine.recommend(field=None, features=_vector())
    assert advisory.severity == expected_severity


@pytest.mark.parametrize(
    "urgency,risk_level,expect_alert",
    [
        ("low", "low", False),
        ("moderate", "moderate", False),
        ("high", "low", True),
        ("low", "severe", True),
        ("severe", "severe", True),
    ],
)
def test_severity_alert_threshold(urgency, risk_level, expect_alert):
    from agro_mirai.models.decision_engine import ALERT_LEVELS

    engine = _build_engine(urgency=urgency, risk_level=risk_level)
    advisory = engine.recommend(field=None, features=_vector())
    assert (advisory.severity in ALERT_LEVELS) == expect_alert
