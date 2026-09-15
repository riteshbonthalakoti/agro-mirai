"""``/v2/farmers/me`` and ``/v2/fields`` — session-scoped equivalents of
``routes/farms.py`` (Module 19).

Same semantics as the /v1 endpoints, but authenticated via
``session_auth.require_session_auth`` (a real per-farmer login session)
instead of the single shared ``API_KEY``/``FARMER_ID`` — this is where
ADR 0003's ownership rule gets enforced per-farmer for real. Deliberately
NOT registered under the /v1 prefix per decisions/0017-multi-tenant-v2.md.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from flask import Blueprint, current_app, g, jsonify, request

from agro_mirai.api.errors import ApiError
from agro_mirai.api.serializers import farmer_to_public_json, to_json
from agro_mirai.api.session_auth import require_session_auth
from agro_mirai.api.validation import validate_field_create, validate_field_update
from agro_mirai.auth.validation import validate_name
from agro_mirai.persistence.models import Field_, Farmer
from agro_mirai.voice.interface import V1_LANGUAGES

farms_v2_bp = Blueprint("farms_v2", __name__, url_prefix="/v2")

_REQUIRED_FIELD_KEYS = ("name", "latitude", "longitude", "area_ha")


#: Module 25: was a locally-duplicated {"en", "kn"} that had silently
#: drifted stale from V1_LANGUAGES — now the single source of truth
#: instead of a second hardcoded copy.
_ALLOWED_LANGUAGE_CODES = V1_LANGUAGES


@farms_v2_bp.get("/farmers/me")
@require_session_auth
def get_me():
    store = current_app.extensions["data_store"]
    farmer = store.get_farmer(g.farmer_id)
    if farmer is None:
        raise ApiError(404, "NOT_FOUND", "Farmer not found")
    return jsonify(farmer_to_public_json(farmer)), 200


@farms_v2_bp.patch("/farmers/me")
@require_session_auth
def update_me():
    """Allow farmers to update their display name and preferred language.

    Only ``name`` and ``preferred_language`` are mutable post-registration
    (email and password changes are out of scope for v1 — noted in ADR 0017's
    known limitations). At least one key must be present.
    """
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError(400, "BAD_REQUEST", "Request body must be a JSON object")

    allowed_keys = {"name", "preferred_language", "photo_url"}
    unknown = set(body) - allowed_keys
    if unknown:
        raise ApiError(400, "BAD_REQUEST", f"Unknown fields: {', '.join(sorted(unknown))}")
    if not body:
        raise ApiError(400, "BAD_REQUEST", "Request body must contain at least one field")

    store = current_app.extensions["data_store"]
    farmer = store.get_farmer(g.farmer_id)
    if farmer is None:
        raise ApiError(404, "NOT_FOUND", "Farmer not found")

    new_name = body.get("name", farmer.name)
    new_lang = body.get("preferred_language", farmer.preferred_language)
    new_photo_url = body.get("photo_url", farmer.photo_url)

    if "name" in body:
        try:
            validate_name(new_name)
        except ValueError as e:
            raise ApiError(400, "BAD_REQUEST", str(e)) from e

    if "preferred_language" in body and new_lang not in _ALLOWED_LANGUAGE_CODES:
        raise ApiError(
            400,
            "BAD_REQUEST",
            f"preferred_language must be one of: {', '.join(sorted(_ALLOWED_LANGUAGE_CODES))}",
        )

    updated = Farmer(
        id=farmer.id,
        created_at=farmer.created_at,
        updated_at=datetime.now(timezone.utc),
        name=new_name,
        preferred_language=new_lang,
        # Real bug found live: this reconstruction previously dropped
        # phone/district/state entirely, so every profile update silently
        # wiped the farmer's phone number -- breaking their ability to log
        # back in via OTP (login is phone-based). Carry them over.
        phone=farmer.phone,
        district=farmer.district,
        state=farmer.state,
        email=farmer.email,
        password_hash=farmer.password_hash,
        role=farmer.role,
        photo_url=new_photo_url,
    )
    saved = store.save_farmer(updated)
    return jsonify(farmer_to_public_json(saved)), 200


@farms_v2_bp.get("/fields")
@require_session_auth
def list_fields():
    store = current_app.extensions["data_store"]
    fields = store.list_fields(g.farmer_id)
    return jsonify({"items": [to_json(f) for f in fields]}), 200


@farms_v2_bp.post("/fields")
@require_session_auth
def create_field():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError(400, "BAD_REQUEST", "Request body must be a JSON object")

    missing = [k for k in _REQUIRED_FIELD_KEYS if k not in body]
    if missing:
        raise ApiError(400, "BAD_REQUEST", f"Missing required fields: {', '.join(missing)}")
    validate_field_create(body)

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


@farms_v2_bp.get("/fields/<field_id>")
@require_session_auth
def get_field(field_id: str):
    store = current_app.extensions["data_store"]
    field = store.get_field(g.farmer_id, field_id)
    if field is None:
        raise ApiError(404, "NOT_FOUND", "Field not found")
    return jsonify(to_json(field)), 200


@farms_v2_bp.delete("/fields/<field_id>")
@require_session_auth
def delete_field(field_id: str):
    """Remove a Field the farmer owns, along with all linked data (advisories,
    soil samples, weather readings, etc. — ON DELETE CASCADE in the migration).
    Returns 204 on success, 404 if not found or not owned by this farmer.
    """
    store = current_app.extensions["data_store"]
    deleted = store.delete_field(g.farmer_id, field_id)
    if not deleted:
        raise ApiError(404, "NOT_FOUND", "Field not found")
    from flask import make_response
    return make_response("", 204)


@farms_v2_bp.patch("/fields/<field_id>")
@require_session_auth
def update_field(field_id: str):
    """Module 23 (A5): the mobile app needs to edit a field it already
    created (change ``current_crop`` at re-sowing, correct ``sown_on``,
    etc.) — decided to add this now rather than let it surface as a third
    mid-UI-build blocker the way A/B were found. Partial update
    (``PATCH``, not ``PUT``): only the keys present in the body are
    changed. ``/v1`` deliberately does NOT get this route — it stays
    frozen per ADR 0017, and no ``/v1`` caller has ever needed field
    mutation.
    """
    store = current_app.extensions["data_store"]
    field = store.get_field(g.farmer_id, field_id)
    if field is None:
        raise ApiError(404, "NOT_FOUND", "Field not found")

    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError(400, "BAD_REQUEST", "Request body must be a JSON object")
    validate_field_update(body)

    sown_on = body["sown_on"] if "sown_on" in body else (field.sown_on.isoformat() if field.sown_on else None)
    updated = Field_(
        id=field.id,
        farmer_id=field.farmer_id,
        created_at=field.created_at,
        updated_at=datetime.now(timezone.utc),
        name=body.get("name", field.name),
        latitude=body.get("latitude", field.latitude),
        longitude=body.get("longitude", field.longitude),
        area_ha=body.get("area_ha", field.area_ha),
        elevation_m=body.get("elevation_m", field.elevation_m),
        soil_type=body.get("soil_type", field.soil_type),
        current_crop=body.get("current_crop", field.current_crop),
        sown_on=date.fromisoformat(sown_on) if sown_on else None,
    )
    saved = store.save_field(g.farmer_id, updated)
    return jsonify(to_json(saved)), 200
