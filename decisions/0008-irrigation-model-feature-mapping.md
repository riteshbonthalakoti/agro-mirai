# ADR 0008 — Irrigation model feature mapping (FeatureVector → dataset inputs, and the depth-mm gap)

**Status:** accepted (partially superseded — see note below)
**Date:** 2026-08-26
**Module:** 07 — Irrigation Prediction Model

> **2026-08-29 update:** the `recommended_depth_mm` (rule-based band,
> not trained)` section below is superseded by
> `decisions/0015-et0-water-balance.md` (Module 17), which replaces the
> fixed urgency-keyed lookup with an ET0 (Hargreaves-Samani) x Kc water
> balance. Everything else in this ADR (the trained `urgency`
> classifier, the `FeatureVector` -> dataset column mapping, the
> missing-data policy) is unchanged and still accurate.

## Context

Unlike Module 06's crop-recommendation dataset, no single canonical
Kaggle dataset covers "soil moisture + weather + crop stage →
irrigation depth in mm" as a continuous regression target. The closest
fit found (see `docs/architecture.md`'s Module 07 section for the
search and why this one was picked) is
`miadul/irrigation-water-requirement-prediction-dataset` (MIT license,
10,000 rows): soil (`Soil_pH`, `Soil_Moisture`, `Organic_Carbon`),
weather (`Temperature_C`, `Humidity`, `Rainfall_mm`), crop/season
context (`Crop_Type`, `Crop_Growth_Stage`, `Season`), and a **3-class
categorical target** `Irrigation_Need` (`Low` / `Medium` / `High` —
5864 / 3800 / 336 rows respectively, no nulls).

`IrrigationAdvice` (`specs/core/schema.yaml`) needs two required
numeric/enum outputs: `recommended_depth_mm` (continuous float) and
`urgency` (`risk_level` enum: `low`/`moderate`/`high`/`severe`). The
dataset supports the second directly (as a classification problem) but
not the first — there is no continuous water-depth column anywhere in
the dataset, only the three-way need label.

## Decision

**Urgency is a trained classifier; `recommended_depth_mm` is a
documented rule-based band, not learned.** Forcing a regression target
out of a categorical label (e.g. by assigning arbitrary numeric depths
to `Low`/`Medium`/`High` and training a regressor against those
invented numbers) would launder a rule into something that looks
learned — worse than being explicit about the rule. This is the
"propose fallback, document as v1 placeholder" path the module brief
allows, applied to one output field rather than the whole model.

### Urgency (classification, trained)

`tools/train_irrigation_model.py` trains a `RandomForestClassifier`
(seed=42) on the dataset's native columns against `Irrigation_Need`.
`Medium` maps to `moderate` at prediction time — `risk_level`'s `severe`
tier has no counterpart in this 3-class label set, so this model
version **never predicts `severe`**; a future dataset/version would be
needed to support it.

| Model column | `FeatureVector` source | Notes |
|---|---|---|
| `Soil_pH` | `soil_ph` | direct pass-through |
| `Soil_Moisture` | `soil_moisture_pct` | direct pass-through — this is the strongest irrigation signal in both the dataset and the vector |
| `Temperature_C` | `temp_c_mean_14d` | 14d window, same rationale as ADR 0007: smooths day-to-day noise without washing out recent conditions |
| `Humidity` | `humidity_pct_mean_14d` | same 14d rationale |
| `Rainfall_mm` | `rainfall_mm_sum_30d` | scale mismatch, flagged as a known limitation below |
| `Season` | `season` | exact match — dataset uses `Kharif`/`Rabi`/`Zaid`, lowercased to match `enums.md`'s `season` enum. This alignment (not a coincidence — Indian-season labels are uncommon in ML datasets) was the deciding factor over other irrigation datasets found in the same Kaggle search |

**Known limitation — rainfall scale mismatch:** the dataset's
`Rainfall_mm` ranges ~0–2500mm (a seasonal/cumulative figure), while
`FeatureVector.rainfall_mm_sum_30d` is a genuine 30-day sum (tens to a
few hundred mm in practice). The model will see live 30d sums that sit
in the low end of its training distribution. This is accepted for v1
because rainfall is a secondary signal here (soil moisture and
temperature dominate feature importance — see the eval report); a
future version should either rescale or find a dataset with a matching
rainfall window.

**Not used:** `Crop_Type`, `Crop_Growth_Stage`, `Irrigation_Type`,
`Water_Source`, `Field_Area_hectare`, `Mulching_Used`,
`Previous_Irrigation_mm`, `Region`, `Electrical_Conductivity`,
`Sunlight_Hours`, `Wind_Speed_kmh` — none have a `FeatureVector`
counterpart (crop stage isn't tracked anywhere upstream yet, and the
rest are dataset-specific context this project doesn't collect).
`ndvi_*` and `days_since_sowing` are likewise not used, same reasoning
as ADR 0007: nothing in this dataset to train them against.

**Missing-data handling:** mirrors ADR 0006/0007 — the mapping function
raises `ValueError` if `soil_data_available` is `False` (no
`soil_ph`/`soil_moisture_pct`) or if `temp_c_mean_14d` /
`humidity_pct_mean_14d` are both `None`, rather than defaulting to
`0.0`.

### `recommended_depth_mm` (rule-based band, not trained)

Mapped deterministically from the predicted urgency class to a
representative depth, using standard light/moderate/heavy irrigation
depth bands for row/field crops (FAO-56-style guidance — light
irrigation ~10mm, moderate ~25mm, heavy ~40mm for a single event):

| Predicted urgency | `recommended_depth_mm` |
|---|---|
| `low` | 10.0 |
| `moderate` | 25.0 |
| `high` | 40.0 |
| `severe` | 50.0 (unreachable in v1 — see above) |

### `window_start_at` / `window_end_at` (rule-based, not trained)

Derived from `created_at` and urgency — more urgent advice gets a
tighter action window: `low` → apply within 5 days, `moderate` → within
3 days, `high`/`severe` → within 1 day. `window_start_at` is always
`created_at` (act starting now); only the end of the window varies.

## Consequences

- `IrrigationPredictionModel.predict` returns a schema-valid
  `IrrigationAdvice` end to end, but only the `urgency` field is backed
  by a trained classifier — `recommended_depth_mm` and the window are
  rule-based lookups keyed off that prediction. This must be called out
  in the Module 07 handoff and is not hidden inside the wrapper.
- If a future dataset with a genuine continuous depth-mm target is
  found, only the depth-band lookup and `tools/train_irrigation_model.py`
  need to change — the urgency classifier, the mapping function's
  column choices, and `IrrigationPredictionModel`'s public interface
  stay the same.
- Same coupling risk as ADR 0007: the trained artifact's column order
  and `irrigation_feature_mapping.py` must stay in sync;
  `tests/models/test_irrigation_feature_mapping.py` pins the column
  order as a regression guard.
