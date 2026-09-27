# MODULE 48 — Landing page redesign, production-grade admin dashboard, full CLI-integrated deployment

Continuing AGRO MIRAI. Module 47 committed, pushed, and device-verified
the mobile redesign. This module does NOT touch the mobile app further —
it covers three things Ritesh explicitly grouped together: a landing page
refresh, a proper bird's-eye admin dashboard, and confirming the whole
stack (frontend, backend, database, deployment, auth) is genuinely wired
together end to end via each service's own official CLI, production-
grade, not hand-wired or dashboard-clicked together.

This is a big module — Ritesh's own words: "this might be... a really big
task." Work through it in the order below; don't let the admin dashboard
or landing page work start before the integration audit in item 1
confirms what's actually true today, so you're not redesigning on top of
an assumption that turns out wrong.

## 1. Full CLI-integrated production audit, first

Before redesigning anything, confirm the real current state of every
piece, using each service's own CLI (not dashboard click-paths, per
`CLAUDE.md`'s CLI-first rule):

- **Frontend (mobile)**: confirmed via Module 47 — real build, real APK,
  real device verification. Note its current state here for reference,
  don't re-verify.
- **Landing page**: check via Vercel CLI what's actually deployed right
  now, which commit it's built from, whether it's stale relative to
  `main`.
- **Admin dashboard** (`web/admin`): same — check via Vercel CLI what's
  deployed, whether `BACKEND_HOST` (from Module 38's follow-ups) points
  at a real, permanent backend or a since-dead tunnel/placeholder.
- **Backend**: check via the Render CLI the real current state of all
  deployed services (`agro-mirai` main API, `agro-mirai-cnn`; confirm
  whether `agro-mirai-tabular` is really gone per Module 44's audit
  finding, and if so, confirm `RemoteCropModel`/`RemoteIrrigationModel`
  are correctly falling back to local models, not silently erroring).
  Confirm env vars are complete (cross-check against `.env.example` and
  Module 45's Sarvam-key fix — confirm those keys are still set after any
  subsequent redeploys).
- **Database**: confirm via Supabase CLI the real current schema state,
  that migrations are fully applied, and that production is genuinely
  using Supabase (not accidentally SQLite) — Module 36 flagged a real
  footgun here before (a placeholder `SUPABASE_URL` silently switching
  modes); re-confirm that's still fixed.
- **Auth**: confirm end to end, live, via CLI/curl — farmer OTP login,
  admin login, session cookies, and the real security gap Module 44 found
  (OTP printed to server logs, no SMS provider) is still accurately
  documented as an open item, not something to silently leave undocumented.
- **CI/CD**: confirm GitHub Actions (test suite, `check_specs.py`, the
  keep-alive cron from Module 41) are all still green against the latest
  push from Module 47.

Write the findings into a short section of `docs/PPT_VS_CODE_AUDIT.md`
(extend Module 44's audit rather than starting a new doc) so this becomes
one running source of truth, not a scattered set of one-off reports.

## 2. Landing page modifications

- Read the current landing page content/design before changing it — this
  is a modification pass, not a rebuild from scratch, per Ritesh's own
  phrasing ("do some modifications").
- Confirm with Ritesh (ask directly if not obvious from context) exactly
  what's wrong with the current landing page before redesigning — don't
  assume; Module 43's lesson (ambiguous "fix the UI" requests need a
  concrete before/after) applies here too.
- Whatever changes are made, confirm the deployed Vercel URL reflects them
  live, via the Vercel CLI, not just a local preview.

## 3. Production-grade admin dashboard, bird's-eye view

Module 38 already built a real, working admin dashboard (farmer list,
farmer detail, aggregate stats, reusing `/admin/login` auth). This module
extends it into the detailed "bird's-eye view" Ritesh wants:

- A real overview/summary view: total farmers, total fields, total scans,
  language distribution, crop distribution, recent activity — real data
  from real `/v2/admin/*` endpoints (extend the backend with new
  read-only admin routes if a needed view genuinely doesn't exist yet —
  additive-only per `CLAUDE.md`, and keep them read-only, matching Module
  19's original design decision that this surface has zero write routes).
- Scans/advisories per farmer, if not already exposed — Module 38's
  follow-up flagged this as a real gap ("Scans run: Not available") since
  no admin route existed for it. Close it now if Ritesh confirms he wants
  it.
- Confirm auth, hosting, and the real backend connection are all
  production-grade per item 1's audit — no tunnel dependency, no
  placeholder `BACKEND_HOST`.
- Real live proof: log in, screenshot each view with real data, same
  standard as every prior admin-dashboard module.

## 4. Confirm the whole thing is genuinely production, not hand-wired

- Re-run through the full user journey once, end to end, entirely against
  production URLs — mobile app (real APK) -> real backend -> real
  database -> admin dashboard shows what the mobile app just did. This is
  the actual proof that "frontend, backend, database, deployment are all
  integrated," not a description of it.
- Document any piece that's still hand-wired, temporary, or dependent on
  Ritesh's laptop being on, plainly, in the handoff — don't let this
  module close on an implied "it's all production" if something still
  isn't.

## What NOT to do

- Don't touch the mobile app itself in this module (Module 47 already
  closed that).
- Don't burn Sarvam voice quota in any of this verification.
- Don't silently add write routes to the admin surface — read-only stays
  read-only unless Ritesh explicitly asks otherwise.

## Handoff format

```
Module: 48 — Landing page, admin dashboard, full production integration
Status: complete | blocked | needs-decision

CLI-verified production state:
  Landing page (Vercel): <deployed commit, live URL confirmed>
  Admin dashboard (Vercel): <deployed commit, BACKEND_HOST confirmed>
  Backend (Render): <services confirmed, env vars confirmed>
  Database (Supabase): <schema/migrations confirmed, prod mode confirmed>
  Auth: <farmer + admin login confirmed live>
  CI/CD: <confirmed green>

Landing page changes: <what changed, why, live URL check>

Admin dashboard (bird's-eye):
  New views added: <list>
  Live proof: <screenshots with real data>

End-to-end production proof: <mobile -> backend -> db -> admin dashboard,
  confirmed against real production URLs only>

Still not fully production (if anything): <honest list>

Known limitations:
Next recommended step:
```
