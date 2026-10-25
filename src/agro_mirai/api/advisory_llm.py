"""LLM-first tier for the farmer-facing Advisory (AI cascade restructure,
scratch/restructure-plan.md): asks a free-tier LLM to synthesize a single
advisory from the same live weather/soil/NDVI/location data the existing
``DecisionEngine`` compositor (``models/decision_engine.py``) already has,
as a second opinion ahead of it.

Mirrors every other client in this project's never-raise contract:
``llm_recommend_advisory`` returns ``None`` on any failure (no key
configured, network error, malformed/incomplete JSON reply) so the caller
(``DecisionEngine.recommend``) falls back to the existing rule-based
compositor -- unchanged, still the authority of record when the LLM tier
is unavailable or its reply can't be trusted.
"""
import logging
import uuid
from datetime import datetime, timezone

from agro_mirai.persistence.models import Advisory
from agro_mirai.processing.feature_builder import FeatureVector

logger = logging.getLogger(__name__)

_VALID_SEVERITIES = {"low", "moderate", "high", "severe"}

_PROMPT_TEMPLATE = """You are an agronomy assistant writing a short advisory for a farmer in India.

Field data:
- Location: latitude {latitude}, longitude {longitude}
- Mean temperature (14d): {temp_c} C
- Rainfall sum (30d): {rainfall_mm} mm
- Soil type: {soil_type}, soil pH: {soil_ph}
- Current crop (if any): {crop_type}
- NDVI (satellite greenness, if available): {ndvi}
- Current month: {month}

Write a short, practical advisory (crop choice, irrigation, and disease risk if relevant)
for this field. Respond with ONLY a JSON object, no other text, matching exactly this shape:
{{"title": "<short title>", "body": "<2-4 sentences of practical advice>", "severity": "<low|moderate|high|severe>"}}"""


def _build_prompt(features: FeatureVector) -> str:
    return _PROMPT_TEMPLATE.format(
        latitude=features.latitude,
        longitude=features.longitude,
        temp_c=features.temp_c_mean_14d,
        rainfall_mm=features.rainfall_mm_sum_30d,
        soil_type=features.soil_type or "unknown",
        soil_ph=features.soil_ph,
        crop_type=features.crop_type or "none",
        ndvi=features.ndvi_latest if features.ndvi_data_available else "unavailable",
        month=features.as_of.month if features.as_of else "unknown",
    )


def llm_recommend_advisory(features: FeatureVector) -> Advisory | None:
    """Returns an ``Advisory`` (``source="llm"``) synthesized by the LLM
    tier, or ``None`` on any failure -- never raises."""
    from agro_mirai.api.gemini_client import ask_gemini_structured  # noqa: PLC0415

    try:
        data = ask_gemini_structured(_build_prompt(features))
    except Exception as exc:  # a tier must never raise
        logger.warning("Advisory LLM tier field=%s: unexpected error: %s", features.field_id, exc)
        return None
    if data is None:
        return None

    try:
        title = str(data["title"]).strip()
        body = str(data["body"]).strip()
        severity = str(data["severity"]).strip().lower()
        if not title or not body:
            raise ValueError("empty title or body")
        if severity not in _VALID_SEVERITIES:
            raise ValueError(f"unexpected severity: {severity!r}")
    except (KeyError, TypeError, ValueError) as exc:
        logger.warning("Advisory LLM tier field=%s: malformed response: %s", features.field_id, exc)
        return None

    return Advisory(
        id=str(uuid.uuid4()),
        field_id=features.field_id,
        created_at=datetime.now(timezone.utc),
        language="en",
        title=title,
        body=body,
        severity=severity,
        source="llm",
    )
