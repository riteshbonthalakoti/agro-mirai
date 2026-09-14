# MODULE 16 — Reliability & CI Hardening (Production push, part 1 of 3)

Continuing AGRO MIRAI in the existing `agro-mirai` repo. Modules 01–15 are
done, tested, and deployed (`5bdf6aa` on `origin/main`). This starts a new,
explicitly non-academic-pace push: three back-to-back modules (16, 17, 18)
over the next few days to take the project from "capstone MVP" toward
"production grade." Read `CLAUDE.md`, `PROGRESS.md`, and the new
`docs/ROADMAP_PRODUCTION.md` first — the roadmap doc explains why this push
exists and what's coming in Modules 17 (multi-tenant + admin) and 18 (CNN
disease model), so you have the full context even though this module only
covers workstream A.

Confirm `git config user.name`/`user.email`. Same commit discipline as
prior modules: real, separately-meaningful commits, not one giant commit,
no inflated history.

## Scope — reliability & correctness hardening only

Do not touch multi-tenancy, auth model, or the disease model in this
module — those are Modules 17 and 18. This module makes what already
exists trustworthy and observable.

### 1. CI pipeline (GitHub Actions)
`.github/workflows/ci.yml` (or split into a couple of workflow files if
that's cleaner) that on every push/PR to `main`:
- Installs the global-interpreter requirements (`requirements.txt` +
  `requirements-dev.txt`) and runs `pytest --ignore=tests/voice`
- Runs `python tools/check_specs.py`
- Optionally, if a `.venv`-only voice test run is impractical in CI within
  a reasonable time/cost budget, it's fine to skip `tests/voice` in CI and
  say so explicitly — don't silently drop it without a note.
- Fails the build (non-zero exit) on any test failure or spec-check
  failure — this needs to actually gate, not just report.
- A lint step (ruff or flake8 — pick one, whichever is already implied by
  existing config, else your call) is a nice-to-have if it doesn't blow
  the time budget; don't let lint failures block the build unless you
  choose to make lint a hard gate deliberately (say which you chose).

### 2. Error monitoring
Wire Sentry's free tier (or an equivalent lightweight tracker if you have
a concrete reason to prefer one — say why) into the Flask app via
`sentry-sdk[flask]`. Errors should report with enough context (route,
farmer/field id if available, request id) to actually debug from the
Sentry dashboard. Document the `SENTRY_DSN` env var in `.env.example` and
`render.yaml` (marked `sync: false`, same pattern as `API_KEY`). Guard so
the app runs fine locally with no DSN configured (no-op, not a crash).

### 3. Structured logging
Add a request-id (e.g. via a `before_request`/`after_request` hook,
`uuid4()` per request, included in Flask's logger's extra context and
echoed in an `X-Request-Id` response header) so a single request's log
lines are traceable end to end. Keep it lightweight — standard library
`logging` with a formatter, no new heavy dependency required unless you
have a good reason.

### 4. Input validation hardening
Audit `POST /fields` and `POST /feedback` (and any other POST/PUT routes)
against `specs/core/openapi.yaml`'s declared request schemas. For each:
missing required field, wrong type, out-of-range value (e.g. a feedback
rating outside 1-5) — confirm each returns a clean 4xx with the existing
JSON error envelope, not a 500 or an unhandled exception. Add tests for
whatever gaps you find and fix the routes/validation layer accordingly.
This is a real audit, not a rubber stamp — if everything already handles
this correctly, say so and show the tests that prove it; if you find and
fix real gaps, list them explicitly in the handoff.

### 5. Backup strategy for Supabase
A `tools/backup_supabase.py` (or shell script, your call) that exports the
core tables to a timestamped local file (JSON or SQL dump — whichever is
simplest against the Supabase Python client/Postgres connection already
in use). Document in `docs/TOOLING.md` or a new `docs/BACKUPS.md` how and
how often to run it manually (a scheduled job is nice-to-have, not
required — Render's free tier doesn't give you cron easily; note this
honestly rather than promising automation that doesn't exist).

### 6. Rate limiting
A basic per-API-key rate limiter on the Flask API (e.g. `Flask-Limiter`
with an in-memory or simple store — no new infra dependency). Sensible
default (e.g. 60 requests/minute per key) — document the choice and how
to adjust it. Confirm exceeding it returns a clean 429, not a crash, and
add a test for it.

## Tests
Every item above needs its own test coverage where testable (validation
gaps, rate-limit 429 behavior, request-id header presence). Don't just
manually verify and skip automated coverage — that's exactly the kind of
thing that quietly regresses later.

## Full regression pass
Before declaring done: run the entire existing test suite (global
interpreter, `tests/` excluding `tests/voice`) plus this module's new
tests, confirm `check_specs.py` still passes, confirm the CI workflow
itself actually runs green on a real push (check the Actions tab, don't
just trust the YAML is syntactically valid).

## Update doctrine
`CLAUDE.md`, `PROGRESS.md` (new row: "Module 16 — Reliability & CI
Hardening"), `docs/ROADMAP_PRODUCTION.md` (check off workstream A items as
completed), commit and push.

## Definition of done
- [ ] CI pipeline running on every push, gating on test + spec-check
      failure, actually verified green on a real push
- [ ] Sentry (or equivalent) wired in, documented env var, no-op without
      DSN
- [ ] Request-id structured logging, header echoed
- [ ] Input validation audited and hardened with tests proving it
- [ ] Supabase backup script + documented process
- [ ] Rate limiting live with a test proving the 429 path
- [ ] Full regression pass, `check_specs.py` passes
- [ ] Pushed to `origin/main`

## Handoff format
```
Module: 16 — Reliability & CI Hardening
Status: complete | blocked
CI: <workflow file(s), confirmed green on a real push — link/describe>
Error monitoring: <Sentry or equivalent, DSN env var, verified how>
Structured logging: <approach, request-id header confirmed>
Input validation: <gaps found and fixed, or confirmed already solid — be specific>
Backup script: <location, how to run, how often recommended>
Rate limiting: <library/approach, limit chosen, 429 test>
Files changed:
Commits made:
Full regression: <pass/fail>
check_specs.py: pass/fail
Known limitations:
Next recommended module: 17 — Multi-tenant + Admin role
```
