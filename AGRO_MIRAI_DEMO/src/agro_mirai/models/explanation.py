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
    #: Module 25, additive: a translation into any V1_LANGUAGES target
    #: (not just Kannada), paired with the language it's actually in.
    #: summary_kn above is frozen at its existing en->kn meaning per the
    #: additive-only contract rule — this is the general-purpose sibling,
    #: not a replacement. Neither field is currently exposed via any API
    #: response (Explanation is internal-only — Advisory.body concatenates
    #: summary_en per ADR 0011); real end-user audio localization for
    #: te/hi already flows through GET /v2/advisories/{id}/audio's
    #: generic translate-then-synthesize path (voice_client.py), which
    #: needed no changes beyond V1_LANGUAGES widening.
    summary_translated: str | None = None
    summary_translated_lang: str | None = None
