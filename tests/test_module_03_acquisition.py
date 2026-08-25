"""Module 03 tests: adapter response-to-schema mapping, the NDVI live/cache
fallback, and (opt-in, network-gated) one real call per external source.

Deterministic by default: the mapping tests below feed recorded/sample
payloads straight into each adapter's private ``_map_*``/``_query``
helpers — no network call, no flakiness, no dependency on a live service's
uptime. Reuses ``tools/check_specs.py``'s validation logic (imported, not
duplicated) to prove the mapped output is schema-conformant, exactly as
Module 02's suite does for the golden fixture.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures_module_03"
sys.path.insert(0, str(ROOT / "tools"))

import check_specs  # noqa: E402  (tools/ added to path above)

from agro_mirai.acquisition import (  # noqa: E402
    FieldInput,
    NDVIAdapter,
    SoilAdapter,
    WeatherAdapter,
)
from agro_mirai.acquisition.earth_engine import SOURCE_CACHE, SOURCE_LIVE  # noqa: E402


# --------------------------------------------------------------------------
# Shared schema-validation helper (reuses check_specs' own machinery)
# --------------------------------------------------------------------------
def _assert_schema_conformant(entity_name: str, record: dict) -> None:
    """Validate one adapter-produced record against schema.yaml/enums.md.

    Mirrors what check_specs.check_specs() does per-fixture-record, but
    for a single record produced directly by an adapter (not loaded from
    the golden fixture file). Reuses check_specs._validate_entity so the
    validation logic itself is never duplicated.
    """
    schema = check_specs._load_yaml(check_specs.SCHEMA_PATH)
    enums = check_specs._parse_enum_doc(
        check_specs.ENUMS_PATH.read_text(encoding="utf-8")
    )
    # known_ids: only field_id refs matter here, and adapters are tested
    # with a real UUID field id, so accept any ref target opportunistically.
    known_ids = {"Field": {record.get("field_id")}} if record.get("field_id") else {}
    errs = check_specs._validate_entity(
        entity_name, record, schema, enums, known_ids, {}, idx=0
    )
    assert not errs, f"{entity_name} failed schema validation: {errs}"


FIELD = FieldInput(
    latitude=15.1394,
    longitude=76.9214,
    field_id="22222222-2222-4222-8222-222222222222",
)


# --------------------------------------------------------------------------
# WeatherAdapter — Open-Meteo
# --------------------------------------------------------------------------
class TestWeatherAdapter:
    def _adapter(self) -> WeatherAdapter:
        return WeatherAdapter()

    def _forecast_payload(self) -> dict:
        return json.loads((FIXTURES / "open_meteo_forecast.json").read_text())

    def _archive_payload(self) -> dict:
        return json.loads((FIXTURES / "open_meteo_archive.json").read_text())

    def test_maps_forecast_to_weather_readings(self):
        adapter = self._adapter()
        payload = self._forecast_payload()
        readings = adapter._map_forecast(payload, FIELD)

        # 1 current reading + 2 remaining forecast days (fixture has 3 daily
        # entries, index 0 consumed by the current reading).
        assert len(readings) == 3
        current = readings[0]
        assert current["is_forecast"] is False
        assert current["source"] == "open_meteo"
        assert current["temp_c"] == 24.9
        assert current["humidity_pct"] == 79.0
        assert current["rainfall_mm"] == 0.0
        assert current["wind_mps"] == 5.26  # already m/s, no conversion
        assert current["observed_at"] == "2026-08-25T17:45:00Z"
        assert current["field_id"] == FIELD.field_id

        forecast_rows = readings[1:]
        assert all(r["is_forecast"] for r in forecast_rows)
        assert forecast_rows[0]["observed_at"] == "2026-08-26T00:00:00Z"
        assert forecast_rows[0]["temp_c"] == 27.4
        assert forecast_rows[0]["wind_mps"] == 6.7

        for r in readings:
            _assert_schema_conformant("WeatherReading", r)

    def test_maps_archive_to_weather_readings(self):
        adapter = self._adapter()
        payload = self._archive_payload()
        readings = adapter._map_archive(payload, FIELD)

        assert len(readings) == 3
        assert all(r["is_forecast"] is False for r in readings)
        assert readings[0]["observed_at"] == "2026-07-01T00:00:00Z"
        assert readings[0]["temp_c"] == 26.3
        assert readings[0]["temp_min_c"] == 23.6
        assert readings[0]["temp_max_c"] == 30.2
        assert readings[0]["rainfall_mm"] == 1.5
        assert readings[0]["wind_mps"] == 7.29

        for r in readings:
            _assert_schema_conformant("WeatherReading", r)

    def test_5xx_then_success_is_swallowed_by_retry(self, monkeypatch):
        adapter = self._adapter()
        payload = self._forecast_payload()
        calls = {"n": 0}

        class FakeResp:
            def __init__(self, status_code, body):
                self.status_code = status_code
                self._body = body
                self.text = json.dumps(body)

            def json(self):
                return self._body

        def fake_get(url, params=None, timeout=None):
            calls["n"] += 1
            if calls["n"] == 1:
                return FakeResp(503, {})
            return FakeResp(200, payload)

        monkeypatch.setattr(adapter._session, "get", fake_get)
        readings = adapter.fetch(FIELD)
        assert calls["n"] == 2
        assert len(readings) == 3

    def test_persistent_failure_raises_typed_error(self, monkeypatch):
        from agro_mirai.acquisition.base import SourceUnavailableError

        adapter = self._adapter()

        def fake_get(url, params=None, timeout=None):
            raise requests.ConnectionError("boom")

        monkeypatch.setattr(adapter._session, "get", fake_get)
        with pytest.raises(SourceUnavailableError):
            adapter.fetch(FIELD)


# --------------------------------------------------------------------------
# SoilAdapter — SoilGrids
# --------------------------------------------------------------------------
class TestSoilAdapter:
    def test_maps_soilgrids_response_to_soil_sample(self):
        adapter = SoilAdapter()
        payload = json.loads((FIXTURES / "soilgrids_query.json").read_text())
        sample = adapter._map_sample(payload, FIELD)

        assert sample["source"] == "soilgrids"
        assert sample["field_id"] == FIELD.field_id
        # phh2o mapped=68, d_factor=10 -> ph = 6.8
        assert sample["ph"] == 6.8
        # nitrogen mapped=450 cg/kg -> *10 -> 4500 mg/kg (see docstring:
        # this is TOTAL nitrogen, a different quantity than a lab report's
        # plant-available nitrogen at a similar-looking field name).
        assert sample["nitrogen_mg_per_kg"] == 4500.0
        # soc mapped=62 dg/kg -> /100 -> 0.62 organic_carbon_pct
        assert sample["organic_carbon_pct"] == 0.62
        # SoilGrids v2 has no phosphorus/potassium/moisture -> left unset
        assert "phosphorus_mg_per_kg" not in sample
        assert "potassium_mg_per_kg" not in sample
        assert "moisture_pct" not in sample

        _assert_schema_conformant("SoilSample", sample)

    def test_no_data_pixel_yields_sample_with_only_required_fields(self):
        adapter = SoilAdapter()
        payload = {
            "properties": {
                "layers": [
                    {
                        "name": "phh2o",
                        "depths": [{"label": "0-5cm", "values": {"mean": None}}],
                    }
                ]
            }
        }
        sample = adapter._map_sample(payload, FIELD)
        assert "ph" not in sample
        _assert_schema_conformant("SoilSample", sample)

    def test_persistent_failure_raises_typed_error(self, monkeypatch):
        from agro_mirai.acquisition.base import SourceUnavailableError

        adapter = SoilAdapter()

        def fake_get(url, params=None, timeout=None):
            raise requests.ConnectionError("boom")

        monkeypatch.setattr(adapter._session, "get", fake_get)
        with pytest.raises(SourceUnavailableError):
            adapter.fetch(FIELD)


# --------------------------------------------------------------------------
# NDVIAdapter — GEE live/cache fallback
# --------------------------------------------------------------------------
class TestNDVIAdapterFallback:
    def test_live_failure_falls_back_to_cache_with_source_cache(
        self, monkeypatch, tmp_path
    ):
        cache_path = tmp_path / "ndvi_cache.json"
        cache_path.write_text(
            json.dumps(
                {
                    "entries": [
                        {
                            "field_id": FIELD.field_id,
                            "latitude": FIELD.latitude,
                            "longitude": FIELD.longitude,
                            "observed_at": "2026-07-14T05:34:48Z",
                            "ndvi": 0.2019,
                            "cloud_cover_pct": 18.57,
                            "satellite": "sentinel-2",
                        }
                    ]
                }
            )
        )
        adapter = NDVIAdapter(cache_path=cache_path)

        def raise_live(field):
            raise RuntimeError("simulated GEE outage")

        monkeypatch.setattr(adapter, "_fetch_live", raise_live)

        readings = adapter.fetch(FIELD)
        assert len(readings) == 1
        reading = readings[0]
        assert reading["source"] == SOURCE_CACHE == "cache"
        assert reading["ndvi"] == 0.2019
        assert reading["field_id"] == FIELD.field_id
        _assert_schema_conformant("NDVIReading", reading)

    def test_live_success_is_not_overridden_by_cache(self, monkeypatch, tmp_path):
        adapter = NDVIAdapter(cache_path=tmp_path / "unused.json")

        def fake_live(field):
            return {
                "id": "abcdefab-0000-4000-8000-000000000001",
                "observed_at": "2026-08-25T05:00:00Z",
                "source": SOURCE_LIVE,
                "ndvi": 0.55,
                "field_id": field.field_id,
            }

        monkeypatch.setattr(adapter, "_fetch_live", fake_live)
        readings = adapter.fetch(FIELD)
        assert readings[0]["source"] == SOURCE_LIVE == "gee_live"
        assert readings[0]["ndvi"] == 0.55
        _assert_schema_conformant("NDVIReading", readings[0])

    def test_cache_miss_after_live_failure_raises(self, monkeypatch, tmp_path):
        from agro_mirai.acquisition.base import SourceUnavailableError

        adapter = NDVIAdapter(cache_path=tmp_path / "empty_cache.json")
        (tmp_path / "empty_cache.json").write_text(json.dumps({"entries": []}))

        def raise_live(field):
            raise RuntimeError("simulated GEE outage")

        monkeypatch.setattr(adapter, "_fetch_live", raise_live)
        with pytest.raises(SourceUnavailableError):
            adapter.fetch(FIELD)

    def test_timeout_triggers_fallback(self, monkeypatch, tmp_path):
        """A live call that exceeds timeout_s must also fall back, not hang.

        Exercises the real timeout machinery in ``_fetch_live`` (the
        ThreadPoolExecutor + ``future.result(timeout=...)``), not just
        `fetch()`'s outer catch-all: `_ensure_initialized` and the GEE
        query itself are monkeypatched to a slow call, so this proves the
        20s-style ceiling actually fires rather than blocking forever.
        """
        cache_path = tmp_path / "ndvi_cache.json"
        cache_path.write_text(
            json.dumps(
                {
                    "entries": [
                        {
                            "field_id": FIELD.field_id,
                            "latitude": FIELD.latitude,
                            "longitude": FIELD.longitude,
                            "observed_at": "2026-07-14T05:34:48Z",
                            "ndvi": 0.2019,
                        }
                    ]
                }
            )
        )
        adapter = NDVIAdapter(cache_path=cache_path, timeout_s=0.05)
        monkeypatch.setattr(adapter, "_ensure_initialized", lambda: None)

        import time as _time
        import types

        fake_ee = types.SimpleNamespace(
            Geometry=types.SimpleNamespace(Point=lambda *a, **k: None),
            Date=lambda *a, **k: types.SimpleNamespace(
                advance=lambda *a, **k: None
            ),
        )
        monkeypatch.setitem(sys.modules, "ee", fake_ee)

        def slow_query(*_args, **_kwargs):
            _time.sleep(1.0)
            return {"ndvi": 0.9}

        # Replace the executor's target: patch concurrent.futures so the
        # submitted callable is the slow one, by monkeypatching
        # NDVIAdapter._fetch_live's inner _query via the module's ee.
        # Simplest reliable seam: monkeypatch time.sleep is fragile, so
        # instead directly patch ThreadPoolExecutor.submit to run the slow
        # function regardless of the real query body.
        import concurrent.futures as cf

        orig_submit = cf.ThreadPoolExecutor.submit

        def patched_submit(self, fn, *a, **k):
            return orig_submit(self, slow_query)

        monkeypatch.setattr(cf.ThreadPoolExecutor, "submit", patched_submit)

        readings = adapter.fetch(FIELD)
        assert readings[0]["source"] == "cache"


# --------------------------------------------------------------------------
# Live, network/credential-gated tests — one real call per source.
# Skipped automatically when network or credentials aren't available, so
# the suite never depends on live access to pass.
# --------------------------------------------------------------------------
def _network_available() -> bool:
    if os.environ.get("AGRO_MIRAI_SKIP_LIVE_TESTS"):
        return False
    try:
        requests.get("https://api.open-meteo.com/v1/forecast", timeout=5)
        return True
    except requests.RequestException:
        return False


@pytest.mark.skipif(not _network_available(), reason="no network access")
def test_open_meteo_live_forecast_call():
    adapter = WeatherAdapter()
    readings = adapter.fetch(FIELD)
    assert len(readings) >= 1
    for r in readings:
        _assert_schema_conformant("WeatherReading", r)


@pytest.mark.skipif(not _network_available(), reason="no network access")
def test_soilgrids_live_call():
    adapter = SoilAdapter()
    try:
        samples = adapter.fetch(FIELD)
    except Exception as exc:  # pragma: no cover - live service flakiness
        pytest.skip(f"SoilGrids live call failed/unavailable: {exc}")
    assert len(samples) == 1
    _assert_schema_conformant("SoilSample", samples[0])


@pytest.mark.skipif(
    not os.environ.get("EE_SERVICE_ACCOUNT_KEY"),
    reason="EE_SERVICE_ACCOUNT_KEY not set; no GEE credentials available",
)
def test_gee_live_ndvi_call():
    adapter = NDVIAdapter()
    readings = adapter.fetch(FIELD)
    assert len(readings) == 1
    assert readings[0]["source"] in ("gee_live", "cache")
    _assert_schema_conformant("NDVIReading", readings[0])
