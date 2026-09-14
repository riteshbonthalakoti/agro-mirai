# MODULE 19 — Multi-tenant data model + real login/session auth + read-only Admin dashboard

Continuing AGRO MIRAI in the existing `agro-mirai` repo. Modules 01–18
are done (`fff78ae` on `origin/main`). Read `CLAUDE.md`, `PROGRESS.md`,
`docs/ROADMAP_PRODUCTION.md`, `decisions/0003-*.md` (single-farmer
ownership model), and `src/agro_mirai/api/auth.py` (current single
shared `API_KEY` → single `FARMER_ID`) first. This is the biggest
module in the production push — real scope, take it seriously, several
sessions' worth of commits is expected, not one sitting.

**This module explicitly supersedes ADR 0003.** ADR 0003 itself says:
*"No later module may reintroduce a multi-tenant abstraction without a
superseding ADR"* and *"it needs a new ADR and a new API version (/v2),
not a patch to v1."* Follow that instruction literally — write
`decisions/0017-multi-tenant-v2.md` (or next-free number) that
explicitly supersedes 0003, and version the new multi-tenant surface
under `/v2` rather than silently mutating the existing `/v1`-equivalent
routes other modules and the demo/report depend on. Decide and document
whether `/v1` (today's single-shared-key routes) stays alive
unauthenticated-single-tenant for backward compat/demo continuity, or is
retired — don't let this happen by accident either way.

Confirm `git config user.name`/`user.email`. Many focused commits across
the three sub-areas below, not one giant one — this is exactly the kind
of module where commit discipline matters for reviewability.

## Decided scope (per Ritesh)

- **Admin surface: read-only.** List all farmers/fields, view
  system-wide feedback aggregates. NOT adjustable advisory-rule
  thresholds or any live model-behavior control — that's explicitly out
  of scope for this module.
- **Auth: a real login/session system**, not per-farmer API keys.
  Ritesh chose this explicitly, understanding it's more work than the
  simpler alternative — build it properly (password hashing, session
  management, real login/logout), not a token-in-a-cookie shortcut
  dressed up as a login system.

## Task

### 1. Data model (v2)
Extend the schema for real multi-farmer support:
- `Farmer` needs authentication fields (email, hashed password — never
  plaintext, use a real KDF like bcrypt/argon2 via an established
  library, not a hand-rolled hash) and a way to distinguish an Admin
  account from a regular farmer account (a `role` field, or a separate
  `AdminUser` entity — your call, document the tradeoff).
- Update `specs/core/schema.yaml` and `specs/core/enums.md` following
  the project's existing additive-and-documented discipline (see how
  the `/health` endpoint and Module 17/18 additive fields were done).
- Migration path for the existing `farm-001`/`farm-002` fixtures and
  any real seeded data — don't silently break `tools/seed_fixture.py`
  or the golden fixtures other tests depend on.
- `SQLiteDataStore` and `SupabaseDataStore` both need to implement
  whatever new repository methods multi-farmer auth requires (farmer
  lookup by email, credential verification) — check
  `specs/core/repository-interface.md` for where this belongs, update
  it as part of this module (it's a contract, not an afterthought).

### 2. Real login/session auth
- Registration (email + password, minimum viable validation — real
  password strength requirements, don't accept `"a"` as a password).
- Login endpoint issuing a session (Flask's signed session cookie is
  fine for this scale — don't over-engineer a separate session store
  unless you have a concrete reason to; if you do add one, justify it).
- Logout, and session expiry.
- `require_auth` (`src/agro_mirai/api/auth.py`) needs a `/v2` sibling
  (or a mode switch, your call) that authenticates via session instead
  of the shared `API_KEY`, and scopes every request to the
  authenticated farmer's own data — this is where ADR 0003's
  authorization rule ("a caller may only read or write records whose
  transitive owner is their own Farmer") gets enforced for real,
  per-farmer, instead of the current single-shared-identity shortcut.
- Rate-limit login attempts specifically (on top of Module 16's general
  API rate limiting) — brute-force protection on the auth endpoint is
  not optional.
- Document in `.env.example`/`render.yaml` whatever new config this
  needs (session secret key, etc. — check if `FLASK_SECRET_KEY` already
  covers this from Module 15's Procfile/render.yaml setup).

### 3. Read-only Admin dashboard
- An Admin role check (not a regular farmer) gating a small set of new
  routes/pages: list all farmers with basic field counts, list all
  fields, view feedback aggregates system-wide (reuse Module 13's
  `feedback/aggregator.py` logic, scoped to "all farmers" instead of
  one).
- Server-rendered (same Flask/Jinja2 pattern as the existing frontend,
  per ADR 0013) unless you have a concrete reason to diverge — keep it
  consistent with the existing UI stack rather than introducing a new
  one, even though the dedicated UI/UX phase comes later; this can be
  minimally styled, it just needs to work and be honestly labeled as
  "functional, not yet polished" if that's the case.
- No write actions from the admin surface in this module — genuinely
  read-only, per the decided scope above.

### 4. Backward compatibility / demo continuity
Be explicit about what happens to the existing single-farmer demo flow
(`FARMER_ID`/`API_KEY` env vars, `MANUAL_TEST_GUIDE.md`,
`docs/DEMO_SCRIPT.md`) — if `/v1` stays alive, confirm it still works
end to end; if it's retired or changed, update those docs so they don't
silently go stale and mislead the next person running through them
before a review.

## Tests

- Unit tests for password hashing/verification, session issuance/
  expiry, registration validation.
- Integration tests: register → login → access own data → cannot access
  another farmer's data (a real cross-tenant isolation test, not just
  "the happy path works") → logout → session invalidated.
- Admin route tests: non-admin gets 403, admin sees all farmers/fields,
  admin cannot mutate anything through these routes (confirm no write
  endpoints exist here, don't just trust the routing).
- Rate-limit test on the login endpoint specifically.
- Full regression pass (everything from Modules 01–18 still green),
  `check_specs.py`, CI green on a real push.

## Update doctrine

`CLAUDE.md`, `PROGRESS.md` (new module row — this one may warrant
sub-entries given its size), `docs/ROADMAP_PRODUCTION.md` (check off
workstream B), new ADR (supersedes 0003), commit and push.

## Definition of done
- [ ] New ADR supersedes 0003, documents `/v1` vs `/v2` decision
      explicitly
- [ ] Multi-farmer data model, both DataStore backends updated,
      repository-interface.md updated
- [ ] Real registration/login/logout/session auth, password hashing via
      an established library, login rate-limited
- [ ] Per-farmer data isolation enforced and tested (cross-tenant
      access genuinely blocked, not just assumed)
- [ ] Read-only Admin dashboard: farmers, fields, system-wide feedback
      aggregates — no write actions
- [ ] Existing demo flow's fate (kept alive or retired) is a documented
      decision, not an accident; docs updated to match
- [ ] Full regression + `check_specs.py` pass, CI green
- [ ] Pushed to `origin/main`

## Handoff format
```
Module: 19 — Multi-tenant + real auth + read-only Admin
Status: complete | blocked
ADR: <number>, supersedes 0003. /v1 decision: <kept alive as-is | retired | changed, and why>
Data model changes: <schema.yaml/enums.md diffs, migration approach for existing fixtures>
Auth: <hashing library, session mechanism, rate-limit config>
Cross-tenant isolation: <how it's enforced, how it's tested>
Admin dashboard: <routes, what's shown, confirmed read-only>
Files changed:
Commits made:
Tests: <new/updated counts, pass/fail>
Full regression: <pass/fail>
check_specs.py: pass/fail
Known limitations:
Next recommended module: 20 — CNN disease model (PlantVillage/MobileNet)
```
