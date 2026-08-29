"""Unit tests for the Kc lookup / growth-stage approximation (Module 17)."""
from __future__ import annotations

from agro_mirai.models.crop_coefficients import KC_TABLE, growth_stage_for, kc_for


def test_kc_table_covers_every_crop_rf_label():
    # docs/eval/crop_rf_eval.json's "labels" field -- the real 22-crop
    # label set the trained crop-recommendation classifier predicts.
    labels = [
        "apple", "banana", "blackgram", "chickpea", "coconut", "coffee",
        "cotton", "grapes", "jute", "kidneybeans", "lentil", "maize",
        "mango", "mothbeans", "mungbean", "muskmelon", "orange", "papaya",
        "pigeonpeas", "pomegranate", "rice", "watermelon",
    ]
    assert set(labels).issubset(KC_TABLE.keys())


def test_annual_crop_growth_stage_breakpoints():
    assert growth_stage_for("rice", 0) == "initial"
    assert growth_stage_for("rice", 19) == "initial"
    assert growth_stage_for("rice", 20) == "development"
    assert growth_stage_for("rice", 49) == "development"
    assert growth_stage_for("rice", 50) == "mid_season"
    assert growth_stage_for("rice", 89) == "mid_season"
    assert growth_stage_for("rice", 90) == "late_season"
    assert growth_stage_for("rice", 300) == "late_season"


def test_perennial_crop_growth_stage():
    # apple is marked perennial=True.
    assert growth_stage_for("apple", 30) == "initial"
    assert growth_stage_for("apple", 364) == "initial"
    assert growth_stage_for("apple", 365) == "mid_season"
    assert growth_stage_for("apple", 2000) == "mid_season"


def test_growth_stage_defaults_to_mid_season_when_missing_inputs():
    assert growth_stage_for(None, 30) == "mid_season"
    assert growth_stage_for("rice", None) == "mid_season"
    assert growth_stage_for(None, None) == "mid_season"


def test_kc_for_initial_and_late_match_table_values():
    curve = KC_TABLE["rice"]
    assert kc_for("rice", "initial") == curve.kc_ini
    assert kc_for("rice", "mid_season") == curve.kc_mid
    assert kc_for("rice", "late_season") == curve.kc_end


def test_kc_for_development_is_midpoint_of_ini_and_mid():
    curve = KC_TABLE["maize"]
    expected = (curve.kc_ini + curve.kc_mid) / 2.0
    assert kc_for("maize", "development") == expected


def test_kc_for_unknown_crop_is_neutral_one():
    assert kc_for("unobtanium", "mid_season") == 1.0
    assert kc_for(None, "mid_season") == 1.0


def test_all_kc_curves_are_positive_and_plausible():
    for crop, curve in KC_TABLE.items():
        assert 0.0 < curve.kc_ini <= 1.5, crop
        assert 0.0 < curve.kc_mid <= 1.5, crop
        assert 0.0 < curve.kc_end <= 1.5, crop
