# MODULE 18 — Crop model localization (Karnataka/Bellary sanity layer)

Continuing AGRO MIRAI in the existing `agro-mirai` repo. Modules 01–17
are done (`7309166` on `origin/main`). Read `CLAUDE.md`, `PROGRESS.md`,
and `docs/ROADMAP_PRODUCTION.md` (Part 4) first — that section documents
why this module exists: `CropRecommendationModel` is trained purely on
Kaggle's generic `atharvaingle/crop-recommendation-dataset` (N/P/K/temp/
humidity/pH/rainfall, 22 global crop classes, suspiciously clean
99.55% accuracy), with no grounding in what's actually agronomically
sane for Karnataka/Bellary specifically.

Sequencing: this is the second of two model-realism modules before
Module 19 (multi-tenant + Admin, renumbered). Module 17 (ET0 irrigation
water balance) is already done — this module doesn't touch irrigation.

Confirm `git config user.name`/`user.email`. Several focused commits.

## Decide the real approach first — don't assume

Before writing code, spend real effort checking whether a genuinely
better India/Karnataka-specific crop-recommendation dataset exists and
is usable (Kaggle, data.gov.in, ICAR/state agriculture department open
data, etc.) — search for one. If you find one with real label overlap
with the current 22-crop set and enough rows to retrain meaningfully,
retraining `CropRecommendationModel` on it (or a merged/weighted
combination with the existing dataset) is the better fix and should be
the primary approach — document what you found, why it's credible, and
retrain following the same pattern as `tools/train_crop_model.py`
(fixed seed, committed eval report, gitignored artifact).

If no such dataset is realistically available within this module's
scope (this is the likely outcome — say so honestly if true, don't
force a low-quality dataset in just to say you localized it), build
**Option B: a regional-suitability sanity layer** on top of the
existing ML prediction instead:

### Option B — regional suitability sanity layer

1. A small, explicitly-sourced reference table
   (`src/agro_mirai/models/regional_suitability.py` or similar) of
   crops genuinely grown at meaningful scale in Bellary district /
   Karnataka's semi-arid agro-climatic zone — cite a real source (state
   agriculture department crop statistics, ICAR Bellary KVK
   publications, or a similar credible reference — search for one,
   don't fabricate the list from general knowledge). Include enough
   crops to be genuinely useful, not just the single field
   fixture's current crop.
2. When `CropRecommendationModel.predict()` returns a top prediction
   that ISN'T in the regional-suitability set, don't silently override
   it — flag it. Add a field (check `specs/core/schema.yaml`'s
   `CropRecommendation` entity for the right additive extension point,
   same additive-spec discipline as the `/health` and ET0 precedents)
   indicating the top prediction is outside the known-regionally-grown
   set, and surface the highest-confidence *regionally-plausible*
   alternative from the existing `alternatives` list (or explicitly
   note none of the alternatives are regional either) — this is
   presented as a caveat/flag alongside the ML output, not a silent
   substitution. The point is honesty: don't let the system confidently
   recommend, say, a crop with zero real cultivation history in the
   region without saying so.
3. Update `ExplanationService`'s crop explanation
   (`explain_crop`/`summary_en`) to mention the regional-fit flag when
   it's raised, in plain language a farmer/extension worker would
   understand.
4. This is explicitly NOT a retrain and NOT a hard override — it's an
   honesty/sanity layer on top of a model whose global training data
   can't know about local reality. Document this distinction clearly in
   a new `decisions/0016-regional-crop-suitability.md` (or a next-free
   ADR number — check `decisions/0001-index.md`).

Whichever path you take (dataset retrain vs. sanity layer, or both if a
usable dataset is found), the deliverable must be genuinely better
grounded in Karnataka/Bellary reality than the current global-generic
model, not cosmetic.

## Tests

- If retrained: same pattern as `train_crop_model.py`'s existing eval
  report discipline, plus a test confirming the new artifact loads and
  predicts sane output for the `farm-001` fixture (Bellary, Karnataka).
- If sanity layer: unit tests for the regional-suitability check
  (in-region crop → no flag; clearly out-of-region crop → flag raised,
  correct alternative surfaced or correctly reports none available).
- Integration test through `DecisionEngine`/API confirming schema-valid
  output either way.
- Full regression pass, `check_specs.py`, CI green on a real push.

## Update doctrine

`CLAUDE.md`, `PROGRESS.md` (new module row), `docs/ROADMAP_PRODUCTION.md`
(check off item 2 under "New backend priorities"), commit and push.

## Definition of done
- [ ] Real investigation into an India/Karnataka-specific dataset done
      and documented, whichever way it concluded
- [ ] Either a genuine retrain on better-grounded data, or a working
      regional-suitability sanity layer that flags (not silently
      overrides) out-of-region predictions
- [ ] Explanation text reflects the regional-fit signal when relevant
- [ ] New ADR documenting the approach and its honest limitations
- [ ] Tests, full regression, `check_specs.py` pass
- [ ] Pushed to `origin/main`

## Handoff format
```
Module: 18 — Crop model localization
Status: complete | blocked
Dataset investigation: <what was searched, found or not found, why>
Approach taken: <retrain | regional sanity layer | both>
Details: <dataset name+source if retrained, or suitability table source+crop list if sanity layer>
Files changed:
Commits made:
Tests: <new/updated, pass/fail>
Full regression: <pass/fail>
check_specs.py: pass/fail
ADR: <number, title>
Known limitations:
Next recommended module: 19 — Multi-tenant data model + real login/session auth + read-only Admin dashboard
```
