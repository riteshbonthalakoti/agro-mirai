"""``ExplanationService`` — turns a Module 06/07/08 prediction into a
uniform ``Explanation`` Module 10 can attach to any advisory output.

Crop and irrigation advice are rule-based (decisions/0027) and already
carry their own plain-language ``rationale``, which is what is reported
here. The disease score (Module 08) is explained by reading the same
weighted terms ``score_disease_risk`` already computes and reporting them
as direct feature attributions, labeled ``method="rule_weight"``. There is
no SHAP any more: the RandomForests it explained were retired. See
``decisions/0010-explainability.md`` (history) and ``decisions/0029``.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from agro_mirai.models.disease_risk_scoring import (
    _HUMIDITY_WEIGHT,
    _NDVI_WEIGHT,
    _RAINFALL_WEIGHT,
    _TEMP_WEIGHT,
    score_disease_risk,
)
from agro_mirai.models.explanation import Explanation, FeatureContribution
from agro_mirai.persistence.models import (
    CropRecommendation,
    DiseaseRiskAlert,
    IrrigationAdvice,
)
from agro_mirai.processing.feature_builder import FeatureVector

_TOP_K = 3
_log = logging.getLogger(__name__)


def _direction(contribution: float) -> str:
    return "increases" if contribution >= 0 else "decreases"


def _summary_en(
    subject_label: str, contributions: list[FeatureContribution], factor_label: str = "factors"
) -> str:
    if not contributions:
        return f"No contributing factors were available to explain this {subject_label}."
    parts = [
        f"{c.feature_name} ({c.feature_value:.2f}, {c.direction} the result)"
        for c in contributions
    ]
    return f"The biggest {factor_label} behind this {subject_label} were: " + "; ".join(parts) + "."


class ExplanationService:
    """Constructed with the same trained artifacts Modules 06/07 already
    load, plus an optional ``VoiceService`` for Kannada summaries."""

    def __init__(self, crop_model=None, irrigation_model=None, voice_service=None):
        self._crop_model = crop_model
        self._irrigation_model = irrigation_model
        self._voice_service = voice_service

    def _translate(self, summary_en: str, target_lang: str = "kn") -> str | None:
        if self._voice_service is None:
            return None
        return self._voice_service.translate(summary_en, "en", target_lang)

    def _finish(self, top, subject_type, subject_id, field_id, label, target_lang, extra="", method="rule_weight", fallback=None):
        summary_en = _summary_en(label, top) if top else (
            fallback or f"No detailed breakdown is available for this {label}; the result itself is unaffected."
        )
        summary_en += extra
        summary_kn = self._translate(summary_en)
        return Explanation(
            id=str(uuid.uuid4()), field_id=field_id, created_at=datetime.now(timezone.utc),
            subject_type=subject_type, subject_id=subject_id,
            method=method if (top or fallback) else "unavailable", top_contributions=top,
            summary_en=summary_en, summary_kn=summary_kn,
            summary_translated=summary_kn if target_lang == "kn" else self._translate(summary_en, target_lang),
            summary_translated_lang=target_lang if self._voice_service is not None else None,
        )

    def explain_crop(
        self, recommendation: CropRecommendation, features: FeatureVector, target_lang: str = "kn"
    ) -> Explanation:
        # rule-based pick (EcoCrop): the model already wrote the reason
        return self._finish(
            [], "crop_recommendation", recommendation.id, recommendation.field_id,
            f"recommendation of {recommendation.recommended_crop}", target_lang,
            method="rule_weight", fallback=recommendation.rationale,
        )

    def explain_irrigation(
        self, advice: IrrigationAdvice, features: FeatureVector, target_lang: str = "kn"
    ) -> Explanation:
        # urgency and depth come from one soil-water balance; its rationale is the explanation
        return self._finish(
            [], "irrigation_advice", advice.id, advice.field_id,
            f"{advice.urgency} irrigation urgency", target_lang,
            method="rule_weight", fallback=advice.rationale,
        )

    def explain_disease(
        self, alert: DiseaseRiskAlert, features: FeatureVector, target_lang: str = "kn"
    ) -> Explanation:
        score_disease_risk(features)  # validates required weather fields, raises if missing

        contributions = _disease_contributions(features)
        top = sorted(contributions, key=lambda c: -abs(c.contribution))[:_TOP_K]

        summary_en = _summary_en(
            f"{alert.risk_level} disease risk", top, factor_label="contributing factors"
        )
        summary_kn = self._translate(summary_en)
        return Explanation(
            id=str(uuid.uuid4()),
            field_id=alert.field_id,
            created_at=datetime.now(timezone.utc),
            subject_type="disease_risk_alert",
            subject_id=alert.id,
            method="rule_weight",
            top_contributions=top,
            summary_en=summary_en,
            summary_kn=summary_kn,
            summary_translated=summary_kn if target_lang == "kn" else self._translate(summary_en, target_lang),
            summary_translated_lang=target_lang if self._voice_service is not None else None,
        )


def _regional_fit_note(recommendation: CropRecommendation) -> str:
    """Module 18: plain-language caveat when the crop model's top pick
    isn't in the known Bellary/Karnataka regionally-grown set
    (`regional_suitability.py`, decisions/0016). Never silently drops or
    replaces the ML output — this is an appended honesty note."""
    if not recommendation.out_of_region:
        return ""
    if recommendation.regional_alternative:
        return (
            f" Caveat: {recommendation.recommended_crop} is not commonly grown in "
            f"the Bellary/Karnataka region based on available regional crop data; "
            f"{recommendation.regional_alternative} is a more regionally-established "
            f"alternative worth considering."
        )
    return (
        f" Caveat: {recommendation.recommended_crop} is not commonly grown in the "
        f"Bellary/Karnataka region based on available regional crop data, and none "
        f"of the other suggested alternatives are either — treat this recommendation "
        f"with extra caution and consult a local agriculture extension officer."
    )


def _clip(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _disease_contributions(vector: FeatureVector) -> list[FeatureContribution]:
    """Exact weight x signal decomposition of score_disease_risk's
    composite — not an approximation, since the scoring function is
    already a linear weighted sum. See decisions/0010-explainability.md.
    """
    humidity_score = _clip((vector.humidity_pct_mean_14d - 50.0) / 40.0, 0.0, 1.0)
    rainfall_score = _clip(vector.rainfall_mm_sum_7d / 40.0, 0.0, 1.0)
    temp_score = 1.0 - _clip(abs(vector.temp_c_mean_14d - 25.0) / 10.0, 0.0, 1.0)
    if (
        vector.ndvi_data_available
        and vector.ndvi_trend is not None
        and vector.ndvi_trend < 0
    ):
        ndvi_score = _clip(-vector.ndvi_trend / 0.05, 0.0, 1.0)
    else:
        ndvi_score = 0.0

    return [
        FeatureContribution(
            feature_name="humidity_pct_mean_14d",
            feature_value=float(vector.humidity_pct_mean_14d),
            contribution=_HUMIDITY_WEIGHT * humidity_score,
            direction="increases",
        ),
        FeatureContribution(
            feature_name="rainfall_mm_sum_7d",
            feature_value=float(vector.rainfall_mm_sum_7d),
            contribution=_RAINFALL_WEIGHT * rainfall_score,
            direction="increases",
        ),
        FeatureContribution(
            feature_name="temp_c_mean_14d",
            feature_value=float(vector.temp_c_mean_14d),
            contribution=_TEMP_WEIGHT * temp_score,
            direction="increases" if temp_score > 0 else "decreases",
        ),
        FeatureContribution(
            feature_name="ndvi_trend",
            feature_value=float(vector.ndvi_trend) if vector.ndvi_trend is not None else 0.0,
            contribution=_NDVI_WEIGHT * ndvi_score,
            direction="increases" if ndvi_score > 0 else "decreases",
        ),
    ]
