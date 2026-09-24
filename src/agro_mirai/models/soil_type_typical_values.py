"""Module 34 follow-up 2: typical soil-chemistry values keyed by the
farmer-picked ``Field.soil_type`` label ("Alluvial" / "Black" / "Red" /
"Laterite" / "Mountain" / "Desert" / "Peaty/Marshy"), used **only** as a
fallback when the real SoilGrids-sourced ``SoilSample`` genuinely has no
chemistry values for that pixel (all of ph/N/P/K came back ``None`` —
see ``soilgrids.py``'s "no-data pixel yields a sample with no chemistry
values" comment). The primary, preferred source of truth for the crop
model remains the real ``SoilSample`` (``source="soilgrids"`` or
``"lab_report"``) once Module 34 follow-up 2's live wiring populates it —
this table never overrides a real value, it only fills a genuine gap.

Values are broad, commonly-cited regional typicals for each Indian soil
order (topsoil, 0-5cm-comparable), not a per-field lab measurement —
this is an honest approximation, not a substitute for real SoilGrids or
lab data, and is flagged as such via ``FeatureVector.soil_source ==
"soil_type_fallback"`` so nothing downstream can mistake it for a
measured value. Sources: ICAR-NBSS&LUP soil-order chemistry summaries
and FAO/ICAR extension-bulletin ranges (same class of source already
used for regional crop suitability, decisions/0016).
"""
from __future__ import annotations

# Keys match specs/core/enums.md's `soil_type` enum exactly.
# (ph, nitrogen_mg_per_kg, phosphorus_mg_per_kg, potassium_mg_per_kg, organic_carbon_pct)
SOIL_TYPE_TYPICAL_VALUES: dict[str, dict[str, float]] = {
    "alluvial": {"ph": 7.5, "nitrogen_mg_per_kg": 280.0, "phosphorus_mg_per_kg": 15.0, "potassium_mg_per_kg": 200.0, "organic_carbon_pct": 0.55},
    "black": {"ph": 8.0, "nitrogen_mg_per_kg": 250.0, "phosphorus_mg_per_kg": 12.0, "potassium_mg_per_kg": 300.0, "organic_carbon_pct": 0.60},
    "red": {"ph": 6.5, "nitrogen_mg_per_kg": 220.0, "phosphorus_mg_per_kg": 10.0, "potassium_mg_per_kg": 120.0, "organic_carbon_pct": 0.45},
    "laterite": {"ph": 5.5, "nitrogen_mg_per_kg": 180.0, "phosphorus_mg_per_kg": 8.0, "potassium_mg_per_kg": 90.0, "organic_carbon_pct": 0.70},
    "mountain": {"ph": 6.0, "nitrogen_mg_per_kg": 300.0, "phosphorus_mg_per_kg": 14.0, "potassium_mg_per_kg": 150.0, "organic_carbon_pct": 1.00},
    "desert": {"ph": 8.5, "nitrogen_mg_per_kg": 120.0, "phosphorus_mg_per_kg": 6.0, "potassium_mg_per_kg": 180.0, "organic_carbon_pct": 0.20},
    "saline": {"ph": 8.8, "nitrogen_mg_per_kg": 150.0, "phosphorus_mg_per_kg": 7.0, "potassium_mg_per_kg": 220.0, "organic_carbon_pct": 0.30},
    "peaty": {"ph": 5.0, "nitrogen_mg_per_kg": 350.0, "phosphorus_mg_per_kg": 9.0, "potassium_mg_per_kg": 100.0, "organic_carbon_pct": 2.50},
}

# Backup for fields with no soil type ("unknown" / not picked): the plain
# average of the eight profiles above, so the models still answer instead
# of failing. Rough on purpose, the app should nudge farmers to pick a type.
_GENERIC = {
    key: round(sum(v[key] for v in SOIL_TYPE_TYPICAL_VALUES.values()) / len(SOIL_TYPE_TYPICAL_VALUES), 2)
    for key in ("ph", "nitrogen_mg_per_kg", "phosphorus_mg_per_kg", "potassium_mg_per_kg", "organic_carbon_pct")
}

# Module 34 follow-up 3: typical topsoil field-capacity moisture (% by
# volume, "typical moist" field condition, not saturation) per soil_type,
# used to fill SoilSample.moisture_pct — SoilGrids never returns a
# moisture reading at all (it is a static-property database: ph/N/P/K/
# texture, not a live sensor feed), so this is the COMMON case, not an
# edge case, unlike the ph/N/P/K fallback above which only fires on a
# genuine no-data pixel. Values are FAO/USDA soil-texture-class field
# capacity ranges (FAO Irrigation & Drainage Paper 56, Table 19;
# USDA-NRCS Soil Survey field-capacity-by-texture tables), midpoint of
# the cited range, mapped from each Indian soil order to its dominant
# USDA texture class: alluvial -> loam (~25%), black/vertisol -> clay
# (~40%, high water-holding), red -> sandy loam (~15%), laterite ->
# sandy clay loam (~22%), mountain -> loam (~25%, forest/hill soils),
# desert -> sand/loamy sand (~10%, lowest of the set), saline -> clay
# loam (~30%, saline soils are typically fine-textured/poorly drained),
# peaty -> organic/muck soil (~55%, far higher than any mineral soil —
# organic matter holds several times its weight in water).
SOIL_TYPE_FIELD_CAPACITY_PCT: dict[str, float] = {
    "alluvial": 25.0,
    "black": 40.0,
    "red": 15.0,
    "laterite": 22.0,
    "mountain": 25.0,
    "desert": 10.0,
    "saline": 30.0,
    "peaty": 55.0,
}
_GENERIC_MOISTURE_PCT = round(sum(SOIL_TYPE_FIELD_CAPACITY_PCT.values()) / len(SOIL_TYPE_FIELD_CAPACITY_PCT), 1)


def lookup_typical_values(soil_type: str | None) -> dict[str, float] | None:
    key = (soil_type or "").strip().lower()
    return SOIL_TYPE_TYPICAL_VALUES.get(key, _GENERIC)


def lookup_typical_moisture_pct(soil_type: str | None) -> float | None:
    key = (soil_type or "").strip().lower()
    return SOIL_TYPE_FIELD_CAPACITY_PCT.get(key, _GENERIC_MOISTURE_PCT)
