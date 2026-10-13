# ADR 0018 — Disease CNN: MobileNetV2 on PlantVillage, additive to the rule-based path

**Status:** accepted
**Date:** 2026-08-30
**Module:** 20 — Disease detection CNN

## Context

ADR 0009 locked Module 08's scope to a rule-based environmental score
because no photo input existed anywhere upstream, and explicitly deferred
an image classifier to a later module with its own additive
`predict(image, field_id) -> DiseaseRiskAlert` entry point. Module 20
builds that path.

## Training setup

Dataset: Kaggle `abdallahalidev/plantvillage-dataset`, `color/` split
only (the `grayscale/` and `segmented/` variants in the same download
were not used). 38 classes, ~55k images, standard PlantVillage — the
same corpus almost every published PlantVillage CNN result is trained
on.

Trained on a Google Colab T4 GPU session (driven via the `colab` CLI,
not the browser UI — see `tools/train_disease_cnn.py`, which documents
the exact reproduction steps and is not runnable locally: this repo's
main venv deliberately excludes torch/torchvision, same policy as the
Module 12 voice stack, decisions/0014). Architecture: `torchvision`
MobileNetV2 pretrained on ImageNet, feature extractor frozen except the
last 3 blocks (fine-tuned), classifier head replaced with a
38-way linear layer. 85/15 train/val split (seed 42), 8 epochs, Adam
(lr 1e-3, step decay), standard augmentation (random crop/flip/rotation/
color jitter) on the train split only.

Artifact: `models/disease_cnn_mobilenetv2.pt` (state_dict) +
`models/disease_cnn_class_names.json` (class-index -> PlantVillage
folder name), both gitignored like `crop_rf.joblib`/`irrigation_rf.joblib`
— reproducible by re-running `tools/train_disease_cnn.py` on a Colab GPU.
Eval numbers: see `docs/eval/disease_cnn_eval.json`.

## Honest limitations (documented, not hidden)

1. **Crop-enum coverage is narrow.** Only 4 of PlantVillage's 38 classes'
   crops — apple, corn/maize, grape, orange — are in AGRO MIRAI's 22-value
   `crop_type` enum (`specs/core/enums.md`). The other 34 classes (pepper,
   potato, tomato, blueberry, cherry, peach, raspberry, soybean, squash,
   strawberry) are real, trained, working disease classes — the CNN will
   correctly identify a photographed tomato leaf disease — but that crop
   has no `crop_type` label anywhere else in this codebase, so today
   there's no way to cross-reference a CNN disease call against a field's
   recommended/actual crop the way `regional_suitability.py` does for
   Module 18. `src/agro_mirai/models/disease_cnn_labels.py`'s
   `CNN_COVERED_CROP_TYPES`/`crop_type_for` exist so a future caller can
   make that comparison once it's needed.
2. **Lab images, not field photos.** PlantVillage images are single
   detached leaves on a plain background under controlled lighting — a
   real farmer's phone photo of a leaf still on the plant, in field
   lighting, with soil/other-leaves in frame, is a meaningfully different
   input distribution. Published research (the same caveat is widely
   reported for PlantVillage-trained models) shows accuracy on
   real-field photos can be substantially lower than PlantVillage's own
   held-out validation accuracy. This is a real generalization risk, not
   resolved by this module — noted here rather than implied away by a
   high validation number.
3. **No severity ground truth.** Unlike ADR 0009's rule-based path (which
   at least has an agronomically-reasoned threshold table), this CNN has
   no per-disease severity data. `risk_level_for`
   (`disease_cnn_labels.py`) is a documented heuristic: healthy -> `low`;
   any disease call floors at `moderate` regardless of confidence (a
   missed real disease is worse than an unnecessary scouting trip) and
   scales up to `high`/`severe` purely off the model's own softmax
   confidence, which is a measure of *classification* certainty, not
   disease *severity* — a real disease predicted at 90% confidence isn't
   necessarily worse for the plant than one at 65%, it's just a class the
   model is more sure about.

## Decision: additive, not integrated into `DecisionEngine` yet

`ImageDiseaseRiskModel.predict(image, field_id) -> DiseaseRiskAlert`
(`src/agro_mirai/models/image_disease_risk_model.py`) matches
`DiseaseRiskAlert`'s existing shape exactly, confirmed field by field per
ADR 0009's own upgrade-path table — no schema change. It reuses
`disease_risk_scoring.py`'s `RISK_ACTION`/`RISK_WINDOW_DAYS` lookups
(newly exported as public aliases) so the risk-level -> action/window
mapping stays single-sourced across both the rule-based and CNN paths.

**`DecisionEngine.recommend` and the API layer do not call this model
yet.** No `Field`/API contract anywhere in this codebase carries an image
upload today (same gap ADR 0009 identified as the real blocker to an
image classifier, not the model itself) — wiring an image-upload
endpoint, storage, and the `DecisionEngine`-side choice of image-path vs.
environmental-path per ADR 0009's fallback sketch is real, additional
scope, not part of this module. This module delivers the trained model
and its wrapper as a working, tested, standalone unit; the upload
path is a documented follow-up.

## Consequences

- `models/` gains two more gitignored artifacts, same pattern as
  Modules 06/07.
- `tests/vision/` (new, mirrors `tests/voice/`'s exclusion) holds
  `ImageDiseaseRiskModel`'s tests; both `tests/voice` and `tests/vision`
  are excluded from the default CI/local `pytest` run (torch not in the
  main venv) and run separately under `.venv/`.
- Anyone re-training later should re-run `tools/train_disease_cnn.py` on
  a fresh Colab GPU session and diff `docs/eval/disease_cnn_eval.json`
  before trusting a new artifact, same convention as
  `requirements.txt`'s note on `train_crop_model.py`/
  `train_irrigation_model.py`.
