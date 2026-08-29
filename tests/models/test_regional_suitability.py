"""Unit tests for the Module 18 Bellary/Karnataka regional-suitability
sanity layer (`regional_suitability.py`, decisions/0016).
"""
from __future__ import annotations

from agro_mirai.models.regional_suitability import (
    BELLARY_REGIONAL_CROPS,
    check_regional_fit,
)


def test_regional_set_is_subset_of_crop_type_enum():
    # 22-label crop_type enum from specs/core/enums.md.
    crop_type_enum = {
        "rice", "maize", "chickpea", "kidneybeans", "pigeonpeas",
        "mothbeans", "mungbean", "blackgram", "lentil", "pomegranate",
        "banana", "mango", "grapes", "watermelon", "muskmelon", "apple",
        "orange", "papaya", "coconut", "cotton", "jute", "coffee",
    }
    assert BELLARY_REGIONAL_CROPS.issubset(crop_type_enum)


def test_regional_set_is_non_trivial():
    # Prompt requires "enough crops to be genuinely useful", not just
    # the single fixture's current crop.
    assert len(BELLARY_REGIONAL_CROPS) >= 3


def test_in_region_crop_no_flag():
    result = check_regional_fit("cotton", ["rice", "maize"])
    assert result.out_of_region is False
    assert result.regional_alternative is None


def test_out_of_region_crop_flag_raised_with_regional_alternative():
    # grapes is not in BELLARY_REGIONAL_CROPS; rice is.
    result = check_regional_fit("grapes", ["banana", "rice", "mango"])
    assert result.out_of_region is True
    assert result.regional_alternative == "rice"


def test_out_of_region_crop_picks_first_regional_alternative_by_rank():
    # alternatives are pre-ranked by probability — the first regional
    # match should win, not an arbitrary one.
    result = check_regional_fit("grapes", ["mango", "cotton", "rice"])
    assert result.regional_alternative == "cotton"


def test_out_of_region_crop_no_regional_alternative_available():
    result = check_regional_fit("grapes", ["mango", "banana", "papaya"])
    assert result.out_of_region is True
    assert result.regional_alternative is None


def test_out_of_region_crop_empty_alternatives():
    result = check_regional_fit("grapes", [])
    assert result.out_of_region is True
    assert result.regional_alternative is None


def test_out_of_region_crop_none_alternatives():
    result = check_regional_fit("grapes", None)
    assert result.out_of_region is True
    assert result.regional_alternative is None
