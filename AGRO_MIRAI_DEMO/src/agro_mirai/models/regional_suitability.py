"""Regional-suitability sanity layer for `CropRecommendationModel`.

This is deliberately NOT a retrain and NOT a hard override — see
`decisions/0016-regional-crop-suitability.md` for the full reasoning and
why a retrain wasn't viable within this module's scope. It is a small,
explicitly-sourced honesty check: `CropRecommendationModel` is trained
purely on the generic Kaggle `atharvaingle/crop-recommendation-dataset`
(N/P/K/temp/humidity/pH/rainfall, 22 global crop classes) and has no
grounding in what is actually grown at meaningful scale in Bellary
(Ballari) district, Karnataka — the region this project's field fixtures
(`farm-001`, `farm-002`) and its single-farmer deployment (ADR 0003) are
both scoped to.

`BELLARY_REGIONAL_CROPS` is the subset of `specs/core/enums.md`'s
`crop_type` enum that real, cited sources confirm is grown at meaningful
scale in Bellary/Ballari district. It is intersected against the
22-label enum, not built from general knowledge — most crops genuinely
dominant in Bellary (jowar/sorghum, groundnut, sunflower, millet,
soybean, Bengal gram's close relatives, coriander) have NO label in the
current 22-crop enum at all, so they simply cannot be represented here;
this is a real limitation of the underlying model's label set, not an
oversight in this table. See the ADR for the full list of what was
found but couldn't be included.

Sources (fetched and cross-checked 2026-08-29):

1. ICAR-CRIDA / UAS Raichur, "District Agriculture Contingency Plan —
   Bellary" (Government of India, ICAR), Karnataka district contingency
   plan series:
   https://www.icar-crida.res.in/CP/Karnataka/UAS,%20Raichur/KA25-Bellary%2004.10.2011.pdf
   — official ICAR/state-university document; names cotton, jowar,
   groundnut, Bengal gram (chickpea), pigeon peas, coriander, millet,
   and soybean among crops grown in the district, and characterises
   Bellary as NARP zone KA-3 (Northern Dry Zone), erratic 400-500mm
   rainfall, predominantly rainfed cultivation on residual moisture.
2. Wikipedia, "Ballari district" (citing Karnataka government / census
   agricultural statistics):
   https://en.wikipedia.org/wiki/Ballari_district
   — cotton, jowar (sorghum), groundnuts, rice, sunflowers, cereals;
   Tungabhadra Dam is the primary irrigation source (~37% of net sown
   area irrigated, canals ~two-thirds of that).
3. AgriFarming.in, "District Wise Crop Production in Karnataka":
   https://www.agrifarming.in/district-wise-crop-production-in-karnataka-list-of-crops-grown-in-karnataka
   — cotton, millet, peanuts (groundnut), rice, sunflower, cereals for
   Ballari district.

All three independently confirm the same core set. Intersected against
`crop_type`'s 22 labels, the crops with BOTH real cited cultivation
history in Bellary AND a matching enum label are: cotton, rice, maize,
chickpea (the closest enum label to "Bengal gram"), and pigeonpeas.
Maize is included on the strength of source 1's broader Northern Dry
Zone contingency-crop guidance and is also the `current_crop` on
`farm-002` — flagged here as the weakest-evidenced entry in the set
(see the ADR's "Known limitations" section) rather than silently
presented with the same confidence as the other four.
"""
from __future__ import annotations

from dataclasses import dataclass

BELLARY_REGIONAL_CROPS: frozenset[str] = frozenset(
    {
        "cotton",
        "rice",
        "maize",
        "chickpea",
        "pigeonpeas",
    }
)


@dataclass(frozen=True)
class RegionalFitResult:
    """Outcome of checking one `CropRecommendation`'s top prediction
    against `BELLARY_REGIONAL_CROPS`."""

    out_of_region: bool
    regional_alternative: str | None


def check_regional_fit(
    recommended_crop: str, alternatives: list[str] | None
) -> RegionalFitResult:
    """Flags (never overrides) a top prediction outside the known
    Bellary/Karnataka regional-suitability set.

    When `recommended_crop` is not in `BELLARY_REGIONAL_CROPS`, scans
    `alternatives` (already ranked by predicted probability) for the
    first entry that IS in the regional set and surfaces it as
    `regional_alternative`. If none of the alternatives are regional
    either, `regional_alternative` is `None` — this is reported
    explicitly by the caller, not left ambiguous.
    """
    if recommended_crop in BELLARY_REGIONAL_CROPS:
        return RegionalFitResult(out_of_region=False, regional_alternative=None)

    for candidate in alternatives or []:
        if candidate in BELLARY_REGIONAL_CROPS:
            return RegionalFitResult(out_of_region=True, regional_alternative=candidate)

    return RegionalFitResult(out_of_region=True, regional_alternative=None)
