"""Unit tests for score_disease_risk against known inputs -> known risk level.

Per docs/testing-strategy.md's "Unit" layer: exercises the scoring
function in isolation, no FeatureBuilder/model wrapper involved.
"""
from __future__ import annotations

from datetime import date

import pytest

from agro_mirai.models.disease_risk_scoring import score_disease_risk
from agro_mirai.processing.feature_builder import FeatureVector


def _vector(**overrides) -> FeatureVector:
    defaults = dict(
        field_id="ff000001-0000-4000-8000-000000000001",
        as_of=date(2026, 8, 24),
        rainfall_mm_sum_7d=5.0,
        temp_c_mean_7d=25.0,
        humidity_pct_mean_7d=60.0,
        rainfall_mm_sum_14d=10.0,
        temp_c_mean_14d=25.0,
        humidity_pct_mean_14d=60.0,
        rainfall_mm_sum_30d=40.0,
        temp_c_mean_30d=25.0,
        humidity_pct_mean_30d=60.0,
        soil_data_available=False,
        ndvi_data_available=False,
        season="kharif",
        days_since_sowing=30,
    )
    defaults.update(overrides)
    return FeatureVector(**defaults)


def test_high_humidity_high_rainfall_optimal_temp_declining_ndvi_is_severe():
    vector = _vector(
        humidity_pct_mean_14d=90.0,
        rainfall_mm_sum_7d=40.0,
        temp_c_mean_14d=25.0,
        ndvi_data_available=True,
        ndvi_trend=-0.08,
    )
    result = score_disease_risk(vector)
    assert result.risk_level == "severe"
    assert result.score >= 0.70


def test_low_humidity_no_rain_extreme_temp_is_low():
    vector = _vector(
        humidity_pct_mean_14d=40.0,
        rainfall_mm_sum_7d=0.0,
        temp_c_mean_14d=10.0,
        ndvi_data_available=False,
    )
    result = score_disease_risk(vector)
    assert result.risk_level == "low"
    assert result.score < 0.30


def test_score_is_not_constant_across_inputs():
    low = score_disease_risk(
        _vector(humidity_pct_mean_14d=40.0, rainfall_mm_sum_7d=0.0, temp_c_mean_14d=10.0)
    )
    high = score_disease_risk(
        _vector(
            humidity_pct_mean_14d=90.0,
            rainfall_mm_sum_7d=40.0,
            temp_c_mean_14d=25.0,
            ndvi_data_available=True,
            ndvi_trend=-0.08,
        )
    )
    assert low.score != high.score
    assert low.risk_level != high.risk_level


def test_confidence_lower_without_ndvi():
    with_ndvi = score_disease_risk(
        _vector(ndvi_data_available=True, ndvi_trend=-0.02)
    )
    without_ndvi = score_disease_risk(_vector(ndvi_data_available=False))
    assert with_ndvi.confidence > without_ndvi.confidence


def test_missing_ndvi_trend_contributes_no_penalty_not_a_bonus():
    # ndvi_data_available=True but trend is None (single reading, no
    # trend computable yet) must not be treated as a decline.
    flat = score_disease_risk(_vector(ndvi_data_available=True, ndvi_trend=None))
    no_ndvi = score_disease_risk(_vector(ndvi_data_available=False))
    assert flat.score == pytest.approx(no_ndvi.score)


def test_rising_ndvi_contributes_no_penalty():
    rising = score_disease_risk(_vector(ndvi_data_available=True, ndvi_trend=0.05))
    no_ndvi = score_disease_risk(_vector(ndvi_data_available=False))
    assert rising.score == pytest.approx(no_ndvi.score)


def test_raises_on_missing_humidity():
    vector = _vector(humidity_pct_mean_14d=None)
    with pytest.raises(ValueError):
        score_disease_risk(vector)


def test_raises_on_missing_temperature():
    vector = _vector(temp_c_mean_14d=None)
    with pytest.raises(ValueError):
        score_disease_risk(vector)


def test_window_days_shrinks_as_risk_increases():
    low = score_disease_risk(
        _vector(humidity_pct_mean_14d=40.0, rainfall_mm_sum_7d=0.0, temp_c_mean_14d=10.0)
    )
    severe = score_disease_risk(
        _vector(
            humidity_pct_mean_14d=90.0,
            rainfall_mm_sum_7d=40.0,
            temp_c_mean_14d=25.0,
            ndvi_data_available=True,
            ndvi_trend=-0.08,
        )
    )
    assert severe.window_days < low.window_days
