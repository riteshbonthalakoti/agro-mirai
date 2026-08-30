"""Unit tests for the PlantVillage class-name -> risk_level/display mapping.

Pure-function tests, no torch/artifact needed — see
docs/testing-strategy.md's "Unit" layer.
"""
from __future__ import annotations

from agro_mirai.models.disease_cnn_labels import (
    CNN_COVERED_CROP_TYPES,
    crop_type_for,
    disease_display_name,
    parse_class_name,
    risk_level_for,
)


def test_parse_class_name_healthy():
    crop, disease, is_healthy = parse_class_name("Apple___healthy")
    assert crop == "Apple"
    assert disease == "healthy"
    assert is_healthy is True


def test_parse_class_name_disease():
    crop, disease, is_healthy = parse_class_name("Corn_(maize)___Northern_Leaf_Blight")
    assert crop == "Corn_(maize)"
    assert disease == "Northern Leaf Blight"
    assert is_healthy is False


def test_crop_type_for_covered_crop():
    assert crop_type_for("Apple___Apple_scab") == "apple"
    assert crop_type_for("Corn_(maize)___healthy") == "maize"
    assert crop_type_for("Grape___Black_rot") == "grapes"
    assert crop_type_for("Orange___Haunglongbing_(Citrus_greening)") == "orange"


def test_crop_type_for_uncovered_crop_returns_none():
    assert crop_type_for("Tomato___Bacterial_spot") is None
    assert crop_type_for("Potato___Late_blight") is None


def test_cnn_covered_crop_types_is_subset_of_four():
    assert CNN_COVERED_CROP_TYPES == {"apple", "maize", "grapes", "orange"}


def test_risk_level_healthy_is_always_low():
    assert risk_level_for("Apple___healthy", confidence=0.99) == "low"
    assert risk_level_for("Tomato___healthy", confidence=0.30) == "low"


def test_risk_level_disease_floors_at_moderate():
    assert risk_level_for("Apple___Apple_scab", confidence=0.01) == "moderate"


def test_risk_level_disease_scales_with_confidence():
    assert risk_level_for("Apple___Apple_scab", confidence=0.50) == "moderate"
    assert risk_level_for("Apple___Apple_scab", confidence=0.70) == "high"
    assert risk_level_for("Apple___Apple_scab", confidence=0.90) == "severe"


def test_disease_display_name_healthy():
    assert disease_display_name("Apple___healthy") == (
        "Apple: no disease detected (healthy foliage)"
    )


def test_disease_display_name_disease():
    assert disease_display_name("Grape___Black_rot") == "Grape: Black rot"
