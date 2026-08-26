"""Unit tests for DiseaseRiskModel's output shape.

Reuses tools/check_specs.py's validation logic against specs/core/schema.yaml
instead of duplicating field/type checks here, per docs/testing-strategy.md's
"Contract" layer.
"""
from __future__ import annotations

import dataclasses
import sys
from datetime import date
from pathlib import Path

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

from agro_mirai.models.disease_risk_model import DiseaseRiskModel  # noqa: E402
from agro_mirai.processing.feature_builder import FeatureVector  # noqa: E402


def _full_vector(**overrides) -> FeatureVector:
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
        soil_moisture_pct=18.0,
        ndvi_data_available=True,
        ndvi_latest=0.55,
        ndvi_trend=-0.03,
        season="kharif",
        days_since_sowing=70,
    )
    defaults.update(overrides)
    return FeatureVector(**defaults)


def _to_fixture_record(rec) -> dict:
    record = dataclasses.asdict(rec)
    for key in ("created_at", "window_start_at", "window_end_at"):
        value = record.get(key)
        if value is not None:
            record[key] = value.strftime("%Y-%m-%dT%H:%M:%SZ")
    return {k: v for k, v in record.items() if v is not None}


@pytest.fixture(scope="module")
def model() -> DiseaseRiskModel:
    return DiseaseRiskModel()


def test_predict_returns_schema_valid_disease_risk_alert(model):
    vector = _full_vector()

    rec = model.predict(vector)

    schema = _load_yaml(SCHEMA_PATH)
    enums = _parse_enum_doc(ENUMS_PATH.read_text(encoding="utf-8"))
    known_ids = {"Field": {vector.field_id}}

    record = _to_fixture_record(rec)
    problems = _validate_entity(
        "DiseaseRiskAlert", record, schema, enums, known_ids, {}, 0
    )
    assert problems == []


def test_predict_confidence_in_range(model):
    rec = model.predict(_full_vector())
    assert 0.0 <= rec.confidence <= 1.0


def test_predict_window_end_after_start(model):
    rec = model.predict(_full_vector())
    assert rec.window_end_at > rec.window_start_at


def test_predict_propagates_field_id(model):
    vector = _full_vector(field_id="zz000001-0000-4000-8000-000000000009")
    rec = model.predict(vector)
    assert rec.field_id == "zz000001-0000-4000-8000-000000000009"


def test_predict_raises_on_missing_weather_means(model):
    vector = _full_vector(humidity_pct_mean_14d=None, temp_c_mean_14d=None)
    with pytest.raises(ValueError):
        model.predict(vector)
