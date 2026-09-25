"""Integration test: fixture -> FeatureBuilder -> DecisionEngine, against
real crop/irrigation artifacts and the real disease scoring/explanation
paths. First test proving Modules 05-09 compose end to end
(decisions/0011-decision-engine.md).
"""
from __future__ import annotations

import dataclasses
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from agro_mirai.models.crop_recommendation_model import CropRecommendationModel  # noqa: E402

from check_specs import (  # noqa: E402
    ENUMS_PATH,
    SCHEMA_PATH,
    _load_yaml,
    _parse_enum_doc,
    _validate_entity,
)

from agro_mirai.models.decision_engine import ALERT_LEVELS, DecisionEngine  # noqa: E402
from agro_mirai.persistence.models import (  # noqa: E402
    Field_,
    NDVIReading,
    SoilSample,
    WeatherReading,
)
from agro_mirai.processing.feature_builder import FeatureBuilder, FeatureVector  # noqa: E402

FIXTURES_DIR = ROOT / "specs" / "domains" / "fixtures"


def _pdt(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _pdate(value: str | None) -> date | None:
    if value is None:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def _field_from(rec: dict) -> Field_:
    return Field_(
        id=rec["id"],
        farmer_id=rec["farmer_id"],
        created_at=_pdt(rec["created_at"]),
        updated_at=_pdt(rec["updated_at"]),
        name=rec["name"],
        latitude=rec["latitude"],
        longitude=rec["longitude"],
        area_ha=rec["area_ha"],
        elevation_m=rec.get("elevation_m"),
        soil_type=rec.get("soil_type"),
        current_crop=rec.get("current_crop"),
        sown_on=_pdate(rec.get("sown_on")),
    )


def _weather_from(rec: dict) -> WeatherReading:
    return WeatherReading(
        id=rec["id"],
        field_id=rec["field_id"],
        observed_at=_pdt(rec["observed_at"]),
        source=rec["source"],
        temp_c=rec["temp_c"],
        is_forecast=rec["is_forecast"],
        temp_min_c=rec.get("temp_min_c"),
        temp_max_c=rec.get("temp_max_c"),
        humidity_pct=rec.get("humidity_pct"),
        rainfall_mm=rec.get("rainfall_mm"),
        wind_mps=rec.get("wind_mps"),
    )


def _soil_from(rec: dict) -> SoilSample:
    return SoilSample(
        id=rec["id"],
        field_id=rec["field_id"],
        observed_at=_pdt(rec["observed_at"]),
        source=rec["source"],
        ph=rec.get("ph"),
        nitrogen_mg_per_kg=rec.get("nitrogen_mg_per_kg"),
        phosphorus_mg_per_kg=rec.get("phosphorus_mg_per_kg"),
        potassium_mg_per_kg=rec.get("potassium_mg_per_kg"),
        organic_carbon_pct=rec.get("organic_carbon_pct"),
        moisture_pct=rec.get("moisture_pct"),
    )


def _ndvi_from(rec: dict) -> NDVIReading:
    return NDVIReading(
        id=rec["id"],
        field_id=rec["field_id"],
        observed_at=_pdt(rec["observed_at"]),
        source=rec["source"],
        ndvi=rec["ndvi"],
        cloud_cover_pct=rec.get("cloud_cover_pct"),
        satellite=rec.get("satellite"),
    )


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def _field_and_vector(fixture_name: str, as_of: date):
    data = _load_fixture(fixture_name)
    field_rec = data["fields"][0]
    field = _field_from(field_rec)

    weather = [_weather_from(r) for r in data["weather_readings"] if r["field_id"] == field.id]
    soil = [_soil_from(r) for r in data["soil_samples"] if r["field_id"] == field.id]
    ndvi = [_ndvi_from(r) for r in data["ndvi_readings"] if r["field_id"] == field.id]

    vector = FeatureBuilder.build(field, weather, soil, ndvi, as_of)
    return field, vector


@pytest.mark.parametrize("fixture_name", ["farm-001.json", "farm-002.json"])
def test_full_chain_produces_schema_valid_advisory(fixture_name):
    field, vector = _field_and_vector(fixture_name, as_of=date(2026, 8, 24))

    engine = DecisionEngine()
    advisory = engine.recommend(field, vector)

    schema = _load_yaml(SCHEMA_PATH)
    enums = _parse_enum_doc(ENUMS_PATH.read_text(encoding="utf-8"))
    known_ids = {"Field": {field.id}}

    record = dataclasses.asdict(advisory)
    record["created_at"] = advisory.created_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    problems = _validate_entity("Advisory", record, schema, enums, known_ids, {}, 0)
    assert problems == []

    assert advisory.field_id == field.id
    assert advisory.title
    assert advisory.body
    assert len(advisory.source_refs) == 3
    assert all(advisory.source_refs)

    # Module 18: if the crop model's top pick for this fixture is
    # out-of-region, the Advisory body (which concatenates
    # summary_en unmodified per ADR 0011) must carry the caveat.
    crop_model = CropRecommendationModel()
    crop = crop_model.predict(vector)
    if crop.out_of_region:
        assert "caveat" in advisory.body.lower()


def test_synthetic_high_urgency_input_triggers_alert():
    _, vector = _field_and_vector("farm-001.json", as_of=date(2026, 8, 24))
    high_risk_vector = dataclasses.replace(
        vector,
        soil_moisture_pct=5.0,
        humidity_pct_mean_14d=90.0,
        rainfall_mm_sum_7d=40.0,
        temp_c_mean_14d=25.0,
        ndvi_trend=-0.08,
    )

    engine = DecisionEngine()
    advisory = engine.recommend(None, high_risk_vector)

    assert advisory.severity in ALERT_LEVELS
