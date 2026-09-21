# MODULE 38 — Admin dashboard (standalone)

Continuing AGRO MIRAI. This module is the admin dashboard only. Don't touch
the backend logic, mobile app, notebooks, or landing page here — Module 36
(backend handover) and Module 37 (mobile offline fix) are already closed.
No offline mobile work, no model-hosting docs, no APK packaging — those are
separate, later modules if/when Ritesh asks for them.

Goal: a real, working, birds-eye admin dashboard a faculty member or team
member can open and see actual farmer/field/scan data from the live
backend — built like a real product team would at zero infra cost for a
capstone, not mocked.

## 1. Stack and hosting

- A simple web dashboard, separate from the mobile app. Match the landing
  page's existing approach (plain HTML/CSS/JS) unless there's a real reason
  to add a lightweight framework — state that reason if you do.
- Deploy it to the same free Vercel project (or a new free one) the landing
  page already uses.
- Talk to the existing `/v2/admin/*` routes — these are already real and
  tested (Module 32/33). Do not rebuild auth or add new backend routes in
  this module; if a view genuinely needs a route that doesn't exist yet,
  flag it as needs-decision rather than quietly adding backend code.

## 2. Auth

- Reuse the existing real admin session-cookie auth (`POST /admin/login`),
  already proven live. Don't invent a second auth system or a client-side
  password check.

## 3. Core views — real data only

- Farmer list: search/filter, real data from `/v2/admin/*`.
- Farmer detail: their fields, scan history, advisories.
- Aggregate stats: total farmers, total fields, total scans run, language
  distribution.
- No mocked/hardcoded placeholder data anywhere — if a view can't get real
  data from an existing endpoint, say so rather than faking it.

## 4. Backend free-tier hosting reality check

Right now the backend only runs on Ritesh's laptop. For the dashboard to be
usable by anyone else without his laptop on, the backend itself would need
to be hosted somewhere. State plainly, as a factual finding (don't attempt
to actually migrate hosting in this module):

- Whether Render/Railway/Fly.io free tiers could realistically run this
  Flask backend today — real current limits, cold-start behavior, and
  specifically whether the GEE service account, voice stack, and CNN
  inference would work under those limits or need the laptop regardless.
- This is a hosting-reality writeup only, separate from actually deploying
  anything — don't spend this module standing up new infra.

## 5. Prove it live

- Real login to the dashboard using the real admin credentials.
- Real farmer list showing real farmers already in the system (from prior
  live-tested modules).
- Click into a real farmer, show their real fields/scans/advisories.
- Screenshot each of these three things.

## What NOT to do

- No backend route changes — read-only consumer of `/v2/admin/*` as it
  exists today.
- No mobile app changes.
- No landing page changes.
- No model-hosting migration, no APK work, no DEMO_SETUP.md — later,
  separate modules.
- Same standing rules as always: short plain human commit messages, no
  AI-attribution anywhere, ordinary comment style.

## Handoff format

```
Module: 38 — Admin dashboard
Status: complete | blocked | needs-decision

Stack: <what was built>
Hosting: <where deployed, URL>
Auth: <confirmed reuses /admin/login>

Views:
  Farmer list: <real data confirmed>
  Farmer detail: <real data confirmed>
  Aggregate stats: <real data confirmed>

Backend free-tier hosting reality: <viable or not, why, real limits cited>

Live proof:
  Login: <screenshot>
  Farmer list: <screenshot>
  Farmer detail: <screenshot>

Known limitations:
Next recommended step:
```
