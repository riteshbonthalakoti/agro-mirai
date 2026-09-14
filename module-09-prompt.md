# MODULE 09 — Explainability (SHAP)

Continuing AGRO MIRAI in the existing `agro-mirai` repo. Modules 01–08
and 12 are done and committed. Read `CLAUDE.md` and `PROGRESS.md` first
— that's your complete required context.

Note: Module 08's `DiseaseRiskModel` is rule-based (no trained artifact
— SHAP doesn't apply to it the same way it does to sklearn classifiers).
Your job is to handle this honestly, not to pretend SHAP works uniformly
across all three models.

Confirm `git config user.name`/`user.email` are correct. Same commit
discipline as prior modules.

## Scope

A uniform `Explanation` object that Module 10 (Decision Engine) can
attach to any advisory output, regardless of which model produced the
underlying prediction. SHAP handles Modules 06/07 (sklearn trained
classifiers); Module 08 gets an explicit feature-attribution alternative
that's honest about what it is.

## Tasks

### 1. ADR first — write `decisions/0010-explainability.md`
Cover:
- Why SHAP (`shap.TreeExplainer`) is appropriate for Modules 06/07's
  RandomForestClassifier/Classifier artifacts, and what its output
  means in the context of a farmer-facing advisory.
- Why SHAP doesn't apply cleanly to Module 08's rule-based scoring
  function, and what you're using instead (e.g. a direct weight-×-signal
  attribution — the same weighted formula in the scoring function
  expressed as per-feature contributions, which is already interpretable
  by construction). Be explicit that this is not SHAP; don't present it
  as SHAP.
- The `Explanation` output shape that Module 10 will consume — field IDs,
  top-k feature contributions (name + value + direction), and a
  human-readable summary string in both `en` and `kn` (via Module 12's
  `VoiceService.translate` — call it here, don't re-implement
  translation).

### 2. `ExplanationService`
A single class (or module of functions) that accepts the output of any
of the three model wrappers and returns a standardised `Explanation`:
- `explain_crop(CropRecommendation, FeatureVector) -> Explanation` —
  uses `shap.TreeExplainer` on the loaded crop RF artifact, returns
  top-3 feature contributions.
- `explain_irrigation(IrrigationAdvice, FeatureVector) -> Explanation` —
  same, uses the irrigation RF artifact.
- `explain_disease(DiseaseRiskAlert, FeatureVector) -> Explanation` —
  uses the rule-based weight-×-signal attribution from the scoring
  function; labels each contribution clearly as "contributing factor"
  not a SHAP value.
- All three return the same `Explanation` dataclass so Module 10 can
  handle them uniformly.

The `Explanation.summary_kn` field is populated by calling
`VoiceService.translate(summary_en, "en", "kn")`. The `VoiceService`
instance should be injected (constructor arg, defaults to `None` —
skip translation when not provided, leave `summary_kn=None`), so
ExplanationService can be instantiated and tested without the full
AI4Bharat model stack.

### 3. Tests — three explicit stages, report each separately
- **Unit**: each `explain_*` method in isolation with a mocked/minimal
  model and feature vector — confirm the `Explanation` shape is correct
  (top-k length, contribution directions, field IDs present). For
  Modules 06/07, mock `shap.TreeExplainer` — don't require the actual
  trained artifacts just to test the plumbing.
- **Integration**: load the real crop and irrigation artifacts, run
  `explain_crop` and `explain_irrigation` against the farm-001/farm-002
  fixtures, confirm the top contributors are agronomically sensible
  (e.g. for irrigation, soil_moisture should be a top contributor).
  The disease explanation requires no artifact — the integration test
  just exercises the full scoring path.
- **Acceptance checklist** (its own section in the handoff):
  - [ ] SHAP values for crop recommendation: top feature is identifiable
        and agronomically sensible (e.g. temperature, soil pH, or NPK
        for some crop — look at what SHAP actually returns, don't assert
        a specific feature in advance)
  - [ ] Disease explanation clearly labels its contributions as
        "contributing factor" not "SHAP value" — verify in the actual
        output, not just in the code
  - [ ] `summary_en` is a human-readable sentence (not a raw dict or
        code-like string) — spot-check the actual output for a fixture
  - [ ] `summary_kn` is produced when a VoiceService is injected (or
        `None` when not) — confirm both paths work

### 4. Update doctrine
`modules/09-explainability/STATUS`, `CLAUDE.md` phase → Module 09
complete, Module 10 next, `PROGRESS.md` row 09,
`python tools/update_state.py`, `python tools/check_specs.py`, commit
and push.

## Definition of done
- [ ] ADR 0010 written first, documenting the SHAP-vs-rule-attribution
      split honestly
- [ ] `ExplanationService` produces a uniform `Explanation` for all
      three models; Kannada translation injected, not hardwired
- [ ] Unit + integration tests pass; acceptance checklist completed in
      the handoff
- [ ] Doctrine updated, pushed to `origin/main`

## Handoff format
```
Module: 09 — Explainability (SHAP)
Status: complete | blocked
Implemented:
Files changed:
Commits made:
Unit tests: <+pass/fail>
Integration tests: <+pass/fail>
Acceptance checklist: <each item, checked or not, with a one-line note>
Known limitations:
Remaining risks:
Next recommended module: 10 — Decision & Recommendation Engine
```
