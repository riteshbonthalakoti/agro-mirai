"""Unit tests for CropRecommendationModel's output shape.

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

from agro_mirai.models.crop_recommendation_model import (  # noqa: E402
    DEFAULT_MODEL_PATH,
    CropRecommendationModel,
)
from agro_mirai.processing.feature_builder import FeatureVector  # noqa: E402

pytestmark = pytest.mark.skipif(
    not DEFAULT_MODEL_PATH.exists(),
    reason="models/crop_rf.joblib not present — run tools/train_crop_model.py first",
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
    """Serializes a CropRecommendation like a JSON fixture record would:
    ISO 8601 timestamps as strings, optional fields omitted (not null) —
    matching how _validate_entity expects optional fields to be absent
    rather than explicitly None (schema.yaml's own JSON fixtures never
    write `"rationale": null`).
    """
    record = dataclasses.asdict(rec)
    record["created_at"] = rec.created_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    return {k: v for k, v in record.items() if v is not None}


@pytest.fixture(scope="module")
def model() -> CropRecommendationModel:
    return CropRecommendationModel()


def test_predict_returns_schema_valid_crop_recommendation(model):
    vector = _full_vector()

    rec = model.predict(vector)

    schema = _load_yaml(SCHEMA_PATH)
    enums = _parse_enum_doc(ENUMS_PATH.read_text(encoding="utf-8"))
    known_ids = {"Field": {vector.field_id}}

    record = _to_fixture_record(rec)
    problems = _validate_entity(
        "CropRecommendation", record, schema, enums, known_ids, {}, 0
    )
    assert problems == []


def test_predict_confidence_in_range(model):
    rec = model.predict(_full_vector())
    assert 0.0 <= rec.confidence <= 1.0


def test_predict_alternatives_respects_top_k(model):
    rec = model.predict(_full_vector(), top_k=2)
    assert len(rec.alternatives) <= 2
    assert rec.recommended_crop not in rec.alternatives


def test_predict_propagates_field_id_and_season(model):
    vector = _full_vector(field_id="zz000001-0000-4000-8000-000000000009", season="rabi")
    rec = model.predict(vector)
    assert rec.field_id == "zz000001-0000-4000-8000-000000000009"
    assert rec.season == "rabi"


def test_predict_raises_on_missing_soil(model):
    vector = _full_vector(soil_data_available=False, soil_ph=None,
                           soil_nitrogen_mg_per_kg=None,
                           soil_phosphorus_mg_per_kg=None,
                           soil_potassium_mg_per_kg=None)
    with pytest.raises(ValueError):
        model.predict(vector)
