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
from agro_mirai.api.field_data_acquisition import acquire_field_data
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


def _status_word(done):
    return "gathering" if done is None else "ready" if done else "unavailable"


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

    # Module 34 follow-up 2: pull real weather/soil (sync, ~5s combined
    # measured) and real NDVI (background thread, GEE latency measured
    # close to its own 20s timeout) for the field just created. Any
    # individual adapter failure is caught inside acquire_field_data and
    # never blocks this 201 response — degrade-not-fail per source.
    data_status = acquire_field_data(
        store, g.farmer_id, saved.id, saved.latitude, saved.longitude
    )

    response = to_json(saved)
    response["data_acquisition"] = {
        "weather": _status_word(data_status["weather"]),
        "soil": _status_word(data_status["soil"]),
        # NDVI is always still in flight at response time by design —
        # the mobile client must not imply it is ready yet.
        "ndvi": "gathering",
    }
    return jsonify(response), 201


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


@farms_v2_bp.post("/fields/<field_id>/refresh-data")
@require_session_auth
def refresh_field_data(field_id: str):
    """Module 34 follow-up 2: manual re-pull of real weather/soil/NDVI for
    a field that already exists (data ages, or a field created before this
    module shipped has none at all). Same auth scoping and degrade-not-fail
    rules as field creation's own acquisition call.

    Deliberately NOT a scheduler — there is no cron/Celery/task-queue
    infrastructure anywhere in this project (checked `tools/`,
    `docs/deploy/`, `render.yaml`, `docker-compose.yml`: none found), and
    building one is out of scope for this pass. This manual-trigger
    endpoint is the intentional MVP; automatic periodic refresh is a real,
    open follow-on, not something this module pretends to solve.
    """
    store = current_app.extensions["data_store"]
    field = store.get_field(g.farmer_id, field_id)
    if field is None:
        raise ApiError(404, "NOT_FOUND", "Field not found")

    data_status = acquire_field_data(
        store, g.farmer_id, field.id, field.latitude, field.longitude
    )
    return jsonify(
        {
            "field_id": field.id,
            "data_acquisition": {
                "weather": _status_word(data_status["weather"]),
                "soil": _status_word(data_status["soil"]),
                "ndvi": "gathering",
            },
        }
    ), 202


@farms_v2_bp.get("/fields/<field_id>/data-summary")
@require_session_auth
def field_data_summary(field_id: str):
    """Module 39: read-only view of the real weather / soil / NDVI rows the
    acquisition adapters already persist for a field (see
    ``field_data_acquisition``). Before this route, the mobile app had no
    way to *show* any of that data -- it was written to the store and only
    ever consumed inside the models. Additive: nothing existing changes.
    Ownership uses the store's farmer-scoped ``get_field`` -> 404 (not 403)
    for another farmer's field, same as every other /v2 route.

    ``weather.current`` is the newest observed (non-forecast) reading;
    ``weather.forecast`` is up to 7 upcoming forecast rows, soonest first.
    ``soil`` / ``ndvi.latest`` are ``null`` when that source has produced
    nothing yet (NDVI is fetched in a background thread after field
    creation, so ``null`` there can mean "still gathering").
    """
    store = current_app.extensions["data_store"]
    field = store.get_field(g.farmer_id, field_id)
    if field is None:
        raise ApiError(404, "NOT_FOUND", "Field not found")

    from agro_mirai.processing.weather_series import one_row_per_day

    weather = store.list_weather_readings(g.farmer_id, field.id, limit=400)
    observed = sorted((w for w in weather if not w.is_forecast), key=lambda w: w.observed_at)
    now = datetime.now(timezone.utc)
    # one row per calendar day: repeated refreshes used to list the same forecast day several times
    upcoming = sorted(
        one_row_per_day(
            [w for w in weather if w.is_forecast and w.observed_at.date() >= now.date()]
        ).values(),
        key=lambda w: w.observed_at,
    )
    observed_days = sorted(one_row_per_day(observed).values(), key=lambda w: w.observed_at)
    soil = store.list_soil_samples(g.farmer_id, field.id, limit=20)
    latest_soil = max(soil, key=lambda s: s.observed_at) if soil else None
    ndvi = sorted(
        store.list_ndvi_readings(g.farmer_id, field.id, limit=50),
        key=lambda n: n.observed_at,
        reverse=True,
    )

    # What the models actually use for soil (real SoilGrids values with typical
    # values for the field's soil type filling only the gaps -- SoilGrids has no
    # phosphorus/potassium/moisture), so the app can show it and label it.
    soil_used = None
    try:
        from agro_mirai.api.features import build_features_for_field

        fv = build_features_for_field(store, g.farmer_id, field)
        if fv.soil_data_available:
            soil_used = {
                "ph": fv.soil_ph,
                "nitrogen_mg_per_kg": fv.soil_nitrogen_mg_per_kg,
                "phosphorus_mg_per_kg": fv.soil_phosphorus_mg_per_kg,
                "potassium_mg_per_kg": fv.soil_potassium_mg_per_kg,
                "organic_carbon_pct": fv.soil_organic_carbon_pct,
                "moisture_pct": fv.soil_moisture_pct,
                "chemistry_source": fv.soil_chemistry_source,
                "moisture_source": fv.soil_moisture_source,
            }
    except Exception:  # noqa: BLE001 - display extra, never blocks the summary
        soil_used = None

    return jsonify(
        {
            "field_id": field.id,
            "fetched_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "soil_used": soil_used,
            "weather": {
                "current": to_json(observed[-1]) if observed else None,
                "recent": [to_json(w) for w in observed_days[-7:]],
                "forecast": [to_json(w) for w in upcoming[:7]],
            },
            "soil": to_json(latest_soil) if latest_soil else None,
            "ndvi": {
                "latest": to_json(ndvi[0]) if ndvi else None,
                "history": [to_json(n) for n in ndvi[:10]],
            },
        }
    ), 200
