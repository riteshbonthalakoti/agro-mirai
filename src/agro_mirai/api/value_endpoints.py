"""Auth-agnostic handler bodies shared by the /v1 (shared-``API_KEY``) and
/v2 (per-farmer session) route surfaces, Module 23.

Blocker A (see decisions/0020-v2-value-endpoints-and-voice-api.md) was
that every endpoint carrying the product's real value —
recommendation/irrigation/disease-risk/disease-risk-image/advisories/
feedback — existed only under ``/v1``'s single shared ``FARMER_ID``, so a
farmer who registered and logged in via Module 19's ``/v2`` session auth
had no authenticated path to their own advisory. Closing that gap by
copy-pasting the six ``/v1`` handlers into new ``/v2`` ones would
guarantee the two drift — a fix landing in one and not the other is
exactly the failure class Module 22 already cost this project. So the
handler bodies live here, once, taking an explicit ``farmer_id`` instead
of reading ``g.farmer_id`` themselves; ``routes/advisory.py``/
``feedback.py``/``disease_image.py`` (``/v1``, ``require_auth``) and
``routes/value_v2.py`` (``/v2``, ``require_session_auth``) are both thin
wrappers that differ only in their auth decorator and URL prefix, never
in behaviour — including the Module 22 degrade-not-fail contracts (422
on data-exhaustion, ``environmental_fallback`` on an unreachable CNN
service), which both surfaces get "for free" from calling the same code.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from agro_mirai.api.errors import ApiError
from agro_mirai.api.features import build_features_for_field
from agro_mirai.api.image_validation import validate_image_upload
from agro_mirai.api.serializers import to_json
from agro_mirai.api.validation import validate_feedback_create
from agro_mirai.models.image_or_environmental_disease import resolve_disease_alert
from agro_mirai.persistence.models import FeedbackEntry


def get_field_or_404(store, farmer_id: str, field_id: str):
    field = store.get_field(farmer_id, field_id)
    if field is None:
        raise ApiError(404, "NOT_FOUND", "Field not found")
    return field


def features_or_422(store, farmer_id: str, field):
    try:
        return build_features_for_field(store, farmer_id, field)
    except ValueError as exc:
        raise ApiError(422, "NO_WEATHER_DATA", str(exc)) from None


def predict_or_422(fn, *args):
    """Turns the water-balance/scoring ``ValueError``s some models raise
    on genuinely insufficient data (e.g. every temperature window empty)
    into a 422 instead of an uncaught 500 — Module 22's fix, now shared
    by both auth surfaces since both call through here."""
    try:
        return fn(*args)
    except ValueError as exc:
        raise ApiError(422, "INSUFFICIENT_DATA", str(exc)) from None


def compute_recommendation(store, ext: dict, farmer_id: str, field_id: str) -> dict:
    field = get_field_or_404(store, farmer_id, field_id)
    features = features_or_422(store, farmer_id, field)
    recommendation = ext["crop_model"].predict(features)
    saved = store.save_crop_recommendation(farmer_id, recommendation)
    return to_json(saved)


def compute_irrigation(store, ext: dict, farmer_id: str, field_id: str) -> dict:
    field = get_field_or_404(store, farmer_id, field_id)
    features = features_or_422(store, farmer_id, field)
    advice = predict_or_422(ext["irrigation_model"].predict, features)
    saved = store.save_irrigation_advice(farmer_id, advice)
    return to_json(saved)


_DISEASE_RISK_DEDUP_WINDOW = timedelta(hours=1)


def compute_disease_risk(store, ext: dict, farmer_id: str, field_id: str) -> dict:
    """List is real history (openapi.yaml), so recompute-on-read must still
    persist a new alert each call -- but the environmental-proxy scorer
    reruns against the same underlying weather/soil window on every GET, so
    a client that polls this a few times in a row (a dashboard refresh, a
    retry) was getting several near-identical alerts seconds apart with no
    new information in them. Skip the insert when the most recent existing
    alert already says the same thing and is still fresh -- a real change
    in disease/risk_level, or enough time passing, still creates a new row."""
    field = get_field_or_404(store, farmer_id, field_id)
    features = features_or_422(store, farmer_id, field)
    alert = predict_or_422(ext["disease_model"].predict, features)

    existing = store.list_disease_risk_alerts(farmer_id, field_id, limit=1)
    latest = existing[0] if existing else None
    is_duplicate = (
        latest is not None
        and latest.disease == alert.disease
        and latest.risk_level == alert.risk_level
        and abs(alert.created_at - latest.created_at) < _DISEASE_RISK_DEDUP_WINDOW
    )
    if not is_duplicate:
        store.save_disease_risk_alert(farmer_id, alert)

    alerts = store.list_disease_risk_alerts(farmer_id, field_id)
    return {"items": [to_json(a) for a in alerts]}


def compute_advisories(store, ext: dict, farmer_id: str, field_id: str) -> dict:
    field = get_field_or_404(store, farmer_id, field_id)
    features = features_or_422(store, farmer_id, field)
    advisory = predict_or_422(ext["decision_engine"].recommend, field, features)
    store.save_advisory(farmer_id, advisory)
    advisories = store.list_advisories_for_field(farmer_id, field_id)
    return {"items": [to_json(a) for a in advisories]}


def compute_disease_risk_image(store, ext: dict, farmer_id: str, field_id: str, file_storage) -> dict:
    field = get_field_or_404(store, farmer_id, field_id)
    image_bytes = validate_image_upload(file_storage)

    try:
        features = build_features_for_field(store, farmer_id, field)
    except ValueError as exc:
        raise ApiError(422, "NO_WEATHER_DATA", str(exc)) from None

    disease_model = ext["disease_model"]
    alert = resolve_disease_alert(disease_model, features, field_id, image_bytes=image_bytes)

    saved = store.save_disease_risk_alert(farmer_id, alert)
    return to_json(saved)


def submit_feedback(store, farmer_id: str, body) -> dict:
    if not isinstance(body, dict):
        raise ApiError(400, "BAD_REQUEST", "Request body must be a JSON object")

    missing = [k for k in ("advisory_id", "rating", "helpful") if k not in body]
    if missing:
        raise ApiError(400, "BAD_REQUEST", f"Missing required fields: {', '.join(missing)}")
    validate_feedback_create(body)

    advisory = store.get_advisory(farmer_id, body["advisory_id"])
    if advisory is None:
        raise ApiError(404, "NOT_FOUND", "Advisory not found")

    entry = FeedbackEntry(
        id=str(uuid.uuid4()),
        farmer_id=farmer_id,
        advisory_id=body["advisory_id"],
        created_at=datetime.now(timezone.utc),
        rating=body["rating"],
        helpful=bool(body["helpful"]),
        comment=body.get("comment"),
    )
    saved = store.save_feedback_entry(farmer_id, entry)
    return to_json(saved)
