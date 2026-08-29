# ADR 0017 — Multi-tenant `/v2`: real login/session auth + read-only Admin

**Status:** accepted
**Date:** 2026-08-29
**Module:** 19 — Multi-tenant data model + real login/session auth + read-only Admin dashboard
**Supersedes:** ADR 0003 (single-farmer-per-account)

## Context

ADR 0003 locked a single-`Farmer`-per-account model for the original
15-module capstone scope, explicitly on the condition that reintroducing
multi-tenancy later "needs a new ADR and a new API version (`/v2`), not
a patch to `v1`." The production push (`docs/ROADMAP_PRODUCTION.md`,
workstream B) calls for real multiple farmers, a real login system
(not a token-in-a-cookie shortcut), and a read-only Admin surface. This
ADR is that superseding decision.

## Decision

### 1. `/v2`, not a v1 patch — and what happens to `/v1`

Every new multi-tenant route lives under `/v2` (`/v2/auth/*`,
`/v2/farmers/me`, `/v2/fields*`, `/v2/admin/*`), authenticated by a real
Flask signed session cookie instead of the single shared `API_KEY`.

**`/v1` stays alive, unmodified, single-tenant, for demo/backward-compat
continuity** — a deliberate decision, not an accident. `require_auth`
(`src/agro_mirai/api/auth.py`) is untouched; the shared `API_KEY` still
maps to the one `FARMER_ID` configured in the environment, exactly as
before. Reasons:

- The existing Module 14/14b web frontend, `MANUAL_TEST_GUIDE.md`, and
  `docs/DEMO_SCRIPT.md` all depend on the `/v1` single-shared-key flow
  working end to end for a live capstone review — retiring it mid-push
  would strand those.
- `/v1` and `/v2` touch disjoint route prefixes and disjoint auth
  decorators (`require_auth` vs. `session_auth.require_session_auth`),
  so there is no code path where a `/v1` request could be silently
  reinterpreted as `/v2`-authenticated or vice versa.
- The underlying `Farmer`/`Field`/... records are the same rows either
  way (one schema, additive fields only) — a `/v1`-created farmer has no
  `email`/`password_hash` and simply cannot log into `/v2`; a
  `/v2`-registered farmer can still be pointed at by `/v1`'s
  `FARMER_ID` env var if someone wants to demo through the old UI with a
  newly-registered account.

`/v1` is not the long-term multi-tenant surface — the roadmap's
intent is for `/v2` to eventually become primary once the frontend is
ported (a follow-up module, not this one) — but it is not deprecated or
frozen either; it is simply out of scope for this module's changes.

### 2. Data model: `role` field on `Farmer`, not a separate `AdminUser`

`Farmer` gained three additive fields: `email`, `password_hash`, `role`
(enum `user_role`: `farmer` | `admin`). A `role` field was chosen over a
separate `AdminUser` entity because:

- Every other domain record (`Field`, `CropRecommendation`, ...) already
  ties back to `Farmer.id`; an `AdminUser` would need its own auth path
  entirely disconnected from that graph, duplicating registration/
  session/password-hashing code for no behavioral gain in a read-only
  admin surface.
- The Admin surface never needs `Field`-shaped data of its own — it
  only *views* every farmer's data. An admin account owning zero fields
  is a natural, already-representable state (`list_fields(admin_id)`
  returns `[]`), not a schema special case.
- Tradeoff accepted: an admin account is also, structurally, a `Farmer`
  row (it could in principle own fields of its own, which no UI
  currently surfaces a reason to do). This is judged acceptable — it
  costs nothing today and avoids a second parallel identity system.

There is no self-service "become admin" endpoint. Provisioning an admin
account is an out-of-band step: register normally via `/v2/auth/
register`, then flip `role` to `admin` directly via the `DataStore`
(`tools/seed_fixture.py`-style script, or `SQLiteDataStore`/
`SupabaseDataStore` directly) — the same pattern the tests use. No admin
self-registration route exists, so a compromised registration endpoint
cannot mint an admin.

### 3. Auth: bcrypt + Flask signed session, not JWT/OAuth/hand-rolled

Password hashing: **bcrypt** (`agro_mirai/auth/password.py`), an
established KDF with a built-in per-hash salt — not
`sha256(password)`, not argon2 (both were acceptable per the module
spec; bcrypt was picked for a smaller, C-extension-only wheel with no
extra native toolchain requirement on this project's Windows dev
environment, and because this project's scale doesn't need argon2's
memory-hardness tuning).

Session: Flask's own signed cookie (`itsdangerous`, already a
transitive Flask dependency — no new session-store dependency). No
separate session store (Redis, a `sessions` table) was added: the
signed cookie is already tamper-proof, this project has no
server-side session revocation requirement beyond logout (which just
clears the cookie), and the single-process/free-tier Render deploy
(ADR 0014) has no multi-worker session-affinity problem to solve.
Expiry is enforced twice — Flask's own cookie `max-age`
(`PERMANENT_SESSION_LIFETIME`, 24h) and an explicit `issued_at`
timestamp checked on every request (`session_auth.is_expired`), the
latter existing specifically so expiry is unit-testable without forging
or waiting out a real signed cookie.

Rate limiting: `POST /v2/auth/login` carries its own Flask-Limiter
instance (`api/login_rate_limit.py`), default `5 per minute` keyed by
remote address, layered on top of Module 16's general per-API-key
`RATE_LIMIT`. It had to be a *separate* `Limiter` object, decorating the
view at import time rather than post-registration, because this
project's installed Flask-Limiter version does not honor `.limit(...)`
applied to an already-registered `app.view_functions[...]` entry
(verified directly — see the commit history for Module 19's test/fix).

### 4. Admin surface: read-only, three routes, no write path

`/v2/admin/{farmers,fields,feedback}` (JSON) and `/admin` (server-
rendered Jinja2, same stack as the Module 14 frontend per ADR 0013,
minimally styled and labeled "functional, not yet polished"). Both
surfaces are gated by `session_auth.require_admin`. There is
deliberately no threshold/model-control route and no write route of any
kind — `tests/api/test_admin_routes.py` asserts this by inspecting
`app.url_map` directly rather than trusting the blueprint's docstring.
The feedback aggregate reuses Module 13's `FeedbackAggregator` unmodified
against a new, deliberately unscoped `DataStore.list_all_feedback_with_advisories`
method — see `specs/core/repository-interface.md`'s design-rule-3
addendum for why this is the one documented exception to "every method
takes a `farmer_id`."

## Consequences

- Two live, parallel auth systems (`/v1` shared-key, `/v2` session) —
  more surface area, but each is independently simple and neither can
  be confused for the other at the routing layer.
- `Farmer` now carries auth material; every serializer that returns a
  `Farmer` must go through `farmer_to_public_json` (strips
  `password_hash`), never raw `to_json` — this is enforced by having
  used it everywhere `Farmer` is returned, not by a schema constraint.
- Cross-tenant isolation is proven by an integration test that actually
  registers two farmers, logs each in, and confirms field-level 404s
  across accounts — not assumed from `store.get_field`'s farmer-scoped
  `WHERE` clause alone.
- If the project later wants `/v2` to become the frontend's primary
  auth path, that is a follow-up module's decision, not implied by this
  ADR.
