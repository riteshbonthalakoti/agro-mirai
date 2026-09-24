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


def _patch(monkeypatch, primary, fallback, history=None, forecast=None):
    from agro_mirai.acquisition import weather_fallbacks as wf

    monkeypatch.setattr(acq, "WeatherAdapter", lambda **kw: primary)
    monkeypatch.setattr(acq, "OpenWeatherMapAdapter", lambda: fallback)
    # no live network from these tests
    monkeypatch.setattr(wf, "nasa_power_history", lambda *a, **k: history or [])
    monkeypatch.setattr(wf, "metno_forecast", lambda *a, **k: forecast or [])


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
    assert store.save_weather_readings.call_args[0][1][0].source == "open_meteo"


def test_rate_limited_primary_falls_back_to_openweathermap(monkeypatch):
    store = MagicMock()
    primary = _adapter(SourceResponseError("Open-Meteo returned 429: Daily API request limit exceeded"))
    _patch(monkeypatch, primary, _adapter([_row("openweathermap", 23.0, 23.0)]))
    assert acq.fetch_and_save_weather(store, "farmer", _fi()) is True
    saved = store.save_weather_readings.call_args[0][1][0]
    assert saved.source == "openweathermap"
    # min == max == temp (single reading) is dropped so the +/-4C estimate applies
    assert saved.temp_min_c is None and saved.temp_max_c is None


def test_real_min_max_are_kept(monkeypatch):
    store = MagicMock()
    _patch(monkeypatch, _adapter(RuntimeError("x")), _adapter([_row("openweathermap", 20.0, 27.0)]))
    assert acq.fetch_and_save_weather(store, "farmer", _fi()) is True
    saved = store.save_weather_readings.call_args[0][1][0]
    assert (saved.temp_min_c, saved.temp_max_c) == (20.0, 27.0)


def test_both_sources_failing_returns_false_never_raises(monkeypatch):
    store = MagicMock()
    _patch(monkeypatch, _adapter(RuntimeError("429")), _adapter(RuntimeError("no key")))
    assert acq.fetch_and_save_weather(store, "farmer", _fi()) is False
    store.save_weather_readings.assert_not_called()


def test_store_failure_returns_false(monkeypatch):
    store = MagicMock()
    store.save_weather_readings.side_effect = RuntimeError("db down")
    store.save_weather_reading.side_effect = RuntimeError("db down")
    _patch(monkeypatch, _adapter([_row("open_meteo")]), _adapter([]))
    assert acq.fetch_and_save_weather(store, "farmer", _fi()) is False


def test_backup_chain_combines_current_history_and_forecast(monkeypatch):
    store = MagicMock()
    hist = [dict(_row("nasa_power"), id=f"h{i}") for i in range(3)]
    fc = [dict(_row("met_norway"), id="m1", is_forecast=True)]
    _patch(monkeypatch, _adapter(RuntimeError("429")), _adapter([_row("openweathermap")]), hist, fc)
    assert acq.fetch_and_save_weather(store, "farmer", _fi()) is True
    sources = sorted(r.source for r in store.save_weather_readings.call_args[0][1])
    assert sources == ["met_norway", "nasa_power", "nasa_power", "nasa_power", "openweathermap"]


def test_history_and_forecast_alone_are_enough(monkeypatch):
    store = MagicMock()
    _patch(monkeypatch, _adapter(RuntimeError("429")), _adapter(RuntimeError("no key")),
           [dict(_row("nasa_power"), id="h1")], [])
    assert acq.fetch_and_save_weather(store, "farmer", _fi()) is True


def test_bulk_failure_falls_back_to_row_by_row_and_keeps_going(monkeypatch):
    store = MagicMock()
    store.save_weather_readings.side_effect = RuntimeError("bulk broke")
    calls = {"n": 0}

    def flaky(farmer_id, reading):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("Server disconnected")

    store.save_weather_reading.side_effect = flaky
    hist = [dict(_row("nasa_power"), id=f"h{i}", observed_at=f"2026-09-0{i + 1}T00:00:00Z") for i in range(4)]
    _patch(monkeypatch, _adapter(RuntimeError("429")), _adapter([]), hist, [])
    assert acq.fetch_and_save_weather(store, "farmer", _fi()) is True
    assert calls["n"] == 4  # one failure did not stop the rest


def test_history_days_we_already_hold_are_not_saved_again(monkeypatch):
    from datetime import datetime, timezone

    store = MagicMock()
    have = MagicMock(is_forecast=False, observed_at=datetime(2026, 9, 1, tzinfo=timezone.utc))
    store.list_weather_readings.return_value = [have]
    hist = [dict(_row("nasa_power"), id=f"h{i}", observed_at=f"2026-09-0{i + 1}T00:00:00Z") for i in range(3)]
    _patch(monkeypatch, _adapter(RuntimeError("429")), _adapter([]), hist, [])
    assert acq.fetch_and_save_weather(store, "farmer", _fi()) is True
    saved_dates = [r.observed_at.day for r in store.save_weather_readings.call_args[0][1]]
    assert saved_dates == [2, 3]
