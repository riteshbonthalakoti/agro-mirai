"""Pure disease-risk scoring function over a Module 05 ``FeatureVector``.

Implements exactly the weighted threshold system documented in
``decisions/0009-disease-risk-model.md`` — read that ADR before changing
any weight, threshold, or window choice here. No sklearn, no trained
artifact: this is a rule-based composite score, not a classifier.
"""
from __future__ import annotations

from dataclasses import dataclass

from agro_mirai.processing.feature_builder import FeatureVector

_HUMIDITY_WEIGHT = 0.40
_RAINFALL_WEIGHT = 0.25
_TEMP_WEIGHT = 0.15
_NDVI_WEIGHT = 0.20

_HUMIDITY_FLOOR = 50.0
_HUMIDITY_SPAN = 40.0  # ceiling 90.0

_RAINFALL_CEILING_MM = 40.0

_TEMP_OPTIMUM_C = 25.0
_TEMP_SPAN_C = 10.0

_NDVI_DROP_CEILING = 0.05

_RISK_DISEASE = "Generic fungal disease risk (environmental proxy — no image-based diagnosis)"

_RISK_ACTION = {
    "low": "Continue routine monitoring; no action needed.",
    "moderate": "Increase field scouting frequency; watch for early lesions or leaf spotting.",
    "high": "Scout field within 2 days; consider preventive fungicide application per local extension guidance.",
    "severe": "Scout immediately; apply fungicide per local extension guidance and consider improving field drainage/airflow.",
}

_RISK_WINDOW_DAYS = {
    "low": 14,
    "moderate": 7,
    "high": 2,
    "severe": 1,
}


@dataclass
class DiseaseRiskScore:
    score: float
    risk_level: str
    confidence: float
    disease: str
    recommended_action: str
    window_days: int


def _clip(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _risk_level_for(score: float) -> str:
    if score < 0.30:
        return "low"
    if score < 0.50:
        return "moderate"
    if score < 0.70:
        return "high"
    return "severe"


def score_disease_risk(vector: FeatureVector) -> DiseaseRiskScore:
    """Scores disease risk from environmental signals in ``vector``.

    Raises ``ValueError`` if ``humidity_pct_mean_14d`` or
    ``temp_c_mean_14d`` are ``None`` — both are expected to always be
    present given ``FeatureBuilder``'s weather-required invariant; see
    ADR 0009's confidence-formula note.
    """
    if vector.humidity_pct_mean_14d is None or vector.temp_c_mean_14d is None:
        raise ValueError(
            "disease risk scoring requires humidity_pct_mean_14d and "
            "temp_c_mean_14d to be non-None"
        )

    humidity_score = _clip(
        (vector.humidity_pct_mean_14d - _HUMIDITY_FLOOR) / _HUMIDITY_SPAN, 0.0, 1.0
    )
    rainfall_score = _clip(vector.rainfall_mm_sum_7d / _RAINFALL_CEILING_MM, 0.0, 1.0)
    temp_score = 1.0 - _clip(
        abs(vector.temp_c_mean_14d - _TEMP_OPTIMUM_C) / _TEMP_SPAN_C, 0.0, 1.0
    )
    if (
        vector.ndvi_data_available
        and vector.ndvi_trend is not None
        and vector.ndvi_trend < 0
    ):
        ndvi_score = _clip(-vector.ndvi_trend / _NDVI_DROP_CEILING, 0.0, 1.0)
    else:
        ndvi_score = 0.0

    score = (
        _HUMIDITY_WEIGHT * humidity_score
        + _RAINFALL_WEIGHT * rainfall_score
        + _TEMP_WEIGHT * temp_score
        + _NDVI_WEIGHT * ndvi_score
    )
    risk_level = _risk_level_for(score)

    confidence = 0.5
    if vector.ndvi_data_available:
        confidence += 0.3
    if vector.rainfall_mm_sum_7d is not None and vector.humidity_pct_mean_14d is not None:
        confidence += 0.2
    confidence = _clip(confidence, 0.0, 1.0)

    return DiseaseRiskScore(
        score=score,
        risk_level=risk_level,
        confidence=confidence,
        disease=_RISK_DISEASE,
        recommended_action=_RISK_ACTION[risk_level],
        window_days=_RISK_WINDOW_DAYS[risk_level],
    )
