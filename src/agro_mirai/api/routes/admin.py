"""``/v2/admin`` — Admin dashboard API (Module 19, writes added Module 50).

Every write route here (PATCH/DELETE) is behind @require_admin and logs
an audit_log row via api/audit.write_audit_log -- see
decisions/0030-admin-write-actions.md for why the original read-only
scope (decisions/0017) was superseded.
"""
import dataclasses
import json
import logging
import time
from collections import Counter

logger = logging.getLogger(__name__)

from flask import Blueprint, Response, current_app, g, jsonify, request

from agro_mirai.api.audit import write_audit_log
from agro_mirai.api.errors import ApiError
from agro_mirai.api.render_logs import find_latest_otp, seconds_old
from agro_mirai.api.routes.auth_v2 import _normalize_phone
from agro_mirai.api.serializers import drop_unset_source, farmer_to_public_json, to_json
from agro_mirai.api.session_auth import require_admin
from agro_mirai.auth.otp import otp_store
from agro_mirai.auth.validation import validate_phone
from agro_mirai.feedback.aggregator import FeedbackAggregator

admin_bp = Blueprint("admin", __name__, url_prefix="/v2/admin")


def _bug_report_events(store, poll_interval: float = 2.0, max_iterations: int | None = None,
                        seen_ids: set | None = None):
    """Yields SSE-formatted strings, one per newly-seen bug report, by
    polling list_all_bug_reports and diffing against ids already seen.
    Kept separate from the Flask route so it can be unit-tested directly
    without a real streaming HTTP connection or a real sleep."""
    seen = set(seen_ids) if seen_ids else set()
    iterations = 0
    while max_iterations is None or iterations < max_iterations:
        for report in store.list_all_bug_reports():
            if report.id not in seen:
                seen.add(report.id)
                yield f"data: {json.dumps(to_json(report))}\n\n"
        iterations += 1
        if max_iterations is None or iterations < max_iterations:
            time.sleep(poll_interval)


@admin_bp.get("/stream/bug-reports")
@require_admin
def stream_bug_reports():
    store = current_app.extensions["data_store"]
    # Seed "seen" with every bug report that already exists, so a client
    # opening the stream doesn't get flooded with history -- only truly
    # new reports are pushed from here on.
    seen = {r.id for r in store.list_all_bug_reports()}

    def _stream():
        # Emit an immediate comment so the response actually starts
        # streaming (and the WSGI layer's start_response fires) right
        # away, rather than blocking on the first poll cycle -- which,
        # with no bug reports yet and no max_iterations cap, could block
        # indefinitely with nothing ever yielded. Kept in this thin
        # wrapper (not in _bug_report_events) so the generator's own
        # unit-tested yield-per-new-report contract is unaffected.
        yield ": connected\n\n"
        yield from _bug_report_events(store, poll_interval=3.0, seen_ids=seen)

    return Response(
        _stream(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@admin_bp.get("/farmers")
@require_admin
def list_farmers():
    """Used to issue one list_fields() query per farmer just to compute
    field_count -- N round trips for N farmers, the same pattern fixed
    in build_overview/list_scans/list_advisories (see that commit). One
    list_all_fields() call plus an in-memory Counter instead."""
    store = current_app.extensions["data_store"]
    farmers = store.list_all_farmers()
    field_counts = Counter(f.farmer_id for f in store.list_all_fields())
    items = [
        {**farmer_to_public_json(f), "field_count": field_counts.get(f.id, 0)}
        for f in farmers
    ]
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


@admin_bp.get("/admins")
@require_admin
def list_admins():
    store = current_app.extensions["data_store"]
    admins = [f for f in store.list_all_farmers() if f.role == "admin"]
    return jsonify({"items": [farmer_to_public_json(f) for f in admins]}), 200


@admin_bp.post("/admins")
@require_admin
def create_admin():
    import uuid
    from datetime import datetime, timezone

    from agro_mirai.auth.password import hash_password
    from agro_mirai.persistence.models import Farmer

    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    name = (body.get("name") or "").strip() or email.split("@")[0]
    if not email or "@" not in email:
        raise ApiError(400, "INVALID_INPUT", "A valid email is required")
    if len(password) < 8:
        raise ApiError(400, "INVALID_INPUT", "Password must be at least 8 characters")
    store = current_app.extensions["data_store"]
    if store.get_farmer_by_email(email) is not None:
        raise ApiError(409, "CONFLICT", "An account with this email already exists")
    now = datetime.now(timezone.utc)
    farmer = Farmer(
        id=str(uuid.uuid4()),
        created_at=now,
        updated_at=now,
        name=name,
        preferred_language="en",
        email=email,
        password_hash=hash_password(password),
        role="admin",
    )
    saved = store.save_farmer(farmer)
    write_audit_log(store, g.farmer_id, "admin.create", "farmer", saved.id, None, saved)
    return jsonify(farmer_to_public_json(saved)), 201


@admin_bp.delete("/admins/<farmer_id>")
@require_admin
def revoke_admin(farmer_id):
    store = current_app.extensions["data_store"]
    farmer = store.get_farmer(farmer_id)
    if farmer is None or farmer.role != "admin":
        raise ApiError(404, "NOT_FOUND", "Admin not found")
    if farmer_id == g.farmer_id:
        raise ApiError(400, "INVALID_INPUT", "Cannot revoke your own admin access")
    before = farmer
    updated = dataclasses.replace(farmer, role="farmer")
    saved = store.save_farmer(updated)
    write_audit_log(store, g.farmer_id, "admin.revoke", "farmer", farmer_id, before, saved)
    return jsonify({"revoked": True}), 200


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


def _field_lookup(store) -> dict:
    """field_id -> Field_, one query, so callers that already fetched
    every field's scans/advisories in bulk can still attach
    farmer_id/field_name without a second per-field round trip."""
    return {f.id: f for f in store.list_all_fields()}


@admin_bp.get("/scans")
@require_admin
def list_scans():
    """Used to issue one Supabase query per field (N round trips for N
    fields) via the old _per_field() helper -- a single query across
    every field, same as list_all_farmers/list_all_fields already did,
    replaces it. Also what used to let one flaky field's query 500 the
    whole page (a stale pooled connection -- see the fix two commits
    before this one); a single query has nothing to fail "per field" at
    all, so that failure mode is gone outright, not just contained."""
    store = current_app.extensions["data_store"]
    fields = _field_lookup(store)
    items = []
    for a in store.list_all_disease_risk_alerts(limit=2000):
        field = fields.get(a.field_id)
        if field is None or a.source not in _SCAN_SOURCES:
            continue
        items.append({**to_json(a), "farmer_id": field.farmer_id, "field_name": field.name})
    items.sort(key=lambda i: i["created_at"], reverse=True)
    return jsonify({"items": items}), 200


@admin_bp.get("/otps")
@require_admin
def list_pending_otps():
    """Dev/demo convenience for the `log`/`test` OTP providers (Module
    27/56): lets an admin retrieve a currently-pending OTP without
    reading Render's own logs. Admin-only (never public). Refuses to
    serve anything once `sms_gateway` (a real SMS provider) is
    configured -- a farmer's real code reaching a 2FA bypass endpoint
    would defeat the point of sending it over SMS at all. Read-only:
    does not consume/invalidate the OTPs it lists."""
    if current_app.config.get("OTP_PROVIDER") == "sms_gateway":
        raise ApiError(404, "NOT_FOUND", "not available with a real SMS provider configured")
    items = [
        {
            "phone": i["phone"],
            "code": i["code"],
            "issued_at": i["issued_at"].isoformat() if i["issued_at"] else None,
            "expires_at": i["expires_at"].isoformat() if i["expires_at"] else None,
        }
        for i in otp_store.peek_all()
    ]
    return jsonify({"items": items}), 200


@admin_bp.get("/otps/lookup")
@require_admin
def lookup_otp():
    """Backup path for when a real SMS doesn't arrive (Module 57) --
    works regardless of OTP_PROVIDER, unlike /otps above. Reads the
    otp_issued line auth_v2.py logs on every send straight out of
    Render's own log stream; never stores an OTP anywhere new."""
    phone = _normalize_phone(request.args.get("phone"))
    try:
        validate_phone(phone)
    except ValueError as e:
        raise ApiError(400, "BAD_REQUEST", str(e)) from e

    found = find_latest_otp(phone)
    if found is None:
        raise ApiError(404, "NOT_FOUND", "No recent OTP found for this number")

    return jsonify({
        "phone": found["phone"],
        "otp": found["otp"],
        "issued_at": found["issued_at"],
        "seconds_old": seconds_old(found["issued_at"]),
    }), 200


@admin_bp.get("/advisories")
@require_admin
def list_advisories():
    store = current_app.extensions["data_store"]
    fields = _field_lookup(store)
    items = []
    for a in store.list_all_advisories(limit=2000):
        field = fields.get(a.field_id)
        if field is None:
            continue
        items.append({**drop_unset_source(to_json(a)), "farmer_id": field.farmer_id, "field_name": field.name})
    items.sort(key=lambda i: i["created_at"], reverse=True)
    return jsonify({"items": items}), 200


def build_overview(store) -> dict:
    """Bird's-eye system summary: totals, language/crop distribution, and
    the most recent activity across every farmer. Shared by the JSON route
    below and ``admin_ui.dashboard`` so both render the same numbers from
    one implementation."""
    farmers = store.list_all_farmers()
    fields = store.list_all_fields()
    fields_by_id = {f.id: f for f in fields}

    language_counts = Counter(f.preferred_language for f in farmers)
    crop_counts = Counter(f.current_crop for f in fields if f.current_crop)

    # "Total Scans" is a true system-wide count, independent of however
    # many rows the recent-activity feed below actually pulls (only the
    # 20 most recent items are ever shown, so 300 is already generous
    # headroom there) -- one query each instead of the old
    # one-query-per-field loop.
    scan_total = store.count_disease_risk_alerts_by_source(list(_SCAN_SOURCES))
    recent = []
    for a in store.list_all_disease_risk_alerts(limit=300):
        field = fields_by_id.get(a.field_id)
        if field is None or a.source not in _SCAN_SOURCES:
            continue
        recent.append(
            {
                "type": "scan",
                "created_at": a.created_at.isoformat(),
                "farmer_id": field.farmer_id,
                "field_name": field.name,
                "detail": a.disease,
            }
        )
    for adv in store.list_all_advisories(limit=300):
        field = fields_by_id.get(adv.field_id)
        if field is None:
            continue
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


_VALID_BUG_REPORT_STATUSES = {"open", "triaged", "in_progress", "resolved"}


@admin_bp.get("/bug-reports")
@require_admin
def list_bug_reports_admin():
    """``photo_url`` is a full base64 data URI (no file-storage service
    exists yet, same as Farmer/DiseaseRiskAlert) -- admin.js never
    renders it anywhere in the list view, confirmed (no `photo_url`
    reference in that file at all), so including it here was pure dead
    weight: measured live at 282KB for this one route alone, re-fetched
    on every single tab switch with no caching. Swapped for a cheap
    boolean; nothing in the UI needs the actual bytes until/unless a
    detail view is built that does."""
    store = current_app.extensions["data_store"]
    reports = store.list_all_bug_reports()
    items = []
    for r in reports:
        item = to_json(r)
        item["has_photo"] = bool(item.pop("photo_url", None))
        items.append(item)
    return jsonify({"items": items}), 200


@admin_bp.patch("/bug-reports/<bug_report_id>")
@require_admin
def patch_bug_report(bug_report_id):
    store = current_app.extensions["data_store"]
    before = store.get_bug_report_by_id(bug_report_id)
    if before is None:
        raise ApiError(404, "NOT_FOUND", "Bug report not found")
    body = request.get_json(silent=True) or {}
    status = body.get("status")
    if status not in _VALID_BUG_REPORT_STATUSES:
        raise ApiError(400, "INVALID_STATUS",
                        f"status must be one of {sorted(_VALID_BUG_REPORT_STATUSES)}")
    updated = store.update_bug_report_status(bug_report_id, status)
    write_audit_log(store, g.farmer_id, "bug_report.status", "bug_report",
                     bug_report_id, before, updated)
    return jsonify(to_json(updated)), 200


@admin_bp.delete("/bug-reports/<bug_report_id>")
@require_admin
def delete_bug_report_admin(bug_report_id):
    store = current_app.extensions["data_store"]
    before = store.get_bug_report_by_id(bug_report_id)
    if before is None:
        raise ApiError(404, "NOT_FOUND", "Bug report not found")
    store.delete_bug_report_by_id(bug_report_id)
    write_audit_log(store, g.farmer_id, "bug_report.delete", "bug_report",
                     bug_report_id, before, None)
    return jsonify({"deleted": True}), 200


@admin_bp.get("/audit-log")
@require_admin
def get_audit_log():
    """Measured live at 338KB for this one route. write_audit_log now
    strips embedded base64 photos from new snapshots at write time (see
    audit.py), but that does nothing for rows already stored before that
    existed -- strip them here too, on the way out, so this doesn't stay
    slow for however long it takes those older rows to age out."""
    from agro_mirai.api.audit import strip_snapshot_photos

    store = current_app.extensions["data_store"]
    entries = store.list_audit_log()
    items = []
    for e in entries:
        item = to_json(e)
        for key in ("before_json", "after_json"):
            raw = item.get(key)
            if not raw:
                continue
            try:
                item[key] = json.dumps(strip_snapshot_photos(json.loads(raw)))
            except (ValueError, TypeError):
                pass  # not valid JSON for some reason -- leave it as-is rather than drop it
        items.append(item)
    return jsonify({"items": items}), 200
