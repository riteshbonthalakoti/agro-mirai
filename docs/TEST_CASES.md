# AGRO MIRAI — Final Test Cases

Built from the actual automated test suite (95 test files under `tests/`), re-run fresh for this document. **714 passed, 40 skipped, 0 failed** (skips are deliberately gated — real external APIs that need live credentials/network not present in CI, e.g. a handful of Open-Meteo/SoilGrids live-call tests).

Run it yourself:
```bash
PYTHONPATH=src .venv/Scripts/pytest.exe --ignore=tests/voice --ignore=tests/vision -q
```

This document describes real, existing test scenarios — it does not invent coverage that isn't there. Where something is only manually tested (most of the mobile UI, for instance), that's said plainly rather than implied.

---

## Test levels

| Level | What it means here | Test count | Representative files |
|---|---|---|---|
| **Unit** | A single function/class in isolation — model math, serializers, validators, single-adapter logic, mocked dependencies | ~547 | `tests/models/test_ecocrop.py`, `test_soil_water_balance.py`, `tests/api/test_serializers.py`, `tests/auth/test_otp.py`, `tests/api/test_key_pool.py` |
| **Integration** | Multiple real components wired together — API route → model → store, LLM cascade with real fallback chain, SQLite ↔ Supabase contract parity | 160 | `tests/api/test_v2_auth_integration.py` (26), `tests/persistence/contract/test_contract.py` (48, runs identically against both DB backends), `tests/api/test_gemini_cascade.py`, `tests/models/test_decision_engine_integration.py` |
| **System (E2E)** | Hits the actual deployed production backend over the network, no test client, no mocks | 6 | `tests/e2e/test_deployed_smoke.py` — pings the live Render `/health` endpoint |

Excluded from the counts above (separate suites, not run by default): `tests/voice/`, `tests/vision/`, `tests/voice_remote/`, and `services/*/tests` — these need either a live model download or an external service, so they're gated out of the fast CI run via `--ignore=tests/voice --ignore=tests/vision`.

---

## 1. Authentication & Session Management (`tests/api/test_v2_auth_integration.py`, `tests/auth/`)

- Phone number normalization: a bare 10-digit number, one with spaces/dashes, and an already-E.164 number all resolve to the same stored identity.
- OTP request never leaks the stored OTP hash in the response.
- First OTP request for a new phone returns `is_new_farmer: true`; a repeat request for the same phone returns `false`.
- A new phone number without a name is rejected (farmers must be named on first contact); an existing phone doesn't require a name again.
- Every one of the 4 supported languages (`en`/`hi`/`kn`/`te`) is accepted on OTP request; an unsupported language code is rejected.
- Wrong OTP code returns 401 **and** does not consume/invalidate the real pending code (so a mistyped digit doesn't lock the farmer out of their real code).
- A second OTP request within seconds of the first is refused (anti-spam).
- An unverified OTP request never creates a farmer record.
- A successful verify returns a session token; that token works as a `Bearer` header **without** needing the cookie too.
- A bearer token from one farmer cannot read another farmer's data (cross-tenant check at the auth layer itself, not just the data layer).
- A malformed bearer token degrades to a clean 401, not a server crash.
- Session expiry: a 100-day-old bearer token is still accepted; a 200-day-old one is correctly rejected (tests the exact configured lifetime boundary, not just "eventually expires").
- Every `/v2` route requires a session — hitting one with no auth at all returns 401.

## 2. Multi-tenancy / Cross-Account Isolation (`tests/api/test_v2_value_endpoints.py`, `tests/persistence/contract/`)

This is the hard rule of the whole project (CLAUDE.md: "account_id isolation — every DB query scoped to the calling user. No exceptions.") and it's tested explicitly per-route, not just assumed from a shared decorator:

- Crop recommendation, irrigation, disease risk (both the environmental and the image-scan versions), advisories, and feedback submission **each individually** verified: farmer A cannot fetch farmer B's field data through that specific endpoint — every one returns 404 (not a leak, not a 403 that confirms the record exists), matching "not found" rather than "forbidden."
- A dedicated persistence-layer test (`test_other_farmers_field_is_refused`) checks the same isolation one layer deeper, directly against the data store, for both weather readings and NDVI readings.
- The persistence contract suite (`tests/persistence/contract/test_contract.py`) runs the **same** assertions against both the SQLite store and the Supabase store, so a bug that only shows up in one backend can't hide.

## 3. Value Endpoints — Recommendation, Irrigation, Disease Risk (`tests/api/test_v2_value_endpoints.py`)

- Each of the three main advice endpoints has a success-path test (real schema-valid response) and a requires-session test.
- Irrigation: when a field genuinely has no weather history, the endpoint returns a clean 422 ("not enough data"), not a 500 crash.
- Disease risk: repeatedly polling the same endpoint does not spam duplicate near-identical alert rows (the 1-hour dedup window is exercised directly).
- Disease-risk-image: both the "Gemini/vision unavailable" 503 path and the real successful-diagnosis path are tested, including with a mocked image upload.
- Advisories: `generate=false` (just viewing) never creates a new advisory row; only an explicit `generate=true` request does.

## 4. Crop Recommendation Engine (`tests/models/test_ecocrop.py`, `test_crop_recommendation_model.py`, `test_crop_recommendation_cascade.py`, `tests/api/test_crop_llm.py`)

- The EcoCrop table genuinely has all 22 known crop labels, every score is between 0 and 1, and results come back sorted.
- Cooler input temperatures do shift the ranking toward cool-weather crops (a real behavioral check, not just "it returns something").
- Missing pH or rainfall data doesn't crash scoring — it still returns a ranked result.
- Season affects the pick (sowing-month fit is exercised, not just climate fit).
- A real annual-rainfall figure correctly separates a genuinely wet climate's ranking from a genuinely dry one's.
- The LLM tier (`crop_llm.py`) is tested with a mocked Gemini response for both the success path and the "reply names a crop outside our known 22" rejection path, confirming the fallback to the rule engine actually fires when the LLM can't be trusted.
- The full cascade (LLM tier → rule-based tier) is tested end-to-end, not just each tier in isolation.

## 5. Irrigation Model (`tests/models/test_irrigation_prediction_model.py`, `test_soil_water_balance.py`, `test_evapotranspiration.py`)

- Output is always schema-valid, the recommended depth is always positive, and urgency can never come back as `"severe"` (that level is reserved for a different alert type — tested as a real guardrail, not assumed).
- The recommended depth is explicitly checked to be water-balance-derived (it moves when the inputs move) rather than a fixed lookup table keyed off urgency.
- The rationale text actually cites real ET0 and deficit numbers, not boilerplate.
- Missing temperature extremes (no daily min/max on record) correctly falls back to the documented diurnal-range approximation rather than failing.
- Heavy rain genuinely produces low urgency; no rain at all genuinely produces high urgency (directional sanity checks on the real calculation).
- A field with absolutely no usable temperature data in any of the 7d/14d/30d windows correctly raises rather than silently guessing.

## 6. Disease Risk Scoring (`tests/models/test_disease_risk_scoring.py`, `test_disease_risk_model.py`, `test_image_or_environmental_disease.py`)

- High humidity + high rainfall + optimal pathogen temperature + declining satellite greenness together score as `severe` — tests the real multi-factor scoring logic, not a single input in isolation.
- Low humidity + no rain + extreme temperature scores as `low`.
- Missing NDVI data correctly reduces confidence rather than pretending full confidence on partial data.
- A missing NDVI *trend* (as opposed to missing NDVI entirely) contributes no penalty — explicitly checked to not be miscounted as a bonus either.
- Missing humidity or temperature correctly raises rather than guessing a plausible-looking score.

## 7. Persistence Layer — SQLite + Supabase Parity (`tests/persistence/`)

- Save/get round-trips, upsert behavior, and list/filter queries are tested identically against both backends via one shared contract test class per record type (farmers, fields, weather, soil, NDVI, crop recommendations, irrigation advice, disease alerts, advisories, feedback).
- Bulk-save operations and an empty-batch no-op are both covered.
- Admin write-audit-log entries round-trip correctly, and the audit migration itself is tested.
- A dedicated test (`test_supabase_bad_ids.py`) checks that a malformed UUID passed to Supabase is treated as "not found," matching SQLite's behavior, instead of surfacing a raw PostgREST error to the caller.
- `test_transport_retry.py` exercises the retry-on-connection-error behavior at the HTTP transport level.

## 8. Admin Dashboard (`tests/api/test_admin_routes.py`, `test_admin_write_routes.py`, `test_admin_ui.py`, `test_admin_bug_report_stream.py`)

- Every admin route requires the `admin` role specifically — a logged-in farmer who isn't an admin gets 403, not 401 (tested as a distinct case from "not logged in at all").
- Write routes (editing/deleting a farmer or field) are tested to actually produce an audit log entry, not just perform the write silently.
- The bug-report live stream (Server-Sent Events) is tested for correctly surfacing a newly-created report without re-sending ones already seen.

## 9. Voice (`tests/voice/`, `tests/api/test_sarvam_client.py`, `test_voice_client_fallback.py`)

- A shared conformance suite runs the **same** assertions against both voice adapters (AI4Bharat and the Bhashini stub), so neither can silently drift from the shared interface contract.
- The Sarvam client's real request/response shape is tested.
- The fallback path (cloud tier unavailable → self-hosted tier, or → honest "unavailable" message) is tested explicitly rather than assumed.

## 10. Feedback Aggregation (`tests/feedback/`)

- Mean rating and helpful-rate calculations are tested against known input sets with hand-computed expected results, both as pure unit logic and as a real integration through the store.

## 11. End-to-End Smoke Test (`tests/e2e/test_deployed_smoke.py`)

- Hits the real deployed production backend's `/health` endpoint — the one test in the suite that checks the actual live Render deployment is reachable, not a local test client.

## 12. Tools & Scripts (`tests/tools/test_backup_supabase.py`, `tests/test_module_03_acquisition.py`)

- The Supabase backup script is tested against a real schema shape.
- The weather/soil/NDVI data-acquisition adapters (Open-Meteo, SoilGrids, Earth Engine) each have contract tests confirming they map external API responses into this project's own schema correctly.

---

## Known gaps — honestly, not papered over

- **Mobile app UI**: no automated test suite exists for the React Native app itself (no Jest/Detox component or E2E tests found in `mobile/`) — `mobile/jest.config.js` exists but the test coverage behind it is minimal to none. All mobile UI verification this project has done has been manual (live device testing, screen recordings), not automated.
- **Vision/CNN model tests** (`tests/vision/`, `tests/voice_remote/`) are excluded from the standard CI run (`--ignore=tests/voice --ignore=tests/vision`) because they need either a live model download or a reachable external service not available in every environment — they exist and pass when run with those dependencies present, but aren't part of the fast default run.
- **Live external-API tests** (a handful of real Open-Meteo/SoilGrids calls) are marked to skip without live network/credentials — the 40 skips in the headline number are mostly these, not untested code paths.
