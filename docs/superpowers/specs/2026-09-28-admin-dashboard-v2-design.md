# Admin Dashboard v2 (Module 50, Phase 1) — Design

## Context

The current `/v2/admin` API and `web/admin` frontend are deliberately
read-only (`decisions/0017-multi-tenant-v2.md`) — no write routes exist
in `admin_bp` at all, enforced by `tests/api/test_admin_routes.py`
inspecting `app.url_map`. Ritesh has asked for a production-grade,
multi-tab admin dashboard with real write/management actions (farmer
CRUD including hard delete, bug-report triage/resolution), a themed
glassmorphism UI, and real-time visibility into incoming bug reports.
This is a deliberate reversal of ADR 0017's read-only scope, not an
oversight — this spec supersedes that part of 0017 the same way ADR
0023 superseded ADR 0022.

"Manage the entire application" is too broad for one build. This spec
covers **Phase 1 only**: farmers/fields CRUD, bug-report management,
audit logging, the new frontend shell, and the dual-URL requirement.
Phase 2 (service health / deploy status / migration ledger / feature
flags) and Phase 3 (analytics drill-downs, exports) are explicitly out
of scope here and get their own spec later.

## Goals

- Real write actions on farmers/fields/bug-reports from the admin
  dashboard, replacing "read-only observation only."
- Every destructive or mutating action is audit-logged (who, what,
  before/after) and, for deletes, requires typing the target's
  name/id to confirm.
- A rebuilt React + Vite frontend with a themed (glassmorphism, this
  app's existing green/leaf palette), multi-tab layout replacing the
  current vanilla-JS single-file app.
- Real-time (SSE) visibility into new bug reports as they arrive.
- The dashboard is reachable at **both**
  `https://agromirai-admin.vercel.app/` (unchanged) **and**
  `https://agromirai.vercel.app/admin/*` (new) — same deployment,
  reverse-proxied, no second build.

## Non-goals (Phase 1)

- Service health / deploy status / CI visibility (Phase 2).
- Feature-flag management UI (Phase 2).
- Multiple admin accounts / role granularity beyond the existing single
  `role=admin` flag (explicitly deferred per Module 49's "open item").
- Any change to farmer-facing `/v2` auth or mobile app.

## Architecture

```
agromirai.vercel.app/admin/*  --(rewrite)-->  agromirai-admin.vercel.app/*
agromirai-admin.vercel.app    --(rewrite)-->  agro-mirai.onrender.com (Flask backend)
```

Both Vercel entry points are reverse proxies in front of the same
Flask backend (Render) — the session cookie is set per-origin by
whichever host the browser is actually on, so logging in via either
URL works independently. No new backend service, no new Render
deployment.

## Data model (additive)

New table `audit_log`, migration
`migrations/{sqlite,postgres}/010_audit_log.sql`:

```sql
CREATE TABLE audit_log (
  id uuid PRIMARY KEY,
  admin_farmer_id uuid NOT NULL REFERENCES farmers(id),
  action text NOT NULL,          -- e.g. "farmer.delete", "bug_report.resolve"
  target_type text NOT NULL,     -- "farmer" | "field" | "bug_report"
  target_id uuid NOT NULL,
  before_json text,              -- snapshot before the change (NULL on create)
  after_json text,               -- snapshot after the change (NULL on delete)
  created_at timestamptz NOT NULL
);
CREATE INDEX idx_audit_log_target ON audit_log(target_type, target_id);
CREATE INDEX idx_audit_log_created_at ON audit_log(created_at);
```

No changes to any existing table's shape — pure addition, per hard
rule 2.

## API (additive to `/v2/admin`)

All routes stay behind `@require_admin`. New routes:

- `PATCH /v2/admin/farmers/{id}` — edit name/district/state/language/etc.
- `DELETE /v2/admin/farmers/{id}` — hard delete, cascades (existing FK
  cascade behavior — fields/scans/advisories/feedback tied to that
  farmer). Requires `?confirm=<farmer_name_or_id>` matching exactly, or
  the request is rejected with 400 — the actual confirmation UX lives
  in the frontend modal, this is the server-side backstop.
- `PATCH /v2/admin/fields/{id}` — edit field attributes.
- `DELETE /v2/admin/fields/{id}` — hard delete.
- `PATCH /v2/admin/bug-reports/{id}` — status transitions
  (`open` → `triaged` → `in_progress` → `resolved`).
- `DELETE /v2/admin/bug-reports/{id}` — hard delete.
- `GET /v2/admin/audit-log` — paginated, filterable by target_type/id.
- `GET /v2/admin/stream/bug-reports` — SSE stream; emits a new event
  each time a bug report is inserted (polling the DB internally on the
  server side at a short interval — no new message-bus infra needed at
  this project's scale — and diffing against the last-seen id).

Every write route is wrapped by one `@audit_logged(action, target_type)`
decorator (`src/agro_mirai/api/audit.py`, new) that captures the
before-state (a `to_json`/`dataclasses.asdict` snapshot, same
serialization already used elsewhere in this module), performs the
handler's action, captures after-state, and writes one `audit_log` row
— so audit logging is enforced structurally, not something each route
has to remember to call.

`bug_reports` currently has no status/lifecycle column — this needs an
additive `status` column (`open` default) in the same
`010_audit_log.sql` migration (or a sibling `010b`), since it didn't
exist before this module and Module 49's migration only created the
table itself.

## Frontend

`web/admin` is rebuilt as a React + Vite app (replacing
`admin.js`/`index.html`/`style.css`, keeping `dev-server.mjs`'s role —
adapted to `vite dev --proxy`). Vite `base: "./"` (relative), so the
same build works unprefixed at `agromirai-admin.vercel.app/` and
prefixed at `agromirai.vercel.app/admin/`.

Tabs (React Router, hash- or path-based within the SPA):
- **Overview** — unchanged content from today (farmer/field counts,
  crop/language breakdown, recent activity), reskinned.
- **Farmers** — list + detail + edit form + delete (confirm modal).
- **Fields** — list + edit + delete.
- **Bug Reports** — list, live-updating via the SSE endpoint, status
  dropdown per row, delete.
- **Feedback** — unchanged content, reskinned.
- **Audit Log** — read-only table of every action taken through this
  dashboard.

Visual: glassmorphism cards (translucent panels, backdrop-blur) over
this app's existing green/leaf theme — extending `style.css`'s current
palette rather than replacing it. No new design-system dependency;
plain CSS (or CSS modules) is enough at this scope.

## Auth / audit trail

No change to session auth (Module 19's cookie-based `require_admin`).
Since there is currently one shared admin account, every audit-log row
attributes to that one `admin_farmer_id` — acceptable for Phase 1 per
Module 49's "note as open item" decision on multiple admins; the
`audit_log` schema already supports per-admin attribution for free
whenever that changes.

## Testing

- Backend: one test per new write route — success path, a cross-tenant/
  not-found path (404, not leaked, matching this project's existing
  isolation convention), and an assertion that the corresponding
  `audit_log` row was written with the right before/after snapshot.
  One dedicated test for the farmer-delete cascade (fields/scans/
  advisories/feedback actually gone afterward). One SSE smoke test
  (connect, insert a bug report directly via the store, assert an event
  arrives).
- Frontend: no pytest coverage (JS/React) — verified live in the
  browser pane against a real dev/staging build, per this project's
  existing UI-testing convention (`CLAUDE.md`: "start the dev server and
  use the feature in a browser before reporting complete").
- `check_specs.py`: `specs/core/openapi.yaml` gains the new paths,
  validated same as every prior module.

## Deployment

- New migration applied via `supabase db push` (or a manual run +
  `migration repair`, matching Module 49's precedent) before the new
  backend code ships, so `PATCH/DELETE` routes don't 500 on a missing
  column/table.
- `web/admin` redeploys via `vercel deploy --prod` as before.
- `web/landing/vercel.json` gains the new redirect + rewrite (no
  redeploy-order dependency — additive config).

## Known limitations (documented up front, not discovered later)

- Single shared admin account — no per-admin login yet, so "who did
  this" in the audit log always shows the same account until a
  multi-admin scheme exists (open item, unprompted expansion explicitly
  avoided per Module 49).
- SSE via short-interval DB polling, not a true pub/sub — fine at this
  project's scale (handful of admins, low bug-report volume), would
  need revisiting if that changes.
- Hard delete really deletes — the type-to-confirm + audit log is a
  safety net, not a recovery mechanism; there is no "undo" or trash/
  restore in Phase 1.
