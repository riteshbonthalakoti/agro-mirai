"""Wires Module 03's acquisition adapters (weather / soil / NDVI) into the
live field-creation and field-refresh paths.

Module 34 follow-up 2: before this module, `WeatherAdapter`, `SoilAdapter`,
and `NDVIAdapter` were real, tested, and completely unused by the live
Flask app -- a brand new field had zero weather/soil/NDVI data until
someone manually ran a seeding script. This module closes that gap.

Sync vs background, decided from a real measurement (see
`decisions/` note in PROGRESS.md Module 34 entry), run against a real
Bellary coordinate (15.1394, 76.9214) on 2026-09-16:

    weather (Open-Meteo): ~1.3s
    soil    (SoilGrids):  ~3.5s
    ndvi    (GEE, live query failed -> cache fallback): ~9.8s

Weather+soil combined (~5s) is a tolerable synchronous add — the farmer's
weather/soil data is ready the moment Add-Field succeeds. NDVI is the
outlier (GEE's own live query can run close to its own 20s timeout
before falling back to cache) and is fired in a background thread instead,
so Add-Field doesn't force the farmer to wait up to ~20s for a single
satellite reading. Each of the three calls is wrapped in its own
try/except (degrade-not-fail, CLAUDE.md hard rule #4 generalized to all
three sources) -- one adapter failing never loses the other two's real
data, and never blocks field creation itself.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any

from agro_mirai.acquisition.base import FieldInput
from agro_mirai.acquisition.earth_engine import NDVIAdapter
from agro_mirai.acquisition.open_meteo import WeatherAdapter
from agro_mirai.acquisition.openweathermap import OpenWeatherMapAdapter
from agro_mirai.acquisition.soilgrids import SoilAdapter
from agro_mirai.persistence.models import NDVIReading, SoilSample, WeatherReading

logger = logging.getLogger("agro_mirai.api.field_data_acquisition")

# days of recent observed weather pulled with the forecast; the soil water
# balance needs a few weeks of rain/heat, not just today
HISTORY_DAYS = 30
# don't re-hit the weather API for the same field more often than this
_REFRESH_MIN_GAP_S = 3 * 3600
_last_refresh: dict[str, float] = {}


def _parse_dt(value: str) -> datetime:
    # Adapters emit either "...Z" or a plain ISO string; both parse via
    # fromisoformat once "Z" is normalized to "+00:00".
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _weather_reading_from_row(row: dict[str, Any]) -> WeatherReading:
    return WeatherReading(
        id=row["id"],
        field_id=row["field_id"],
        observed_at=_parse_dt(row["observed_at"]),
        source=row["source"],
        temp_c=row["temp_c"],
        is_forecast=row["is_forecast"],
        temp_min_c=row.get("temp_min_c"),
        temp_max_c=row.get("temp_max_c"),
        humidity_pct=row.get("humidity_pct"),
        rainfall_mm=row.get("rainfall_mm"),
        wind_mps=row.get("wind_mps"),
    )


def _soil_sample_from_row(row: dict[str, Any]) -> SoilSample:
    return SoilSample(
        id=row["id"],
        field_id=row["field_id"],
        observed_at=_parse_dt(row["observed_at"]),
        source=row["source"],
        ph=row.get("ph"),
        nitrogen_mg_per_kg=row.get("nitrogen_mg_per_kg"),
        phosphorus_mg_per_kg=row.get("phosphorus_mg_per_kg"),
        potassium_mg_per_kg=row.get("potassium_mg_per_kg"),
        organic_carbon_pct=row.get("organic_carbon_pct"),
        moisture_pct=row.get("moisture_pct"),
    )


def _ndvi_reading_from_row(row: dict[str, Any]) -> NDVIReading:
    return NDVIReading(
        id=row["id"],
        field_id=row["field_id"],
        observed_at=_parse_dt(row["observed_at"]),
        source=row["source"],
        ndvi=row["ndvi"],
        cloud_cover_pct=row.get("cloud_cover_pct"),
        satellite=row.get("satellite"),
    )


def _fallback_weather_rows(field_input: FieldInput) -> list[dict[str, Any]]:
    """Open-Meteo is refusing us: current conditions from OpenWeatherMap,
    observed history from NASA POWER and the forecast from MET Norway, all
    three fetched in parallel. Any subset is fine; [] only if all fail."""
    from concurrent.futures import ThreadPoolExecutor

    from agro_mirai.acquisition import weather_fallbacks as wf

    def current() -> list[dict[str, Any]]:
        try:
            rows = OpenWeatherMapAdapter().fetch(field_input)
            for row in rows:
                # a single current reading reports min == max == temp, which would
                # read as "no day/night swing" in the ET0 balance; drop them
                if row.get("temp_min_c") == row.get("temp_max_c"):
                    row.pop("temp_min_c", None)
                    row.pop("temp_max_c", None)
            return rows
        except Exception as exc:  # noqa: BLE001
            logger.warning("OpenWeatherMap failed field=%s (%s: %s)", field_input.field_id, type(exc).__name__, exc)
            return []

    lat, lon, fid = field_input.latitude, field_input.longitude, field_input.field_id
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [
            pool.submit(current),
            pool.submit(wf.nasa_power_history, lat, lon, fid, HISTORY_DAYS),
            pool.submit(wf.metno_forecast, lat, lon, fid),
        ]
        results = [f.result() for f in futures]
    rows = [r for part in results for r in part]
    logger.info(
        "weather fallback field=%s current=%d history=%d forecast=%d",
        fid, len(results[0]), len(results[1]), len(results[2]),
    )
    return rows


def fetch_and_save_weather(store, farmer_id: str, field_input: FieldInput) -> bool:
    """Fetch+persist weather rows for a field. Returns True on success,
    False (logged, never raised) on any adapter/store failure."""
    rows = None
    try:
        rows = WeatherAdapter(past_days=HISTORY_DAYS).fetch(field_input)
    except Exception as exc:  # noqa: BLE001 — degrade-not-fail per adapter
        # Open-Meteo rate-limits shared hosting IPs (429 "daily limit
        # exceeded" seen on Render), so use the backup sources.
        logger.warning(
            "weather primary source failed field=%s (%s: %s); trying backup sources",
            field_input.field_id, type(exc).__name__, exc,
        )
        rows = _fallback_weather_rows(field_input)
        if not rows:
            logger.warning("weather acquisition failed field=%s (all sources)", field_input.field_id)
            return False
    try:
        for row in rows:
            store.save_weather_reading(farmer_id, _weather_reading_from_row(row))
        logger.info(
            "weather acquisition ok field=%s rows=%d source=%s",
            field_input.field_id, len(rows), rows[0].get("source") if rows else "-",
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "weather save failed field=%s (%s: %s)", field_input.field_id, type(exc).__name__, exc
        )
        return False


def fetch_and_save_soil(store, farmer_id: str, field_input: FieldInput) -> bool:
    try:
        rows = SoilAdapter().fetch(field_input)
        for row in rows:
            store.save_soil_sample(farmer_id, _soil_sample_from_row(row))
        logger.info("soil acquisition ok field=%s rows=%d", field_input.field_id, len(rows))
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "soil acquisition failed field=%s (%s: %s)",
            field_input.field_id, type(exc).__name__, exc,
        )
        return False


def fetch_and_save_ndvi(store, farmer_id: str, field_input: FieldInput) -> bool:
    try:
        rows = NDVIAdapter().fetch(field_input)
        for row in rows:
            store.save_ndvi_reading(farmer_id, _ndvi_reading_from_row(row))
        logger.info("ndvi acquisition ok field=%s rows=%d", field_input.field_id, len(rows))
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "ndvi acquisition failed field=%s (%s: %s)",
            field_input.field_id, type(exc).__name__, exc,
        )
        return False


def acquire_field_data(store, farmer_id: str, field_id: str, latitude: float, longitude: float) -> dict[str, bool]:
    """Sync weather+soil (fast, ~5s combined measured), background NDVI
    (slow, GEE can run close to its own 20s timeout before cache fallback).

    Returns the sync-path results immediately: {"weather": bool, "soil": bool}.
    NDVI's result is not known synchronously — it is fired in a daemon
    thread and merely logged when it finishes, per the sync-vs-background
    decision above. Callers (create_field / refresh-data) should tell the
    client NDVI may still be catching up.
    """
    field_input = FieldInput(latitude=latitude, longitude=longitude, field_id=field_id)

    results = {
        "weather": fetch_and_save_weather(store, farmer_id, field_input),
        "soil": fetch_and_save_soil(store, farmer_id, field_input),
    }

    def _bg_ndvi() -> None:
        fetch_and_save_ndvi(store, farmer_id, field_input)

    threading.Thread(target=_bg_ndvi, daemon=True, name=f"ndvi-fetch-{field_id}").start()

    def _bg_rain() -> None:
        # warms the 12-month rainfall cache so the first crop suggestion is fast
        try:
            from agro_mirai.acquisition.open_meteo import annual_rainfall_mm

            annual_rainfall_mm(latitude, longitude, timeout_s=15.0)
        except Exception:  # noqa: BLE001
            pass

    threading.Thread(target=_bg_rain, daemon=True, name=f"rain-warm-{field_id}").start()

    return results


def ensure_fresh_weather(store, farmer_id: str, field, as_of, weather_rows) -> bool:
    """Refetch weather when what we hold is stale or has no history.

    Stale = nothing for today. No history = fewer than 7 distinct observed
    days in the last 14 (old fields only ever got today + forecast). At most
    once per _REFRESH_MIN_GAP_S per field, and never raises. Returns True if
    new rows were saved."""
    import time

    days = {w.observed_at.date() for w in weather_rows}
    today = as_of
    recent = [d for d in days if 0 <= (today - d).days < 14]
    stale = today not in days
    thin = len(recent) < 7
    if not (stale or thin):
        return False
    now = time.monotonic()
    if now - _last_refresh.get(field.id, -1e9) < _REFRESH_MIN_GAP_S:
        return False
    _last_refresh[field.id] = now
    return fetch_and_save_weather(
        store, farmer_id, FieldInput(latitude=field.latitude, longitude=field.longitude, field_id=field.id)
    )
