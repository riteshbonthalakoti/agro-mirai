"""Backup weather sources for when Open-Meteo refuses us.

Open-Meteo's free forecast API rate-limits shared hosting IPs (HTTP 429 seen
on Render). The old fallback was OpenWeatherMap's single "current" reading,
which has no history and no forecast, so the irrigation balance had nothing
to work with. Two more free, key-less sources fill that gap:

* NASA POWER (agroclimatology community): daily observed history, about 3
  days behind real time. Coarser grid than Open-Meteo but same rain pattern.
* MET Norway locationforecast: 9-10 day forecast (hourly, then 6-hourly).

Both return rows in the same dict shape as ``WeatherAdapter`` so the caller
saves them the same way. Every function returns [] on failure and never
raises.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

import requests

from agro_mirai.acquisition.base import iso_from_date, new_id

log = logging.getLogger("agro_mirai.acquisition.weather_fallbacks")

METNO_URL = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
# MET Norway asks every client to identify itself
METNO_HEADERS = {"User-Agent": "agro-mirai-capstone/1.0 github.com/riteshbonthalakoti/agro-mirai"}
POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"

_POWER_MISSING = -999.0


def _row(day: date, field_id: str | None, *, forecast: bool, source: str, **vals: float | None) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": new_id(),
        "observed_at": iso_from_date(day.isoformat()),
        "source": source,
        "is_forecast": forecast,
    }
    for k, v in vals.items():
        if v is not None:
            row[k] = float(v)
    if field_id:
        row["field_id"] = field_id
    return row


def nasa_power_history(lat: float, lon: float, field_id: str | None, days: int = 30, timeout_s: float = 12.0) -> list[dict[str, Any]]:
    """Observed daily weather for the last ~``days`` days (newest ~3 days missing)."""
    end = date.today()
    start = end - timedelta(days=days)
    try:
        resp = requests.get(
            POWER_URL,
            params={
                "parameters": "T2M,T2M_MAX,T2M_MIN,RH2M,PRECTOTCORR,WS2M",
                "community": "AG", "longitude": lon, "latitude": lat,
                "start": start.strftime("%Y%m%d"), "end": end.strftime("%Y%m%d"), "format": "JSON",
            },
            timeout=timeout_s,
        )
        resp.raise_for_status()
        p = resp.json()["properties"]["parameter"]
        rows = []
        for key, tmean in p["T2M"].items():
            if tmean == _POWER_MISSING:
                continue
            g = lambda name: (None if p[name].get(key, _POWER_MISSING) == _POWER_MISSING else p[name][key])  # noqa: E731
            ws2 = g("WS2M")
            # downstream treats wind as the 10 m daily max; invert the 2 m mean conversion
            wind = None if ws2 is None else ws2 / (0.6 * 0.748)
            d = datetime.strptime(key, "%Y%m%d").date()
            rows.append(_row(
                d, field_id, forecast=False, source="nasa_power",
                temp_c=tmean, temp_min_c=g("T2M_MIN"), temp_max_c=g("T2M_MAX"),
                humidity_pct=g("RH2M"), rainfall_mm=g("PRECTOTCORR"), wind_mps=wind,
            ))
        rows.sort(key=lambda r: r["observed_at"])
        return rows
    except Exception as exc:  # noqa: BLE001
        log.warning("NASA POWER history failed: %s: %s", type(exc).__name__, exc)
        return []


def metno_forecast(lat: float, lon: float, field_id: str | None, timeout_s: float = 12.0) -> list[dict[str, Any]]:
    """Daily forecast rows from tomorrow (UTC) on; today is partial so it is skipped."""
    try:
        resp = requests.get(
            METNO_URL, params={"lat": round(lat, 4), "lon": round(lon, 4)},
            headers=METNO_HEADERS, timeout=timeout_s,
        )
        resp.raise_for_status()
        series = resp.json()["properties"]["timeseries"]
    except Exception as exc:  # noqa: BLE001
        log.warning("MET Norway forecast failed: %s: %s", type(exc).__name__, exc)
        return []

    today = datetime.now(timezone.utc).date()
    temps: dict[date, list[float]] = defaultdict(list)
    rh: dict[date, list[float]] = defaultdict(list)
    wind: dict[date, list[float]] = defaultdict(list)
    rain: dict[date, float] = defaultdict(float)
    for i, step in enumerate(series):
        t = datetime.fromisoformat(step["time"].replace("Z", "+00:00"))
        d = t.date()
        det = step["data"]["instant"]["details"]
        if "air_temperature" in det:
            temps[d].append(det["air_temperature"])
        if "relative_humidity" in det:
            rh[d].append(det["relative_humidity"])
        if "wind_speed" in det:
            wind[d].append(det["wind_speed"])
        nxt = step["data"]
        if "next_1_hours" in nxt:
            rain[d] += nxt["next_1_hours"]["details"].get("precipitation_amount", 0.0)
        elif "next_6_hours" in nxt:
            # 6-hourly part of the series: this step covers the next 6 h
            rain[d] += nxt["next_6_hours"]["details"].get("precipitation_amount", 0.0)

    rows = []
    for d in sorted(temps):
        if d <= today or len(temps[d]) < 2:
            continue
        rows.append(_row(
            d, field_id, forecast=True, source="met_norway",
            temp_c=sum(temps[d]) / len(temps[d]), temp_min_c=min(temps[d]), temp_max_c=max(temps[d]),
            humidity_pct=(sum(rh[d]) / len(rh[d])) if rh[d] else None,
            rainfall_mm=rain[d], wind_mps=max(wind[d]) if wind[d] else None,
        ))
    return rows


def nasa_power_annual_rain(lat: float, lon: float, timeout_s: float = 20.0) -> float | None:
    """Rain over the last year (mm) from NASA POWER, scaled if a few days are missing."""
    end = date.today()
    start = end - timedelta(days=364)
    try:
        resp = requests.get(
            POWER_URL,
            params={
                "parameters": "PRECTOTCORR", "community": "AG", "longitude": lon, "latitude": lat,
                "start": start.strftime("%Y%m%d"), "end": end.strftime("%Y%m%d"), "format": "JSON",
            },
            timeout=timeout_s,
        )
        resp.raise_for_status()
        vals = [v for v in resp.json()["properties"]["parameter"]["PRECTOTCORR"].values() if v != _POWER_MISSING]
        return sum(vals) * 365.0 / len(vals) if len(vals) >= 300 else None
    except Exception as exc:  # noqa: BLE001
        log.warning("NASA POWER annual rain failed: %s: %s", type(exc).__name__, exc)
        return None
