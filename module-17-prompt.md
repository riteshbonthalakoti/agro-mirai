# MODULE 17 — ET0-based irrigation water balance (replaces Module 17's old slot)

Continuing AGRO MIRAI in the existing `agro-mirai` repo. Modules 01–16b
are done (`origin/main`). Read `CLAUDE.md`, `PROGRESS.md`, and
`docs/ROADMAP_PRODUCTION.md` (Part 4) first — that section is the reason
this module exists: a source-level audit found that
`recommended_depth_mm` and the irrigation advisory window are currently
a hardcoded lookup table keyed off predicted urgency
(`_URGENCY_TO_DEPTH_MM` in `src/agro_mirai/models/irrigation_prediction_model.py`),
not physically grounded. Real irrigation scheduling uses a water
balance — reference evapotranspiration (ET0) combined with a crop
coefficient (Kc) — and this module replaces the lookup table with that.

Sequencing note: this runs BEFORE Module 18 (formerly "17" — multi-tenant
+ Admin) per Ritesh's explicit call — model/backend logic first, so
multi-tenant auth isn't layered on top of models about to change.
`docs/ROADMAP_PRODUCTION.md`'s module numbering should be corrected to
reflect this if it still shows the old order.

Confirm `git config user.name`/`user.email`. Same commit discipline —
several focused commits, not one giant one.

## What's not changing

The trained `IrrigationPredictionModel` classifier (urgency: low/
moderate/high — RandomForest on the Kaggle dataset) stays as-is for this
module; that's the crop/dataset localization work, which is a separate
module. This module only replaces how `recommended_depth_mm` and the
advisory window get computed downstream of the urgency prediction.

## Task

### 1. Implement ET0 calculation
Add a `src/agro_mirai/models/evapotranspiration.py` (or similar) module
implementing a reference evapotranspiration formula. Use the
**Hargreaves-Samani** method — it only needs temperature (mean/min/max)
and extraterrestrial radiation (computable from latitude + day-of-year,
no separate radiation sensor needed), which fits what this project
already has (Open-Meteo gives temp min/mean/max; `Field` has
latitude). Penman-Monteith is more accurate but needs solar radiation,
wind speed, and vapor pressure deficit data this project doesn't
consistently have — don't reach for it unless you find those inputs are
actually reliably available; if you do, that's a fine upgrade, but
justify it.

Formula reference (Hargreaves-Samani, standard form):
```
ET0 = 0.0023 * Ra * (Tmean + 17.8) * sqrt(Tmax - Tmin)
```
where `Ra` is extraterrestrial radiation (MJ/m²/day, computed from
latitude and day-of-year via the standard FAO-56 formula), and ET0 comes
out in mm/day. Cite the source (FAO Irrigation and Drainage Paper 56, or
equivalent) in a code comment — don't hand-derive without a reference.

### 2. Crop coefficient (Kc)
A small lookup table `Kc` by crop and growth stage (initial/development/
mid-season/late-season) for at least the crops the training dataset's
label set actually covers (check `docs/eval/crop_rf_eval.json`'s
`labels` field for the real list — don't guess). FAO-56 publishes
standard Kc tables; use those as the source, cited. Growth stage can be
approximated from `days_since_sowing` (already in `FeatureVector`) via
rough day-count breakpoints per crop — document the approximation
honestly, this doesn't need to be perfect, just principled instead of
arbitrary.

### 3. Water balance → recommended_depth_mm
`ETc = ET0 * Kc` (crop evapotranspiration, mm/day). Combine with
`rainfall_mm_sum_7d` (already in `FeatureVector`) to get a net water
deficit over the advisory window, and use that — not a fixed number per
urgency bucket — to compute `recommended_depth_mm`. The urgency
classifier's low/moderate/high output can still gate the advisory
window length (`_URGENCY_TO_WINDOW_DAYS` can stay, or be recomputed from
the deficit — your call, document which) and the `rationale` text should
now cite the actual ET0/deficit numbers, not just "predicted irrigation
need: X".

### 4. Tests
- Unit tests for the ET0 formula against known reference values (FAO-56
  publishes worked examples — use one as a golden test case, not just
  "does it run without erroring").
- Unit tests for the Kc lookup/growth-stage approximation.
- Update/extend `IrrigationPredictionModel`'s existing tests so they
  assert on the new water-balance-derived `recommended_depth_mm` instead
  of the old fixed values — if any existing tests hardcoded the old
  `_URGENCY_TO_DEPTH_MM` values, they need updating, not deleting
  silently (say what changed and why in the handoff).
- An integration-level test through `DecisionEngine`/the API route
  confirming a full request still returns schema-valid output with the
  new depth values.

### 5. Update the ADR
`decisions/0008-irrigation-model-feature-mapping.md` documented the old
lookup-table approach explicitly (with a stated reason: "no dataset with
a continuous depth-mm target was available"). Update it — either amend
in place with a dated addendum explaining the water-balance replacement,
or write a new `decisions/0015-et0-water-balance.md` that supersedes the
relevant section, whichever fits the project's existing ADR convention
better (check how ADR 0014 handled superseding, if it did).

## Full regression pass

Full existing test suite (global interpreter) plus this module's new
tests, `check_specs.py`, CI green on a real push (both jobs — main test
job and the Module 16b voice job).

## Update doctrine

`CLAUDE.md`, `PROGRESS.md` (new module row), `docs/ROADMAP_PRODUCTION.md`
(check off item 1 under "New backend priorities", fix the module
numbering note if needed), commit and push.

## Definition of done
- [ ] ET0 (Hargreaves-Samani) implemented, tested against a cited
      reference value
- [ ] Kc lookup by crop/growth-stage, cited source, covers the model's
      real label set
- [ ] `recommended_depth_mm` genuinely water-balance-derived, not a
      fixed lookup
- [ ] Rationale text reflects real ET0/deficit numbers
- [ ] Tests updated/added, full regression + `check_specs.py` pass
- [ ] ADR updated
- [ ] Pushed to `origin/main`

## Handoff format
```
Module: 17 — ET0-based irrigation water balance
Status: complete | blocked
ET0 method: <Hargreaves-Samani or other, why, reference cited>
Kc table: <crops covered, source, growth-stage approximation approach>
Water balance formula: <how recommended_depth_mm is now derived>
Files changed:
Commits made:
Tests: <new/updated, pass/fail>
Full regression: <pass/fail>
check_specs.py: pass/fail
ADR: <updated 0008 in place | new 0015, which and why>
Known limitations:
Next recommended module: 18 — Crop model localization
```
