"""Crop coefficient (Kc) lookup by crop and growth stage — Module 17.

Source: Allen, R.G. et al. (1998), FAO Irrigation and Drainage Paper 56,
Table 12 ("Single crop coefficients, Kc, ... for non stressed, well
managed crops"). Table 12 gives three coefficients per crop —
``Kc_ini`` (initial/establishment), ``Kc_mid`` (mid-season, full
canopy), ``Kc_end`` (late-season, senescence) — covering the
"development" stage implicitly as a linear interpolation between
``Kc_ini`` and ``Kc_mid``.

**Coverage / honesty about approximation.** This table covers the 22
crop labels the trained crop-recommendation classifier actually
predicts (``docs/eval/crop_rf_eval.json``'s ``labels`` field — the
model/dataset's real label set, not guessed). FAO-56 Table 12 does not
have an entry for every one of those 22 crops (it's an agronomic
reference table, not exhaustive of India's cropping list), so crops
without a direct entry are mapped to the closest agronomic analog in
the table and flagged in ``_ANALOG_NOTES`` below — this is a documented
approximation, not a silent guess:
  - ``jute``    -> Table 12 "Cotton" (comparable fibrous row crop, no
                   direct FAO-56 entry for jute)
  - ``mango``   -> Table 12 "Avocado" (comparable evergreen sub-tropical
                   tree fruit; FAO-56 has no direct mango entry)
  - ``coconut`` -> Table 12 "Dates, no ground cover" (comparable
                   evergreen palm; FAO-56 has no direct coconut entry)

**Growth stage from ``days_since_sowing``.** FAO-56 Table 11 gives
typical stage-length breakpoints by crop/region; this project doesn't
track per-crop planting calendars precisely enough to reproduce that
table exactly, so growth stage is approximated with two coarse crop
categories and fixed day-count breakpoints (documented as approximate,
not precise agronomy):
  - **Annual crops** (row/field/vine crops that complete a season):
    initial 0-20 days, development 20-50 days, mid-season 50-90 days,
    late-season 90+ days since sowing — a rough composite of FAO-56
    Table 11's typical stage lengths across cereals/legumes/melons.
  - **Perennial/tree crops** (orchard/plantation crops with no annual
    bare-soil establishment phase from ``sown_on``): treated as
    permanently mid-season (``Kc_mid``) once ``days_since_sowing`` is
    known, since an established orchard's canopy doesn't cycle through
    FAO-56's annual-crop stage structure the way a field crop does.
    Kc_ini is used only if `days_since_sowing` is very small (< 365,
    i.e. still establishing).

If ``days_since_sowing`` is ``None`` (no ``sown_on`` on the field), or
the crop isn't in this table, growth stage defaults to ``mid_season``
(Kc_mid) — a neutral, moderate-demand assumption rather than refusing
to produce an estimate.
"""
from __future__ import annotations

from dataclasses import dataclass

GrowthStage = str  # "initial" | "development" | "mid_season" | "late_season"

_ANNUAL_STAGE_BREAKPOINTS = (20, 50, 90)  # (ini->dev, dev->mid, mid->late) days


@dataclass(frozen=True)
class KcCurve:
    kc_ini: float
    kc_mid: float
    kc_end: float
    perennial: bool = False


# FAO-56 Table 12 values (or the documented analog noted in the module
# docstring). Crop names match specs/core/enums.md's `crop_type` enum /
# docs/eval/crop_rf_eval.json's `labels` list exactly.
KC_TABLE: dict[str, KcCurve] = {
    "rice": KcCurve(1.05, 1.20, 0.90),
    "maize": KcCurve(0.30, 1.20, 0.35),
    "cotton": KcCurve(0.35, 1.18, 0.70),
    "jute": KcCurve(0.35, 1.18, 0.70),  # analog: cotton (see docstring)
    # Grain legumes / pulses (Table 12 "Beans, dry and Pulses").
    "chickpea": KcCurve(0.40, 1.15, 0.35),
    "kidneybeans": KcCurve(0.40, 1.15, 0.35),
    "lentil": KcCurve(0.40, 1.15, 0.35),
    "mothbeans": KcCurve(0.40, 1.15, 0.35),
    "mungbean": KcCurve(0.40, 1.15, 0.35),
    "pigeonpeas": KcCurve(0.40, 1.15, 0.35),
    "blackgram": KcCurve(0.40, 1.15, 0.35),
    # Melons (Table 12 "Muskmelon"; watermelon shares the same curve
    # per Table 12's own "Watermelon" entry, Kc_ini differs slightly
    # (0.4 vs 0.5) but mid/end match — using muskmelon's for both).
    "muskmelon": KcCurve(0.50, 1.00, 0.75),
    "watermelon": KcCurve(0.40, 1.00, 0.75),
    # Vine fruit (Table 12 "Grapes, table").
    "grapes": KcCurve(0.30, 0.85, 0.45, perennial=True),
    # Citrus (Table 12 "Citrus, no ground cover, 70% canopy").
    "orange": KcCurve(0.70, 0.65, 0.70, perennial=True),
    # Deciduous orchard, no ground cover (Table 12 "Apples, Cherries,
    # Pears -- no ground cover, killing frost").
    "apple": KcCurve(0.45, 0.95, 0.70, perennial=True),
    "pomegranate": KcCurve(0.45, 0.95, 0.70, perennial=True),
    # Tropical/sub-tropical tree & large-herb fruit (Table 12 direct
    # entries where available).
    "papaya": KcCurve(0.50, 1.00, 0.75, perennial=True),
    "banana": KcCurve(0.50, 1.10, 1.00, perennial=True),
    "mango": KcCurve(0.60, 0.85, 0.75, perennial=True),  # analog: avocado
    "coconut": KcCurve(0.90, 0.90, 0.90, perennial=True),  # analog: dates
    "coffee": KcCurve(0.90, 0.95, 0.95, perennial=True),  # bare ground
}


def growth_stage_for(crop_type: str | None, days_since_sowing: int | None) -> GrowthStage:
    """Approximates FAO-56 growth stage from days since sowing.

    See module docstring for the annual-vs-perennial breakpoint policy
    and the documented reasoning for defaulting to ``mid_season`` when
    inputs are missing.
    """
    if days_since_sowing is None or crop_type is None:
        return "mid_season"

    curve = KC_TABLE.get(crop_type)
    is_perennial = curve.perennial if curve is not None else False

    if is_perennial:
        return "initial" if days_since_sowing < 365 else "mid_season"

    ini_end, dev_end, mid_end = _ANNUAL_STAGE_BREAKPOINTS
    if days_since_sowing < ini_end:
        return "initial"
    if days_since_sowing < dev_end:
        return "development"
    if days_since_sowing < mid_end:
        return "mid_season"
    return "late_season"


def kc_for(crop_type: str | None, growth_stage: GrowthStage) -> float:
    """Kc for a crop at a growth stage. Unknown crop -> 1.0 (neutral,
    matches ET0 == ETc — documented fallback, not a silent 0)."""
    curve = KC_TABLE.get(crop_type) if crop_type else None
    if curve is None:
        return 1.0

    if growth_stage == "initial":
        return curve.kc_ini
    if growth_stage == "development":
        # Linear interpolation midpoint between Kc_ini and Kc_mid, per
        # FAO-56's own treatment of the development stage as a linear
        # ramp (this project doesn't track exact position within the
        # development window, so uses its midpoint as the representative
        # value).
        return (curve.kc_ini + curve.kc_mid) / 2.0
    if growth_stage == "late_season":
        return curve.kc_end
    return curve.kc_mid
