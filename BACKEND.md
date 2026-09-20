# AGRO MIRAI — Backend guide

For a faculty reviewer, a teammate taking over the code, or whoever is
demoing it live. Plain language first, commands second.

## 1. What the backend does

A farmer registers a field (location, soil, sown crop). The backend then:

1. **Fetches real data** for that location — weather, soil chemistry,
   satellite vegetation health (NDVI).
2. **Turns it into features** — e.g. "average temperature, last 14 days".
3. **Runs three models**:
   - **Crop recommendation** — *what should grow here?*
   - **Irrigation** — *how much water, and how urgently?*
   - **Disease risk** — *how likely is a fungal outbreak?* (also: a leaf
     photo can be classified by a CNN)
4. **Explains every answer** in plain language (which inputs mattered
   most), then bundles the three into one **Advisory** with a severity
   level.
5. **Serves it over an HTTP API** (with English / Kannada / Telugu / Hindi
   text, and spoken audio) to the mobile app, web pages and the admin
   dashboard, and records farmer **feedback** on each advisory.

## 2. Architecture

```
 DATA ACQUISITION            PROCESSING          ML MODELS               DECISION + EXPLANATION            API
 src/agro_mirai/acquisition  .../processing      .../models              .../models                        .../api

 Open-Meteo (weather)  ─┐                        crop_recommendation ─┐
 OpenWeatherMap (fallback)                       (RandomForest)        │   ExplanationService
 SoilGrids (soil)      ─┼─► FeatureBuilder ─►   irrigation           ─┼─► (SHAP for trained models,  ─►  DecisionEngine ─► Flask routes
 Earth Engine NDVI     ─┘   → FeatureVector       (ET0 water balance   │    exact weight breakdown        → one Advisory     (/v1, /v2, /admin)
   (local cache if GEE      (specs/core/           + urgency RF)       │    for the rule-based one)
    is unreachable)          features.md)        disease risk        ─┘
                                                 (rule-based + CNN)
                                     ▲
                    DataStore (persistence/) — SQLite in dev, Supabase Postgres in prod, same interface
```

| Stage | What it is | Code |
|---|---|---|
| Acquisition | One adapter per source, all returning the same record types. Earth Engine degrades to a local NDVI cache instead of failing. | `src/agro_mirai/acquisition/` |
| Processing | `FeatureBuilder` — a pure function from raw readings to a `FeatureVector`; missing data yields "unavailable", never a made-up number. | `src/agro_mirai/processing/feature_builder.py` |
| Models | The three models plus their wrappers (see §4). | `src/agro_mirai/models/` |
| Decision + explanation | `DecisionEngine` calls all three models and `ExplanationService` and returns one `Advisory`. | `models/decision_engine.py`, `models/explanation_service.py` |
| Persistence | A repository interface; nothing else talks to a database directly. | `src/agro_mirai/persistence/` |
| API | Flask app factory `create_app()`, blueprints under `api/routes/`. | `src/agro_mirai/api/` |
| Voice | Translate / speech-to-text / text-to-speech, run as a **separate container** (`services/voice/`) and called over HTTP. | `src/agro_mirai/voice/` |
| Auth | `/v2`: name + phone + one-time code (no password). `/admin`: email + password. | `src/agro_mirai/auth/`, `api/session_auth.py` |

Design rules that explain "why is it built like this" are in
[`CLAUDE.md`](CLAUDE.md) (hard rules) and [`docs/architecture.md`](docs/architecture.md).
Every non-obvious decision has a numbered write-up in
[`decisions/`](decisions/0001-index.md).

## 3. The API

The full, authoritative list of endpoints, request/response shapes and
error formats is **[`specs/core/openapi.yaml`](specs/core/openapi.yaml)** —
it is not repeated here on purpose. Shape in one paragraph:

- `/health` — liveness check.
- `/v2/...` — the real, per-farmer API used by the mobile app: OTP login,
  fields, per-field recommendation / irrigation / disease-risk /
  advisories, leaf-photo disease scan, feedback, advisory audio, voice
  question.
- `/v1/...`-style routes (`/farmers/me`, `/fields/{id}/...`) — the older
  single-key API, kept for demo continuity (`decisions/0017-multi-tenant-v2.md`).
- `/v2/admin/...` and the `/admin` page — read-only admin view.
- The data types those endpoints exchange are defined in
  [`specs/core/schema.yaml`](specs/core/schema.yaml).

## 4. The three models — where each came from

| Model | What it is | Training / fitting code | Recorded results | Why it's built this way |
|---|---|---|---|---|
| **Crop recommendation** | RandomForest over soil N/P/K/pH + temperature, humidity, rainfall → 22 crops. Plus a regional sanity check for Bellary. | **`tools/train_crop_model.py`** (Kaggle *crop-recommendation-dataset*, seed 42) → `models/crop_rf.joblib`. Inference: `models/crop_recommendation_model.py`. | `docs/eval/crop_rf_eval.json` — accuracy 0.9955 | `decisions/0007`, `0016` |
| **Irrigation** | **Not a single trained model.** Depth (mm) = crop water demand from the FAO-56 Hargreaves-Samani ET0 formula × crop coefficient, minus rainfall. *Urgency* (low/moderate/high) comes from a trained RandomForest. | Classifier: **`tools/train_irrigation_model.py`** (Kaggle *irrigation-water-requirement-prediction-dataset*, seed 42) → `models/irrigation_rf.joblib`. Water-balance formulas (no training — they're agronomy equations): `models/evapotranspiration.py`, `models/crop_coefficients.py`, `models/irrigation_prediction_model.py`. | `docs/eval/irrigation_rf_eval.json` — accuracy 0.724 | `decisions/0008`, `0015` |
| **Disease risk** | (a) **Rule-based** weighted score over humidity, rainfall, temperature and NDVI trend — this is what runs by default. (b) **CNN** (MobileNetV2, PlantVillage, 38 classes) when a leaf photo is uploaded. | (a) **No training** — it is a documented formula, no labelled dataset exists for it: `models/disease_risk_scoring.py`. (b) **`tools/train_disease_cnn.py`** (run on a Colab GPU) → `models/disease_cnn_mobilenetv2.pt`; served by `services/cnn-inference/`. | (b) `docs/eval/disease_cnn_eval.json` — val. accuracy 0.9924 (lab-condition images; expect lower on real field photos) | `decisions/0009`, `0018` |

Two honest points a reviewer may ask about:

- The trained files under `models/` are **git-ignored** (they are large and
  reproducible). Section 5 rebuilds the two RandomForests in a minute or so;
  the CNN weights are not needed to run the backend (photo scans fall back
  to the rule-based path when the CNN service is absent).
- The same three models are demonstrated step by step, with real outputs,
  in `notebooks/01_crop_recommendation.ipynb`, `02_irrigation_advisory.ipynb`
  and `03_disease_risk_detection.ipynb` (open in Google Colab → *Runtime →
  Run all*; notebooks 1 and 2 need a free Kaggle `kaggle.json`, explained
  at the top of each).

## 5. Run it locally (tested from a fresh clone)

Needs **Python 3.12** (the version the pinned dependencies were tested
on) and Git. Nothing else — no API keys are required for the core demo.

```bash
git clone <repo-url> agro-mirai
cd agro-mirai
python -m venv .venv
```

Activate the environment — Windows PowerShell: `.venv\Scripts\Activate.ps1`;
macOS/Linux/Git-Bash: `source .venv/bin/activate` (Git-Bash on Windows:
`source .venv/Scripts/activate`). Then:

```bash
pip install -r requirements.txt

# 1. Build the two trained model files (git-ignored, so a fresh clone has none).
python tools/train_crop_model.py
python tools/train_irrigation_model.py

# 2. Configure. The template already points at the demo farmer and a local
#    SQLite file; open .env and replace API_KEY's placeholder with any string.
cp .env.example .env

# 3. Load the demo farmer + field into that SQLite file (agro_mirai.db).
python tools/seed_fixture.py --backend sqlite --db-path agro_mirai.db
```

Start the server (the `src` folder must be on the Python path):

```bash
# macOS / Linux / Git-Bash
PYTHONPATH=src python -m flask --app agro_mirai.api.app:create_app run
```
```powershell
# Windows PowerShell
$env:PYTHONPATH = "src"; python -m flask --app agro_mirai.api.app:create_app run
```

Check it (a second terminal). The demo field id is
`22222222-2222-4222-8222-222222222222`; use the `API_KEY` you set:

```bash
curl http://127.0.0.1:5000/health
curl -H "Authorization: Bearer <API_KEY>" http://127.0.0.1:5000/fields/22222222-2222-4222-8222-222222222222/recommendation
curl -H "Authorization: Bearer <API_KEY>" http://127.0.0.1:5000/fields/22222222-2222-4222-8222-222222222222/irrigation
```

Each of the last two runs the real trained model on the seeded field and
returns JSON (a crop with confidence, and an irrigation depth with a
rationale showing ET0 / crop demand / rainfall). Opening
`http://127.0.0.1:5000/` in a browser shows the web dashboard for the
same farmer.

**Optional:** Supabase (production database), Earth Engine (live NDVI),
OpenWeatherMap, Gemini, and the CNN/voice services are all optional —
`.env.example` says what each one is, where to get the key, and what
degrades if it's absent.

### Tests

```bash
pip install -r requirements-dev.txt
PYTHONPATH=src python -m pytest --ignore=tests/voice --ignore=tests/vision --ignore=tests/e2e \
    --ignore=services/cnn-inference --ignore=services/voice -q
python tools/check_specs.py                  # validates fixtures against the contracts
(cd services/cnn-inference && PYTHONPATH=../../src python -m pytest tests -q)
(cd services/voice && PYTHONPATH=../../src python -m pytest tests -q)
```

(The two `services/` suites are run from their own folders because both
services have a module called `app`.) `tests/voice` and `tests/vision`
need the heavy AI stacks (torch etc.) and run separately — see `docs/TOOLING.md`.

## 6. Hosted on Render (partial backend)

The Flask API is deployed on Render's free tier at `https://agro-mirai.onrender.com`,
using Supabase as the store. The admin dashboard (`web/admin`, on Vercel at
`https://agromirai-admin.vercel.app`) forwards `/admin/*`, `/v2/*` and `/health` to it
through the rewrites in `web/admin/vercel.json`, so it works with the laptop off.

What Render covers today:

- The API and `/v2/admin/*`, `/admin` login, farmers, fields, feedback.
- Crop, irrigation and rule-based disease-risk advisories (`/v2/fields/{id}/advisories`).
  Checked live; one gunicorn worker only, because two workers were OOM-killed at the free
  tier's 512 MB.

What Render does not cover:

- **Voice** (translate, speech-to-text, text-to-speech): the AI4Bharat stack does not fit in
  512 MB. `/v2/advisories/{id}/audio` returns 503 `VOICE_UNAVAILABLE`, and the mobile app
  falls back to on-device TTS.
- **CNN disease image path**: no CNN service is configured, so image upload returns the
  rule-based result with `source: environmental_fallback`.
- Full model functionality still needs the laptop (or the Oracle VM from Module 21) running
  the voice and CNN services, with `VOICE_SERVICE_URL` / `CNN_SERVICE_URL` pointing at it.

Free-tier behaviour: the service spins down after about 15 minutes idle and the next
request waits for a cold start. Secrets (`SUPABASE_*`, `FLASK_SECRET_KEY`, `API_KEY`,
`FARMER_ID`, `OPENWEATHER_API_KEY`, the Earth Engine key as a secret file) are set in
Render's env config, never in the repo.

## 7. Where to look next

| Question | File |
|---|---|
| How was this built, module by module? | [`PROGRESS.md`](PROGRESS.md) |
| Why was X decided? | [`decisions/`](decisions/0001-index.md) |
| What are the data contracts? | [`specs/core/`](specs/core/) |
| Live-demo script | [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md), [`docs/DEMO_DAY.md`](docs/DEMO_DAY.md) |
| Deploying (Render + Supabase, Oracle VM for CNN/voice) | `render.yaml`, [`docs/deploy/oracle-vm-setup.md`](docs/deploy/oracle-vm-setup.md), [`decisions/0019-deployment-architecture.md`](decisions/0019-deployment-architecture.md) |
| Manual click-through of every feature | [`MANUAL_TEST_GUIDE.md`](MANUAL_TEST_GUIDE.md) |
