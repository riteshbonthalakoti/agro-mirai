"""Module 14 — server-rendered web frontend.

Talks ONLY to Module 11's own JSON API (via ``frontend_client``, an
in-process HTTP round trip) — never imports ``DecisionEngine`` or any
model class directly. See
``decisions/0013-frontend-platform-sequencing.md``.

Single-farmer view per ADR 0003: no farmer/account switcher, just a
field picker for whichever ``Field``s the one configured ``FARMER_ID``
owns.
"""
from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from agro_mirai.api.frontend_client import ApiError, api_get, api_post

frontend_bp = Blueprint("frontend", __name__)


@frontend_bp.get("/")
def dashboard():
    try:
        farmer = api_get("/farmers/me")
        fields = api_get("/fields")["items"]
    except ApiError as exc:
        return render_template("error.html", error=exc.payload), exc.status_code
    return render_template("index.html", farmer=farmer, fields=fields)


@frontend_bp.get("/field/<field_id>")
def field_detail(field_id: str):
    try:
        field = api_get(f"/fields/{field_id}")
        recommendation = _safe_get(f"/fields/{field_id}/recommendation")
        irrigation = _safe_get(f"/fields/{field_id}/irrigation")
        disease_alerts = _safe_get_list(f"/fields/{field_id}/disease-risk")
        advisories = _safe_get_list(f"/fields/{field_id}/advisories")
    except ApiError as exc:
        return render_template("error.html", error=exc.payload), exc.status_code

    return render_template(
        "field.html",
        field=field,
        recommendation=recommendation,
        irrigation=irrigation,
        disease_alerts=disease_alerts,
        advisories=advisories,
    )


@frontend_bp.post("/ui/feedback")
def submit_feedback():
    field_id = request.form.get("field_id", "")
    advisory_id = request.form.get("advisory_id", "")
    rating = request.form.get("rating", "")
    helpful = request.form.get("helpful") == "yes"
    comment = request.form.get("comment") or None

    errors = []
    if not advisory_id:
        errors.append("Missing advisory to rate.")
    try:
        rating_int = int(rating)
        if not (1 <= rating_int <= 5):
            errors.append("Rating must be between 1 and 5.")
    except (TypeError, ValueError):
        errors.append("Rating must be a whole number 1-5.")

    if errors:
        for e in errors:
            flash(e, "error")
        return redirect(url_for("frontend.field_detail", field_id=field_id))

    body = {
        "advisory_id": advisory_id,
        "rating": rating_int,
        "helpful": helpful,
    }
    if comment:
        body["comment"] = comment

    try:
        api_post("/feedback", body)
        flash("Thanks — your feedback was recorded.", "success")
    except ApiError as exc:
        flash(f"Could not submit feedback: {exc.payload.get('error', {}).get('message', 'unknown error')}", "error")

    return redirect(url_for("frontend.field_detail", field_id=field_id))


def _safe_get(path: str):
    """GET that tolerates a 422 (e.g. no weather data yet) by returning
    None instead of failing the whole page render."""
    try:
        return api_get(path)
    except ApiError as exc:
        if exc.status_code in (404, 422):
            return None
        raise


def _safe_get_list(path: str):
    try:
        return api_get(path)["items"]
    except ApiError as exc:
        if exc.status_code in (404, 422):
            return []
        raise
