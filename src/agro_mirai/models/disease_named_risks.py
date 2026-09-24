"""Crop-specific disease risk from the weather, instead of one generic label.

For each crop we list a few common diseases and the weather they are
usually said to favour (a temperature band and how wet/humid it has to be).
Each day of real weather (last week plus the forecast) is checked against
that, so a farmer growing rice hears "Rice blast: conditions favour it"
instead of "generic fungal risk".

This says conditions *favour* a disease, not that it is present. The bands
are typical textbook infection conditions gathered from general agronomy
sources, approximate and not fitted to this project's data (see
decisions/0028). Crops not listed here keep the generic score.
"""
from __future__ import annotations

from dataclasses import dataclass

from agro_mirai.processing.feature_builder import FeatureVector


@dataclass(frozen=True)
class NamedRisk:
    name: str
    temp_lo: float  # favourable temperature band (C)
    temp_hi: float
    min_rh: float  # a day counts as humid at/above this mean RH (%)
    action: str  # what to check / do


_SCOUT = "Check the leaves"

RISKS: dict[str, list[NamedRisk]] = {
    "rice": [
        NamedRisk("Rice blast", 20, 30, 85,
                  f"{_SCOUT} for grey-centred, spindle-shaped spots; avoid extra nitrogen; ask your extension officer about a preventive spray if spots appear."),
        NamedRisk("Bacterial leaf blight", 25, 34, 80,
                  f"{_SCOUT} for yellow-white streaks starting at leaf tips; drain standing water and avoid extra nitrogen."),
    ],
    "maize": [
        NamedRisk("Northern leaf blight", 18, 27, 85,
                  f"{_SCOUT} for long grey-green cigar-shaped patches; remove badly hit leaves and ask about a spray if it spreads."),
    ],
    "cotton": [
        NamedRisk("Bacterial blight and leaf spots", 26, 35, 80,
                  f"{_SCOUT} for angular, water-soaked spots; avoid working in the field when leaves are wet."),
    ],
    "chickpea": [
        NamedRisk("Ascochyta blight", 15, 25, 80,
                  f"{_SCOUT} and stems for brown spots with dark rings; cool wet weather spreads it fast."),
    ],
    "pigeonpeas": [
        NamedRisk("Phytophthora blight", 25, 30, 85,
                  "Look for sudden wilting patches in low, waterlogged spots; improve drainage."),
    ],
    "grapes": [
        NamedRisk("Downy mildew", 18, 26, 80,
                  f"{_SCOUT} for yellow oily patches with white growth underneath; ask about a preventive spray."),
    ],
    "banana": [
        NamedRisk("Sigatoka leaf spot", 24, 30, 80,
                  f"{_SCOUT} for yellow streaks turning into brown spots; remove badly hit leaves."),
    ],
    "mango": [
        NamedRisk("Anthracnose", 24, 30, 85,
                  f"{_SCOUT}, flowers and young fruit for dark sunken spots."),
    ],
    "orange": [
        NamedRisk("Citrus canker", 25, 33, 80,
                  f"{_SCOUT} and fruit for raised corky spots with a yellow ring."),
    ],
    "apple": [
        NamedRisk("Apple scab", 10, 24, 85,
                  f"{_SCOUT} for olive-green velvety spots; wet spells in cool weather favour it."),
    ],
    "pomegranate": [
        NamedRisk("Bacterial blight and fruit spot", 25, 35, 80,
                  f"{_SCOUT} and fruit for small dark water-soaked spots."),
    ],
    "watermelon": [
        NamedRisk("Downy mildew", 18, 28, 85,
                  f"{_SCOUT} for yellow angular patches with grey-purple growth underneath."),
    ],
    "muskmelon": [
        NamedRisk("Downy mildew", 18, 28, 85,
                  f"{_SCOUT} for yellow angular patches with grey-purple growth underneath."),
    ],
    "coffee": [
        NamedRisk("Coffee leaf rust", 18, 28, 85,
                  f"{_SCOUT} for orange powdery spots underneath."),
    ],
    "coconut": [
        NamedRisk("Bud rot", 20, 28, 90,
                  "Look for a yellowing or drooping central spike after heavy rain; keep the crown clean and dry."),
    ],
    "papaya": [
        NamedRisk("Anthracnose and leaf spot", 24, 30, 85,
                  f"{_SCOUT} and fruit for dark sunken spots."),
    ],
    "jute": [
        NamedRisk("Stem rot", 28, 35, 85,
                  "Look for dark patches on stems near the ground; drain standing water."),
    ],
    "mungbean": [
        NamedRisk("Cercospora leaf spot", 25, 30, 80,
                  f"{_SCOUT} for round brown spots with a grey centre."),
    ],
    "blackgram": [
        NamedRisk("Cercospora leaf spot", 25, 30, 80,
                  f"{_SCOUT} for round brown spots with a grey centre."),
    ],
    "kidneybeans": [
        NamedRisk("Rust and angular leaf spot", 16, 28, 85,
                  f"{_SCOUT} for rusty pustules and angular brown spots."),
    ],
}


def _temp_fit(t: float, lo: float, hi: float) -> float:
    """1 inside the band, 0 when 6 C or more outside it."""
    if lo <= t <= hi:
        return 1.0
    gap = lo - t if t < lo else t - hi
    return max(0.0, 1.0 - gap / 6.0)


@dataclass
class NamedRiskResult:
    risk: NamedRisk
    score: float
    humid_days_7d: int
    wet_days_7d: int
    days_counted: int
    rain_forecast_3d_mm: float | None
    rain_forecast_7d_mm: float | None
    trend: str  # "rising" | "steady" | "easing"


def _recent_days(features: FeatureVector) -> tuple[list[dict], list[dict]]:
    daily = features.daily_weather or []
    past = [d for d in daily if d["date"] <= features.as_of.isoformat()]
    future = [d for d in daily if d["date"] > features.as_of.isoformat()]
    past.sort(key=lambda d: d["date"])
    future.sort(key=lambda d: d["date"])
    return past[-7:], future


def score_named(features: FeatureVector) -> NamedRiskResult | None:
    """Best-matching named disease for the field's crop, or None (unknown
    crop, or no temperature at all)."""
    candidates = RISKS.get(features.crop_type or "")
    if not candidates:
        return None
    temp = features.temp_c_mean_7d if features.temp_c_mean_7d is not None else features.temp_c_mean_14d
    if temp is None:
        return None

    past7, future = _recent_days(features)
    best: NamedRiskResult | None = None
    for r in candidates:
        if past7:
            humid = sum(1 for d in past7 if (d.get("rh") or 0) >= r.min_rh)
            wet = sum(1 for d in past7 if (d.get("rain") or 0) >= 1.0)
            n = len(past7)
            wetness = min(1.0, 0.7 * humid / n + 0.7 * wet / n)
        else:
            # no daily series: fall back to the weekly aggregates
            rh = features.humidity_pct_mean_7d if features.humidity_pct_mean_7d is not None else features.humidity_pct_mean_14d
            humid = wet = n = 0
            wetness = 0.0
            if rh is not None:
                wetness += 0.7 * max(0.0, min(1.0, (rh - (r.min_rh - 15)) / 15))
            wetness += 0.7 * min(1.0, features.rainfall_mm_sum_7d / 40.0)
            wetness = min(1.0, wetness)

        rain3 = features.rain_forecast_mm_3d
        rain7 = features.rain_forecast_mm_7d
        fc_bonus = 0.0 if not rain7 else min(0.15, rain7 / 200.0)
        score = min(1.0, _temp_fit(temp, r.temp_lo, r.temp_hi) * wetness + fc_bonus)

        if (rain3 or 0) >= 10:
            trend = "rising"
        elif past7 and len(past7) >= 5:
            early = sum(1 for d in past7[:4] if (d.get("rain") or 0) >= 1.0 or (d.get("rh") or 0) >= r.min_rh)
            late = sum(1 for d in past7[4:] if (d.get("rain") or 0) >= 1.0 or (d.get("rh") or 0) >= r.min_rh)
            trend = "easing" if (early / 4) - (late / max(1, len(past7) - 4)) >= 0.4 else "steady"
        else:
            trend = "steady"

        res = NamedRiskResult(r, score, humid, wet, n, rain3, rain7, trend)
        if best is None or res.score > best.score:
            best = res
    return best
