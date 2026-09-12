"""Server-rendered read-only Admin dashboard (Module 19), same Jinja2/
Flask pattern as the Module 14 frontend (ADR 0013), minimally styled and
honestly labeled "functional, not yet polished" per the module spec.

Renders directly from the DataStore (not a JSON round trip through
``/v2/admin/*``) since this lives in-process anyway and it is the same
data those JSON routes already expose read-only — no new write path.
Genuinely no POST/PUT/DELETE route in this blueprint touches domain
data; the only POSTs are login/logout, which only touch the session.
"""
from __future__ import annotations

import dataclasses

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from agro_mirai.api.errors import ApiError
from agro_mirai.api.serializers import farmer_to_public_json, to_json
from agro_mirai.api.session_auth import clear_session, issue_session, require_admin
from agro_mirai.auth.password import verify_password
from agro_mirai.feedback.aggregator import FeedbackAggregator

admin_ui_bp = Blueprint("admin_ui", __name__, url_prefix="/admin")


@admin_ui_bp.get("/login")
def login_form():
    return render_template("admin_login.html")


@admin_ui_bp.post("/login")
def login():
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    store = current_app.extensions["data_store"]
    farmer = store.get_farmer_by_email(email) if email else None
    if farmer is None or not verify_password(password, farmer.password_hash):
        flash("Invalid email or password", "error")
        return redirect(url_for("admin_ui.login_form"))
    if farmer.role != "admin":
        flash("This account does not have admin access", "error")
        return redirect(url_for("admin_ui.login_form"))
    issue_session(farmer.id, farmer.role)
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
