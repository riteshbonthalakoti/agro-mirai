"""Flask application factory.

Initialises the ``DataStore`` and the model wrappers once per app (stored
in ``app.extensions``, not module-level globals) and registers every
blueprint. Config is read from env vars — see ``.env.example`` for
``DATABASE_URL``, ``API_KEY``, ``FARMER_ID``.
"""
from __future__ import annotations

import logging
import os
from datetime import timedelta

import sentry_sdk
from flask import Flask, g, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sentry_sdk.integrations.flask import FlaskIntegration

from agro_mirai.api.errors import register_error_handlers
from agro_mirai.api.request_context import init_request_logging
from agro_mirai.models.crop_recommendation_model import CropRecommendationModel
from agro_mirai.models.decision_engine import DecisionEngine
from agro_mirai.models.disease_risk_model import DiseaseRiskModel
from agro_mirai.models.irrigation_prediction_model import IrrigationPredictionModel
from agro_mirai.persistence.sqlite_store import SQLiteDataStore


def _build_default_store(app: Flask):
    """Pick SupabaseDataStore when creds are configured, else SQLite.

    Render's filesystem is ephemeral across restarts/deploys, so the
    deployed instance must use Supabase — set via ``SUPABASE_URL``/
    ``SUPABASE_KEY`` env vars in Render's dashboard. Local dev leaves
    those unset and gets the existing SQLite path unchanged.
    """
    if os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_KEY"):
        from agro_mirai.persistence.supabase_store import SupabaseDataStore

        return SupabaseDataStore()
    return SQLiteDataStore(app.config["DATABASE_URL"])


def _configure_sentry(app: Flask) -> None:
    """No-op with no SENTRY_DSN set — local dev and any deploy that hasn't
    configured one run fine without it. With a DSN, tags each event with
    the request id, route, and farmer id (when known) so an error in the
    Sentry dashboard is debuggable without reproducing it blind.
    """
    dsn = app.config.get("SENTRY_DSN") or os.environ.get("SENTRY_DSN", "")
    if not dsn:
        return

    sentry_sdk.init(dsn=dsn, integrations=[FlaskIntegration()], traces_sample_rate=0.0)

    @app.before_request
    def _tag_sentry_scope():
        sentry_sdk.set_tag("request_id", g.get("request_id", ""))
        sentry_sdk.set_tag("route", request.path)
        farmer_id = app.config.get("FARMER_ID")
        if farmer_id:
            sentry_sdk.set_tag("farmer_id", farmer_id)


def _rate_limit_key() -> str:
    """Key by the caller's API key (Bearer token) so each key gets its own
    bucket; falls back to remote address for unauthenticated requests so
    they still share a (coarser) limit instead of bypassing it entirely.
    """
    from flask import request

    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[len("Bearer "):].strip()
    return get_remote_address()


def _configure_rate_limit(app: Flask) -> Limiter:
    """Sensible default: 60 requests/minute per API key, in-memory store —
    no new infra dependency (fine for a single-process deployment; a
    multi-worker deploy would need a shared store like Redis, noted here
    rather than silently assumed). Adjust via the RATE_LIMIT env var, e.g.
    "120 per minute". /health is exempt so uptime checks never trip it.
    """
    limiter = Limiter(
        key_func=_rate_limit_key,
        app=app,
        default_limits=[app.config["RATE_LIMIT"]],
        storage_uri="memory://",
    )
    return limiter


def _configure_logging(app: Flask) -> None:
    """Standard-library ``logging`` only — no new dependency. Each handler
    gets a formatter that includes ``request_id`` (populated by the
    ``_RequestIdLogFilter`` installed in ``init_request_logging``).
    """
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "[%(asctime)s] %(levelname)s request_id=%(request_id)s %(name)s: %(message)s"
        )
    )
    app.logger.handlers = [handler]
    app.logger.setLevel(logging.INFO)


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)

    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-only-secret-not-for-prod")
    app.config["API_KEY"] = os.environ.get("API_KEY", "")
    app.config["FARMER_ID"] = os.environ.get("FARMER_ID", "")
    app.config["DATABASE_URL"] = os.environ.get("DATABASE_URL", "agro_mirai.db")
    app.config["TESTING"] = os.environ.get("FLASK_ENV") == "testing"
    app.config["RATE_LIMIT"] = os.environ.get("RATE_LIMIT", "60 per minute")
    app.config["SENTRY_DSN"] = os.environ.get("SENTRY_DSN", "")
    # Module 19 — /v2 session auth. FLASK_SECRET_KEY (already required by
    # Module 15's Procfile/render.yaml for Flask's session signing) covers
    # this; no new secret was introduced. LOGIN_RATE_LIMIT is specific to
    # /v2/auth/login, on top of the general per-key RATE_LIMIT above.
    app.config["LOGIN_RATE_LIMIT"] = os.environ.get("LOGIN_RATE_LIMIT", "5 per minute")
    # Module 23 — voice endpoints (/v2/advisories/{id}/audio, /v2/stt) are
    # far more expensive per call than a JSON read, so they get their own,
    # tighter limits on top of the general RATE_LIMIT above.
    app.config["TTS_RATE_LIMIT"] = os.environ.get("TTS_RATE_LIMIT", "20 per minute")
    app.config["STT_RATE_LIMIT"] = os.environ.get("STT_RATE_LIMIT", "10 per minute")
    app.permanent_session_lifetime = timedelta(hours=24)
    if config:
        app.config.update(config)

    store = app.config.get("DATA_STORE") or _build_default_store(app)
    crop_model = app.config.get("CROP_MODEL") or CropRecommendationModel()
    irrigation_model = app.config.get("IRRIGATION_MODEL") or IrrigationPredictionModel()
    disease_model = app.config.get("DISEASE_MODEL") or DiseaseRiskModel()
    decision_engine = app.config.get("DECISION_ENGINE") or DecisionEngine(
        crop_model=crop_model,
        irrigation_model=irrigation_model,
        disease_model=disease_model,
    )

    app.extensions["data_store"] = store
    app.extensions["crop_model"] = crop_model
    app.extensions["irrigation_model"] = irrigation_model
    app.extensions["disease_model"] = disease_model
    app.extensions["decision_engine"] = decision_engine

    register_error_handlers(app)
    _configure_logging(app)
    init_request_logging(app)
    _configure_sentry(app)
    limiter = _configure_rate_limit(app)

    from agro_mirai.api.routes.admin import admin_bp
    from agro_mirai.api.routes.admin_ui import admin_ui_bp
    from agro_mirai.api.routes.advisory import advisory_bp
    from agro_mirai.api.routes.auth_v2 import auth_v2_bp
    from agro_mirai.api.routes.disease_image import disease_image_bp
    from agro_mirai.api.routes.farms import farms_bp
    from agro_mirai.api.routes.farms_v2 import farms_v2_bp
    from agro_mirai.api.routes.feedback import feedback_bp
    from agro_mirai.api.routes.frontend import frontend_bp
    from agro_mirai.api.routes.health import health_bp
    from agro_mirai.api.routes.value_v2 import value_v2_bp
    from agro_mirai.api.routes.voice_v2 import voice_v2_bp

    limiter.exempt(health_bp)

    app.register_blueprint(health_bp)
    app.register_blueprint(farms_bp)
    app.register_blueprint(advisory_bp)
    app.register_blueprint(disease_image_bp)
    app.register_blueprint(feedback_bp)
    app.register_blueprint(frontend_bp)
    app.register_blueprint(auth_v2_bp)
    app.register_blueprint(farms_v2_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(admin_ui_bp)
    app.register_blueprint(value_v2_bp)
    app.register_blueprint(voice_v2_bp)

    # Module 19 — login-specific rate limit, on top of the general
    # per-key limit above. The @login_limiter.limit(...) decorator lives
    # on the view function itself in routes/auth_v2.py (must be applied
    # before blueprint registration, see login_rate_limit.py's
    # docstring); this just binds that limiter to this app instance.
    from agro_mirai.api.login_rate_limit import login_limiter

    login_limiter.init_app(app)

    # Module 23 — same pattern as login_limiter, for the two voice routes.
    from agro_mirai.api.voice_rate_limit import voice_limiter

    voice_limiter.init_app(app)

    return app
