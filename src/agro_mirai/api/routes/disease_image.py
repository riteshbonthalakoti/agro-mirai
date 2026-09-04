"""``POST /fields/{field_id}/disease-risk/image`` (Module 21; ``/v1``,
shared-``API_KEY`` auth — see ``routes/value_v2.py`` for the
session-authenticated ``/v2`` copy).

Closes the real gap ADR 0018 left open: an image-upload path that calls
the standalone CNN inference service (``services/cnn-inference``) over
HTTP, falling back to the existing rule-based ``DiseaseRiskModel`` if the
CNN service is unreachable, times out, or errors — a hard requirement,
never a 500. See ``image_or_environmental_disease.resolve_disease_alert``
for the shared choice logic (also used by ``DecisionEngine.recommend``'s
optional ``image_bytes`` parameter).

Module 23: handler body moved to
``value_endpoints.compute_disease_risk_image`` so ``/v1`` and ``/v2``
share one implementation, including this route's Module 22/21 degrade-
not-fail behaviour (422 on exhausted weather data, ``environmental_fallback``
on an unreachable CNN service).
"""
from __future__ import annotations

from flask import Blueprint, current_app, g, jsonify, request

from agro_mirai.api import value_endpoints
from agro_mirai.api.auth import require_auth

disease_image_bp = Blueprint("disease_image", __name__)


@disease_image_bp.post("/fields/<field_id>/disease-risk/image")
@require_auth
def post_disease_risk_image(field_id: str):
    store = current_app.extensions["data_store"]
    body = value_endpoints.compute_disease_risk_image(
        store, current_app.extensions, g.farmer_id, field_id, request.files.get("image")
    )
    return jsonify(body), 200
