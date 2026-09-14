#!/usr/bin/env python3
"""Load the golden fixture into a DataStore backend and verify round-trip.

Loads ``specs/domains/fixtures/farm-001.json`` through the ``DataStore``
interface (never raw SQL/PostgREST), in dependency order, then reads
every record back and compares field-for-field against what was loaded.

Usage:

    python tools/seed_fixture.py --backend sqlite --db-path /tmp/seed.db
    python tools/seed_fixture.py --backend supabase   # needs SUPABASE_URL/KEY

Exits non-zero and prints a diff-style report on any mismatch.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agro_mirai.persistence.models import (  # noqa: E402
    Advisory,
    CropRecommendation,
    DiseaseRiskAlert,
    Farmer,
    FeedbackEntry,
    Field_,
    IrrigationAdvice,
    NDVIReading,
    SoilSample,
    WeatherReading,
)

ROOT = Path(__file__).resolve().parent.parent
FIXTURE_PATH = ROOT / "specs" / "domains" / "fixtures" / "farm-001.json"


def _parse_dt(value: str | None, shift: timedelta = timedelta()) -> datetime | None:
    if value is None:
        return None
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) + shift


def _parse_date(value: str | None, shift: timedelta = timedelta()):
    if value is None:
        return None
    return (datetime.strptime(value, "%Y-%m-%d") + shift).date()


def _fixture_time_shift(data: dict) -> timedelta:
    """How far to shift every timestamp in the fixture so its weather
    data is never stale relative to "now".

    The fixture's dates are fixed calendar dates (e.g. a week ending
    2026-08-24). ``FeatureBuilder`` windows (7d/14d/30d) are computed
    relative to the real current date at request time
    (``api/features.py``), so as real time passes the fixture's weather
    readings age out of those windows and every temperature/rainfall
    aggregate silently comes back ``None`` — this is exactly what caused
    a live 500 on ``GET /fields/{id}/advisories`` against an otherwise
    correctly-seeded ``farm-001`` (see ``decisions/`` Module 22 notes).

    Anchoring the shift to the fixture's *latest weather reading* date,
    landing it on today, keeps every other timestamp's relative offset
    from that reading intact (soil sample still ~2 months before it,
    NDVI reading still mid-week, advisories still same-day) while
    guaranteeing the 7-day window is never empty, today or on any future
    run.
    """
    readings = data.get("weather_readings") or []
    if not readings:
        return timedelta()
    latest = max(_parse_dt(r["observed_at"]) for r in readings)
    today = datetime.now(timezone.utc)
    return timedelta(days=(today.date() - latest.date()).days)


def build_store(backend: str, db_path: str | None):
    if backend == "sqlite":
        from agro_mirai.persistence.sqlite_store import SQLiteDataStore

        return SQLiteDataStore(db_path or "seed_fixture.db")
    if backend == "supabase":
        from agro_mirai.persistence.supabase_store import SupabaseDataStore

        return SupabaseDataStore()
    raise ValueError(f"unknown backend: {backend!r}")


def load_fixture(store, data: dict) -> dict[str, list]:
    """Loads every record via the DataStore interface. Returns what was
    loaded, keyed by collection name, for the verification pass.

    Every timestamp in the fixture is shifted by ``_fixture_time_shift``
    so the weather data is never stale relative to "now" — see that
    function's docstring. ``_pdt``/``_pdate`` are shadowed here (same
    names, shift baked in) so every call site below is unchanged.
    """
    loaded: dict[str, list] = {}
    _shift = _fixture_time_shift(data)

    def _pdt(value):
        return _parse_dt(value, _shift)

    def _pdate(value):
        return _parse_date(value, _shift)

    farmer_ids = []
    loaded["farmers"] = []
    for rec in data["farmers"]:
        f = Farmer(
            id=rec["id"],
            created_at=_pdt(rec["created_at"]),
            updated_at=_pdt(rec["updated_at"]),
            name=rec["name"],
            preferred_language=rec["preferred_language"],
            phone=rec.get("phone"),
            district=rec.get("district"),
            state=rec.get("state"),
        )
        saved = store.save_farmer(f)
        loaded["farmers"].append(saved)
        farmer_ids.append(saved.id)

    field_to_farmer = {}
    loaded["fields"] = []
    for rec in data["fields"]:
        fl = Field_(
            id=rec["id"],
            farmer_id=rec["farmer_id"],
            created_at=_pdt(rec["created_at"]),
            updated_at=_pdt(rec["updated_at"]),
            name=rec["name"],
            latitude=rec["latitude"],
            longitude=rec["longitude"],
            area_ha=rec["area_ha"],
            elevation_m=rec.get("elevation_m"),
            soil_type=rec.get("soil_type"),
            current_crop=rec.get("current_crop"),
            sown_on=_pdate(rec.get("sown_on")),
        )
        saved = store.save_field(rec["farmer_id"], fl)
        loaded["fields"].append(saved)
        field_to_farmer[saved.id] = rec["farmer_id"]

    def farmer_for(field_id: str) -> str:
        return field_to_farmer[field_id]

    loaded["weather_readings"] = []
    for rec in data.get("weather_readings", []):
        r = WeatherReading(
            id=rec["id"], field_id=rec["field_id"], observed_at=_pdt(rec["observed_at"]),
            source=rec["source"], temp_c=rec["temp_c"], is_forecast=rec["is_forecast"],
            temp_min_c=rec.get("temp_min_c"), temp_max_c=rec.get("temp_max_c"),
            humidity_pct=rec.get("humidity_pct"), rainfall_mm=rec.get("rainfall_mm"),
            wind_mps=rec.get("wind_mps"),
        )
        loaded["weather_readings"].append(
            store.save_weather_reading(farmer_for(rec["field_id"]), r)
        )

    loaded["soil_samples"] = []
    for rec in data.get("soil_samples", []):
        s = SoilSample(
            id=rec["id"], field_id=rec["field_id"], observed_at=_pdt(rec["observed_at"]),
            source=rec["source"], ph=rec.get("ph"),
            nitrogen_mg_per_kg=rec.get("nitrogen_mg_per_kg"),
            phosphorus_mg_per_kg=rec.get("phosphorus_mg_per_kg"),
            potassium_mg_per_kg=rec.get("potassium_mg_per_kg"),
            organic_carbon_pct=rec.get("organic_carbon_pct"),
            moisture_pct=rec.get("moisture_pct"),
        )
        loaded["soil_samples"].append(
            store.save_soil_sample(farmer_for(rec["field_id"]), s)
        )

    loaded["ndvi_readings"] = []
    for rec in data.get("ndvi_readings", []):
        n = NDVIReading(
            id=rec["id"], field_id=rec["field_id"], observed_at=_pdt(rec["observed_at"]),
            source=rec["source"], ndvi=rec["ndvi"], cloud_cover_pct=rec.get("cloud_cover_pct"),
            satellite=rec.get("satellite"),
        )
        loaded["ndvi_readings"].append(
            store.save_ndvi_reading(farmer_for(rec["field_id"]), n)
        )

    loaded["crop_recommendations"] = []
    for rec in data.get("crop_recommendations", []):
        c = CropRecommendation(
            id=rec["id"], field_id=rec["field_id"], created_at=_pdt(rec["created_at"]),
            recommended_crop=rec["recommended_crop"], confidence=rec["confidence"],
            alternatives=rec.get("alternatives"), rationale=rec.get("rationale"),
            season=rec.get("season"),
        )
        loaded["crop_recommendations"].append(
            store.save_crop_recommendation(farmer_for(rec["field_id"]), c)
        )

    loaded["irrigation_advices"] = []
    for rec in data.get("irrigation_advices", []):
        i = IrrigationAdvice(
            id=rec["id"], field_id=rec["field_id"], created_at=_pdt(rec["created_at"]),
            recommended_depth_mm=rec["recommended_depth_mm"],
            window_start_at=_pdt(rec["window_start_at"]), window_end_at=_pdt(rec["window_end_at"]),
            urgency=rec["urgency"], rationale=rec.get("rationale"),
        )
        loaded["irrigation_advices"].append(
            store.save_irrigation_advice(farmer_for(rec["field_id"]), i)
        )

    loaded["disease_risk_alerts"] = []
    for rec in data.get("disease_risk_alerts", []):
        d = DiseaseRiskAlert(
            id=rec["id"], field_id=rec["field_id"], created_at=_pdt(rec["created_at"]),
            disease=rec["disease"], risk_level=rec["risk_level"], confidence=rec["confidence"],
            window_start_at=_pdt(rec.get("window_start_at")),
            window_end_at=_pdt(rec.get("window_end_at")),
            recommended_action=rec.get("recommended_action"),
        )
        loaded["disease_risk_alerts"].append(
            store.save_disease_risk_alert(farmer_for(rec["field_id"]), d)
        )

    loaded["advisories"] = []
    for rec in data.get("advisories", []):
        a = Advisory(
            id=rec["id"], field_id=rec["field_id"], created_at=_pdt(rec["created_at"]),
            language=rec["language"], title=rec["title"], body=rec["body"],
            severity=rec["severity"], source_refs=rec.get("source_refs") or [],
        )
        loaded["advisories"].append(
            store.save_advisory(farmer_for(rec["field_id"]), a)
        )

    loaded["feedback_entries"] = []
    for rec in data.get("feedback_entries", []):
        fb = FeedbackEntry(
            id=rec["id"], farmer_id=rec["farmer_id"], advisory_id=rec["advisory_id"],
            created_at=_pdt(rec["created_at"]), rating=rec["rating"], helpful=rec["helpful"],
            comment=rec.get("comment"),
        )
        loaded["feedback_entries"].append(
            store.save_feedback_entry(rec["farmer_id"], fb)
        )

    return loaded


def verify(store, loaded: dict[str, list]) -> list[str]:
    """Reads every record back via the DataStore interface and compares
    field-for-field against what was loaded. Returns a list of mismatch
    descriptions (empty == clean round-trip)."""
    problems: list[str] = []

    for expected in loaded["farmers"]:
        actual = store.get_farmer(expected.id)
        if actual != expected:
            problems.append(f"farmer {expected.id}: {actual} != {expected}")

    field_owner = {f.id: f.farmer_id for f in loaded["fields"]}
    for expected in loaded["fields"]:
        actual = store.get_field(expected.farmer_id, expected.id)
        if actual != expected:
            problems.append(f"field {expected.id}: {actual} != {expected}")

    for expected in loaded["weather_readings"]:
        farmer_id = field_owner[expected.field_id]
        rows = store.list_weather_readings(farmer_id, expected.field_id, limit=100)
        if not any(r == expected for r in rows):
            problems.append(f"weather_reading {expected.id}: not found round-trip-equal")

    for expected in loaded["soil_samples"]:
        farmer_id = field_owner[expected.field_id]
        rows = store.list_soil_samples(farmer_id, expected.field_id, limit=100)
        if not any(r == expected for r in rows):
            problems.append(f"soil_sample {expected.id}: not found round-trip-equal")

    for expected in loaded["ndvi_readings"]:
        farmer_id = field_owner[expected.field_id]
        rows = store.list_ndvi_readings(farmer_id, expected.field_id, limit=100)
        if not any(r == expected for r in rows):
            problems.append(f"ndvi_reading {expected.id}: not found round-trip-equal")

    for expected in loaded["crop_recommendations"]:
        farmer_id = field_owner[expected.field_id]
        actual = store.get_latest_crop_recommendation(farmer_id, expected.field_id)
        if actual != expected:
            problems.append(f"crop_recommendation {expected.id}: {actual} != {expected}")

    for expected in loaded["irrigation_advices"]:
        farmer_id = field_owner[expected.field_id]
        actual = store.get_latest_irrigation_advice(farmer_id, expected.field_id)
        if actual != expected:
            problems.append(f"irrigation_advice {expected.id}: {actual} != {expected}")

    for expected in loaded["disease_risk_alerts"]:
        farmer_id = field_owner[expected.field_id]
        rows = store.list_disease_risk_alerts(farmer_id, expected.field_id, limit=100)
        if not any(r == expected for r in rows):
            problems.append(f"disease_risk_alert {expected.id}: not found round-trip-equal")

    advisory_owner = {}
    for expected in loaded["advisories"]:
        farmer_id = field_owner[expected.field_id]
        advisory_owner[expected.id] = farmer_id
        actual = store.get_advisory(farmer_id, expected.id)
        if actual != expected:
            problems.append(f"advisory {expected.id}: {actual} != {expected}")

    for expected in loaded["feedback_entries"]:
        rows = store.list_feedback_for_advisory(
            expected.farmer_id, expected.advisory_id, limit=100
        )
        if not any(r == expected for r in rows):
            problems.append(f"feedback_entry {expected.id}: not found round-trip-equal")

    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=["sqlite", "supabase"], default="sqlite")
    parser.add_argument("--db-path", default=None, help="SQLite file path (sqlite backend only)")
    parser.add_argument("--fixture", type=Path, default=FIXTURE_PATH)
    args = parser.parse_args(argv)

    data = json.loads(args.fixture.read_text(encoding="utf-8"))
    store = build_store(args.backend, args.db_path)

    loaded = load_fixture(store, data)
    total = sum(len(v) for v in loaded.values())
    print(f"seed_fixture: loaded {total} records across {len(loaded)} collections into {args.backend}")

    problems = verify(store, loaded)
    if problems:
        print("seed_fixture: VERIFICATION FAILED", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    print("seed_fixture: OK — all records round-tripped field-for-field")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
