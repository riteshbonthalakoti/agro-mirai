"""``POST /fields/{field_id}/disease-risk/image`` (Module 21).

Closes the real gap ADR 0018 left open: an image-upload path that calls
the standalone CNN inference service (``services/cnn-inference``) over
HTTP, falling back to the existing rule-based ``DiseaseRiskModel`` if the
CNN service is unreachable, times out, or errors — a hard requirement,
never a 500. See ``image_or_environmental_disease.resolve_disease_alert``
for the shared choice logic (also used by ``DecisionEngine.recommend``'s
optional ``image_bytes`` parameter).
"""
from __future__ import annotations

from flask import Blueprint, current_app, g, jsonify, request

from agro_mirai.api.auth import require_auth
from agro_mirai.api.errors import ApiError
from agro_mirai.api.features import build_features_for_field
from agro_mirai.api.image_validation import validate_image_upload
from agro_mirai.api.serializers import to_json
from agro_mirai.models.image_or_environmental_disease import resolve_disease_alert

disease_image_bp = Blueprint("disease_image", __name__)


@disease_image_bp.post("/fields/<field_id>/disease-risk/image")
@require_auth
def post_disease_risk_image(field_id: str):
    store = current_app.extensions["data_store"]
    field = store.get_field(g.farmer_id, field_id)
    if field is None:
        raise ApiError(404, "NOT_FOUND", "Field not found")

    image_bytes = validate_image_upload(request.files.get("image"))

    try:
        features = build_features_for_field(store, g.farmer_id, field)
    except ValueError as exc:
        raise ApiError(422, "NO_WEATHER_DATA", str(exc)) from None

    disease_model = current_app.extensions["disease_model"]
    alert = resolve_disease_alert(disease_model, features, field_id, image_bytes=image_bytes)

    saved = store.save_disease_risk_alert(g.farmer_id, alert)
    return jsonify(to_json(saved)), 200
