"""``POST /feedback`` — stores a farmer's rating of an ``Advisory``
(``/v1``, shared-``API_KEY`` auth — see ``routes/value_v2.py`` for the
session-authenticated ``/v2`` copy).

Module 23: handler body moved to ``value_endpoints.submit_feedback`` so
``/v1`` and ``/v2`` share one implementation.
"""
from __future__ import annotations

from flask import Blueprint, current_app, g, jsonify, request

from agro_mirai.api import value_endpoints
from agro_mirai.api.auth import require_auth

feedback_bp = Blueprint("feedback", __name__)


@feedback_bp.post("/feedback")
@require_auth
def submit_feedback():
    store = current_app.extensions["data_store"]
    body = request.get_json(silent=True)
    saved = value_endpoints.submit_feedback(store, g.farmer_id, body)
    return jsonify(saved), 201
