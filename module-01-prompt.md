# MODULE 01 — Foundation, Tooling & Doctrine

You are the implementation agent for AGRO MIRAI, an AI-driven smart agriculture
advisory system (VTU Semester 7 capstone, BITM, Dept. of AIML). This is
Module 01 of 15 in a dependency-gated build — nothing in this module produces
farming logic yet. It produces the scaffold every later module depends on.

You are starting with an EMPTY project folder. Do not assume any prior state.

## Ground rules for this whole project (apply from this module onward)

1. CLI-first, always. Before touching any external service (GitHub, Supabase,
   Render, Google Cloud/Earth Engine, Hugging Face, Kaggle), check whether an
   official CLI exists and use it. Never describe a dashboard click-path if a
   CLI command does the same thing.
2. Nothing is hand-faked. If a step needs human auth (browser OAuth, an API
   key), STOP, print the exact command and what it will ask for, and wait —
   do not simulate success.
3. Every module ends in: implementation → tests → docs updated → git commit.
   No module is "done" without a passing test for it.
4. State must be generated, not hand-maintained (see the state script below).

## Tasks

### 1. Verify / install CLIs (check before installing each one)
- `git` — verify present.
- `gh` (GitHub CLI) — check `gh --version`; if missing, install for this OS.
  Then run `gh auth status`. If not authenticated, print the exact
  `gh auth login` command and stop for me to complete it in-browser.
- `supabase` CLI — check, install if missing, then `supabase login` (same
  stop-and-wait pattern if it needs browser auth).
- `render` CLI ([render-oss/cli](https://github.com/render-oss/cli)) — check,
  install if missing, `render login`.
- `gcloud` CLI — check, install if missing. Then install the Earth Engine
  Python API (`pip install earthengine-api`) and run `earthengine authenticate`
  — this opens a browser flow, stop and wait for me.
- `huggingface-cli` (`pip install huggingface_hub[cli]`) — check, install,
  `huggingface-cli login` (needs a token from huggingface.co/settings/tokens —
  print the URL, wait for me to paste it).
- `kaggle` CLI — check, install (`pip install kaggle`), tell me to place
  `kaggle.json` in the right config path (don't ask me to paste the key
  contents into chat).
- Record the verified version of every tool in `docs/TOOLING.md`.

### 2. Initialize the repository
- `git init` in the project root.
- Create `.gitignore` for Python, Node, env files, model artifacts, and
  IDE clutter.
- `gh repo create agro-mirai --private --source=. --remote=origin` (confirm
  the name with me first if you think a different name fits better — but
  default to `agro-mirai`).
- Initial commit: "Module 01: project foundation and tooling".

### 3. Repo layout (create empty, annotated folders — content comes in later modules)
```
agro-mirai/
  CLAUDE.md              # doctrine — hard rules, repo map, current phase
  PROGRESS.md            # session handoff log — see template below
  docs/
    TOOLING.md            # CLI versions verified in step 1
    architecture.md        # placeholder, filled in Module 02+
  specs/
    core/                  # placeholder for Module 02's contracts
    domains/
  decisions/
    0001-index.md          # empty ADR index to start
  modules/
    01-foundation/          # this module's own notes + tests live here
  tools/
    update_state.py         # see step 4
  tests/
```

### 4. Build the state-generation script (`tools/update_state.py`)
This is the mechanism that keeps `PROGRESS.md` accurate without manual upkeep.
It should:
- Read `git log` (last N commits, one line each) and the list of modules
  present under `modules/` with a `STATUS` marker file in each.
- Read the latest test run output (assume `pytest --json-report` or similar —
  pick one and document it in `docs/TOOLING.md`).
- Regenerate ONLY the "Current State" section of `PROGRESS.md` between two
  HTML comment markers (`<!-- STATE:START -->` / `<!-- STATE:END -->`),
  leaving the hand-written sections (role table, locked decisions, open
  questions) untouched.
- Be runnable as `python tools/update_state.py` and be the last step of every
  module's own workflow, right before the commit.

### 5. Write `CLAUDE.md`
Following the doctrine-file shape: one-liner, hard rules `[LOCKED]` (start
with: CLI-first, additive-only data contracts, SQLite-dev/Supabase-prod via
a repository interface — do not let any module talk to a database engine
directly, GEE-live-with-NDVI-cache fallback, module N+1 never starts before
module N is tested and committed), annotated repo map, current phase.

### 6. Write `PROGRESS.md`
Using the session-continuity template: role table, locked decisions table
(pull these from `docs/agro-mirai-stack-brief` decisions if you have access
to it, otherwise leave placeholders I'll fill), phase plan (all 15 modules,
status column, all "not started" except 01), and the state block from step 4.

## Definition of done for Module 01
- [ ] Every CLI in the list above is verified installed and authenticated
      (or I've explicitly told you to skip one for now)
- [ ] Private GitHub repo exists and `origin` is set
- [ ] Folder structure above exists
- [ ] `tools/update_state.py` runs without error and produces a real state
      block in `PROGRESS.md`
- [ ] `CLAUDE.md` and `PROGRESS.md` exist and are accurate
- [ ] One clean commit, pushed to `origin/main`

## What to hand back to me
One handoff, after everything above is done and committed — not a
step-by-step transcript. Use this shape:

```
Module: 01 — Foundation, Tooling & Doctrine
Status: complete | blocked (say on what)
Implemented: <bullet list>
Files changed: <list>
Tests created: <list + pass/fail>
CLI tools verified: <table of tool → version → auth status>
Known limitations:
Remaining risks:
Next recommended module: 02 — Data Contracts & Conventions
```
