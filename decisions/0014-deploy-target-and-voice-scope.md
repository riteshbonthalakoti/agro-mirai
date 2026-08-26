# ADR 0014 — Deploy target, WSGI server, and voice-stack scope

**Status:** accepted
**Date:** 2026-08-27
**Module:** 15 — Integration, Deploy, Docs

## Context

Module 15 needs to actually ship AGRO MIRAI somewhere reachable outside
the developer's own machine, without silently letting a resource
constraint (Render free tier: 512MB RAM / 0.1 CPU) make a decision by
accident. Three things needed an explicit call: whether the voice/
AI4Bharat stack ships in the deployed instance, what runs the WSGI
process, and how the model artifacts get built without a committed
`models/*.joblib`.

## Decision 1 — voice stack is excluded from the deployed instance

`requirements.txt` does **not** include `torch`, `transformers`,
`indicnlp`, `sacremoses`, `regex`, `soundfile`, `piper-tts`, or
`torchaudio`. Reasoning:

- The AI4Bharat stack alone is ~6.8GB of model weights
  (`docs/TOOLING.md`) plus `torch`, which is several hundred MB on its
  own — this does not fit in 512MB RAM at inference time, let alone
  alongside Flask/sklearn/shap in the same process.
- `.venv/` (pinned `transformers==4.49.0`) is a separate, project-local
  environment specifically because the global interpreter's
  `transformers` 5.x is incompatible with these models
  (`docs/architecture.md`) — there is no single environment that runs
  both the API and voice inference today, so "deploy it all in one
  service" was never actually on the table without a rewrite.
- The stack brief's own fallback for this exact situation is a separate
  Hugging Face Spaces service. Given the Nov 14 deadline and that this
  is a solo capstone, standing up and maintaining a second deployed
  service for one demo moment is not worth the risk of it breaking
  independently of the main submission.

**Chosen: option (a) — demo voice locally.** The Kannada voice pipeline
(translate / ASR / TTS) is fully real and tested (`tests/voice/`, 25
passing under `.venv/`) — it is demoed live on the developer's own
machine per `MANUAL_TEST_GUIDE.md` §7, not through the hosted Render
instance. `docs/DEMO_SCRIPT.md` calls this out explicitly with a
pre-recorded-audio fallback in case live inference isn't practical
during the review slot. This is a scope boundary of *the hosted
instance*, not of the project — the voice pipeline itself is complete
and independently verifiable.

## Decision 2 — gunicorn as the production WSGI server

`gunicorn==26.2.0` added to `requirements.txt`, run via `Procfile` /
`render.yaml`'s `startCommand`:
`PYTHONPATH=src gunicorn -w 2 -b 0.0.0.0:$PORT
"agro_mirai.api.app:create_app()"`.

`waitress` was the documented alternative (cross-platform, including
Windows) but wasn't needed: Render's build/runtime environment is
Linux, and gunicorn is the more common choice there with no concrete
reason on this project to prefer waitress.

**gunicorn does not run on Windows at all** (no `fcntl`), so the
multi-worker verification for this decision could not run on this
dev machine directly. It was run for real under WSL (Ubuntu, a
throwaway `--user`-installed environment, not committed) instead of
skipped or assumed:

- `gunicorn -w 2 -b 127.0.0.1:5099 ...` against the real `create_app()`
  factory (models mocked the same way `tests/api/test_threaded_server.py`
  mocks them — this test is about the WSGI/threading boundary, not model
  correctness) and a real `SQLiteDataStore` file.
- 60 concurrent requests via a `ThreadPoolExecutor` (matching the
  existing regression test's shape) across the **2 worker processes** —
  all 200s, zero `sqlite3.ProgrammingError`, zero exceptions in
  gunicorn's error log during the live run.
- **Multi-process finding:** each gunicorn worker is a separate OS
  process, so each gets its own independent `SQLiteDataStore` /
  thread-local-connection pool onto the *same* SQLite file — this is
  the standard SQLite multi-process access pattern (file-level locking),
  not something the existing thread-local fix needed to additionally
  handle. No new bug surfaced. This confirms — not just assumes — that
  the Module 11 fix-up (`3364fa2`) holds under gunicorn's process model,
  not only under Flask's dev-server thread model it was originally
  fixed against.

## Decision 3 — model artifacts are trained at Render build time, not committed

`models/*.joblib` stays gitignored (unchanged from Modules 06/07's
original decision — see `decisions/0007-...`/`0008-...`). Since Render's
filesystem doesn't persist a locally-trained artifact across a fresh
build, `render.yaml`'s `buildCommand` runs
`python tools/train_crop_model.py && python tools/train_irrigation_model.py`
after `pip install`, which requires the training CSVs to exist at build
time. Rather than depend on Kaggle API credentials as a Render build
secret (an extra external-service dependency for something this small),
the two source CSVs (`data/raw/Crop_recommendation.csv`,
`data/raw/irrigation_prediction.csv`, ~1.2MB combined) are committed
directly — `.gitignore`'s `data/raw/` blanket rule now carries explicit
`!`-exceptions for just these two files. `data/cache/` (the NDVI cache)
stays ignored; unrelated to this decision.

This keeps the "reproducible artifact, not a committed binary" policy
intact for the actual model file while making the Render build
deterministic and free of a second external credential to configure.

## Decision 4 — Supabase is selected automatically when configured

`create_app()` (`src/agro_mirai/api/app.py`) now picks `SupabaseDataStore`
over `SQLiteDataStore` when both `SUPABASE_URL` and `SUPABASE_KEY` are
set in the environment, and falls back to the existing SQLite path
otherwise — additive, no change to any caller that doesn't set those
vars (every existing test still gets SQLite or an injected `DATA_STORE`
mock unchanged). Render's env vars (dashboard-configured, not committed)
set both, so the deployed instance persists to the real Supabase
project (`yzsemdauwafxssaknlzr`, Module 04) rather than an ephemeral
local SQLite file that would reset on every Render restart/redeploy.

## Consequences

- The hosted Render demo covers Modules 06-11, 13, 14/14b end to end
  (crop/irrigation/disease/advisory/feedback, web frontend) against real
  Supabase persistence. It does not cover Module 12 live — that is a
  local-machine demo moment by design, not a gap.
- A future "make voice deployable" effort (if ever pursued) is scoped
  cleanly as its own service per the stack brief's Spaces fallback; this
  ADR does not block that, it just declines to build it now.
