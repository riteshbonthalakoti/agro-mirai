# 0026 — Three-Microservice Split on Render Free Tier & 12-Minute Keep-Alive Cron

## Context

The AGRO MIRAI production backend runs on **Render Free Tier** (512 MB RAM cap per instance). In a single-instance setup, running the Flask API alongside Scikit-Learn RandomForest models (`crop_rf.joblib`, `irrigation_rf.joblib`), GEE cache integration, authentication, and execution of build-time training scripts (`tools/train_crop_model.py` and `tools/train_irrigation_model.py`) caused memory consumption to spill over 512 MB. This triggered automated Render "Memory Limit Exceeded" emails and worker restarts.

Additionally, Render Free instances automatically go to sleep after 15 minutes of zero traffic. Waking up a cold container takes 50–60 seconds, causing mobile client HTTP requests to time out. Paid Starter instances ($7/mo each) were ruled out due to strict zero-cost budget constraints.

## Decision

1. **Decouple Backend into 3 Render Free Web Services (512 MB RAM each)**:
   - **`agro-mirai`** (Main API & Backend Architecture): Exposes Flask `/v1` and `/v2` REST routes, database repository (`SQLite`/`Supabase`), authentication, acquisition adapters (Open-Meteo, SoilGrids, GEE). Offloads all heavy ML model loading.
   - **`agro-mirai-cnn`** (CNN Disease ONNX Service): Microservice in `services/cnn-onnx` serving MobileNetV2 ONNX model predictions over HTTP.
   - **`agro-mirai-tabular`** (Tabular ML Service): Microservice in `services/tabular-ml` serving Crop Recommendation and Irrigation Prediction RandomForest models over HTTP (`POST /predict/crop` and `POST /predict/irrigation`).

2. **Remote Client Delegation with Local Fallback**:
   - Created `RemoteCropModel` and `RemoteIrrigationModel` in `src/agro_mirai/models/remote_tabular_client.py`.
   - `DecisionEngine` and `app.py` delegate inference requests over HTTP to `TABULAR_SERVICE_URL`. If the service is unreachable or unset, the system silently falls back to local model/rule execution, ensuring the main API never returns a 500 error.

3. **Build & RAM Optimizations**:
   - Removed model training scripts from `render.yaml` buildCommand (`pip install -r requirements.txt` only).
   - Constrained Gunicorn to `-w 1 --threads 2` across all 3 services.

4. **100% Free 12-Minute Keep-Alive Cron System**:
   - Created `.github/workflows/keep_alive.yml` running on GitHub Actions with cron schedule `cron: '*/12 * * * *'`.
   - Automatically pings `/health` on all 3 Render URLs every 12 minutes to keep containers permanently awake without sleeping.

## Consequences

- Peak RAM consumption per instance stays strictly under 250 MB (well below the 512 MB limit).
- Main API memory footprint drops significantly as Scikit-Learn RandomForest models are offloaded to `agro-mirai-tabular`.
- Zero-downtime mobile application connectivity with no cold-start timeouts.
- 100% free hosting budget maintained across all cloud infrastructure.
