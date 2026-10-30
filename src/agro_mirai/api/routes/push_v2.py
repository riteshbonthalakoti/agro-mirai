"""``/v2/push-tokens`` -- registers a farmer's device for Android push
notifications (Module 59). Same session-auth pattern as every other
``/v2`` route; the actual push send lives in ``api/push_client.py``,
triggered from value_endpoints.py (fresh high/severe scan result) and
``tools/push_sweep.py`` (periodic background check, run by the same
GitHub Actions cron that already keeps the Render free tier awake)."""
import uuid
from datetime import datetime, timezone

from flask import Blueprint, current_app, g, jsonify, request

from agro_mirai.api.session_auth import require_session_auth
from agro_mirai.persistence.models import PushToken

push_v2_bp = Blueprint("push_v2", __name__, url_prefix="/v2")


@push_v2_bp.post("/push-tokens")
@require_session_auth
def register_push_token():
    store = current_app.extensions["data_store"]
    body = request.get_json(silent=True) or {}
    token = (body.get("token") or "").strip()
    if not token:
        return jsonify({"error": {"message": "token is required", "code": "TOKEN_REQUIRED"}}), 400
    platform = (body.get("platform") or "android").strip() or "android"
    now = datetime.now(timezone.utc)
    record = PushToken(id=str(uuid.uuid4()), farmer_id=g.farmer_id, token=token, platform=platform, created_at=now, updated_at=now)
    store.save_push_token(g.farmer_id, record)
    return jsonify({"ok": True}), 200


@push_v2_bp.delete("/push-tokens")
@require_session_auth
def unregister_push_token():
    """Called on logout -- a signed-out device should stop receiving this
    farmer's pushes immediately, not just whenever the token naturally
    goes stale on Expo's side."""
    body = request.get_json(silent=True) or {}
    token = (body.get("token") or "").strip()
    if token:
        store = current_app.extensions["data_store"]
        store.delete_push_token(token)
    return jsonify({"ok": True}), 200
