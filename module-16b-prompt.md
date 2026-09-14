# MODULE 16b — Voice stack in CI

Quick follow-up to Module 16 (`121cfee` on `origin/main`). CI currently
runs the 230 global-interpreter tests but excludes `tests/voice`
(`--ignore=tests/voice` in `.github/workflows/ci.yml`) because that suite
needs the pinned `.venv` (`transformers==4.49.0`, torch, etc.) which isn't
installed in the main CI job. Locally it's been verified at 25/25 passing
(`.venv/Scripts/python.exe -m pytest tests/voice`), but it's never been
gated in CI — this closes that gap.

## Task

Add a second job to `.github/workflows/ci.yml` (e.g. `voice-tests`,
running alongside the existing `test` job, not blocking it) that:
1. Checks out the repo, sets up Python 3.12.
2. Installs the voice-stack requirements — check whether these are
   already captured anywhere (a `requirements-voice.txt`? inline in
   `.venv`'s history?); if not, generate one now via `pip freeze` inside
   the actual `.venv` equivalent and commit it, the same way
   `requirements.txt` was generated in Module 15. Don't hand-guess
   versions — `transformers==4.49.0` is confirmed, torch's version needs
   to match what's actually been working.
3. Runs `pytest tests/voice -q` with `PYTHONPATH=src`.
4. Fails the job on any test failure (this should be a real gate, same
   as the main test job).

Expect the first run to be slow (~several minutes, multi-GB download for
torch + the AI4Bharat model weights the tests pull from Hugging Face on
first use) — that's expected and acceptable; note it in the workflow
file as a comment so it's not mistaken for a hang later.

If GitHub Actions' runner disk/time limits make this genuinely
impractical (e.g. runs consistently time out or exceed available disk),
say so explicitly with the actual error, and propose the next-best
option (e.g. caching the Hugging Face model downloads between runs via
`actions/cache`) rather than silently reverting to `--ignore`.

## Verify

Push and confirm the new job actually runs green on `origin/main` — not
just valid YAML. Update `PROGRESS.md`'s CI note and
`docs/ROADMAP_PRODUCTION.md` to reflect that voice is now CI-gated, not
manual-only.

## Commit

One or two commits (dependency file if new, workflow change), pushed to
`origin/main`.

## Handoff format
```
Module: 16b — Voice stack in CI
Status: complete | blocked
New CI job: <name, what it installs, confirmed green on a real push — link>
Voice deps file: <new file or existing, how versions were confirmed>
Run time observed: <first run vs. cached, if applicable>
Files changed:
Commits made:
Known limitations:
Next recommended module: 17 — Multi-tenant + Admin role
```
