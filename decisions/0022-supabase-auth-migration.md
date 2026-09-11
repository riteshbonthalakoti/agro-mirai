# ADR 0022 — Migrate `/v2` auth from custom sessions to Supabase Auth

**Status:** accepted
**Date:** 2026-09-11
**Module:** 26 — Migrate `/v2` auth from custom Flask sessions to Supabase Auth
**Supersedes:** decisions/0017-multi-tenant-v2.md §3 ("Auth: bcrypt + Flask
signed session, not JWT/OAuth/hand-rolled") and §2's role note. ADR 0017's
other sections (data model rationale, admin-surface scope, `/v1` staying
frozen) are unaffected and still stand.

## Context

ADR 0017 deliberately chose bcrypt + a Flask signed session cookie over
JWT/OAuth for Module 19, reasoning that a hand-rolled session was
"simpler" for a single-process, free-tier deploy with no multi-worker
session-affinity problem. That reasoning held for a web-only frontend.
It stopped holding once Module 23-25 built a real `/v2` client-facing
surface (value endpoints, voice API) and a separately-built React
Native/Expo mobile app (the Antigravity build) started depending on it:
a signed cookie is fundamentally a browser primitive, awkward for a
mobile client to store/attach correctly, offers no built-in refresh-token
flow, and every credential (registration validation, password hashing,
session expiry) was hand-maintained code this project has to keep
secure itself. Supabase Auth (GoTrue) was already a live dependency of
this project (`SupabaseDataStore`, Module 04) for data — but never for
auth. This migration closes that gap: real auth infrastructure instead
of a hand-rolled one, using the same Supabase project this project
already provisions.

This is a genuine breaking change to the `/v2` contract, not an additive
module — treated with the same "frozen contract, deliberate break"
seriousness Module 23 applied to freezing `openapi.yaml` in the first
place.

## Decision

### 1. Direct-SDK-from-mobile, not Flask-as-auth-proxy

Confirmed with Ritesh before implementation (per this module's own
"stop and report" requirement). The mobile app talks to Supabase Auth
**directly** via the Supabase JS/RN SDK — registration, login, token
refresh, and logout all happen client-side against Supabase, never
through Flask. Flask becomes a pure **resource server**: every `/v2`
route now verifies an incoming `Authorization: Bearer <JWT>` and trusts
its `sub` claim as the farmer id.

Reasoning:

- This is what Supabase Auth is built for — fighting that model by
  proxying every auth call through Flask would mean re-implementing
  Supabase's own registration/login/refresh/logout logic a second time,
  for no functional gain.
- Less code to maintain on the Flask side. `POST /v2/auth/register`,
  `/v2/auth/login`, `/v2/auth/logout`, `agro_mirai/auth/password.py`,
  `agro_mirai/api/session_auth.py`'s old cookie-issuing logic, and
  `agro_mirai/api/login_rate_limit.py` are all deleted, not kept
  alongside the new path (see §3).
- No project-specific reason argued for keeping Flask in the loop.
  Module 19's login rate limiter (5/min) is superseded by Supabase
  Auth's own built-in abuse protection on its auth endpoints — not
  reimplemented. The mobile app's offline-queue retry logic (built
  separately for `/v2` value-endpoint calls) treats authentication as a
  precondition to have before a request is queued, not something it
  retries through, so it needs no change for this migration.

### 2. JWT verification: direct PyJWT decode against JWKS, not the
   `supabase-py` SDK's `auth.get_user(token)`

`agro_mirai/api/jwt_auth.py` verifies tokens locally via `PyJWT` +
`PyJWKClient` against this project's live JWKS endpoint
(`https://yzsemdauwafxssaknlzr.supabase.co/auth/v1/.well-known/jwks.json`,
confirmed live and populated with a real ES256 key during this module's
investigation — this project's Supabase instance uses the current
asymmetric signing-key default, not the legacy HS256 shared secret). A
`SUPABASE_JWT_SECRET`-based HS256 fallback path exists for robustness
(a project on the legacy signing key would need it) but is not this
project's actual configuration.

Local JWKS-based verification was chosen over calling
`supabase-py`'s `auth.get_user(token)` because the latter is a network
round trip to Supabase on **every single authenticated request** — for
an API that authenticates every `/v2` call, that is a real latency and
availability cost the local-verification approach avoids entirely after
its one-time (cached) JWKS fetch.

`role` is read from the verified token's `app_metadata.role` claim,
**never** `user_metadata` — `app_metadata` is server-side-writable only
(via the Supabase Admin API), while `user_metadata` a signed-up user can
write to themselves via the SDK. Trusting the wrong one would let any
farmer mint themselves an admin token client-side. Provisioning an admin
account is still the same out-of-band step ADR 0017 established (no
self-service "become admin" endpoint exists) — it now means setting
`app_metadata.role = "admin"` on the Supabase user via the Admin API
instead of flipping a `Farmer.role` column via the `DataStore`.
`Farmer.role` is kept as a column (display-only, shown in the admin
farmer listing) but is **not** the authorization source of truth any
more — every `/v2` authorization check reads `g.role` from the verified
token on each request, not the stored row, so a role change takes effect
on that user's very next token without any `Farmer` row update needed.

### 3. `farmers.id` IS `auth.users.id` — no separate mapping column

Rather than adding a new `auth_id`/`user_id` column and a lookup step,
`Farmer.id` now **is** the Supabase-issued `auth.users.id` for every
farmer registered from this migration forward. This was possible only
because of the clean-slate reset (§5) — there were no existing rows
whose primary key needed to be reconciled with a Supabase id after the
fact. Consequences:

- Every existing foreign key that already points at `Farmer.id`
  (`Field.farmer_id`, and everything that cascades from a Field) needed
  **zero** schema changes — the re-keying is free.
- `migrations/postgres/004_supabase_auth.sql` adds a real
  `FOREIGN KEY (id) REFERENCES auth.users(id) ON DELETE CASCADE`
  constraint on `farmers.id`, enforced by Postgres itself. Deleting a
  Supabase user now automatically cleans up their farmer profile (and
  everything that cascades from it) — a real integrity guarantee this
  project didn't have before, not just an application-level convention.
  (SQLite has no `auth.users` table to reference, so the SQLite twin of
  this migration only drops `password_hash`, no FK.)
- There is no explicit "create my profile" API call. Flask
  auto-provisions a `Farmer` row (`session_auth._ensure_farmer_profile`)
  on the first authenticated `/v2` request from a Supabase user id it
  hasn't seen before, defaulting `name` from the token's email local-part
  and `preferred_language` to `"en"`. `PATCH /v2/farmers/me` remains how
  a farmer sets their real name/language afterward — unchanged from
  Module 19.

### 4. `password_hash` and the old session machinery: removed, not
   left half-wired

Per this module's explicit instruction, dead code was deleted rather
than kept dormant alongside the new path:

- `Farmer.password_hash` — removed from the dataclass, `schema.yaml`,
  both `DataStore` implementations, and the `farmers` table (migration
  below).
- `src/agro_mirai/auth/password.py` (bcrypt hash/verify) — deleted.
  `bcrypt` dropped from `requirements.txt`, replaced by `PyJWT` (already
  a transitive dependency of `supabase-py`, now a direct one).
- `src/agro_mirai/auth/validation.py`'s `validate_email`/
  `validate_password_strength` — deleted (Supabase Auth enforces its own
  password policy now; only `validate_name` survives, still used by
  `PATCH /v2/farmers/me`).
- `src/agro_mirai/api/routes/auth_v2.py` (the `/v2/auth/register|login|
  logout` blueprint) — deleted entirely.
- `src/agro_mirai/api/login_rate_limit.py` — deleted (superseded by
  Supabase Auth's own rate limiting, per §1).
- `session_auth.py`'s old `issue_session`/cookie-based
  `require_session_auth`/`require_admin` — replaced with JWT-verifying
  versions of the same two decorator names (call sites in
  `farms_v2.py`/`value_v2.py`/`voice_v2.py`/`admin.py`/`admin_ui.py`
  needed **zero** changes beyond ownership plumbing already keyed off
  `g.farmer_id`, since the decorator contract — "set `g.farmer_id`/
  `g.role`, raise 401 otherwise" — was kept identical on purpose to
  minimize route-level churn).

One session-cookie consumer survives deliberately: the server-rendered
`/admin` browser dashboard (`routes/admin_ui.py`, Module 19's read-only
Jinja2 UI) has no SDK of its own to hold a token in JS state between
page loads. Its login form now makes a **server-side** call to Supabase
Auth's password grant (via the `supabase` Python client's
`auth.sign_in_with_password`, not a hand-rolled HTTP call), then stores
the resulting Supabase JWT inside Flask's own signed session cookie
purely as same-origin browser storage — the token itself is still
verified through the exact same `jwt_auth.verify_token` every `/v2` API
call uses. This is not the old auth model resurrected: no password
hash, no custom credential check, and no cookie is ever accepted by the
`/v2` JSON API — only by `/admin`'s own routes.

Session-cookie config (`SESSION_COOKIE_SAMESITE`/`SECURE`) was revisited
per this module's instruction: the cross-origin `SameSite=None`
configuration Module 19/24 added specifically for the (now-removed)
`/v2` cookie-based API auth was dead weight and was simplified to a
plain same-origin `Lax` cookie — `/admin` is same-origin (browser talks
to the same Flask process that set the cookie), so there is no
cross-origin delivery requirement left to solve for.

### 5. Data migration: clean-slate reset

Confirmed with Ritesh before implementation. Every existing farmer row's
`password_hash` became permanently unusable the moment Supabase Auth
became the credential store — a bcrypt hash cannot be reversed into a
plaintext password to re-register with Supabase. This project has only
seeded/test data at this stage (no real end users), so rather than a
more elaborate migrate-with-forced-reset flow, every existing farmer row
(and everything that cascades from it via `ON DELETE CASCADE` — fields,
advisories, feedback, etc.) was wiped as part of the migration itself.
Farmers (including the mobile app's already-registered test accounts)
re-register fresh through the Supabase SDK; Flask auto-provisions a
fresh profile on their first authenticated request (§3).

`migrations/sqlite/004_supabase_auth.sql` and
`migrations/postgres/004_supabase_auth.sql` both do the wipe + drop
`password_hash`; the Postgres twin additionally adds the `auth.users`
foreign key. The SQLite migration is applied automatically and
idempotently by `SQLiteDataStore._apply_supabase_auth_migration`
(guarded on whether `password_hash` still exists as a column — unlike
the ADD-COLUMN migrations before it, a blind re-run-every-boot approach
would be unsafe here since it contains a real `DELETE`). The Postgres
migration was applied for real, out-of-band, against this project's
live linked Supabase project (`yzsemdauwafxssaknlzr`) via
`supabase db query --file migrations/postgres/004_supabase_auth.sql
--linked` during this module's implementation — verified afterward by
querying `information_schema.columns` (no `password_hash`),
`pg_constraint` (the new FK present), and `SELECT count(*) FROM
farmers` (0 rows) directly against the live database, not assumed.

## Consequences

- `/v2` is now Supabase-JWT-bearer authenticated
  (`security: [{ supabaseAuth: [] }]` in `openapi.yaml`), not
  session-cookie authenticated. `/v2/auth/register`, `/v2/auth/login`,
  and `/v2/auth/logout` no longer exist in the contract at all —
  removed, not deprecated-but-present. `/v1` (Module 19's shared-`
  API_KEY` surface, ADR 0017) is completely untouched by this module and
  stays frozen exactly as before.
- Every `/v2` cross-tenant ownership check (`get_field`, `get_advisory`,
  etc.) is unchanged in its own logic — it was always farmer-id-scoped
  — but the `farmer_id` it now receives comes from a verified JWT's
  `sub` claim instead of a session dict, re-verified per-endpoint in
  `tests/api/test_v2_auth_integration.py` and
  `tests/api/test_v2_value_endpoints.py` (404-not-403-not-leaked on
  every route, the same standard Module 23 held).
- `Farmer.role` is now cosmetic/display-only in the database — the
  authorization source of truth moved entirely to the JWT's
  `app_metadata.role`, checked fresh on every request. This is a
  deliberate simplification (no stale-role-after-promotion bug is
  possible) but means an admin promotion is invisible until that user's
  *next* token — acceptable for this project's out-of-band admin
  provisioning flow, flagged here in case a future module wants
  instant-revocation semantics instead.
- Mobile app impact (Antigravity/React Native): registration, login,
  token refresh, and logout must be rebuilt against the Supabase JS/RN
  SDK directly instead of calling the removed `/v2/auth/*` endpoints;
  every authenticated `/v2` call must attach
  `Authorization: Bearer <supabase-session-access-token>` (the SDK's
  session object) instead of relying on cookie persistence. See the
  Module 26 handoff for the concrete before/after request shapes.
- Known limitation, not hidden: the two Oracle-hosted services from
  Module 21 (`services/cnn-inference`, `services/voice`) still have no
  authentication of their own — this migration did not touch that gap
  (ADR 0019 already flagged it as open).
