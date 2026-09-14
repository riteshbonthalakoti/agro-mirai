# MODULE 08 — Crop Health / Disease Risk

Continuing AGRO MIRAI in the existing `agro-mirai` repo. Modules 01–07
and 12 are done and committed. Read `CLAUDE.md` and `PROGRESS.md` first
— that's your complete required context. No concurrent session this
time: M09 depends on this module, M10 depends on M09, M11 depends on
M10 — it's a single-file chain from here through the API layer, so this
one runs alone.

Confirm `git config user.name`/`user.email` are correct before your
first commit. Same commit discipline as prior modules: one commit per
real checkpoint.

## Scope — this is a locked scope decision, not a shortcut

Per the roadmap's decision 5, M08 ships as a **threshold + lightweight
risk model MVP**, not a PlantVillage-trained image CNN. This is a
deliberate, documented scope call made before this module started — the
full CNN is a drop-in upgrade slot for later, not something to sneak in
under time pressure, and not something to apologize for in the handoff.
Build the MVP well rather than building a rushed, undertested CNN.

The MVP predicts disease risk from **environmental/feature signals**,
not images: humidity, temperature, NDVI trend/level, and rainfall are
real, established agronomic risk proxies for major crop diseases
(e.g. high humidity + moderate temp + NDVI decline is a classic fungal-
risk signature) — this is not a toy stand-in, it's a real, if simpler,
approach used in actual agronomy extension tools.

## Tasks

### 1. The feature-mapping / risk-model decision — write this down first
`decisions/0009-disease-risk-model.md` (ADR 0008 was Module 07's,
confirm the number by checking `decisions/` before writing). Cover:
- Which `FeatureBuilder` outputs drive the risk score (weather
  aggregates, NDVI trend, season) and why each is a legitimate signal
  for disease risk specifically, not just reused because they're
  available.
- Whether this is a rule/threshold system, a lightweight trained
  classifier (e.g. logistic regression / small RF on a proxy-labeled
  dataset if you find one), or a hybrid — your call, but justify it
  against what's actually achievable without an image dataset.
- The explicit CNN upgrade path: what would need to change (a real
  image classifier consuming photos, presumably behind the same output
  shape) and confirm it's a genuinely additive swap, not a rewrite of
  `DiseaseRiskAlert`'s shape.
- If you use any labeled dataset for calibration (even a small one),
  document source/license the way Module 06/07 did — don't fabricate
  thresholds without basis; cite the agronomic reasoning if no dataset
  exists to calibrate against.

### 2. `DiseaseRiskModel` (or similar) wrapper
Consumes a `Field` + its `FeatureBuilder` output (same input shape as
Modules 06/07), produces a schema-valid `DiseaseRiskAlert` (check
`schema.yaml` for the exact fields — risk level, likely disease/cause if
in scope, confidence or basis). Keep the interface clean the same way
Module 06/07's wrappers kept sklearn out of the public surface — Module
09 (explainability) needs to call this uniformly across all three
models (06/07/08), so match their calling convention.

### 3. Tests — three explicit stages, report each separately
- **Unit**: the risk-scoring function in isolation against known
  inputs → known expected risk level; output validated against
  `schema.yaml` (reuse `check_specs.py`'s logic).
- **Integration**: `farm-001`/`farm-002` fixture → `FeatureBuilder` →
  risk model → schema-valid `DiseaseRiskAlert`, end to end.
- **Acceptance checklist** (its own section in the handoff):
  - [ ] Risk outputs for the fixture fields are agronomically plausible
        given their weather/NDVI conditions — a quick human sanity read
  - [ ] The threshold/model logic doesn't trivially return the same risk
        level regardless of input (test with at least one deliberately
        high-risk and one deliberately low-risk synthetic input, not
        just the fixtures)
  - [ ] CNN upgrade path is genuinely additive — confirm by checking
        `DiseaseRiskAlert`'s schema doesn't need to change shape for a
        future image-based version to slot in

### 4. Update doctrine
`modules/08-disease-risk/STATUS`, `CLAUDE.md` phase → Module 08
complete, Module 09 next, `PROGRESS.md`'s Phase plan table (row 08),
`python tools/update_state.py`, `python tools/check_specs.py`, commit.

## Definition of done
- [ ] ADR written before the model/scoring logic, documenting the
      MVP approach and the CNN upgrade path
- [ ] `DiseaseRiskModel` wrapper matches `schema.yaml` exactly, calling
      convention consistent with Modules 06/07's wrappers
- [ ] Unit + integration tests pass; acceptance checklist completed and
      included in the handoff as its own section
- [ ] Doctrine updated (including `PROGRESS.md` row 08), pushed to
      `origin/main`

## Handoff format
```
Module: 08 — Crop Health / Disease Risk
Status: complete | blocked
Implemented:
Files changed:
Commits made:
Unit tests: <+pass/fail>
Integration tests: <+pass/fail>
Acceptance checklist: <each item, checked or not, with a one-line note>
Known limitations:
Remaining risks:
Next recommended module: 09 — Explainability (SHAP) — needs Modules 06, 07, 08 all done
```
