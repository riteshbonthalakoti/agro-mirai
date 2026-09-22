"""Tabular ML microservice for Crop Recommendation and Irrigation Prediction.

Runs as a standalone web service on Render (`agro-mirai-tabular`), offloading
scikit-learn RandomForest inference from the main API service to stay strictly
within Render's 512 MB Free Tier limit.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
import json
import os
import sys
from pathlib import Path

from flask import Flask, jsonify, request

# Ensure `src` is in sys.path when running inside services/tabular-ml
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agro_mirai.models.crop_recommendation_model import CropRecommendationModel
from agro_mirai.models.irrigation_prediction_model import IrrigationPredictionModel
from agro_mirai.processing.feature_builder import FeatureVector

_crop_model: CropRecommendationModel | None = None
_irrigation_model: IrrigationPredictionModel | None = None
_load_error: str | None = None


def _get_models():
    global _crop_model, _irrigation_model, _load_error
    if _crop_model is not None and _irrigation_model is not None:
        return _crop_model, _irrigation_model
    if _load_error is not None:
        raise RuntimeError(_load_error)
    try:
        _crop_model = CropRecommendationModel()
        _irrigation_model = IrrigationPredictionModel()
        return _crop_model, _irrigation_model
    except Exception as exc:
        _load_error = str(exc)
        raise


def _dict_to_feature_vector(data: dict) -> FeatureVector:
    """Deserializes JSON dict into a FeatureVector dataclass."""
    data = dict(data)
    if isinstance(data.get("as_of"), str):
        data["as_of"] = date.fromisoformat(data["as_of"])
    valid_fields = set(FeatureVector.__dataclass_fields__.keys())
    filtered = {k: v for k, v in data.items() if k in valid_fields}
    return FeatureVector(**filtered)


def _serialize_domain_model(obj: object) -> dict:
    """Helper to convert dataclass domain models with datetimes to JSON dict."""
    res = asdict(obj)
    for k, v in res.items():
        if isinstance(v, (datetime, date)):
            res[k] = v.isoformat()
    return res


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    @app.get("/health")
    def health():
        try:
            _get_models()
            return jsonify({"status": "ok", "service": "tabular-ml"}), 200
        except Exception as exc:
            return jsonify({"status": "degraded", "detail": str(exc)}), 200

    @app.post("/predict/crop")
    def predict_crop():
        try:
            data = request.get_json(force=True)
            if not data or "feature_vector" not in data:
                return jsonify({"error": {"code": "BAD_REQUEST", "message": "feature_vector is required"}}), 400
            
            top_k = int(data.get("top_k", 3))
            features = _dict_to_feature_vector(data["feature_vector"])
            crop_model, _ = _get_models()
            recommendation = crop_model.predict(features, top_k=top_k)
            return jsonify(_serialize_domain_model(recommendation)), 200
        except Exception as exc:
            return jsonify({"error": {"code": "INFERENCE_ERROR", "message": str(exc)}}), 422

    @app.post("/predict/irrigation")
    def predict_irrigation():
        try:
            data = request.get_json(force=True)
            if not data or "feature_vector" not in data:
                return jsonify({"error": {"code": "BAD_REQUEST", "message": "feature_vector is required"}}), 400

            features = _dict_to_feature_vector(data["feature_vector"])
            _, irrigation_model = _get_models()
            advice = irrigation_model.predict(features)
            return jsonify(_serialize_domain_model(advice)), 200
        except Exception as exc:
            return jsonify({"error": {"code": "INFERENCE_ERROR", "message": str(exc)}}), 422

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8004))
    app.run(host="0.0.0.0", port=port)
