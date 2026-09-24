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
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sentry_sdk.integrations.flask import FlaskIntegration

from agro_mirai.api.errors import register_error_handlers
from agro_mirai.api.request_context import _RequestIdLogFilter, init_request_logging
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
    """Standard-library ``logging`` only — no new dependency. The handler's
    formatter includes ``request_id``, populated by ``_RequestIdLogFilter``
    attached to the handler itself (not to one specific logger) so it
    applies uniformly regardless of which module's logger emitted the
    record.

    The handler and INFO level are set on the shared ``agro_mirai`` package
    logger, not just ``app.logger`` -- every module in this codebase logs
    via ``logging.getLogger(__name__)`` under that namespace (e.g.
    ``agro_mirai.auth.otp``, whose OTP-to-server-logs delivery is the only
    thing that makes Module 27's OTP auth testable at all), and without
    this they'd inherit the root logger's default WARNING level and no
    handler, silently dropping every INFO log line. Module 27 shipped with
    exactly that bug -- request-otp returned 200 but the OTP itself never
    appeared anywhere, found via live testing, not a code review guess.
    ``app.logger`` (name ``agro_mirai.api.app``) gets no handler of its own
    and propagates up to this one, so request/response logging and OTP
    logging end up in the same stream with the same format, not duplicated.
    """
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "[%(asctime)s] %(levelname)s request_id=%(request_id)s %(name)s: %(message)s"
        )
    )
    handler.addFilter(_RequestIdLogFilter())
    package_logger = logging.getLogger("agro_mirai")
    package_logger.handlers = [handler]
    package_logger.setLevel(logging.INFO)
    package_logger.propagate = False
    app.logger.handlers = []
    app.logger.propagate = True


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
    # this. Module 27: OTP_RATE_LIMIT is specific to /v2/auth/request-otp,
    # on top of the general per-key RATE_LIMIT above (env var renamed from
    # LOGIN_RATE_LIMIT since Module 27 replaced email+password login with
    # Name+Phone+OTP; see decisions/0023-name-phone-otp-auth.md).
    app.config["OTP_RATE_LIMIT"] = os.environ.get("OTP_RATE_LIMIT", "5 per minute")
    # Module 23 — voice endpoints (/v2/advisories/{id}/audio, /v2/stt) are
    # far more expensive per call than a JSON read, so they get their own,
    # tighter limits on top of the general RATE_LIMIT above.
    app.config["TTS_RATE_LIMIT"] = os.environ.get("TTS_RATE_LIMIT", "20 per minute")
    app.config["STT_RATE_LIMIT"] = os.environ.get("STT_RATE_LIMIT", "10 per minute")
    # Module 30 — /v2/voice/ask chains STT + a Gemini call + TTS per
    # request, the most expensive voice route yet, so it gets the
    # tightest limit of the three.
    app.config["ASK_RATE_LIMIT"] = os.environ.get("ASK_RATE_LIMIT", "6 per minute")
    app.permanent_session_lifetime = timedelta(hours=24)
    # Session cookie hardening — safe defaults that work for both the
    # browser frontend and React Native mobile client.
    # SameSite=None + Secure is required for cross-origin cookie delivery
    # (e.g. Next.js SPA on a different domain calling the Render API).
    # In dev (no FLASK_SECRET_KEY set), these still apply but the cookie
    # is only sent over HTTP, which is fine for localhost.
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = os.environ.get(
        "SESSION_COOKIE_SAMESITE", "None"
    )
    app.config["SESSION_COOKIE_SECURE"] = os.environ.get("FLASK_ENV") == "production"
    if config:
        app.config.update(config)

    # crop + irrigation are plain python now (no model files), so run in-process
    from agro_mirai.models.crop_recommendation_model import CropRecommendationModel
    from agro_mirai.models.irrigation_prediction_model import IrrigationPredictionModel

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

    # CORS — allow browser clients (Next.js landing page, React Native web
    # build) to reach the /v2 API. CORS_ORIGINS env var is a comma-separated
    # list of allowed origins (e.g. "https://agro-mirai.vercel.app"). Unset
    # means no CORS headers are emitted — same-origin only, safe default for
    # curl/mobile. supports_credentials=True so the session cookie is sent
    # cross-origin; this requires an explicit origin list (not "*") in
    # production.
    #
    # Dev-only exception: the Expo web build's dev-server origin changes
    # with the runtime host (see mobile/src/config.ts's dynamic
    # API_BASE_URL, itself the fix for this exact problem's IP side) --
    # there is no fixed origin to list. Outside production, fall back to
    # origins="*", which flask-cors (unlike a hand-rolled "Access-Control-
    # Allow-Origin: *" header) correctly reflects the request's actual
    # Origin rather than emitting a literal "*" when supports_credentials
    # is True — the one combination browsers accept with credentialed
    # requests. Never used when FLASK_ENV=production.
    cors_origins_raw = os.environ.get("CORS_ORIGINS", "")
    is_production = os.environ.get("FLASK_ENV") == "production"
    if cors_origins_raw:
        origins = [o.strip() for o in cors_origins_raw.split(",") if o.strip()]
        CORS(app, origins=origins, supports_credentials=True, resources={r"/v2/*": {}})
    elif not is_production:
        CORS(app, origins="*", supports_credentials=True, resources={r"/v2/*": {}})

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

    # Module 27 — OTP-request-specific rate limit, on top of the general
    # per-key limit above. The @otp_request_limiter.limit(...) decorator
    # lives on the view function itself in routes/auth_v2.py (must be
    # applied before blueprint registration, see login_rate_limit.py's
    # docstring); this just binds that limiter to this app instance.
    from agro_mirai.api.login_rate_limit import otp_request_limiter

    otp_request_limiter.init_app(app)

    # Module 23 — same pattern as login_limiter, for the two voice routes.
    from agro_mirai.api.voice_rate_limit import voice_limiter

    voice_limiter.init_app(app)

    return app
