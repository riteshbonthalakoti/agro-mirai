# 0029 - Remove the tabular service and the RandomForest models

Status: accepted, 2026-09-25. Supersedes the tabular part of 0026.

## Why
Module 43 replaced the crop and irrigation RandomForests with rules (EcoCrop suitability, FAO-56 water
balance; see 0027). After that nothing called the trained models, but the code, model files, the
`agro-mirai-tabular` Render service and the SHAP explainer were still there, and CI still trained the
models on every run.

## What was removed
- `services/tabular-ml/`, `remote_tabular_client.py`, the feature-mapping modules, `tools/train_crop_model.py`,
  `tools/train_irrigation_model.py`.
- scikit-learn, scipy, joblib, shap and friends from `requirements.txt` (pandas moved to dev).
- The Render `agro-mirai-tabular` service and its keep-alive ping.

## What changed
- `ExplanationService` reports the rationale the rule already wrote for crop and irrigation
  (`method="rule_weight"`); the disease explanation is unchanged.
- The main API is lighter and has one fewer service that can be asleep or down.

## Trade-off
The old RF eval reports stay in `docs/eval/` as history only.
