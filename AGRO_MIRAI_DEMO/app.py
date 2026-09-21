"""AGRO MIRAI demo backend: one small Flask app over the real project code.

Everything here is a thin layer over the same packages the full product uses
(src/agro_mirai): live data acquisition (Open-Meteo weather, SoilGrids soil,
Google Earth Engine NDVI), feature building, and the three trained models
(crop recommendation, irrigation, disease CNN).

Data is stored in a local SQLite file (demo.db), so nothing you do here can
change the real Supabase database.

Run:  python app.py        (or double-click run.bat)
"""
import dataclasses
import io
import os
import sys
import time
import uuid
from datetime import date, datetime, timezone
from functools import wraps
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
key_path = os.environ.get("EE_SERVICE_ACCOUNT_KEY", "")
if key_path and not os.path.isabs(key_path):
    os.environ["EE_SERVICE_ACCOUNT_KEY"] = str(ROOT / key_path)

from flask import Flask, g, jsonify, request  # noqa: E402

from agro_mirai.acquisition.base import FieldInput  # noqa: E402
from agro_mirai.api.errors import ApiError, register_error_handlers  # noqa: E402
from agro_mirai.api.features import build_features_for_field  # noqa: E402
from agro_mirai.api.field_data_acquisition import (  # noqa: E402
    fetch_and_save_ndvi,
    fetch_and_save_soil,
    fetch_and_save_weather,
)
from agro_mirai.api.image_validation import validate_image_upload  # noqa: E402
from agro_mirai.api.serializers import to_json  # noqa: E402
from agro_mirai.api.validation import validate_feedback_create, validate_field_create  # noqa: E402
from agro_mirai.models.crop_recommendation_model import CropRecommendationModel  # noqa: E402
from agro_mirai.models.decision_engine import DecisionEngine  # noqa: E402
from agro_mirai.models.disease_risk_model import DiseaseRiskModel  # noqa: E402
from agro_mirai.models.image_disease_risk_model import ImageDiseaseRiskModel  # noqa: E402
from agro_mirai.models.irrigation_prediction_model import IrrigationPredictionModel  # noqa: E402
from agro_mirai.persistence.models import Field_, FeedbackEntry  # noqa: E402
from agro_mirai.persistence.sqlite_store import SQLiteDataStore  # noqa: E402

API_KEY = os.environ.get("API_KEY", "")
FARMER_ID = os.environ.get("FARMER_ID", "")

app = Flask(__name__)
register_error_handlers(app)

store = SQLiteDataStore(str(ROOT / "demo.db"))
crop_model = CropRecommendationModel()
irrigation_model = IrrigationPredictionModel()
disease_model = DiseaseRiskModel()  # rule-based, weather driven
cnn_model = ImageDiseaseRiskModel()  # MobileNetV2, looks at the leaf photo
engine = DecisionEngine(crop_model=crop_model, irrigation_model=irrigation_model, disease_model=disease_model)


def require_key(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer ") or header[7:].strip() != API_KEY:
            raise ApiError(401, "UNAUTHORIZED", "Send the header  Authorization: Bearer <API_KEY>")
        g.farmer_id = FARMER_ID
        return view(*args, **kwargs)

    return wrapped


def field_or_404(field_id):
    field = store.get_field(g.farmer_id, field_id)
    if field is None:
        raise ApiError(404, "NOT_FOUND", "Field not found")
    return field


def features_for(field):
    try:
        return build_features_for_field(store, g.farmer_id, field)
    except ValueError as exc:
        raise ApiError(422, "NO_WEATHER_DATA", f"{exc}. Call POST /fields/<id>/refresh-data first.") from None


def acquire_live_data(field):
    """Pull live weather, soil and NDVI for a field and save them.
    Returns what happened per source, with timings."""
    fi = FieldInput(latitude=field.latitude, longitude=field.longitude, field_id=field.id)
    result = {}
    for name, fn in [
        ("weather", fetch_and_save_weather),
        ("soil", fetch_and_save_soil),
        ("ndvi", fetch_and_save_ndvi),
    ]:
        start = time.time()
        ok = fn(store, g.farmer_id, fi)
        result[name] = {"ok": ok, "seconds": round(time.time() - start, 1)}
    return result


# ---------------------------------------------------------------- basics
@app.get("/")
def index():
    return jsonify(
        {
            "app": "AGRO MIRAI demo backend",
            "auth": "header  Authorization: Bearer <API_KEY from .env>",
            "GET": [
                "/health",
                "/farmers/me",
                "/fields",
                "/fields/<id>",
                "/fields/<id>/live-data",
                "/fields/<id>/recommendation",
                "/fields/<id>/irrigation",
                "/fields/<id>/disease-risk",
                "/fields/<id>/advisories",
                "/feedback",
            ],
            "POST": [
                "/fields",
                "/fields/<id>/refresh-data",
                "/fields/<id>/disease-risk/image  (multipart, field name: image)",
                "/feedback",
            ],
        }
    )


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/farmers/me")
@require_key
def farmer_me():
    farmer = store.get_farmer(g.farmer_id)
    if farmer is None:
        raise ApiError(404, "NOT_FOUND", "Farmer not found. Run seed_demo_data.py first.")
    data = to_json(farmer)
    data.pop("password_hash", None)
    return jsonify(data)


# ---------------------------------------------------------------- fields
@app.get("/fields")
@require_key
def list_fields():
    return jsonify({"items": [to_json(f) for f in store.list_fields(g.farmer_id)]})


@app.post("/fields")
@require_key
def create_field():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError(400, "BAD_REQUEST", "Request body must be a JSON object")
    missing = [k for k in ("name", "latitude", "longitude", "area_ha") if k not in body]
    if missing:
        raise ApiError(400, "BAD_REQUEST", f"Missing required fields: {', '.join(missing)}")
    validate_field_create(body)
    now = datetime.now(timezone.utc)
    sown_on = body.get("sown_on")
    field = Field_(
        id=str(uuid.uuid4()),
        farmer_id=g.farmer_id,
        created_at=now,
        updated_at=now,
        name=body["name"],
        latitude=body["latitude"],
        longitude=body["longitude"],
        area_ha=body["area_ha"],
        elevation_m=body.get("elevation_m"),
        soil_type=body.get("soil_type"),
        current_crop=body.get("current_crop"),
        sown_on=date.fromisoformat(sown_on) if sown_on else None,
    )
    saved = store.save_field(g.farmer_id, field)
    out = to_json(saved)
    out["live_data"] = acquire_live_data(saved)
    return jsonify(out), 201


@app.get("/fields/<field_id>")
@require_key
def get_field(field_id):
    return jsonify(to_json(field_or_404(field_id)))


@app.post("/fields/<field_id>/refresh-data")
@require_key
def refresh_data(field_id):
    return jsonify({"field_id": field_id, "live_data": acquire_live_data(field_or_404(field_id))})


@app.get("/fields/<field_id>/live-data")
@require_key
def live_data(field_id):
    """The newest stored weather / soil / NDVI reading, with where it came from,
    and the feature numbers the models actually use."""
    field = field_or_404(field_id)
    fid = g.farmer_id
    weather = store.list_weather_readings(fid, field_id, limit=1000)
    soil = store.list_soil_samples(fid, field_id, limit=1000)
    ndvi = store.list_ndvi_readings(fid, field_id, limit=1000)
    latest = lambda rows: to_json(max(rows, key=lambda r: r.observed_at)) if rows else None  # noqa: E731
    features = dataclasses.asdict(features_for(field))
    return jsonify(
        {
            "field": field.name,
            "counts": {"weather_rows": len(weather), "soil_samples": len(soil), "ndvi_readings": len(ndvi)},
            "latest_weather": latest([w for w in weather if not w.is_forecast]),
            "forecast_rows": sum(1 for w in weather if w.is_forecast),
            "latest_soil": latest(soil),
            "latest_ndvi": latest(ndvi),
            "model_features": {k: (v.isoformat() if isinstance(v, date) else v) for k, v in features.items()},
        }
    )


# ---------------------------------------------------------------- models
@app.get("/fields/<field_id>/recommendation")
@require_key
def recommendation(field_id):
    field = field_or_404(field_id)
    try:
        features = features_for(field)
        rec = crop_model.predict(features)
        # The crop model itself leaves `rationale` empty; the SHAP explanation
        # (which soil / weather numbers pushed the pick) is attached here.
        try:
            explanation = engine._explanation_service.explain_crop(rec, features)
            rec = dataclasses.replace(rec, rationale=explanation.summary_en)
        except Exception as exc:  # noqa: BLE001 - the pick still works without its explanation
            print(f"(crop explanation skipped: {exc})")
    except ValueError as exc:
        raise ApiError(
            422,
            "SOIL_DATA_MISSING",
            f"{exc}. The soil service (SoilGrids) did not answer for this field. "
            "Run POST /fields/<id>/refresh-data and try again.",
        ) from None
    return jsonify(to_json(store.save_crop_recommendation(g.farmer_id, rec)))


@app.get("/fields/<field_id>/irrigation")
@require_key
def irrigation(field_id):
    field = field_or_404(field_id)
    try:
        advice = irrigation_model.predict(features_for(field))
    except ValueError as exc:
        raise ApiError(422, "INSUFFICIENT_DATA", str(exc)) from None
    return jsonify(to_json(store.save_irrigation_advice(g.farmer_id, advice)))


@app.get("/fields/<field_id>/disease-risk")
@require_key
def disease_risk(field_id):
    """Weather-driven disease risk (no photo). The photo version is the POST below."""
    field = field_or_404(field_id)
    alert = disease_model.predict(features_for(field))
    alert = dataclasses.replace(alert, source="environmental")
    return jsonify(to_json(store.save_disease_risk_alert(g.farmer_id, alert)))


@app.get("/fields/<field_id>/advisories")
@require_key
def advisories(field_id):
    field = field_or_404(field_id)
    try:
        advisory = engine.recommend(field, features_for(field))
    except ValueError as exc:
        raise ApiError(422, "INSUFFICIENT_DATA", str(exc)) from None
    store.save_advisory(g.farmer_id, advisory)
    items = store.list_advisories_for_field(g.farmer_id, field_id)
    return jsonify({"items": [to_json(a) for a in items]})


@app.post("/fields/<field_id>/disease-risk/image")
@require_key
def disease_risk_image(field_id):
    """Upload a leaf photo (form field name: image). The CNN classifies the
    photo itself; the reply includes its top-3 classes with probabilities."""
    field_or_404(field_id)
    data = validate_image_upload(request.files.get("image"))
    alert, top3 = cnn_model.predict_detailed(io.BytesIO(data), field_id)
    alert = dataclasses.replace(alert, source="cnn")
    saved = store.save_disease_risk_alert(g.farmer_id, alert)
    out = to_json(saved)
    out["top_predictions"] = top3
    out["analysed_by"] = "MobileNetV2 CNN trained on PlantVillage (38 classes)"
    return jsonify(out)


# ---------------------------------------------------------------- feedback
@app.post("/feedback")
@require_key
def post_feedback():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError(400, "BAD_REQUEST", "Request body must be a JSON object")
    missing = [k for k in ("advisory_id", "rating", "helpful") if k not in body]
    if missing:
        raise ApiError(400, "BAD_REQUEST", f"Missing required fields: {', '.join(missing)}")
    validate_feedback_create(body)
    if store.get_advisory(g.farmer_id, body["advisory_id"]) is None:
        raise ApiError(404, "NOT_FOUND", "Advisory not found")
    entry = FeedbackEntry(
        id=str(uuid.uuid4()),
        farmer_id=g.farmer_id,
        advisory_id=body["advisory_id"],
        created_at=datetime.now(timezone.utc),
        rating=body["rating"],
        helpful=bool(body["helpful"]),
        comment=body.get("comment"),
    )
    return jsonify(to_json(store.save_feedback_entry(g.farmer_id, entry))), 201


@app.get("/feedback")
@require_key
def list_feedback():
    return jsonify({"items": [to_json(f) for f in store.list_feedback_for_farmer(g.farmer_id)]})


def warm_up():
    """The first advisory and the first CNN call are slow (libraries compile on
    first use), so do one of each now, before anybody is watching."""
    try:
        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", (64, 64), (40, 120, 40)).save(buf, "PNG")
        buf.seek(0)
        cnn_model.predict_detailed(buf, "warm-up")
        fields = store.list_fields(FARMER_ID, limit=1)
        if fields:
            engine.recommend(fields[0], build_features_for_field(store, FARMER_ID, fields[0]))
    except Exception as exc:  # noqa: BLE001
        print(f"(warm-up skipped: {exc})")


if __name__ == "__main__":
    print("Warming up the models, about 30 seconds ...")
    warm_up()
    print("READY. AGRO MIRAI demo backend on http://localhost:5000  (Ctrl+C to stop)")
    app.run(host="127.0.0.1", port=5000, debug=False)
