"""``POST /feedback`` — stores a farmer's rating of an ``Advisory``.

The route is fully wired against ``DataStore.save_feedback_entry``; Module
13 (Feedback Loop) is expected to build the aggregation/analysis logic on
top of what's persisted here, not to fill in a stub route.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from flask import Blueprint, current_app, g, jsonify, request

from agro_mirai.api.auth import require_auth
from agro_mirai.api.errors import ApiError
from agro_mirai.api.serializers import to_json
from agro_mirai.api.validation import validate_feedback_create
from agro_mirai.persistence.models import FeedbackEntry

feedback_bp = Blueprint("feedback", __name__)

_REQUIRED_KEYS = ("advisory_id", "rating", "helpful")


@feedback_bp.post("/feedback")
@require_auth
def submit_feedback():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError(400, "BAD_REQUEST", "Request body must be a JSON object")

    missing = [k for k in _REQUIRED_KEYS if k not in body]
    if missing:
        raise ApiError(400, "BAD_REQUEST", f"Missing required fields: {', '.join(missing)}")
    validate_feedback_create(body)
    rating = body["rating"]

    store = current_app.extensions["data_store"]
    advisory = store.get_advisory(g.farmer_id, body["advisory_id"])
    if advisory is None:
        raise ApiError(404, "NOT_FOUND", "Advisory not found")

    entry = FeedbackEntry(
        id=str(uuid.uuid4()),
        farmer_id=g.farmer_id,
        advisory_id=body["advisory_id"],
        created_at=datetime.now(timezone.utc),
        rating=rating,
        helpful=bool(body["helpful"]),
        comment=body.get("comment"),
    )
    saved = store.save_feedback_entry(g.farmer_id, entry)
    return jsonify(to_json(saved)), 201
