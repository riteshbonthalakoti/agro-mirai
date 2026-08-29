"""``/v2/admin`` — read-only Admin dashboard API (Module 19).

Every route here is a GET. There are deliberately no POST/PUT/PATCH/
DELETE routes in this blueprint at all — per the decided scope
(read-only: list farmers/fields, system-wide feedback aggregates, no
threshold/model-control routes) — see decisions/0017-multi-tenant-v2.md.
``tests/api/test_admin_routes.py`` asserts this by inspecting
``app.url_map`` rather than trusting this docstring.
"""
from __future__ import annotations

import dataclasses

from flask import Blueprint, current_app, jsonify

from agro_mirai.api.serializers import farmer_to_public_json, to_json
from agro_mirai.api.session_auth import require_admin
from agro_mirai.feedback.aggregator import FeedbackAggregator

admin_bp = Blueprint("admin", __name__, url_prefix="/v2/admin")


@admin_bp.get("/farmers")
@require_admin
def list_farmers():
    store = current_app.extensions["data_store"]
    farmers = store.list_all_farmers()
    items = []
    for f in farmers:
        field_count = len(store.list_fields(f.id, limit=1000))
        items.append({**farmer_to_public_json(f), "field_count": field_count})
    return jsonify({"items": items}), 200


@admin_bp.get("/fields")
@require_admin
def list_fields():
    store = current_app.extensions["data_store"]
    fields = store.list_all_fields()
    return jsonify({"items": [to_json(f) for f in fields]}), 200


@admin_bp.get("/feedback")
@require_admin
def feedback_summary():
    store = current_app.extensions["data_store"]
    pairs = store.list_all_feedback_with_advisories()
    report = FeedbackAggregator.aggregate(pairs)
    return jsonify(dataclasses.asdict(report)), 200
