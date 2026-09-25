"""Integration test: fixture -> FeatureBuilder -> mapping -> IrrigationPredictionModel.

Exercises the full chain end to end against real fixture data, not
mocked partway through, per docs/testing-strategy.md's "Integration"
layer. farm-001 has full data (weather+soil+NDVI); farm-002 has
weather+soil but no NDVI — both should still produce a valid advice
since NDVI is not used by this model version
(decisions/0008-irrigation-model-feature-mapping.md).
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

from check_specs import (  # noqa: E402
    ENUMS_PATH,
    SCHEMA_PATH,
    _load_yaml,
    _parse_enum_doc,
    _validate_entity,
)

from agro_mirai.models.irrigation_prediction_model import IrrigationPredictionModel  # noqa: E402
from agro_mirai.persistence.models import (  # noqa: E402
    Field_,
    NDVIReading,
    SoilSample,
    WeatherReading,
)
from agro_mirai.processing.feature_builder import FeatureBuilder  # noqa: E402

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


def _advise_for_first_field(fixture_name: str, as_of: date):
    data = _load_fixture(fixture_name)
    field_rec = data["fields"][0]
    field = _field_from(field_rec)

    weather = [
        _weather_from(r) for r in data["weather_readings"] if r["field_id"] == field.id
    ]
    soil = [_soil_from(r) for r in data["soil_samples"] if r["field_id"] == field.id]
    ndvi = [_ndvi_from(r) for r in data["ndvi_readings"] if r["field_id"] == field.id]

    vector = FeatureBuilder.build(field, weather, soil, ndvi, as_of)

    model = IrrigationPredictionModel()
    return model.predict(vector), field


def _to_fixture_record(rec) -> dict:
    """Serializes like a JSON fixture record: ISO timestamp strings,
    optional fields omitted rather than explicitly null."""
    record = dataclasses.asdict(rec)
    for key in ("created_at", "window_start_at", "window_end_at"):
        record[key] = getattr(rec, key).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {k: v for k, v in record.items() if v is not None}


@pytest.mark.parametrize("fixture_name", ["farm-001.json", "farm-002.json"])
def test_full_chain_produces_schema_valid_advice(fixture_name):
    rec, field = _advise_for_first_field(fixture_name, as_of=date(2026, 8, 24))

    schema = _load_yaml(SCHEMA_PATH)
    enums = _parse_enum_doc(ENUMS_PATH.read_text(encoding="utf-8"))
    known_ids = {"Field": {field.id}}

    record = _to_fixture_record(rec)
    problems = _validate_entity(
        "IrrigationAdvice", record, schema, enums, known_ids, {}, 0
    )
    assert problems == []
    assert rec.field_id == field.id
