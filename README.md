# AGRO MIRAI

AI-driven smart agriculture advisory system for Indian farms — crop recommendation, ET0-based irrigation advisory, and disease risk detection, with voice support in English, Kannada, Telugu, and Hindi.

**Live:** [agromirai.vercel.app](https://agromirai.vercel.app)

## What it does

Every recommendation is generated from a farmer's own field data — soil samples, local weather, and satellite NDVI — not a generic lookup table.

- **Crop recommendation** — ranks 22 crop types against FAO EcoCrop's temperature/soil-pH/soil-texture ranges plus the field's real 12-month rainfall, with a regional-suitability check against ICAR/state agriculture data.
- **Irrigation advisory** — a daily FAO-56 root-zone water balance (Hargreaves-Samani reference evapotranspiration, crop coefficient by growth stage, root depth, soil water-holding capacity).
- **Disease risk detection** — a MobileNetV2 CNN (PlantVillage-trained) reads an uploaded leaf photo; a weighted rule-based score over humidity/rainfall/temperature/NDVI trend fills in when no photo is available or the CNN call fails.
- **Voice, in four languages** — every advisory translates and speaks back in English, Kannada, Telugu, and Hindi (IndicTrans2 + AI4Bharat ASR/TTS, Piper for English/Hindi). Farmer login is name + phone + OTP, no password.

## Architecture

```
acquisition/ (weather, SoilGrids, GEE NDVI w/ cache fallback)
  -> persistence/ (DataStore: SQLiteDataStore | SupabaseDataStore)
  -> processing/feature_builder.py (FeatureVector)
  -> models/ (crop rules, irrigation ET0 water balance, disease CNN/rules)
  -> ExplanationService
  -> DecisionEngine.recommend (Advisory)
  -> api/ (Flask, create_app() factory)
```

- **API surfaces**: `/v1` (shared API-key auth, frozen for back-compat) and `/v2` (session-cookie auth — Name+Phone+OTP for farmers, email+password for admins, per-farmer tenant isolation). Both call the same handlers in `api/value_endpoints.py`.
- **Degrade, never fail**: every external dependency has a fallback — GEE → local NDVI cache, CNN service → rule-based disease model, voice service down → 503, missing data → 422, never a 500.
- **Repository pattern**: no module talks to a database engine directly; a `DataStore` abstraction runs SQLite in dev and Supabase Postgres in prod against the same code.
- **Contracts**: `specs/core/enums.md` is the additive-only, CI-enforced source of truth for enum values (`tools/check_specs.py` gates every CI run on it).

## Repo layout

```
src/agro_mirai/       Flask API, models, persistence, acquisition, voice
tests/                pytest suite (mirrors src/ layout)
mobile/               React Native / Expo app (farmer-facing)
web/                  landing page + admin dashboard (server-rendered/vanilla JS)
services/             standalone inference services (CNN ONNX, voice) for separate deployment
migrations/           SQLite + Postgres schema migrations
specs/core/            enums.md — the CI-enforced contract
tools/                 CLI utilities (seeding, spec validation, training scripts)
supabase/              Supabase-specific config
data/                  small committed reference datasets
```

## Running it locally

```bash
pip install -r requirements-dev.txt
python tools/seed_fixture.py --backend sqlite --db-path agro_mirai.db
PYTHONPATH=src python -m flask --app agro_mirai.api.app:create_app run
```

Run the test suite (excludes the voice/vision/service subpackages, which need their own environments):

```bash
PYTHONPATH=src pytest --ignore=tests/voice --ignore=tests/vision --ignore=services/cnn-inference --ignore=services/voice
```

Validate the CI-gated specs contract:

```bash
python tools/check_specs.py
```

Mobile app (Expo SDK 57):

```bash
cd mobile && npx expo run:android
```

## Deployment

- **API** — Render (`render.yaml`), Flask via gunicorn.
- **Landing page + admin dashboard** — Vercel, auto-deployed on push to `main`.
- **CNN / voice inference** — separate containerized services (`services/`), deployable independently (torch/AI4Bharat dependencies are kept out of the main API's requirements).
- **Mobile OTA updates** — EAS Update, `staging` and `production` channels.

## License

Built for Indian farms as a capstone project.
