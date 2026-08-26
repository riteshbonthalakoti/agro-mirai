"""``/farmers/me`` and ``/fields`` CRUD."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from flask import Blueprint, current_app, g, jsonify, request

from agro_mirai.api.auth import require_auth
from agro_mirai.api.errors import ApiError
from agro_mirai.api.serializers import to_json
from agro_mirai.persistence.models import Field_

farms_bp = Blueprint("farms", __name__)

_REQUIRED_FIELD_KEYS = ("name", "latitude", "longitude", "area_ha")


@farms_bp.get("/farmers/me")
@require_auth
def get_me():
    store = current_app.extensions["data_store"]
    farmer = store.get_farmer(g.farmer_id)
    if farmer is None:
        raise ApiError(404, "NOT_FOUND", "Farmer not found")
    return jsonify(to_json(farmer)), 200


@farms_bp.get("/fields")
@require_auth
def list_fields():
    store = current_app.extensions["data_store"]
    fields = store.list_fields(g.farmer_id)
    return jsonify({"items": [to_json(f) for f in fields]}), 200


@farms_bp.post("/fields")
@require_auth
def create_field():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError(400, "BAD_REQUEST", "Request body must be a JSON object")

    missing = [k for k in _REQUIRED_FIELD_KEYS if k not in body]
    if missing:
        raise ApiError(400, "BAD_REQUEST", f"Missing required fields: {', '.join(missing)}")

    store = current_app.extensions["data_store"]
    now = datetime.now(timezone.utc)
    sown_on = body.get("sown_on")

    field = Field_(
        id=str(uuid.uuid4()),
        farmer_id=g.farmer_id,
        created_at=now,
        updated_at=now,
        name=body["name"],
        latitude=body["latitude"],
        longitude=body["longitude"],
        area_ha=body["area_ha"],
        elevation_m=body.get("elevation_m"),
        soil_type=body.get("soil_type"),
        current_crop=body.get("current_crop"),
        sown_on=date.fromisoformat(sown_on) if sown_on else None,
    )
    saved = store.save_field(g.farmer_id, field)
    return jsonify(to_json(saved)), 201


@farms_bp.get("/fields/<field_id>")
@require_auth
def get_field(field_id: str):
    store = current_app.extensions["data_store"]
    field = store.get_field(g.farmer_id, field_id)
    if field is None:
        raise ApiError(404, "NOT_FOUND", "Field not found")
    return jsonify(to_json(field)), 200
