"""``/v2/admin`` — Admin dashboard API (Module 19, writes added Module 50).

Every write route here (PATCH/DELETE) is behind @require_admin and logs
an audit_log row via api/audit.write_audit_log -- see
decisions/0030-admin-write-actions.md for why the original read-only
scope (decisions/0017) was superseded.
"""
from __future__ import annotations

import dataclasses
from collections import Counter

from flask import Blueprint, current_app, g, jsonify, request

from agro_mirai.api.audit import write_audit_log
from agro_mirai.api.errors import ApiError
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


_FARMER_PATCHABLE = {"name", "preferred_language", "phone", "district", "state"}


@admin_bp.patch("/farmers/<farmer_id>")
@require_admin
def patch_farmer(farmer_id):
    store = current_app.extensions["data_store"]
    farmer = store.get_farmer(farmer_id)
    if farmer is None:
        raise ApiError(404, "NOT_FOUND", "Farmer not found")
    before = farmer
    body = request.get_json(silent=True) or {}
    updates = {k: v for k, v in body.items() if k in _FARMER_PATCHABLE}
    updated = dataclasses.replace(farmer, **updates)
    saved = store.save_farmer(updated)
    write_audit_log(store, g.farmer_id, "farmer.update", "farmer", farmer_id, before, saved)
    return jsonify(farmer_to_public_json(saved)), 200


@admin_bp.delete("/farmers/<farmer_id>")
@require_admin
def delete_farmer(farmer_id):
    store = current_app.extensions["data_store"]
    farmer = store.get_farmer(farmer_id)
    if farmer is None:
        raise ApiError(404, "NOT_FOUND", "Farmer not found")
    store.delete_farmer(farmer_id)
    write_audit_log(store, g.farmer_id, "farmer.delete", "farmer", farmer_id, farmer, None)
    return jsonify({"deleted": True}), 200


_FIELD_PATCHABLE = {"name", "latitude", "longitude", "area_ha", "elevation_m",
                     "soil_type", "current_crop", "sown_on"}


@admin_bp.patch("/fields/<field_id>")
@require_admin
def patch_field(field_id):
    store = current_app.extensions["data_store"]
    field = store.get_field_by_id(field_id)
    if field is None:
        raise ApiError(404, "NOT_FOUND", "Field not found")
    before = field
    body = request.get_json(silent=True) or {}
    updates = {k: v for k, v in body.items() if k in _FIELD_PATCHABLE}
    updated = dataclasses.replace(field, **updates)
    saved = store.save_field(field.farmer_id, updated)
    write_audit_log(store, g.farmer_id, "field.update", "field", field_id, before, saved)
    return jsonify(to_json(saved)), 200


@admin_bp.delete("/fields/<field_id>")
@require_admin
def delete_field_admin(field_id):
    store = current_app.extensions["data_store"]
    field = store.get_field_by_id(field_id)
    if field is None:
        raise ApiError(404, "NOT_FOUND", "Field not found")
    store.delete_field(field.farmer_id, field_id)
    write_audit_log(store, g.farmer_id, "field.delete", "field", field_id, field, None)
    return jsonify({"deleted": True}), 200


@admin_bp.get("/feedback")
@require_admin
def feedback_summary():
    store = current_app.extensions["data_store"]
    pairs = store.list_all_feedback_with_advisories()
    report = FeedbackAggregator.aggregate(pairs)
    return jsonify(dataclasses.asdict(report)), 200


# Alerts created by an image upload carry one of these sources; the plain
# GET /disease-risk path stores "environmental", so it is not a scan.
_SCAN_SOURCES = {"cnn", "environmental_fallback"}


def _per_field(store, fetch, limit):
    """Yield (field, records) across every farmer's fields. One query per
    field, fine at this project's scale."""
    for field in store.list_all_fields():
        yield field, fetch(field.farmer_id, field.id, limit=limit)


@admin_bp.get("/scans")
@require_admin
def list_scans():
    store = current_app.extensions["data_store"]
    items = []
    for field, alerts in _per_field(store, store.list_disease_risk_alerts, 200):
        for a in alerts:
            if a.source in _SCAN_SOURCES:
                items.append(
                    {**to_json(a), "farmer_id": field.farmer_id, "field_name": field.name}
                )
    items.sort(key=lambda i: i["created_at"], reverse=True)
    return jsonify({"items": items}), 200


@admin_bp.get("/advisories")
@require_admin
def list_advisories():
    store = current_app.extensions["data_store"]
    items = []
    for field, advisories in _per_field(store, store.list_advisories_for_field, 50):
        for a in advisories:
            items.append({**to_json(a), "farmer_id": field.farmer_id, "field_name": field.name})
    items.sort(key=lambda i: i["created_at"], reverse=True)
    return jsonify({"items": items}), 200


def build_overview(store) -> dict:
    """Bird's-eye system summary: totals, language/crop distribution, and
    the most recent activity across every farmer. Shared by the JSON route
    below and ``admin_ui.dashboard`` so both render the same numbers from
    one implementation."""
    farmers = store.list_all_farmers()
    fields = store.list_all_fields()

    language_counts = Counter(f.preferred_language for f in farmers)
    crop_counts = Counter(f.current_crop for f in fields if f.current_crop)

    scan_total = 0
    recent = []
    for field, alerts in _per_field(store, store.list_disease_risk_alerts, 200):
        for a in alerts:
            if a.source in _SCAN_SOURCES:
                scan_total += 1
                recent.append(
                    {
                        "type": "scan",
                        "created_at": a.created_at.isoformat(),
                        "farmer_id": field.farmer_id,
                        "field_name": field.name,
                        "detail": a.disease,
                    }
                )
    for field, advisories in _per_field(store, store.list_advisories_for_field, 50):
        for adv in advisories:
            recent.append(
                {
                    "type": "advisory",
                    "created_at": adv.created_at.isoformat(),
                    "farmer_id": field.farmer_id,
                    "field_name": field.name,
                    "detail": adv.severity,
                }
            )
    recent.sort(key=lambda i: i["created_at"], reverse=True)

    return {
        "total_farmers": len(farmers),
        "total_fields": len(fields),
        "total_scans": scan_total,
        "language_distribution": dict(language_counts),
        "crop_distribution": dict(crop_counts),
        "recent_activity": recent[:20],
    }


@admin_bp.get("/overview")
@require_admin
def overview():
    store = current_app.extensions["data_store"]
    return jsonify(build_overview(store)), 200
