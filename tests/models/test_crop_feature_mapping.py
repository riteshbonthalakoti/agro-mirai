"""Unit tests for crop_feature_mapping, per decisions/0007-crop-model-feature-mapping.md."""
from __future__ import annotations

from datetime import date

import pytest

from agro_mirai.models.crop_feature_mapping import MODEL_FEATURE_COLUMNS, map_features
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
        "N": 45.0,
        "P": 28.0,
        "K": 180.0,
        "temperature": 25.5,
        "humidity": 68.0,
        "ph": 6.8,
        "rainfall": 120.0,
    }
    assert list(row.keys()) == list(MODEL_FEATURE_COLUMNS)


def test_raises_when_soil_unavailable():
    vector = _full_vector(
        soil_data_available=False,
        soil_ph=None,
        soil_nitrogen_mg_per_kg=None,
        soil_phosphorus_mg_per_kg=None,
        soil_potassium_mg_per_kg=None,
    )

    with pytest.raises(ValueError, match="soil_data_available"):
        map_features(vector)


def test_raises_when_soil_available_but_field_none():
    vector = _full_vector(soil_ph=None)

    with pytest.raises(ValueError, match="soil_ph"):
        map_features(vector)


def test_raises_when_weather_window_missing():
    vector = _full_vector(temp_c_mean_14d=None)

    with pytest.raises(ValueError, match="temp_c_mean_14d"):
        map_features(vector)


def test_raises_when_humidity_window_missing():
    vector = _full_vector(humidity_pct_mean_14d=None)

    with pytest.raises(ValueError, match="humidity_pct_mean_14d"):
        map_features(vector)
