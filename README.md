# AGRO MIRAI

AI-driven smart agriculture advisory system — a VTU Semester 7 capstone
project, Dept. of AIML, BITM. Solo-built by Ritesh.

Given a farmer's field (location, soil, sown crop) AGRO MIRAI pulls
real weather, soil, and satellite-NDVI data and turns it into three
concrete recommendations — **what to plant**, **when/how much to
irrigate**, and **disease risk** — each backed by a human-readable
explanation (SHAP for the trained models, weighted-factor breakdown for
the rule-based one), unified into a single advisory, translatable to
Kannada, with a feedback loop farmers can rate.

## What's actually in here

| Layer | What it does | Where |
|---|---|---|
| Data acquisition | Live weather (Open-Meteo), soil (SoilGrids), satellite NDVI (Google Earth Engine) with a local-cache fallback when GEE is unreachable | `src/agro_mirai/acquisition/` |
| Storage | A `DataStore` repository interface — SQLite in dev, Supabase Postgres in prod, same code either way | `src/agro_mirai/persistence/` |
| Feature engineering | Weather rolling aggregates, soil pass-through, NDVI trend, season — one pure function from raw records to a `FeatureVector` | `src/agro_mirai/processing/` |
| Models | Crop recommendation (RandomForest, 99.55% held-out accuracy), irrigation urgency (RandomForest), disease risk (documented weighted-scoring MVP, not a trained classifier — see `decisions/0009-disease-risk-model.md`) | `src/agro_mirai/models/` |
| Explainability | SHAP for the two trained models, exact weight×signal breakdown for the rule-based one, translated to Kannada when the voice service is wired in | `src/agro_mirai/models/explanation_service.py` |
| Decision engine | Orchestrates all three models + explanations into one `Advisory` with a severity level | `src/agro_mirai/models/decision_engine.py` |
| API | Flask, one shared bearer `API_KEY`, matches `specs/core/openapi.yaml` exactly | `src/agro_mirai/api/` |
| Voice & language | Real Kannada↔English translation (IndicTrans2), speech-to-text, text-to-speech (Piper / AI4Bharat) — needs a separate pinned environment, see below | `src/agro_mirai/voice/` |
| Feedback loop | Farmers rate advisories; aggregated into a report | `src/agro_mirai/feedback/`, `tools/feedback_report.py` |
| Web frontend | Server-rendered dashboard + field detail + feedback form, same Flask process as the API | `src/agro_mirai/api/templates/`, `.../static/`, `.../routes/frontend.py` |

## Project structure and how it was built

This project was built **module by module**, in strict dependency
order (module N+1 never started before module N was tested and
committed — see `CLAUDE.md`'s hard rules). Each module has:

- A written prompt (`module-NN-*.md` at repo root — session prompts,
  not shipped code, intentionally untracked).
- A `modules/NN-<name>/STATUS` file (`done`/`in-progress`/`not-started`).
- One or more ADRs under `decisions/` for any non-obvious call made
  along the way (`decisions/0001-index.md` is the index).
- Its own tests under `tests/`.

`PROGRESS.md` is the authoritative, currently-accurate module-by-module
log — read that for what each module actually did and how it was
verified, not just this file's summary table. `docs/architecture.md`
has the system diagram and the "why" behind cross-cutting choices
(repository interface, GEE-cache fallback, the two-Python-environment
split for voice). `specs/core/` holds the data contracts everything
else is built against (`schema.yaml`, `enums.md`, `openapi.yaml`,
`repository-interface.md`) — additive-only once published.

## Running it locally

Full step-by-step instructions (two terminal windows, seeding data,
exercising every module through the browser and the API directly) are
in **[`MANUAL_TEST_GUIDE.md`](MANUAL_TEST_GUIDE.md)** — that document is
the actual "how do I run this" reference; this README won't duplicate
it. Short version:

```bash
pip install -r requirements.txt        # API + web frontend
cp .env.example .env                   # fill in API_KEY, FARMER_ID
python tools/seed_fixture.py --backend sqlite --db-path agro_mirai_demo.db
python -m flask --app agro_mirai.api.app:create_app run
```

Then open `http://127.0.0.1:5000/`. The voice stack (`tests/voice/`,
Module 12) needs its own pinned environment — see `.venv/` setup and
`MANUAL_TEST_GUIDE.md` §7.

## Deployment

Live at Render (free tier) against a real Supabase Postgres backend —
see `docs/DEMO_DAY.md` for the URL, the ~1-minute cold-start reality,
and the "wake it up before your review" reminder. Voice inference is
**not** part of the hosted instance (documented, deliberate scope
decision — `decisions/0014-deploy-target-and-voice-scope.md`); it's
demoed from the developer's own machine.

## Tests

```bash
python -m pytest --ignore=tests/voice --ignore=tests/vision --ignore=tests/e2e -q   # everything except voice, vision + the deployed-instance smoke test
python tools/check_specs.py                                    # contract/fixture validation
.venv/Scripts/python.exe -m pytest tests/voice -q               # voice stack, needs the pinned .venv
```

`tests/e2e/test_deployed_smoke.py` hits the real deployed URL and is
skipped unless `AGRO_MIRAI_DEPLOYED_URL` / `AGRO_MIRAI_DEPLOYED_API_KEY`
are set — see that file's docstring.

## For an evaluator skimming the repo

- `CLAUDE.md` — the project's hard rules and doctrine (CLI-first,
  additive contracts, repository interface, GEE-with-cache-fallback,
  strict module gating).
- `PROGRESS.md` — module-by-module log, what's done, current phase.
- `decisions/` — every non-obvious engineering call, with reasoning,
  numbered chronologically.
- `docs/DEMO_SCRIPT.md` — the literal 10-minute walkthrough used for
  the live review.
