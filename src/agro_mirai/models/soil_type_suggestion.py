"""Suggests the Indian soil-order label (``Field.soil_type``) that best
matches a location's real, measured soil chemistry (Module 61 — raised
directly by a teammate: a farmer picking a soil type the location's real
soil data doesn't actually support got no feedback at all).

SoilGrids has no concept of "Alluvial / Black / Red / ..." (that is an
Indian taxonomic classification, not something ISRIC's global model
predicts) -- there is no authoritative "correct answer" to look up. What
this does instead: compare the location's real, measured pH and organic
carbon % (the two SoilGrids properties directly comparable to
``soil_type_typical_values.py``'s typical profile for each order — N/P/K
are NOT used here, see that module's docstring on why SoilGrids' total-N
scale isn't comparable) against each soil order's typical pH/OC%, and
surface whichever order is the closest match. This is a *suggestion*
based on the closest typical profile, never a hard override of the
farmer's own pick — they may genuinely know their field better than a
global coarse-resolution soil model does.
"""
from agro_mirai.models.soil_type_typical_values import SOIL_TYPE_TYPICAL_VALUES

# pH spans roughly 5.0-8.8 across the table (range ~3.8), OC% spans
# roughly 0.2-2.5 (range ~2.3) -- normalizing each term by its own typical
# range before summing keeps one axis from dominating the distance just
# because its raw numbers happen to be bigger.
_PH_RANGE = 3.8
_OC_RANGE = 2.3


def suggest_soil_type(ph: float | None, organic_carbon_pct: float | None) -> dict | None:
    """Returns {"soil_type": str, "distance": float} for the closest-
    matching typical profile, or None if neither input is usable (never
    guesses from nothing)."""
    if ph is None and organic_carbon_pct is None:
        return None

    best_type: str | None = None
    best_distance = float("inf")
    for soil_type, typical in SOIL_TYPE_TYPICAL_VALUES.items():
        distance = 0.0
        if ph is not None:
            distance += ((ph - typical["ph"]) / _PH_RANGE) ** 2
        if organic_carbon_pct is not None:
            distance += ((organic_carbon_pct - typical["organic_carbon_pct"]) / _OC_RANGE) ** 2
        if distance < best_distance:
            best_distance = distance
            best_type = soil_type

    return {"soil_type": best_type, "distance": round(best_distance, 3)} if best_type else None
