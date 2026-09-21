# 0025 — Leaf-disease CNN served from ONNX on a second free Render service

## Context

The hosted API (Render free, 512 MB) cannot run the torch build of the leaf
CNN, and the planned Oracle VM (ADR 0019) does not exist. Without a hosted CNN,
every photo scan on the deployed backend falls back to the weather-based
estimate, and the app (correctly) reports "photo check unavailable". Hugging
Face Docker Spaces now need a paid PRO plan, so they were ruled out.

## Decision

Export the trained MobileNetV2 to ONNX (`services/cnn-onnx/model/`) and serve it
with onnxruntime + numpy + Pillow in a separate free Render web service
(`agro-mirai-cnn`). Same contract as `services/cnn-inference`
(`POST /predict`, `GET /health`), so `cnn_client.py` needed only an optional
shared-secret header (`CNN_SERVICE_TOKEN` -> `X-Service-Token`), which also
closes ADR 0019's "these services have no authentication" gap.

* Faithfulness: the ONNX model returns the same class and probabilities as the
  torch model (max difference < 1e-5) on all seven sample photos.
* Alert rules (risk level, action, window) are imported from
  `agro_mirai.models.disease_cnn_labels` / `disease_risk_scoring`, not copied,
  so the two serving paths cannot drift.
* The main API's `/health` wakes the photo service in the background (at most
  every 5 minutes), because the app pings `/health` on launch.

## Consequences

* The torch service (`services/cnn-inference`) and the Oracle plan remain valid
  alternatives; nothing was removed.
* Two free instances mean two cold starts; the warm-up above hides the second.
* The ONNX file (9 MB) is committed under `services/cnn-onnx/model/` because
  `/models/` is git-ignored. Retraining requires re-exporting it.
* Known limits are unchanged from ADR 0018: only 4 of the 38 trained crops exist
  in the app's crop list, and validation accuracy is on lab-condition photos.
