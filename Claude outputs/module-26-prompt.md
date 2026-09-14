# MODULE 26 — Migrate /v2 auth from custom Flask sessions to Supabase Auth

Continuing AGRO MIRAI in the existing `agro-mirai` repo. Modules 01–25 are
done (`6553af4` on `origin/main` — confirm this yourself, my last fetch
attempt hit a network-level 403 from this machine's proxy, unrelated to
the repo). This is a real architecture migration, not an additive module:
it replaces the custom bcrypt+signed-session-cookie auth built in Module 19
and extended in Modules 23-25 with real Supabase Auth (GoTrue), using the
Supabase CLI throughout.

Read `CLAUDE.md`, `PROGRESS.md`, `decisions/0017-multi-tenant-v2.md` (why
custom session auth was chosen originally — understand what you're
replacing and why, before replacing it), `src/agro_mirai/api/session_auth.py`,
`src/agro_mirai/api/routes/auth_v2.py`, `src/agro_mirai/persistence/supabase_store.py`
(Supabase is already used as an optional `DataStore` backend — this module
is about using Supabase's *Auth* product too, not introducing Supabase to
the project for the first time), and `specs/core/openapi.yaml`'s current
`/v2/auth/*` paths first.

Confirm `git config user.name`/`user.email`. Confirm the Supabase CLI is
installed and authenticated (`supabase --version`, `supabase projects list`)
before writing any code — if it isn't, stop and tell me what setup step is
needed rather than working around it.

## Stop and report before executing the migration

This changes the frontend contract. Before touching code:

1. Confirm via `supabase` CLI which Supabase project this repo's
   `SUPABASE_URL`/`SUPABASE_KEY` already point to (`.env`), and whether
   Auth is already enabled on it or needs enabling.
2. Decide and report back on **one specific question**: does the mobile
   app talk to Supabase Auth *directly* (via the Supabase JS/RN SDK,
   getting a session/JWT straight from Supabase, with Flask only verifying
   that JWT on incoming `/v2` requests), or does the app keep talking to
   Flask's `/v2/auth/*` endpoints and Flask proxies to Supabase Auth under
   the hood? Recommend direct-SDK-from-mobile (it's what Supabase Auth is
   built for, and it's less code to maintain on the Flask side — Flask
   becomes a resource server, not an auth server) but confirm there's no
   reason specific to this project's rate-limiting/offline design (the
   login 5/min limiter, the offline-queue retry logic already built into
   the mobile app) that argues for keeping Flask in the loop. Report your
   recommendation and reasoning before implementing either way — I want
   to confirm this before it's built, not after.
3. Confirm how existing farmer rows (the ones already in the `farmers`
   table with a bcrypt `password_hash`) get migrated — there is real
   seeded/test data and potentially the mobile app's already-registered
   test farmers. A clean-slate reset is acceptable for a capstone project
   at this stage (say so if you think that's right) but state it
   explicitly rather than silently dropping data.

## The migration itself, once the above is confirmed

- Enable Supabase Auth on the project via the CLI; configure email/password
  as the auth method (matches what's already built — no need to add
  magic-link/OAuth providers unless you have a reason to).
- `farmers` table: add/repoint a `user_id` (or `auth_id`) column as a
  foreign key to `auth.users.id`; the `password_hash` column and any
  custom session-cookie-signing logic in `session_auth.py` becomes dead
  code to remove, not to leave half-wired alongside the new path.
- Flask side: replace `require_session_auth` with JWT verification against
  Supabase's JWKS/secret (the `supabase` Python SDK or a direct JWT
  decode — pick whichever is more maintainable, justify the choice).
  Ownership checks (`get_field`, `get_advisory`, etc.) re-key from the old
  `farmer_id` to the Supabase-issued user id — audit every place
  `farmer_id` currently comes from `g.farmer_id` via the old session
  mechanism and confirm it now comes from the verified JWT's `sub` claim.
- `POST /v2/auth/register` / `login` / `logout`: either become thin
  wrappers if Flask stays in the loop, or get removed from `openapi.yaml`
  in favor of documenting the direct-Supabase-SDK flow if the mobile app
  talks to Supabase directly — whichever was decided in the "stop and
  report" step above.
- CORS/session-cookie config (`SESSION_COOKIE_*`, `CORS_ORIGINS` from
  Module 24) gets revisited — a JWT-bearer-token model doesn't need
  cookie SameSite/Secure flags the way the old session model did; don't
  leave dead cookie config alongside the new token-based auth.
- `specs/core/openapi.yaml`: this is the breaking change the "frozen
  contract" doctrine exists to control — update it explicitly, and add a
  note in the ADR (below) that this is a deliberate contract break, not
  an additive change, with the old vs. new auth flow both described so
  Antigravity's already-built mobile auth screens have something concrete
  to update against.

## Tests

- Every existing `/v2` auth/session/ownership test needs to be rewritten
  against the new JWT-based auth, not just left pointing at removed code.
- New tests: real Supabase Auth registration/login round trip (against a
  real or properly mocked Supabase Auth endpoint — state which), JWT
  rejection on tampered/expired tokens, ownership checks re-verified
  cross-tenant (404-not-403, the same standard every prior module held).
- Full regression pass. This will likely be the largest test-count change
  of any module so far given how much of `/v2`'s test suite assumes the
  old auth mechanism — that's expected, report the real before/after
  numbers honestly rather than a suspiciously-unchanged count.
- `check_specs.py` pass.

## Update doctrine

`CLAUDE.md`, `PROGRESS.md` (new module row, flagged clearly as a breaking
migration, not a feature add), `decisions/0022-supabase-auth-migration.md`
(or next available number) documenting: why the switch, what was removed,
the direct-SDK-vs-Flask-proxy decision and reasoning, the data-migration
approach, and explicitly what changes for the mobile app team (you) as a
result. No `Co-Authored-By` line in commits — this is the standing rule;
if you're unsure it still holds, ask rather than defaulting to adding one.

## Definition of done

- [ ] Direct-SDK-vs-Flask-proxy decision confirmed with me before
      implementation, not decided unilaterally
- [ ] Supabase Auth genuinely enabled and verified via the CLI, not assumed
- [ ] `farmers` table re-keyed to `auth.users.id`, old password/session
      code fully removed (not left dead alongside the new path)
- [ ] Every `/v2` ownership check re-verified cross-tenant safe under the
      new auth (404-not-403, per-endpoint, the same standard as Module 23)
- [ ] `openapi.yaml` updated to reflect the real breaking change, with the
      old flow's removal explicit, not silently dropped
- [ ] Full regression suite rewritten and passing, real numbers reported
- [ ] `check_specs.py` pass
- [ ] ADR documents the decision, the migration, and mobile-app impact
- [ ] Pushed to `origin/main`

## Handoff format

```
Module: 26 — Migrate /v2 auth to Supabase Auth
Status: complete | blocked | needs-decision (specify what's blocking)
Direct-SDK vs Flask-proxy decision: <which, and why>
Data migration approach: <what happened to existing farmer rows>
Changes made: <files>
Auth flow before vs after: <concrete before/after, for the mobile team>
Tests: <new/updated/removed, pass/fail, real counts>
Full regression: <pass/fail>
check_specs.py: pass/fail
Known limitations:
Mobile app impact — what Antigravity/the mobile auth screens need to change:
Next recommended step:
```
