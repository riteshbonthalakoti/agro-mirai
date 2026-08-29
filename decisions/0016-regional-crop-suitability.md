# ADR 0016 — Regional-suitability sanity layer for CropRecommendation (no retrain)

**Status:** accepted
**Date:** 2026-08-29
**Module:** 18 — Crop model localization (Karnataka/Bellary sanity layer)

## Context

`docs/ROADMAP_PRODUCTION.md` Part 4 flagged that `CropRecommendationModel`
is trained purely on Kaggle's generic `atharvaingle/crop-recommendation-dataset`
(N/P/K/temp/humidity/pH/rainfall, 22 global crop classes, 99.55%
held-out accuracy — a red flag for a real agronomic problem, not a
win). It has no grounding in what is actually grown at meaningful scale
in Bellary (Ballari) district, Karnataka — the region this project's
field fixtures (`farm-001`, `farm-002`) and single-farmer deployment
(ADR 0003) are scoped to.

## Investigation — was a real India/Karnataka dataset available?

Per the module prompt's instruction to actually search before assuming
a retrain isn't possible, the following was searched (web search,
2026-08-29):

- `Karnataka Bellary district crop recommendation dataset Kaggle India`
- `ICAR KVK Bellary crops grown district agro-climatic zone`
- `"crop-recommendation-dataset" Karnataka India Kaggle N P K soil real
  district accuracy overlap 22 crops`

**Found, and rejected:**
- Several Kaggle "crop recommendation" datasets
  (`madhuraatmarambhagat/crop-recommendation-dataset`,
  `siddharthss/crop-recommendation-dataset`,
  `saganachinnathambi/crop-recommendation`) are re-uploads/derivatives
  of the *same* generic ICFA-sourced dataset already in use, not an
  independent India-district-specific source — retraining on them would
  not have changed anything.
- `imtkaggleteam/agriculture-dataset-karnataka` and
  `dataful.in`'s district/season/crop area-production dataset are real
  Karnataka-specific data, but they are **yield/area/production
  statistics by district and season**, not per-sample soil-N/P/K +
  climate feature rows with a crop label — a fundamentally different
  schema from what `CropRecommendationModel` trains on. Using them would
  require building an entirely new feature-engineering pipeline and
  training target from scratch (a new model, not a retrain of the
  existing one), which is out of this module's scope per the prompt's
  own framing of "retrain on it... following the same pattern as
  `train_crop_model.py`".
- `akshatgupta7/crop-yield-in-indian-states-dataset` and
  `shankarpriya2913/crop-and-soil-dataset` — same issue: state/district
  yield aggregates or a different, non-overlapping feature schema, not a
  drop-in replacement or supplement for the existing 7-column N/P/K/
  temp/humidity/pH/rainfall -> 22-crop-label training data.
- No ICAR, data.gov.in, or Karnataka state agriculture department
  dataset was found in per-sample ML-ready format (soil/climate features
  -> crop label) for Bellary or Karnataka specifically. ICAR-CRIDA's
  district Agriculture Contingency Plans (see below) are narrative/PDF
  reports with crop lists and area figures, not row-level training data.

**Conclusion: no usable India/Karnataka-specific crop-recommendation
dataset was found with real feature-schema overlap and enough rows to
retrain `CropRecommendationModel` meaningfully.** This is the "likely
outcome" the module prompt anticipated, and it is reported honestly
rather than forcing a low-quality or mismatched dataset in to claim
localization happened. **Option B (regional-suitability sanity layer)
is the approach taken.**

## Decision

Add `src/agro_mirai/models/regional_suitability.py`: a small,
explicitly-sourced table, `BELLARY_REGIONAL_CROPS`, of crops from the
existing 22-label `crop_type` enum that independent, cited sources
confirm are actually grown at meaningful scale in Bellary/Ballari
district:

- ICAR-CRIDA / UAS Raichur, "District Agriculture Contingency Plan —
  Bellary" (official ICAR/state-university document):
  `https://www.icar-crida.res.in/CP/Karnataka/UAS,%20Raichur/KA25-Bellary%2004.10.2011.pdf`
- Wikipedia, "Ballari district" (citing Karnataka government / census
  agricultural statistics): `https://en.wikipedia.org/wiki/Ballari_district`
- AgriFarming.in, "District Wise Crop Production in Karnataka":
  `https://www.agrifarming.in/district-wise-crop-production-in-karnataka-list-of-crops-grown-in-karnataka`

All three independently name cotton, jowar (sorghum), groundnut, rice,
sunflower, millet, and cereals as the district's major crops; source 1
additionally names Bengal gram (chickpea), pigeon peas, coriander, and
soybean, and classifies Bellary as NARP zone KA-3 (Northern Dry Zone,
erratic 400-500mm rainfall, predominantly rainfed).

**Intersected against the 22-label `crop_type` enum**, the set with both
real cited cultivation history and a matching label is:
`{cotton, rice, maize, chickpea, pigeonpeas}`. Most of Bellary's actual
dominant crops (jowar, groundnut, sunflower, millet, soybean, coriander)
have **no label at all** in the current 22-crop enum — a real limitation
of the underlying Kaggle dataset's label set, not something this sanity
layer can paper over. Maize is included on weaker evidence (broader
Northern Dry Zone contingency-crop guidance rather than a district-major-crop
citation, though it is also `farm-002`'s `current_crop`) and is flagged
as such in the module docstring.

`CropRecommendationModel.predict()` now calls
`check_regional_fit(recommended_crop, alternatives)` after producing its
ranked prediction. When the top prediction is outside
`BELLARY_REGIONAL_CROPS`, two new additive `CropRecommendation` fields
are set:

- `out_of_region: bool` — true when the top prediction is outside the
  known regional set. Absent/false for records predating this module,
  or when the check passes.
- `regional_alternative: str | None` — the highest-confidence
  regionally-plausible crop from the existing `alternatives` list, or
  `None` if none of the alternatives are regional either (reported
  explicitly, not left ambiguous).

`ExplanationService.explain_crop` appends a plain-language caveat
sentence to `summary_en` when `out_of_region` is true, naming the
regional alternative when one exists, or explicitly noting that none of
the alternatives are regional either and suggesting a local extension
officer be consulted.

## This is explicitly NOT a retrain and NOT a hard override

The underlying `CropRecommendationModel` prediction, confidence, and
`alternatives` are completely unchanged — this module adds zero new
training data and does not touch `tools/train_crop_model.py`,
`models/crop_rf.joblib`, or `docs/eval/crop_rf_eval.json`. The ML output
is always still returned as-is; `out_of_region`/`regional_alternative`
are a caveat surfaced *alongside* it, per the module prompt's explicit
requirement ("don't silently override it — flag it"). A farmer or
extension worker seeing "cotton, 92% confidence" vs. "grapes, 61%
confidence, **not commonly grown in this region, consider cotton
instead**" gets meaningfully different, more honest information without
the system pretending to know something the training data can't
actually support.

## Known limitations (honest, not swept under the rug)

- **Coverage gap, not solved by this ADR**: the crops Bellary actually
  grows the most of by area (jowar, groundnut, sunflower per the sources
  above) aren't representable at all because they aren't in the 22-crop
  enum. A field genuinely best suited to groundnut will never get
  flagged as such — it can only ever be told "your top ML pick isn't
  regional" and pointed at the best available regional alternative from
  a label set that doesn't include the crop that's actually best. Fixing
  this needs either extending `crop_type` (a schema version bump per
  CLAUDE.md's additive-only rule — new enum values are additive, but
  retraining the model on data using them is not a small change) or a
  genuine retrain on a dataset that has those labels, which section
  "Investigation" above confirms doesn't currently exist in usable form.
- **Bellary-specific, not general-purpose**: `BELLARY_REGIONAL_CROPS` is
  hardcoded to one district. It is not parameterized by `Field_.district`/
  `state`, because this project is currently single-farmer/single-region
  (ADR 0003) and both existing field fixtures are in Bellary. If/when
  multi-tenant support (Module 19+) onboards farmers outside Karnataka,
  this table will need to become field-location-aware or the flag will
  misfire for those fields — noted here so it isn't a silent surprise
  later.
- **`maize`'s inclusion is weaker-evidenced** than the other four crops
  in the set — flagged in the module docstring, not hidden.
- **Static, not sourced from a live/queryable dataset**: the table is a
  fixed Python `frozenset`, not backed by a refreshable data source. If
  Karnataka's district cropping patterns materially shift, this needs a
  manual update, same maintenance burden as `crop_coefficients.py`'s
  FAO-56 lookup table from Module 17.
- **No confidence weighting on the flag itself**: the flag is binary
  (in-region / not) — a crop grown on a handful of experimental plots
  and a crop with zero regional history both read as equally
  "out-of-region" to this layer. The underlying sources didn't provide
  fine-grained enough data to support a graded confidence signal.

## Consequences

- `CropRecommendation.out_of_region` / `regional_alternative` are new
  additive-only fields on an already-published schema entity — no
  existing field renamed/removed, per CLAUDE.md hard rule #2.
- `ExplanationService.explain_crop`'s `summary_en` output changes (grows
  a caveat sentence) exactly when `out_of_region` is true; unchanged
  otherwise. `DecisionEngine.recommend`'s `Advisory.body` inherits this
  automatically since it concatenates `summary_en` unmodified (ADR 0011).
- No change to `CropRecommendationModel`'s trained artifact, confidence
  scores, or ranking — this is purely an additive annotation layer.
- Forward-compatible with a future genuine retrain: if a usable
  Karnataka-specific dataset is later found, this sanity layer can
  either be retired or kept as a secondary honesty check even on top of
  a better-grounded model.
