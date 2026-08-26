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

## Test reporting

Test runs use `pytest` with the `pytest-json-report` plugin
(`pip install pytest-json-report`), invoked as:

```bash
pytest --json-report --json-report-file=.report.json
```

`tools/update_state.py` reads `.report.json` for the latest pass/fail
summary. `.report.json` is gitignored (regenerated per run, not
version-controlled).
