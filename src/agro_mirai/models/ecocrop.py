"""Crop suitability from the FAO EcoCrop ranges (temperature, soil pH,
soil texture) for our 22 crops. Data file is built by
tools/build_ecocrop_table.py, see decisions/0027.

Why not the old RandomForest on its own: it was trained on plant-available
N/P/K numbers we never actually have for a field (SoilGrids gives total N
and no P/K), so the live answers were basically random. Temperature, pH and
soil type we do have, so those drive the score here.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_DATA = Path(__file__).resolve().parent / "data" / "ecocrop_crops.json"
_TABLE: dict[str, dict] | None = None

# Farmer soil type -> EcoCrop texture words it roughly matches
_SOIL_TEXTURE = {
    "black": {"heavy"},
    "alluvial": {"medium"},
    "red": {"light", "medium"},
    "laterite": {"light", "medium"},
    "mountain": {"medium", "light"},
    "desert": {"light"},
    "saline": {"medium", "heavy"},
    "peaty": {"organic"},
}

# Crops we show a small preference for when the field is in the region the
# regional list was checked for (see regional_suitability.py).
_REGIONAL_MULT_OUTSIDE = 0.85


# Months a crop is normally sown in Karnataka / peninsular India (kharif Jun-Sep,
# rabi Oct-Jan, zaid Feb-May). Approximate ICAR / state agri-dept calendars;
# perennials (trees, plantations) can be planted any time so are left out.
SOWING_MONTHS: dict[str, set[int]] = {
    "rice": {6, 7, 8, 11, 12, 1},
    "maize": {6, 7, 8, 10, 11, 12, 1},
    "cotton": {6, 7, 8},
    "pigeonpeas": {6, 7, 8},
    "mungbean": {3, 4, 6, 7, 8},
    "blackgram": {6, 7, 8, 9},
    "mothbeans": {6, 7, 8},
    "jute": {3, 4, 5},
    "kidneybeans": {6, 7, 10, 11},
    "chickpea": {10, 11, 12},
    "lentil": {10, 11, 12},
    "watermelon": {1, 2, 3, 11, 12},
    "muskmelon": {1, 2, 3, 11, 12},
}


_PERENNIAL_FACTOR = 0.9


def season_factor(crop: str, month: int | None) -> float:
    """1.0 in a normal sowing month, 0.85 a month either side, else 0.6."""
    months = SOWING_MONTHS.get(crop)
    if months is None:
        # tree / plantation crop: no sowing month, but a years-long commitment,
        # so it only wins when it is clearly the best fit
        return _PERENNIAL_FACTOR
    if month is None:
        return 1.0
    if month in months:
        return 1.0
    if ((month - 2) % 12) + 1 in months or (month % 12) + 1 in months:
        return 0.85
    return 0.6


def table() -> dict[str, dict]:
    global _TABLE
    if _TABLE is None:
        _TABLE = json.loads(_DATA.read_text(encoding="utf-8"))
    return _TABLE


def _range_fit(x: float, abs_min, opt_min, opt_max, abs_max) -> float:
    """1 inside the optimal range, falling linearly to 0 at the absolute limits."""
    if None in (abs_min, opt_min, opt_max, abs_max):
        return 0.7  # no data for this crop, stay neutral
    if opt_min <= x <= opt_max:
        return 1.0
    if x < opt_min:
        return 0.0 if x <= abs_min else (x - abs_min) / (opt_min - abs_min)
    return 0.0 if x >= abs_max else (abs_max - x) / (abs_max - opt_max)


def _texture_fit(soil_type: str | None, crop_text: str | None) -> float:
    wanted = _SOIL_TEXTURE.get((soil_type or "").strip().lower())
    if not wanted or not crop_text:
        return 0.8
    words = {w.strip() for w in crop_text.replace(",", " ").split()}
    if "wide" in words or words & wanted:
        return 1.0
    return 0.4


@dataclass
class CropFit:
    crop: str
    score: float
    temp_fit: float
    ph_fit: float
    texture_fit: float
    rain_fit: float = 0.7
    season_fit: float = 1.0


def score_crops(
    temp_c: float,
    ph: float | None,
    soil_type: str | None,
    rain_30d_mm: float | None = None,
    regional_crops: frozenset[str] | None = None,
    month: int | None = None,
    annual_rain_mm: float | None = None,
) -> list[CropFit]:
    """``rain_30d_mm`` is annualised (x12) only for a soft check, since one
    month is a noisy guide to the year. ``regional_crops`` (if the field is
    in the region that list covers) nudges listed crops above the rest.
    ``month`` (1-12) favours crops that are normally sown around now."""
    # real 12-month total when we have it, else a rough x12 of the last month
    reliable_rain = annual_rain_mm is not None
    annual_rain = annual_rain_mm if reliable_rain else (None if rain_30d_mm is None else rain_30d_mm * 12.17)
    rain_weight = 0.45 if reliable_rain else 0.3
    out = []
    for crop, e in table().items():
        t = _range_fit(temp_c, e["tmin"], e["topmn"], e["topmx"], e["tmax"])
        p = 0.8 if ph is None else _range_fit(ph, e["phmin"], e["phopmn"], e["phopmx"], e["phmax"])
        x = _texture_fit(soil_type, e["text"])
        r = 0.7 if annual_rain is None else _range_fit(annual_rain, e["rmin"], e["ropmn"], e["ropmx"], e["rmax"])
        score = t * (0.6 + 0.4 * p) * (0.8 + 0.2 * x) * ((1 - rain_weight) + rain_weight * r)
        score *= season_factor(crop, month)
        if regional_crops is not None and crop not in regional_crops:
            score *= _REGIONAL_MULT_OUTSIDE
        # small nudge to crops whose ideal temperature is centred on ours
        if e["topmn"] is not None and e["topmx"] is not None and t > 0:
            mid = (e["topmn"] + e["topmx"]) / 2
            score += 0.05 * max(0.0, 1 - abs(temp_c - mid) / 10)
        out.append(CropFit(crop, score, t, p, x, r, season_factor(crop, month)))
    out.sort(key=lambda f: -f.score)
    top = out[0].score if out and out[0].score > 0 else 1.0
    for f in out:
        f.score = round(min(f.score / max(top, 1.0), 1.0), 3)
    return out


def describe(fit: CropFit, temp_c: float, ph: float | None) -> str:
    e = table()[fit.crop]
    parts = []
    if fit.temp_fit >= 1.0:
        parts.append(f"the temperature ({temp_c:.0f}°C) is in its ideal range of {e['topmn']:.0f}-{e['topmx']:.0f}°C")
    elif fit.temp_fit > 0:
        parts.append(f"the temperature ({temp_c:.0f}°C) is a bit outside its ideal {e['topmn']:.0f}-{e['topmx']:.0f}°C")
    else:
        parts.append(f"the temperature ({temp_c:.0f}°C) is too far from what it needs")
    if ph is not None and e["phopmn"] is not None:
        if fit.ph_fit >= 1.0:
            parts.append(f"soil pH {ph:.1f} suits it")
        else:
            parts.append(f"soil pH {ph:.1f} is outside its ideal {e['phopmn']:.1f}-{e['phopmx']:.1f}")
    return "; ".join(parts)
