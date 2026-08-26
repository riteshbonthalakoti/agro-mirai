"""Liveness endpoint — public, no auth."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health():
    store = current_app.extensions["data_store"]
    ok = store.ping()
    return jsonify({"status": "ok" if ok else "degraded"}), 200
