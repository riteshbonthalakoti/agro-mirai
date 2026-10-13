# DEMO_DAY.md — before you present

## Deployed URL

**`<fill in after the Render Blueprint is applied — see below>`**

The service is provisioned from `render.yaml` (a Render Blueprint) —
see `decisions/0014-deploy-target-and-voice-scope.md` for what it runs
and why. Deploying it is the one step in this module that needs a
human in a browser (connecting the GitHub repo to Render's GitHub App
is an OAuth-style authorization, not something the CLI can complete
headlessly):

1. `git push origin main` (get all of Module 15's commits up).
2. https://dashboard.render.com/blueprints → **New Blueprint Instance**
   → connect the `riteshbonthalakoti/agro-mirai` repo (installs Render's
   GitHub App on first use if not already installed) → Render reads
   `render.yaml` from the repo root automatically.
3. Fill in the env vars the blueprint marks `sync: false` (Render will
   prompt for each): `API_KEY` (pick a real secret — this becomes what
   `MANUAL_TEST_GUIDE.md`'s `curl` examples call `$KEY`), `FARMER_ID`
   (the seeded farmer's UUID — see step 4), `SUPABASE_URL` /
   `SUPABASE_KEY` (from the existing project, ref `yzsemdauwafxssaknlzr`
   — `supabase projects api-keys --project-ref yzsemdauwafxssaknlzr`),
   `FLASK_SECRET_KEY` (any random string).
4. **Seed Supabase before or right after first deploy** — the deployed
   instance reads/writes the real Supabase project, not a local SQLite
   file, so it needs the golden fixture loaded there too:
   `python tools/seed_fixture.py --backend supabase` (from your own
   machine, against the same `SUPABASE_URL`/`SUPABASE_KEY`). Use the
   farmer id that script prints as `FARMER_ID` in step 3.
5. Once deployed, run the real smoke test against it:
   ```bash
   AGRO_MIRAI_DEPLOYED_URL=https://<your-service>.onrender.com \
   AGRO_MIRAI_DEPLOYED_API_KEY=<the API_KEY you set> \
   python -m pytest tests/e2e/test_deployed_smoke.py -v
   ```
6. Paste the final URL into this file's first line and into
   `docs/DEMO_SCRIPT.md`.

## Cold-start reality — wake it up before your review

- **Render free tier** spins the service down after a period of no
  traffic. The **first** request after that can take up to **~60
  seconds** to respond while it cold-starts — don't let that happen
  live in front of an evaluator. Hit `/health` from your phone or
  laptop **5-10 minutes before** your review slot starts.
- **Supabase free tier** auto-pauses a project after **7 days with no
  API/DB activity** (documented in `docs/TOOLING.md`). If your review is
  more than a week after your last deploy/demo, restore it first:
  `supabase projects restore yzsemdauwafxssaknlzr` (or via the
  dashboard: project → "Project is paused" banner → **Restore
  project**). A paused Supabase project makes the Render instance's
  `/health` return `"degraded"`, not crash — that degraded state is
  itself a legitimate thing to point at as evidence the repository
  interface (Module 04) is doing its job, but you don't want to
  discover it live.

## What the hosted instance does and doesn't cover

Covers, end to end, against real Supabase persistence: dashboard, field
detail, crop/irrigation/disease recommendations, unified advisory with
explanation, feedback form, the raw JSON API.

Does **not** include live voice inference (Module 12) — that's a
deliberate scope decision for the *hosted* instance, not a project gap;
see `decisions/0014-deploy-target-and-voice-scope.md`. Demo Kannada
voice locally per `MANUAL_TEST_GUIDE.md` §7, or play a pre-recorded
clip if you're not near your own machine during the review — see
`docs/DEMO_SCRIPT.md`.
