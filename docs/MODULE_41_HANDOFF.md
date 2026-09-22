# Module 41 Handoff — 3-Service Render Microservice Split & 12-Minute Keep-Alive Cron

**Status:** done, 2026-09-23  
**Depends on:** Module 21 (Deployment Architecture), Module 25 (ONNX Leaf CNN Service)  
**Scope:** 100% Free-Tier Infrastructure Hardening, RAM Optimization (< 512 MB RAM limit), Microservice Decoupling, and 24/7 Zero-Cost Uptime.

---

## 1. Problem & Context

The hosted backend runs on Render's **Free Tier** (512 MB RAM per web service). When running the Flask API, Scikit-Learn models, GEE satellite cache integration, authentication, and execution of build-time training scripts (`train_crop_model.py` / `train_irrigation_model.py`) within a single instance, peak RAM exceeded 512 MB. This triggered automated Render "Memory Limit Exceeded" emails and worker terminations.

Furthermore, Render Free services spin down to sleep after 15 minutes of zero traffic. Waking up a cold Python container takes 50–60 seconds, causing mobile client requests to time out. Paid plans ($7/mo each) were ruled out due to strict zero-budget requirements.

---

## 2. Architecture & Microservices Split

The backend is decoupled into **3 free-tier web services on Render**:

```
                            ┌─────────────────────────────────┐
                            │  Mobile App Client / Frontend   │
                            └────────────────┬────────────────┘
                                             │ REST API
                                             ▼
                            ┌─────────────────────────────────┐
                            │  Service 1: `agro-mirai`        │
                            │  (Main API & Architecture)      │
                            │  Flask /v1 & /v2, Auth, DB,     │
                            │  Adapters, Orchestration        │
                            └────────┬───────────────┬────────┘
                                     │               │
                   HTTP /predict     │               │ HTTP /predict/crop & /irrigation
                  (CNN image alert)  │               │ (Tabular RandomForest)
                                     ▼               ▼
          ┌────────────────────────────┐   ┌────────────────────────────┐
          │ Service 2: `agro-mirai-cnn`│   │ Service 3: `agro-mirai-ml` │
          │ (CNN ONNX Disease Service) │   │ (Tabular ML Service)       │
          │ MobileNetV2 ONNX           │   │ Crop & Irrigation RF models│
          └────────────────────────────┘   └────────────────────────────┘
```

1. **`agro-mirai` (Main API & Core Architecture)**:
   - **URL**: `https://agro-mirai.onrender.com`
   - **Role**: Handles REST API routes (`/v1`, `/v2`), Supabase Postgres / SQLite database repository, authentication, and data acquisition adapters (Open-Meteo, SoilGrids, GEE). Offloads all heavy ML model loading to dedicated microservices.
   - **RAM Optimization**: Build command simplified to `pip install -r requirements.txt` (removed build-time training scripts).

2. **`agro-mirai-cnn` (CNN Disease Detection ONNX Service)**:
   - **URL**: `https://agro-mirai-cnn.onrender.com`
   - **Role**: Located in `services/cnn-onnx`, serves MobileNetV2 ONNX predictions over HTTP using `onnxruntime` + `Pillow` + `numpy`.

3. **`agro-mirai-tabular` (Tabular ML Microservice)**:
   - **URL**: `https://agro-mirai-tabular.onrender.com`
   - **Role**: Located in `services/tabular-ml`, serves Scikit-Learn `RandomForestClassifier` models for Crop Recommendation and Irrigation Prediction (`POST /predict/crop` and `POST /predict/irrigation`).

---

## 3. Remote Client Delegation & Resilient Fallback

- **Remote Clients**: `RemoteCropModel` and `RemoteIrrigationModel` in [src/agro_mirai/models/remote_tabular_client.py](file:///c:/Projects/AGRO%20MIRAI/src/agro_mirai/models/remote_tabular_client.py).
- **HTTP Routing**: `DecisionEngine` and `app.py` delegate crop & irrigation inference over HTTP to `TABULAR_SERVICE_URL`.
- **Zero-Downtime Fallback**: If `TABULAR_SERVICE_URL` is unreachable or unset, the remote client silently degrades to local model/rule execution — preventing 500 errors.

---

## 4. 24/7 Zero-Cost Keep-Alive System

- **GitHub Actions Workflow**: [.github/workflows/keep_alive.yml](file:///c:/Projects/AGRO%20MIRAI/.github/workflows/keep_alive.yml)
- **Schedule**: `cron: '*/12 * * * *'` (Runs every 12 minutes on GitHub Actions).
- **Behavior**: Sends HTTP GET `/health` requests to all 3 Render URLs:
  - `https://agro-mirai.onrender.com/health`
  - `https://agro-mirai-cnn.onrender.com/health`
  - `https://agro-mirai-tabular.onrender.com/health`
- **Result**: Keeps all 3 Render instances permanently awake 24/7 with zero cold-start delays for mobile clients.

---

## 5. Verification & Test Suite

| Test Suite | File Path | Status |
|---|---|---|
| Tabular Microservice Unit Tests | `services/tabular-ml/tests/test_tabular_service.py` | 3 passed |
| Remote Client & Fallback Tests | `tests/models/test_remote_tabular_client.py` | 4 passed |
| Decision Engine Integration | `tests/models/test_decision_engine_integration.py` | 3 passed |
| API End-to-End Integration | `tests/api/test_integration.py` | 10 passed |
| Specification Integrity | `python tools/check_specs.py` | OK |
| State Tracking | `python tools/update_state.py` | OK |

---

## 6. Documented Decisions & Artifacts

- **ADR 0026**: [decisions/0026-three-microservices-render-split.md](file:///c:/Projects/AGRO%20MIRAI/decisions/0026-three-microservices-render-split.md)
- **ADR Index**: [decisions/0001-index.md](file:///c:/Projects/AGRO%20MIRAI/decisions/0001-index.md)
- **Architecture Spec**: [docs/architecture.md](file:///c:/Projects/AGRO%20MIRAI/docs/architecture.md)
- **Session Progress Log**: [PROGRESS.md](file:///c:/Projects/AGRO%20MIRAI/PROGRESS.md)
- **Repository Doctrine**: [CLAUDE.md](file:///c:/Projects/AGRO%20MIRAI/CLAUDE.md)
