"""Tests for FeatureBuilder, per specs/core/features.md.

Covers the missing-data policy explicitly: full data, missing NDVI,
missing soil, weather-only (bare minimum), and the zero-weather error.
farm-002.json is loaded directly to exercise the "missing NDVI" case
against real fixture data rather than only synthetic in-test data.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from agro_mirai.persistence.models import Field_, NDVIReading, SoilSample, WeatherReading
from agro_mirai.processing.feature_builder import FeatureBuilder

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "specs" / "domains" / "fixtures"


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


def _sample_field(sown_on: date | None = date(2026, 6, 15)) -> Field_:
    return Field_(
        id="ff000001-0000-4000-8000-000000000001",
        farmer_id="aa000001-0000-4000-8000-000000000001",
        created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        name="Test Field",
        latitude=15.0,
        longitude=76.0,
        area_ha=1.0,
        sown_on=sown_on,
    )


def _sample_weather(days: list[int], month: int = 8) -> list[WeatherReading]:
    return [
        WeatherReading(
            id=f"w{d}",
            field_id="ff000001-0000-4000-8000-000000000001",
            observed_at=datetime(2026, month, d, 6, 0, tzinfo=timezone.utc),
            source="open_meteo",
            temp_c=25.0 + d * 0.1,
            is_forecast=False,
            humidity_pct=70.0,
            rainfall_mm=1.0,
        )
        for d in days
    ]


def _sample_soil() -> SoilSample:
    return SoilSample(
        id="s1",
        field_id="ff000001-0000-4000-8000-000000000001",
        observed_at=datetime(2026, 6, 10, tzinfo=timezone.utc),
        source="lab_report",
        ph=6.8,
        nitrogen_mg_per_kg=45.0,
        phosphorus_mg_per_kg=28.0,
        potassium_mg_per_kg=180.0,
        organic_carbon_pct=0.6,
        moisture_pct=18.0,
    )


def _sample_ndvi(as_of_day: int) -> list[NDVIReading]:
    return [
        NDVIReading(
            id="n1",
            field_id="ff000001-0000-4000-8000-000000000001",
            observed_at=datetime(2026, 8, as_of_day - 4, 5, 30, tzinfo=timezone.utc),
            source="gee_live",
            ndvi=0.55,
        ),
        NDVIReading(
            id="n2",
            field_id="ff000001-0000-4000-8000-000000000001",
            observed_at=datetime(2026, 8, as_of_day - 1, 5, 30, tzinfo=timezone.utc),
            source="cache",
            ndvi=0.62,
        ),
    ]


# --- (a) full data ---

def test_full_data_all_features_populated():
    field = _sample_field()
    weather = _sample_weather(range(18, 25))
    soil = [_sample_soil()]
    ndvi = _sample_ndvi(24)
    as_of = date(2026, 8, 24)

    fv = FeatureBuilder.build(field, weather, soil, ndvi, as_of)

    assert fv.soil_data_available is True
    assert fv.soil_ph == 6.8
    assert fv.soil_npk_balance_index == pytest.approx(45.0 / (45.0 + 28.0 + 180.0))

    assert fv.ndvi_data_available is True
    assert fv.ndvi_latest == 0.62
    assert fv.ndvi_trend == pytest.approx(0.62 - 0.55)
    assert fv.ndvi_confidence_source == "cache"

    assert fv.rainfall_mm_sum_7d == pytest.approx(7.0)
    assert fv.temp_c_mean_7d is not None
    assert fv.humidity_pct_mean_7d == pytest.approx(70.0)

    assert fv.season == "kharif"
    assert fv.days_since_sowing == 70


# --- (b) missing NDVI entirely (synthetic) ---

def test_missing_ndvi_entirely():
    field = _sample_field()
    weather = _sample_weather(range(18, 25))
    soil = [_sample_soil()]
    as_of = date(2026, 8, 24)

    fv = FeatureBuilder.build(field, weather, soil, [], as_of)

    assert fv.ndvi_data_available is False
    assert fv.ndvi_latest is None
    assert fv.ndvi_trend is None
    assert fv.ndvi_confidence_source is None
    # soil/weather unaffected
    assert fv.soil_data_available is True
    assert fv.rainfall_mm_sum_7d == pytest.approx(7.0)


# --- (b') missing NDVI, loaded from real farm-002.json fixture ---

def test_missing_ndvi_from_farm_002_fixture():
    data = _load_fixture("farm-002.json")
    assert data["ndvi_readings"] == []

    field_rec = data["fields"][0]
    field = _field_from(field_rec)
    weather = [_weather_from(r) for r in data["weather_readings"]]
    soil = [_soil_from(r) for r in data["soil_samples"]]
    ndvi = [_ndvi_from(r) for r in data["ndvi_readings"]]

    as_of = max(w.observed_at.date() for w in weather)
    fv = FeatureBuilder.build(field, weather, soil, ndvi, as_of)

    assert fv.ndvi_data_available is False
    assert fv.ndvi_latest is None
    assert fv.ndvi_trend is None
    assert fv.ndvi_confidence_source is None

    assert fv.soil_data_available is True
    assert fv.soil_ph == 7.2
    assert fv.rainfall_mm_sum_7d == pytest.approx(2.4)
    assert fv.season == "kharif"


# --- (c) missing soil entirely ---

def test_missing_soil_entirely():
    field = _sample_field()
    weather = _sample_weather(range(18, 25))
    ndvi = _sample_ndvi(24)
    as_of = date(2026, 8, 24)

    fv = FeatureBuilder.build(field, weather, [], ndvi, as_of)

    assert fv.soil_data_available is False
    assert fv.soil_ph is None
    assert fv.soil_nitrogen_mg_per_kg is None
    assert fv.soil_npk_balance_index is None
    # ndvi/weather unaffected
    assert fv.ndvi_data_available is True


# --- (d) weather-only (bare minimum) ---

def test_weather_only_bare_minimum():
    field = _sample_field()
    weather = _sample_weather(range(18, 25))
    as_of = date(2026, 8, 24)

    fv = FeatureBuilder.build(field, weather, [], [], as_of)

    assert fv.soil_data_available is False
    assert fv.ndvi_data_available is False
    assert fv.rainfall_mm_sum_7d == pytest.approx(7.0)
    assert fv.temp_c_mean_7d is not None


# --- (e) zero weather readings raises ---

def test_zero_weather_readings_raises():
    field = _sample_field()
    as_of = date(2026, 8, 24)

    with pytest.raises(ValueError):
        FeatureBuilder.build(field, [], [], [], as_of)


# --- season mapping spot checks ---

@pytest.mark.parametrize(
    "sown_month,expected_season",
    [(6, "kharif"), (7, "kharif"), (10, "rabi"), (12, "rabi"),
     (3, "zaid"), (5, "zaid"), (8, None), (1, None)],
)
def test_season_mapping(sown_month, expected_season):
    field = _sample_field(sown_on=date(2026, sown_month, 10))
    weather = _sample_weather([1], month=sown_month)
    as_of = date(2026, sown_month, 20)

    fv = FeatureBuilder.build(field, weather, [], [], as_of)
    assert fv.season == expected_season


def test_no_sown_on_yields_none_season_and_days():
    field = _sample_field(sown_on=None)
    weather = _sample_weather(range(18, 25))
    as_of = date(2026, 8, 24)

    fv = FeatureBuilder.build(field, weather, [], [], as_of)
    assert fv.season is None
    assert fv.days_since_sowing is None
