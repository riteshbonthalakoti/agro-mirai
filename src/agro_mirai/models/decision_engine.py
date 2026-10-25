"""``DecisionEngine`` — orchestrates Modules 06/07/08/09 into one
``Advisory``.

Calls ``CropRecommendationModel``/``IrrigationPredictionModel``/
``DiseaseRiskModel`` and ``ExplanationService`` for a ``Field`` +
``FeatureVector``, then assembles the results into a single
schema-valid ``Advisory`` (``specs/core/schema.yaml``). This is a
compositor, not an arbiter — see ``decisions/0011-decision-engine.md``
for why conflicts between model outputs are surfaced unmodified rather
than synthesized, why all three models are always called, and why the
alert-threshold signal reuses ``Advisory.severity`` instead of a new
field.
"""
import uuid
from datetime import datetime, timezone

from agro_mirai.models.disease_risk_model import DiseaseRiskModel
from agro_mirai.models.explanation_service import ExplanationService
from agro_mirai.persistence.models import Advisory
from agro_mirai.processing.feature_builder import FeatureVector

_RISK_RANK = {"low": 0, "moderate": 1, "high": 2, "severe": 3}

ALERT_LEVELS = {"high", "severe"}


class DecisionEngine:
    def __init__(
        self,
        crop_model=None,
        irrigation_model=None,
        disease_model=None,
        explanation_service=None,
        voice_service=None,
    ):
        from agro_mirai.models.crop_recommendation_model import CropRecommendationModel
        from agro_mirai.models.irrigation_prediction_model import IrrigationPredictionModel

        self._crop_model = crop_model or CropRecommendationModel()
        self._irrigation_model = irrigation_model or IrrigationPredictionModel()
        self._disease_model = disease_model or DiseaseRiskModel()
        self._explanation_service = explanation_service or ExplanationService(
            crop_model=self._crop_model,
            irrigation_model=self._irrigation_model,
            voice_service=voice_service,
        )

    def recommend(self, field, features: FeatureVector, image_bytes: bytes | None = None) -> Advisory:
        """``image_bytes``: Module 21, optional. When given, the disease
        leg tries the CNN image path first (via
        ``image_or_environmental_disease.resolve_disease_alert``), falling
        back to the existing rule-based ``disease_model`` path on any CNN
        service failure — never raises, matches the hard fallback
        requirement. Existing callers that don't pass an image are
        unaffected: behavior is identical to before this parameter
        existed.

        AI cascade restructure (scratch/restructure-plan.md): tries a new
        LLM tier first (``source="llm"``), falling back to the full
        rule-based compositor below (``source="rule_based"``) if the LLM
        tier is unavailable or its reply can't be trusted. The rule-based
        path is unchanged -- still the authority of record, and the only
        path that runs the crop/irrigation/disease sub-models and their
        own cascades (see ``crop_recommendation_model.py`` and
        ``image_or_environmental_disease.py``)."""
        import logging

        from agro_mirai.api.advisory_llm import llm_recommend_advisory

        try:
            llm_result = llm_recommend_advisory(features)
        except Exception as exc:  # a tier must never raise
            logging.getLogger(__name__).warning(
                "Advisory LLM tier field=%s: unexpected error: %s", features.field_id, exc
            )
            llm_result = None
        if llm_result is not None:
            logging.getLogger(__name__).info(
                "advisory_cascade field=%s tier=1 provider=llm", features.field_id
            )
            return llm_result

        logging.getLogger(__name__).info(
            "advisory_cascade field=%s tier=2 provider=rule_based", features.field_id
        )
        return self._recommend_rule_based(field, features, image_bytes=image_bytes)

    def _recommend_rule_based(self, field, features: FeatureVector, image_bytes: bytes | None = None) -> Advisory:
        crop = self._crop_model.predict(features)
        irrigation = self._irrigation_model.predict(features)

        from agro_mirai.models.image_or_environmental_disease import resolve_disease_alert

        disease = resolve_disease_alert(
            self._disease_model, features, features.field_id, image_bytes=image_bytes
        )

        crop_explanation = self._explanation_service.explain_crop(crop, features)
        irrigation_explanation = self._explanation_service.explain_irrigation(
            irrigation, features
        )
        disease_explanation = self._explanation_service.explain_disease(disease, features)

        severity = max(
            irrigation.urgency, disease.risk_level, key=lambda level: _RISK_RANK[level]
        )

        body = "\n\n".join(
            [
                crop_explanation.summary_en,
                irrigation_explanation.summary_en,
                disease_explanation.summary_en,
            ]
        )

        return Advisory(
            id=str(uuid.uuid4()),
            field_id=features.field_id,
            created_at=datetime.now(timezone.utc),
            language="en",
            title=f"Advisory for {crop.recommended_crop}",
            body=body,
            severity=severity,
            source_refs=[crop.id, irrigation.id, disease.id],
            source="rule_based",
        )
