"""``/v2`` value endpoints — recommendation/irrigation/disease-risk/
disease-risk-image/advisories/feedback, session-authenticated (Module 23,
Blocker A). Same semantics as the ``/v1`` copies in ``routes/advisory.py``/
``feedback.py``/``disease_image.py``, both calling into
``value_endpoints.py`` so the two surfaces cannot drift — see that
module's docstring and decisions/0020-v2-value-endpoints-and-voice-api.md.

Ownership is enforced the same way Module 19 established for
``/v2/fields``: ``store.get_field(farmer_id, field_id)``/
``store.get_advisory(farmer_id, advisory_id)`` are farmer-scoped, so a
field or advisory that exists but belongs to a different farmer returns
404 (via ``value_endpoints.get_field_or_404`` /
``DataStore.get_advisory``), never a 403 or a leak — see
``tests/api/test_v2_value_endpoints.py`` for the cross-tenant proof on
every one of these six routes individually (the blind spot that let
Blocker A ship unnoticed: the existing
``test_full_cross_tenant_isolation_flow`` only ever exercised
``/v2/fields``).
"""
from __future__ import annotations

from flask import Blueprint, current_app, g, jsonify, request

from agro_mirai.api import value_endpoints
from agro_mirai.api.session_auth import require_session_auth

value_v2_bp = Blueprint("value_v2", __name__, url_prefix="/v2")


@value_v2_bp.get("/fields/<field_id>/recommendation")
@require_session_auth
def get_recommendation(field_id: str):
    store = current_app.extensions["data_store"]
    body = value_endpoints.compute_recommendation(store, current_app.extensions, g.farmer_id, field_id)
    return jsonify(body), 200


@value_v2_bp.get("/fields/<field_id>/irrigation")
@require_session_auth
def get_irrigation(field_id: str):
    store = current_app.extensions["data_store"]
    body = value_endpoints.compute_irrigation(store, current_app.extensions, g.farmer_id, field_id)
    return jsonify(body), 200


@value_v2_bp.get("/fields/<field_id>/disease-risk")
@require_session_auth
def get_disease_risk(field_id: str):
    store = current_app.extensions["data_store"]
    target_lang = value_endpoints.resolve_disease_target_lang(
        store, g.farmer_id, request.args.get("language")
    )
    body = value_endpoints.compute_disease_risk(
        store, current_app.extensions, g.farmer_id, field_id, target_lang
    )
    return jsonify(body), 200


@value_v2_bp.post("/fields/<field_id>/disease-risk/image")
@require_session_auth
def post_disease_risk_image(field_id: str):
    store = current_app.extensions["data_store"]
    target_lang = value_endpoints.resolve_disease_target_lang(
        store, g.farmer_id, request.args.get("language")
    )
    body = value_endpoints.compute_disease_risk_image(
        store, current_app.extensions, g.farmer_id, field_id, request.files.get("image"), target_lang
    )
    return jsonify(body), 200


@value_v2_bp.get("/fields/<field_id>/advisories")
@require_session_auth
def get_advisories(field_id: str):
    store = current_app.extensions["data_store"]
    body = value_endpoints.compute_advisories(store, current_app.extensions, g.farmer_id, field_id)
    return jsonify(body), 200


@value_v2_bp.post("/feedback")
@require_session_auth
def submit_feedback():
    store = current_app.extensions["data_store"]
    body = request.get_json(silent=True)
    saved = value_endpoints.submit_feedback(store, g.farmer_id, body)
    return jsonify(saved), 201


@value_v2_bp.post("/bug-reports")
@require_session_auth
def submit_bug_report():
    """Farmer-facing "what went wrong" report from the mobile app's
    Settings screen -- see value_endpoints.submit_bug_report for the
    validation rules and decisions note on why this is a new record
    instead of a bend of the existing /feedback contract."""
    store = current_app.extensions["data_store"]
    body = request.get_json(silent=True)
    saved = value_endpoints.submit_bug_report(store, g.farmer_id, body)
    return jsonify(saved), 201
