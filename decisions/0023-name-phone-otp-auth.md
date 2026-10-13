# 0023 — Name+Phone+OTP auth replaces email+password (and the reverted Supabase Auth)

Date: 2026-09-12
Status: accepted

## Context

Module 26 migrated `/v2` auth from Module 19's bcrypt+signed-session
email+password scheme to real Supabase Auth (direct-SDK-from-mobile,
Flask as a pure JWT-verifying resource server). A separate, parallel
Antigravity mobile session then introduced two undocumented regressions
on top of that migration — an `if token.startswith("demo_")` backdoor in
`session_auth.py` that skipped verification entirely, and a
`get_field_or_404` change in `value_endpoints.py` that fabricated a fake
"North Field" instead of 404ing on a missing/cross-tenant field. Both
were discarded (never committed) — see the Module 27 commit history.

Separately, and unprompted by either of those regressions, Ritesh
decided he wants auth to stay fully self-owned rather than depend on
Supabase Auth, and — since farmers in this project are identified by
name and phone rather than email — wants the simplest possible farmer
auth: enter name + phone, receive an OTP, enter it back to log in. No
password to remember or type on a phone in a field.

## Decision

1. **Revert Module 26 entirely** (`git revert dc97804`). Farmer auth is
   fully self-owned again — no dependency on Supabase Auth, JWKS, or any
   external identity provider. Supabase remains available only as an
   optional `DataStore` backend (its original, pre-Module-26 role), not
   as an auth provider. See the Module 27 revert commit for what this
   restored.

2. **Replace the restored email+password farmer auth with Name+Phone+OTP**
   (this module, on top of the revert):
   - `POST /v2/auth/request-otp {phone, name?, preferred_language?}` —
     finds-or-creates the Farmer by phone (name required only the first
     time a phone is seen), generates a 6-digit code
     (`agro_mirai.auth.otp.OtpStore`), and "sends" it — today, only by
     writing it to the server's own log output via `logging`
     (`send_otp`). No SMS provider is wired up. This is a stated,
     deliberate dev/demo posture, not an oversight: at this project's
     current stage (capstone, pre-production, the person running the
     server can read its own terminal), reading the OTP off the server
     logs is a perfectly workable way to test the flow, and pretending
     an SMS was sent when none was would violate CLAUDE.md's "nothing is
     hand-faked" rule. `send_otp(phone, code)` is the one seam a real
     provider (Twilio Verify, etc.) plugs into later without touching
     `request-otp`/`verify-otp`'s calling code.
   - `POST /v2/auth/verify-otp {phone, otp}` — checks the code against
     `OtpStore.verify` (one-shot: a correct or attempts-exhausted check
     consumes the pending code; a wrong-but-not-yet-exhausted guess does
     not, so a mistyped digit doesn't force a fresh OTP request) and, on
     success, issues the same signed Flask session
     (`agro_mirai.api.session_auth.issue_session`) every other `/v2`
     route already expects — zero changes needed to
     `require_session_auth`/`require_admin` or any downstream route.
   - `POST /v2/auth/logout` is unchanged.

3. **`OtpStore` is a process-local in-memory dict, not a DataStore table
   or Redis.** An OTP only needs to live for a few minutes
   (`OTP_TTL = 10 minutes`); persisting it to SQLite/Supabase would add
   schema and migration surface for a value that's fine to lose on
   restart. This carries the same single-process limitation the general
   per-key rate limiter already has (`api/app.py`'s
   `_configure_rate_limit` docstring) — a multi-worker deployment would
   need a shared store. Not a new risk class for this project, and not
   worth solving before this project actually runs multi-worker.

4. **`Farmer.phone` is now unique** (`migrations/{sqlite,postgres}/005_phone_unique.sql`,
   a partial unique index mirroring Module 19's `idx_farmers_email`
   pattern exactly) — `get_farmer_by_phone` must resolve to at most one
   farmer.

5. **The admin-account email+password login path is untouched.** Admin
   accounts are still provisioned out-of-band directly against the
   `DataStore` (`MANUAL_TEST_GUIDE.md` step 8) with a real bcrypt
   password, and still log in via `POST /admin/login` (the
   server-rendered dashboard, `api/routes/admin_ui.py`) — there was
   never a reason to put an OTP flow in front of a human who already has
   direct database access to create their own account. `bcrypt`,
   `agro_mirai/auth/password.py`, and `validate_email`/
   `validate_password_strength` all stay for this reason; they are no
   longer used by farmer self-registration.

6. **`OTP_RATE_LIMIT` replaces `LOGIN_RATE_LIMIT`** (env var renamed;
   `login_rate_limit.py`'s file name and `Limiter` instance are kept as
   the same object, just repurposed and renamed to
   `otp_request_limiter`, to avoid an unrelated import-path churn across
   the app-factory wiring) — it now guards `/v2/auth/request-otp`
   specifically, since spamming OTP requests (each one generates and
   logs a real code) is the equivalent risk password-guessing was for
   the old login route.

## Consequences

- Farmers never handle a password. The tradeoff: whoever can read the
  server's log output can log in as any farmer who has ever requested an
  OTP within the last `OTP_TTL` — acceptable at this project's current
  single-operator dev/demo stage, explicitly not acceptable once this
  ships to real farmers with a real SMS provider wired up. This is the
  next real gap, tracked as this module's known limitation below, not
  hidden.
- `Farmer.email`/`Farmer.password_hash` remain in the schema
  (`specs/core/schema.yaml`, additive, unchanged shape) but are now
  admin-only fields — a farmer record created via `/v2/auth` has neither
  set. This is a meaning change on an existing field's *usage*, not its
  *shape*, so no schema version bump.
- `specs/core/openapi.yaml`'s `/v2/auth/register` and `/v2/auth/login`
  paths are removed and replaced with `/v2/auth/request-otp` and
  `/v2/auth/verify-otp` — this is the second breaking change to this
  surface in two modules (Module 26 broke it once migrating to Supabase
  Auth; this reverts that and breaks it again moving to OTP). There is
  no external consumer of `/v2/auth/register|login` yet (frontend phase
  hadn't started before Module 26), so no real client is stranded by
  either break.

## Known limitations (stated, not hidden)

- **No SMS delivery.** `OTP_DELIVERY=log` is the only mode. Before real
  farmers use this, `send_otp` needs a real provider (Twilio Verify is
  the obvious candidate — this project's plugin set already includes
  Twilio skills) wired in behind the same function signature.
- **OTP brute-force surface is the request-otp rate limit only** — once
  a code is issued, `MAX_VERIFY_ATTEMPTS = 5` wrong guesses lock out that
  specific pending code (forcing a fresh `request-otp` call), but there
  is no rate limit on `verify-otp` itself distinct from the general
  per-key `RATE_LIMIT`. Acceptable at a 6-digit/10-minute/5-attempt
  combination for a dev/demo system; worth tightening (a dedicated
  verify-otp limiter, or shortening `OTP_TTL`) before production SMS
  delivery makes the attack surface real.
- **Single-process only** (see `OtpStore`'s docstring) — a multi-worker
  deployment needs a shared OTP store (Redis, or a DataStore table) as a
  prerequisite, same as the existing per-key rate limiter's own
  documented limitation.

## Links

- Supersedes: [0022-supabase-auth-migration.md](0022-supabase-auth-migration.md)
  (not deleted — see that file for what Module 26 did and why it was
  tried before being reverted).
- Extends: [0017-multi-tenant-v2.md](0017-multi-tenant-v2.md) (session
  mechanism, ownership enforcement — both unchanged by this module).
