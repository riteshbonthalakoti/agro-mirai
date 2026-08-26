"""Flask application factory.

Initialises the ``DataStore`` and the model wrappers once per app (stored
in ``app.extensions``, not module-level globals) and registers every
blueprint. Config is read from env vars — see ``.env.example`` for
``DATABASE_URL``, ``API_KEY``, ``FARMER_ID``.
"""
from __future__ import annotations

import os

from flask import Flask

from agro_mirai.api.errors import register_error_handlers
from agro_mirai.models.crop_recommendation_model import CropRecommendationModel
from agro_mirai.models.decision_engine import DecisionEngine
from agro_mirai.models.disease_risk_model import DiseaseRiskModel
from agro_mirai.models.irrigation_prediction_model import IrrigationPredictionModel
from agro_mirai.persistence.sqlite_store import SQLiteDataStore


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)

    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-only-secret-not-for-prod")
    app.config["API_KEY"] = os.environ.get("API_KEY", "")
    app.config["FARMER_ID"] = os.environ.get("FARMER_ID", "")
    app.config["DATABASE_URL"] = os.environ.get("DATABASE_URL", "agro_mirai.db")
    app.config["TESTING"] = os.environ.get("FLASK_ENV") == "testing"
    if config:
        app.config.update(config)

    store = app.config.get("DATA_STORE") or SQLiteDataStore(app.config["DATABASE_URL"])
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

    from agro_mirai.api.routes.advisory import advisory_bp
    from agro_mirai.api.routes.farms import farms_bp
    from agro_mirai.api.routes.feedback import feedback_bp
    from agro_mirai.api.routes.frontend import frontend_bp
    from agro_mirai.api.routes.health import health_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(farms_bp)
    app.register_blueprint(advisory_bp)
    app.register_blueprint(feedback_bp)
    app.register_blueprint(frontend_bp)

    return app
