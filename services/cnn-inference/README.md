# CNN inference service

Standalone Flask service wrapping `ImageDiseaseRiskModel` (Module 20)
behind HTTP, meant to run as its own Docker container on the Oracle VM
(`docs/deploy/oracle-vm-setup.md`) — NOT inside the main Render-hosted
`agro_mirai` Flask app, because torch/torchvision are deliberately kept
out of the main app's dependency set (same policy as the Module 12 voice
stack, `decisions/0014-deploy-target-and-voice-scope.md`).

## Endpoints

- `GET /health` — `{"status": "ok"}` if the model is loaded (or loads
  successfully on demand), `{"status": "degraded", "detail": "..."}`
  otherwise. Never 500s. Mirrors
  `src/agro_mirai/api/routes/health.py`'s response shape.
- `POST /predict` — multipart form: `image` (file), `field_id` (string).
  Returns the same JSON shape `agro_mirai.api.serializers.to_json`
  produces for a `DiseaseRiskAlert` (`id`, `field_id`, `created_at`,
  `disease`, `risk_level`, `confidence`, `window_start_at`,
  `window_end_at`, `recommended_action`). 400 on a missing file/field_id,
  503 if the model can't load (missing weights), 422 on an inference
  error (e.g. an unreadable image).

## Getting the trained artifact onto the VM

The trained artifacts (`models/disease_cnn_mobilenetv2.pt`,
`models/disease_cnn_class_names.json`) are gitignored, same as
`crop_rf.joblib`/`irrigation_rf.joblib` — they are never built inside
this container. Chosen approach: **plain `scp` + a Docker bind mount**,
not a build-time `COPY` and not a registry-hosted volume — simplest thing
that works for a single VM with no CI/CD pipeline for this artifact yet.

```bash
# From wherever tools/train_disease_cnn.py's Colab output was downloaded:
scp models/disease_cnn_mobilenetv2.pt models/disease_cnn_class_names.json \
    ubuntu@<oracle-vm-ip>:/opt/agro-mirai/models/
```

`docker-compose.yml` at the repo root mounts `/opt/agro-mirai/models` on
the host to `/models` in the container (matches `CNN_WEIGHTS_PATH`/
`CNN_CLASS_NAMES_PATH`'s defaults in the `Dockerfile`). Re-running the
`scp` and restarting the container (`docker compose restart cnn-inference`)
is the whole "redeploy a new model version" workflow — no rebuild needed.

## ARM64 CPU torch wheel — open question, documented not asserted

Oracle's free-tier Ampere A1 shape is `aarch64`. PyTorch does publish
CPU wheels for `linux_aarch64` on both PyPI and
`download.pytorch.org/whl/cpu` for the 2.5.x line pinned in
`requirements.txt`, and this Dockerfile's base image
(`python:3.12-slim`) has an official `arm64` variant — so this **should**
build correctly on the VM. This was **not verified by an actual arm64
build** in this session (no Oracle VM exists yet, per project scope).
Before relying on this in production: `docker compose build cnn-inference`
on the real VM and confirm `import torch; print(torch.__version__)`
works, before assuming the requirements.txt pins are correct as-is. If
wheel resolution fails, the escape hatches (in order of preference) are:
(1) pin an even more recent torch release with confirmed aarch64 wheels,
(2) build under QEMU `--platform linux/amd64` emulation (works, much
slower, higher CPU/RAM use on already-constrained free-tier resources),
(3) build torch from source (last resort, very slow, likely impractical
on a 2 OCPU free-tier VM).

## Local testing without torch installed

`tests/test_predict_route.py` injects a stub model via `create_app`'s
`model_factory` parameter, so the route logic (multipart handling,
400/503/422 branches, response shape) is fully covered without torch
installed — mirrors how `tests/vision/` isolates real-model tests from
the rest of this repo's default `pytest` run. This service's own test
suite lives under `services/cnn-inference/tests/`, excluded from the main
`pytest --ignore=tests/voice --ignore=tests/vision` CI run — run it
separately: `pytest services/cnn-inference/tests`.
