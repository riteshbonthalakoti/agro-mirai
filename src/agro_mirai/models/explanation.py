"""``Explanation`` — the uniform output shape Module 10 consumes from
``ExplanationService``, regardless of which model produced the
underlying advisory. See ``decisions/0010-explainability.md`` for the
SHAP-vs-rule-attribution split and the full field-by-field rationale.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class FeatureContribution:
    feature_name: str
    feature_value: float
    contribution: float
    direction: str  # "increases" | "decreases"


@dataclass
class Explanation:
    id: str
    field_id: str
    created_at: datetime
    subject_type: str  # "crop_recommendation" | "irrigation_advice" | "disease_risk_alert"
    subject_id: str
    method: str  # "shap_tree" | "rule_weight"
    top_contributions: list[FeatureContribution]
    summary_en: str
    summary_kn: str | None = None
