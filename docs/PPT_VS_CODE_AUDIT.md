# PPT / docs vs. code: verification audit (Module 44)

Date: 2026-09-25. Sources audited: `AGRO_MIRAI2.1.pptx` (40 slides, Phase-1 review, dated 5/14/2026), `README.md`, `BACKEND.md`, `docs/architecture.md`, `docs/PROJECT_WALKTHROUGH.md`, `CLAUDE.md`, `specs/core/openapi.yaml`, `decisions/*.md`.

## How this was checked

- **Live API**: real requests to `https://agro-mirai.onrender.com` (main API) and `https://agro-mirai-cnn.onrender.com`. Logged in as the existing test farmer (`+919000000042`) via the real OTP flow; the OTP was read from the service logs with the Render CLI (that is how OTP delivery works today, see claim 47). I created one Bellary field (15.14, 76.92, black soil), called every advisory endpoint, then deleted the field (HTTP 204). Feedback row `7d7b3856...` was created against the test farmer and left in place.
- **Infra**: `render services` (Render CLI v2.24.0) and `render logs`. Env var values cannot be read via the CLI, so anything that depends on a secret being set is inferred from behavior and labelled as such.
- **Code**: file paths cited. **Numbers**: read from `docs/eval/*.json`. **Tests**: fresh runs today.
- **Not done**: no Expo Go / device session. Anything that only shows on the phone is marked "needs Ritesh on device".

Verdict key: **CW** = Confirmed working, **UNV** = Implemented but unverified live, **BRK** = Broken, **NI** = Not implemented, **STALE** = Claim is stale/inaccurate (doc/PPT differs from what the code deliberately does now).

## A. Claims from the PPT

| # | Claim (source) | Verdict | Evidence |
|---|---|---|---|
| 1 | Integrates satellite, weather, soil and field data (slides 2, 5, 7, 8, 15, 36) | CW, with a caveat | Live `GET /v2/fields/{id}/data-summary` returned NDVI 0.5136 from Sentinel-2 (`source: gee_live`, observed 2026-09-17), current weather `source: openweathermap` plus 7-day forecast `source: met_norway`, and a SoilGrids row. **Caveat:** the SoilGrids row had every value `null`; the model used typical values for the soil type instead (`soil_used.chemistry_source: "soil_type_fallback"`, ph 8.0, N 250). So "soil data" in practice meant the farmer-selected soil type, not a measured/SoilGrids value. |
| 2 | Crop recommendation from location, weather and soil (slides 6, 19, 28) | CW | Live `/recommendation` -> 200, `recommended_crop: "chickpea"`, confidence 0.872, `method: "ecocrop_rules"`, alternatives maize/cotton/mango, plain-language rationale. Code: `src/agro_mirai/models/crop_recommendation_model.py`, `ecocrop.py`. |
| 3 | Water availability and irrigation planning (slides 2, 6, 19, 30) | CW | Live `/irrigation` -> 200: urgency `high`, `recommended_depth_mm: 60`, `method: soil_water_balance`, `et0_method: penman_monteith`, 31 days of weather used. Code: `models/irrigation_prediction_model.py`, `soil_water_balance.py`. **Oddity to check:** `soil_water_used_pct: 143` (above 100%) with a 60 mm recommendation. May be intended (deficit beyond easily-available water) but a demo audience could question it. Not investigated further (out of scope). |
| 4 | Early risk / disease detection from environmental data (slides 2, 6, 30) | CW, with a caveat | Live `/disease-risk` -> 200: `risk_level: high`, `method: weather_rules`, score 0.57. **Caveat:** no crop-specific disease list for chickpea (`crop_specific: false`), so the output was "Generic fungal disease risk (environmental proxy)". Code: `models/disease_risk_scoring.py`, `disease_named_risks.py`. |
| 5 | Disease prediction from a leaf photo, MobileNet CNN (slides 16, 8) | CW on the pipeline; UNV on real leaves | Live `POST /v2/fields/{id}/disease-risk/image` with a synthetic drawn leaf -> 200, `source: "cnn"`, confidence 0.415, and the app correctly answered "Not sure. Best guess: ...; retake the photo". The CNN service rejects unauthenticated calls (`401 invalid service token`), so the main-to-CNN token is correctly matched. **No real leaf photo was available**, so real-photo behavior needs Ritesh's phone. |
| 6 | Multilingual, voice-enabled system (slides 2, 6, 8, 15, 32) | **BRK in production** (UI strings CW) | Live `GET /v2/advisories/{id}/audio?language=en/kn/te/hi` -> **503 `VOICE_UNAVAILABLE` for all four languages**; `POST /v2/translate` -> `{"translated": false}`. `render logs` show no Sarvam warnings and no VOICE_SERVICE_URL calls, and the 503 comes back in about 1.5 s, which is consistent with neither `SARVAM_API_KEY_*` nor `VOICE_SERVICE_URL` being set on the deployed service (cannot confirm; env values are not readable via CLI). Voice worked on 2026-09-21/22 (`POST /v2/voice/ask -> 200` with ~300 KB bodies in the logs), so this regressed. Code path: `api/voice_client.py::_speak` (Sarvam, then remote voice service, then None). UI text is translated in `mobile/src/i18n.ts` for en/kn/te/hi (blocks at lines 1388-1412 and beyond). |
| 7 | Cost-effective, minimal hardware (slides 2, 15) | CW | `render services`: `agro-mirai` and `agro-mirai-cnn` are both `plan: free`, Singapore. Keep-alive is a GitHub Action (`.github/workflows/keep_alive.yml`, every 12 min). |
| 8 | Real-time weather + historical data for decisions (slide 6, 29) | CW, with a limit | Live data-summary: current reading dated the moment of request, 31 days of history used in the irrigation call, NDVI history returned. **Limit:** `openapi.yaml` states there is no automatic periodic refresh; weather is pulled at field creation and on manual `POST /refresh-data`. "Real-time" is on-request, not streaming. |
| 9 | Season-wise cropping patterns from water availability (slides 6, 7, 31) | **NI** (as a season-wise plan) | Live recommendation has `"season": null`; the only season logic is a per-crop sowing-month check (`good_time_to_sow`, `sowing_month: 9`) in `crop_recommendation_model.py`. No Kharif/Rabi/Zaid plan or season-by-season pattern is produced, and `mobile/src/screens/HomeTab.tsx` has no season output. `annual_rain_mm` is used for fit. |
| 10 | Hyper-localized (slides 2, 7, 8) | CW | Data is fetched per field lat/long (weather, SoilGrids, GEE point NDVI). Live field at 15.14, 76.92 got local values. Regional check for Bellary in `models/regional_suitability.py`. |
| 11 | NDVI is used in the analysis (slide 8) | CW | NDVI feeds the disease score (`disease_risk_scoring.py`) and the "is the current crop struggling" check (`crop_recommendation_model.py:61-66`), and is shown in the app. It does not affect the crop ranking itself. |
| 12 | Out of scope: no hardware control, no financial services (slide 8) | CW | No pump/drone/IoT/market-price code in `src/`. |
| 13 | Module 1: User interaction: farmer inputs, multilingual voice output (slide 13) | UNV | Input side works live (fields, feedback `POST /v2/feedback` -> 201). Voice output is broken in prod (claim 6). App UX needs device. |
| 14 | Module 2: Data acquisition: weather, NDVI, soil, historical (slide 13) | CW | `src/agro_mirai/acquisition/{openweathermap,open_meteo,weather_fallbacks,soilgrids,earth_engine}.py`; live output above. |
| 15 | Module 3: Data processing: cleaning and feature extraction (slide 13) | CW | `src/agro_mirai/processing/feature_builder.py` (`FeatureVector`); exercised by every live call. |
| 16 | Module 4: AI/ML prediction: crop, irrigation, disease (slide 13) | CW, but "ML" is mostly rules now | Crop = EcoCrop rules, irrigation = FAO-56 water balance, weather disease = weighted rules, only the leaf scan is a trained model (CNN). See claims 20-24. |
| 17 | Module 5: Decision support: final recommendation and alerts (slide 13) | CW | Live `/advisories` -> 200: combined text, `severity: "high"` (`models/decision_engine.py`). |
| 18 | Improvement: single-source systems vs integrated data (slide 15) | CW | Same as claim 1. |
| 19 | Improvement: "provides explainable AI-based outputs" (slides 10, 15, 19) | CW | Live advisory body says "What mattered most: rain in the last 7 days is 42.5 mm; humidity ... 69.8%; ..." and crop/irrigation rationale sentences with numbers. `explanation_service.py` uses `method="rule_weight"`. It is rule explanation, not SHAP (claim 24). |
| 20 | Technique: Random Forest (slide 16) | STALE | Removed in Module 44 cleanup (`decisions/0029-remove-tabular-service-and-rf-models.md`). Live crop method is `ecocrop_rules`, irrigation is `soil_water_balance`. Old RF eval files remain in `docs/eval/` as history. |
| 21 | Technique: Gradient Boosting, Decision Tree (slide 16) | NI | No such model in `src/`, `tools/`, `services/` (searched). |
| 22 | Technique: Regression models, Linear / RF Regression (slide 16) | NI | None found. Irrigation depth is an ET0 x Kc physics formula, not a regression. |
| 23 | Technique: CNN such as MobileNet (slide 16) | CW | `services/cnn-onnx/`, `models/disease_cnn_mobilenetv2.onnx`, live `source: cnn`. Eval: `docs/eval/disease_cnn_eval.json` (38 classes, best val 99.24% on PlantVillage) and `disease_cnn_plantdoc_eval.json` (shipped fine-tune: PlantDoc test top-1 45.8%, top-3 76.7%; PlantVillage sample 98.7%). |
| 24 | Technique: Explainable AI, SHAP and feature importance (slide 16) | STALE / NI for SHAP | SHAP was removed with the RF models (ADR 0029; `explanation_service.py` header says "no SHAP any more"; not in `requirements.txt`). `Explanation.method` still lists the label `"shap_tree"` in `explanation.py:27`, but nothing produces it. Feature-contribution breakdown (`rule_weight`) is CW. |
| 25 | Technique: Data fusion, feature-level fusion and normalization (slide 16) | CW for fusion; UNV for "normalization" | Fusion: `FeatureVector` merges weather/soil/NDVI/field. No scaler/normalizer step exists in `src/` (the only "normalize" hits are the NDVI band formula and phone numbers). No trained model needs one any more. |
| 26 | Technique: Spatio-temporal, "location-based clustering" (slide 16) | NI | No clustering code anywhere. NDVI trend (`ndvi_trend`) and 7/14/30-day window features exist (seasonal trend analysis only in that limited sense). |
| 27 | Technique: Rule-based inference, alerts, thresholds (slide 16) | CW | `disease_risk_scoring.py`, `decision_engine.py` severity ladder, live `severity: high`. |
| 28 | Tools: TensorFlow (slide 18) | STALE | Project uses PyTorch for training and ONNX Runtime for serving (`services/cnn-onnx/`). TensorFlow is only mentioned in `tools/train_disease_cnn_plantdoc.py`. |
| 29 | Tools: Scikit-learn (slide 18) | STALE | Removed from `requirements.txt` (ADR 0029). |
| 30 | Tools: Pandas, NumPy (slide 18) | CW (NumPy) / STALE (Pandas) | NumPy is in `requirements.txt`; Pandas moved to dev only (ADR 0029). |
| 31 | Weather API: OpenWeatherMap (slide 18) | CW, but docs disagree | Live current weather `source: openweathermap`; forecast `source: met_norway`. `open_meteo.py` also exists and README/walkthrough say Open-Meteo. The PPT is right for the current reading; the README is right that other providers are used too. |
| 32 | Satellite: Google Earth Engine (slide 18) | CW | Live `source: gee_live`, `satellite: sentinel-2`. `earth_engine.py` has the cache fallback (not forced live). |
| 33 | Database: MySQL (slide 18) | STALE | No MySQL anywhere. Prod is Supabase Postgres, dev is SQLite (`persistence/`). The test farmer created 2026-09-24 still existed after several redeploys of a free service with a wiped disk, which fits Postgres; the env var itself is unreadable. |
| 34 | Backend: Flask (slides 18, 22) | CW | `agro_mirai.api.app:create_app`, gunicorn in `render.yaml`. |
| 35 | Frontend: HTML, CSS, JavaScript (slides 18, 22) | STALE | The farmer client is React Native + Expo (`mobile/`); there is also a server-rendered Jinja2 web UI and admin page. |
| 36 | Software requirement: SQLite / MySQL (slide 22) | Half true | SQLite yes; MySQL no (claim 33). |
| 37 | FR: accept field, soil, weather, location data (slide 19) | CW | `POST /v2/fields` -> 201 with lat/long/area/soil_type/crop/sown_on (`FieldCreate` in openapi). Weather and soil are fetched automatically, the farmer does not type them. |
| 38 | FR: alerts with explainable recommendations (slide 19) | CW | Live advisory `severity: high` with reasons (claim 19). |
| 39 | NFR: fast responses (slide 20) | CW on API, UNV on user experience | Health 0.5-0.8 s. The five advisory calls above each returned within a couple of seconds (server timestamps 16:36:09 to 16:36:14). Cold start not measured (keep-alive ping is on). |
| 40 | NFR: reliability / "degrades, never fails" (slide 20) | CW | Fresh test run: **540 passed, 33 skipped, 0 failed** (`pytest --ignore=tests/voice --ignore=tests/vision --ignore=services/cnn-inference --ignore=services/voice`); `services/cnn-onnx/tests`: 12 passed, 1 skipped; `tools/check_specs.py`: OK. Live: image scan and translate degrade rather than 500. |
| 41 | NFR: scalability (slide 20) | UNV | One gunicorn worker, 512 MB free tier, in-memory rate limiter (`requirements.txt` notes it is single-process only). Works for a demo, not load-tested. |
| 42 | "Basic offline capability" (slide 10, gap addressed) | UNV, needs Ritesh on device | `mobile/src/hooks.ts` paints cached data first and keeps it on failure; `mobile/src/api.ts:22` tracks online/offline; cache in `storage.ts`. Cannot confirm behavior without airplane-mode test on a phone. |
| 43 | Simple UI / farmer-friendly (slides 6, 10, 20, 32) | UNV, needs Ritesh on device | Cannot be judged from code. |
| 44 | Multilingual output actually shown in kn/te/hi (slide 32) | UNV (UI) / BRK (server text) | App labels are translated locally. Server-side advisory translation returned `translated:false` live (claim 6). Needs a device run to see what the farmer sees. |
| 45 | Applications: government programs, large scale (slide 33) | UNV | Read-only admin (`/admin`, `/v2/admin/*`) exists; live check as a normal farmer -> **403 "Admin role required"** and unauthenticated `/admin` -> 302. Admin content not viewed (no admin credentials used). Nothing tests large scale. |
| 46 | Future scope: robots/drones, Edge AI, Digital Twin, Blockchain (slide 34) | NI (correctly future) | No code. Note Edge AI "full offline" is beyond the "basic offline" in claim 42. |
| 47 | Work plan / Waterfall model (slides 17, 35) | STALE | The repo was built as 44 iterative modules with per-module ADRs, not waterfall phases. Process claim, not a defect. |
| 48 | Conclusion: real-time guidance, large-scale potential (slide 36) | UNV | See claims 8 and 41. |

## B. Claims from the repo docs

| # | Claim (source) | Verdict | Evidence |
|---|---|---|---|
| 49 | Three Render services incl. `agro-mirai-tabular` (`PROJECT_WALKTHROUGH.md` s.4, `CLAUDE.md` Module 41, `architecture.md` s.7) | STALE | `render services` lists only `agro-mirai` and `agro-mirai-cnn` for this project (plus unrelated services in the same account). `render.yaml` matches. `architecture.md` has a Module-44 update note, the walkthrough does not. |
| 50 | Crop = trained RandomForest, 99.55%, explained with SHAP (`README.md` lines 10, 31-32; `PROJECT_WALKTHROUGH.md`; `BACKEND.md`; `DEMO_SCRIPT.md`) | STALE | RF and SHAP removed (ADR 0029). The number is still what `docs/eval/crop_rf_eval.json` says (accuracy 0.99545, macro-F1 0.99545), but it describes a retired model. |
| 51 | Irrigation urgency = trained RF, 72.4% / macro-F1 0.58 (`PROJECT_WALKTHROUGH.md`) | STALE | `irrigation_rf_eval.json` still says 0.724 / 0.5796, but live method is `soil_water_balance`. |
| 52 | README quick-start: `python tools/train_crop_model.py && python tools/train_irrigation_model.py` | **BRK -> fixed** | Both scripts were deleted in ADR 0029 (`ls tools` shows only the disease-CNN training scripts). The step would fail for anyone following the README. **Fixed:** line removed from `README.md`. `BACKEND.md` section 5, `MANUAL_TEST_GUIDE.md` (installs scikit-learn/shap, step 09) and the `CLAUDE.md` Commands block still reference it (not changed; larger doc rewrite). |
| 53 | README: "disease risk (CNN on real photos ...)" | Partly stale | The CNN's shipped fine-tune reaches PlantDoc test top-1 45.8% (see claim 23), which is the closest available proxy for phone photos. "Real photos" overstates it. |
| 54 | Voice: en/kn/te/hi via IndicTrans2, Piper, AI4Bharat container (`README.md`) | STALE + BRK | Production voice code is Sarvam first, then the AI4Bharat container (`voice_client.py::_speak`). Prod returns 503 for all languages (claim 6). Docker-compose / Oracle VM path is not deployed. |
| 55 | CNN accuracy 99.24%, 38 classes (`PROJECT_WALKTHROUGH.md`, `CLAUDE.md`) | CW (number), misleading | Matches `disease_cnn_eval.json` (0.99239, 54,305 images, 38 classes) but that is the old PlantVillage-only model on in-distribution data; the file itself says so. |
| 56 | OpenAPI `/v2` endpoints exist as documented (`specs/core/openapi.yaml`) | CW for 13 of 25 | Live-tested: `request-otp` (400 on bad phone, 200 on valid), `verify-otp`, `farmers/me`, `fields` (GET/POST/DELETE), `data-summary`, `recommendation`, `irrigation`, `disease-risk`, `disease-risk/image`, `advisories`, `feedback` (400 without `helpful`, 201 with), `admin/farmers` (403 for farmer), `translate` (200, degraded), `advisories/{id}/audio` (503). **Not live-tested:** `logout`, `PATCH fields`, `refresh-data`, `stt`, `voice/ask`, `bug-reports`, `admin/fields|feedback|scans|advisories`, cross-tenant 404 (covered by the 540-test suite only). |
| 57 | `/v1` shared-key routes still alive (`CLAUDE.md`) | CW | Unauthenticated `GET /farmers/me` -> 401 "Missing bearer token" (v1 routes are unprefixed in the openapi file; `/v1/...` is 404). |
| 58 | Name + Phone + OTP auth, no SMS provider (`CLAUDE.md`, `decisions/0023`) | CW, and it is a launch blocker | Real flow completed: request-otp 200 -> OTP found in `render logs` (`auth.otp: OTP for +919000000042: ...`) -> verify-otp 200 with session cookie. **Any person with log access can log in as any farmer.** No SMS delivery exists (`auth/otp.py::send_otp` only logs). |
| 59 | Session isolation: unauthenticated requests rejected (`CLAUDE.md`) | CW | `GET /v2/fields` without cookie -> 401 UNAUTHORIZED. |
| 60 | CNN service protected by service token (`render.yaml`) | CW | Direct `POST /predict` -> 401 `invalid service token`; main API call with the token succeeded (claim 5). |
| 61 | GEE live with NDVI cache fallback (`CLAUDE.md` rule 4) | CW (live) / UNV (fallback) | Live path shown. Fallback exists in `earth_engine.py` and tests; not forced in prod. |
| 62 | Rate limiting: OTP 5/min, TTS 20/min, STT 10/min (`render.yaml`) | UNV live | Configured in `render.yaml` and unit-tested; not hit in prod (would have locked the test phone). |
| 63 | Mobile app in 4 languages with tour, notifications, etc. (`PROJECT_WALKTHROUGH.md` s.5) | UNV, needs Ritesh on device | Code present under `mobile/src`; I did not run Expo Go. |
| 64 | "Backend suite: 311 tests passing" (`PROJECT_WALKTHROUGH.md`) | STALE | Fresh run today: 540 passed, 33 skipped. |
| 65 | Keep-alive pings all 3 services every 12 minutes (`CLAUDE.md` Module 41) | STALE | `.github/workflows/keep_alive.yml` now pings 2 (main API, CNN). |

## C. Cheap fix made

- `README.md`: removed the quick-start line that runs the deleted `tools/train_crop_model.py` / `train_irrigation_model.py` (claim 52).

No code, config, model or PPT was changed. The test field created for this audit was deleted from production (204).

## D. Summary

Total claims checked: **65** (48 from the PPT, 17 from repo docs).

| Verdict (primary, one per claim) | Count | Claims |
|---|---|---|
| Confirmed working (some with a stated caveat) | 32 | 1-5, 7, 8, 10-12, 14-19, 23, 25, 27, 31, 32, 34, 37-40, 55, 57-61 |
| Implemented but unverified live | 9 | 13, 41, 42, 43, 45, 48, 56, 62, 63 |
| Broken | 3 | 6 (prod voice 503), 44 (server-side text translation), 52 (README quick-start, fixed) |
| Not implemented | 5 | 9 (season-wise plan), 21, 22, 26, 46 (future scope, expected) |
| Stale / inaccurate | 16 | 20, 24, 28, 29, 30, 33, 35, 36, 47, 49, 50, 51, 53, 54, 64, 65 |

Several rows carry a second verdict for one half of the claim (5, 25, 44, 56, 61); the table above uses the primary one. Row 5's "unverified" half is real-leaf accuracy.

**Needs Ritesh on a device:** voice playback and dictation in all four languages (after fixing the prod voice config), camera leaf scan on real leaves, offline behavior (airplane-mode), the language picker and translated UI, notifications, and overall usability.

## E. What matters most for a faculty demo or a real farmer

1. **Voice is down in production.** All four languages return 503 on advisory audio and translation returns untranslated text; the PPT sells voice and multilingual output as a headline feature. Most likely cause is that neither `SARVAM_API_KEY_*` nor `VOICE_SERVICE_URL` is set on the deployed `agro-mirai` service (or the Sarvam keys are exhausted). That is an env-var check in the Render dashboard, not a code change, so it was not touched here.
2. **The PPT's ML story no longer matches the product.** Random Forest, Gradient Boosting, Decision Tree, regression, SHAP, TensorFlow, scikit-learn and MySQL are named on slides 16 and 18, but crop and irrigation are rule/physics based (EcoCrop, FAO-56), the only trained model is the MobileNetV2 leaf CNN, explanations are rule-weight breakdowns, and the database is Supabase Postgres/SQLite. If the faculty ask "which model gives the crop recommendation", the honest answer is now "rules, by design" (ADR 0027/0029). "Location-based clustering" and "season-wise cropping patterns" are not built.
3. **Soil data is thinner than it sounds.** For the live Bellary field SoilGrids returned no values, so crop and irrigation used typical values for the chosen soil type; the response marks this (`soil_values_measured: false`) and the advisory text says "typical for your soil type, not measured".
4. **Leaf scan accuracy claim needs care.** 99.24% is on PlantVillage lab images; the shipped model scores 45.8% top-1 (76.7% top-3) on the PlantDoc phone-style test set. The app handles uncertainty well (it said "Not sure, retake the photo" on a fake leaf), but quoting 99% to a farmer or panel would be misleading.
5. **OTP login is not safe for real users** (the code is printed to server logs; there is no SMS), and several project docs (`PROJECT_WALKTHROUGH.md`, `BACKEND.md`, `MANUAL_TEST_GUIDE.md`, `DEMO_SCRIPT.md`, README table) still describe the retired RF/SHAP/tabular architecture and 311 tests, so they should be refreshed before they are handed to anyone.

Suggested follow-up modules (not started): (a) restore prod voice config and re-test all four languages on a phone, (b) refresh README/BACKEND/WALKTHROUGH/DEMO_SCRIPT/MANUAL_TEST_GUIDE and produce a corrected PPT slide 16/18 list, (c) SMS OTP provider, (d) check the `soil_water_used_pct: 143` irrigation output and the empty SoilGrids result for Bellary.

## F. Module 48 — full CLI-integrated production audit (2026-09-27)

Checked with each service's own CLI (`render`, `vercel`, `supabase`, `gh`), not dashboards, per `CLAUDE.md`'s CLI-first rule. All four CLIs were already authenticated in this environment (`render whoami` → B.Ritesh; `vercel whoami` → ritesh1918; `supabase projects list` → linked to `agro-mirai`/`yzsemdauwafxssaknlzr`, status `ACTIVE_HEALTHY`; `gh auth status` → riteshbonthalakoti).

**Backend (Render)** — `render services -o json` + `render deploys list <id>`:
- `agro-mirai` (`srv-dadapin10e5c73e3qhf0`) — live deploy is commit `5c327a6` (`save Ask AI conversations...`), the current `main` HEAD. `curl https://agro-mirai.onrender.com/health` → `{"status":"ok"}`.
- `agro-mirai-cnn` (`srv-daoosulg1s2s739363ug`) — live deploy also at `5c327a6`. `/health` → `{"status":"ok"}`.
- `agro-mirai-tabular` — confirmed genuinely gone, per Module 44's finding: not in `render services` output at all, and `curl https://agro-mirai-tabular.onrender.com/health` → 404 (dead Render subdomain, not a live-but-broken service). `RemoteCropModel`/`RemoteIrrigationModel` in `src/agro_mirai/models/remote_tabular_client.py` fall back to local rule-based models when `TABULAR_SERVICE_URL` is unset/unreachable — this was verified by code inspection (Module 44/decisions/0029), not re-tested live this module, since it isn't a new change.
- Render CLI (v2.24.0, this environment) has no `env`/`envgroups` subcommand, so env-var completeness against `.env.example` could not be checked via CLI; confirmed indirectly instead via live behavior: `/v2/stt` returns 401 (auth required, reached the app — not a boot-time crash from a missing required var) and OTP requests succeed end to end (below), which needs `SUPABASE_URL`/`SUPABASE_KEY`/`API_KEY`/session-secret to all be set correctly. Sarvam's kill switch (Module 47/`f39496e`, `SARVAM_DISABLED` default) is deployed and live.

**Landing page & admin dashboard (Vercel)** — `vercel projects list` + `vercel ls <project>` + `vercel inspect`:
- `agromirai` (landing, `web/landing`) — latest production deployment is 5 days old (`agromirai-flvfvcymb-...`, created 2026-09-22 13:53 IST). `git log -- web/landing` shows the last commit touching that directory is `ae63cb9` (2026-09-22 13:52 IST) and `git diff --stat ae63cb9 HEAD -- web/landing` is empty — the deployment is **not stale**, it exactly matches the last real change to that code.
- `agromirai-admin` (`web/admin`) — several production deployments in the last few hours (12m/27m/43m/4h old at audit time) with **no corresponding new commits** (`git diff --stat ae63cb9 HEAD -- web/admin` is also empty) — these were redundant re-deploys of unchanged code, not a staleness problem, but worth knowing before assuming a recent deploy means recent code changed.
- `BACKEND_HOST` (Module 38's follow-up concern): `web/admin/vercel.json` hardcodes three `rewrites` (`/admin/:path*`, `/v2/:path*`, `/health`) to `https://agro-mirai.onrender.com` — a static config value pointing at the real, permanent Render service, not an env var, not a tunnel, not a placeholder. `vercel env ls production` for `agromirai-admin` returned zero env vars, confirming there is no separate `BACKEND_HOST` env var to drift from what's in the repo.
- `web/admin` also already has read-only scans/advisories admin routes (commit `e92eacf`, "Admin: read-only scans and advisories routes, dashboard scan/advisory panels") — Module 38's follow-up gap ("Scans run: Not available") is **already closed**, before this module started; item 3 below doesn't need to reopen it.

**Database (Supabase)** — `supabase migration list --linked` against the linked `agro-mirai` project:
- 7 of 8 tracked migrations show matching `local`/`remote` timestamps. One real gap found: `20260921000900` (`009_bug_reports.sql`) shows `"remote":""` — the CLI's migration-history table thinks it was never applied. Direct check via `supabase inspect db table-stats --linked` shows `public.bug_reports` **does exist** in production with 3 real rows — the table was created out-of-band (a manual SQL run, most likely) rather than through a CLI-tracked `supabase db push`, so the migration ledger is out of sync with actual schema state even though the schema itself is correct and working. Documented here as a real, if low-severity, gap: a future `supabase db push` could be confused about what's pending, and a fresh clone of this migration history would not reproduce today's production schema by replaying migrations alone.
- The gap in migration numbering (003 → 005, no 004) is not a bug — it matches Module 26's Supabase-Auth-migration attempt-then-revert (`git revert dc97804`); 004 was that migration and was removed on revert.
- Production is genuinely on Supabase Postgres, not SQLite: `supabase projects list` shows `agro-mirai` (`yzsemdauwafxssaknlzr`) `status: ACTIVE_HEALTHY`, `linked: true`, and real row counts across `farmers`/`fields`/`crop_recommendations`/etc. confirm live traffic against it, not a placeholder.

**Auth** — live curl against production:
- Farmer OTP: `POST /v2/auth/request-otp` with a fresh phone number → `{"is_new_farmer":false,"otp_sent":true,"phone":"+919999999999"}`, HTTP 200. The OTP-to-server-logs-only, no-SMS-provider gap Module 44 already documented (audit section E.5 above) is still accurate — this module did not change or hide it.
- Admin login page: `GET /admin/login` → HTTP 200, reachable.
- Session-cookie flow itself (login → cookie → protected route → logout → cookie dead) was not re-run end-to-end this module beyond what Module 23's own integration tests already cover live in CI; no code in this path changed since Module 23/44.

**CI/CD** — `gh run list --branch main`:
- Latest 3 CI runs are all green (`success`), including the run against `5c327a6` (the exact commit both Render services are deployed from) and the one against `f39496e` (the Sarvam kill-switch commit). The `Render Keep-Alive Ping` cron (Module 41) also shows a recent green run in the same list — confirmed live, not just configured.

**Net finding for item 1**: nothing here is hand-wired, a tunnel, or a placeholder. The one real, novel gap this audit surfaced — the `009_bug_reports` migration-ledger/schema mismatch on Supabase — is worth a follow-up (`supabase migration repair --status applied 20260921000900` or equivalent) but does not affect current production behavior, since the table and its data are real. Render env-var completeness against `.env.example` could not be checked via CLI (no `render env` command in this CLI version) and was only checked indirectly via live behavior — flagged here rather than silently assumed complete.

## G. Module 48 — end-to-end production proof (2026-09-27)

Ran the full journey against production URLs only, no local server, using a disposable test farmer created and destroyed in this session:

1. `POST https://agro-mirai.onrender.com/v2/auth/request-otp` for a fresh phone number — `otp_sent: true`; the OTP itself was read from `render logs -r srv-dadapin10e5c73e3qhf0 --text "OTP"` (confirms the documented log-only, no-SMS behavior is still exactly what's live).
2. `POST /v2/auth/verify-otp` with that OTP — 200, real session cookie, new farmer row created in Supabase (`farmers` count 14→15, confirmed via `supabase inspect db table-stats --linked`).
3. `POST /v2/fields` (same session) — 201, a real field (`Module48 E2E Field`, cotton) written to Supabase (`fields` count 12→13).
4. Promoted that one test farmer to `role=admin` via `supabase db query --linked` (a throwaway bcrypt password, not touching any of Ritesh's real accounts), logged into `POST /admin/login` on production — 302 to `/admin`, real session.
5. `GET /v2/admin/overview` with that session — 200, and the response genuinely reflected the write from step 3: `total_farmers: 15`, `total_fields: 13`, `crop_distribution` included the new `cotton` field, confirming mobile-app-equivalent write → Render → Supabase → admin dashboard is a real, live path, not three independently-configured pieces that happen to look connected.
6. Cleaned up: `DELETE FROM farmers WHERE id=...` (cascades to the field) — confirmed back to 14 farmers / 12 fields afterward. No test data left in production.

This is the concrete proof the module brief asked for ("not a description of it"). The one piece not re-proven this way: Ritesh's own admin account login (no credential was available or requested in this session, per the security rules governing this environment) — the mechanism was proven end to end with a disposable admin instead, which exercises the identical code path.

## H. Module 49 — migration ledger fix + real admin credentials (2026-09-27)

**Migration ledger.** Re-checked section F's finding first, live, rather than trusting it: `supabase migration list --linked` still showed `20260921000900` (`009_bug_reports.sql`) as `"remote":""` — unapplied in the ledger — while `bug_reports` genuinely holds 3 rows in production (confirmed via the Supabase client, not just `table-stats`). Ran `supabase migration repair --status applied 20260921000900 --linked` (current CLI syntax, confirmed via `supabase migration repair --help` before running). Before/after:

- Before: 7/8 migrations matched; `20260921000900` had `remote: ""`.
- Command: `supabase migration repair --status applied 20260921000900 --linked`.
- After: `supabase migration list --linked` shows all 8 migrations with matching `local`/`remote` timestamps — a fully clean ledger. `bug_reports` re-queried afterward: still 3 rows, same ids/farmer_ids/timestamps as before the repair — a ledger-only fix, no schema or data touched.

**Real admin credentials.** Before provisioning anything new, checked what already existed: an admin-role farmer account already existed in production — `admin@agromirai.com`, name "Ritesh", created 2026-09-19 (predates Module 48's disposable-admin proof in section G, which was a separate account, created and deleted within that session). Asked Ritesh directly rather than assuming; he confirmed this is his account and asked for its password to be reset rather than a second admin account being created.

- Account: `admin@agromirai.com` (role `admin`, existing row, not newly created).
- Password: generated with `secrets.choice` (20 chars, mixed case/digits/symbols), hashed with bcrypt (cost 12, matching `src/agro_mirai/auth/password.py`'s scheme), written directly via the Supabase client to that farmer row's `password_hash`.
- Delivery: written to `admin_credentials.local.txt` in the project root (gitignored — `*.local.txt` added to `.gitignore` alongside the existing `.env`/`*credentials*.json` exclusions) rather than printed in this session's output. Ritesh reads it directly from his own checkout.
- Live login confirmed: `POST https://agro-mirai.onrender.com/admin/login` with the new password → 302 to `/admin` with a real session cookie. Followed through to `GET /admin` in the browser pane (not just curl) — real data rendered: 14 farmers, 12 fields, 22 scans, the crop/language breakdown, and the Module 48 recent-activity feed (scans/advisories with real timestamps and farmers, most recent from 2026-09-27T17:02). Screenshot taken confirming this — closes the one gap Module 48 explicitly left open ("no real admin-account screenshot was taken").

Known limitation carried forward: no second admin account was provisioned for any other team member — noted as an open item per the module brief, not actioned.
