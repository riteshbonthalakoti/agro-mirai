# MODULE 36 — Verify the 3 Colab notebooks + prepare the backend for handover to the team

Continuing AGRO MIRAI. This module has exactly two things in it, nothing
else. Mobile offline fix is Module 37. Admin dashboard is Module 38. Don't
touch either of those here.

Context: the team split their own progress into 5 "paper" modules for
faculty (Module 1 = backend + models + architecture + APIs, Module 2 =
frontend/landing page + mobile UI + dashboard, Module 3 = database, Module
4 = testing, Module 5 = production deployment) — this is a presentation
framing only, not the actual build order, and doesn't need to be followed
in code. Right now the team's faculty wants to see Module 1 (backend) and
Module 2 (frontend). Frontend is done — the landing page is live and
should be submitted as-is, no redesign. This module's job is to get the
backend into genuinely handoff-ready shape.

## 1. Verify the 3 Colab notebooks actually run

Notebooks 1 (crop recommendation) and 2 (irrigation) need a `kaggle.json`
upload and have not been run in a live Colab session yet. Notebook 3
(disease risk) status unconfirmed either way.

- Run each of the 3 notebooks in a genuinely fresh Colab runtime,
  Runtime → Run All, from top to bottom, with no manual intervention
  beyond the documented `kaggle.json` upload step.
- Fix anything that breaks — a stale import, a path assumption that
  doesn't hold in a clean runtime, anything.
- Confirm each one produces real, correct output by the end (not just
  "no errors" — check the actual results cell shows a sensible real
  result).
- If `kaggle.json` is genuinely required and the reviewer/faculty won't
  have one, note that clearly in each notebook's top markdown cell with
  exact instructions for getting one (a 2-minute Kaggle account step) —
  don't silently assume everyone has this.

## 2. Prepare the backend for handover — this is the real priority

The team needs to hand the actual backend code to their one technical
teammate, and have their non-technical teammate able to demo it live to
faculty. "Production-grade" here means: clean, documented, runnable by
someone who didn't build it, and genuinely representative of the real
architecture — not a redesign, a cleanup and packaging pass.

- **Code cleanliness pass on `src/agro_mirai/`**: confirm no stray debug
  prints, no commented-out dead code blocks, no leftover
  experiment/scratch files sitting in the main source tree (move
  anything genuinely scratch into a clearly-named folder or remove it,
  your judgment, but don't silently delete anything that might be real).
- **A backend-specific README** (`src/agro_mirai/README.md` or a
  top-level `BACKEND.md`, your call on which reads better given the repo
  layout) that a faculty member or teammate can read to understand, in
  plain language: what the backend does, the real architecture (data
  acquisition → processing → ML models → decision/explanation → API),
  the real API surface (link to `specs/core/openapi.yaml`, don't
  duplicate it by hand), and where the model training code lives.
- **Confirm the model training code is genuinely present and traceable**
  — for each of the three real models (crop recommendation, irrigation
  water-balance, disease-risk), confirm the actual training/fitting code
  exists in the repo (not just inference) and is referenced from the
  README, since faculty will likely ask "where did this model come
  from," not just "does it run."
- **A real, tested local run-through**: from a clean checkout (simulate
  this — don't just trust the existing working directory), follow your
  own README's setup steps exactly and confirm the backend starts
  successfully and answers a real request. If any step is missing or
  wrong, fix the README, don't just note the gap.
- **Confirm `.env.example` is complete and accurate** — every real env
  var the backend actually needs, with placeholder values and a one-line
  comment on where to get each real key (OpenWeatherMap, GEE service
  account, Supabase, etc.) — this is what the technical teammate will
  actually use to get it running.
- **Do not touch the mobile app or any frontend/landing code in this
  module** — confirmed out of scope, that's Module 37/38.

## What NOT to do

- No mobile offline work (Module 37).
- No admin dashboard work (Module 38).
- No landing page changes — it's done, submit as-is.
- No new features anywhere — this is verification and packaging only.

## Handoff format

```
Module: 36 — Colab notebook verification + backend handover prep
Status: complete | blocked | needs-decision

Notebook verification:
  Notebook 1 (crop rec): <run confirmed, fixes made if any, kaggle.json note>
  Notebook 2 (irrigation): <run confirmed, fixes made if any>
  Notebook 3 (disease risk): <run confirmed, fixes made if any>

Backend handover prep:
  Code cleanliness: <what was found/cleaned>
  README written: <path, what it covers>
  Model training code confirmed present: <for each of the 3 models, where>
  Clean-checkout run-through: <confirmed working, any README fixes made>
  .env.example: <confirmed complete>

Known limitations:
Next recommended step:
```
