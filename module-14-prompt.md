# MODULE 14 — Frontend (Web)

Continuing AGRO MIRAI in the existing `agro-mirai` repo. Modules 01–11
are done and committed (`822251b` on `origin/main`). Read `CLAUDE.md`
and `PROGRESS.md` first.

This module runs in parallel with Module 13 (Feedback Loop) — a
different Claude Code session is building the feedback aggregation
against the same `origin/main` at the same time. Stay inside a new
frontend directory (see structure below) and `src/agro_mirai/api/` only
if you find a genuine API gap (same discipline as Module 11's `/health`
fix — propose it, add it to `openapi.yaml` first in its own commit,
call it out explicitly), and pull before you push in case M13 has
already merged something. If you hit a real conflict with M13's work,
stop and report it in the handoff rather than resolving it blindly.

Confirm `git config user.name`/`user.email` are correct. Same commit
discipline as prior modules.

## Product decision (locked)

The end product will eventually cover web, mobile, and a
WhatsApp/messaging integration, but they're being built in that order,
one at a time — not simultaneously and not as three half-built
surfaces. This module builds **the web app only**. Do not scaffold
mobile (React Native/Flutter) or messaging-bot code in this module —
that's Module 16+/future scope. If this isn't already recorded, write a
short ADR (`decisions/0013-frontend-platform-sequencing.md`) stating
this decision and the order (web now, mobile next, WhatsApp/messaging
after) so it's not re-litigated later.

## Scope

A web frontend for farmers/extension workers that talks only to Module
11's Flask API (`specs/core/openapi.yaml` is the contract — don't call
`DecisionEngine` or any model class directly, ever). Given the
capstone's evaluators and demo context, prioritize something that
actually runs and demonstrates the full pipeline (advisory retrieval,
explanation, Kannada voice output) over a large untested feature
surface.

## Tasks

### 1. Stack choice — write it down
Pick a stack appropriate for a solo-built capstone frontend that needs
to be demoable, not production-scaled: a lightweight framework you can
actually finish (e.g. a Flask-templates + minimal JS approach reusing
the same backend process, or a small React/Vite SPA — your call, but
justify it in terms of what's achievable well before Nov 14, not what's
trendiest). Document the choice and why in the ADR from the product
decision above, or a separate short note if that ADR is only about
sequencing. State clearly whether this is a separate deployable service
or served by the same Flask app as Module 11 — check `decisions/` for
anything Module 15 (deploy) will need to know about this.

### 2. Structure
- If a separate app: `frontend/` at repo root, its own README for
  install/run steps, added to root `.gitignore` for `node_modules`/build
  output as needed.
- If served by Flask: `src/agro_mirai/api/templates/` +
  `src/agro_mirai/api/static/`, new route(s) added to serve pages —
  additive to `app.py`'s blueprints, not a rewrite of Module 11's API
  routes.

### 3. Core screens/flows
- Farmer/field selection (or a simple hardcoded single-farmer view,
  consistent with ADR 0003's single-tenancy decision — don't build
  multi-tenant UI for a single-tenant backend).
- Advisory view: calls `GET /fields/{id}/advisories` (or the
  recommendation/irrigation/disease-risk endpoints individually — match
  whatever Module 11 actually exposes, check the routes yourself rather
  than assuming), displays the crop recommendation, irrigation advice,
  and disease risk together with their explanations (from
  `ExplanationService`'s `summary_en` — surface `summary_kn` too if
  present, don't hide the Kannada-language support Module 09/12 built).
- Feedback submission: a simple form hitting `POST /feedback` — check
  `routes/feedback.py`'s actual required fields before building the
  form; don't guess.
- If Module 12's `VoiceService` TTS is reachable in this environment
  without adding heavy runtime deps to the deploy target, a "listen in
  Kannada" button is a nice-to-have, not required — don't block the
  module on wiring live AI4Bharat inference into a browser flow if it's
  not straightforward; note it as a known limitation instead of forcing
  it in.

### 4. Auth
The frontend needs to send `Authorization: Bearer <API_KEY>` to Module
11's API. For a capstone demo, hardcoding/env-configuring a single key
client-side (or proxying through a thin backend route that holds the
key server-side) is fine — pick whichever is simpler for your stack and
say which you chose and why in the handoff. Don't build a login system;
that's out of scope per ADR 0003.

### 5. Tests — three explicit stages, report each separately
- **Unit**: whatever unit-testable logic exists (form validation,
  response-shape handling, any JS/Python helper functions) — appropriate
  to whatever framework you pick; if the stack is mostly templates with
  little testable logic, say so honestly rather than padding this
  section.
- **Integration**: an end-to-end check that the frontend's calls to the
  API actually work against a running instance of Module 11's Flask app
  (real `DecisionEngine`, fixture data) — at minimum a scripted
  request/response check per screen's API calls; a full browser-driven
  test (e.g. Playwright) if the stack supports it easily, but don't
  block the module on standing up a browser test harness if that's
  disproportionate effort for a capstone timeline.
- **Acceptance checklist**:
  - [ ] Advisory view renders real data for farm-001's field, matching
        what `GET /fields/{id}/advisories` actually returns
  - [ ] Feedback form successfully posts and the entry is retrievable
        via the `DataStore` afterward (manual or scripted check)
  - [ ] The app runs from a clean checkout following the README's
        install/run steps (actually try this, don't assume)

### 6. Update doctrine
`modules/14-frontend/STATUS`, `CLAUDE.md` phase (note this ran in
parallel with M13), `PROGRESS.md` row 14, `python tools/update_state.py`,
`python tools/check_specs.py`, commit and push. Before your final push,
`git pull` and resolve/report anything from M13 that landed while you
were working.

## Definition of done
- [ ] ADR recording the web-first/mobile-next/WhatsApp-later sequencing
      decision and the stack choice
- [ ] Web app calls Module 11's API exclusively — no direct model/engine
      imports
- [ ] Core advisory + feedback flows work against real fixture data
- [ ] Unit + integration tests (appropriate to the stack) pass;
      acceptance checklist in handoff
- [ ] Doctrine updated, pushed to `origin/main`, no unresolved conflicts
      with M13's parallel work

## Handoff format
```
Module: 14 — Frontend (Web)
Status: complete | blocked
Stack chosen and why:
Implemented:
Files changed:
Commits made:
Unit tests: <+pass/fail>
Integration tests: <+pass/fail>
Acceptance checklist: <each item, checked or not, with a one-line note>
Known limitations:
Remaining risks:
Conflicts with Module 13: <none | describe>
Next recommended module: 15 — Integration, deploy, docs (after M13 also lands)
```
