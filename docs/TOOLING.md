# TOOLING.md — Verified CLI Versions

Verified on: 2026-08-25, Windows 11.

| Tool | Version | Auth status |
|---|---|---|
| git | 2.55.0.windows.3 | n/a |
| gh (GitHub CLI) | 2.97.0 | ✓ logged in (riteshbonthalakoti) |
| supabase | 2.114.0 | ✓ logged in (org access confirmed via `supabase projects list`) |
| render (render-oss/cli) | 2.24.0 | pending — user must run `render login` |
| gcloud | 581.0.0 (core), bq 2.1.37 | ✓ logged in (riteshbonthalakoti@gmail.com) |
| python | 3.12.10 | n/a |
| pip | 25.0.1 | n/a |
| earthengine-api (`ee`) | 1.7.41 | pending — `earthengine authenticate` blocked by Google as sensitive-scope app; retry with `earthengine authenticate --auth_mode=gcloud` |
| hf (huggingface_hub CLI, replaces deprecated `huggingface-cli`) | latest via `hf` | ✓ logged in (user ritesh1918) |
| kaggle | 2.2.4 | ✓ configured (username ritheshbonthalakoti, ACCESS_TOKEN) |

## Notes

- `render` CLI has no winget/npm package; installed manually from the
  [render-oss/cli GitHub releases](https://github.com/render-oss/cli/releases)
  (`cli_2.24.0_windows_amd64.zip`), binary placed at `~/bin/render.exe`.
- `huggingface-cli` is deprecated upstream; the `hf` command is the
  replacement and was already installed/authenticated in this environment.
- Earth Engine's default OAuth client triggered Google's "This app is
  blocked" sensitive-scope warning. Do not attempt to bypass this — it is a
  Google-side app verification gate, not a bug. Use `--auth_mode=gcloud`
  (piggybacks on the already-authenticated gcloud identity) or register an
  Earth Engine Cloud project and use a project-scoped service account for
  Module-level automation later.

## Test reporting

Test runs use `pytest` with the `pytest-json-report` plugin
(`pip install pytest-json-report`), invoked as:

```bash
pytest --json-report --json-report-file=.report.json
```

`tools/update_state.py` reads `.report.json` for the latest pass/fail
summary. `.report.json` is gitignored (regenerated per run, not
version-controlled).
