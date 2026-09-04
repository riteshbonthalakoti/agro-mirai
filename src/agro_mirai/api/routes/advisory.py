"""Recommendation / irrigation / disease-risk / advisory endpoints
(``/v1``, shared-``API_KEY`` auth — see ``routes/value_v2.py`` for the
session-authenticated ``/v2`` copies).

Each GET here is also the trigger: it builds a fresh ``FeatureVector``
from whatever the store currently holds, runs the relevant model (or the
full ``DecisionEngine`` for advisories), persists the result, and returns
it. There is no separate "generate" endpoint in ``openapi.yaml``, so the
read is what causes the compute.

Module 23: the actual handler bodies moved to ``value_endpoints.py`` so
``/v1`` and ``/v2`` share one implementation instead of two that could
drift — these routes are now thin wrappers differing from their ``/v2``
counterparts only in the auth decorator and URL prefix.
"""
from __future__ import annotations

from flask import Blueprint, current_app, g, jsonify

from agro_mirai.api import value_endpoints
from agro_mirai.api.auth import require_auth

advisory_bp = Blueprint("advisory", __name__)


@advisory_bp.get("/fields/<field_id>/recommendation")
@require_auth
def get_recommendation(field_id: str):
    store = current_app.extensions["data_store"]
    body = value_endpoints.compute_recommendation(store, current_app.extensions, g.farmer_id, field_id)
    return jsonify(body), 200


@advisory_bp.get("/fields/<field_id>/irrigation")
@require_auth
def get_irrigation(field_id: str):
    store = current_app.extensions["data_store"]
    body = value_endpoints.compute_irrigation(store, current_app.extensions, g.farmer_id, field_id)
    return jsonify(body), 200


@advisory_bp.get("/fields/<field_id>/disease-risk")
@require_auth
def get_disease_risk(field_id: str):
    store = current_app.extensions["data_store"]
    body = value_endpoints.compute_disease_risk(store, current_app.extensions, g.farmer_id, field_id)
    return jsonify(body), 200


@advisory_bp.get("/fields/<field_id>/advisories")
@require_auth
def get_advisories(field_id: str):
    store = current_app.extensions["data_store"]
    body = value_endpoints.compute_advisories(store, current_app.extensions, g.farmer_id, field_id)
    return jsonify(body), 200
