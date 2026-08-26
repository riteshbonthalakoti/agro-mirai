"""Recommendation / irrigation / disease-risk / advisory endpoints.

Each GET here is also the trigger: it builds a fresh ``FeatureVector``
from whatever the store currently holds, runs the relevant model (or the
full ``DecisionEngine`` for advisories), persists the result, and returns
it. There is no separate "generate" endpoint in ``openapi.yaml``, so the
read is what causes the compute.
"""
from __future__ import annotations

from flask import Blueprint, current_app, g, jsonify

from agro_mirai.api.auth import require_auth
from agro_mirai.api.errors import ApiError
from agro_mirai.api.features import build_features_for_field
from agro_mirai.api.serializers import to_json

advisory_bp = Blueprint("advisory", __name__)


def _get_field_or_404(store, field_id: str):
    field = store.get_field(g.farmer_id, field_id)
    if field is None:
        raise ApiError(404, "NOT_FOUND", "Field not found")
    return field


def _features_or_422(store, field):
    try:
        return build_features_for_field(store, g.farmer_id, field)
    except ValueError as exc:
        raise ApiError(422, "NO_WEATHER_DATA", str(exc)) from None


@advisory_bp.get("/fields/<field_id>/recommendation")
@require_auth
def get_recommendation(field_id: str):
    store = current_app.extensions["data_store"]
    field = _get_field_or_404(store, field_id)
    features = _features_or_422(store, field)

    recommendation = current_app.extensions["crop_model"].predict(features)
    saved = store.save_crop_recommendation(g.farmer_id, recommendation)
    return jsonify(to_json(saved)), 200


@advisory_bp.get("/fields/<field_id>/irrigation")
@require_auth
def get_irrigation(field_id: str):
    store = current_app.extensions["data_store"]
    field = _get_field_or_404(store, field_id)
    features = _features_or_422(store, field)

    advice = current_app.extensions["irrigation_model"].predict(features)
    saved = store.save_irrigation_advice(g.farmer_id, advice)
    return jsonify(to_json(saved)), 200


@advisory_bp.get("/fields/<field_id>/disease-risk")
@require_auth
def get_disease_risk(field_id: str):
    store = current_app.extensions["data_store"]
    field = _get_field_or_404(store, field_id)
    features = _features_or_422(store, field)

    alert = current_app.extensions["disease_model"].predict(features)
    store.save_disease_risk_alert(g.farmer_id, alert)

    alerts = store.list_disease_risk_alerts(g.farmer_id, field_id)
    return jsonify({"items": [to_json(a) for a in alerts]}), 200


@advisory_bp.get("/fields/<field_id>/advisories")
@require_auth
def get_advisories(field_id: str):
    store = current_app.extensions["data_store"]
    field = _get_field_or_404(store, field_id)
    features = _features_or_422(store, field)

    advisory = current_app.extensions["decision_engine"].recommend(field, features)
    store.save_advisory(g.farmer_id, advisory)

    advisories = store.list_advisories_for_field(g.farmer_id, field_id)
    return jsonify({"items": [to_json(a) for a in advisories]}), 200
