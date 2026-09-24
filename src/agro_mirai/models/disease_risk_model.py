"""``DiseaseRiskModel`` — environmental threshold scoring, wrapped.

Wraps ``disease_risk_scoring.score_disease_risk`` so callers (Module 09)
never touch the scoring internals directly and call this the same way
they call ``CropRecommendationModel``/``IrrigationPredictionModel``:
``predict(FeatureVector) -> DiseaseRiskAlert``. Unlike Modules 06/07,
there is no trained artifact to load — see
``decisions/0009-disease-risk-model.md`` for why this module is
rule-based rather than a trained classifier or image CNN.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from agro_mirai.models.disease_risk_scoring import score_disease_risk
from agro_mirai.persistence.models import DiseaseRiskAlert
from agro_mirai.processing.feature_builder import FeatureVector


class DiseaseRiskModel:
    def predict(self, features: FeatureVector) -> DiseaseRiskAlert:
        result = score_disease_risk(features)

        created_at = datetime.now(timezone.utc)

        return DiseaseRiskAlert(
            id=str(uuid.uuid4()),
            field_id=features.field_id,
            created_at=created_at,
            disease=result.disease,
            risk_level=result.risk_level,
            confidence=result.confidence,
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
