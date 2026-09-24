"""Reference evapotranspiration (ET0) — Hargreaves-Samani method.

Module 17: replaces the fixed urgency->depth-mm lookup table in
``irrigation_prediction_model.py`` with a physically grounded water
balance. ET0 is the rate at which a well-watered reference grass surface
loses water to the atmosphere; combined with a crop coefficient (Kc, see
``crop_coefficients.py``) it gives crop evapotranspiration (ETc), the
actual water demand a field needs replaced.

**Method choice — Hargreaves-Samani, not Penman-Monteith.** Penman-Monteith
(FAO-56's own "gold standard") needs solar radiation, wind speed, and
vapor pressure deficit (dewpoint/relative humidity at a sub-daily
resolution) — none of which this project reliably has: Open-Meteo's
history/forecast calls used elsewhere in this codebase are configured
for temp min/mean/max only (see ``docs/architecture.md`` Module 03).
Hargreaves-Samani needs only temperature (min/mean/max) and
extraterrestrial radiation, which is computable purely from latitude and
day-of-year — no sensor at all. This fits what ``Field_`` (`latitude`)
and ``FeatureVector`` (`temp_c_min_7d`/`temp_c_mean_7d`/`temp_c_max_7d`,
Module 17 additions) actually carry. Hargreaves-Samani is a well-
established FAO-endorsed alternative for exactly this data-scarce
situation (FAO-56 §K, Annex).

Reference: Allen, R.G., Pereira, L.S., Raes, D., Smith, M. (1998).
*Crop Evapotranspiration — Guidelines for computing crop water
requirements*, FAO Irrigation and Drainage Paper 56, Rome.
  - Ra (extraterrestrial radiation): FAO-56 Chapter 3, Equations 21-25.
  - Hargreaves-Samani ET0: FAO-56 Chapter 3, Equation 52 (and Annex).
"""
from __future__ import annotations

import math

# FAO-56 Eq 20: 1 mm of water evaporated corresponds to 2.45 MJ/m^2
# (latent heat of vaporization at ~20C) -> the inverse, 0.408, converts
# radiation from MJ/m^2/day to mm/day "equivalent evaporation".
_MJ_TO_MM = 0.408

# FAO-56 Eq 21/24: solar constant, MJ m^-2 min^-1.
_SOLAR_CONSTANT_MJ = 0.0820


def extraterrestrial_radiation_mj(latitude_deg: float, day_of_year: int) -> float:
    """Extraterrestrial radiation Ra (MJ m^-2 day^-1), FAO-56 Eq 21.

    ``day_of_year`` is the Julian day (1-365/366). Sign convention:
    ``latitude_deg`` is positive for the northern hemisphere, negative
    for the southern (matches ``Field_.latitude`` / standard decimal
    degrees).

    Sanity check (not asserted here, documented for reviewers): at the
    equator near an equinox (day ~80), Ra in mm/day equivalent
    (``* 0.408``) comes out close to ~15 mm/day, matching the commonly
    cited equatorial range in FAO-56 Table 2.6 — used as this module's
    golden test in ``tests/models/test_evapotranspiration.py``.
    """
    phi = math.radians(latitude_deg)
    j = day_of_year

    # Inverse relative distance Earth-Sun (Eq 23).
    dr = 1 + 0.033 * math.cos(2 * math.pi / 365 * j)
    # Solar declination, radians (Eq 24).
    delta = 0.409 * math.sin(2 * math.pi / 365 * j - 1.39)
    # Sunset hour angle, radians (Eq 25). Clamp the arccos argument for
    # polar edge cases (permanent day/night) where |x| can exceed 1 due
    # to floating point at extreme latitudes.
    x = -math.tan(phi) * math.tan(delta)
    x = max(-1.0, min(1.0, x))
    omega_s = math.acos(x)

    ra = (
        (24 * 60 / math.pi)
        * _SOLAR_CONSTANT_MJ
        * dr
        * (
            omega_s * math.sin(phi) * math.sin(delta)
            + math.cos(phi) * math.cos(delta) * math.sin(omega_s)
        )
    )
    return ra


def hargreaves_samani_et0(
    temp_mean_c: float,
    temp_min_c: float,
    temp_max_c: float,
    latitude_deg: float,
    day_of_year: int,
) -> float:
    """Reference evapotranspiration ET0 (mm/day), FAO-56 Eq 52.

    ``ET0 = 0.0023 * (Tmean + 17.8) * sqrt(Tmax - Tmin) * 0.408 * Ra``

    where Ra (MJ m^-2 day^-1) is converted to mm/day-equivalent via the
    0.408 factor (FAO-56 Eq 20) before combining, per the standard form
    of the Hargreaves-Samani equation. ``Tmax`` is clamped to be at
    least ``Tmin`` (equal, giving ET0=0 for that term) to avoid a
    negative value under ``sqrt`` on degenerate/noisy input — this
    should not happen with real Open-Meteo data but guards against it.
    """
    if temp_max_c < temp_min_c:
        temp_max_c = temp_min_c

    ra_mj = extraterrestrial_radiation_mj(latitude_deg, day_of_year)
    ra_mm = ra_mj * _MJ_TO_MM

    et0 = 0.0023 * (temp_mean_c + 17.8) * math.sqrt(temp_max_c - temp_min_c) * ra_mm
    return max(0.0, et0)


def _sat_vp_kpa(t_c: float) -> float:
    return 0.6108 * math.exp(17.27 * t_c / (t_c + 237.3))


def penman_monteith_et0(
    *,
    temp_mean_c: float,
    temp_min_c: float,
    temp_max_c: float,
    rh_mean_pct: float,
    wind10_max_ms: float,
    latitude_deg: float,
    day_of_year: int,
    elevation_m: float = 500.0,
) -> float:
    """FAO-56 Penman-Monteith ET0 (mm/day), Eq 6, for when we do have
    humidity and wind (Open-Meteo gives both daily).

    Solar radiation is not measured: it is estimated from the daily
    temperature range (Hargreaves, FAO-56 Eq 50, kRs 0.17). Wind from
    Open-Meteo is the daily MAX at 10 m, so a mean at 2 m is guessed as
    0.6 x max x 0.748 (log profile), floored at 0.5 m/s as FAO-56 advises.
    """
    ra = extraterrestrial_radiation_mj(latitude_deg, day_of_year)
    trange = max(temp_max_c - temp_min_c, 0.0)
    rso = (0.75 + 2e-5 * elevation_m) * ra
    rs = min(0.17 * math.sqrt(trange) * ra, rso) if rso > 0 else 0.0

    es = 0.5 * (_sat_vp_kpa(temp_max_c) + _sat_vp_kpa(temp_min_c))
    ea = es * min(max(rh_mean_pct, 5.0), 100.0) / 100.0

    rns = (1 - 0.23) * rs
    ratio = min(max(rs / rso, 0.3), 1.0) if rso > 0 else 0.5
    rnl = (
        4.903e-9
        * (((temp_max_c + 273.16) ** 4 + (temp_min_c + 273.16) ** 4) / 2)
        * (0.34 - 0.14 * math.sqrt(max(ea, 0.0)))
        * (1.35 * ratio - 0.35)
    )
    rn = rns - rnl

    delta = 4098 * _sat_vp_kpa(temp_mean_c) / (temp_mean_c + 237.3) ** 2
    pressure = 101.3 * ((293 - 0.0065 * elevation_m) / 293) ** 5.26
    gamma = 0.000665 * pressure
    u2 = max(0.5, 0.6 * wind10_max_ms * 0.748)

    num = 0.408 * delta * rn + gamma * 900 / (temp_mean_c + 273) * u2 * (es - ea)
    et0 = num / (delta + gamma * (1 + 0.34 * u2))
    return max(et0, 0.0)
