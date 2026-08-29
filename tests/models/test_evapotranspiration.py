"""Unit tests for the Hargreaves-Samani ET0 module (Module 17).

Golden test case: extraterrestrial radiation Ra at the equator near an
equinox is a widely-cited FAO-56 reference figure (Table 2.6 lists
equatorial daily Ra, expressed as mm/day equivalent evaporation, in the
~32-41 MJ/m^2/day range across the year, i.e. ~13-17mm/day equivalent,
peaking near equinox around 15mm/day). This is used as the golden
check for `extraterrestrial_radiation_mj`, not just "does it run".
"""
from __future__ import annotations

import math

import pytest

from agro_mirai.models.evapotranspiration import (
    extraterrestrial_radiation_mj,
    hargreaves_samani_et0,
)


def test_ra_equator_equinox_matches_fao56_reference_range():
    # March equinox ~ day 80 (non-leap year).
    ra_mj = extraterrestrial_radiation_mj(latitude_deg=0.0, day_of_year=80)
    ra_mm_equivalent = ra_mj * 0.408

    # FAO-56 Table 2.6: equatorial Ra in mm/day-equivalent is
    # documented to sit close to ~15mm/day near the equinoxes.
    assert ra_mm_equivalent == pytest.approx(15.4, abs=0.5)


def test_ra_is_symmetric_between_hemispheres_at_equinox():
    # At the equinox, day length (and thus Ra) should be ~equal for a
    # given latitude magnitude in either hemisphere -- a basic physical
    # sanity check independent of any specific reference number.
    ra_north = extraterrestrial_radiation_mj(latitude_deg=20.0, day_of_year=80)
    ra_south = extraterrestrial_radiation_mj(latitude_deg=-20.0, day_of_year=80)
    assert ra_north == pytest.approx(ra_south, rel=0.05)


def test_ra_higher_at_high_latitude_summer_than_equator():
    # A well-known qualitative fact used as a second sanity check:
    # near summer solstice, high-latitude Ra can exceed equatorial Ra
    # (long day length compensates for lower sun angle).
    ra_equator = extraterrestrial_radiation_mj(latitude_deg=0.0, day_of_year=172)
    ra_high_lat_summer = extraterrestrial_radiation_mj(
        latitude_deg=50.0, day_of_year=172
    )
    assert ra_high_lat_summer > ra_equator


def test_hargreaves_samani_matches_hand_computed_value():
    # Hand-computed via the same FAO-56 Eq 52 formula/coefficients cited
    # in evapotranspiration.py, for a representative Karnataka-latitude,
    # mid-monsoon-day scenario (latitude 15N, day-of-year 200,
    # Tmean=27C, Tmin=22C, Tmax=33C). Independently re-derived here in
    # the test (not by importing the function under test) so this is a
    # real regression guard on the constants, not a tautology.
    latitude_deg = 15.0
    day_of_year = 200
    tmean, tmin, tmax = 27.0, 22.0, 33.0

    phi = math.radians(latitude_deg)
    dr = 1 + 0.033 * math.cos(2 * math.pi / 365 * day_of_year)
    delta = 0.409 * math.sin(2 * math.pi / 365 * day_of_year - 1.39)
    omega_s = math.acos(-math.tan(phi) * math.tan(delta))
    ra_mj = (
        (24 * 60 / math.pi)
        * 0.0820
        * dr
        * (
            omega_s * math.sin(phi) * math.sin(delta)
            + math.cos(phi) * math.cos(delta) * math.sin(omega_s)
        )
    )
    ra_mm = ra_mj * 0.408
    expected_et0 = 0.0023 * (tmean + 17.8) * math.sqrt(tmax - tmin) * ra_mm

    actual = hargreaves_samani_et0(tmean, tmin, tmax, latitude_deg, day_of_year)
    assert actual == pytest.approx(expected_et0, rel=1e-9)
    # Sanity range: tropical mid-monsoon ET0 is typically ~3-7mm/day.
    assert 2.0 < actual < 8.0


def test_hargreaves_samani_nonnegative_when_tmax_lt_tmin():
    # Degenerate/noisy input guard: should not raise or go negative.
    actual = hargreaves_samani_et0(
        temp_mean_c=20.0,
        temp_min_c=25.0,
        temp_max_c=20.0,
        latitude_deg=15.0,
        day_of_year=100,
    )
    assert actual == 0.0


def test_hargreaves_samani_zero_diurnal_range_gives_zero_et0():
    actual = hargreaves_samani_et0(
        temp_mean_c=25.0,
        temp_min_c=25.0,
        temp_max_c=25.0,
        latitude_deg=15.0,
        day_of_year=150,
    )
    assert actual == 0.0
