"""Parity contract suite — same assertions against every ``DataStore``.

Per ``specs/core/repository-interface.md`` §Testing contract: one suite,
run against both backends via a parametrized fixture. SQLite always
runs (in-memory, no setup needed). Supabase is skipped cleanly
(``pytest.mark.skipif``-equivalent via fixture-level ``pytest.skip``)
when ``SUPABASE_URL`` / ``SUPABASE_KEY`` are not set — it must never fail
the suite just because credentials are absent.

Uses the golden fixture id conventions (`specs/domains/fixtures/farm-001.json`)
as a source of realistic values, but each test mints its own fresh UUIDs
so tests don't collide with each other or with a real Supabase project's
existing data.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from agro_mirai.persistence.models import (
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
from agro_mirai.persistence.sqlite_store import SQLiteDataStore
from agro_mirai.persistence.store import NotFoundError


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


@pytest.fixture(params=["sqlite", "supabase"])
def store(request):
    backend = request.param
    if backend == "sqlite":
        s = SQLiteDataStore(":memory:")
        yield s
        s.close()
        return

    # backend == "supabase"
    if not (os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_KEY")):
        pytest.skip("SUPABASE_URL/SUPABASE_KEY not set — skipping Supabase parity tests")
    from agro_mirai.persistence.supabase_store import SupabaseDataStore

    s = SupabaseDataStore()
    if not s.ping():
        pytest.skip("Supabase project unreachable (may be auto-paused) — skipping")
    yield s


@pytest.fixture
def farmer(store) -> Farmer:
    # Phone must be unique per test run against a backend with a live
    # unique constraint on phone (migrations/postgres/005_phone_unique.sql) —
    # a fixed phone here would collide across tests within the same run.
    f = Farmer(
        id=_new_uuid(),
        created_at=_now(),
        updated_at=_now(),
        name="Ravi Kumar",
        preferred_language="kn",
        phone=f"+91{_new_uuid().replace('-', '')[:10]}",
        district="Bellary",
        state="Karnataka",
    )
    saved = store.save_farmer(f)
    yield saved
    # No delete_farmer in the repository interface (farmers aren't meant to
    # be deleted via the app) -- for the Supabase backend specifically,
    # clean up the raw row directly so live test runs don't accumulate data.
    client = getattr(store, "_client", None)
    if client is not None:
        client.table("farmers").delete().eq("id", saved.id).execute()


@pytest.fixture
def field(store, farmer) -> Field_:
    fl = Field_(
        id=_new_uuid(),
        farmer_id=farmer.id,
        created_at=_now(),
        updated_at=_now(),
        name="North Plot",
        latitude=15.1394,
        longitude=76.9214,
        area_ha=1.75,
        soil_type="red",
        current_crop="cotton",
    )
    return store.save_field(farmer.id, fl)


class TestFarmer:
    def test_save_and_get_round_trips(self, store, farmer):
        got = store.get_farmer(farmer.id)
        assert got is not None
        assert got.id == farmer.id
        assert got.name == "Ravi Kumar"
        assert got.preferred_language == "kn"

    def test_get_missing_returns_none(self, store):
        assert store.get_farmer(_new_uuid()) is None

    def test_save_is_upsert(self, store, farmer):
        farmer.name = "Ravi K."
        updated = store.save_farmer(farmer)
        assert updated.name == "Ravi K."
        assert store.get_farmer(farmer.id).name == "Ravi K."


class TestField:
    def test_save_and_get(self, store, farmer, field):
        got = store.get_field(farmer.id, field.id)
        assert got is not None
        assert got.name == "North Plot"
        assert got.area_ha == 1.75

    def test_list_fields(self, store, farmer, field):
        fields = store.list_fields(farmer.id)
        assert any(f.id == field.id for f in fields)

    def test_save_field_unknown_farmer_raises(self, store):
        fl = Field_(
            id=_new_uuid(),
            farmer_id=_new_uuid(),
            created_at=_now(),
            updated_at=_now(),
            name="Ghost Plot",
            latitude=1.0,
            longitude=1.0,
            area_ha=1.0,
        )
        with pytest.raises(NotFoundError):
            store.save_field(fl.farmer_id, fl)

    def test_delete_field(self, store, farmer, field):
        assert store.delete_field(farmer.id, field.id) is True
        assert store.get_field(farmer.id, field.id) is None
        assert store.delete_field(farmer.id, field.id) is False


class TestWeatherReading:
    def test_save_and_list(self, store, farmer, field):
        r = WeatherReading(
            id=_new_uuid(),
            field_id=field.id,
            observed_at=_now(),
            source="open_meteo",
            temp_c=25.0,
            is_forecast=False,
            humidity_pct=70.0,
            rainfall_mm=0.0,
        )
        saved = store.save_weather_reading(farmer.id, r)
        assert saved.temp_c == 25.0
        readings = store.list_weather_readings(farmer.id, field.id)
        assert any(x.id == saved.id for x in readings)

    def test_since_filter(self, store, farmer, field):
        old = WeatherReading(
            id=_new_uuid(), field_id=field.id,
            observed_at=_now() - timedelta(days=10),
            source="open_meteo", temp_c=20.0, is_forecast=False,
        )
        new = WeatherReading(
            id=_new_uuid(), field_id=field.id,
            observed_at=_now(),
            source="open_meteo", temp_c=27.0, is_forecast=False,
        )
        store.save_weather_reading(farmer.id, old)
        store.save_weather_reading(farmer.id, new)
        since = _now() - timedelta(days=1)
        recent = store.list_weather_readings(farmer.id, field.id, since=since)
        ids = {r.id for r in recent}
        assert new.id in ids
        assert old.id not in ids


class TestSoilSample:
    def test_save_and_list(self, store, farmer, field):
        s = SoilSample(
            id=_new_uuid(), field_id=field.id, observed_at=_now(),
            source="lab_report", ph=6.8, nitrogen_mg_per_kg=45.0,
        )
        saved = store.save_soil_sample(farmer.id, s)
        assert saved.ph == 6.8
        assert any(x.id == saved.id for x in store.list_soil_samples(farmer.id, field.id))


class TestNDVIReading:
    def test_save_and_list(self, store, farmer, field):
        n = NDVIReading(
            id=_new_uuid(), field_id=field.id, observed_at=_now(),
            source="gee_live", ndvi=0.62, satellite="sentinel-2",
        )
        saved = store.save_ndvi_reading(farmer.id, n)
        assert saved.ndvi == 0.62
        assert any(x.id == saved.id for x in store.list_ndvi_readings(farmer.id, field.id))


class TestCropRecommendation:
    def test_save_and_get_latest(self, store, farmer, field):
        rec = CropRecommendation(
            id=_new_uuid(), field_id=field.id, created_at=_now(),
            recommended_crop="cotton", confidence=0.82,
            alternatives=["maize", "pigeonpeas"], season="kharif",
        )
        saved = store.save_crop_recommendation(farmer.id, rec)
        latest = store.get_latest_crop_recommendation(farmer.id, field.id)
        assert latest is not None
        assert latest.id == saved.id
        assert latest.alternatives == ["maize", "pigeonpeas"]

    def test_regional_suitability_fields_round_trip(self, store, farmer, field):
        # Real bug found live (Module 18's out_of_region/regional_alternative
        # silently dropped on every save) -- explicit round-trip coverage so
        # it can't regress silently again.
        rec = CropRecommendation(
            id=_new_uuid(), field_id=field.id, created_at=_now(),
            recommended_crop="grapes", confidence=0.25,
            alternatives=["muskmelon", "mothbeans"], season="kharif",
            out_of_region=True, regional_alternative="cotton",
        )
        saved = store.save_crop_recommendation(farmer.id, rec)
        assert saved.out_of_region is True
        assert saved.regional_alternative == "cotton"
        latest = store.get_latest_crop_recommendation(farmer.id, field.id)
        assert latest.out_of_region is True
        assert latest.regional_alternative == "cotton"


class TestIrrigationAdvice:
    def test_save_and_get_latest(self, store, farmer, field):
        adv = IrrigationAdvice(
            id=_new_uuid(), field_id=field.id, created_at=_now(),
            recommended_depth_mm=12.0,
            window_start_at=_now(), window_end_at=_now() + timedelta(hours=3),
            urgency="moderate",
        )
        saved = store.save_irrigation_advice(farmer.id, adv)
        latest = store.get_latest_irrigation_advice(farmer.id, field.id)
        assert latest is not None
        assert latest.id == saved.id


class TestDiseaseRiskAlert:
    def test_save_and_list(self, store, farmer, field):
        alert = DiseaseRiskAlert(
            id=_new_uuid(), field_id=field.id, created_at=_now(),
            disease="cotton_bollworm", risk_level="moderate", confidence=0.71,
        )
        saved = store.save_disease_risk_alert(farmer.id, alert)
        assert any(x.id == saved.id for x in store.list_disease_risk_alerts(farmer.id, field.id))


class TestAdvisoryAndFeedback:
    def test_advisory_round_trip(self, store, farmer, field):
        adv = Advisory(
            id=_new_uuid(), field_id=field.id, created_at=_now(),
            language="kn", title="Irrigation + pest watch",
            body="Irrigate 12mm today.", severity="moderate",
            source_refs=[_new_uuid()],
        )
        saved = store.save_advisory(farmer.id, adv)
        fetched = store.get_advisory(farmer.id, saved.id)
        assert fetched is not None
        assert fetched.title == "Irrigation + pest watch"
        listed = store.list_advisories_for_field(farmer.id, field.id)
        assert any(x.id == saved.id for x in listed)

    def test_feedback_round_trip(self, store, farmer, field):
        adv = Advisory(
            id=_new_uuid(), field_id=field.id, created_at=_now(),
            language="kn", title="T", body="B", severity="low",
        )
        saved_adv = store.save_advisory(farmer.id, adv)
        entry = FeedbackEntry(
            id=_new_uuid(), farmer_id=farmer.id, advisory_id=saved_adv.id,
            created_at=_now(), rating=4, helpful=True, comment="Good timing.",
        )
        saved = store.save_feedback_entry(farmer.id, entry)
        assert saved.rating == 4
        listed = store.list_feedback_for_advisory(farmer.id, saved_adv.id)
        assert any(x.id == saved.id for x in listed)

    def test_feedback_unknown_advisory_raises(self, store, farmer, field):
        entry = FeedbackEntry(
            id=_new_uuid(), farmer_id=farmer.id, advisory_id=_new_uuid(),
            created_at=_now(), rating=3, helpful=False,
        )
        with pytest.raises(NotFoundError):
            store.save_feedback_entry(farmer.id, entry)


class TestHealth:
    def test_ping(self, store):
        assert store.ping() is True
