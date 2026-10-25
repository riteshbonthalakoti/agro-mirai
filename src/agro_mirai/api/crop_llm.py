"""LLM-first tier for crop recommendation (AI cascade restructure,
scratch/restructure-plan.md): asks a free-tier LLM to rank crops for a
field from the same live weather/soil/NDVI/location data the existing
EcoCrop rule engine (``models/crop_recommendation_model.py``) already has,
as a second opinion ahead of it.

Mirrors every other client in this project's never-raise contract:
``llm_recommend_crop`` returns ``None`` on any failure (no key configured,
network error, malformed/incomplete JSON reply) so the caller
(``CropRecommendationModel.predict``) falls back to the existing
rule-based ranking -- unchanged, still the authority of record when the
LLM tier is unavailable or its reply can't be trusted.
"""
import logging
import uuid
from datetime import datetime, timezone

from agro_mirai.persistence.models import CropRecommendation
from agro_mirai.processing.feature_builder import FeatureVector

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = """You are an agronomy assistant recommending a crop for a farm field in India.

Field data:
- Location: latitude {latitude}, longitude {longitude}
- Mean temperature (14d): {temp_c} C
- Rainfall sum (30d): {rainfall_mm} mm
- Estimated annual rainfall: {annual_rain_mm} mm
- Soil type: {soil_type}
- Soil pH: {soil_ph}
- Current crop (if any): {crop_type}
- Current month: {month}

Recommend the single best crop to grow given this data, plus up to 3 alternatives.
Respond with ONLY a JSON object, no other text, matching exactly this shape:
{{"recommended_crop": "<crop name>", "confidence": <0.0-1.0>, "alternatives": ["<crop>", ...], "rationale": "<one or two sentences>"}}"""


def _build_prompt(features: FeatureVector) -> str:
    return _PROMPT_TEMPLATE.format(
        latitude=features.latitude,
        longitude=features.longitude,
        temp_c=features.temp_c_mean_14d,
        rainfall_mm=features.rainfall_mm_sum_30d,
        annual_rain_mm=features.annual_rain_mm_est,
        soil_type=features.soil_type or "unknown",
        soil_ph=features.soil_ph,
        crop_type=features.crop_type or "none",
        month=features.as_of.month if features.as_of else "unknown",
    )


def llm_recommend_crop(features: FeatureVector, top_k: int = 3) -> CropRecommendation | None:
    """Returns a ``CropRecommendation`` (``source="llm"``) synthesized by
    the LLM tier, or ``None`` on any failure -- never raises."""
    from agro_mirai.api.gemini_client import ask_gemini_structured  # noqa: PLC0415

    try:
        data = ask_gemini_structured(_build_prompt(features))
    except Exception as exc:  # a tier must never raise
        logger.warning("Crop LLM tier field=%s: unexpected error: %s", features.field_id, exc)
        return None
    if data is None:
        return None

    from agro_mirai.models import ecocrop  # noqa: PLC0415

    known_crops = ecocrop.table()
    try:
        recommended_crop = str(data["recommended_crop"]).strip().lower()
        if recommended_crop not in known_crops:
            # schema's recommended_crop is an enum (specs/core/schema.yaml) -- an
            # LLM reply naming a crop outside our known 22 can't be returned as-is.
            raise ValueError(f"recommended_crop {recommended_crop!r} is not a known crop_type")
        confidence = float(data["confidence"])
        alternatives = [
            a for a in (str(x).strip().lower() for x in (data.get("alternatives") or []))
            if a in known_crops
        ][:top_k]
        rationale = str(data.get("rationale") or "") or None
    except (KeyError, TypeError, ValueError) as exc:
        logger.warning("Crop LLM tier field=%s: malformed response: %s", features.field_id, exc)
        return None

    return CropRecommendation(
        id=str(uuid.uuid4()),
        field_id=features.field_id,
        created_at=datetime.now(timezone.utc),
        recommended_crop=recommended_crop,
        confidence=confidence,
        alternatives=alternatives or None,
        rationale=rationale,
        season=features.season,
        source="llm",
    )
