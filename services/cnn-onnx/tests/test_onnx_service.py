"""Module 40: the ONNX CNN service. Route tests use a stub session (no model
needed); the real-model test runs only if the ONNX file is present."""
import io
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

import app as svc  # noqa: E402

NAMES = ["Tomato___Late_blight", "Tomato___healthy"]


class _Session:
    def __init__(self, logits):
        self._logits = np.array([logits], dtype=np.float32)

    def run(self, _outputs, feed):
        assert feed["input"].shape == (1, 3, 224, 224) and feed["input"].dtype == np.float32
        return [self._logits]


def _client(logits=(8.0, 0.0)):
    app = svc.create_app(model_factory=lambda: (_Session(logits), NAMES))
    app.config["TESTING"] = True
    return app.test_client()


def _jpeg():
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (40, 120, 40)).save(buf, "JPEG")
    return buf.getvalue()


def _post(client, headers=None, data=None):
    body = data if data is not None else {"field_id": "f1", "image": (io.BytesIO(_jpeg()), "leaf.jpg")}
    return client.post("/predict", data=body, content_type="multipart/form-data", headers=headers or {})


def test_health_ok_and_degraded():
    assert _client().get("/health").get_json()["status"] == "ok"

    def boom():
        raise FileNotFoundError("model missing")

    app = svc.create_app(model_factory=boom)
    assert app.test_client().get("/health").get_json()["status"] == "degraded"
    assert _post(app.test_client()).status_code == 503


def test_predict_returns_disease_risk_alert_shape():
    r = _post(_client())
    assert r.status_code == 200
    j = r.get_json()
    assert j["field_id"] == "f1" and j["disease"]
    assert j["risk_level"] in {"low", "moderate", "high", "severe"}
    assert 0.9 < j["confidence"] <= 1.0
    for key in ("id", "created_at", "window_start_at", "window_end_at", "recommended_action"):
        assert j[key]
    # the main API parses these timestamps with exactly this format
    datetime.strptime(j["created_at"], "%Y-%m-%dT%H:%M:%SZ")


def test_healthy_class_is_low_risk():
    assert _post(_client(logits=(0.0, 9.0))).get_json()["risk_level"] == "low"


def test_validation_errors():
    c = _client()
    assert c.post("/predict", data={"field_id": "f"}, content_type="multipart/form-data").status_code == 400
    assert _post(c, data={"image": (io.BytesIO(_jpeg()), "l.jpg")}).status_code == 400
    assert _post(c, data={"field_id": "f", "image": (io.BytesIO(b"not an image"), "l.jpg")}).status_code == 422


def test_token(monkeypatch):
    monkeypatch.setenv("CNN_SERVICE_TOKEN", "s3cret")
    c = _client()
    assert _post(c).status_code == 401
    assert _post(c, {"X-Service-Token": "nope"}).status_code == 401
    assert _post(c, {"X-Service-Token": "s3cret"}).status_code == 200
    monkeypatch.delenv("CNN_SERVICE_TOKEN")
    assert _post(c).status_code == 200


@pytest.mark.skipif(not svc.MODEL_PATH.exists(), reason="ONNX model not present")
def test_real_model_identifies_real_samples():
    session, names = svc._load()
    samples = Path(__file__).resolve().parents[3] / "AGRO_MIRAI_DEMO" / "samples"
    expect = {
        "tomato_late_blight.jpg": "Tomato___Late_blight",
        "potato_early_blight.jpg": "Potato___Early_blight",
        "maize_healthy.jpg": "Corn_(maize)___healthy",
    }
    for fname, cls in expect.items():
        f = samples / fname
        if not f.exists():
            pytest.skip("demo samples not present")
        got, conf = svc.classify(session, names, Image.open(f))
        assert got == cls and conf > 0.9
