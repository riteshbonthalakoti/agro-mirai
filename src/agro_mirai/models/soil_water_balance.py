"""Daily root-zone soil water balance (FAO-56 chapters 7-8, single Kc).

Replaces the old "7-day ETc minus 7-day rain" shortcut. It walks the last
few weeks of real daily weather (rain, heat, humidity, wind), tracks how
much of the crop's usable soil water is gone (depletion Dr), then looks
ahead through the forecast to say when the crop will be stressed and
whether rain is coming first. See decisions/0027.

Everything is an estimate from weather alone: nothing here knows how much
the farmer actually irrigated, so it assumes none (rain-fed).

Table values are approximate, from FAO-56 Table 22 (root depth, allowable
depletion p) and USDA-NRCS available-water ranges mapped to Indian soil
orders. They are starting points, not field measurements.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from agro_mirai.models.crop_coefficients import growth_stage_for, kc_for
from agro_mirai.models.evapotranspiration import (
    hargreaves_samani_et0,
    penman_monteith_et0,
)

# total available water per metre of soil (mm/m): field capacity - wilting point
TAW_MM_PER_M = {
    "black": 160.0,
    "alluvial": 140.0,
    "red": 90.0,
    "laterite": 100.0,
    "mountain": 130.0,
    "desert": 60.0,
    "saline": 120.0,
    "peaty": 220.0,
}
_TAW_DEFAULT = 120.0

# (max root depth m, allowable depletion fraction p) per crop
CROP_ROOT_P = {
    "rice": (0.6, 0.20), "maize": (1.2, 0.55), "cotton": (1.3, 0.65), "jute": (0.8, 0.60),
    "chickpea": (0.8, 0.50), "kidneybeans": (0.6, 0.45), "lentil": (0.8, 0.50),
    "mothbeans": (0.6, 0.50), "mungbean": (0.6, 0.45), "pigeonpeas": (1.0, 0.50),
    "blackgram": (0.6, 0.45), "muskmelon": (1.0, 0.40), "watermelon": (1.0, 0.40),
    "grapes": (1.2, 0.35), "orange": (1.1, 0.50), "apple": (1.2, 0.50),
    "pomegranate": (1.0, 0.50), "papaya": (0.9, 0.40), "banana": (0.7, 0.35),
    "mango": (1.2, 0.50), "coconut": (0.9, 0.65), "coffee": (1.0, 0.40),
}
_ROOT_P_DEFAULT = (0.8, 0.50)

# share of max root depth reached at each growth stage
_ROOT_FRACTION = {"initial": 0.35, "development": 0.65, "mid_season": 1.0, "late_season": 1.0}

_FALLOW_KC = 0.3
_SPINUP_DEPLETION_SHARE = 0.3  # start of window: soil assumed 30% used up
_MIN_EFFECTIVE_RAIN_MM = 2.0
_RAIN_EFFICIENCY = 0.85


def taw_per_m(soil_type: str | None) -> float:
    return TAW_MM_PER_M.get((soil_type or "").strip().lower(), _TAW_DEFAULT)


def effective_rain(rain_mm: float | None) -> float:
    r = rain_mm or 0.0
    return 0.0 if r < _MIN_EFFECTIVE_RAIN_MM else r * _RAIN_EFFICIENCY


def _et0_for(day: dict, lat: float, elevation_m: float) -> tuple[float, str]:
    d = date.fromisoformat(day["date"])
    doy = d.timetuple().tm_yday
    tmean, tmin, tmax = day.get("tmean"), day.get("tmin"), day.get("tmax")
    if tmean is None:
        return 4.0, "default"
    if tmin is None or tmax is None:
        tmin, tmax = tmean - 4.0, tmean + 4.0
    if day.get("rh") is not None and day.get("wind") is not None:
        return (
            penman_monteith_et0(
                temp_mean_c=tmean, temp_min_c=tmin, temp_max_c=tmax,
                rh_mean_pct=day["rh"], wind10_max_ms=day["wind"],
                latitude_deg=lat, day_of_year=doy, elevation_m=elevation_m,
            ),
            "penman_monteith",
        )
    return (
        hargreaves_samani_et0(
            temp_mean_c=tmean, temp_min_c=tmin, temp_max_c=tmax,
            latitude_deg=lat, day_of_year=doy,
        ),
        "hargreaves",
    )


@dataclass
class BalanceResult:
    crop: str | None
    stage: str
    kc: float
    taw_mm: float
    raw_mm: float
    depletion_mm: float
    et0_mm_day: float
    etc_mm_day: float
    rain_past_7d_mm: float
    rain_forecast_3d_mm: float
    rain_forecast_7d_mm: float
    days_used: int
    et0_method: str
    #: days from as_of until depletion passes RAW with no irrigation (None = not within forecast)
    stress_in_days: int | None
    #: depletion (mm) projected for each forecast day, no irrigation
    projected_depletion_mm: list[float] = field(default_factory=list)

    @property
    def depletion_share(self) -> float:
        return self.depletion_mm / self.raw_mm if self.raw_mm > 0 else 0.0


def run_balance(
    daily: list[dict],
    *,
    as_of: date,
    crop: str | None,
    days_since_sowing: int | None,
    soil_type: str | None,
    latitude: float | None,
    elevation_m: float | None = None,
) -> BalanceResult | None:
    """None when there are too few days of weather to say anything."""
    past = [d for d in daily if date.fromisoformat(d["date"]) <= as_of]
    future = [d for d in daily if date.fromisoformat(d["date"]) > as_of]
    if len(past) < 5:
        return None
    past.sort(key=lambda d: d["date"])
    future.sort(key=lambda d: d["date"])

    lat = latitude if latitude is not None else 15.0
    elev = elevation_m if elevation_m is not None else 500.0
    zr_max, p = CROP_ROOT_P.get(crop or "", _ROOT_P_DEFAULT)
    taw_m = taw_per_m(soil_type)

    def day_params(d: date):
        if crop is None or days_since_sowing is None:
            stage = growth_stage_for(crop, days_since_sowing)
            return stage, kc_for(crop, stage), zr_max * _ROOT_FRACTION[stage]
        ds = days_since_sowing - (as_of - d).days
        if ds < 0:
            return "fallow", _FALLOW_KC, 0.3
        stage = growth_stage_for(crop, ds)
        return stage, kc_for(crop, stage), zr_max * _ROOT_FRACTION[stage]

    def step(dr: float, day: dict, d: date):
        stage, kc, zr = day_params(d)
        taw = taw_m * zr
        raw = p * taw
        et0, method = _et0_for(day, lat, elev)
        # water stress reduces use once past RAW (FAO-56 Eq 84)
        ks = 1.0 if dr <= raw or taw <= raw else max(0.0, (taw - dr) / (taw - raw))
        etc = ks * kc * et0
        dr = min(max(dr - effective_rain(day.get("rain")) + etc, 0.0), taw)
        return dr, stage, kc, taw, raw, et0, etc, method

    zr0 = day_params(date.fromisoformat(past[0]["date"]))[2]
    dr = _SPINUP_DEPLETION_SHARE * taw_m * zr0
    last = None
    for day in past:
        last = step(dr, day, date.fromisoformat(day["date"]))
        dr = last[0]
    dr_now, stage, kc, taw, raw, et0, etc, method = last

    projected: list[float] = []
    stress_in = None
    dr_f = dr_now
    for i, day in enumerate(future, start=1):
        dr_f = step(dr_f, day, date.fromisoformat(day["date"]))[0]
        projected.append(dr_f)
        if stress_in is None and dr_f > raw:
            stress_in = i

    def rain_sum(rows, n):
        return sum(r.get("rain") or 0.0 for r in rows[:n])

    return BalanceResult(
        crop=crop, stage=stage, kc=kc, taw_mm=taw, raw_mm=raw, depletion_mm=dr_now,
        et0_mm_day=et0, etc_mm_day=etc,
        rain_past_7d_mm=rain_sum(list(reversed(past)), 7),
        rain_forecast_3d_mm=rain_sum(future, 3),
        rain_forecast_7d_mm=rain_sum(future, 7),
        days_used=len(past), et0_method=method,
        stress_in_days=stress_in, projected_depletion_mm=projected,
    )
