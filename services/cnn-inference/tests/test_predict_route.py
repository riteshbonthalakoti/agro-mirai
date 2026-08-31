"""Route-level tests for the CNN inference service, using a stub model —
no torch needed to run these (see README.md's isolation note, mirrors
tests/vision/'s pattern of keeping torch-dependent tests separate)."""
import dataclasses
import io
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402


@dataclasses.dataclass
class _FakeAlert:
    id: str
    field_id: str
    created_at: datetime
    disease: str
    risk_level: str
    confidence: float
    window_start_at: datetime
    window_end_at: datetime
    recommended_action: str


class _StubModel:
    def predict(self, image_path, field_id):
        created_at = datetime(2026, 9, 1, tzinfo=timezone.utc)
        return _FakeAlert(
            id="alert-1",
            field_id=field_id,
            created_at=created_at,
            disease="Apple Scab",
            risk_level="moderate",
            confidence=0.72,
            window_start_at=created_at,
            window_end_at=created_at + timedelta(days=5),
            recommended_action="Scout the field within 5 days.",
        )


class _BrokenModel:
    def predict(self, image_path, field_id):
        raise ValueError("corrupt image tensor")


def _client(model_factory):
    app = create_app(model_factory=model_factory)
    app.config["TESTING"] = True
    return app.test_client()


def test_health_ok_when_model_loads():
    client = _client(lambda: _StubModel())
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_health_degraded_when_model_load_fails():
    def _boom():
        raise FileNotFoundError("weights missing")

    client = _client(_boom)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "degraded"


def test_predict_success():
    client = _client(lambda: _StubModel())
    data = {
        "field_id": "field-1",
        "image": (io.BytesIO(b"fake-image-bytes"), "leaf.jpg"),
    }
    resp = client.post("/predict", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["field_id"] == "field-1"
    assert body["risk_level"] == "moderate"
    assert body["created_at"] == "2026-09-01T00:00:00Z"


def test_predict_missing_image_400():
    client = _client(lambda: _StubModel())
    resp = client.post("/predict", data={"field_id": "field-1"}, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_predict_missing_field_id_400():
    client = _client(lambda: _StubModel())
    data = {"image": (io.BytesIO(b"x"), "leaf.jpg")}
    resp = client.post("/predict", data=data, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_predict_model_unavailable_503():
    def _boom():
        raise FileNotFoundError("weights missing")

    client = _client(_boom)
    data = {"field_id": "field-1", "image": (io.BytesIO(b"x"), "leaf.jpg")}
    resp = client.post("/predict", data=data, content_type="multipart/form-data")
    assert resp.status_code == 503


def test_predict_inference_error_422():
    client = _client(lambda: _BrokenModel())
    data = {"field_id": "field-1", "image": (io.BytesIO(b"x"), "leaf.jpg")}
    resp = client.post("/predict", data=data, content_type="multipart/form-data")
    assert resp.status_code == 422
