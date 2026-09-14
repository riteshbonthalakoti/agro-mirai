# MODULE 11 FIX-UP 2 — SQLite cross-thread bug in SQLiteDataStore

Continuing AGRO MIRAI in the existing `agro-mirai` repo. This is a
targeted bug fix, not new scope — found during manual end-user testing
of the running app (not caught by the existing test suite, which is
worth noting itself: `pytest tests/api/` and `tests/frontend/` all pass
today despite this bug being real and reproducible).

## The bug

`SQLiteDataStore` opens one `sqlite3.connect(...)` connection when the
app factory (`create_app`) constructs it, and reuses that single
connection object for the lifetime of the app. Flask's dev server
(`flask run`), by default, dispatches each incoming request on its own
thread (`threaded=True` is Werkzeug's current default). `sqlite3`
connections are not safe to use across threads — the connection that
was created in the app-factory's thread cannot be used by a request
handled in a different thread.

Reproduction: run `flask run --port 5000` (no flags) against a real
seeded SQLite DB and hit any route that touches the store (`/`,
`/farmers/me`, `/fields/{id}/advisories`, etc.) — you'll get:

```
sqlite3.ProgrammingError: SQLite objects created in a thread can only
be used in that same thread. The object was created in thread id X
and this is thread id Y.
```

`flask run --port 5000 --without-threads` avoids it by forcing the dev
server single-threaded — but that's a workaround, not a fix, and it
won't help in production: Module 15's Render deploy will run under a
real WSGI server (gunicorn or similar), typically with multiple worker
threads/processes, where this bug will resurface and likely be *worse*
(harder to reproduce, intermittent under load) than the dev-server
case.

The existing test suite doesn't catch this because `app.test_client()`
in the current tests runs requests synchronously in the same thread as
the test — it never exercises the multi-threaded dispatch path that
`flask run`'s real dev server (and a real WSGI server) uses.

## Fix

Pick whichever approach fits `SQLiteDataStore`'s existing shape best,
and justify the choice briefly in the handoff:

1. **Per-request connection** (usually simplest and safest): open a new
   `sqlite3.connect(...)` at the start of each store method call (or
   via a Flask `g`-scoped helper opened once per request and closed via
   `teardown_appcontext`), rather than one long-lived connection on the
   store object. SQLite connections are cheap to open for a file-based
   DB at this scale.
2. **`check_same_thread=False` + a lock**: pass
   `sqlite3.connect(..., check_same_thread=False)` and guard all access
   with a single `threading.Lock` around each call, since a shared
   connection still isn't safe for concurrent use even across threads
   that take turns. Simpler patch, more contention under real
   concurrency — acceptable at this project's scale but say so.
3. Something else you find is more idiomatic (e.g. a small connection
   pool) — fine, as long as it's actually safe under Flask's threaded
   dev server *and* under a multi-worker production WSGI server, and
   you explain the reasoning.

Whatever you pick, don't paper over it with `--without-threads` in any
run instructions/docs — fix the actual data-access pattern.

## Also: close the test gap

Add a regression test that would have caught this — e.g. a test that
spins up the Flask app with `threaded=True` (or otherwise exercises a
real multi-threaded request path, not just `test_client()`'s
synchronous dispatch) and fires a handful of concurrent requests at a
route that touches the store, asserting none of them 500. If a
lightweight way to do this within the existing `tests/api/` structure
isn't obvious, say so honestly in the handoff and propose the closest
practical alternative rather than skipping it.

## Verify

- `flask run --port 5000` (no `--without-threads` flag) — hit `/`,
  `/farmers/me`, `/fields/{id}/advisories` repeatedly and confirm no
  thread errors.
- Full existing suite (`pytest tests/api/ tests/frontend/`) still
  passes.
- New regression test passes and would have failed against the old
  code (verify this — check it out against the pre-fix commit if
  needed, or reason through why it would have failed).

## Commit

One commit: something like
`fix: SQLiteDataStore connections were not thread-safe under Flask's
threaded dev server`. Push to `origin/main`. Update
`MANUAL_TEST_GUIDE.md` at the repo root if it still references
`--without-threads` as a required flag (it shouldn't be needed after
this fix — quick check, quick edit, not a big doc pass).

## Handoff format
```
Module: 11 fix-up 2 — SQLite threading bug
Status: complete | blocked
Root cause:
Fix approach chosen and why:
Files changed:
Commit made:
Regression test added: <describe, and confirm it would have caught the original bug>
Existing tests: <pass/fail>
Manual verification: <ran flask run without --without-threads, hit N routes M times, no errors>
Known limitations:
Next recommended module: 15 — Integration, deploy, docs
```
