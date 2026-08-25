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

## Test reporting

Test runs use `pytest` with the `pytest-json-report` plugin
(`pip install pytest-json-report`), invoked as:

```bash
pytest --json-report --json-report-file=.report.json
```

`tools/update_state.py` reads `.report.json` for the latest pass/fail
summary. `.report.json` is gitignored (regenerated per run, not
version-controlled).
