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

import dataclasses
import uuid
from datetime import datetime, timedelta, timezone

from agro_mirai.api.errors import ApiError
from agro_mirai.api.farmer_text import in_karnataka, plain_advisory, plain_irrigation
from agro_mirai.api.features import build_features_for_field
from agro_mirai.api.image_validation import validate_image_upload
from agro_mirai.api.leaf_gate import looks_like_plant_photo
from agro_mirai.api.serializers import to_json
from agro_mirai.api.validation import validate_feedback_create
from agro_mirai.api.voice_client import translate_text
from agro_mirai.models.image_or_environmental_disease import resolve_disease_alert
from agro_mirai.persistence.models import BugReport, FeedbackEntry
from agro_mirai.voice.interface import V1_LANGUAGES

_BUG_REPORT_CATEGORIES = {
    "crash",
    "wrong_info",
    "unclear_advice",
    "photo_scan_failed",
    "login_failed",
    "other",
}
_MAX_BUG_MESSAGE_LEN = 2000
# Photos are sent inline as a base64 data: URI (no separate upload/storage
# pipeline exists yet — see Module note in decisions/). ~10MB raw image ->
# ~13.4M base64 chars; capped a bit under that.
_MAX_BUG_PHOTO_DATA_URI_LEN = 14_000_000


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


def _annual_rain(field):
    """12-month rain at the field; short wait, None if slow or down."""
    try:
        from agro_mirai.acquisition.open_meteo import annual_rainfall_mm

        return annual_rainfall_mm(field.latitude, field.longitude, timeout_s=2.5)
    except Exception:  # noqa: BLE001 - optional signal
        return None


def compute_recommendation(store, ext: dict, farmer_id: str, field_id: str) -> dict:
    field = get_field_or_404(store, farmer_id, field_id)
    features = features_or_422(store, farmer_id, field)
    features = dataclasses.replace(features, annual_rain_mm_est=_annual_rain(field))
    try:
        recommendation = ext["crop_model"].predict(features)
    except ValueError as exc:
        # Soil N/P/K missing (SoilGrids has no P/K and the farmer picked no
        # soil type to fall back on): a clear 422 the app can show, not a 500.
        raise ApiError(
            422,
            "SOIL_DATA_MISSING",
            f"{exc}. Choose a soil type for this field (Me > Edit field) or refresh field data.",
        ) from None
    # Module 39: CropRecommendationModel never fills `rationale` (only the
    # irrigation model does); the SHAP explanation existed only inside
    # Advisory.body. Attach it here so GET /recommendation carries its own
    # "why". Degrades to rationale=None if the explainer is unavailable.
    if recommendation.rationale is None:
        try:
            service = getattr(ext.get("decision_engine"), "_explanation_service", None)
            if service is not None:
                explanation = service.explain_crop(recommendation, features)
                if isinstance(explanation.summary_en, str):
                    recommendation = dataclasses.replace(recommendation, rationale=explanation.summary_en)
        except Exception:  # noqa: BLE001 - explanation is additive, never blocks the pick
            pass
    saved = store.save_crop_recommendation(farmer_id, recommendation)
    out = to_json(saved)
    # The "not commonly grown in your region" check is a hard-coded
    # Bellary/Karnataka list (decisions/0016): meaningless for fields elsewhere.
    local = in_karnataka(field.latitude, field.longitude)
    if not local:
        out["out_of_region"] = None
        out["regional_alternative"] = None
    out["rationale_plain"] = plain_advisory(out.get("rationale") or "", drop_regional_caveat=not local) or None
    return out


def compute_irrigation(store, ext: dict, farmer_id: str, field_id: str) -> dict:
    field = get_field_or_404(store, farmer_id, field_id)
    features = features_or_422(store, farmer_id, field)
    advice = predict_or_422(ext["irrigation_model"].predict, features)
    saved = store.save_irrigation_advice(farmer_id, advice)
    out = to_json(saved)
    out["rationale_plain"] = plain_irrigation(out.get("rationale"))
    return out


_DISEASE_RISK_DEDUP_WINDOW = timedelta(hours=1)


def resolve_disease_target_lang(store, farmer_id: str, language_override: str | None) -> str:
    """Same resolution order as ``voice_v2._resolve_language`` (explicit
    ``?language=`` query override, else the farmer's own
    ``preferred_language``, else ``en``) -- kept here rather than imported
    from ``routes/voice_v2.py`` so ``value_endpoints.py`` (used by both
    ``/v1`` and ``/v2``) doesn't depend on a route module. An unrecognized
    override silently falls back to ``en`` rather than a 400, since
    disease-risk display language is a client convenience, not a strict
    API contract the way ``/v2/stt``'s ``language`` param is."""
    if language_override and language_override in V1_LANGUAGES:
        return language_override
    farmer = store.get_farmer(farmer_id)
    lang = (farmer.preferred_language if farmer else None) or "en"
    return lang if lang in V1_LANGUAGES else "en"


def _with_disease_translation(alert_json: dict, target_lang: str) -> dict:
    """Module 34 follow-up: the disease-scan headline (``disease``) and
    rationale (``recommended_action``) were server-generated English
    sentences the mobile app displayed as-is regardless of active
    language -- CNN-vs-environmental ``source`` was already localized
    client-side, but this text never was. Rather than restructure
    ``DiseaseRiskAlert`` (``recommended_action`` is already fully
    structured -- exactly 4 fixed strings keyed by ``risk_level``, see
    ``disease_risk_scoring.RISK_ACTION`` -- so the mobile client can and
    now does translate that one from ``risk_level`` alone with no backend
    change), only ``disease`` is genuinely free text (a fixed proxy
    string for the environmental path, or a PlantVillage
    crop+condition label built by ``disease_cnn_labels.disease_display_name``
    for the CNN path) that a client-side lookup table can't cover. This
    reuses the existing IndicTrans2 MT path (``voice_client.translate_text``
    -> ``RemoteVoiceService`` -> ``services/voice``), the same one
    ``synthesize_advisory_audio`` already uses for advisory audio,
    per the "acceptable fallback" documented in this module's brief.
    Additive only: adds ``disease_translated``/``translated_lang`` next to
    the existing ``disease`` field; never modifies ``disease`` itself, and
    both fields are omitted (falls back silently) when ``target_lang`` is
    English or the voice service is unavailable -- the same degrade-not-
    fail contract every other voice-service call in this project follows.
    """
    if target_lang == "en":
        return alert_json
    translated = translate_text(alert_json["disease"], "en", target_lang)
    if translated is None:
        return alert_json
    return {**alert_json, "disease_translated": translated, "translated_lang": target_lang}


def compute_disease_risk(store, ext: dict, farmer_id: str, field_id: str, target_lang: str = "en") -> dict:
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
    return {"items": [_with_disease_translation(to_json(a), target_lang) for a in alerts]}


def compute_advisories(store, ext: dict, farmer_id: str, field_id: str, generate: bool = True) -> dict:
    """``generate=True`` (the original contract) computes and stores a NEW
    advisory on every call. Module 39: the mobile app passes ``generate=False``
    when merely opening the Advice tab (it used to mint a new advisory on every
    open) and only generates when the farmer asks for fresh advice."""
    field = get_field_or_404(store, farmer_id, field_id)
    if generate:
        features = features_or_422(store, farmer_id, field)
        advisory = predict_or_422(ext["decision_engine"].recommend, field, features)
        store.save_advisory(farmer_id, advisory)
    advisories = store.list_advisories_for_field(farmer_id, field_id)
    local = in_karnataka(field.latitude, field.longitude)
    items = []
    for a in advisories:
        item = to_json(a)
        item["body_plain"] = plain_advisory(a.body, drop_regional_caveat=not local)
        items.append(item)
    return {"items": items}


def compute_disease_risk_image(
    store, ext: dict, farmer_id: str, field_id: str, file_storage, target_lang: str = "en"
) -> dict:
    field = get_field_or_404(store, farmer_id, field_id)
    image_bytes = validate_image_upload(file_storage)
    if not looks_like_plant_photo(image_bytes):
        # Module 39: never let the closed-set CNN "diagnose" a bed sheet.
        raise ApiError(
            422,
            "NOT_A_LEAF",
            "This photo does not look like a plant leaf. Take a close, well-lit photo of one leaf.",
        )

    try:
        features = build_features_for_field(store, farmer_id, field)
    except ValueError as exc:
        raise ApiError(422, "NO_WEATHER_DATA", str(exc)) from None

    disease_model = ext["disease_model"]
    alert = resolve_disease_alert(disease_model, features, field_id, image_bytes=image_bytes)

    saved = store.save_disease_risk_alert(farmer_id, alert)
    return _with_disease_translation(to_json(saved), target_lang)


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


def submit_bug_report(store, farmer_id: str, body) -> dict:
    """Low-friction "what went wrong" bug report from the mobile app.
    Deliberately its own record (see BugReport's docstring / migration
    009's header), not a bend of the existing star-rating feedback
    contract -- every field here is optional except that at least one of
    category/message must be present, so a one-tap preset-only submit
    (no typing at all) still counts as a valid report."""
    if not isinstance(body, dict):
        raise ApiError(400, "BAD_REQUEST", "Request body must be a JSON object")

    category = body.get("category")
    message = body.get("message")
    if category is None and not message:
        raise ApiError(400, "BAD_REQUEST", "Provide a category or a message")
    if category is not None:
        if not isinstance(category, str) or category not in _BUG_REPORT_CATEGORIES:
            raise ApiError(
                400,
                "BAD_REQUEST",
                f"category must be one of: {', '.join(sorted(_BUG_REPORT_CATEGORIES))}",
            )
    if message is not None:
        if not isinstance(message, str) or len(message) > _MAX_BUG_MESSAGE_LEN:
            raise ApiError(400, "BAD_REQUEST", f"message must be a string up to {_MAX_BUG_MESSAGE_LEN} chars")

    for optional_str_field in ("photo_url", "app_version", "platform"):
        value = body.get(optional_str_field)
        if value is not None and not isinstance(value, str):
            raise ApiError(400, "BAD_REQUEST", f"{optional_str_field} must be a string")
    photo_url = body.get("photo_url")
    if photo_url is not None and len(photo_url) > _MAX_BUG_PHOTO_DATA_URI_LEN:
        raise ApiError(
            400,
            "BAD_REQUEST",
            f"photo_url exceeds the {_MAX_BUG_PHOTO_DATA_URI_LEN} char limit "
            "(photos are sent as a base64 data: URI, capped well under 10MB raw)",
        )

    report = BugReport(
        id=str(uuid.uuid4()),
        farmer_id=farmer_id,
        created_at=datetime.now(timezone.utc),
        category=category,
        message=message,
        photo_url=body.get("photo_url"),
        app_version=body.get("app_version"),
        platform=body.get("platform"),
    )
    saved = store.save_bug_report(farmer_id, report)
    return to_json(saved)
