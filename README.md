# AGRO MIRAI

AI-driven smart agriculture advisory system — a VTU Semester 7 capstone
project, Dept. of AIML, BITM. Solo-built by Ritesh.

Give it a farmer's field (location, soil, sown crop) and it pulls real
weather, soil, and satellite-NDVI data and turns that into three
concrete recommendations — **what to plant**, **when/how much to
irrigate**, and **disease risk** — each with a human-readable
explanation (SHAP for the trained models, a weighted-factor breakdown
for the rule-based one), unified into a single advisory, voiced in
English/Kannada/Telugu/Hindi, with a farmer feedback loop.

## What's in the repo

```
src/agro_mirai/    Flask API + ML models + voice + decision engine (the backend)
mobile/            React Native + Expo app (the farmer-facing client)
services/          Standalone CNN-inference and voice containers (heavy ML, isolated)
specs/core/        The data contracts everything else is built against
decisions/         One ADR per non-obvious engineering call, numbered
docs/              Architecture, deploy runbooks, demo script
tests/             Backend test suite (mirrors src/ layout)
tools/             Seeding, training, backup, and spec-check scripts
```

| Layer | What it does | Where |
|---|---|---|
| Data acquisition | Live weather (Open-Meteo), soil (SoilGrids), satellite NDVI (Google Earth Engine) with a local-cache fallback when GEE is unreachable | `src/agro_mirai/acquisition/` |
| Storage | A `DataStore` repository interface — SQLite in dev, Supabase Postgres in prod, same code either way | `src/agro_mirai/persistence/` |
| Models | Crop recommendation (RandomForest, 99.55% held-out accuracy), irrigation (ET0 water-balance + urgency classifier), disease risk (CNN on real photos, with a documented rule-based fallback) | `src/agro_mirai/models/` |
| Explainability | SHAP for the trained models, exact weight×signal breakdown for the rule-based one | `src/agro_mirai/models/explanation_service.py` |
| Decision engine | Orchestrates all three models + explanations into one `Advisory` with a severity level | `src/agro_mirai/models/decision_engine.py` |
| API | Flask. `/v1` — one shared bearer key (legacy/demo). `/v2` — real per-farmer session auth, Name+Phone+OTP, no password or email required. Matches `specs/core/openapi.yaml` exactly | `src/agro_mirai/api/` |
| Voice & language | Translation, speech-to-text, text-to-speech for en/kn/te/hi (IndicTrans2, Piper, AI4Bharat) — containerized, called over HTTP, never imported into the main API process | `src/agro_mirai/voice/`, `services/voice/` |
| Mobile app | The farmer-facing client: OTP login, home dashboard, camera-based leaf disease scan, advisory feed with voice playback, scan history | `mobile/` |
| Admin dashboard | Read-only, session-authenticated, server-rendered | `src/agro_mirai/api/routes/admin*.py` |

## Quick start — backend

```bash
pip install -r requirements.txt
cp .env.example .env                   # fill in API_KEY, FARMER_ID
python tools/seed_fixture.py --backend sqlite --db-path agro_mirai_demo.db
python -m flask --app agro_mirai.api.app:create_app run
```

Open `http://127.0.0.1:5000/`. Full step-by-step instructions (seeding,
exercising every module via the browser and the API directly) are in
**[`MANUAL_TEST_GUIDE.md`](MANUAL_TEST_GUIDE.md)**.

The voice stack needs its own pinned Python environment (`.venv/`,
`transformers==4.49.0`) separate from the main interpreter — see
`MANUAL_TEST_GUIDE.md` §7. In production it runs as its own container
(`services/voice/`); the main API never imports it directly.

## Quick start — mobile app

```bash
cd mobile
npm install
npx expo run:android      # builds + installs a real dev client on a USB-connected device
# or: npx expo start      # Expo Go, for quick iteration without a native build
```

`mobile/src/config.ts` picks up the backend URL automatically from
Metro's `hostUri` in dev — no manual IP editing needed on the same
network. Requires a running backend (see above) to log in and pull
real data.

## Tests

```bash
python -m pytest --ignore=tests/voice --ignore=tests/vision --ignore=tests/e2e -q
python tools/check_specs.py                          # contract/fixture validation
.venv/Scripts/python.exe -m pytest tests/voice -q     # voice stack, needs the pinned .venv
```

`tests/e2e/test_deployed_smoke.py` hits the real deployed URL and is
skipped unless `AGRO_MIRAI_DEPLOYED_URL` / `AGRO_MIRAI_DEPLOYED_API_KEY`
are set.

## Deployment

Backend is live on Render (free tier) against a real Supabase Postgres
instance — see `docs/DEMO_DAY.md` for the URL and cold-start notes.
CNN and voice inference run as separate containers, deployed
independently (`docs/deploy/oracle-vm-setup.md`) — the core API works
even if those are down (`decisions/0019-deployment-architecture.md`).

## How this was built

Built module by module in strict dependency order — module N+1 never
started before module N was tested and committed (`CLAUDE.md`'s hard
rules). For each module: a `modules/NN-<name>/STATUS` file, one or more
ADRs under `decisions/` for any non-obvious call, and its own tests.

- **`PROGRESS.md`** — the authoritative module-by-module log: what each
  module actually did and how it was verified. Read this first.
- **`decisions/`** — every non-obvious engineering call, numbered,
  with reasoning (`decisions/0001-index.md` is the index).
- **`docs/architecture.md`** — the system diagram and the "why" behind
  cross-cutting choices (repository interface, GEE-cache fallback, the
  voice environment split).
- **`specs/core/`** — the data contracts (`schema.yaml`, `enums.md`,
  `openapi.yaml`, `repository-interface.md`) — additive-only once
  published.
- **`CLAUDE.md`** — the project's hard rules and current phase.
- **`docs/DEMO_SCRIPT.md`** — the literal walkthrough used for the live
  review.
