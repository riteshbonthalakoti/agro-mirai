# MODULE 07 — Irrigation Prediction Model

Continuing AGRO MIRAI in the existing `agro-mirai` repo. Modules 01–06 and
12 are done and committed (`d988c36` on `origin/main`). Read `CLAUDE.md`
and `PROGRESS.md` first — that's your complete required context.

## Before any code: two doctrine fixes, each its own commit

These are real, separate cleanup items, not part of Module 07's feature
work — commit them before starting Module 07's tasks, not folded in.

1. **`PROGRESS.md`'s Phase plan table is stale.** Row 04 shows
   "not started" (should be "done" — Storage Layer). Row 06 shows
   "TBD"/"not started" (should be "Crop Recommendation Model"/"done").
   Fix both rows to match reality. Check every other row against
   `CLAUDE.md`'s "Current phase" section and the actual `modules/*/STATUS`
   files while you're in there — don't just patch the two known-wrong
   rows if you find others drifted.
2. **`docs/testing-strategy.md` exists on disk but was never committed**
   (neither Module 06 nor Module 12 claimed it — check `git log -- docs/testing-strategy.md`
   to confirm it's genuinely new, then `git add` and commit it with an
   honest message; don't attribute it to a module that didn't write it if
   you can't tell which one did — a plain "docs: commit testing strategy
   (previously untracked)" is fine).

Also: confirm `git config user.name`/`user.email` are still correct, and
check for a stale `.git/index.lock` before your first git command — if
one exists and `git status` hangs or errors with "Unable to create...
File exists", delete it (it's safe to delete if no git process is
actually running — check with a process list first) before proceeding.

## Scope

Train and wrap the irrigation prediction model — per the PPT, this
predicts whether/how much to irrigate from soil moisture proxy + weather
+ crop stage. Same pattern as Module 06: consumes Module 05's
`FeatureBuilder` output, produces a schema-valid `IrrigationAdvice`.

## Tasks

### 1. Confirm the training data source
The PPT's methodology doesn't specify a single canonical irrigation
dataset the way it did for crop recommendation. Search Kaggle via the
`kaggle` CLI for a suitable soil-moisture/irrigation dataset (e.g. a
smart-irrigation or crop-water-requirement dataset with soil moisture,
weather, and crop-stage-like features). Pick one, document why in
`docs/architecture.md` (source, license/attribution, why it's a
reasonable proxy for this project's use case), same discipline as
Module 06's dataset note. If nothing suitable exists on Kaggle, say so
explicitly in your handoff and propose the fallback (e.g. a rule-based
model documented as a v1 placeholder for a future ML upgrade) rather
than silently forcing a bad dataset fit.

### 2. The feature-mapping decision — write this down before training
Same discipline as Module 06 (`decisions/0007-crop-model-feature-mapping.md`
is your template). Write `decisions/000N-irrigation-model-feature-mapping.md`
documenting the mapping from `FeatureBuilder`'s output to whatever shape
the trained model expects, before writing the training script.

### 3. Training script (`tools/train_irrigation_model.py`)
- Fixed random seed, documented.
- Train/test split, report the appropriate regression/classification
  metrics for whatever target the dataset supports (e.g. RMSE/MAE for a
  continuous irrigation-amount target, or accuracy/F1 if it's a
  irrigate-yes-no classification — match the model type to what
  `IrrigationAdvice` in `schema.yaml` actually needs).
- Save the trained artifact locally (e.g. `models/irrigation_model.joblib`)
  — already covered by `.gitignore`'s `/models/` pattern, confirm it is.
  Commit the eval report (JSON/markdown), not the binary.

### 4. `IrrigationPredictionModel` wrapper
Loads the artifact, exposes `predict(features) -> IrrigationAdvice`
matching `schema.yaml` exactly. Keep sklearn/model-library objects out of
the public interface, same as Module 06's wrapper.

### 5. Tests — three explicit stages, report each separately
- **Unit**: the feature-mapping function in isolation, the wrapper's
  output validated against `schema.yaml` (reuse `check_specs.py`'s
  validation logic).
- **Integration**: `farm-001`/`farm-002` fixture → `FeatureBuilder` →
  feature-mapping → `IrrigationPredictionModel.predict` → schema-valid
  `IrrigationAdvice`, exercised end to end.
- **Acceptance checklist** (manual, its own section in the handoff):
  - [ ] Held-out metrics reported and sanity-checked (not suspiciously
        perfect, not unusably bad)
  - [ ] Predictions for the fixture fields are agronomically plausible
        (a cotton field mid-season shouldn't get a wildly implausible
        irrigation recommendation) — quick human read, not a formal metric
  - [ ] Re-running the training script from scratch reproduces the same
        eval numbers

### 6. Update doctrine
`modules/07-irrigation-model/STATUS`, `CLAUDE.md` phase → Module 07
complete, Module 08 next, `PROGRESS.md`'s Phase plan table (row 07),
`python tools/update_state.py`, `python tools/check_specs.py`, commit.

## Definition of done
- [ ] `PROGRESS.md` phase-table fix and `testing-strategy.md` commit done
      first, as their own commits
- [ ] Dataset choice documented with reasoning (or fallback explicitly
      justified if no suitable dataset exists)
- [ ] Feature-mapping ADR written before the training script
- [ ] Model trains reproducibly, artifact gitignored, eval report committed
- [ ] Unit + integration tests pass; acceptance checklist completed and
      included in the handoff as its own section
- [ ] Doctrine updated (including `PROGRESS.md` row 07), pushed to `origin/main`

## Handoff format
```
Module: 07 — Irrigation Prediction Model
Status: complete | blocked
Preamble fixes: PROGRESS.md table corrected (rows fixed: ...), testing-strategy.md committed (commit: ...)
Implemented:
Files changed:
Commits made:
Unit tests: <+pass/fail>
Integration tests: <+pass/fail>
Acceptance checklist: <each item, checked or not, with a one-line note>
Known limitations:
Remaining risks:
Next recommended module: 08
```
