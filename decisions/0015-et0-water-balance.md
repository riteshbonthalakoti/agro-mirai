# ADR 0015 — ET0/Kc water balance replaces the fixed depth-mm lookup (supersedes part of ADR 0008)

**Status:** accepted
**Date:** 2026-08-29
**Module:** 17 — ET0-based irrigation water balance

## Context

`docs/ROADMAP_PRODUCTION.md` Part 4's source-level audit flagged that
`IrrigationAdvice.recommended_depth_mm` and the advisory window were a
hardcoded band keyed off the predicted `urgency` class
(`_URGENCY_TO_DEPTH_MM` in
`src/agro_mirai/models/irrigation_prediction_model.py`) — explicitly
documented as a rule-based placeholder in ADR 0008 ("no dataset with a
continuous depth-mm target was available"). That reasoning for *why*
there's no trained regressor still holds (no such dataset was found for
this module either), but a fixed per-urgency-bucket number ignores
actual conditions: two fields both classified `moderate` urgency could
have wildly different real water needs depending on temperature,
season, and how much rain they've already had.

## Decision

Replace the fixed lookup with a physically grounded water balance:
**ET0 (Hargreaves-Samani) x Kc (FAO-56 Table 12) - rainfall received =
net deficit -> `recommended_depth_mm`.**

### This explicitly supersedes ADR 0008's "`recommended_depth_mm`
### (rule-based band, not trained)" section

ADR 0008 remains accurate for everything else it documents (the
`urgency` classifier, the `FeatureVector` -> dataset column mapping,
the missing-data policy for `soil_data_available`/temperature/humidity)
— only its `recommended_depth_mm` table and rationale are superseded by
this ADR. ADR 0008 is left in place (not rewritten) per this project's
existing convention of not silently editing a previously-accepted ADR;
this document is the amendment, cross-referenced from both files.

### ET0 method — Hargreaves-Samani, not Penman-Monteith

FAO-56's reference method, Penman-Monteith, needs solar radiation, wind
speed, and vapor pressure deficit — none of which this project reliably
collects (Open-Meteo calls used elsewhere are configured for temp min/
mean/max only, see `docs/architecture.md`). Hargreaves-Samani needs only
temperature and extraterrestrial radiation (computable from latitude +
day-of-year, no sensor). This is a documented, FAO-endorsed fallback for
exactly this data-scarcity situation, not an ad hoc simplification.
Source: Allen, R.G. et al. (1998), FAO Irrigation and Drainage Paper 56.
Implementation: `src/agro_mirai/models/evapotranspiration.py`.

### Kc table — FAO-56 Table 12, covering the crop model's real label set

`src/agro_mirai/models/crop_coefficients.py` covers all 22 crop labels
in `docs/eval/crop_rf_eval.json`. FAO-56 Table 12 doesn't have a direct
entry for every one of those 22 (it's not an India-crop-list-exhaustive
table); three crops without a direct entry use a documented closest
agronomic analog instead of a guess: `jute` -> cotton, `mango` ->
avocado, `coconut` -> dates (no ground cover). Growth stage is
approximated from `FeatureVector.days_since_sowing` via two coarse
categories (annual field/row/vine crops vs. perennial orchard/plantation
crops) with fixed day-count breakpoints, not FAO-56's full per-crop
Table 11 stage-length table — documented in the module docstring as an
approximation, not hidden.

### Water balance formula

```
ETc (mm/day) = ET0 * Kc[crop, growth_stage]
demand (mm)  = ETc * 7  (over the same 7-day window as rainfall_mm_sum_7d)
deficit (mm) = max(0, demand - rainfall_mm_sum_7d)
recommended_depth_mm = max(deficit, 2.0)  # floor so "no need right now" isn't a bare 0.0
```

The 7-day window was chosen (over 14/30d, both already on
`FeatureVector`) because it's short enough to be actionable for a
day-to-few-days-ahead irrigation decision, and because it lines up with
`rainfall_mm_sum_7d`'s existing granularity rather than introducing a
new aggregation window.

### `urgency` still gates the advisory window length, not recomputed

`_URGENCY_TO_WINDOW_DAYS` (low->5 days, moderate->3, high/severe->1) is
kept unchanged from ADR 0008 rather than derived from the deficit
number. Rationale: the trained classifier's urgency output is a
genuinely learned signal (soil moisture, temperature, humidity, season)
about how time-pressured the situation is, which the deficit-mm number
alone doesn't capture (e.g. a small deficit under rapidly worsening
soil-moisture trend vs. a small deficit that's stable) — using both
signals for what they're each good at (urgency -> timing, water balance
-> quantity) was judged better than collapsing everything into one
number. This is a judgment call, documented rather than hidden, and
easy to revisit later.

### `FeatureVector` additions (additive, `specs/core/features.md`)

The water balance needs inputs the vector didn't previously carry:
`temp_c_min_7d`, `temp_c_max_7d` (Tmin/Tmax for Hargreaves-Samani, from
`WeatherReading.temp_min_c`/`temp_max_c`, previously computed into
means only), `latitude` (from `Field_.latitude`, for extraterrestrial
radiation), and `crop_type` (from `Field_.current_crop`, for the Kc
lookup). All four are new optional fields with `None`/no-default-break
semantics — no existing field renamed or removed, per CLAUDE.md's
additive-only-contracts rule.

### Missing-data handling

- Missing `temp_c_mean_7d` -> `ValueError` (matches the existing
  raise-on-missing-critical-input pattern from ADR 0006/0008, since
  there's no reasonable fallback for the mean itself).
- Missing `temp_c_min_7d`/`temp_c_max_7d` (both optional per
  `WeatherReading` schema, even though Open-Meteo populates them in
  practice) -> approximated via a documented +/-4C offset from the mean
  (8C typical diurnal range for semi-arid/tropical Indian cropping
  regions), not a raised error — this follows CLAUDE.md's
  degrade-not-fail doctrine (the GEE-cache-fallback rule's spirit
  applied here) rather than refusing to produce an estimate over a
  secondary input.
- Unknown/missing `crop_type` -> Kc defaults to a neutral `1.0`
  (ETc == ET0), not a refusal.
- Missing `days_since_sowing` or unknown crop for growth-stage lookup ->
  defaults to `mid_season`, a moderate/neutral assumption.

## Consequences

- `recommended_depth_mm` now genuinely varies with real conditions
  (temperature, latitude/season via Ra, crop, growth stage, and
  rainfall already received) instead of being one of four fixed
  numbers. Verified in
  `tests/models/test_irrigation_prediction_model.py`'s
  `test_predict_depth_is_water_balance_derived_not_fixed_lookup`
  (0mm vs 200mm rainfall over 7 days produces different depths for the
  same urgency classification).
- `rationale` now cites the actual ET0/ETc/deficit numbers, not just
  the urgency label.
- If a future dataset with a genuine continuous depth-mm target is
  found, only this water-balance function needs to change —
  `IrrigationPredictionModel`'s public interface and the urgency
  classifier are unaffected, same forward-compatibility property ADR
  0008 already established.
- New coupling: the water balance now depends on `Field_.latitude` and
  `Field_.current_crop` reaching the vector, and on
  `WeatherReading.temp_min_c`/`temp_max_c` being populated for full
  accuracy (degrades, doesn't fail, if they're absent).
