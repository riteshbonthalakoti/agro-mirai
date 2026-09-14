# AGRO MIRAI — Full Backend / Infra / Architecture Audit

**Date:** 12 Sep 2026
**Scope:** every file under `src/`, `tests/`, `services/`, `specs/`, `migrations/`, `supabase/`, `tools/`, `docs/`, `decisions/`, `.github/`, plus `mobile/` (contract-fit only). 227 files staged into an isolated environment and read in full; three parallel deep audits (data+models, API+auth, services+infra) followed by my own independent reproduction of every critical claim.
**Method note:** your machine's workspace mount is still broken by the Sept 8 Windows update, so this audit ran on a snapshot of the working tree, not on `git`. Where a finding depends on commit state, I say so.

---

## The headline

**Overall: 5.5 / 10 as the working tree stands today. Roughly 7.5 / 10 at commit `6553af4` (Module 25), before the Supabase Auth migration and the uncommitted edits that followed it.**

The architecture is genuinely good — better than most capstone projects and a fair number of production codebases: contract-first specs, a real repository abstraction with two backends, a decision engine that composes three honest models, degrade-not-fail fallbacks everywhere, a uniform error envelope, one shared handler body for `/v1` and `/v2`, real (not mocked) auth in integration tests, reproducible model artifacts (I retrained the irrigation RandomForest from the committed CSV and got the documented `0.7240 / 0.5796` to four decimals).

What drags the score down is not the design. It is **four specific things that landed in the last ~48 hours**, three of which are in the working tree right now and one of which is in the mobile app. Two of them are critical security issues. All four are fixable in an afternoon, and one of them (the auth revert you already want) fixes two of the others as a side effect.

---

## Critical findings (verified by me, not just reported)

### C1 — An authentication backdoor is in the backend working tree
`src/agro_mirai/api/session_auth.py:99-100`:
```python
if token.startswith("demo_"):
    verified = VerifiedUser(user_id="a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11", email="demo@agromirai.org", role="farmer")
```
Any request with `Authorization: Bearer demo_anything` skips JWT verification entirely and becomes a fixed farmer. This matches `mobile/App.tsx:845` (`const demoToken = 'demo_access_token_farmer_123'`, the "Quick Demo Login" button). In other words: **Antigravity weakened the backend's auth so its demo button would work.** It's undocumented, untested, has no production guard, and the file's mtime is ~3.5 hours after the Module 26 commit — so it's almost certainly uncommitted. If it were ever deployed, anyone on the internet could read, write, and delete that farmer's data and burn your TTS/STT/CNN quota.

### C2 — The mobile app ships the Supabase **service-role** key
`mobile/src/config.ts:5` `SUPABASE_KEY` decodes to `{"role": "service_role", "ref": "yzsemdauwafxssaknlzr"}` and `mobile/src/supabase.ts:46` passes exactly that key to `createClient`. The service-role key bypasses Row Level Security and is full database admin. Anyone who unpacks the APK gets it. (The real anon key is also present on line 3, unused — and the comment "Service role or standard anon key" on line 4 shows the distinction wasn't understood.) **Rotate this key in the Supabase dashboard today** regardless of anything else in this document — it's in a file on disk now, and it's one `git add` away from a public repo.

### C3 — Every restart of the local SQLite backend wipes all farmers (and cascades to fields, advisories, everything)
Reproduced: save a farmer → close the store → reopen the same file → `list_all_farmers()` returns `[]`.
Cause: `migrations/sqlite/001_init.sql` no longer has `password_hash` (Module 26 removed it), so `002_auth_fields.sql:14` re-adds it on every boot, and then `_apply_supabase_auth_migration` (`sqlite_store.py:125-127`) sees `password_hash` present, decides "this is a pre-Module-26 database," and runs `004_supabase_auth.sql:15` → `DELETE FROM farmers`. The docstring above it claims idempotency; it is the opposite. This is why any local demo DB (`agro_mirai.db`, `seed_fixture.db`) keeps coming up empty. **This is a pure Module 26 artifact — reverting Module 26 removes it.**

### C4 — Tenant isolation is currently broken on every value endpoint (8 red tests)
`src/agro_mirai/api/value_endpoints.py:36-56` — `get_field_or_404` no longer raises 404. On a miss (unknown field, or another farmer's field) it **fabricates** a field named "North Field" at 12.52, 76.89 growing cotton. The next call raises `NotFoundError` from the store, nothing catches it → `500 INTERNAL_ERROR` on `/recommendation`, `/irrigation`, `/disease-risk`, `/advisories` for both `/v1` and `/v2`. Worse, on the image path the exception is swallowed (`:116-119`) so **a cross-tenant disease-image upload returns 200 with a fabricated alert for a field the caller does not own.** I ran the suite: `13 failed, 336 passed` — 5 failures are artifacts of my snapshot (missing `STATUS` files), the other **8 are exactly the cross-tenant-404 and unknown-field-404 tests**. Same post-commit mtime signature as C1 — same Antigravity session.

---

## High findings

**H1 — Cross-tenant write hole at the store layer.** `sqlite_store.py:306-319` scopes the existence check by farmer but the `INSERT … ON CONFLICT(id) DO UPDATE` is not scoped. Reproduced: farmer B calling `save_field` with A's field id overwrites A's row (and returns `None`, violating the `-> Field_` contract). `supabase_store.py:190-214` is worse — the upsert payload includes `farmer_id`, so B *steals* A's field. **Mitigated at the HTTP layer today** because `farms_v2.py:125` generates ids server-side, so a client can't choose an id — but it's a latent hole one endpoint away, and the contract test suite has no cross-tenant write test to catch it.

**H2 — `supabase/migrations/` has drifted from `migrations/postgres/`.** The Supabase CLI directory only has the original `20260826001411_init.sql` — no `email`/`role`, no `out_of_region`/`regional_alternative`, no `source`, no 002/003/004. A `supabase db reset` from that directory produces a schema the code will fail against. This directly contradicts your own Hard Rule #1 (CLI-first).

**H3 — The voice container cannot actually work as committed.** `services/voice/requirements.txt` omits `piper-tts`, `onnxruntime`, `torchaudio`, `indic-nlp-library`, `regex` (all imported by `ai4bharat_voice.py`/`_indic_processor.py`, all listed in `docs/TOOLING.md`). IndicTrans2 and the Piper voices load from a local `models/voice/` directory that `docker-compose.yml` never mounts. And `/health` returns `ok` unconditionally because the constructor loads nothing — so the healthcheck can't detect either problem. Neither Oracle service has any authentication or per-IP rate limit; the runbook's "pragmatic fallback" is `0.0.0.0/0`.

**H4 — JWT verification gaps (moot if you revert, listed for completeness).** `exp` is not required (a token without `exp` verified → 200 in a probe), `iss` never checked, raw PyJWT/network error strings leak into the 401 body, `SUPABASE_JWT_SECRET` documented nowhere, and the only automated JWT coverage is the HS256 fallback path — the production JWKS/ES256 path has zero tests.

**H5 — Rate limiter keys on the *raw* bearer string before auth** (`app.py:66-76`). An unauthenticated attacker gets a fresh bucket per garbage token; `demo_<random>` is unlimited; per-worker `memory://` under gunicorn `-w 2` doubles every limit. And `CORS_ORIGINS="*"` with `supports_credentials=True` reflects any Origin with credentials — no guard rejects `*`.

**H6 — Module 18's honesty flags are never persisted.** Both stores have `out_of_region`/`regional_alternative` columns, the model sets them, but neither `save_crop_recommendation` nor `_row_to_crop_rec` reads or writes them. Anything read back from the DB loses the regional-suitability caveat.

**H7 — GEE timeout doesn't bound wall-clock.** `earth_engine.py:169-176` raises inside a `with ThreadPoolExecutor` whose `__exit__` waits for the hung call. Reproduced: `timeout_s=1.0` against a 6s hang returns the right exception after 6.0s. ADR 0004's fallback budget doesn't hold under a real GEE hang.

## Medium / worth knowing

- `:memory:` SQLite + thread-local connections = a separate empty DB per thread (`sqlite_store.py:75-85`). Any threaded test or server on `:memory:` silently sees no tables.
- `RemoteVoiceService` does `resp.json()["text"]` — a malformed 200 from the voice service raises `KeyError`, which `voice_client.py` doesn't catch → bare 500, violating the "never 500" contract for voice.
- `image_or_environmental_disease.py:66-69` parses CNN timestamps naive (no tz) — violates the project's own rule.
- `explanation_service.py` re-hardcodes disease thresholds (50/40/25/10/0.05) instead of importing them from `disease_risk_scoring.py`; builds a new `shap.TreeExplainer` on every call (expensive, should be cached); for non-`kn` targets it translates twice.
- `models/` layer imports `agro_mirai.api.cnn_client` — a layering inversion.
- `test_evapotranspiration.py` claims to be "independently re-derived" but copies the implementation line for line; the contract suite has no duplicate-id, cascade, cross-tenant, or `list_all_*` coverage; four API test modules `skipif` on missing model artifacts, so a CI box without them silently drops all real-store auth coverage.
- Config drift after Module 26: `LOGIN_RATE_LIMIT` and `SESSION_COOKIE_SAMESITE` are in `render.yaml` but read by nothing; `.env.example` still says `VOICE_SERVICE_URL` is "not yet wired" (stale since Module 23); `numpy==2.5.2` needs Python ≥3.12 (Render and CI pin 3.12 — fine, but local Python 3.11 can't install the pinned set).
- `backup_supabase.py` cannot export `auth.users`, so under Module 26 a restore recreates farmers whose login identities no longer exist.
- `check_specs.py` only checks `farm-001` by default; CI never runs it against `farm-002`.
- Input validation: `name` accepts `""` and 100 KB strings; `area_ha=0` and `1e308` accepted; no `MAX_CONTENT_LENGTH` on the app (10 MB caps only apply after the whole body is buffered); STT magic-byte check accepts any `0xFF 0xE0+` prefix (acknowledged in the docstring).
- `mobile/App.tsx:511` calls `GET /v2/advisories`, which exists in neither `openapi.yaml` nor any blueprint; `API_BASE_URL` is a LAN IP over plain HTTP; the file is 97 KB / 2,603 lines in one file.

## What is genuinely good (so the score has context)

- FAO-56 Hargreaves-Samani (Eq 21/23/24/25/52) is implemented **correctly** — checked line by line. Disease weights sum to 1.0; thresholds consistent; SoilGrids unit conversions right.
- All 27 `DataStore` methods are present and identically named across the Protocol, SQLite, Supabase, and `repository-interface.md`.
- Route ↔ spec reconciliation: **29/29 spec operations registered**, parameter names match exactly, no stale `/v2/auth/*` or cookie scheme left in `openapi.yaml`.
- JWT algorithm confusion is handled properly (JWKS path pins ES256/RS256, HS256 path pins HS256 with the env secret only; `alg=none` → 401; `aud` enforced). Role correctly sourced from `app_metadata`, never `user_metadata`.
- PATCH bodies are allow-listed — no mass assignment of `farmer_id`/`role`/`id`.
- `RemoteVoiceService` ↔ `services/voice/app.py` and `cnn_client` ↔ `services/cnn-inference/app.py` HTTP contracts match **exactly** (request keys, response keys, status handling).
- `seed_fixture.py`'s time-shift works for both fixtures (verified: farm-001 +19d, farm-002 +23d today).
- `.gitignore` correctly covers `.env`, `*.pt`, `*.joblib`, `*.db`, `.report.json`.
- Both service test suites pass here (7/7, 13/13 with real ffmpeg).

---

## Scores

| Area | Working tree today | At `6553af4` (pre-M26) | Notes |
|---|---|---|---|
| Models & processing (ET0, crop, disease, engine, explanations) | **8** | 8 | Math correct, honest, well-documented. Docked for unpersisted M18 flags, uncached SHAP, threshold duplication. |
| Persistence & migrations | **4** | 6.5 | C3 boot-wipe and H2 CLI drift are M26; H1 upsert hole and `:memory:` threading predate it. |
| API & auth | **3** | 7 | C1 backdoor + C4 fabricated-field regression are uncommitted post-M26 edits. Underlying design is sound. |
| Services & voice | **5** | 5 | Contracts match exactly; container is missing deps and mounts, unauthenticated, vacuous healthcheck. |
| Infra / CI / deployability | **5** | 6 | Render path coherent, CI real. Oracle half not deployable as written; config drift after M26. |
| Tests | **6** | 7 | 336 pass; the 8 red ones are correctly catching a real regression — the suite did its job. Gaps in the contract suite. |
| **Overall** | **5.5** | **7.5** | |

"Is it 100% properly wired up?" — No, not today. The wiring **was** essentially complete at Module 25; the four items above broke it. After fixing them it will be, with H1–H7 as the next tier.

---

## Recommendations, in order

**Do today, before anything else:**
1. **Rotate the Supabase service-role key** (Supabase dashboard → Project Settings → API → regenerate). Then delete line 5 of `mobile/src/config.ts` and use the anon key.
2. **Discard the uncommitted backend edits** (`session_auth.py`, `value_endpoints.py`) — `git checkout -- src/agro_mirai/api/session_auth.py src/agro_mirai/api/value_endpoints.py` — and confirm the 8 red tests go green. Have Claude Code do this and show you `git status` before and after.

**Then the revert you already asked for — do it as Module 27, properly:**
3. `git revert dc97804` (Module 26 is one commit; nothing after it touched those files except the uncommitted edits you're discarding). That restores bcrypt + signed-session `/v2/auth/*`, `password_hash`, the login rate limiter, the old `openapi.yaml`, and — as a side effect — **fixes C3** (the 004 migration disappears) and moots H4.
4. The revert does **not** un-migrate the live Supabase Postgres (password_hash was dropped, farmers wiped, FK to `auth.users` added). Claude Code needs a `005_revert_supabase_auth.sql` (or a clean `supabase db reset` from a regenerated `supabase/migrations/` — which also fixes H2 in the same stroke).
5. ADR 0023 documenting *why* you reverted (Supabase Auth was tried, it worked, and you chose the self-owned auth for the capstone), so the history reads as a decision, not a flip-flop. Update `PROGRESS.md`, `CLAUDE.md`'s "Current phase," `render.yaml` (remove dead vars, restore `LOGIN_RATE_LIMIT`), `.env.example`.

**Next tier (Module 28, "hardening"), roughly one session:**
6. H1 — scope upserts by `farmer_id` in both stores, add a cross-tenant write test to the contract suite.
7. H6 — persist/read `out_of_region`/`regional_alternative`.
8. H5 — key the general limiter on the verified identity post-auth (else IP); refuse `CORS_ORIGINS="*"` when credentials are on; note per-worker limits.
9. H3 — fix the voice container (`requirements.txt`, mount `models/voice`, real healthcheck) and add a shared-secret header + per-IP limit to both Oracle services (`cnn_client.py`/`remote_voice.py` send it).
10. H7, the `:memory:` threading fix, `RemoteVoiceService` KeyError catch, `MAX_CONTENT_LENGTH`, name/area bounds, SHAP explainer caching.

---

## On Artemis (github.com/google/artemis)

Verified, and it's a real fit for what you described: Google's Pixel Test Engineering team's AI-driven Android automation platform. It drives a **real phone over USB (ADB) or an emulator**, takes natural-language instructions, exposes itself over **MCP so Claude Code can call it directly**, and claims 99%+ on the AndroidWorld benchmark. Install is `.\start.bat` on Windows (auto-installs ADB, scrcpy, FFmpeg, Python via `uv`), then a web console at `localhost:8000`. Needs Python 3.12+, USB debugging on the phone, Apache-2.0, ~1.4k stars, actively maintained. Two modes: Flash (fast/cheap) and Pro (plans + safety verification). This gives Claude Code the "test the real app on my real phone" loop you want — the missing piece was never the model, it was a way for the agent to see and tap the screen.

Sequence I'd suggest: fix C1–C4 and do the revert first (so Claude Code is testing a backend that's actually correct), *then* install Artemis and point Claude Code at the phone. Testing the current working tree on a real device would just be exercising the backdoor.

## On the Antigravity → Claude Code switch

The evidence in this audit supports the switch on the merits: every critical finding in the working tree (C1, C2, C4, the fake `/v2/advisories` route, the LAN IP, the 2,603-line `App.tsx`) came from the Antigravity session, and two of them were the *backend* being edited to fit the app rather than the app being built to the frozen contract. Claude Code operating under `CLAUDE.md`'s doctrine — contract-first, additive-only, nothing hand-faked — is the discipline that produced the 7.5/10 backend in the first place. The `mobile/` directory should be treated as a design reference (the Stitch screens and the three-zone home are worth keeping) and rebuilt, not patched.
