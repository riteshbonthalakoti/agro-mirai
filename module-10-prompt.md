# MODULE 10 — Decision & Recommendation Engine

Continuing AGRO MIRAI in the existing `agro-mirai` repo. Modules 01–09
and 12 are done and committed. Read `CLAUDE.md` and `PROGRESS.md` first.

Confirm `git config user.name`/`user.email` are correct. Same commit
discipline as prior modules.

## Before Module 10 work: one test-hygiene fix, its own commit

`tests/models/test_explanation_service.py` and
`tests/models/test_explanation_integration.py` (Module 09) have no
auto-skip guard for when `shap` is not installed — a fresh interpreter
without shap gets 5 hard failures instead of 5 clean skips. Every other
module with an optional dep uses a skip guard (e.g.
`tests/models/test_crop_model_integration.py`, `tests/voice/`). Fix
this first, its own commit, before starting Module 10:

```python
# at the top of each test file, after imports
try:
    import shap  # noqa: F401
    _SHAP_AVAILABLE = True
except ImportError:
    _SHAP_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _SHAP_AVAILABLE,
    reason="shap not installed — pip install shap to run these tests",
)
```

Confirm the full suite still passes (or skips cleanly when shap is
absent) after this fix before proceeding.

## Scope

The decision engine is the central orchestrator: it takes a `Field` +
`FeatureVector`, calls all three model wrappers (crop, irrigation,
disease), gets explanations for each via `ExplanationService`, and
assembles a unified `Advisory` matching `schema.yaml` exactly. This is
what Module 11 (the Flask API) will call as its core logic.

## Tasks

### 1. ADR first — `decisions/0011-decision-engine.md`
Cover:
- How the engine resolves conflicts or priorities (e.g. when irrigation
  urgency is high but crop recommendation suggests a drought-tolerant
  crop — does the engine synthesise, flag both, or pass both through
  unmodified? Decide explicitly).
- Whether the engine calls all three models always, or gates on data
  availability (e.g. skip irrigation if soil moisture is missing — same
  missing-data discipline as Module 05's imputation policy).
- How `Advisory` fields map to the three models' outputs + explanations.

### 2. `DecisionEngine`
A class with one primary method:
`recommend(field: Field, features: FeatureVector) -> Advisory`

Internally:
- Calls `CropRecommendationModel.predict`, `IrrigationPredictionModel.predict`,
  `DiseaseRiskModel.predict`
- Calls `ExplanationService.explain_crop/irrigation/disease` for each
- Assembles an `Advisory` matching `schema.yaml` (check the exact fields
  — `recommended_crop`, `irrigation_advice`, `disease_risk`, `explanation`
  or similar — use what's there, don't add new fields)
- The `VoiceService` and `ExplanationService` are injected (not
  hardwired) so Module 11 can configure them; defaults to creating them
  internally if not provided.

### 3. Alert thresholds
If `DiseaseRiskAlert.risk_level` is `high` or `severe`, or
`IrrigationAdvice.urgency` is `high` or `severe`, the engine should
set a flag or field on the `Advisory` indicating it warrants immediate
action (check `schema.yaml` for whether this field already exists —
don't add a new field that contradicts the contract).

### 4. Tests — three explicit stages
- **Unit**: `DecisionEngine.recommend` with all three model wrappers and
  `ExplanationService` mocked — confirm the `Advisory` output is
  schema-valid and the alert threshold logic fires correctly for known
  inputs.
- **Integration**: `farm-001`/`farm-002` fixture → `FeatureBuilder` →
  `DecisionEngine.recommend` → schema-valid `Advisory`, end to end with
  real model artifacts. This is the first test that proves all modules
  05–09 actually compose correctly together.
- **Acceptance checklist**:
  - [ ] `Advisory` output for farm-001 is schema-valid (reuse
        `check_specs.py`'s validation) and contains real, non-null
        values from all three models
  - [ ] Alert threshold fires correctly for a synthetic high-urgency
        input — confirm the flag/field is set
  - [ ] The full fixture chain (data → features → three models →
        explanations → advisory) runs end to end without error

### 5. Update doctrine
`modules/10-decision-engine/STATUS`, `CLAUDE.md` phase → Module 10
complete, Module 11 next, `PROGRESS.md` row 10,
`python tools/update_state.py`, `python tools/check_specs.py`, commit
and push.

## Definition of done
- [ ] Module 09 skip-guard fix committed first, its own commit
- [ ] ADR 0011 written before the engine code
- [ ] `DecisionEngine.recommend` produces schema-valid `Advisory`;
      alert thresholds tested
- [ ] Unit + integration tests pass; acceptance checklist in handoff
- [ ] Doctrine updated, pushed to `origin/main`

## Handoff format
```
Module: 10 — Decision & Recommendation Engine
Status: complete | blocked
Preamble fix: Module 09 shap skip-guard (commit: ...)
Implemented:
Files changed:
Commits made:
Unit tests: <+pass/fail>
Integration tests: <+pass/fail>
Acceptance checklist: <each item, checked or not, with a one-line note>
Known limitations:
Remaining risks:
Next recommended module: 11 — API Layer (Flask)
```
