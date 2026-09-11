"""Server-rendered read-only Admin dashboard (Module 19), same Jinja2/
Flask pattern as the Module 14 frontend (ADR 0013), minimally styled and
honestly labeled "functional, not yet polished" per the module spec.

Renders directly from the DataStore (not a JSON round trip through
``/v2/admin/*``) since this lives in-process anyway and it is the same
data those JSON routes already expose read-only — no new write path.
Genuinely no POST/PUT/DELETE route in this blueprint touches domain
data; the only POSTs are login/logout, which only touch the session.

Module 26: login no longer checks a local ``password_hash`` — it makes a
server-side call to Supabase Auth's password grant (via the ``supabase``
client's ``auth.sign_in_with_password``, not a hand-rolled HTTP call) and
stores the resulting JWT in Flask's signed session cookie
(``session_auth.issue_browser_session``). The admin role check reads the
verified token's ``app_metadata.role`` claim, the same source of truth
every ``/v2`` route now uses (never the client-writable
``user_metadata``) — see decisions/0022-supabase-auth-migration.md.
"""
from __future__ import annotations

import dataclasses
import os

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from agro_mirai.api.errors import ApiError
from agro_mirai.api.jwt_auth import verify_token
from agro_mirai.api.serializers import farmer_to_public_json, to_json
from agro_mirai.api.session_auth import clear_session, issue_browser_session, require_admin
from agro_mirai.feedback.aggregator import FeedbackAggregator

admin_ui_bp = Blueprint("admin_ui", __name__, url_prefix="/admin")


@admin_ui_bp.get("/login")
def login_form():
    return render_template("admin_login.html")


@admin_ui_bp.post("/login")
def login():
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    if not email or not password:
        flash("Invalid email or password", "error")
        return redirect(url_for("admin_ui.login_form"))

    from supabase import create_client

    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        flash("Admin login is not configured (SUPABASE_URL/SUPABASE_KEY unset)", "error")
        return redirect(url_for("admin_ui.login_form"))

    client = create_client(url, key)
    try:
        auth_response = client.auth.sign_in_with_password(
            {"email": email, "password": password}
        )
    except Exception:  # noqa: BLE001 - any Supabase Auth rejection is just "invalid creds"
        flash("Invalid email or password", "error")
        return redirect(url_for("admin_ui.login_form"))

    access_token = auth_response.session.access_token if auth_response.session else None
    if not access_token:
        flash("Invalid email or password", "error")
        return redirect(url_for("admin_ui.login_form"))

    verified = verify_token(access_token)
    if verified.role != "admin":
        flash("This account does not have admin access", "error")
        return redirect(url_for("admin_ui.login_form"))

    issue_browser_session(access_token)
    return redirect(url_for("admin_ui.dashboard"))


@admin_ui_bp.post("/logout")
def logout():
    clear_session()
    return redirect(url_for("admin_ui.login_form"))


@admin_ui_bp.errorhandler(ApiError)
def _redirect_unauthorized(err: ApiError):
    flash(err.message, "error")
    return redirect(url_for("admin_ui.login_form"))


@admin_ui_bp.get("")
@require_admin
def dashboard():
    store = current_app.extensions["data_store"]
    farmers = store.list_all_farmers()
    farmer_rows = []
    for f in farmers:
        row = farmer_to_public_json(f)
        row["field_count"] = len(store.list_fields(f.id, limit=1000))
        farmer_rows.append(row)
    fields = [to_json(f) for f in store.list_all_fields()]
    pairs = store.list_all_feedback_with_advisories()
    feedback = dataclasses.asdict(FeedbackAggregator.aggregate(pairs))
    return render_template(
        "admin_dashboard.html", farmers=farmer_rows, fields=fields, feedback=feedback
    )
