# MODULE 38 — FOLLOW-UP 2: deploy the backend to Render, point the dashboard at it

Continuing AGRO MIRAI. Module 38 and its first follow-up are closed: the
admin dashboard is real, verified against real Supabase data, and live at
https://agromirai-admin.vercel.app through a cloudflared tunnel to the
laptop. Ritesh has now chosen Option B from that follow-up's hosting
findings: deploy the Flask backend itself to Render's free tier, so the
dashboard (and basic API routes) work without the laptop running.

This is still admin-dashboard/backend-hosting scope, not a new module. Do
not touch mobile, notebooks, or the landing page here.

## 1. Install and authenticate the Render CLI

- Install Render's CLI (`render` — check Render's current install docs for
  the right method, don't assume a package name from memory).
- Authenticate it to Ritesh's Render account. If Ritesh doesn't have a
  Render account yet, stop and tell him exactly what to do (sign up at
  render.com, free tier, no card should be required for the free web
  service tier — confirm this is still true before telling him it is).
- Confirm the CLI actually works (`render whoami` or equivalent) before
  proceeding.

## 2. Deploy the Flask backend as a Render free-tier web service

- Be explicit up front, in the handoff, about what this deployment can and
  can't do — restate Module 38's own findings: the Flask API + Supabase
  should work fine; the voice stack (IndicTrans2/Piper) and CNN inference
  will not fit in Render free tier's ~512MB RAM and are expected to fail or
  need to be disabled/stubbed for this deployment. Don't try to force them
  to fit — if a route needs them, it should degrade the same
  try/except-and-report way the rest of this codebase already does, not
  crash the whole service.
- Create the Render web service (via CLI or a `render.yaml` blueprint,
  whichever is cleaner — check both are real, current Render features
  before picking).
- Set every env var Render needs from the real `.env.example` (Module 36
  made this complete and accurate) — Supabase URL/key, GEE service account
  key, OpenWeatherMap/whatever weather key is actually used, etc. Do not
  put real secret values in any committed file — set them through Render's
  env var config (CLI or dashboard), the same way `.env` already isn't
  committed.
- Confirm `FLASK_ENV=production` or whatever setting makes the app run in
  production mode is set correctly for a real hosted deployment (this
  affects the session cookie behavior noted in the last handoff).
- Deploy. Watch the build/deploy logs for real, don't assume success —
  confirm the service actually starts and stays up (Render free tier
  spins down after ~15 min idle — note the real first-request cold-start
  time you observe, don't estimate it).

## 3. Verify the Render-hosted backend for real

- Hit its real `/health` endpoint (or equivalent) from outside — confirm
  a real 200, not just "the Render dashboard says running."
- Hit a real data-bearing route (`/admin/login` then an `/v2/admin/*` read)
  against the Render-hosted backend and confirm it returns Ritesh's real
  Supabase data — same data the tunnel path already proved works.
- Explicitly test one of the routes expected to be degraded (disease-risk
  image upload if the CNN needs weights that won't be on Render, or a
  voice/audio endpoint) and confirm it degrades honestly (a clear
  error/fallback) rather than crashing the whole service or hanging.

## 4. Point the dashboard at the permanent Render URL

- Update `vercel.json`'s `BACKEND_HOST` to the real Render service URL (not
  a placeholder, not the old tunnel host) and redeploy the dashboard.
- Confirm the live `agromirai-admin.vercel.app` URL now loads real data
  through Render, with the laptop, Flask on :5002, and cloudflared all
  fully OFF — this is the actual point of the exercise, so don't skip
  turning them off before confirming.
- If the dashboard still needs the laptop for anything (a specific route
  Render can't serve), say exactly which one and why.

## 5. Update the docs

- `BACKEND.md` / `DEMO_SETUP.md` (if it exists yet) / `vercel.json`
  comments — wherever makes sense — should now state plainly: the API and
  admin dashboard can run on Render alone; full model functionality (crop
  rec if it depends on anything heavier, irrigation, disease-risk CNN
  path, voice) still needs the laptop running locally and pointed at by
  whatever's demoing, exactly as Module 38's original hosting-reality
  section said. Don't overstate what Render now covers.

## What NOT to do

- Don't try to cram the voice stack or CNN weights onto Render free tier
  through workarounds (quantization hacks, external model APIs not already
  in this project, etc.) — if it doesn't fit, say so plainly, same
  standing instruction as before.
- Don't touch mobile, notebooks, or the landing page.
- Don't commit any real secret value anywhere, including `render.yaml` if
  you use one — env values only through Render's own env var mechanism.

## Handoff format

```
Module: 38 (follow-up 2) — Render backend deployment
Status: complete | blocked | needs-decision

Render CLI: <installed, authenticated, confirmed working>
Render account: <existing / newly created by Ritesh — confirm free tier, no card>

Backend deployed to Render:
  Service URL: <real URL>
  Env vars set: <list, no values>
  Build/deploy: <confirmed successful, real log evidence>
  Cold start observed: <real seconds, not estimated>

Verification:
  /health: <real response>
  Real Supabase data through Render: <confirmed, what was checked>
  Degraded route tested: <which one, honest degrade confirmed>

Dashboard repointed:
  BACKEND_HOST updated to Render URL: <confirmed>
  Redeployed: <confirmed>
  Live check with laptop/tunnel fully OFF: <confirmed, what still needs the laptop if anything>

Docs updated: <what, where>

Known limitations:
Next recommended step:
```
