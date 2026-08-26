"""Unit tests for IrrigationPredictionModel's output shape.

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

from agro_mirai.models.irrigation_prediction_model import (  # noqa: E402
    DEFAULT_MODEL_PATH,
    IrrigationPredictionModel,
)
from agro_mirai.processing.feature_builder import FeatureVector  # noqa: E402

pytestmark = pytest.mark.skipif(
    not DEFAULT_MODEL_PATH.exists(),
    reason="models/irrigation_rf.joblib not present — run tools/train_irrigation_model.py first",
)


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
        soil_nitrogen_mg_per_kg=45.0,
        soil_phosphorus_mg_per_kg=28.0,
        soil_potassium_mg_per_kg=180.0,
        soil_organic_carbon_pct=0.6,
        soil_moisture_pct=18.0,
        soil_npk_balance_index=0.177,
        ndvi_data_available=False,
        season="kharif",
        days_since_sowing=70,
    )
    defaults.update(overrides)
    return FeatureVector(**defaults)


def _to_fixture_record(rec) -> dict:
    """Serializes an IrrigationAdvice like a JSON fixture record would:
    ISO 8601 timestamps as strings, optional fields omitted (not null).
    """
    record = dataclasses.asdict(rec)
    for key in ("created_at", "window_start_at", "window_end_at"):
        record[key] = getattr(rec, key).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {k: v for k, v in record.items() if v is not None}


@pytest.fixture(scope="module")
def model() -> IrrigationPredictionModel:
    return IrrigationPredictionModel()


def test_predict_returns_schema_valid_irrigation_advice(model):
    vector = _full_vector()

    rec = model.predict(vector)

    schema = _load_yaml(SCHEMA_PATH)
    enums = _parse_enum_doc(ENUMS_PATH.read_text(encoding="utf-8"))
    known_ids = {"Field": {vector.field_id}}

    record = _to_fixture_record(rec)
    problems = _validate_entity(
        "IrrigationAdvice", record, schema, enums, known_ids, {}, 0
    )
    assert problems == []


def test_predict_depth_is_positive(model):
    rec = model.predict(_full_vector())
    assert rec.recommended_depth_mm > 0.0


def test_predict_urgency_is_never_severe(model):
    # ADR 0008: the 3-class dataset has no `severe` counterpart, so this
    # model version can never produce it.
    rec = model.predict(_full_vector())
    assert rec.urgency != "severe"


def test_predict_window_end_after_start(model):
    rec = model.predict(_full_vector())
    assert rec.window_end_at > rec.window_start_at


def test_predict_propagates_field_id(model):
    vector = _full_vector(field_id="zz000001-0000-4000-8000-000000000009")
    rec = model.predict(vector)
    assert rec.field_id == "zz000001-0000-4000-8000-000000000009"


def test_predict_raises_on_missing_soil(model):
    vector = _full_vector(soil_data_available=False, soil_ph=None, soil_moisture_pct=None)
    with pytest.raises(ValueError):
        model.predict(vector)
