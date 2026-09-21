# MODULE 36 — Offline-first mobile, admin dashboard, and final handoff packaging

Continuing AGRO MIRAI (github.com/riteshbonthalakoti/agro-mirai, main @
d771755). Landing page is live (agromirai.vercel.app), three Colab
notebooks are built (not yet run end-to-end — do that first, see item 0).
This module is the final push toward closing the project: fix the
mobile app's total-failure-when-offline bug, build a real admin
dashboard, and package everything for handoff to a five-person team where
only one person can receive code and only one can demo it.

## Standing rules for this module and everything after it (do not ask again)

- **No "Co-Authored-By: Claude" or any Claude/AI attribution anywhere** —
  not in commits, not in code comments, not in the PR/README. This was
  already scrubbed from git history earlier in the project; keep it that
  way going forward.
- **Commit messages: short, plain, human, inconsistent style** — the way
  a student actually types them (lowercase sometimes, no strict
  conventional-commits format, no bullet-pointed commit bodies, no
  "Generated with Claude Code" footers). One line each, plainly describing
  what changed, nothing more.
- **Code comments: plain and ordinary**, the way a 3rd/4th-year CS student
  writes them — not overly thorough, not AI-formal, no
  restating-the-obvious-in-perfect-grammar. Skip comments on trivial
  lines; comment only where a real explanation helps.
- These rules exist because Ritesh is submitting this repo on behalf of a
  5-person student team, most of whom didn't write the code — the repo
  needs to read like normal student work, not like an obviously AI-
  authored capstone. This is about tone and attribution, not about hiding
  that AI tools were used in development generally.

## 0. First: actually run the 3 Colab notebooks end-to-end

Notebooks 1 and 2 need a `kaggle.json` upload and none have been run in a
live session yet — this was flagged as not-yet-done in the last handoff.
Run all three for real, fix anything that breaks on a fresh runtime,
confirm each completes with real output. This is a fast, high-value check
before building anything new — don't let it slip.

## 1. Fix the mobile app's offline failure (highest priority)

Confirmed real, reported directly: with the backend laptop off, opening
the installed app shows a totally blank white screen — no login screen,
no cached data, nothing. This is unacceptable for a real product and an
easy tell that nothing is engineered defensively.

- Root-cause the blank screen first — this is very likely an unhandled
  promise rejection or a render-blocking `await` on a network call with
  no try/catch/fallback at app startup (e.g. a session-check or initial
  data fetch that throws and crashes the render tree instead of degrading
  gracefully). Find the exact failing call.
- Fix the immediate crash: the app must always render *something* — at
  minimum the last-known screen/login state — even with zero network.
  Wrap every startup network call in proper error handling with a clear
  offline fallback path, not a silent hang or crash.
- Build real local persistence, not just a crash fix: cache the farmer's
  session, their fields, and their most recent advisories/scan results/
  records locally on the device (AsyncStorage for small state,
  `expo-sqlite` or similar for structured records — pick whichever fits
  the existing data shapes better, state which and why) so that opening
  the app offline shows real previously-fetched data, clearly marked as
  possibly-stale ("last updated <time>"), rather than either nothing or a
  fake "live" look.
- Define the offline contract precisely and implement it consistently:
  what works with zero network (viewing cached fields/records/advisories,
  browsing previously-seen content) vs. what correctly shows a clear
  "you're offline, connect to do this" state (submitting a new scan,
  adding a field, requesting an OTP) — never a silent failure or an
  infinite spinner for either category.
- Prove it live: real device, real app with real cached data, turn off
  the laptop/backend entirely, force-close and reopen the app, confirm it
  opens straight into a real, useful offline view — screenshot it.

## 2. Admin dashboard — production-grade, birds-eye farmer management

Ritesh's framing: build this like a real product team would, at zero
infra cost, for a prototype/capstone context. Concretely:

- **Stack**: a web dashboard (not part of the mobile app) — a simple,
  real framework choice (plain HTML/CSS/JS matching the landing page's
  approach, or a lightweight framework if the team already has one in the
  stack) deployed to the same free Vercel project or a new one, talking to
  the existing `/v2/admin/*` routes (already real and tested per Module
  32/33 — build on them, don't rebuild auth).
- **Core views**: farmer list (search/filter), farmer detail (their
  fields, scan history, advisories), aggregate stats (total farmers,
  fields, scans run, language distribution) — real data from real
  `/v2/admin/*` endpoints, not mocked.
- **Auth**: reuse the existing real admin session-cookie auth
  (`POST /admin/login`) already proven live — don't invent a second auth
  system.
- **Hosting reality check**: state plainly in the handoff whether the
  Flask backend itself can realistically be hosted on a genuinely free
  tier (Render/Railway/Fly.io free tiers, their real current limits and
  cold-start behavior) for the admin dashboard and basic API routes to
  work without Ritesh's laptop running — this is separate from the ML
  model-hosting question below, and the two shouldn't be conflated in
  the final writeup.

## 3. Model-hosting reality and the local-demo plan — document, don't overbuild

Ritesh's own read is correct: free tiers generally can't run these models
(GEE service account, IndicTrans2/Piper voice stack, CNN inference) at
any real capacity, and building paid infra for a capstone isn't the
right call. Don't try to force free-tier ML hosting. Instead:

- Write a clear, short **DEMO_SETUP.md** at the repo root: exact steps for
  someone unfamiliar with the codebase to start the backend locally
  (`.env.example` with placeholders for every required key, exact
  commands, expected startup log lines confirming success), point the
  mobile app / admin dashboard at their machine's LAN IP, and verify
  end-to-end before a live demo — mirroring exactly the setup steps this
  session has done repeatedly, written for someone with much less context.
- State explicitly in this doc: the landing page and login/browsing work
  from anywhere with the backend hosted on a free tier (if 2 above
  confirms that's viable); full model functionality (crop rec, irrigation,
  disease-risk, voice) requires the demo-runner's laptop to be on and the
  backend running, pointed at by whatever device is demoing.
- Also state clearly which specific things do NOT need the laptop running
  at demo time (viewing the landing page, browsing cached mobile data
  offline per item 1) vs. which DO (any new field/scan/advisory request) —
  this doc is what the 4 non-technical teammates will actually rely on.

## 4. Final packaging for handoff

- **Real signed/buildable APK**: produce a real release APK (or the exact,
  tested command to produce one) pointed at the deployed/hostable backend
  where possible, falling back to the local-LAN setup per item 3 where a
  model needs a local run. Confirm it actually installs and opens on a
  real device.
- **README.md at repo root**, written for the 5-person team, not for
  Ritesh: what the project is, what's live (landing page link), how to
  run the backend locally for a demo (link to DEMO_SETUP.md), how to open
  the APK, credits section listing the actual team members from the PPT.
- Confirm the landing page links correctly to whatever's real and live
  today (the Vercel URL itself is already live — confirm nav/CTA buttons
  on it point where they should, not dead links or placeholders).
- Final repo cleanup pass: confirm `.env`/secrets are genuinely gitignored
  and never committed (this got overwritten with placeholders earlier
  this session more than once — do a final check that the real repo
  history is clean, not just the working tree).

## What to explicitly NOT do

- Don't try to stand up paid infrastructure "for free" through workarounds
  that will break or get flagged (shared free-tier abuse, unofficial GEE
  proxies, etc.) — if something genuinely can't be free and reliable, say
  so plainly in DEMO_SETUP.md rather than building something fragile.
- Don't touch the earlier-parked dashboard/onboarding UI decisions unless
  they're now required for the admin dashboard specifically.

## Handoff format

```
Module: 36 — Offline-first mobile, admin dashboard, final packaging
Status: complete | blocked | needs-decision

Notebooks run end-to-end: <confirmed, any fixes made>

Offline mobile fix:
  Root cause of blank screen: <exact finding>
  Local persistence approach: <AsyncStorage/SQLite, what's cached>
  Offline contract: <what works offline vs. requires connection>
  Live proof: <real device, backend off, real screenshot of offline view>

Admin dashboard:
  Stack/hosting: <what was built, where deployed>
  Views: <what's real and working>
  Backend free-tier hosting reality: <viable or not, why, real limits cited>

Model-hosting plan: <DEMO_SETUP.md written, what needs local run vs. hosted>

Final packaging:
  APK: <built/tested, real device install confirmed>
  README: <written>
  Landing page link check: <confirmed>
  Secrets/history cleanliness: <confirmed>

Known limitations:
Next recommended step:
```
