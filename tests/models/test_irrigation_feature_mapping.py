"""Unit tests for irrigation_feature_mapping, per decisions/0008-irrigation-model-feature-mapping.md."""
from __future__ import annotations

from datetime import date

import pytest

from agro_mirai.models.irrigation_feature_mapping import (
    MODEL_FEATURE_COLUMNS,
    map_features,
)
from agro_mirai.processing.feature_builder import FeatureVector


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


def test_known_input_known_expected_shape():
    vector = _full_vector()

    row = map_features(vector)

    assert row == {
        "Soil_pH": 6.8,
        "Soil_Moisture": 18.0,
        "Temperature_C": 25.5,
        "Humidity": 68.0,
        "Rainfall_mm": 120.0,
        "season_Kharif": 1.0,
        "season_Rabi": 0.0,
        "season_Zaid": 0.0,
    }
    assert list(row.keys()) == list(MODEL_FEATURE_COLUMNS)


def test_season_one_hot_switches_column():
    row = map_features(_full_vector(season="rabi"))

    assert row["season_Kharif"] == 0.0
    assert row["season_Rabi"] == 1.0
    assert row["season_Zaid"] == 0.0


def test_raises_when_soil_unavailable():
    vector = _full_vector(soil_data_available=False, soil_ph=None, soil_moisture_pct=None)

    with pytest.raises(ValueError, match="soil_data_available"):
        map_features(vector)


def test_raises_when_soil_available_but_moisture_none():
    vector = _full_vector(soil_moisture_pct=None)

    with pytest.raises(ValueError, match="soil_moisture_pct"):
        map_features(vector)


def test_raises_when_weather_window_missing():
    vector = _full_vector(temp_c_mean_14d=None)

    with pytest.raises(ValueError, match="temp_c_mean_14d"):
        map_features(vector)


def test_raises_when_humidity_window_missing():
    vector = _full_vector(humidity_pct_mean_14d=None)

    with pytest.raises(ValueError, match="humidity_pct_mean_14d"):
        map_features(vector)


def test_raises_when_season_unrecognized():
    vector = _full_vector(season="monsoon")

    with pytest.raises(ValueError, match="season"):
        map_features(vector)


def test_season_none_no_longer_raises_it_falls_back_to_as_of_month():
    # Module 39: was "raises when season None" -- see the fallback test below.
    assert map_features(_full_vector(season=None))["season_Kharif"] == 1.0  # as_of is 24 Aug


def test_season_falls_back_to_advice_date_when_sowing_month_has_no_season():
    """Module 39: a field sown in Sep has FeatureVector.season None; irrigation
    must still map, using the month of as_of instead of refusing."""
    assert map_features(_full_vector(season=None, as_of=date(2026, 9, 20)))["season_Kharif"] == 1.0
    assert map_features(_full_vector(season=None, as_of=date(2026, 1, 15)))["season_Rabi"] == 1.0
    assert map_features(_full_vector(season=None, as_of=date(2026, 3, 15)))["season_Zaid"] == 1.0
