"""Weather adapter — OpenWeatherMap (fallback source, requires an API key).

Maps OpenWeatherMap's "One Call" current+daily response to
``WeatherReading`` records (``specs/core/schema.yaml``), matching
``open_meteo.py``'s shape exactly so callers can treat the two adapters
interchangeably.

Why this exists: Open-Meteo (``open_meteo.py``) is the primary weather
source — free, no key, already proven live — per
``decisions/0025-acquisition-wiring-and-fallback-sources.md``. This
adapter is a genuine fallback, tried only when Open-Meteo fails, using a
real OpenWeatherMap API key (``OPENWEATHER_API_KEY`` env var, never
hardcoded — mirrors the ``EE_SERVICE_ACCOUNT_KEY`` convention in
``earth_engine.py``). It also closes the literal PPT Tools &
Technologies slide claim ("OpenWeatherMap") for real, rather than just
documenting around the substitution.

OpenWeatherMap's free/lite tiers only expose *current* conditions
reliably without a paid subscription (the historical/forecast "One
Call 3.0" daily array requires a paid plan) — so unlike Open-Meteo,
this adapter maps a single current-conditions reading, not a multi-day
forecast. That is a real, documented capability gap versus the primary
source, not an oversight: when this fallback fires, the field gets one
real current reading rather than a week of forecast rows, which is
enough to unblock feature-building's degrade-not-fail thresholds but
less than the primary path normally provides.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any

import requests

from .base import (
    Adapter,
    FieldInput,
    SourceResponseError,
    SourceUnavailableError,
    new_id,
)

CURRENT_WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"

DEFAULT_TIMEOUT_S = 10.0


class OpenWeatherMapAdapter(Adapter):
    """OpenWeatherMap current conditions → ``WeatherReading`` (fallback)."""

    source = "openweathermap"

    def __init__(
        self,
        api_key: str | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        session: requests.Session | None = None,
    ) -> None:
        self._api_key = api_key  # else read OPENWEATHER_API_KEY lazily
        self.timeout_s = timeout_s
        self._session = session or requests.Session()

    # -- public API --------------------------------------------------------
    def fetch(self, field: FieldInput) -> list[dict[str, Any]]:
        """Current conditions only (see module docstring for why)."""
        api_key = self._api_key or os.environ.get("OPENWEATHER_API_KEY")
        if not api_key:
            raise SourceUnavailableError(
                "OPENWEATHER_API_KEY is not set; cannot call OpenWeatherMap"
            )
        params = {
            "lat": field.latitude,
            "lon": field.longitude,
            "appid": api_key,
            "units": "metric",
        }
        payload = self._get_with_retry(CURRENT_WEATHER_URL, params)
        return [self._map_current(payload, field)]

    # -- mapping (pure) ------------------------------------------------------
    def _map_current(
        self, payload: dict[str, Any], field: FieldInput
    ) -> dict[str, Any]:
        main = payload.get("main") or {}
        if "temp" not in main:
            raise SourceResponseError(
                f"OpenWeatherMap payload missing main.temp: {payload!r}"
            )
        wind = payload.get("wind") or {}
        rain = payload.get("rain") or {}
        dt = payload.get("dt")

        reading: dict[str, Any] = {
            "id": new_id(),
            "observed_at": _epoch_to_iso(dt),
            "source": self.source,
            "temp_c": _num(main["temp"]),
            "is_forecast": False,
        }
        self._maybe(reading, "temp_min_c", main.get("temp_min"))
        self._maybe(reading, "temp_max_c", main.get("temp_max"))
        self._maybe(reading, "humidity_pct", main.get("humidity"))
        # OpenWeatherMap reports rain volume for the last 1h/3h, keyed by
        # window (e.g. "1h"); take whichever window is present.
        rain_mm = rain.get("1h", rain.get("3h"))
        self._maybe(reading, "rainfall_mm", rain_mm)
        self._maybe(reading, "wind_mps", wind.get("speed"))
        if field.field_id:
            reading["field_id"] = field.field_id
        return reading

    @staticmethod
    def _maybe(record: dict[str, Any], key: str, value: Any) -> None:
        if value is not None:
            record[key] = _num(value)

    # -- transport ---------------------------------------------------------
    def _get_with_retry(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        last_exc: Exception | None = None
        for attempt in range(2):  # initial try + one retry
            try:
                resp = self._session.get(url, params=params, timeout=self.timeout_s)
                if resp.status_code == 401:
                    # Not transient — a bad/missing key won't fix itself on retry.
                    raise SourceResponseError(
                        "OpenWeatherMap returned 401 (invalid API key)"
                    )
                if resp.status_code >= 500:
                    raise SourceUnavailableError(
                        f"OpenWeatherMap returned {resp.status_code}"
                    )
                if resp.status_code >= 400:
                    raise SourceResponseError(
                        f"OpenWeatherMap returned {resp.status_code}: {resp.text[:200]}"
                    )
                return resp.json()
            except SourceResponseError:
                raise
            except (requests.RequestException, SourceUnavailableError) as exc:
                last_exc = exc
                if attempt == 0:
                    time.sleep(0.5)
                    continue
        raise SourceUnavailableError(
            f"OpenWeatherMap unreachable after retry: {last_exc}"
        ) from last_exc


def _num(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SourceResponseError(f"expected a number, got {value!r}")
    return float(value)


def _epoch_to_iso(dt: Any) -> str:
    if dt is None:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return datetime.fromtimestamp(float(dt), tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
