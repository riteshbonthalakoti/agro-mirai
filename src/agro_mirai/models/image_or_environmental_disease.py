"""Chooses the image (CNN) vs. environmental (rule-based) disease-risk
path for a single call, with the hard fallback-to-environmental
requirement (Module 21): if a photo was submitted but the CNN service is
unreachable, times out, or errors, this NEVER raises — it returns a
schema-valid ``DiseaseRiskAlert`` from the rule-based model instead,
tagged ``source="environmental_fallback"``.

Shared by both the API route (``api/routes/disease_image.py``) and
``DecisionEngine.recommend``'s optional image path, so the choice logic
lives in exactly one place — see ``decisions/0019-deployment-architecture.md``
and ``decisions/0018-disease-cnn.md``'s "additive, not integrated into
DecisionEngine yet" section, which this module closes.
"""
from __future__ import annotations

import dataclasses
from typing import Callable

from agro_mirai.persistence.models import DiseaseRiskAlert
from agro_mirai.processing.feature_builder import FeatureVector

CnnCaller = Callable[[bytes, str], dict | None]


def resolve_disease_alert(
    disease_model,
    features: FeatureVector,
    field_id: str,
    image_bytes: bytes | None = None,
    cnn_caller: CnnCaller | None = None,
) -> DiseaseRiskAlert:
    """Returns a ``DiseaseRiskAlert`` for ``field_id``.

    - No ``image_bytes``: calls the rule-based ``disease_model`` directly,
      tagged ``source="environmental"``.
    - ``image_bytes`` given and the CNN service call (via ``cnn_caller``,
      defaults to ``agro_mirai.api.cnn_client.call_cnn_service``) succeeds:
      returns a ``DiseaseRiskAlert`` built from that response, tagged
      ``source="cnn"``.
    - ``image_bytes`` given but the CNN call fails/times out/is
      unreachable (``cnn_caller`` returns ``None``): falls back to the
      rule-based model, tagged ``source="environmental_fallback"`` — the
      hard requirement that this path never 500s.
    """
    if image_bytes is None:
        alert = disease_model.predict(features)
        return dataclasses.replace(alert, source="environmental")

    if cnn_caller is None:
        from agro_mirai.api.cnn_client import call_cnn_service as cnn_caller  # noqa: PLC0415

    cnn_result = cnn_caller(image_bytes, field_id)
    if cnn_result is not None:
        try:
            return _alert_from_cnn_json(cnn_result)
        except (KeyError, TypeError, ValueError):
            pass  # malformed response from the service — fall through to fallback

    alert = disease_model.predict(features)
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
