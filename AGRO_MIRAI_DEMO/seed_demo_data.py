"""Builds the local demo database (demo.db).

1. Reads the previous, real data for the demo farmer from Supabase
   (READ ONLY, nothing is ever written to Supabase) and copies it into demo.db.
2. Adds three synthetic demo fields in Karnataka, and pulls live weather, soil
   and satellite (NDVI) data for them from the real sources.

Run once by setup.bat. Safe to run again: it rebuilds demo.db from scratch.
"""
import os
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
key_path = os.environ.get("EE_SERVICE_ACCOUNT_KEY", "")
if key_path and not os.path.isabs(key_path):
    os.environ["EE_SERVICE_ACCOUNT_KEY"] = str(ROOT / key_path)

from agro_mirai.acquisition.base import FieldInput  # noqa: E402
from agro_mirai.api.field_data_acquisition import (  # noqa: E402
    fetch_and_save_ndvi,
    fetch_and_save_soil,
    fetch_and_save_weather,
)
from agro_mirai.persistence.models import Farmer, Field_  # noqa: E402
from agro_mirai.persistence.sqlite_store import SQLiteDataStore  # noqa: E402

FARMER_ID = os.environ["FARMER_ID"]

SYNTHETIC_FIELDS = [
    # name, latitude, longitude, area_ha, soil_type, current_crop
    ("SYNTHETIC Raichur Cotton Plot", 16.2076, 77.3463, 3.2, "black", "cotton"),
    ("SYNTHETIC Mandya Rice Paddy", 12.5218, 76.8951, 1.8, "alluvial", "rice"),
    ("SYNTHETIC Dharwad Maize Field", 15.4589, 75.0078, 2.4, "red", "maize"),
]


def copy_real_data_from_supabase(store):
    """Read-only copy of the farmer's previous data. Returns a short summary."""
    from agro_mirai.persistence.supabase_store import SupabaseDataStore

    remote = SupabaseDataStore()
    farmer = remote.get_farmer(FARMER_ID)
    if farmer is None:
        raise RuntimeError(f"farmer {FARMER_ID} not found in Supabase")
    # never copy login details into the demo database
    farmer.email, farmer.password_hash, farmer.role = None, None, "farmer"
    store.save_farmer(farmer)

    counts = {"fields": 0, "weather": 0, "soil": 0, "ndvi": 0, "advisories": 0, "alerts": 0, "feedback": 0}
    for field in remote.list_fields(FARMER_ID, limit=100):
        store.save_field(FARMER_ID, field)
        counts["fields"] += 1
        for r in remote.list_weather_readings(FARMER_ID, field.id, limit=1000):
            store.save_weather_reading(FARMER_ID, r)
            counts["weather"] += 1
        for r in remote.list_soil_samples(FARMER_ID, field.id, limit=1000):
            store.save_soil_sample(FARMER_ID, r)
            counts["soil"] += 1
        for r in remote.list_ndvi_readings(FARMER_ID, field.id, limit=1000):
            store.save_ndvi_reading(FARMER_ID, r)
            counts["ndvi"] += 1
        for a in remote.list_advisories_for_field(FARMER_ID, field.id, limit=200):
            store.save_advisory(FARMER_ID, a)
            counts["advisories"] += 1
        for a in remote.list_disease_risk_alerts(FARMER_ID, field.id, limit=200):
            store.save_disease_risk_alert(FARMER_ID, a)
            counts["alerts"] += 1
    for fb in remote.list_feedback_for_farmer(FARMER_ID, limit=500):
        store.save_feedback_entry(FARMER_ID, fb)
        counts["feedback"] += 1
    return counts


def main():
    db_file = ROOT / "demo.db"
    if db_file.exists():
        db_file.unlink()
    store = SQLiteDataStore(str(db_file))

    try:
        counts = copy_real_data_from_supabase(store)
        print("Copied previous data from Supabase (read only):", counts)
    except Exception as exc:  # noqa: BLE001
        print(f"WARNING: could not read Supabase ({type(exc).__name__}: {exc}).")
        print("Continuing with a local demo farmer only.")
        now = datetime.now(timezone.utc)
        store.save_farmer(
            Farmer(id=FARMER_ID, created_at=now, updated_at=now, name="Demo Farmer", preferred_language="en")
        )

    print("\nCreating synthetic fields and pulling LIVE data (about 15 s each) ...")
    for name, lat, lon, area, soil, crop in SYNTHETIC_FIELDS:
        now = datetime.now(timezone.utc)
        field = Field_(
            id=str(uuid.uuid4()),
            farmer_id=FARMER_ID,
            created_at=now,
            updated_at=now,
            name=name,
            latitude=lat,
            longitude=lon,
            area_ha=area,
            soil_type=soil,
            current_crop=crop,
            sown_on=date(now.year, max(1, now.month - 2), 1),
        )
        store.save_field(FARMER_ID, field)
        fi = FieldInput(latitude=lat, longitude=lon, field_id=field.id)
        results = {
            "weather": fetch_and_save_weather(store, FARMER_ID, fi),
            "soil": fetch_and_save_soil(store, FARMER_ID, fi),
            "ndvi": fetch_and_save_ndvi(store, FARMER_ID, fi),
        }
        print(f"  {name}: {results}")

    # bring the real field's weather up to date too, so every model has fresh data
    for field in store.list_fields(FARMER_ID, limit=100):
        if field.name.startswith("SYNTHETIC"):
            continue
        fi = FieldInput(latitude=field.latitude, longitude=field.longitude, field_id=field.id)
        results = {
            "weather": fetch_and_save_weather(store, FARMER_ID, fi),
            "soil": fetch_and_save_soil(store, FARMER_ID, fi),
            "ndvi": fetch_and_save_ndvi(store, FARMER_ID, fi),
        }
        print(f"  {field.name} (real field, refreshed live): {results}")

    print("\nDone. demo.db is ready. Start the server with run.bat")


if __name__ == "__main__":
    main()
