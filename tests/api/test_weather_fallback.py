"""Open-Meteo returns 429 ("daily limit exceeded") for Render's shared
outbound IPs, which left every new field with no weather and made all three
models fail with NO_WEATHER_DATA. ``fetch_and_save_weather`` must fall back to
OpenWeatherMap. Both adapters are mocked: no live network."""
from __future__ import annotations

from unittest.mock import MagicMock

from agro_mirai.acquisition.base import FieldInput, SourceResponseError
from agro_mirai.api import field_data_acquisition as acq


def _row(source, tmin=None, tmax=None):
    row = {
        "id": "w1", "field_id": "f1", "observed_at": "2026-09-21T10:00:00Z",
        "source": source, "temp_c": 23.0, "is_forecast": False,
    }
    if tmin is not None:
        row["temp_min_c"], row["temp_max_c"] = tmin, tmax
    return row


def _fi():
    return FieldInput(latitude=15.1, longitude=76.9, field_id="f1")


def _patch(monkeypatch, primary, fallback):
    monkeypatch.setattr(acq, "WeatherAdapter", lambda: primary)
    monkeypatch.setattr(acq, "OpenWeatherMapAdapter", lambda: fallback)


def _adapter(result):
    a = MagicMock()
    if isinstance(result, Exception):
        a.fetch.side_effect = result
    else:
        a.fetch.return_value = result
    return a


def test_primary_success_does_not_touch_fallback(monkeypatch):
    store = MagicMock()
    fallback = _adapter([_row("openweathermap")])
    _patch(monkeypatch, _adapter([_row("open_meteo")]), fallback)
    assert acq.fetch_and_save_weather(store, "farmer", _fi()) is True
    fallback.fetch.assert_not_called()
    assert store.save_weather_reading.call_args[0][1].source == "open_meteo"


def test_rate_limited_primary_falls_back_to_openweathermap(monkeypatch):
    store = MagicMock()
    primary = _adapter(SourceResponseError("Open-Meteo returned 429: Daily API request limit exceeded"))
    _patch(monkeypatch, primary, _adapter([_row("openweathermap", 23.0, 23.0)]))
    assert acq.fetch_and_save_weather(store, "farmer", _fi()) is True
    saved = store.save_weather_reading.call_args[0][1]
    assert saved.source == "openweathermap"
    # min == max == temp (single reading) is dropped so the +/-4C estimate applies
    assert saved.temp_min_c is None and saved.temp_max_c is None


def test_real_min_max_are_kept(monkeypatch):
    store = MagicMock()
    _patch(monkeypatch, _adapter(RuntimeError("x")), _adapter([_row("openweathermap", 20.0, 27.0)]))
    assert acq.fetch_and_save_weather(store, "farmer", _fi()) is True
    saved = store.save_weather_reading.call_args[0][1]
    assert (saved.temp_min_c, saved.temp_max_c) == (20.0, 27.0)


def test_both_sources_failing_returns_false_never_raises(monkeypatch):
    store = MagicMock()
    _patch(monkeypatch, _adapter(RuntimeError("429")), _adapter(RuntimeError("no key")))
    assert acq.fetch_and_save_weather(store, "farmer", _fi()) is False
    store.save_weather_reading.assert_not_called()


def test_store_failure_returns_false(monkeypatch):
    store = MagicMock()
    store.save_weather_reading.side_effect = RuntimeError("db down")
    _patch(monkeypatch, _adapter([_row("open_meteo")]), _adapter([]))
    assert acq.fetch_and_save_weather(store, "farmer", _fi()) is False
