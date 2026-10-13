# 0030 - Admin dashboard v2: real write actions, audit log

Status: accepted and deployed, 2026-09-28. Supersedes the read-only-scope part of 0017 (section 4).

## Why

Ritesh asked for a production-grade admin dashboard that can actually manage the
application — edit/delete farmers and fields, triage bug reports — not just observe it.
0017's read-only scope was a deliberate Module 19 decision, not an oversight, but it's
being deliberately reversed here at Ritesh's explicit request (Module 50).

## What changed

- `/v2/admin` gained real write routes: `PATCH`/`DELETE` on `farmers/{id}` and
  `fields/{id}`, `PATCH`/`DELETE` on `bug-reports/{id}`, plus `GET bug-reports` and
  `GET audit-log`. All still gated by the existing `require_admin` session check —
  no new auth mechanism.
- `DataStore` gained 8 new admin-only, unscoped methods (same convention as the
  existing `list_all_farmers`/`list_all_fields`): `delete_farmer`, `get_field_by_id`,
  `list_all_bug_reports`, `get_bug_report_by_id`, `update_bug_report_status`,
  `delete_bug_report_by_id`, `save_audit_log_entry`, `list_audit_log`. Implemented in
  both `SQLiteDataStore` and `SupabaseDataStore`.
- A new `audit_log` table (additive migration, `migrations/{sqlite,postgres}/010_admin_write_actions.sql`)
  records every write: who (`admin_farmer_id`), what (`action`, `target_type`,
  `target_id`), and before/after JSON snapshots. `src/agro_mirai/api/audit.py`'s
  `write_audit_log` helper is called explicitly from each route — not a decorator,
  since a generic decorator would still need per-route "how do I fetch the target"
  logic anyway, so an explicit call is no less DRY and is easier to read at each
  call site.
- `bug_reports` gained an additive `status` column (`open` default), with a new
  `bug_report_status` enum (`specs/core/enums.md`).
- Farmer/field PATCH routes use an explicit field whitelist
  (`_FARMER_PATCHABLE`/`_FIELD_PATCHABLE`) so an admin can't smuggle in `role` or
  `id` via a PATCH body — verified by a dedicated test, not just code inspection.

## What did NOT change

- Auth mechanism: still the single session-cookie `require_admin` check from Module 19.
  No per-admin API keys, no new roles, no multi-admin attribution beyond the one
  shared admin account (still a known limitation — see Module 49's "open item").
- Destructive-action safety: hard delete really deletes. The frontend's
  type-to-confirm modal is the UX safety net; the server-side backstop is the
  audit trail plus the existing 404-on-missing behavior — there is deliberately no
  server-side "confirmation token" requirement, since `require_admin` is already
  the real access control and a second confirmation layer at the API level would
  just be UX-in-the-backend for no additional security.
- Cascade behavior: `delete_farmer` relies on the schema's existing
  `ON DELETE CASCADE` foreign keys (fields/bug_reports/feedback/etc already
  reference `farmers.id` this way since Module 19/49) — no new cascade logic was
  written.

## Known limitations

- Single shared admin account — every audit-log row attributes to the same
  `admin_farmer_id` until a real multi-admin scheme exists. The `audit_log` schema
  already supports per-admin attribution for free whenever that changes.
- `patch_farmer`'s whitelist includes `phone` with no format/uniqueness validation
  (unlike registration's phone validation) — an admin could set a duplicate or
  malformed phone via PATCH, breaking that farmer's OTP login until corrected.
  Deferred: this is internal admin-only tooling at a small farmer-base scale today;
  revisit if/when this dashboard has more than one admin or a larger user base.
- The SSE bug-report stream (`GET /v2/admin/stream/bug-reports`) polls the database
  every few seconds rather than using real pub/sub — fine at this project's scale,
  would need revisiting if bug-report volume or admin count grows significantly.

## Deployment proof (2026-09-28)

Deployed the same day as design: `supabase db push` applied the
migration live (a real gap was found here — see `PROGRESS.md`'s Module
50 entry — the CLI-tracked `supabase/migrations` file didn't exist
yet, only this project's own `migrations/postgres/*.sql` convention
did); Render auto-deployed the backend on push; a new CD pipeline
(`docs/TOOLING.md`'s "CI/CD (Module 50)" section) auto-deployed both
Vercel frontends. Verified live, not just in a test suite: logged into
`agromirai-admin.vercel.app` with the real admin account, changed a
real bug report's status through the dashboard, and confirmed via the
Supabase client that the `bug_reports` row and a matching `audit_log`
row (correct before/after JSON, correct `admin_farmer_id`) both landed
in production — the write-path proof the Module 48 audit flagged as
missing.
