"""Shows the REAL production data that already lives in Supabase.

Read only: this script only calls list/get methods, it cannot change anything.

Run:  python supabase_read.py
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from agro_mirai.persistence.supabase_store import SupabaseDataStore  # noqa: E402

store = SupabaseDataStore()
print("Connected to Supabase:", os.environ["SUPABASE_URL"])

farmers = store.list_all_farmers()
print(f"\nFARMERS ({len(farmers)})")
for f in farmers:
    print(f"  {f.name}  language={f.preferred_language}  phone={f.phone}")

fields = store.list_all_fields()
print(f"\nFIELDS ({len(fields)})")
for fld in fields:
    print(f"  {fld.name}  crop={fld.current_crop}  soil={fld.soil_type}  {fld.area_ha} ha  ({fld.latitude}, {fld.longitude})")
    weather = store.list_weather_readings(fld.farmer_id, fld.id, limit=1000)
    soil = store.list_soil_samples(fld.farmer_id, fld.id, limit=1000)
    ndvi = store.list_ndvi_readings(fld.farmer_id, fld.id, limit=1000)
    advisories = store.list_advisories_for_field(fld.farmer_id, fld.id, limit=200)
    alerts = store.list_disease_risk_alerts(fld.farmer_id, fld.id, limit=200)
    print(f"    stored: {len(weather)} weather rows, {len(soil)} soil samples, {len(ndvi)} NDVI readings,")
    print(f"            {len(advisories)} advisories, {len(alerts)} disease alerts")
    if advisories:
        latest = advisories[0]
        print(f"    latest advisory ({latest.created_at:%Y-%m-%d %H:%M}, severity {latest.severity}): {latest.title}")

pairs = store.list_all_feedback_with_advisories()
print(f"\nFEEDBACK ENTRIES ({len(pairs)})")
for fb, adv in pairs[:5]:
    print(f"  rating {fb.rating}/5, helpful={fb.helpful}  on '{adv.title}'")
