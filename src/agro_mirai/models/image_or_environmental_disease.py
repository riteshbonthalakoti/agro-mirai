"""Chooses the vision-LLM / CNN / environmental (rule-based) disease-risk
path for a single call, with the hard fallback-to-environmental
requirement (Module 21): if a photo was submitted but every image tier is
unreachable, times out, or errors, this NEVER raises — it returns a
schema-valid ``DiseaseRiskAlert`` from the rule-based model instead,
tagged ``source="environmental_fallback"``.

Shared by both the API route (``api/routes/disease_image.py``) and
``DecisionEngine.recommend``'s optional image path, so the choice logic
lives in exactly one place — see ``decisions/0019-deployment-architecture.md``
and ``decisions/0018-disease-cnn.md``'s "additive, not integrated into
DecisionEngine yet" section, which this module closes.

AI cascade restructure (scratch/restructure-plan.md): added a vision-LLM
tier ahead of the CNN call, for the same reliability reason the weather
acquisition layer already tries several sources before falling back
(``acquisition/weather_fallbacks.py``) -- a second, independent read on
the image before relying on a single model. The vision tier is tried
first; the CNN call (and, below that, the rule-based model) is the
existing fallback chain, unchanged.
"""
import dataclasses
import logging
from typing import Callable

from agro_mirai.persistence.models import DiseaseRiskAlert
from agro_mirai.processing.feature_builder import FeatureVector

logger = logging.getLogger(__name__)

CnnCaller = Callable[[bytes, str], dict | None]

_VISION_PROMPT = (
    "You are looking at a photo of a crop leaf or plant. Identify the crop "
    "and any visible disease. Respond with ONLY a JSON object, no other "
    "text, matching exactly this shape: "
    '{"crop": "<crop name or null>", "disease": "<disease name, or '
    '\\"healthy\\" if none visible>", "risk_level": "<low|moderate|high|severe>", '
    '"confidence": <0.0-1.0>, "recommended_action": "<one short sentence>"}'
)


def _try_vision_llm_tier(image_bytes: bytes, field_id: str) -> DiseaseRiskAlert | None:
    """New tier 1: ask a vision LLM to read the photo directly. Returns
    ``None`` on any failure (no key configured, network error, non-JSON
    reply, missing required fields) so the caller falls through to the
    existing CNN tier -- never raises, matches every other tier's
    never-raise contract in this cascade."""
    from agro_mirai.api.gemini_client import ask_gemini_vision  # noqa: PLC0415

    try:
        text = ask_gemini_vision(image_bytes, _VISION_PROMPT)
    except Exception as exc:  # belt-and-suspenders: a tier must never raise
        logger.warning("Vision LLM tier field=%s: unexpected error: %s", field_id, exc)
        return None
    if text is None:
        return None

    import json
    from datetime import datetime, timezone
    import uuid

    try:
        data = json.loads(text)
        risk_level = data["risk_level"]
        if risk_level not in ("low", "moderate", "high", "severe"):
            raise ValueError(f"unexpected risk_level: {risk_level!r}")
        return DiseaseRiskAlert(
            id=str(uuid.uuid4()),
            field_id=field_id,
            created_at=datetime.now(timezone.utc),
            disease=str(data.get("disease") or "unknown"),
            risk_level=risk_level,
            confidence=float(data["confidence"]),
            recommended_action=data.get("recommended_action"),
            source="vision_llm",
        )
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        logger.warning("Vision LLM tier field=%s: malformed response: %s", field_id, exc)
        return None


def resolve_disease_alert(
    disease_model,
    features: FeatureVector,
    field_id: str,
    image_bytes: bytes | None = None,
    cnn_caller: CnnCaller | None = None,
    crop_type: str | None = None,
) -> DiseaseRiskAlert:
    """Returns a ``DiseaseRiskAlert`` for ``field_id``.

    - No ``image_bytes``: calls the rule-based ``disease_model`` directly,
      tagged ``source="environmental"``.
    - ``image_bytes`` given: tries the vision-LLM tier first
      (``source="vision_llm"`` on success), then the CNN service call
      (via ``cnn_caller``, defaults to
      ``agro_mirai.api.cnn_client.call_cnn_service``, ``source="cnn"`` on
      success), falling back to the rule-based model
      (``source="environmental_fallback"``) if every image tier fails —
      the hard requirement that this path never 500s.
    """
    if image_bytes is None:
        alert = disease_model.predict(features)
        return dataclasses.replace(alert, source="environmental")

    vision_alert = _try_vision_llm_tier(image_bytes, field_id)
    if vision_alert is not None:
        logger.info("disease_cascade field=%s tier=1 provider=vision_llm", field_id)
        return vision_alert

    if cnn_caller is None:
        from agro_mirai.api.cnn_client import call_cnn_service as cnn_caller  # noqa: PLC0415

    try:
        cnn_result = cnn_caller(image_bytes, field_id, crop_type=crop_type) if crop_type else cnn_caller(image_bytes, field_id)
    except TypeError:  # a caller that predates the crop hint
        cnn_result = cnn_caller(image_bytes, field_id)
    if cnn_result is not None:
        try:
            alert = _alert_from_cnn_json(cnn_result)
            logger.info("disease_cascade field=%s tier=2 provider=cnn", field_id)
            return alert
        except (KeyError, TypeError, ValueError):
            pass  # malformed response from the service — fall through to fallback

    alert = disease_model.predict(features)
    logger.info("disease_cascade field=%s tier=3 provider=rule_based", field_id)
    return dataclasses.replace(alert, source="environmental_fallback")


def _alert_from_cnn_json(data: dict) -> DiseaseRiskAlert:
    from datetime import datetime

    def _parse(value):
        if value is None:
            return None
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")

    return DiseaseRiskAlert(
        id=data["id"],
        field_id=data["field_id"],
        created_at=_parse(data["created_at"]),
        disease=data["disease"],
        risk_level=data["risk_level"],
        confidence=data["confidence"],
        window_start_at=_parse(data.get("window_start_at")),
        window_end_at=_parse(data.get("window_end_at")),
        recommended_action=data.get("recommended_action"),
        source="cnn",
    )
