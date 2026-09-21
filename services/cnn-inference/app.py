"""CNN inference service — standalone Flask app wrapping
``ImageDiseaseRiskModel`` (Module 20) behind an HTTP boundary.

Deliberately a SEPARATE process/service from the main ``agro_mirai`` API
(``src/agro_mirai/api/app.py``), not a blueprint added to it: torch/
torchvision are excluded from the main app's ``requirements.txt`` (same
policy as the voice stack, ``decisions/0014``), and this is the container
that ships them, meant to run on the Oracle VM per ADR 0019 while the
main API stays on Render.

``GET /health`` mirrors ``src/agro_mirai/api/routes/health.py``'s
shape (``{"status": "ok"|"degraded"}``). ``POST /predict`` accepts a
multipart image upload (`image` file field) + a `field_id` form field
and returns the same JSON shape ``agro_mirai.api.serializers.to_json``
produces for a ``DiseaseRiskAlert``.

The model is loaded lazily on first request (not at import time) so
``GET /health`` still responds (as "degraded") even before the weight
files have been mounted/copied onto the VM — see README.md for how the
gitignored ``models/disease_cnn_mobilenetv2.pt`` /
``disease_cnn_class_names.json`` artifacts get there.
"""
from __future__ import annotations

import dataclasses
import hmac
import os
import tempfile
from datetime import date, datetime
from pathlib import Path

from flask import Flask, jsonify, request

_model = None
_model_load_error: str | None = None


def _fmt(value):
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(value, date):
        return value.isoformat()
    return value


def _to_json(record) -> dict:
    data = dataclasses.asdict(record)
    return {k: _fmt(v) for k, v in data.items()}


def _get_model():
    """Lazily constructs (and caches) the ``ImageDiseaseRiskModel``.

    Import happens inside the function so this module can be imported
    (and ``/health`` can respond) even in an environment where torch
    isn't installed yet, or the weight files aren't present.
    """
    global _model, _model_load_error
    if _model is not None:
        return _model
    if _model_load_error is not None:
        raise RuntimeError(_model_load_error)
    try:
        from agro_mirai.models.image_disease_risk_model import ImageDiseaseRiskModel

        weights_path = Path(os.environ.get("CNN_WEIGHTS_PATH", "") or "") or None
        class_names_path = Path(os.environ.get("CNN_CLASS_NAMES_PATH", "") or "") or None
        kwargs = {}
        if weights_path:
            kwargs["weights_path"] = weights_path
        if class_names_path:
            kwargs["class_names_path"] = class_names_path
        _model = ImageDiseaseRiskModel(**kwargs)
        return _model
    except Exception as exc:  # noqa: BLE001 — reported via /health + 503, not a crash
        _model_load_error = str(exc)
        raise


def create_app(model_factory=None) -> Flask:
    """``model_factory``, if given, overrides ``_get_model`` — used by
    tests to inject a stub without needing torch installed."""
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10MB, matches the main API's cap

    get_model = model_factory or _get_model

    @app.get("/health")
    def health():
        try:
            get_model()
            return jsonify({"status": "ok"}), 200
        except Exception as exc:  # noqa: BLE001
            return jsonify({"status": "degraded", "detail": str(exc)}), 200

    @app.post("/predict")
    def predict():
        # When CNN_SERVICE_TOKEN is set (public hosting), callers must present
        # it; unset keeps local/dev use open.
        expected = os.environ.get("CNN_SERVICE_TOKEN", "").strip()
        if expected and not hmac.compare_digest(request.headers.get("X-Service-Token", ""), expected):
            return jsonify({"error": {"code": "UNAUTHORIZED", "message": "invalid service token"}}), 401
        if "image" not in request.files:
            return jsonify({"error": {"code": "BAD_REQUEST", "message": "image file is required"}}), 400
        field_id = request.form.get("field_id")
        if not field_id:
            return jsonify({"error": {"code": "BAD_REQUEST", "message": "field_id form field is required"}}), 400

        image_file = request.files["image"]
        try:
            model = get_model()
        except Exception as exc:  # noqa: BLE001
            return jsonify({"error": {"code": "MODEL_UNAVAILABLE", "message": str(exc)}}), 503

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            image_file.save(tmp.name)
            tmp_path = tmp.name
        try:
            alert = model.predict(tmp_path, field_id)
        except Exception as exc:  # noqa: BLE001
            return jsonify({"error": {"code": "INFERENCE_ERROR", "message": str(exc)}}), 422
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        return jsonify(_to_json(alert)), 200

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8001)))
