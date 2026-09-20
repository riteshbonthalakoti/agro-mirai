"""Runs the demo test cases (backend + models) for real and writes results.

Needs the demo backend running (run.bat) and internet. Inside the demo folder this
file is test_cases.py:

    .\.venv\Scripts\python test_cases.py

It takes about 3 to 5 minutes and adds a few test fields and feedback entries to the
local demo.db only, never to Supabase.

Every case records what was actually observed, so the Status and "Work Done"
columns of the test-case tables are real results, not assumptions.
"""
import dataclasses
import io
import json
import math
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import warnings

warnings.filterwarnings("ignore")
DEMO = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else DEMO / "test_results.json"
EVAL_DIR = DEMO / "docs" / "eval" if (DEMO / "docs" / "eval").exists() else Path(__file__).resolve().parent.parent / "docs" / "eval"
sys.path.insert(0, str(DEMO / "src"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(DEMO / ".env")
os.environ["EE_SERVICE_ACCOUNT_KEY"] = str(DEMO / "keys" / "ee-service-account.json")

import requests  # noqa: E402

BASE = "http://127.0.0.1:5000"
KEY = os.environ["API_KEY"]
H = {"Authorization": "Bearer " + KEY}
FARMER = os.environ["FARMER_ID"]
SAMPLES = DEMO / "samples"

from agro_mirai.acquisition.base import FieldInput  # noqa: E402
from agro_mirai.acquisition.earth_engine import NDVIAdapter  # noqa: E402
from agro_mirai.acquisition.open_meteo import WeatherAdapter  # noqa: E402
from agro_mirai.acquisition.soilgrids import SoilAdapter  # noqa: E402
from agro_mirai.api.features import build_features_for_field  # noqa: E402
from agro_mirai.models.crop_recommendation_model import CropRecommendationModel  # noqa: E402
from agro_mirai.models.disease_risk_model import DiseaseRiskModel  # noqa: E402
from agro_mirai.models.evapotranspiration import hargreaves_samani_et0  # noqa: E402
from agro_mirai.models.image_disease_risk_model import ImageDiseaseRiskModel  # noqa: E402
from agro_mirai.models.irrigation_prediction_model import IrrigationPredictionModel  # noqa: E402
from agro_mirai.models.crop_coefficients import growth_stage_for, kc_for  # noqa: E402
from agro_mirai.models.regional_suitability import BELLARY_REGIONAL_CROPS  # noqa: E402
from agro_mirai.persistence.sqlite_store import SQLiteDataStore  # noqa: E402

store = SQLiteDataStore(str(DEMO / "demo.db"))
CROPS22 = {
    "rice", "maize", "chickpea", "kidneybeans", "pigeonpeas", "mothbeans", "mungbean", "blackgram",
    "lentil", "pomegranate", "banana", "mango", "grapes", "watermelon", "muskmelon", "apple", "orange",
    "papaya", "coconut", "cotton", "jute", "coffee",
}
LADDER = ["low", "moderate", "high", "severe"]


def get(path, **kw):
    return requests.get(BASE + path, headers=H, timeout=180, **kw)


def post(path, **kw):
    return requests.post(BASE + path, headers=H, timeout=180, **kw)


def fields():
    items = get("/fields").json()["items"]
    return sorted(items, key=lambda f: f["created_at"])


def real_field():
    return fields()[0]


def features_of(field_dict):
    f = store.get_field(FARMER, field_dict["id"])
    return build_features_for_field(store, FARMER, f)


CASES = []


def case(cid, area, level, module, test, expected):
    def deco(fn):
        CASES.append(dict(id=cid, area=area, level=level, module=module, test=test, expected=expected, fn=fn))
        return fn

    return deco


# ============================================================ BACKEND: unit
@case("B-U1", "Backend", "Unit", "Health endpoint", "GET /health", "HTTP 200 and {\"status\": \"ok\"}")
def _():
    r = requests.get(BASE + "/health", timeout=10)
    return r.status_code == 200 and r.json() == {"status": "ok"}, f"HTTP {r.status_code} {r.json()}"


@case("B-U2", "Backend", "Unit", "API key security", "GET /fields with no key, then with a wrong key",
      "Both rejected with HTTP 401 UNAUTHORIZED")
def _():
    a = requests.get(BASE + "/fields", timeout=10)
    b = requests.get(BASE + "/fields", headers={"Authorization": "Bearer wrong"}, timeout=10)
    ok = a.status_code == 401 and b.status_code == 401 and a.json()["error"]["code"] == "UNAUTHORIZED"
    return ok, f"no key: HTTP {a.status_code}, wrong key: HTTP {b.status_code}"


@case("B-U3", "Backend", "Unit", "Farmer profile", "GET /farmers/me",
      "HTTP 200 with the farmer's name and no password hash in the reply")
def _():
    r = get("/farmers/me")
    d = r.json()
    ok = r.status_code == 200 and d.get("name") and "password_hash" not in d
    return ok, f"HTTP {r.status_code}, name={d.get('name')}, language={d.get('preferred_language')}"


@case("B-U4", "Backend", "Unit", "Field listing", "GET /fields",
      "HTTP 200, at least 4 fields, each with latitude, longitude and area")
def _():
    r = get("/fields")
    items = r.json()["items"]
    ok = r.status_code == 200 and len(items) >= 4 and all(i["latitude"] and i["longitude"] and i["area_ha"] for i in items)
    return ok, f"HTTP {r.status_code}, {len(items)} fields"


@case("B-U5", "Backend", "Unit", "Field validation (range)", "POST /fields with latitude 200",
      "HTTP 400 BAD_REQUEST, nothing is saved")
def _():
    before = len(fields())
    r = post("/fields", json={"name": "bad", "latitude": 200, "longitude": 76, "area_ha": 1})
    ok = r.status_code == 400 and len(fields()) == before
    return ok, f"HTTP {r.status_code}: {r.json()['error']['message']}"


@case("B-U6", "Backend", "Unit", "Field validation (missing data)", "POST /fields without the name",
      "HTTP 400 that names the missing field")
def _():
    r = post("/fields", json={"latitude": 15, "longitude": 76, "area_ha": 1})
    msg = r.json()["error"]["message"]
    return r.status_code == 400 and "name" in msg, f"HTTP {r.status_code}: {msg}"


@case("B-U7", "Backend", "Unit", "Unknown field", "GET /fields/does-not-exist",
      "HTTP 404 NOT_FOUND (not a 500)")
def _():
    r = get("/fields/does-not-exist")
    return r.status_code == 404, f"HTTP {r.status_code} {r.json()['error']['code']}"


@case("B-U8", "Backend", "Unit", "Image upload validation", "Upload a text file (app.py) as the image",
      "HTTP 400 \"file is not a valid image\"")
def _():
    fid = real_field()["id"]
    with open(DEMO / "app.py", "rb") as fh:
        r = post(f"/fields/{fid}/disease-risk/image", files={"image": ("app.py", fh)})
    return r.status_code == 400, f"HTTP {r.status_code}: {r.json()['error']['message']}"


@case("B-U9", "Backend", "Unit", "Feedback validation", "POST /feedback with rating 9",
      "HTTP 400 BAD_REQUEST")
def _():
    r = post("/feedback", json={"advisory_id": "x", "rating": 9, "helpful": True})
    return r.status_code == 400, f"HTTP {r.status_code}: {r.json()['error']['message']}"


@case("B-U10", "Backend", "Unit", "Weather adapter (Open-Meteo)", "Fetch live weather for the Ballari field coordinates",
      "Weather rows returned with temperature and humidity, source open_meteo")
def _():
    rows = WeatherAdapter().fetch(FieldInput(latitude=15.14, longitude=76.92, field_id="t"))
    ok = len(rows) > 0 and all(r["temp_c"] is not None for r in rows) and rows[0]["source"] == "open_meteo"
    return ok, f"{len(rows)} rows, source {rows[0]['source']}, first temp {rows[0]['temp_c']} C"


@case("B-U11", "Backend", "Unit", "Soil adapter (SoilGrids)", "Fetch live soil data for the Ballari field coordinates",
      "A soil record returned with source soilgrids")
def _():
    rows = SoilAdapter().fetch(FieldInput(latitude=15.14, longitude=76.92, field_id="t"))
    ok = len(rows) >= 1 and rows[0]["source"] == "soilgrids"
    return ok, f"{len(rows)} record, source {rows[0]['source']}, pH {rows[0].get('ph')}"


@case("B-U12", "Backend", "Unit", "Satellite adapter (Google Earth Engine)", "Fetch live NDVI for the Ballari field coordinates",
      "NDVI between 0 and 1 from Sentinel-2, source gee_live")
def _():
    rows = NDVIAdapter().fetch(FieldInput(latitude=15.14, longitude=76.92, field_id="t"))
    r = rows[0]
    ok = r["source"] == "gee_live" and 0 < r["ndvi"] < 1
    return ok, f"source {r['source']}, NDVI {r['ndvi']}, scene date {r['observed_at'][:10]}, cloud {r.get('cloud_cover_pct')}%"


@case("B-U13", "Backend", "Unit", "NDVI fallback", "Break the Earth Engine key, then fetch NDVI for a cached location",
      "Adapter does not crash; it serves the stored (cache) value and reports source cache")
def _():
    adapter = NDVIAdapter(key_path=str(DEMO / "keys" / "does-not-exist.json"))
    rows = adapter.fetch(FieldInput(latitude=15.1394, longitude=76.9214, field_id=None))
    return rows[0]["source"] == "cache", f"source {rows[0]['source']}, NDVI {rows[0]['ndvi']}"


@case("B-U14", "Backend", "Unit", "Feature builder", "Build model features for the Ballari field from stored readings",
      "7/14/30-day weather aggregates, soil values, NDVI and season are filled in")
def _():
    f = features_of(real_field())
    ok = all(v is not None for v in (f.temp_c_mean_7d, f.humidity_pct_mean_14d, f.rainfall_mm_sum_30d, f.soil_ph)) and f.season
    return ok, f"temp7d {f.temp_c_mean_7d:.1f} C, humidity14d {f.humidity_pct_mean_14d:.0f}%, rain30d {f.rainfall_mm_sum_30d} mm, season {f.season}"


@case("B-U15", "Backend", "Unit", "Data store ownership", "Read a field using a different farmer's id",
      "Nothing returned (a farmer cannot read another farmer's field)")
def _():
    fid = real_field()["id"]
    other = store.get_field("00000000-0000-0000-0000-000000000000", fid)
    mine = store.get_field(FARMER, fid)
    return other is None and mine is not None, f"other farmer -> {other}, owner -> {mine.name}"


# ============================================================ BACKEND: integration
_new_field = {}


@case("B-I1", "Backend", "Integration", "Field API + live data adapters + data store",
      "POST /fields, then GET /fields/<id>/live-data",
      "HTTP 201 with weather, soil and NDVI all fetched; the readings are then stored and readable")
def _():
    t = time.time()
    r = post("/fields", json={"name": "Test Case Plot", "latitude": 15.1394, "longitude": 76.9214,
                              "area_ha": 2.0, "soil_type": "black", "current_crop": "cotton", "sown_on": "2026-07-15"})
    d = r.json()
    _new_field.update(d)
    note = ""
    if not all(v["ok"] for v in d["live_data"].values()):  # a free public service timed out: use the documented refresh
        note = " (one source timed out, fixed with refresh-data as the guide says)"
        d["live_data"] = post(f"/fields/{d['id']}/refresh-data").json()["live_data"]
    live = get(f"/fields/{d['id']}/live-data").json()
    c = live["counts"]
    ok = r.status_code == 201 and all(v["ok"] for v in d["live_data"].values()) and c["weather_rows"] > 0 and c["soil_samples"] > 0 and c["ndvi_readings"] > 0
    return ok, f"HTTP {r.status_code} in {time.time() - t:.0f}s; stored {c['weather_rows']} weather rows, {c['soil_samples']} soil, {c['ndvi_readings']} NDVI{note}"


@case("B-I2", "Backend", "Integration", "Live data + feature builder", "GET /fields/<new field>/live-data",
      "Model features are computed from the live readings and record where each came from")
def _():
    live = get(f"/fields/{_new_field['id']}/live-data").json()
    mf = live["model_features"]
    ok = mf["temp_c_mean_7d"] is not None and mf["ndvi_confidence_source"] in ("gee_live", "cache") and live["latest_weather"]["source"] == "open_meteo"
    return ok, f"temp7d {mf['temp_c_mean_7d']:.1f} C, NDVI source {mf['ndvi_confidence_source']}, weather source {live['latest_weather']['source']}"


@case("B-I3", "Backend", "Integration", "API + crop model", "GET /fields/<id>/recommendation",
      "HTTP 200 with a recommended crop, confidence and alternatives")
def _():
    r = get(f"/fields/{real_field()['id']}/recommendation")
    d = r.json()
    ok = r.status_code == 200 and d["recommended_crop"] in CROPS22 and 0 < d["confidence"] <= 1 and len(d["alternatives"]) >= 1
    return ok, f"HTTP {r.status_code}, {d['recommended_crop']} (confidence {d['confidence']}), alternatives {d['alternatives']}"


@case("B-I4", "Backend", "Integration", "API + decision engine + explanations", "GET /fields/<id>/advisories",
      "HTTP 200; newest advisory has a plain-language explanation and a severity")
def _():
    r = get(f"/fields/{real_field()['id']}/advisories")
    a = r.json()["items"][0]
    ok = r.status_code == 200 and a["severity"] in LADDER and "biggest factors" in a["body"]
    return ok, f"HTTP {r.status_code}, severity {a['severity']}, title '{a['title']}'"


@case("B-I5", "Backend", "Integration", "Image upload + CNN + data store", "POST a leaf photo, then read the saved alert from the database",
      "HTTP 200 with source cnn, and the same alert id is stored in the database")
def _():
    fid = real_field()["id"]
    with open(SAMPLES / "tomato_late_blight.jpg", "rb") as fh:
        r = post(f"/fields/{fid}/disease-risk/image", files={"image": ("leaf.jpg", fh)})
    d = r.json()
    saved = {a.id for a in store.list_disease_risk_alerts(FARMER, fid, limit=200)}
    return r.status_code == 200 and d["source"] == "cnn" and d["id"] in saved, f"HTTP {r.status_code}, source {d['source']}, stored in database: {d['id'] in saved}"


@case("B-I6", "Backend", "Integration", "Advisory + feedback", "POST /feedback for a real advisory, then GET /feedback",
      "HTTP 201, and the rating appears in the feedback list")
def _():
    adv = get(f"/fields/{real_field()['id']}/advisories").json()["items"][0]
    r = post("/feedback", json={"advisory_id": adv["id"], "rating": 4, "helpful": True, "comment": "test case"})
    listed = [f["id"] for f in get("/feedback").json()["items"]]
    return r.status_code == 201 and r.json()["id"] in listed, f"HTTP {r.status_code}, rating {r.json().get('rating')}, listed: {r.json()['id'] in listed}"


@case("B-I7", "Backend", "Integration", "Feedback + data store integrity", "POST /feedback for an advisory that does not exist",
      "HTTP 404 (feedback cannot point at a missing advisory)")
def _():
    r = post("/feedback", json={"advisory_id": "11111111-1111-1111-1111-111111111111", "rating": 3, "helpful": False})
    return r.status_code == 404, f"HTTP {r.status_code}: {r.json()['error']['message']}"


@case("B-I8", "Backend", "Integration", "Supabase (read only) + local demo database", "Compare Supabase records with their local copy",
      "The farmer and the real field exist in both, with identical names and coordinates")
def _():
    from agro_mirai.persistence.supabase_store import SupabaseDataStore

    remote = SupabaseDataStore()
    rf = remote.list_fields(FARMER, limit=50)[0]
    lf = store.get_field(FARMER, rf.id)
    ok = lf is not None and (lf.name, lf.latitude, lf.longitude) == (rf.name, rf.latitude, rf.longitude) and remote.get_farmer(FARMER).name == store.get_farmer(FARMER).name
    return ok, f"Supabase field '{rf.name}' ({rf.latitude}, {rf.longitude}) matches the local copy"


# ============================================================ BACKEND: system
_supabase_before = {}


def _supabase_counts():
    from agro_mirai.persistence.supabase_store import SupabaseDataStore

    r = SupabaseDataStore()
    farmers = r.list_all_farmers()
    fl = r.list_all_fields()
    adv = sum(len(r.list_advisories_for_field(f.farmer_id, f.id, limit=500)) for f in fl)
    fb = len(r.list_all_feedback_with_advisories())
    alerts = sum(len(r.list_disease_risk_alerts(f.farmer_id, f.id, limit=500)) for f in fl)
    return {"farmers": len(farmers), "fields": len(fl), "advisories": adv, "alerts": alerts, "feedback": fb}


@case("B-S1", "Backend", "System", "Complete farmer journey", "Add a field, then live data, crop, irrigation, disease, advisory and feedback",
      "Every step succeeds in one run without any manual data entry")
def _():
    t = time.time()
    r0 = post("/fields", json={"name": "Journey Plot", "latitude": 16.2076, "longitude": 77.3463, "area_ha": 3.0,
                               "soil_type": "black", "current_crop": "cotton", "sown_on": "2026-07-10"})
    fid = r0.json()["id"]
    if not all(v["ok"] for v in r0.json()["live_data"].values()):
        post(f"/fields/{fid}/refresh-data")  # guide troubleshooting step if a free service timed out
    steps = [("crop", get(f"/fields/{fid}/recommendation")), ("irrigation", get(f"/fields/{fid}/irrigation")),
             ("disease", get(f"/fields/{fid}/disease-risk")), ("advisory", get(f"/fields/{fid}/advisories"))]
    adv = steps[-1][1].json()["items"][0]
    fb = post("/feedback", json={"advisory_id": adv["id"], "rating": 5, "helpful": True})
    codes = [r0.status_code] + [s[1].status_code for s in steps] + [fb.status_code]
    return codes == [201, 200, 200, 200, 200, 201], f"HTTP codes {codes}, total {time.time() - t:.0f}s"


@case("B-S2", "Backend", "System", "Real data safety", "Compare the real Supabase record counts before the test run and after it",
      "No count changes: nothing done in the demo can modify the production database")
def _():
    after = _supabase_counts()
    return after == _supabase_before, f"before {_supabase_before} / after {after}"


@case("B-S3", "Backend", "System", "Live data freshness", "Check the age of the newest weather observation stored for the new field",
      "Newest observed (non forecast) weather is not more than 3 days old")
def _():
    live = get(f"/fields/{_new_field['id']}/live-data").json()
    obs = datetime.fromisoformat(live["latest_weather"]["observed_at"].replace("Z", "+00:00"))
    age = (datetime.now(timezone.utc) - obs).days
    return age <= 3, f"newest observation {live['latest_weather']['observed_at']} ({age} days old)"


@case("B-S4", "Backend", "System", "Robustness to bad requests", "Send malformed JSON, wrong data types, an empty body and a huge value",
      "Every bad request gets a clean HTTP 4xx error, never a 500 crash")
def _():
    fid = real_field()["id"]
    codes = [
        requests.post(BASE + "/fields", headers={**H, "Content-Type": "application/json"}, data="{not json", timeout=20).status_code,
        post("/fields", json={"name": 5, "latitude": "x", "longitude": [], "area_ha": {}}).status_code,
        post("/fields", json={}).status_code,
        post("/fields", json={"name": "a", "latitude": 1e308, "longitude": 0, "area_ha": 1}).status_code,
        post("/feedback", json={"advisory_id": None, "rating": "a", "helpful": 1}).status_code,
        get(f"/fields/{fid}/nothing").status_code,
    ]
    return all(400 <= c < 500 for c in codes), f"HTTP codes {codes}"


@case("B-S5", "Backend", "System", "Response time", "Time a simple request and the full advisory request",
      "GET /fields under 1 second, advisory under 15 seconds")
def _():
    fid = real_field()["id"]
    t = time.time(); get("/fields"); a = time.time() - t
    t = time.time(); get(f"/fields/{fid}/advisories"); b = time.time() - t
    return a < 1 and b < 15, f"/fields {a:.2f}s, advisory {b:.1f}s"


@case("B-S6", "Backend", "System", "Concurrent users", "Send 8 requests at the same moment",
      "All 8 answered HTTP 200")
def _():
    with ThreadPoolExecutor(8) as ex:
        codes = list(ex.map(lambda _: get("/fields").status_code, range(8)))
    return codes == [200] * 8, f"HTTP codes {codes}"


# ============================================================ MODELS: unit
crop_model = CropRecommendationModel()
irrigation_model = IrrigationPredictionModel()
disease_model = DiseaseRiskModel()
cnn_model = ImageDiseaseRiskModel()


@case("M-U1", "Models", "Unit", "Model files", "Load the three trained model files",
      "crop_rf.joblib, irrigation_rf.joblib and disease_cnn_mobilenetv2.pt all exist and load")
def _():
    sizes = {n: round((DEMO / "models" / n).stat().st_size / 1e6, 1) for n in ("crop_rf.joblib", "irrigation_rf.joblib", "disease_cnn_mobilenetv2.pt")}
    return all(sizes.values()), f"loaded; sizes in MB {sizes}"


@case("M-U2", "Models", "Unit", "Crop model: training evaluation", "Read the held-out evaluation report of each trained model",
      "Crop accuracy >= 0.99, irrigation >= 0.70, disease CNN >= 0.99 on data not used for training")
def _():
    ev = EVAL_DIR
    c = json.load(open(ev / "crop_rf_eval.json"))
    i = json.load(open(ev / "irrigation_rf_eval.json"))
    d = json.load(open(ev / "disease_cnn_eval.json"))
    ca = c.get("accuracy"); ia = i.get("accuracy")
    da = d.get("best_val_acc")
    return ca >= 0.99 and ia >= 0.70 and da >= 0.99, f"crop {ca:.4f} (macro-F1 {c.get('macro_f1', 0):.4f}), irrigation {ia:.4f}, disease CNN {da:.4f}"


@case("M-U3", "Models", "Unit", "Crop model: prediction", "Predict the crop for 300 rows of the Kaggle dataset",
      "At least 97% predicted correctly; probabilities of the 22 crops add up to 1")
def _():
    import pandas as pd

    df = pd.read_csv(DEMO / "data" / "raw" / "Crop_recommendation.csv").sample(300, random_state=7)
    X = df[["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]]
    m = crop_model._model
    pred = m.predict(X)
    acc = float((pred == df["label"].values).mean())
    ps = m.predict_proba(X.iloc[:5]).sum(axis=1)
    return acc >= 0.97 and all(abs(p - 1) < 1e-6 for p in ps) and len(m.classes_) == 22, f"{acc * 100:.1f}% correct on 300 rows, 22 classes, probabilities sum to {ps[0]:.3f}"


@case("M-U4", "Models", "Unit", "Crop model: regional check", "Check cotton and muskmelon against the Ballari district crop list",
      "Cotton is in the regional list, muskmelon is not (so it would be flagged out_of_region)")
def _():
    return "cotton" in BELLARY_REGIONAL_CROPS and "muskmelon" not in BELLARY_REGIONAL_CROPS, f"regional crops {sorted(BELLARY_REGIONAL_CROPS)}"


@case("M-U5", "Models", "Unit", "Irrigation model: ET0 (FAO-56)", "Compute ET0 for 15 N, day 200, mean 27 C, min 22 C, max 33 C and compare with a hand calculation",
      "Matches the hand-calculated FAO-56 Hargreaves value and lies in the normal 2 to 8 mm/day range")
def _():
    lat, doy, tm, tn, tx = 15.0, 200, 27.0, 22.0, 33.0
    phi = math.radians(lat); dr = 1 + 0.033 * math.cos(2 * math.pi / 365 * doy)
    dl = 0.409 * math.sin(2 * math.pi / 365 * doy - 1.39); ws = math.acos(-math.tan(phi) * math.tan(dl))
    ra = (24 * 60 / math.pi) * 0.0820 * dr * (ws * math.sin(phi) * math.sin(dl) + math.cos(phi) * math.cos(dl) * math.sin(ws))
    exp = 0.0023 * (tm + 17.8) * math.sqrt(tx - tn) * ra * 0.408
    got = hargreaves_samani_et0(tm, tn, tx, lat, doy)
    return abs(got - exp) < 1e-9 and 2 < got < 8, f"model {got:.3f} mm/day, hand calculation {exp:.3f} mm/day"


@case("M-U6", "Models", "Unit", "Irrigation model: crop coefficient", "Growth stage and Kc for cotton at 81 days after sowing and for rice at 10 days",
      "Cotton is in mid-season with Kc above 1.0; rice at 10 days is in the initial stage with a lower Kc")
def _():
    s1 = growth_stage_for("cotton", 81); k1 = kc_for("cotton", s1)
    s2 = growth_stage_for("rice", 10); k2 = kc_for("rice", s2)
    return s1 == "mid_season" and k1 > 1.0 and s2 == "initial", f"cotton: {s1}, Kc {k1}; rice: {s2}, Kc {k2}"


@case("M-U7", "Models", "Unit", "Irrigation model: water balance", "Same field, once with 0 mm rain and once with 60 mm rain in 7 days",
      "Less water is recommended when more rain has fallen, and never below the 2 mm minimum")
def _():
    f = features_of(real_field())
    d0 = irrigation_model.predict(dataclasses.replace(f, rainfall_mm_sum_7d=0.0)).recommended_depth_mm
    d60 = irrigation_model.predict(dataclasses.replace(f, rainfall_mm_sum_7d=60.0)).recommended_depth_mm
    return d0 > d60 >= 2.0, f"0 mm rain -> {d0} mm, 60 mm rain -> {d60} mm"


@case("M-U8", "Models", "Unit", "Irrigation model: urgency", "Predict irrigation urgency for the live features of all 4 fields",
      "Urgency is one of low, moderate, high for every field")
def _():
    u = [irrigation_model.predict(features_of(f)).urgency for f in fields()[:4]]
    return all(x in LADDER for x in u), f"urgency per field {u}"


@case("M-U9", "Models", "Unit", "Disease model (weather based)", "Score a hot, humid, rainy scenario and a dry scenario",
      "Wet and humid scenario gives high or severe risk; dry hot scenario gives low risk")
def _():
    f = features_of(real_field())
    wet = dataclasses.replace(f, humidity_pct_mean_14d=92.0, rainfall_mm_sum_7d=45.0, temp_c_mean_14d=25.0)
    dry = dataclasses.replace(f, humidity_pct_mean_14d=40.0, rainfall_mm_sum_7d=0.0, temp_c_mean_14d=38.0)
    a = disease_model.predict(wet).risk_level; b = disease_model.predict(dry).risk_level
    return a in ("high", "severe") and b == "low", f"wet/humid -> {a}, dry/hot -> {b}"


_EXPECT = {"tomato_late_blight": "Tomato___Late_blight", "maize_common_rust": "Corn_(maize)___Common_rust_",
           "grape_black_rot": "Grape___Black_rot", "apple_healthy": "Apple___healthy",
           "maize_healthy": "Corn_(maize)___healthy", "potato_early_blight": "Potato___Early_blight"}


def _scan(name):
    a, top3 = cnn_model.predict_detailed(SAMPLES / f"{name}.jpg", "t")
    return a, top3


@case("M-U10", "Models", "Unit", "Disease CNN: classification", "Classify 6 leaf photos (3 crops, healthy and diseased)",
      "All 6 photos are classified as their correct disease or healthy class")
def _():
    hits = []
    for n, exp in _EXPECT.items():
        _, t3 = _scan(n)
        hits.append(t3[0]["class"] == exp)
    return all(hits), f"{sum(hits)}/6 correct"


@case("M-U11", "Models", "Unit", "Disease CNN: risk level", "Compare the risk level of a healthy leaf and a diseased leaf",
      "Healthy leaf -> low; diseased leaf -> moderate or higher")
def _():
    h, _t = _scan("apple_healthy"); d, _t2 = _scan("tomato_late_blight")
    return h.risk_level == "low" and LADDER.index(d.risk_level) >= 1, f"healthy apple -> {h.risk_level}, tomato late blight -> {d.risk_level}"


@case("M-U12", "Models", "Unit", "Disease CNN: output validity", "Inspect the top-3 probabilities of a prediction",
      "3 classes, probabilities in 0..1, in descending order, top one equals the reported confidence")
def _():
    a, t3 = _scan("maize_common_rust")
    p = [x["probability"] for x in t3]
    ok = len(p) == 3 and all(0 <= x <= 1 for x in p) and p == sorted(p, reverse=True) and abs(p[0] - a.confidence) < 1e-3
    return ok, f"top-3 {[(x['class'], x['probability']) for x in t3]}"


@case("M-U13", "Models", "Unit", "Disease CNN: input handling", "Send the same leaf as JPG, as PNG, and as a tiny 32x32 image",
      "JPG and PNG give the same class; the tiny image is handled without error")
def _():
    from PIL import Image

    src = Image.open(SAMPLES / "grape_black_rot.jpg").convert("RGB")
    b1, b2, b3 = io.BytesIO(), io.BytesIO(), io.BytesIO()
    src.save(b1, "JPEG"); src.save(b2, "PNG"); src.resize((32, 32)).save(b3, "PNG")
    for b in (b1, b2, b3):
        b.seek(0)
    _a, t1 = cnn_model.predict_detailed(b1, "t"); _b, t2 = cnn_model.predict_detailed(b2, "t"); _c, t3 = cnn_model.predict_detailed(b3, "t")
    return t1[0]["class"] == t2[0]["class"], f"JPG {t1[0]['class']}, PNG {t2[0]['class']}, 32x32 {t3[0]['class']} ({t3[0]['probability']})"


# ============================================================ MODELS: integration
@case("M-I1", "Models", "Integration", "Live features + crop model", "Get the crop recommendation for all 4 fields through the API",
      "HTTP 200 for every field, each crop is one of the 22 known crops")
def _():
    out = []
    for f in fields()[:4]:
        r = get(f"/fields/{f['id']}/recommendation")
        out.append((r.status_code, r.json()["recommended_crop"]))
    return all(c == 200 and k in CROPS22 for c, k in out), f"{out}"


@case("M-I2", "Models", "Integration", "Live features + FAO-56 + irrigation model", "Get irrigation advice for all 4 fields through the API",
      "Depth is at least 2 mm and the rationale shows the ET0, ETc and rainfall numbers used")
def _():
    out = []
    for f in fields()[:4]:
        d = get(f"/fields/{f['id']}/irrigation").json()
        out.append((d["recommended_depth_mm"], d["urgency"], "ET0" in d["rationale"] and "rainfall" in d["rationale"]))
    return all(depth >= 2 and u in LADDER and r for depth, u, r in out), f"(depth mm, urgency, rationale ok) per field {out}"


@case("M-I3", "Models", "Integration", "Weather features + disease model", "GET /fields/<id>/disease-risk for the real field",
      "A complete alert with a risk level, action and 7-day window, source environmental")
def _():
    d = get(f"/fields/{real_field()['id']}/disease-risk").json()
    ok = d["source"] == "environmental" and d["risk_level"] in LADDER and d["recommended_action"] and d["window_end_at"] > d["window_start_at"]
    return ok, f"risk {d['risk_level']}, source {d['source']}, action '{d['recommended_action'][:45]}...'"


@case("M-I4", "Models", "Integration", "Decision engine (three models combined)", "Read irrigation urgency, disease risk and the advisory severity for one field",
      "Advisory severity equals the higher of the irrigation urgency and the disease risk level")
def _():
    fid = real_field()["id"]
    u = get(f"/fields/{fid}/irrigation").json()["urgency"]
    r = get(f"/fields/{fid}/disease-risk").json()["risk_level"]
    s = get(f"/fields/{fid}/advisories").json()["items"][0]["severity"]
    exp = LADDER[max(LADDER.index(u), LADDER.index(r))]
    return s == exp, f"irrigation {u}, disease {r} -> expected {exp}, advisory {s}"


@case("M-I5", "Models", "Integration", "SHAP explanations + decision engine", "Read the text of the newest advisory",
      "It names the biggest factors behind the recommendation and adds the regional caution when the crop is out of region")
def _():
    a = get(f"/fields/{real_field()['id']}/advisories").json()["items"][0]["body"]
    return "biggest factors" in a and "not commonly grown" in a, a[:170] + "..."


@case("M-I6", "Models", "Integration", "Disease CNN + alert record", "POST a leaf photo and check the fields of the saved alert",
      "Alert has id, disease name, risk level, confidence, action and time window")
def _():
    with open(SAMPLES / "grape_black_rot.jpg", "rb") as fh:
        d = post(f"/fields/{real_field()['id']}/disease-risk/image", files={"image": ("l.jpg", fh)}).json()
    need = ["id", "disease", "risk_level", "confidence", "recommended_action", "window_start_at", "window_end_at", "source", "top_predictions"]
    return all(k in d for k in need) and d["disease"].startswith("Grape"), f"disease '{d['disease']}', risk {d['risk_level']}, confidence {d['confidence']:.3f}"


@case("M-I7", "Models", "Integration", "Models use each field's own data", "Compare irrigation depth across the 4 fields",
      "The fields do not all get the same answer, so the models react to the live data of each location")
def _():
    depths = [get(f"/fields/{f['id']}/irrigation").json()["recommended_depth_mm"] for f in fields()[:4]]
    return len(set(depths)) >= 2, f"irrigation depth (mm) per field {depths}"


# ============================================================ MODELS: system
@case("M-S1", "Models", "System", "All models on all fields", "Run crop, irrigation, disease and advisory for every field",
      "16 model calls, all HTTP 200")
def _():
    codes = []
    for f in fields()[:4]:
        for ep in ("recommendation", "irrigation", "disease-risk", "advisories"):
            codes.append(get(f"/fields/{f['id']}/{ep}").status_code)
    return codes == [200] * 16, f"{codes.count(200)}/16 returned HTTP 200"


@case("M-S2", "Models", "System", "CNN honesty check", "Upload a photo that is not a leaf (a farmer portrait)",
      "The answer comes with a clearly lower confidence than a real leaf (below 0.9), so the low confidence can be flagged")
def _():
    with open(SAMPLES / "not_a_leaf_farmer_photo.jpg", "rb") as fh:
        d = post(f"/fields/{real_field()['id']}/disease-risk/image", files={"image": ("p.jpg", fh)}).json()
    return d["confidence"] < 0.9, f"confidence {d['confidence']:.2f} (real leaves score 0.99+), guess '{d['disease']}'"


@case("M-S3", "Models", "System", "Repeatability", "Ask for the same crop recommendation and irrigation depth twice",
      "Identical answers both times (the models are deterministic for the same data)")
def _():
    fid = real_field()["id"]
    a = (get(f"/fields/{fid}/recommendation").json()["recommended_crop"], get(f"/fields/{fid}/irrigation").json()["recommended_depth_mm"])
    b = (get(f"/fields/{fid}/recommendation").json()["recommended_crop"], get(f"/fields/{fid}/irrigation").json()["recommended_depth_mm"])
    return a == b, f"first {a}, second {b}"


@case("M-S4", "Models", "System", "Image model accuracy on the demo set", "Send all 6 leaf photos through the live API",
      "All 6 correct through the full backend, each marked source cnn")
def _():
    fid = real_field()["id"]; ok = 0; rows = []
    for n, exp in _EXPECT.items():
        with open(SAMPLES / f"{n}.jpg", "rb") as fh:
            d = post(f"/fields/{fid}/disease-risk/image", files={"image": (n + ".jpg", fh)}).json()
        hit = d["top_predictions"][0]["class"] == exp and d["source"] == "cnn"
        ok += hit; rows.append(f"{n}: {d['disease']} ({d['confidence']:.2f})")
    return ok == 6, f"{ok}/6 correct; " + "; ".join(rows[:3]) + " ..."


# ============================================================ run
def main():
    _supabase_before.update(_supabase_counts())
    results = []
    for c in CASES:
        t = time.time()
        try:
            ok, observed = c["fn"]()
            status = "PASS" if ok else "FAIL"
        except Exception as exc:  # noqa: BLE001
            status, observed = "ERROR", f"{type(exc).__name__}: {exc}"
        results.append({k: c[k] for k in ("id", "area", "level", "module", "test", "expected")} | {"status": status, "observed": observed, "seconds": round(time.time() - t, 1)})
        print(f"{status:5} {c['id']:7} {c['module'][:44]:44} {observed[:95]}", flush=True)
    OUT.write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    bad = [r for r in results if r["status"] != "PASS"]
    print(f"\n{len(results) - len(bad)}/{len(results)} passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
