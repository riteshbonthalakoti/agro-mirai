# MODULE 06 — Crop Recommendation Model

Continuing AGRO MIRAI in the existing `agro-mirai` repo. Modules 01–05 are
done and committed. Read `CLAUDE.md` and `PROGRESS.md` first.

NOTE: A second Claude Code session may be running Module 12 (Voice &
Language) concurrently in this same folder — it touches an unrelated part
of the tree (`src/agro_mirai/voice/`), so this shouldn't conflict, but
`git pull` before you start and before you push, and re-run the full test
suite after pulling in case anything landed while you worked.

Confirm `git config user.name`/`user.email` are still correct. Same commit
discipline as Modules 04–05: one commit per real checkpoint.

## Scope

Train and wrap the crop recommendation model — Random Forest / Gradient
Boosting per the PPT's methodology — using the Kaggle crop-recommendation
dataset, and expose it as something that consumes Module 05's
`FeatureBuilder` output and produces a schema-valid `CropRecommendation`.

## Tasks

### 1. Get the dataset via CLI (kaggle already authenticated)
`kaggle datasets download atharvaingle/crop-recommendation-dataset`, unzip
into a gitignored `data/raw/` (already in `.gitignore`). Note the dataset's
license/attribution in `docs/architecture.md`.

### 2. The feature-mapping decision — write this down before training
The Kaggle dataset's columns (N, P, K, temperature, humidity, ph, rainfall)
are NOT the same shape as Module 05's `FeatureBuilder` output (weather
rollups, soil pass-through + NPK index, NDVI trend, season). You need an
explicit, documented mapping from `FeatureBuilder`'s output to whatever
shape the trained model actually expects — write this as an ADR
(`decisions/000N-crop-model-feature-mapping.md`) before writing the
training script, not as an afterthought once you notice the mismatch.

### 3. Training script (`tools/train_crop_model.py`)
- Fixed random seed, documented.
- Train/test split, report accuracy + macro-F1 + confusion matrix.
- Save the trained model artifact locally (e.g. `models/crop_rf.joblib`)
  — **do not commit the binary artifact to git**; add `models/` to
  `.gitignore` and document in `docs/architecture.md` that the model is
  reproducible by re-running this script, not version-controlled. Commit
  the eval report (metrics as JSON or markdown) instead — that's the part
  that needs to be visible and diffable.

### 4. `CropRecommendationModel` wrapper
Loads the artifact, exposes `predict(features) -> CropRecommendation`
matching `schema.yaml` exactly — `recommended_crop`, `confidence`,
`alternatives` (top-k by probability), `season`. This is what Module 09
(explainability) and Module 10 (decision engine) will call — keep the
interface clean, don't leak sklearn objects past this wrapper.

### 5. Tests — three explicit stages, report each separately
- **Unit**: the feature-mapping function in isolation (known input →
  known expected shape), the wrapper's output validated against
  `schema.yaml` (reuse `check_specs.py`'s validation logic, don't
  duplicate it).
- **Integration**: the full chain — `farm-001`/`farm-002` fixture →
  `FeatureBuilder` → feature-mapping → `CropRecommendationModel.predict`
  → schema-valid `CropRecommendation` — actually exercised end to end,
  not mocked partway through.
- **Acceptance checklist** (manual, report as a checklist in the handoff,
  not folded into the pass/fail count):
  - [ ] Held-out test accuracy and macro-F1 reported and reviewed —
        sanity-check they're not suspiciously perfect (would suggest
        leakage) or unusably bad
  - [ ] Predictions for `farm-001`'s cotton field and any other fixture
        field are agronomically plausible for the region/season — a
        quick human sanity read, not a formal metric
  - [ ] Re-running the training script from scratch reproduces the same
        eval numbers (proves the seed/reproducibility claim is real)

### 6. Update doctrine
`modules/06-crop-model/STATUS`, `CLAUDE.md` phase → Module 06 complete,
Module 07 next, `python tools/update_state.py`, `python tools/check_specs.py`,
commit.

## Definition of done
- [ ] Feature-mapping ADR written before the training script, not after
- [ ] Model trains reproducibly, artifact excluded from git, eval report
      committed
- [ ] Unit + integration tests pass; acceptance checklist completed and
      included in the handoff as its own section
- [ ] Pulled/merged cleanly against any Module 12 changes before pushing
- [ ] Doctrine updated, pushed to `origin/main`

## Handoff format
```
Module: 06 — Crop Recommendation Model
Status: complete | blocked
Implemented:
Files changed:
Commits made:
Unit tests: <+pass/fail>
Integration tests: <+pass/fail>
Acceptance checklist: <each item, checked or not, with a one-line note>
Known limitations:
Remaining risks:
Next recommended module: 07 — Irrigation Prediction Model
```
