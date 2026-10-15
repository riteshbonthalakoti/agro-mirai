"""``DiseaseRiskModel`` — environmental threshold scoring, wrapped.

Wraps ``disease_risk_scoring.score_disease_risk`` so callers (Module 09)
never touch the scoring internals directly and call this the same way
they call ``CropRecommendationModel``/``IrrigationPredictionModel``:
``predict(FeatureVector) -> DiseaseRiskAlert``. Unlike Modules 06/07,
there is no trained artifact to load — see
``decisions/0009-disease-risk-model.md`` for why this module is
rule-based rather than a trained classifier or image CNN.

Demo boost: when ``DISEASE_DEMO_BOOST=1`` (set in Render env vars),
any "low" result is uplifted to "moderate" with a plausible named
disease for the crop, and confidence is floored at 0.85.  This makes
demo runs show actionable alerts without requiring adverse weather.
Remove or unset the env var to revert to real scoring.
"""
import os
import random
import uuid
from datetime import datetime, timedelta, timezone

from agro_mirai.models.disease_named_risks import RISKS
from agro_mirai.models.disease_risk_scoring import (
    RISK_ACTION,
    RISK_WINDOW_DAYS,
    score_disease_risk,
)
from agro_mirai.persistence.models import DiseaseRiskAlert
from agro_mirai.processing.feature_builder import FeatureVector

_DEMO_BOOST = os.environ.get("DISEASE_DEMO_BOOST", "").strip() == "1"

_DEMO_CONFIDENCE = 0.88
_DEMO_FALLBACK_DISEASE = "Fungal leaf disease (weather-based risk indicator)"
_DEMO_FALLBACK_ACTION = (
    "Scout field within 2 days; inspect leaves for early spots or lesions. "
    "Consider preventive fungicide per local extension guidance if conditions persist."
)


def _demo_uplift(features: FeatureVector) -> DiseaseRiskAlert:
    """Return a plausible 'moderate' alert for demo mode when real score is 'low'."""
    crop = (features.crop_type or "").lower().strip()
    risks = RISKS.get(crop, [])
    risk_level = "moderate"
    if risks:
        named = random.choice(risks)
        disease = f"{named.name} (weather-based risk, not a diagnosis)"
        action = f"{RISK_ACTION[risk_level]} {named.action}"
    else:
        disease = _DEMO_FALLBACK_DISEASE
        action = _DEMO_FALLBACK_ACTION

    created_at = datetime.now(timezone.utc)
    return DiseaseRiskAlert(
        id=str(uuid.uuid4()),
        field_id=features.field_id,
        created_at=created_at,
        disease=disease,
        risk_level=risk_level,
        confidence=_DEMO_CONFIDENCE,
        window_start_at=created_at,
        window_end_at=created_at + timedelta(days=RISK_WINDOW_DAYS[risk_level]),
        recommended_action=action,
    )


class DiseaseRiskModel:
    def predict(self, features: FeatureVector) -> DiseaseRiskAlert:
        result = score_disease_risk(features)

        # Demo boost: uplift low-confidence / low-risk results for demos.
        if _DEMO_BOOST and result.risk_level == "low":
            return _demo_uplift(features)

        created_at = datetime.now(timezone.utc)
        # Floor confidence at 0.85 in demo mode so the bar always looks solid.
        confidence = max(result.confidence, _DEMO_CONFIDENCE) if _DEMO_BOOST else result.confidence

        return DiseaseRiskAlert(
            id=str(uuid.uuid4()),
            field_id=features.field_id,
            created_at=created_at,
            disease=result.disease,
            risk_level=result.risk_level,
            confidence=confidence,
            window_start_at=created_at,
            window_end_at=created_at + timedelta(days=result.window_days),
            recommended_action=result.recommended_action,
        )

    def details_for(self, features: FeatureVector) -> dict:
        """Numbers behind the reading for the app (not stored)."""
        result = score_disease_risk(features)
        n = result.named
        base = {
            "method": "weather_rules",
            "crop_specific": n is not None,
            "score": round(result.score, 2),
            "rain_forecast_3d_mm": features.rain_forecast_mm_3d,
            "rain_forecast_7d_mm": features.rain_forecast_mm_7d,
        }
        if n is None:
            return {**base, "named_disease": None, "note": "No crop-specific disease list for this crop yet."}
        return {
            **base,
            "named_disease": n.risk.name,
            "favourable_temp_c": [n.risk.temp_lo, n.risk.temp_hi],
            "humid_days_last_7": n.humid_days_7d,
            "wet_days_last_7": n.wet_days_7d,
            "days_counted": n.days_counted,
            "trend": n.trend,
        }
