"""CNN leaf-disease service on ONNX Runtime (Module 40).

Same HTTP contract as ``services/cnn-inference`` (``POST /predict`` with an
``image`` file + ``field_id``; ``GET /health``), but the MobileNetV2 was
exported to ONNX so inference needs onnxruntime + numpy + Pillow instead of
torch. That keeps it inside Render's free 512 MB tier, where the torch build
cannot run. The export was verified against the torch model: identical class
and probabilities (max difference < 1e-5) on every sample photo.

If ``CNN_SERVICE_TOKEN`` is set, callers must send it as ``X-Service-Token``.
The alert-building rules (risk level, action, window) are the project's own
(``agro_mirai.models.disease_cnn_labels`` / ``disease_risk_scoring``), shared
with the torch model so both paths answer identically.
"""
from __future__ import annotations

import hmac
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from flask import Flask, jsonify, request
from PIL import Image

_HERE = Path(__file__).resolve().parent
MODEL_PATH = Path(os.environ.get("CNN_ONNX_PATH") or _HERE / "model" / "disease_cnn_mobilenetv2.onnx")
CLASS_NAMES_PATH = Path(os.environ.get("CNN_CLASS_NAMES_PATH") or _HERE / "model" / "disease_cnn_class_names.json")

_IMG_SIZE = 224
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

_state: dict = {}
_load_error: str | None = None


def _load():
    """Loads (once) and returns ``(session, class_names)``. Lazy so /health can
    answer while the model is still loading."""
    global _load_error
    if _state:
        return _state["session"], _state["names"]
    if _load_error is not None:
        raise RuntimeError(_load_error)
    try:
        import onnxruntime as ort

        with open(CLASS_NAMES_PATH, encoding="utf-8") as fh:
            names = json.load(fh)
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1  # one small CPU; avoid oversubscription
        session = ort.InferenceSession(str(MODEL_PATH), opts, providers=["CPUExecutionProvider"])
        _state.update(session=session, names=names)
        return session, names
    except Exception as exc:  # noqa: BLE001 - reported via /health + 503
        _load_error = str(exc)
        raise


def preprocess(image: Image.Image) -> np.ndarray:
    """Resize to 224x224, scale to [0,1], ImageNet-normalise, NCHW float32
    (identical to the torch model's torchvision transform)."""
    arr = np.asarray(image.convert("RGB").resize((_IMG_SIZE, _IMG_SIZE), Image.BILINEAR), dtype=np.float32) / 255.0
    arr = (arr - _MEAN) / _STD
    return arr.transpose(2, 0, 1)[None].astype(np.float32)


def classify(session, names: list[str], image: Image.Image) -> tuple[str, float]:
    logits = session.run(None, {"input": preprocess(image)})[0][0]
    exp = np.exp(logits - logits.max())
    probs = exp / exp.sum()
    idx = int(probs.argmax())
    return names[idx], float(probs[idx])


def build_alert(raw_class: str, confidence: float, field_id: str) -> dict:
    from agro_mirai.models.disease_cnn_labels import disease_display_name, risk_level_for
    from agro_mirai.models.disease_risk_scoring import RISK_ACTION, RISK_WINDOW_DAYS

    risk = risk_level_for(raw_class, confidence)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return {
        "id": str(uuid.uuid4()),
        "field_id": field_id,
        "created_at": now.strftime(fmt),
        "disease": disease_display_name(raw_class),
        "risk_level": risk,
        "confidence": confidence,
        "window_start_at": now.strftime(fmt),
        "window_end_at": (now + timedelta(days=RISK_WINDOW_DAYS[risk])).strftime(fmt),
        "recommended_action": RISK_ACTION[risk],
    }


def create_app(model_factory=None) -> Flask:
    """``model_factory`` (tests) returns ``(session, class_names)``."""
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
    get_model = model_factory or _load

    @app.get("/")
    @app.get("/health")
    def health():
        try:
            get_model()
            return jsonify({"status": "ok"}), 200
        except Exception as exc:  # noqa: BLE001
            return jsonify({"status": "degraded", "detail": str(exc)}), 200

    @app.post("/predict")
    def predict():
        expected = os.environ.get("CNN_SERVICE_TOKEN", "").strip()
        if expected and not hmac.compare_digest(request.headers.get("X-Service-Token", ""), expected):
            return jsonify({"error": {"code": "UNAUTHORIZED", "message": "invalid service token"}}), 401
        if "image" not in request.files:
            return jsonify({"error": {"code": "BAD_REQUEST", "message": "image file is required"}}), 400
        field_id = request.form.get("field_id")
        if not field_id:
            return jsonify({"error": {"code": "BAD_REQUEST", "message": "field_id form field is required"}}), 400
        try:
            session, names = get_model()
        except Exception as exc:  # noqa: BLE001
            return jsonify({"error": {"code": "MODEL_UNAVAILABLE", "message": str(exc)}}), 503
        try:
            image = Image.open(request.files["image"].stream)
            raw_class, confidence = classify(session, names, image)
            return jsonify(build_alert(raw_class, confidence, field_id)), 200
        except Exception as exc:  # noqa: BLE001
            return jsonify({"error": {"code": "INFERENCE_ERROR", "message": str(exc)}}), 422

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8003)))
