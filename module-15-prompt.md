# MODULE 15 — Integration, Deploy, Docs

Continuing AGRO MIRAI in the existing `agro-mirai` repo. Modules 01–14b
are done and committed, including two post-hoc fix-ups (the `/health`
spec gap and the SQLite cross-thread bug — `3364fa2` is the latest
commit on `origin/main` as of this prompt). Read `CLAUDE.md`,
`PROGRESS.md`, and `MANUAL_TEST_GUIDE.md` first — the last one exists
precisely because this module needs to know what "actually works when
a human runs it" looks like, not just what the test suite claims.

Confirm `git config user.name`/`user.email` are correct. Same commit
discipline as prior modules — but expect this one to be several
commits across genuinely different concerns (requirements pinning,
deploy config, end-to-end tests, docs, demo script), not one giant
commit.

This is the last module before the Nov 14 final report. Nothing ships
after this without it being a deliberate, separate decision — treat
"done" here as "actually done," not "mostly done."

## Known gaps this module must close

1. **No `requirements.txt` exists anywhere in the repo.** Every module
   so far installed packages ad hoc into whatever interpreter was
   active. This is a real gap, not a nice-to-have — Render can't deploy
   an app it doesn't know the dependencies for.
2. **No production WSGI server is installed or configured.** The app
   has only ever been run via `flask run` (Werkzeug's dev server),
   which prints its own warning that it's not for production use.
3. **The SQLite threading fix (thread-local connections) was tested
   under Flask's dev server, not yet under a real multi-worker/
   multi-thread production WSGI server.** Don't assume it's fine there
   — verify it, since that's exactly the deployment target this module
   sets up.
4. **The two Python-environment split (global interpreter for API/web,
   `.venv` pinned to `transformers==4.49.0` for voice) has no
   documented resolution for a single deployed service.** Decide and
   document how (or whether) the deployed Render instance includes
   voice inference at all — see task 4 below.

## Tasks

### 1. Pin real dependencies
Generate `requirements.txt` from what's actually imported and used
across `src/`, `tools/`, and `tests/` — don't hand-guess. Use
`pip freeze` from a clean environment that has everything installed, or
a proper dependency-scanning approach (e.g. `pipreqs`), then hand-check
the result against actual imports (freeze output includes trans
itive deps too, which is fine, but sanity-check nothing bizarre or
unrelated snuck in from a dirty dev environment). Split into
`requirements.txt` (runtime — what Render installs) and, if useful,
`requirements-dev.txt` (pytest, etc.) — your call, document whichever
you choose in `docs/TOOLING.md`.

Explicitly decide and document: does `requirements.txt` include the
voice/AI4Bharat stack (`transformers`, `torch`, etc.) or not? Given
Render's free tier is 512 MB RAM / 0.1 CPU, a full transformers+torch
install is likely to blow that budget or make cold-starts unusable.
The honest options are (a) deploy without live voice inference in the
hosted demo, documenting that voice is demoed locally per
`MANUAL_TEST_GUIDE.md` instead, or (b) split voice into a separate
service per the stack brief's Hugging Face Spaces fallback. Given the
timeline, (a) is probably right — but make the call explicitly, write
it into `decisions/0014-deploy-target-and-voice-scope.md`, and don't
let it happen by accident.

### 2. Production WSGI server
Add `gunicorn` (or `waitress` if you have a concrete reason to prefer
it on this stack) to `requirements.txt`, and a `Procfile` or Render
`start command` that runs the app through it instead of `flask run`.
Confirm the SQLite thread-local fix from the prior fix-up actually
holds under this real multi-worker setup — run it locally with
gunicorn (`gunicorn -w 2 -b 127.0.0.1:5000 "agro_mirai.api.app:create_app()"`
or equivalent) and hit it concurrently, the same way the regression
test in `tests/api/test_threaded_server.py` does, before trusting it in
production. If gunicorn's multi-*process* model (not just multi-thread)
exposes a problem the thread-local fix doesn't cover — each worker
process would get its own SQLite connection pool, which should be fine
for a single SQLite file, but confirm rather than assume — document
what you found either way.

### 3. Render deployment
Stand up the actual Render free-tier web service per the stack brief's
decision 2 (local-first, Render link kept live, not depended on for the
primary demo). Environment variables (`API_KEY`, `FARMER_ID`,
`DATABASE_URL`/Supabase creds, `FLASK_ENV=production`) configured in
Render's dashboard, not committed. Confirm the deployed instance:
- Serves the web frontend and API correctly
- Uses Supabase (not a local SQLite file, which won't persist across
  Render's ephemeral filesystem/restarts) — this is where Module 04's
  repository-interface abstraction pays off; confirm
  `SupabaseDataStore` actually works end to end against a real Supabase
  project, not just unit-tested
- Cold-starts acceptably (document the ~1 minute cold-start reality
  from the stack brief so it's not a surprise on review day)

Document the deployed URL and the "wake it up before your review"
reminder (Render sleep + Supabase's 7-day pause) in `PROGRESS.md` or a
`docs/DEMO_DAY.md` — wherever fits best, your call, but it needs to
exist somewhere obvious.

### 4. End-to-end tests against the deployed instance
A small test/script (`tests/e2e/test_deployed_smoke.py` or a
`tools/smoke_test.py` — whichever fits the existing test structure
better) that hits the real deployed Render URL (not localhost) and
confirms: health check, an authenticated advisory request returns
schema-valid data, feedback submission round-trips. This is different
from the existing `tests/api/` integration tests — those run against a
local Flask test client; this one proves the actual hosted deployment
works, which is the thing evaluators will actually click on.

### 5. Docs and demo script
- `PROGRESS.md`: finalize — every module row accurate, no stale "TBD"s
  (check the whole table, not just the last few rows — this has drifted
  before).
- `docs/DEMO_SCRIPT.md`: a literal walkthrough script for the live
  review — what to click/say/show in what order, including the
  Kannada voice moment from `MANUAL_TEST_GUIDE.md` section 7 if you
  decide to demo it live (pre-recorded audio as a fallback if live
  inference isn't in the deployed instance per task 1's decision).
  Assume the presenter (Ritesh) has 10 minutes, not 30 — prioritize the
  full pipeline (crop/irrigation/disease → explanation → advisory) and
  the Kannada language story, since those are the two things this
  project claims that a generic capstone doesn't.
- Confirm `README.md` (create one at repo root if none exists) gives a
  newcomer — an evaluator poking at the GitHub repo, not just running
  the deployed link — enough to understand what they're looking at:
  what the project is, the module/ADR structure, how to run it locally
  (can point to `MANUAL_TEST_GUIDE.md` rather than duplicate it).
- Update `CLAUDE.md`'s phase marker to reflect the project is complete
  pending final report writing.

### 6. Full regression pass
Before declaring this done: run the entire test suite (both
environments — global interpreter for `tests/` excluding `tests/voice`,
and `.venv` for `tests/voice`), confirm `check_specs.py` still passes,
and confirm nothing in this module's changes (dependency pins,
gunicorn config, Render env) broke anything that was working. If
`requirements.txt` pins a different version of something than what's
been running (e.g. if `pip freeze` captures a newer sklearn than what
trained the artifacts), flag it explicitly — don't silently let a
version pin invalidate a working model artifact.

## Definition of done
- [ ] `requirements.txt` (and dev-requirements if split) generated from
      real usage, voice-stack inclusion decision made and documented
      in ADR 0014
- [ ] Production WSGI server (gunicorn or equivalent) configured;
      SQLite thread-safety re-verified under it, not assumed
- [ ] Render deployment live, using Supabase (not local SQLite),
      documented cold-start/wake-up reality
- [ ] End-to-end smoke test against the real deployed URL, not just
      localhost
- [ ] `PROGRESS.md` fully accurate, `docs/DEMO_SCRIPT.md` written,
      `README.md` exists and orients a newcomer
- [ ] Full regression pass across both environments, `check_specs.py`
      passes
- [ ] Pushed to `origin/main`

## Handoff format
```
Module: 15 — Integration, Deploy, Docs
Status: complete | blocked
Voice-in-deploy decision (ADR 0014): <included | excluded, and why>
Deployed URL:
Files changed:
Commits made:
Full regression: <pass/fail, both environments>
check_specs.py: pass/fail
E2E smoke test against deployed URL: <pass/fail, what it checked>
Known limitations:
Remaining risks:
Demo script location:
Next recommended step: final report writing (no more modules)
```
