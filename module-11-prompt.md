# MODULE 11 — API Layer (Flask)

Continuing AGRO MIRAI in the existing `agro-mirai` repo. Modules 01–10
and 12 are done and committed. Read `CLAUDE.md` and `PROGRESS.md` first.

Confirm `git config user.name`/`user.email` are correct. Same commit
discipline as prior modules.

## Scope

Expose Module 10's `DecisionEngine` (and the underlying models/storage)
behind Flask endpoints that exactly match `specs/core/openapi.yaml`.
This is the only interface Module 14 (Frontend) and Module 13 (Feedback
Loop) will call — everything goes through here, nothing imports the
Python model classes directly from outside the `src/` package after this
module.

## Tasks

### 1. Read `specs/core/openapi.yaml` completely before writing any code
The contract already exists from Module 02. Every endpoint you build
must match it exactly — method, path, request shape, response shape. If
you find a gap (a capability Module 10 now supports that isn't in
openapi.yaml, e.g. an advisory endpoint that's missing), add it to
openapi.yaml first (in its own commit) and note it in the handoff as an
additive change to a pre-existing contract. Don't invent endpoints that
aren't in the spec, and don't silently omit endpoints that are.

### 2. Flask application structure
`src/agro_mirai/api/` package:
- `app.py` — Flask app factory (`create_app(config=None) -> Flask`),
  registers blueprints, initialises the `DataStore` and `DecisionEngine`
  singletons via app context (not module-level globals). Config reads
  from env vars (`FLASK_ENV`, `DATABASE_URL` or equivalent — add to
  `.env.example` any new vars).
- `routes/advisory.py` (or similar) — the advisory/recommendation
  endpoint(s).
- `routes/farms.py` — CRUD for Farmer/Field entities if openapi.yaml
  specifies them; skip if not.
- `routes/feedback.py` — the feedback endpoint stub (Module 13 fills in
  the logic; the route itself should exist and return a 200 with a
  placeholder body so Module 14 can be built against a working API
  from day one, not a 404).
- Error handling: return JSON error responses (not HTML Flask default
  errors) with a consistent `{"error": ..., "detail": ...}` shape for
  400/404/422/500.

### 3. Auth basics
A simple API key check via `Authorization: Bearer <key>` header,
validated against an env var (`API_KEY`). Not OAuth, not JWT — just
enough that the API isn't completely open. Skip endpoints that shouldn't
require auth if openapi.yaml marks them public. Add `API_KEY` to
`.env.example`.

### 4. Tests — three explicit stages, report each separately
- **Unit**: each route handler's response shape for a known input,
  mocking `DecisionEngine.recommend` and the `DataStore` — confirm
  status codes, JSON structure, auth rejection (missing/wrong key →
  401).
- **Integration**: start the Flask test client (`app.test_client()`),
  make real HTTP requests with a real `DecisionEngine` (using the actual
  model artifacts and farm-001/farm-002 fixtures loaded via the
  `DataStore`) — confirm the advisory endpoint returns a schema-valid
  `Advisory` JSON payload end to end.
- **Acceptance checklist**:
  - [ ] `POST /advisory` (or whatever the spec names it) returns a valid
        advisory JSON for farm-001's field ID with real model outputs
  - [ ] Missing auth header returns 401, wrong key returns 401
  - [ ] An unknown field ID returns 404, not a 500
  - [ ] `GET /health` (or equivalent liveness endpoint) returns 200

### 5. Update doctrine
`modules/11-api-layer/STATUS`, `CLAUDE.md` phase → Module 11 complete,
Modules 13 and 14 next (now in parallel), `PROGRESS.md` row 11,
`python tools/update_state.py`, `python tools/check_specs.py`, commit
and push.

## Definition of done
- [ ] All openapi.yaml endpoints are implemented or explicitly noted as
      stubs with a reason — no silent omissions
- [ ] Auth works; JSON errors for all failure cases
- [ ] Unit + integration tests pass; acceptance checklist in handoff
- [ ] Doctrine updated (note in CLAUDE.md that M13/M14 can now start in
      parallel), pushed to `origin/main`

## Handoff format
```
Module: 11 — API Layer (Flask)
Status: complete | blocked
Implemented:
Endpoints: <list each route: method + path + status>
Files changed:
Commits made:
Unit tests: <+pass/fail>
Integration tests: <+pass/fail>
Acceptance checklist: <each item, checked or not, with a one-line note>
Known limitations:
Remaining risks:
Next recommended module: 13 + 14 in parallel (M13: Feedback Loop, M14: Frontend)
```
