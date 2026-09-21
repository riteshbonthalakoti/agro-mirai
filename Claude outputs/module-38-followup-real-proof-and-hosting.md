# MODULE 38 — FOLLOW-UP: real-data proof, admin promotion, backend host decision

Continuing AGRO MIRAI. Module 38's admin dashboard is built, committed
(`26b7d91`) and deployed to https://agromirai-admin.vercel.app, and was
verified end-to-end against a throwaway local test database. Two things are
left before this module is truly closed — both need Ritesh directly for the
credential/decision step, everything else is yours to execute.

## 1. Promote the real admin account

- Follow `MANUAL_TEST_GUIDE.md` step 8 to promote Ritesh's real Supabase
  account to admin. Do this against the real Supabase data, not the
  throwaway test DB.
- Do not create or type Ritesh's real password yourself — either wait for
  Ritesh to type it in the browser pane, or if he tells you to proceed with
  a password he gives you directly in this conversation, use exactly what
  he gives you and don't invent one.

## 2. Real-data live proof

Once the real admin account exists:

- Log in to the dashboard (local dev server against the real backend, or
  the deployed Vercel one once item 3 below is resolved — whichever is
  reachable first) with the real admin account.
- Screenshot: login success, farmer list (should show the real farmer(s) —
  right now that's Ritesh's own Hindi-language account with 1 field —
  don't be surprised if the list is short, that's the real current data,
  not a bug), farmer detail (real fields shown), aggregate stats (real
  counts, even if small).
- If anything breaks against real data that didn't break against the test
  DB (a null field, a missing column, a different date format, etc.), fix
  it — this is exactly the kind of gap a throwaway fixture can hide.

## 3. Backend host decision for the deployed dashboard

`vercel.json` still has a placeholder `BACKEND_HOST` — the deployed
`agromirai-admin.vercel.app` can't reach any backend right now. Two real
options, present both plainly and let Ritesh decide, don't pick silently:

- **Option A — laptop stays the backend, dashboard only works when it's
  on**: use a tunnel (e.g. ngrok, Cloudflare Tunnel) pointed at the
  laptop's Flask process, put that URL in `BACKEND_HOST`, redeploy. Cheapest,
  zero new infra, but the dashboard is dead whenever the laptop/backend is
  off — same constraint the mobile app already has.
- **Option B — deploy Flask to Render's free tier** (per Module 38's own
  hosting-reality findings: viable for the API alone with Supabase as the
  store, ~1 min cold start after 15 min idle, 750 free hours/month). This
  makes the dashboard (and basic API routes) work without the laptop
  running, but voice/CNN/GEE-heavy paths still need the laptop or the
  Oracle VM from Module 21 — state clearly in the handoff that this is a
  *partial* backend, not the full one.
- Whichever Ritesh picks, update `BACKEND_HOST` in `vercel.json`, redeploy,
  and confirm the live `agromirai-admin.vercel.app` URL actually loads real
  data end-to-end (not just a 200 on the static page, like last time).

## What NOT to do

- Don't add new `/v2/admin` routes for scans/advisories in this follow-up —
  that was correctly flagged as needs-decision last time; if Ritesh wants
  it, that's a separate small backend change he should explicitly ask for.
- Don't touch mobile, notebooks, or the landing page.
- Don't fabricate or pad real-data screenshots — a short farmer list is the
  honest current state, not something to work around.

## Handoff format

```
Module: 38 (follow-up) — Real-data proof, admin promotion, backend host
Status: complete | blocked | needs-decision

Admin promotion: <confirmed, how the password was handled>
Real-data live proof:
  Login: <screenshot>
  Farmer list: <screenshot, real counts>
  Farmer detail: <screenshot>
  Aggregate stats: <screenshot>
Bugs found against real data (if any): <what, fix>

Backend host decision: <A (tunnel) or B (Render), why, confirmed by Ritesh>
BACKEND_HOST updated + redeployed: <confirmed>
Deployed dashboard end-to-end check: <confirmed real data loads at the live URL>

Known limitations:
Next recommended step:
```
