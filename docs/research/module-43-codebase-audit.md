# Module 43 - Codebase Audit

Date: 2026-09-24. Read-only audit. Files being edited by another engineer (irrigation/crop models, value_endpoints.py, serializers.py, mobile HomeTab) were read for design only. Model and farmer-UX research already exist in `docs/research/module-43-model-research.md` and `module-43-farmer-ux-research.md`; not repeated here.

Line numbers marked `~` were read from a file view without line numbering, so they are approximate (within a few lines).

---

## 1. How the app works today

### 1.1 End-to-end walkthrough

1. **Register / login (OTP).** Mobile `Onboarding.tsx` calls `POST /v2/auth/request-otp` (`api/routes/auth_v2.py`). The route normalizes the phone to +91 form, find-or-creates the `Farmer` by phone (this happens BEFORE the OTP is verified), issues a 6-digit code in a process-local dict (`auth/otp.py`, TTL 10 min, 5 attempts) and "sends" it with `logger.info` (`otp.py` `send_otp`, ~line 95). `POST /v2/auth/verify-otp` checks the code and calls `issue_session` (`api/session_auth.py`): a Flask signed cookie holding farmer_id, role, issued_at, valid 24h. RN's native networking stores the cookie. Admin login is separate: email+bcrypt password form at `/admin/login` (`routes/admin_ui.py`).
2. **Create field.** `POST /v2/fields` (`routes/farms_v2.py`) validates, saves a `Field_`, then `acquire_field_data` (`api/field_data_acquisition.py`) starts weather and soil threads (join 20s / 5s), a background NDVI thread (GEE, cache fallback) and a background annual-rain warm-up. Weather goes Open-Meteo (30 days history + forecast), then on failure OpenWeatherMap + NASA POWER history + MET Norway forecast. Soil is SoilGrids with typical values for the soil type filling P/K/moisture gaps. The response reports `weather/soil/ndvi` as ready, unavailable or gathering.
3. **Advisories.** Mobile calls `GET /v2/fields/<id>/recommendation | irrigation | disease-risk | advisories?generate=` (`routes/value_v2.py` -> `api/value_endpoints.py`). Each call runs `build_features_for_field` (`api/features.py`), which reads up to 1000 weather/soil/NDVI rows and may refetch weather in-request (`ensure_fresh_weather`, throttled to once per 3h per field, in-process dict). `FeatureBuilder.build` produces a `FeatureVector`. Crop is EcoCrop ranges plus season and annual rain (ADR 0027); irrigation is a daily soil water balance with ET0 (Hargreaves) and forecast; disease is rules (`DiseaseRiskModel`). `DecisionEngine.recommend` joins the three plain-English explanations into an `Advisory` (severity = max of urgency and risk). Results are persisted every time. `plain_advisory` / `plain_irrigation` (`api/farmer_text.py`) produce the farmer-readable text.
4. **Feedback.** `POST /v2/feedback` (`submit_feedback`) checks the advisory belongs to the farmer, then stores rating/helpful/comment. `POST /v2/bug-reports` stores a category, message and optional base64 photo as a `BugReport`.
5. **Voice.** `GET /v2/advisories/<id>/audio?language=` translates (Sarvam first, else IndicTrans2 via `services/voice`) and synthesizes (Sarvam / Piper / vits) and returns OGG with an ETag. `POST /v2/stt` transcribes. `POST /v2/voice/ask` chains STT -> Gemini (answer grounded in the farmer's own rows) -> TTS. `POST /v2/translate` translates up to 10 English strings. All return 503 on failure so the app can fall back to on-device TTS. Caches are process-local dicts (`api/voice_client.py:43-44`).
6. **Leaf photo.** `POST /v2/fields/<id>/disease-risk/image`: `validate_image_upload` (Pillow verify, 10MB), `looks_like_plant_photo` gate (`api/leaf_gate.py`), then `cnn_client.call_cnn_service` -> `services/cnn-onnx` (MobileNetV2 ONNX, optional `X-Service-Token`), one retry. On failure it falls back to the rule-based path (`source=environmental_fallback`). `/health` on the main API wakes the CNN service in the background (`routes/health.py`).
7. **Notifications.** Local only. `mobile/src/notifications.tsx` `notify()` shows an in-app banner if the app is foregrounded, else schedules an immediate local notification, and keeps an inbox in AsyncStorage. There is NO server-driven push: no push token registration anywhere in `mobile/` (grepped) and no scheduler on the backend.
8. **Admin.** `/admin` (Jinja, read-only) and `/v2/admin/{farmers,fields,feedback,scans,advisories}` (`routes/admin.py`, `admin_ui.py`).

### 1.2 Data flow

`Open-Meteo / OWM / NASA POWER / MET Norway / SoilGrids / GEE` -> adapters (`acquisition/`) -> `DataStore` (SQLite dev, Supabase prod) -> `FeatureBuilder` -> models (EcoCrop crop, water-balance irrigation, rule disease; RF path retained as fallback and in the tabular service) -> `ExplanationService` -> `DecisionEngine` -> Advisory row -> Flask JSON -> mobile (AsyncStorage cache via `hooks.ts` stale-while-revalidate) -> optional TTS/translate via Sarvam or `services/voice`.

### 1.3 External services

| Service | Used for |
|---|---|
| Render (3 free web services) | main API, `agro-mirai-tabular`, `agro-mirai-cnn` |
| GitHub Actions | CI (`ci.yml`) and 12-minute keep-alive ping (`keep_alive.yml`) |
| Supabase Postgres | prod persistence via service key (`SupabaseDataStore`) |
| Open-Meteo, OpenWeatherMap, NASA POWER, MET Norway | weather (primary and fallbacks), annual rain |
| SoilGrids (ISRIC) | soil properties |
| Google Earth Engine | NDVI (with local cache fallback) |
| Sarvam AI (3 keys) | translate / TTS / STT (fast path) |
| `services/voice` (AI4Bharat, Oracle VM or container) | fallback translate/TTS/STT |
| Gemini | `/v2/voice/ask` answers |
| Sentry | error monitoring (no-op without DSN) |
| Expo / EAS | mobile build |

---

## 2. Enhancements (ranked by impact / effort, best first)

Effort S/M/L, Impact H/M/L. "Confirmed" = read in code. "Inferred" = follows from code plus deployment behavior but not exercised live.

### E1. OTP is only written to server logs, so production farmers cannot log in - H impact, M effort, risk M
- Evidence: `auth/otp.py` `send_otp` only calls `logger.info` (docstring says "OTP_DELIVERY=log the only mode"). Session lifetime is 24h (`api/app.py:156`), so every farmer needs a fresh OTP daily.
- Fix: plug an SMS provider into the single `send_otp` seam. India requires DLT registration for SMS (see https://help.leadsquared.com/mandatory-dlt-registration-for-sms-services-in-india/); providers with pre-registered DLT (MSG91, Gupshup) can shorten onboarding. Until then, gate the log line behind `OTP_DELIVERY=log` and refuse to start in `FLASK_ENV=production` with it (a demo mode flag). Also stop logging the code in production: anyone with Render log access can take over any account.
- Extend session lifetime for the mobile client (30 days, sliding) so OTP is not needed daily.

### E2. Rate limits are keyed by proxy IP, probably shared by all farmers - H, S, risk L (inferred)
- Evidence: `otp_request_limiter` and `voice_limiter` use `get_remote_address` (`api/login_rate_limit.py` last line); the default limiter (`api/app.py` `_rate_limit_key`) falls back to remote address for session-cookie users (no Bearer header). No `ProxyFix` or `X-Forwarded-For` handling anywhere in `src` (grepped). Behind Render's load balancer gunicorn sees the proxy address, so "5 OTP/min", "20 TTS/min", "60/min default" are likely global, not per user.
- Fix: `werkzeug.middleware.proxy_fix.ProxyFix(x_for=1)` (verify Render's header count), and key authenticated routes by `session["farmer_id"]`. Add a test with `X-Forwarded-For`.

### E3. Forgeable sessions if `FLASK_SECRET_KEY` is ever unset in prod - H, S, risk L (confirmed)
- Evidence: `api/app.py:133` `os.environ.get("FLASK_SECRET_KEY", "dev-only-secret-not-for-prod")`. `render.yaml` has `sync: false`, so a missed dashboard entry silently boots with a public secret, and the session cookie carries `role` (admin).
- Fix: raise at startup when `FLASK_ENV=production` and the key is missing or equals the default. Also make `SESSION_COOKIE_SECURE` default true unless `FLASK_ENV` is `development`/`testing` (`app.py:167` only sets it for exactly "production").

### E4. OTP endpoint creates accounts before verification and leaks registration state - M, S, risk L (confirmed)
- Evidence: `auth_v2.py` `request_otp` calls `store.save_farmer` before any verification, and returns `is_new_farmer`, an enumeration oracle. Anyone can create unlimited farmer rows (bounded only by E2's limiter).
- Fix: store pending registration in the OTP record; create the farmer in `verify_otp`. Drop `is_new_farmer` or return it only after verification. Add a per-phone limit (e.g. 3 requests/hour) in addition to per-IP.

### E5. No service-to-service auth on the tabular service; CNN token optional - M, S, risk L (confirmed)
- Evidence: `services/tabular-ml/app.py` has no token check on `/predict/*` and `/explain/*` (grep for TOKEN found only cnn services). `render.yaml` lists `CNN_SERVICE_TOKEN` for cnn but nothing for tabular; `services/cnn-onnx/app.py:116` accepts requests when the token is unset. Also `request.get_json(force=True)` with no `MAX_CONTENT_LENGTH` on the tabular app, and its errors return `str(exc)` (information leak, 422 for server faults).
- Fix: shared `X-Service-Token` on tabular (same pattern as cnn), fail closed in production when unset, `MAX_CONTENT_LENGTH`, generic error messages.

### E6. Main API has no request body size cap - M, S, risk L (confirmed)
- Evidence: `MAX_CONTENT_LENGTH` set in all three services (`services/*/app.py:84/102/226`) but not in `api/app.py` (grepped). Bug report photos may be a ~14MB base64 string inside JSON (`value_endpoints.py` `_MAX_BUG_PHOTO_DATA_URI_LEN`), stored in a DB row; a 512MB instance parses that in memory.
- Fix: `MAX_CONTENT_LENGTH` (16MB) plus store bug photos outside the DB row (Supabase Storage) or shrink client-side; add a 413 handler that uses the error envelope.

### E7. In-request network work blocks the only 2 worker threads - H, M, risk M (confirmed)
- Evidence: gunicorn `-w 1 --threads 2` (`render.yaml`, `Procfile`). `build_features_for_field` -> `ensure_fresh_weather` (`features.py:24-26`, `field_data_acquisition.py:298`) can run a multi-source weather fetch (join waits up to `_WEATHER_WAIT_S = 20`) inside a GET; `_annual_rain` waits up to 2.5s; `/v2/voice/ask` allows 90s from the client; `/v2/translate` client timeout is 120s. Two slow requests stall everybody.
- Fix: move refresh out of the read path: refresh on field open (fire-and-forget) or from the keep-alive cron (see E8), and read cached rows. Raise threads to 4 if RAM allows, or use `gthread` with per-route timeouts.

### E8. Keep-alive pings `/health` but nothing does useful scheduled work - M, M, risk L (confirmed)
- Evidence: `keep_alive.yml` curls three `/health` URLs; `farms_v2.py` `refresh_field_data` docstring states there is no scheduler. GitHub cron may be delayed or dropped, and "free tier stays awake" is not guaranteed (scheduled workflows are disabled after 60 days without repo activity; inferred from GitHub behavior, not tested here).
- Fix: add a protected `POST /internal/daily-refresh` (token) called by the cron to refresh weather for all fields and generate the daily advisory / alerts (also enables server push, F5). Have the workflow fail loudly (drop `|| true`, add `--fail`) so a dead service shows red.

### E9. Weather freshness state and caches are process-local and unbounded - M, S, risk L (confirmed)
- Evidence: `_last_refresh` dict (`field_data_acquisition.py:48`), `_AUDIO_CACHE` and `_TRANSLATION_CACHE` (`voice_client.py:43-44`), OTP store, and the memory limiters are plain dicts. `_AUDIO_CACHE` stores audio bytes with no size or count bound on a 512MB instance; every Render restart empties all of them (so also all OTPs in flight).
- Fix: `cachetools.TTLCache`/LRU with byte budget for audio; persist audio or translation in Supabase Storage keyed by the advisory ETag hash; put `_last_refresh` on the field row (`weather_refreshed_at`).

### E10. `supabase/migrations` is missing 009; no automated migration apply - M, S, risk L (confirmed)
- Evidence: `supabase/migrations/` ends at `20260915000800_...`, while `migrations/postgres/` has `009_bug_reports.sql`. `migrations/sqlite/` lacks `007`/`008` (SQLite gets those columns through `001_init.sql` regenerated from `schema.yaml`, so needs a check with a pre-008 DB file). Postgres migration comments say "Apply out-of-band" (`005_phone_unique.sql` header).
- Fix: `supabase db push` in a release step; a CI job that diffs `migrations/postgres` against `supabase/migrations` names; add a test that opens an old-shape SQLite DB and upgrades it.

### E11. Admin dashboard N+1 queries and stale columns - M, S, risk L (confirmed)
- Evidence: `admin.py:30` and `admin_ui.py:67` call `store.list_fields(f.id, limit=1000)` per farmer just to count; `_per_field` in `admin.py` runs one query per field for scans/advisories; no pagination; template (`admin_dashboard.html`) shows an Email column but farmers register by phone (email always "-") and phone is not shown; no scan/advisory/bug-report views, no user disable or export; `border="1"` table, admin login is a shared-cookie form with no rate limit or CSRF token.
- Fix: add `count_fields_by_farmer()` and paged `list_all_*` to `DataStore`; show phone, language, last active, field count, scans, mean rating; add bug reports (`BugReport` rows exist, no list method for admin); add CSRF and rate limit on `/admin/login`.

### E12. Docs drift: CLAUDE.md and README describe the retired RF architecture - M, S, risk L (confirmed)
- Evidence: `CLAUDE.md` still says crop is an RF trained by `tools/train_crop_model.py` and irrigation urgency comes from the trained classifier; ADR 0027 and `render.yaml` moved to EcoCrop and water-balance urgency. CLAUDE.md says `/v1` "frozen" and lists module changelog up to 41 only. `render.yaml` still exposes an unused-looking tabular service; CLAUDE.md quotes 374 tests (stale).
- Fix: rewrite the "Current phase" block as a short current-state summary, move history into `PROGRESS.md`, and make `tools/update_state.py` also regenerate the architecture diagram list.

### E13. Leftover RF artifacts and dead-ish tabular path - M, M, risk M (confirmed)
- Evidence: `git ls-files` shows `services/tabular-ml/model/crop_rf.joblib` and `irrigation_rf.joblib` (about 68MB of binaries) committed; main `requirements.txt` still pins scikit-learn, shap, numba, llvmlite, pandas, scipy (heavy for a 512MB instance) though the product path is now plain Python; `DecisionEngine.__init__` (`models/decision_engine.py:40-46`) defaults to `RemoteCropModel`/`RemoteIrrigationModel` while `create_app` injects local models, so the remote client is dead unless someone constructs `DecisionEngine()` directly; `ExplanationService._remote_contributions` still calls the tabular `/explain/*` (`explanation_service.py:95`, 25s timeout). CI still trains both RFs (`ci.yml`).
- Fix: decide: either delete tabular service plus RF/SHAP and drop those pins (saves RAM and cold start, 68MB from history), or keep it as a documented "ML ranker" with a purpose. Note the model-research doc's verdict (retire irrigation ML, keep ML only as secondary ranker).

### E14. Cold-start and retry policy is inconsistent - M, S, risk L (confirmed)
- Evidence: `cnn_client.py` retries network errors once; `remote_tabular_client._post_with_retry` retries once with doubled timeout; Sarvam/Gemini/voice have no retry; mobile `request()` (`mobile/src/api.ts`) has no retry or backoff for GETs (only `wakeServer`). The keep-alive is the only defense against a 30-60s cold start.
- Fix: a tiny shared `http_retry` helper (2 tries, jittered backoff, idempotent GET only) in the API, and in `api.ts` retry idempotent GETs on network error and 502/503/504 (Render returns these during wake).

### E15. Supabase service key used for all farmer queries - M, M, risk M (confirmed design, RLS state unknown)
- Evidence: `supabase_store.py:70-80` uses `SUPABASE_KEY` (a service-role key given the store bypasses per-user auth); no RLS statements in `migrations/postgres` or `supabase/migrations` (grepped "policy"/"row level": none). Tenant isolation lives only in application code (`get_field(farmer_id, ...)`).
- Fix: at minimum enable RLS with no policies (deny all for anon key) so a leaked anon key exposes nothing; document that only the API holds the service key; add a test that every `list_*`/`get_*` takes and applies `farmer_id`.

### E16. Persisted data grows without bound and results are recomputed per read - M, M, risk L (confirmed)
- Evidence: `compute_recommendation`/`compute_irrigation` save a new row on every GET (`value_endpoints.py`); disease has a 1h dedupe but crop and irrigation do not; `build_features_for_field` loads up to 1000 rows of each type for every request (`features.py:20-31`); Supabase free plan is 500MB.
- Fix: dedupe crop/irrigation like disease (same inputs, same day -> return latest); cache the `FeatureVector` per field for a few minutes; add retention (delete weather older than 90 days, keep advisories 1 year); index `(field_id, observed_at)` in Postgres (only `field_id` indexes exist, `001_init.sql`).

### E17. Test gaps and CI configuration - M, M, risk L (confirmed)
- Evidence: no mobile tests or `tsc`/lint step in CI (`ci.yml` covers Python only; `mobile/` has no `__tests__`); `tests/voice` and `tests/vision` are excluded from CI; `services/tabular-ml/tests` has one file; no test found for `keep_alive`, `ensure_fresh_weather` throttling, OTP under a real proxy, `/v2/translate` (route not in `openapi.yaml`, count 0 in grep), and `check_specs.py` therefore cannot catch it; lint is `continue-on-error`. Live-network tests are deselected by name in `ci.yml`. No Postgres/Supabase test at all (only SQLite is exercised).
- Fix: add `npx tsc --noEmit` and an Expo lint job; contract test that every registered `/v2` route is in `openapi.yaml`; a Postgres service container (or `pytest-postgresql`) running the store contract tests against `SupabaseDataStore` via a fake or PostgREST mock; make ruff blocking on `src`.

### E18. Observability is thin - M, S, risk L (confirmed)
- Evidence: Sentry only when DSN set and `traces_sample_rate=0.0` (`app.py`), and the farmer tag uses `app.config["FARMER_ID"]` (the /v1 shared id) rather than `g.farmer_id`, so /v2 errors carry no farmer; request logging (`request_context.py`) prints method/path/status only, no latency, no farmer id; no metrics; `/health` returns only ok/degraded and hides which dependency is down (CNN, tabular, voice, Supabase).
- Fix: log latency and farmer_id, tag Sentry with `g.farmer_id`, add `/health/deep` (admin or token) that checks store, CNN, tabular, voice URLs and returns per-dependency status and version; count fallbacks (`environmental_fallback`, voice 503, GEE cache) as log lines you can alert on.

### E19. Mobile accessibility gaps - M, M, risk L (confirmed)
- Evidence: `grep accessibilityLabel|accessibilityRole` across `mobile/src` and `App.tsx` found 1 hit against 84 `onPress` handlers; `app.json` locks `userInterfaceStyle: light`; icons (`icons.tsx`) are custom SVG-like components with no labels. Farmer UX research covers content; this is the missing screen-reader/touch-target layer.
- Fix: label every icon-only Pressable, add `accessibilityRole="button"`, minimum 48dp targets, respect font scaling (test at 130%), and add TalkBack smoke-check to release checklist.

### E20. i18n is one 1164-line hard-coded file with server text left in English - M, M, risk L (confirmed)
- Evidence: `mobile/src/i18n.ts` (83KB, four languages inline); server text (advisories, irrigation rationale) is English and translated on demand via `/v2/translate` (round trip to Sarvam or IndicTrans2, 120s client timeout) and cached per string on the device (`hooks.ts:100`).
- Fix: return stable message codes plus parameters from the API for the fixed sentences (`RISK_ACTION`, irrigation wording, EcoCrop reasons) so the app renders them from local dictionaries; keep MT only for free text. Removes a network dependency and the cold-start cost from the most common screen.

### E21. Offline behavior is read-only cache without a queue - M, M, risk L (confirmed)
- Evidence: `hooks.ts` does stale-while-revalidate with `fromCache`; `storage.ts` cache is per key with no expiry or size limit; writes (`sendFeedback`, `sendBugReport`, `patchField`, scans) fail with an error when offline, and there is no retry queue. `withCleartextTraffic.js` plugin allows http traffic in release builds (comment says remove once HTTPS), yet `PRODUCTION_API_BASE_URL` is https, so the exception is no longer needed.
- Fix: a small outbox in AsyncStorage for feedback/bug reports/field edits, flushed when `subscribeNet` reports online; remove the cleartext plugin for release; add cache TTL and a "last updated" label on cached advisories.

### E22. Session/cookie model on mobile depends on native cookie jar - M, M, risk M (inferred)
- Evidence: `api.ts` header comment: "React Native's native networking layer stores and resends" the cookie; 401 handler calls `onUnauthorized` and logs out. Cookie has `SameSite=None` (`render.yaml`), fine for mobile but unnecessary for the native app and it widens CSRF exposure for the `/admin` and any browser use.
- Fix: for mobile, issue a bearer session token (signed, stored in `expo-secure-store`) alongside cookies, keep cookies for `/admin` with `SameSite=Lax`. Also ensures the session survives OS cookie-jar clearing.

### E23. Duplicate allowlists and small code-quality debts - L, S, risk L (confirmed)
- Evidence: `V1_LANGUAGES` is now imported in `farms_v2.py` (fine), but `_LANGUAGE_NAMES` in `voice_client.py:~30`, mobile `i18n.ts` and `openapi.yaml` enums carry their own lists; `value_endpoints.py` has three copies of the "language override else farmer preferred else en" rule (`resolve_disease_target_lang` vs `voice_v2._resolve_language`, the docstring admits it); `auth/validation` plus `_normalize_phone` live in a route file; `farms_v2.py` `update_me` rebuilds a `Farmer` by hand (already caused one bug per its own comment) instead of `dataclasses.replace`; `models/` (repo root) directory and root files `agro_mirai.db`, `seed_fixture.db`, `AGRO_MIRAI_DEMO.zip` (22.8MB) sit in the working tree (db/zip not tracked per `git ls-files`, but worth a .gitignore check).
- Fix: one `resolve_language()` helper, `dataclasses.replace` for updates, move `_normalize_phone` to `auth/validation.py`.

### E24. `/v1` shared-key surface and token comparison - L, S, risk L (confirmed)
- Evidence: `api/auth.py:25` `token != expected` is not constant-time; `/v1` maps every caller to one `FARMER_ID` and is still registered in production.
- Fix: `hmac.compare_digest`; disable `/v1` in production unless an env flag is set (ADR 0017 keeps it for demo continuity, so a flag preserves that).

### E25. Photo scan trust gaps - M, M, risk M (confirmed design)
- Evidence: CNN trained on PlantVillage (4 of 38 crops in the crop enum; see ADR 0018 and the model research doc); `leaf_gate.py` is a heuristic gate; no user-visible "not sure" state when the softmax is low beyond risk level mapping; photos are not stored, so feedback on a wrong scan cannot be used to improve it.
- Fix: return `confidence_band` and show "not sure, retake photo" below a threshold; store the photo (Supabase Storage, consent checkbox) with the scan for the retraining loop the model research recommends.

---

## 3. New feature ideas

### F1. Mandi (market) price tracker
- Why: farmers decide when and where to sell; crop advice without price context is half the answer.
- Data: Agmarknet daily prices via data.gov.in (state/district/market/commodity; min, max, modal price), free with a registered API key. https://www.data.gov.in/catalog/current-daily-price-various-commodities-various-markets-mandi
- Effort: M (adapter in `acquisition/`, a `market_prices` table, `GET /v2/fields/<id>/market-prices` for nearest markets, a mobile card; cache daily via the E8 cron).
- Fit: same adapter + repository pattern as weather; additive OpenAPI paths; degrade to last cached day.

### F2. Server push and daily "what to do today" digest
- Why: today's notifications are local only, so a farmer who does not open the app gets nothing, even for a severe disease-risk or irrigation-due alert.
- Data: none new. Uses existing advisories plus Expo push tokens (Expo Push service, https://docs.expo.dev/push-notifications/overview/ - not verified by search in this audit).
- Effort: M (store push token on `farmers`, migration, daily cron job from E8, send only when severity is high/severe or irrigation window opens).
- Fit: cron endpoint from E8, additive `PUT /v2/farmers/me/push-token`.

### F3. Government scheme finder
- Why: PM-KISAN, crop insurance and state subsidies are underused; farmers rarely know eligibility.
- Data: myScheme (https://www.myscheme.gov.in/) publishes 4,700+ central and state schemes; public scraped datasets exist (https://www.kaggle.com/datasets/elchemist/myscheme-india-govt-welfare-schemes). Confirm license and freshness before shipping, and prefer linking to the official page.
- Effort: M (static curated table filtered to agriculture and Karnataka/Telangana/Andhra, matched on land size and crop; text translated with the existing MT).
- Fit: a read-only reference table plus `GET /v2/schemes`; no per-user data needed.

### F4. Irrigation and input logging feeding the water balance
- Why: the water balance (`soil_water_balance.py`) must guess what the farmer already irrigated; a one-tap "I irrigated 20mm today" makes advice honest and creates real ground truth for future model checks. Also enables yield tracking at harvest.
- Data: farmer-entered.
- Effort: M (`field_events` table, `POST /v2/fields/<id>/events`, feed into the balance as inflow, a simple history list).
- Fit: additive schema and migration (both dialects), one more feature-builder input.

### F5. Official agromet advisory (IMD GKMS) as a cross-check
- Why: district-level bulletins are what farmers already hear about; showing them next to the app's advice builds trust and covers gaps where our rules are weak.
- Data: IMD Gramin Krishi Mausam Sewa district agromet bulletins, twice weekly (https://mausam.imd.gov.in/responsive/agromet_adv_ser_state_current.php). Bulletins are PDFs/pages; check reuse terms before republishing.
- Effort: L (scrape and parse per district, language handling).
- Fit: an optional "official advisory" card via a new adapter with cache; not blocking.

### F6. Crop calendar reminders
- Why: sowing, fertiliser and harvest timing are the questions farmers ask most, and `sown_on` and `current_crop` already exist on `Field_`.
- Data: FAO EcoCrop cycle lengths (already vendored for crops, `tools/build_ecocrop_table.py`) plus Kc growth stages (`crop_coefficients.py`); state ICAR calendars for validation.
- Effort: S-M (derive stage dates from `sown_on`, schedule local notifications now, server push later via F2).
- Fit: pure function of existing fields, no new external service.

Note: WhatsApp/SMS delivery of advisories is a candidate too, but it needs the same DLT/business verification as E1; sequence it after E1.

---

## 4. Three-sprint roadmap

**Sprint 1 - Make it safe and real (1-2 weeks)**
E3 (fail on default secret), E2 (ProxyFix + farmer-keyed limits), E4 (create farmer on verify), E5 and E6 (service token, body cap), E24, E1 stage 1 (OTP demo flag + refuse log in prod; start DLT paperwork), E10 (migration parity + CI check), E12 (docs). All S effort, mostly one-file changes with tests.

**Sprint 2 - Reliability, cost and trust (2 weeks)**
E7 (remove in-request refresh) together with E8 (daily-refresh cron endpoint), E9 and E16 (bounded caches, dedupe, retention, index), E14, E18, E13 (decide RF/tabular fate, drop heavy deps), E17 (mobile tsc in CI, route-vs-openapi test), E11 (admin count/pagination, phone, bug reports). E1 stage 2 if the SMS vendor is ready. Start F4 (irrigation log) since it needs the migration path from E10.

**Sprint 3 - Farmer value (2 weeks)**
F2 (push digest, uses E8 cron), F1 (mandi prices), F6 (calendar reminders), E20 (message codes), E21 (outbox), E19 (accessibility pass), E25 (scan confidence band + consented photo storage). F3 and F5 as stretch or next module.

---

## 5. Verified vs unverified

Confirmed by reading code (file and line evidence above): E3, E4, E5, E6, E7, E8 (workflow and docstring), E9, E10 (directory listings), E11, E12, E13, E14, E16, E17 (test tree and CI file), E19 (grep counts), E20, E21, E23, E24, and the walkthrough in section 1.

Inferred, not run live: E2 (Render proxy address behavior and gunicorn `forwarded_allow_ips` default; needs one deploy test logging `request.remote_addr`), E8's claim about GitHub cron delays and 60-day disablement, E15 (whether RLS is enabled in the live Supabase project was not checked; only migrations were read), E22 (RN cookie jar behavior), cold-start durations, SMS provider cost/DLT timelines (from search results in section 3 and the E1 link).

Not audited in depth: `services/voice` internals, `services/cnn-inference` (torch variant), `acquisition/earth_engine.py`, `feedback/aggregator.py`, most of `mobile/src/screens/*` beyond grep-level checks, and `web/`. Files under active edit by another engineer (irrigation and crop model files, `value_endpoints.py`, `serializers.py`, mobile HomeTab) were read for design only and no bugs are reported against them. External data sources in section 3 were confirmed to exist via web search only; API terms, rate limits and data freshness must be checked before building. The Expo push docs URL in F2 was not checked by search.
