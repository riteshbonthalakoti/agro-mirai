# MODULE 39 — Stop and prove it works, with Ritesh actually watching

Continuing AGRO MIRAI. Read this whole module before doing anything. This
is not a feature module. Every prior "complete" report in this project has
been verified by you (Claude Code) alone — curl calls, pytest, your own
screenshots, your own description of what you saw. Ritesh has now said,
directly and honestly, that as an actual user tapping through the real
app, he has never personally seen any of this work: not the three trained
models, not weather data, not soil data, not satellite/GEE data, nothing,
on the mobile dashboard. He also thinks the UI looks overdesigned, not
minimalistic — that's real feedback but it comes second, after
functionality is proven, not before.

This module has exactly one goal: close the gap between "Claude Code says
it works" and "Ritesh has seen it work with his own eyes." Nothing is done
in this module until Ritesh has personally confirmed it, not until you've
tested it internally.

Pause everything else — no admin dashboard work, no Render, no new
features, no UI redesign — until this module is closed.

## 0. Ground rules for this module specifically

- Do not report anything as "confirmed" or "working" based on your own
  curl/pytest/internal testing in this module. That kind of testing is
  fine for finding bugs, but the definition of done here is Ritesh
  physically seeing it on his phone and saying so.
- If something breaks, fix it, then have Ritesh re-check it — don't fix it
  and mark it done based on your own retest.
- Be completely honest in the handoff about what Ritesh has and hasn't
  personally verified. If he only got through half the checklist, say so.

## 1. Truly clean slate

- Uninstall the app entirely from Ritesh's phone (not just force-close —
  actually uninstall, clear app data).
- Build and install a genuinely fresh copy (dev client or release APK,
  whichever is faster to iterate on right now — your call, just say which).
- Confirm the backend Ritesh's phone will talk to is actually running and
  reachable from his phone before he opens the app (don't let "can't
  reach server" be mistaken for "feature broken").

## 2. Walk through the real user flow together, step by step

Do this live, with Ritesh tapping on his own phone while you watch/guide
(screen share, or you narrating steps and him reporting back what he sees
— whatever's practical). At each step below, Ritesh states out loud/in
writing whether he personally saw real data or not. Do not move to the
next step until the current one is either confirmed working by Ritesh or
logged as a real bug.

- Fresh signup / OTP login as a new or existing farmer — does it work
  without errors, from Ritesh's actual phone, on his actual network?
- Add a field with real inputs (location, soil type, sowing date, crop) —
  does it save without error?
- Open the field's dashboard — does Ritesh see actual weather data (not
  a blank section, not a spinner forever, not a placeholder)? Real numbers
  he can sanity-check (today's temp, recent rainfall)?
- Does he see actual soil data (chemistry and/or moisture, labeled with
  its real source — SoilGrids vs. fallback, per the existing
  `soil_source` work)?
- Does he see actual satellite/NDVI/GEE-derived data, or a clear
  "processing" state if it's still backgrounding, not silence?
- Does he see a real crop recommendation, and can he open its explanation
  (the SHAP-based rationale)?
- Does he see a real irrigation recommendation with a real depth/urgency,
  not stuck on the sowing-date bug from before?
- Does he run a real disease scan (upload or take a photo of a leaf,
  anything) and get back a real result — either the CNN path or the
  documented environmental-fallback path, clearly labeled which one?
- Is any of this in a language other than what he expects, or missing
  translation, per the earlier i18n work?

For every "no" above: root-cause it for real (don't guess), fix it, then
have Ritesh re-check that specific step before moving on.

## 3. The three trained models specifically

Ritesh said directly he has never personally confirmed the three models
(crop recommendation, irrigation, disease-risk) produce real predictions
inside the actual running app — only that notebooks or backend tests
produced numbers. Close that gap explicitly:

- For each of the three, show Ritesh the real prediction appearing in the
  actual app UI (not a notebook, not a curl response) tied to a real or
  realistic input he provided.
- If a model's output genuinely isn't reachable from the app UI yet (wired
  to the backend but never actually rendered anywhere a user sees), that
  is the bug — fix it, this is exactly the kind of gap this module exists
  to catch.

## 4. Only after functionality is confirmed: note the UI complaint

Do not act on the "UI looks overdesigned, not minimalistic" feedback in
this module — record it precisely (which screens, what Ritesh specifically
found overdone) so a future, dedicated UI module can address it with clear
direction instead of guessing. Fixing UI before functionality is confirmed
would waste effort on screens that might still be showing broken data.

## What NOT to do

- No admin dashboard, Render, notebooks, or landing page work.
- No UI redesign yet — just capture the complaint precisely.
- No claiming anything is "done" based on internal testing alone in this
  module.

## Handoff format

```
Module: 39 — Real manual verification with Ritesh
Status: complete | blocked | needs-decision

Clean install: <confirmed, method used>
Backend reachability from Ritesh's phone: <confirmed>

Walked through with Ritesh, per step — for each, Ritesh's own verdict:
  Signup/login: <Ritesh confirmed working / bug found + fixed + reconfirmed>
  Add field: <same>
  Weather data visible: <same>
  Soil data visible: <same>
  Satellite/NDVI data visible: <same>
  Crop recommendation + explanation visible: <same>
  Irrigation recommendation visible: <same>
  Disease scan result visible: <same>
  Language/translation correct: <same>

Three models — real in-app predictions Ritesh personally saw:
  Crop recommendation: <confirmed by Ritesh, or still not reachable in UI>
  Irrigation: <same>
  Disease risk: <same>

Bugs found and fixed this module: <list, root cause + fix for each>
Still broken / not yet reconfirmed by Ritesh: <honest list, do not omit>

UI complaint captured (not acted on): <specific screens/issues Ritesh named>

Next recommended step:
```
