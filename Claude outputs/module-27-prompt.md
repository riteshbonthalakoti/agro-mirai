# MODULE 27 — Discard the Antigravity backend regressions, revert Module 26 (Supabase Auth), restore bcrypt+session auth

Continuing AGRO MIRAI in the existing `agro-mirai` repo. This follows a full
independent audit (227 files, every module re-verified against the live
repo, findings reproduced with standalone scripts, not taken on trust) that
found two uncommitted regressions introduced by a parallel Antigravity
mobile session, on top of Module 26's Supabase Auth migration, which Ritesh
has decided to revert. Read this whole prompt before touching anything —
it's sequenced deliberately: discard first, verify, revert second, verify
again.

## Context you need before starting

- `decisions/0022-supabase-auth-migration.md` — what Module 26 did and why.
- `git log --oneline -20` and `git show dc97804 --stat` — confirm this is
  the exact commit that migrated `/v2` auth to Supabase Auth. If the hash
  has changed or doesn't match a Supabase-Auth-migration commit, STOP and
  report — do not guess which commit to revert.
- `git status` and `git diff` — before doing anything else, capture the
  current uncommitted diff in full and show it to Ritesh in your first
  report back. Do not discard anything until you've shown what's being
  thrown away.

## Step 0 — Rotate the leaked key (tell Ritesh, don't do it yourself)

`mobile/src/config.ts` currently ships the Supabase **service-role** key,
not the anon key — full DB admin, no RLS. This needs to be rotated in the
Supabase dashboard (Project Settings → API → regenerate service role key)
by a human, before or during this module. If Ritesh hasn't confirmed he's
done this, remind him explicitly in your first response — don't proceed
past Step 3 (anything that touches live Supabase) until he confirms the
rotation, since the old key stays valid until it's regenerated.

## Step 1 — Discard the two uncommitted regressions

Confirm both of these are genuinely uncommitted (`git diff` / `git status`
against `HEAD`) before touching them:

1. `src/agro_mirai/api/session_auth.py` — contains an undocumented
   `if token.startswith("demo_")` branch (around lines 99-100) that skips
   JWT verification entirely and hardcodes a farmer id. This has no place
   in the backend regardless of the Module 26 revert below — it's a
   security backdoor, not a feature to preserve or migrate forward.
2. `src/agro_mirai/api/value_endpoints.py` — `get_field_or_404` (around
   lines 36-56) no longer raises 404 on a missing/cross-tenant field; it
   fabricates a fake `Field_` ("North Field", cotton, made-up coords)
   instead. This breaks tenant isolation and causes 500s or fabricated 200
   responses downstream.

Run `git checkout -- src/agro_mirai/api/session_auth.py src/agro_mirai/api/value_endpoints.py`
(or the equivalent for whatever these files' committed state actually is —
confirm neither file has *other* legitimate uncommitted changes mixed in
first; if it does, hand-edit instead of blanket-checkout so nothing good
gets lost).

**Verify, don't assume**: run the full test suite and confirm these
previously-red tests now pass:
`test_recommendation_cross_tenant_404`, `test_irrigation_cross_tenant_404`,
`test_disease_risk_cross_tenant_404`, `test_disease_risk_image_cross_tenant_404`,
`test_advisories_cross_tenant_404`, `test_unknown_field_404`,
`test_unknown_field_id_returns_404_not_500`,
`test_recommendation_unknown_field_returns_404`. Report the real before/
after pass count, not just "tests pass."

Also grep the whole repo for `demo_` and `"North Field"` to confirm no
other trace of either regression exists (e.g. a test that was quietly
updated to expect the fabricated behavior — if you find one, that test is
wrong and should be reverted to its pre-regression assertion, not kept).

## Step 2 — Revert Module 26 itself

Once Step 1 is clean and verified:

```
git revert dc97804
```

This should restore: bcrypt password hashing, Flask signed-session cookies,
`POST /v2/auth/register|login|logout`, the `password_hash` column, the
login rate limiter as it existed pre-Module-26, and the pre-Module-26
`openapi.yaml`. If the revert conflicts (likely, since Module 26 touched
many of the same files Modules 23/25 also touched), resolve conflicts by
keeping every Module 23/25 change (value_endpoints sharing, language
expansion) and only removing the Supabase-Auth-specific pieces — do not
resolve by mechanically taking "theirs" or "ours"; read each conflict.

Confirm afterward, by reading the actual files, not by trusting the merge:
- `session_auth.py` has real `require_session_auth`/`require_admin` back,
  no JWT/JWKS code, no `demo_` backdoor (it shouldn't have survived Step 1,
  but check again — a revert can resurrect deleted-then-reintroduced code
  in confusing ways).
- `jwt_auth.py` and any other Module-26-only file is removed, not left
  dead alongside the restored session code.
- `specs/core/openapi.yaml` matches the pre-Module-26 `/v2/auth/*` shape.

## Step 3 — Reverse the live Supabase migration

The code revert does **not** undo what actually happened to the live
Supabase Postgres project (`yzsemdauwafxssaknlzr`) when Module 26 ran:
`password_hash` was dropped, farmers were wiped in a clean-slate reset, and
a FK to `auth.users.id` was added. Confirm Step 0's key rotation is done
before touching this project.

- Write `migrations/postgres/005_revert_supabase_auth.sql`: re-add
  `password_hash` (nullable is fine, no data to backfill), drop the FK to
  `auth.users.id`, drop whatever Module 26 added that has no pre-existing
  analog. Mirror it for SQLite if SQLite's migration chain also needs a
  reverse step (check `_apply_supabase_auth_migration` in
  `sqlite_store.py` — this is also where the boot-time farmer-wipe bug
  lived, so confirm this whole code path is gone after the revert, not
  just dormant).
- Regenerate `supabase/migrations/` via the Supabase CLI so it actually
  matches what's applied (`supabase db diff`/`supabase migration new` —
  whatever the CLI's real workflow is; this closes the CLI-drift gap the
  audit found, where the CLI migrations directory had no 002/003/004 files
  at all, violating the project's own CLI-first rule).
- Apply it against the real project via the CLI and confirm via
  `supabase db diff` (or an equivalent live check) that the schema now
  matches the reverted code's expectations. Do not simulate this — this is
  exactly the kind of external-service step `CLAUDE.md`'s "nothing is
  hand-faked" rule exists for. If applying it requires interactive auth
  Ritesh hasn't done yet, stop and tell him the exact command and what
  it'll ask for.
- Existing farmers created under Supabase Auth (if any beyond test data)
  will not have a `password_hash` and cannot log in under the restored
  scheme — confirm with Ritesh whether any real farmer accounts exist that
  need re-registration, or whether this is still test/seed data only
  (Module 26's original migration was itself a clean-slate reset, so this
  is likely just seed fixtures).

## Step 4 — Doctrine

- `decisions/0023-revert-supabase-auth.md`: document this as a considered
  decision, not a flip-flop — Supabase Auth was tried, implemented
  correctly on its own terms (note the audit found the JWT algorithm
  handling, JWKS/HS256 split, and role-sourcing were all done right), but
  reverted because [state Ritesh's actual reasoning — capstone scope,
  wanting the self-owned auth system Claude Code originally built and
  fully controls, whatever he confirms]. Link back to
  `decisions/0022-supabase-auth-migration.md` rather than deleting it.
- `PROGRESS.md`: new Module 27 row.
- `CLAUDE.md`'s "Current phase" paragraph: update to reflect that `/v2`
  auth is back to bcrypt+session, Supabase Auth was tried and reverted,
  and Supabase remains available only as an optional `DataStore` backend
  (its original pre-Module-26 role), not as an auth provider.
- `render.yaml`: remove Module-26-only env vars (`SUPABASE_JWT_SECRET`,
  anything JWKS-related) that now do nothing; restore/confirm
  `LOGIN_RATE_LIMIT` and `SESSION_COOKIE_SAMESITE` are both present and
  actually read by the restored code (the audit found these present in
  `render.yaml` but read by nothing — confirm that's fixed, not just
  re-added cosmetically).
- `.env.example`: same cleanup.

## Tests

- Full regression suite. Report real before/after counts (the audit's
  last clean baseline was 374 passed / 25 skipped / 0 failed at Module 25
  — reconcile against that, don't just report a number in isolation).
- `check_specs.py` — must pass, against **both** `farm-001` and
  `farm-002` (the audit found CI only ever exercises farm-001 by default;
  if that's still true, note it as a known gap rather than silently
  leaving it).
- Add the two tests the audit found missing: a cross-tenant **write**
  test for `save_field` (farmer B cannot overwrite farmer A's field by id
  — this was H1 in the audit, a latent hole in both `sqlite_store.py` and
  `supabase_store.py` unrelated to the Module 26 revert, but cheap to
  close now while you're in this code) and a duplicate-registration/
  cascade-delete test if neither currently exists for the restored
  `/v2/auth/register` path.

## Definition of done

- [ ] Full uncommitted diff shown to Ritesh before anything was discarded
- [ ] Service-role key rotation confirmed by Ritesh before Step 3
- [ ] `session_auth.py` backdoor and `value_endpoints.py` fabricated-field
      regression both confirmed gone, all 8 previously-red cross-tenant/
      404 tests passing
- [ ] `git revert dc97804` completed, conflicts resolved by reading each
      one (not mechanical ours/theirs), verified by reading the resulting
      files
- [ ] Live Supabase Postgres schema reversed via a real CLI-applied
      migration, verified via `supabase db diff` or equivalent — not
      simulated
- [ ] `supabase/migrations/` regenerated so the CLI directory matches
      what's actually applied (closes the CLI-drift gap)
- [ ] ADR 0023 written, `PROGRESS.md`/`CLAUDE.md`/`render.yaml`/
      `.env.example` updated
- [ ] Full regression suite passing, real counts reported against the
      374/25/0 Module 25 baseline
- [ ] `check_specs.py` passes against both fixtures
- [ ] New cross-tenant write test added and passing
- [ ] Pushed to `origin/main`

## Handoff format

```
Module: 27 — Discard Antigravity regressions, revert Module 26, restore bcrypt+session auth
Status: complete | blocked | needs-decision (specify what's blocking)
Uncommitted diff discarded: <confirm shown to Ritesh first, what was in it>
Service-role key rotation: confirmed by Ritesh? <yes/no — do not proceed past Step 3 if no>
8 previously-red tests: <before/after status, each one>
Revert conflicts encountered and how resolved:
Live Supabase migration: <what was run, via which CLI command, verified how>
Tests: <new/updated, pass/fail, real counts vs 374/25/0 baseline>
check_specs.py: pass/fail, both fixtures?
New cross-tenant write test: added, passing?
Known limitations:
Next recommended step: <Module 28 hardening tier, and/or Artemis install for phone testing>
```
