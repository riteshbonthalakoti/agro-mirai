"""Module 19: server-rendered /admin dashboard (Jinja2, ADR 0013 pattern).

Admin accounts stay on email+password (never Name+Phone+OTP) since
they're provisioned out-of-band directly against the DataStore, not via
farmer self-registration — see decisions/0023-name-phone-otp-auth.md.
These tests create the Farmer row directly rather than going through
/v2/auth (which is phone+OTP only since Module 27).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from agro_mirai.api.app import create_app
from agro_mirai.auth.password import hash_password
from agro_mirai.persistence.models import Farmer
from agro_mirai.persistence.sqlite_store import SQLiteDataStore


def _app_and_client():
    store = SQLiteDataStore(":memory:")
    app = create_app({"TESTING": True, "DATA_STORE": store, "API_KEY": "x", "FARMER_ID": "y"})
    return app, app.test_client()


def _provision(store, email: str, password: str, name: str, role: str) -> Farmer:
    now = datetime.now(timezone.utc)
    farmer = Farmer(
        id=str(uuid.uuid4()),
        created_at=now,
        updated_at=now,
        name=name,
        preferred_language="en",
        email=email,
        password_hash=hash_password(password),
        role=role,
    )
    return store.save_farmer(farmer)


def test_admin_dashboard_redirects_when_not_logged_in():
    app, client = _app_and_client()
    resp = client.get("/admin", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Admin login" in resp.data


def test_admin_login_rejects_non_admin_account():
    app, client = _app_and_client()
    store = app.extensions["data_store"]
    _provision(store, "farmer@example.com", "Sup3rSecret1", "F", "farmer")

    resp = client.post(
        "/admin/login",
        data={"email": "farmer@example.com", "password": "Sup3rSecret1"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Admin login" in resp.data  # bounced back, not the dashboard


def test_admin_login_and_dashboard_render():
    app, client = _app_and_client()
    store = app.extensions["data_store"]
    _provision(store, "admin@example.com", "Sup3rSecret1", "Admin", "admin")

    resp = client.post(
        "/admin/login",
        data={"email": "admin@example.com", "password": "Sup3rSecret1"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Admin dashboard" in resp.data
    assert b"admin@example.com" in resp.data
