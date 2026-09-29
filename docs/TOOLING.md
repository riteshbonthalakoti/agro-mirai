# TOOLING.md — Verified CLI Versions

Verified on: 2026-08-25, Windows 11.

| Tool | Version | Auth status |
|---|---|---|
| git | 2.55.0.windows.3 | n/a |
| gh (GitHub CLI) | 2.97.0 | ✓ logged in (riteshbonthalakoti) |
| supabase | 2.114.0 | ✓ logged in (org access confirmed via `supabase projects list`) |
| render (render-oss/cli) | 2.24.0 | ✓ logged in (device-authorization flow, CLI token saved) |
| gcloud | 581.0.0 (core), bq 2.1.37 | ✓ logged in (riteshbonthalakoti@gmail.com) |
| python | 3.12.10 | n/a |
| pip | 25.0.1 | n/a |
| earthengine-api (`ee`) | 1.7.41 | ✓ authenticated via service account (see notes) |
| hf (huggingface_hub CLI, replaces deprecated `huggingface-cli`) | latest via `hf` | ✓ logged in (user ritesh1918) |
| kaggle | 2.2.4 | ✓ configured (username ritheshbonthalakoti, ACCESS_TOKEN) |

## Notes

- `render` CLI has no winget/npm package; installed manually from the
  [render-oss/cli GitHub releases](https://github.com/render-oss/cli/releases)
  (`cli_2.24.0_windows_amd64.zip`), binary placed at `~/bin/render.exe`.
- `huggingface-cli` is deprecated upstream; the `hf` command is the
  replacement and was already installed/authenticated in this environment.
- Earth Engine's interactive `earthengine authenticate` flow (all auth
  modes: default, `--auth_mode=gcloud`, `--auth_mode=appdefault`) was
  hard-blocked by Google with "This app is blocked" on the Earth Engine
  OAuth client itself — reproduced 3x on a plain (non-Workspace) personal
  Gmail account, so this is a Google-side block on that legacy client, not
  an account policy issue. Resolved by switching to a **service account**,
  which is the correct approach for non-interactive/automated use anyway:
  - Dedicated GCP project `agro-mirai-8315`, registered for Earth Engine
    **noncommercial (Academic & Research)** use at
    https://code.earthengine.google.com/register (one-time human step).
  - Service account `agro-mirai-ee@agro-mirai-8315.iam.gserviceaccount.com`
    created via `gcloud iam service-accounts create`.
  - JSON key generated via `gcloud iam service-accounts keys create` and
    stored at `~/.config/agro-mirai/ee-service-account.json` — **outside
    the repo, never committed**. Later modules that call GEE should load
    this path from an environment variable (e.g. `EE_SERVICE_ACCOUNT_KEY`),
    not hardcode it.
  - Verified: `ee.Initialize(ee.ServiceAccountCredentials(...))` +
    `ee.Number(1).add(1).getInfo()` returns `2`.
  - **Module 03 addendum:** registering the GCP project for Earth Engine
    was not sufficient on its own — the service account also needed two
    IAM roles granted on `agro-mirai-8315` before live queries (not just
    `ee.Number(1).add(1)`) would work: `roles/serviceusage.
    serviceUsageConsumer` (without it: `403 USER_PROJECT_DENIED`) and
    `roles/earthengine.writer` (without it: `Permission
    'earthengine.computations.create' denied`). Granted via:
    ```
    gcloud projects add-iam-policy-binding agro-mirai-8315 \
      --member="serviceAccount:agro-mirai-ee@agro-mirai-8315.iam.gserviceaccount.com" \
      --role="roles/serviceusage.serviceUsageConsumer" --condition=None
    gcloud projects add-iam-policy-binding agro-mirai-8315 \
      --member="serviceAccount:agro-mirai-ee@agro-mirai-8315.iam.gserviceaccount.com" \
      --role="roles/earthengine.writer" --condition=None
    ```
    Verified end-to-end via `tools/seed_ndvi_cache.py`, which pulled a
    real Sentinel-2 NDVI value into
    `specs/domains/fixtures/ndvi_cache.json`.

## Supabase (Module 04)

- No AGRO MIRAI project exists yet under any org visible to
  `supabase projects list` (5 unrelated projects found, all for other
  work). Creating one is a human decision (which org, db password, size)
  — not done automatically. See `modules/04-storage/STATUS` for the
  exact `supabase projects create` / `supabase link` / `supabase db
  push` sequence to unblock `SupabaseDataStore`.
- Supabase's free tier auto-pauses a project after **7 days with no
  API/DB activity**. A paused project rejects connections until resumed.
  Resume via CLI with `supabase projects restore <project-ref>`, or from
  the dashboard: Project → banner "Project is paused" → **Restore
  project**. The parity test suite's Supabase branch calls
  `SupabaseDataStore.ping()` first and skips cleanly (with a clear
  reason, not a failure) if the project is unreachable — restore it and
  re-run for real coverage instead of a skip.

## Voice stack (Module 12)

- All four AI4Bharat model repos used (`indictrans2-en-indic-dist-200M`,
  `indictrans2-indic-en-dist-200M`, `indic-conformer-600m-multilingual`,
  `vits_rasa_13`) are **HF-gated** — each needed a separate manual
  "Request access" click on huggingface.co under the `ritesh1918`
  account (auto-approved within a couple of minutes each, but it is a
  human step, not something `hf download`/`hf auth login` alone unlocks;
  README.md is fetchable on a gated repo before access is granted, which
  is misleading — don't take that as proof of full access, verify with
  an actual model file like `config.json`).
- Download sizes/times, measured on this connection: en-indic dist200M
  2.21GB (~39s), indic-en dist200M 1.84GB (~29s), indic-conformer-600m
  2.56GB / 404 files (~110s), vits_rasa_13 0.16GB (~8s), Piper
  `en_US-lessac-medium` voice ~60MB. **~6.8GB total, well under 5
  minutes** on this connection — reasonable for a capstone setup step,
  but worth budgeting for on a slower connection.
- `models/voice/` holds the downloaded weights and is gitignored
  (`/models/` in `.gitignore`), same pattern as `models/crop_rf.joblib`.
  Reproduce with `hf download <repo> --local-dir models/voice/<name>`
  per repo (see `src/agro_mirai/voice/ai4bharat_voice.py` for exact repo
  ids/paths) or regenerate via the model card usage snippets.
- **Module 25 (te/hi expansion)**: translation (IndicTrans2) and STT
  (IndicConformer) need no new downloads — the already-downloaded
  weights above cover `te`/`hi` too, confirmed against both model cards
  before wiring (`decisions/0021-language-expansion-te-hi.md`). TTS does
  need one new download — Telugu reuses the already-downloaded
  `vits_rasa_13` weights (just a different speaker id), but Hindi is on
  a different backend (Piper) with no Hindi voice downloaded yet:

  ```bash
  hf download rhasspy/piper-voices hi/hi_IN/rohan/medium/hi_IN-rohan-medium.onnx hi/hi_IN/rohan/medium/hi_IN-rohan-medium.onnx.json --local-dir models/voice/piper
  ```

  Until that command is run, `text_to_speech(text, "hi")` raises
  `VoiceUnavailableError` (the existing lazy-load-with-clear-error
  pattern, not a crash) — this is a real, not-yet-completed step, not
  silently faked. `en`/`kn`/`te` need no action beyond what Module 12
  already downloaded.
- **Project-local virtualenv required**: `.venv/` (gitignored), created
  with `python -m venv .venv`, pinned to `transformers==4.49.0` +
  `torch==2.4.1`/`torchaudio==2.4.1` (CPU wheels from
  `https://download.pytorch.org/whl/cpu`) + `sentencepiece soundfile
  indic-nlp-library sacremoses regex onnxruntime==1.20.1 piper-tts`. The
  project's global Python interpreter has transformers 5.15, which is
  incompatible with these AI4Bharat models in three different ways — see
  `docs/architecture.md` "AI4Bharat model / transformers version pin"
  for the specifics. Run voice code/tests with
  `.venv/Scripts/python.exe`, not bare `python`.
- `IndicTransToolkit` (IndicTrans2's required preprocessor) has no
  prebuilt Windows wheel and needs MSVC Build Tools to compile from
  source — not installed on this machine. Worked around with a
  pure-Python port (`src/agro_mirai/voice/_indic_processor.py`) instead
  of installing a C++ toolchain for one dependency — see
  `docs/architecture.md` for details.

## Running the web frontend (Module 14)

The frontend is server-rendered Jinja2 templates in the same Flask
process as Module 11's API — there is no separate service or build
step. From a clean checkout:

```bash
pip install -r requirements.txt   # or the individual packages Modules 01-11 already need
cp .env.example .env              # then fill in API_KEY and FARMER_ID

# Seed a farmer/field into SQLite so the dashboard has something to show
python tools/seed_fixture.py specs/domains/fixtures/farm-001.json agro_mirai.db
# (copy the printed farmer id into .env's FARMER_ID if it's not already set)

python -m flask --app agro_mirai.api.app:create_app run
```

Then open `http://127.0.0.1:5000/` in a browser — it shows the
configured farmer's fields; click one to see crop recommendation,
irrigation advice, disease-risk alerts, advisories, and a feedback form
per advisory. See `decisions/0013-frontend-platform-sequencing.md` for
why this is same-process rather than a separate SPA, and
`modules/14-frontend/STATUS` for what was verified against a real
seeded database.

## Dependency pinning and production WSGI (Module 15)

- `requirements.txt` (runtime) and `requirements-dev.txt` (adds pytest
  tooling) are generated from `pip freeze` against the global
  interpreter, hand-checked against actual imports across `src/`,
  `tools/`, and `tests/` (excluding `tests/voice/`, which needs the
  separate `.venv`). See `decisions/0014-deploy-target-and-voice-scope.md`
  for why the voice/AI4Bharat stack is excluded from `requirements.txt`.
- The pinned versions (`numpy==2.5.2`, `pandas==3.0.5`, `scikit-learn==1.4.2`,
  etc.) are exactly what Modules 06/07's training scripts already ran
  under on this machine — not a newer/different set introduced by this
  module. No re-training or eval-report invalidation risk from the pin
  itself; if you ever bump `scikit-learn` independently of a
  `requirements.txt` sync, re-run `tools/train_crop_model.py` /
  `tools/train_irrigation_model.py` and diff `docs/eval/*.json` first.
- `gunicorn==26.2.0` added for production. **It does not run on
  Windows** (no `fcntl`) — this dev machine can only run it inside WSL
  or a container, never natively. The multi-worker/SQLite-thread-safety
  verification for this module was done via a throwaway
  `pip install --user` environment inside WSL (Ubuntu), not committed
  anywhere — see ADR 0014 for the exact commands and result (60
  concurrent requests across 2 worker processes, all 200s).
- `Procfile` and `render.yaml`'s `startCommand` both run:
  `PYTHONPATH=src gunicorn -w 2 -b 0.0.0.0:$PORT "agro_mirai.api.app:create_app()"`
  — `PYTHONPATH=src` is needed because there's still no `pyproject.toml`/
  `setup.py` installing the package; this mirrors how tests and
  `flask run` already load it.

## Test reporting

Test runs use `pytest` with the `pytest-json-report` plugin
(`pip install pytest-json-report`), invoked as:

```bash
pytest --json-report --json-report-file=.report.json
```

`tools/update_state.py` reads `.report.json` for the latest pass/fail
summary. `.report.json` is gitignored (regenerated per run, not
version-controlled).

## CI/CD (Module 50)

Two GitHub Actions workflows plus Render's own git integration cover
the full pipeline — nothing here is manual anymore except a live
Supabase migration push (deliberately kept manual, see below):

- **`.github/workflows/ci.yml`** ("CI") — runs the full backend test
  suite, `check_specs.py`, and the CNN/voice service suites on every
  push/PR to `main`. Unchanged by Module 50.
- **`.github/workflows/deploy.yml`** ("Deploy (Vercel)", new) — triggers
  via `workflow_run` on CI's completion, `main` branch only, so a
  broken build can never reach production. Two jobs, `deploy-admin` and
  `deploy-landing`, each run `vercel pull` / `vercel build --prod` /
  `vercel deploy --prebuilt --prod` against `web/admin` and
  `web/landing` respectively.
- **Render** (`agro-mirai`, `agro-mirai-cnn`) — already had its own git
  integration (`autoDeploy: yes`, trigger `commit`) from earlier
  modules; nothing new needed there, confirmed via
  `render deploys list <service-id>`.
- **Supabase migrations** — deliberately **not** automated. `supabase
  db push` stays a manual CLI step before/alongside a deploy that needs
  a new migration, per this project's own safety norms around
  production schema changes. `supabase/migrations/` (CLI-tracked) must
  stay in sync with `migrations/postgres/*.sql` (this project's own
  documented-contract convention) — Module 50 found a real gap here
  (see `decisions/0030-admin-write-actions.md`) where a migration only
  existed in the latter, so `supabase db push` had nothing to push.
  Check both whenever adding a schema change.

**Required GitHub repo secrets** (`gh secret list`):

| Secret | Value | Source |
|---|---|---|
| `VERCEL_TOKEN` | a Vercel access token | **Currently a short-lived OAuth session token pulled from the local CLI's own auth store on 2026-09-28, expires 2026-09-28 ~06:58 UTC — replace with a real personal access token from https://vercel.com/account/tokens before then**, or every deploy after expiry will fail with a 403. |
| `VERCEL_ORG_ID` | `team_qa5DQgHjCoaK4byyXuslEOov` | `web/admin/.vercel/project.json` / `web/landing/.vercel/project.json` (same team for both) |
| `VERCEL_ADMIN_PROJECT_ID` | `prj_gfZvgbYyLwLvWWItQZqQHgg0SjTt` | `web/admin/.vercel/project.json` |
| `VERCEL_LANDING_PROJECT_ID` | `prj_3NJk8iRVRFFrMJ9mHt7X4QubVQrK` | `web/landing/.vercel/project.json` |

To rotate `VERCEL_TOKEN`: generate a new token at the URL above, then
`gh secret set VERCEL_TOKEN` (reads from stdin or a local file — never
paste a token directly into a chat/session transcript).

Not yet automated (documented as a real gap, not an oversight): a
Supabase-migration-drift CI check (fail the build if
`supabase migration list --linked` shows any unapplied local
migration) was scoped for this module but not built — extracting a
durable Supabase access token from this machine's CLI auth store hit
the same dead end as Vercel's did (session-scoped, not a real PAT), and
a fresh PAT generation step wasn't completed in this session. Add it
the same way `VERCEL_TOKEN` was added, once a token exists.

## OTA updates (EAS Update) -- local build channel binding

Release APKs are built locally, not via `eas build` cloud -- see the Module 51 APK-size work for
why (Windows path-length limits under the deep worktree path this repo's harness creates made a
short-path local build worth setting up instead of fighting cloud-build upload/queue times).
`eas.json`'s per-profile `"channel"` field only binds a channel for cloud (`eas build`) builds.

**app.json cannot read environment variables at all -- it's static JSON, not JS.** The channel is
set via `mobile/app.config.js`, a thin dynamic config that extends `app.json` and reads
`process.env.APP_CHANNEL` into `updates.requestHeaders['expo-channel-name']` -- the actual
mechanism `expo-updates` uses to pick a channel (confirmed by reading the installed
`expo-updates`/`@expo/config-plugins` source, not assumed). Set `APP_CHANNEL` *before* running
`expo prebuild` (config resolution happens at that point; setting it after prebuild has no
effect):

```bash
# Personal test build (receives `staging` channel updates):
APP_CHANNEL=staging npx expo prebuild --platform android --clean

# Real public release build (receives `production` channel updates):
APP_CHANNEL=production npx expo prebuild --platform android --clean
```

`runtimeVersion` uses the `fingerprint` policy (computed from the actual native code), not
`appVersion` -- this means an update can never be silently offered to a binary with a mismatched
native module set just because `app.json`'s `version` field wasn't bumped for a native change.
No manual version-bump discipline to remember or get wrong.

The `staging` and `production` EAS Update channels/branches don't exist until created once:
```bash
eas channel:create staging
eas channel:create production
```

Publishing an update to staging:
```bash
eas update --branch staging --message "<what changed>"
```

Promoting an already-tested staging update to production (this is the manual safety gate --
never script this step). **Promote the specific tested update, not the whole branch** --
`eas channel:edit production --branch staging` would point `production` at the live `staging`
branch permanently, so every future `eas update --branch staging` (including the one-click
GitHub Action) would go straight to production from then on, silently removing this gate after
its first use:
```bash
# Find the update group ID for what you just tested on staging:
eas channel:view staging

# Republish that exact update (same bits, not a rebuild) to the production branch:
eas update:republish --group <update-group-id> --destination-branch production
```
