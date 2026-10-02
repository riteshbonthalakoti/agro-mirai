# AGRO MIRAI — Session Log (late Sep – early Oct 2026)

An honest record of one long Claude Code working session on AGRO MIRAI, written for
handover when switching accounts. It covers what was asked, what was done, what went
wrong, what was refused and why, and what is still open. Secrets (passwords, tokens)
are deliberately **not** in this file — see "Credentials" below for where they live.

---

## 1. Starting state

- Repo: `riteshbonthalakoti/agro-mirai`. Flask API (Render), React Native/Expo app,
  landing page + admin dashboard (Vercel), Supabase Postgres in prod.
- Work happened first in a git worktree `worktree-module-51-offline-errors-bug-reporting`,
  later directly on `main`.
- Backup branch created before any cleanup: **`backup/pre-cleanup-2026-09-29`** — full
  history and every deleted file are recoverable from it.

---

## 2. Work completed, in order

### 2.1 Module 51 — offline mode, error handling, bug reporting
Built per its prompt using subagent-driven development, merged to `main`, deployed.

### 2.2 Module 49/50 numbering discrepancy
Found mid-session; documented as an erratum instead of rewriting history.

### 2.3 OTP viewer (admin only)
- User asked twice for a **public** page listing farmer phone numbers + live OTP codes.
  **Refused both times**: it would expose third parties' phone numbers and let anyone log
  in as any farmer.
- Built the fallback instead: `GET /v2/admin/otps` (`OtpStore.peek_all()`, read-only,
  never consumes OTPs) and an `#/otps` view in the admin dashboard, behind admin login,
  polling every 5 s.

### 2.4 Vercel CI/CD
`vercel tokens add` returns 403 for CLI OAuth sessions. User created a PAT in the Vercel
dashboard; it was stored with `gh secret set VERCEL_TOKEN`. Pushes to `main` now run
CI → "Deploy (Vercel)" workflow.

### 2.5 Landing page — many rounds
- Fixed broken APK link, stronger hero CTA, clickable logo, 3D tilt cards.
- Fixed a factual error: the page said Penman-Monteith; the code uses Hargreaves-Samani.
- Added Lenis smooth scroll (SRI-pinned), scroll-linked parallax, kinetic headline.
- Fixed scroll jank (native `scroll` vs `lenis.on('scroll')` mismatch).
- Removed floating stat chips that collided with the hero photo; warmed the overlay.
- Design critique ("roast"): rated ~6.5/10 as a marketing site, 3–4/10 vs Awwwards-tier.
  Flagged the tension between the user's earlier "simple, professional" ask and a
  maximal 3D style.
- Researched patterns (bento grids, sticky/pinned sections, kinetic type; Watershed,
  Pachama, Planet Labs as references; 21st.dev rejected — needs React+Tailwind+bundler).
- Implemented four changes (commit `afc35ea`): bento feature grid, bento stats with SVG
  sparklines + "So what" captions, sticky-left/scrolling-right "How it works", one
  oversized-type breather section. Verified desktop + mobile in the browser.

### 2.6 APK size reduction — 112 MB → ~38–40 MB
Three real causes found and fixed: dev-client bundled in, minify/shrinkResources off,
4 CPU architectures. Fixed with `expo-build-properties` (minify, shrink, `arm64-v8a`
only — user approved the compatibility tradeoff). Built locally in a short-path worktree
(Windows MAX_PATH). Released as v1.6.0.

### 2.7 "Download stuck at 100%" report
Initially misdiagnosed as a link-attribute problem (added then reverted `target="_blank"`
/ `download`). After clarification, verified the server/file side is fine (re-downloaded,
checksum matched). Likely a client-side issue (Play Protect scan, Brave Shields, network).
**Never confirmed resolved** — user did not report back.

### 2.8 Admin dashboard
- Sign-in button had no feedback → added loading state.
- Fully restyled to the **mobile app's** theme (white, one green accent, no shadows),
  not the landing page palette.

### 2.9 OTA updates (EAS Update) — full brainstorm → spec → plan → execution
- `expo-updates` installed; `mobile/src/updates.ts` silently checks/fetches on launch.
- Final review (fresh reviewer) found real bugs, all fixed (`df02303`):
  - `EXPO_UPDATES_CHANNEL` env var never reached the app — `app.json` is static JSON.
    Fix: `mobile/app.config.js` sets `updates.requestHeaders['expo-channel-name']` from
    `APP_CHANNEL`.
  - Docs said `eas channel:edit production --branch staging`, which would permanently
    point production at all of staging. Replaced with `eas update:republish`.
  - `runtimeVersion` switched from `appVersion` to `fingerprint`.
  - Shell-injection in `.github/workflows/publish-update.yml` (input interpolated into
    `run:`) fixed by passing via `env:`.
- Live device verification (phone over wireless ADB):
  - Build blockers fixed: corrupted NDK install; `JDK_JAVA_OPTIONS` set to empty string
    still printed a JVM note that Gradle's prefab step treated as an error (needs
    `unset`, not `export VAR=`); MAX_PATH again (short-path worktree).
  - `staging` channel didn't exist (only a branch) → `eas channel:create staging`.
  - Fingerprint mismatch turned out to be stale `android/` from earlier failed builds;
    `expo prebuild --clean` fixed it.
  - A no-op update (identical content) correctly reports "no update".
  - **Proven end to end**: published a temporary text change, phone downloaded it and
    showed it on next launch with no reinstall. Reverted and republished clean.
- Lesson: always `expo prebuild --clean` right before a build used for OTA.

### 2.10 Language-screen "Continue blocked by audio" report
Tested live on the device with fresh app data: Continue was tappable immediately and
navigated on. Did not reproduce on the current build; likely an older install.

### 2.11 Repo cleanup ("very minimal")
- Removed `Claude outputs/` and an unused hero image.
- Removed `decisions/`, `docs/`, `modules/`, `notebooks/`, then every `.md` file
  (READMEs, CLAUDE.md, AGENTS.md, PROGRESS.md, credits, prose specs).
- **Mistakes made and fixed:**
  - `docs/TOOLING.md` (real build/OTA commands) was deleted with the rest — flagged.
  - A failed `vercel --prod` CLI attempt created an unwanted `vercel.json` — deleted.
  - CI went red: old tests asserted deleted doc files existed. Deleted
    `test_module_01_foundation.py`, trimmed `test_module_02_contracts.py` (real contract
    tests kept). CI green again (`f9cd54e`).
- Kept `specs/core/enums.md` — `tools/check_specs.py` parses it as a CI gate.
- Added a new `README.md` (`da45b75`).

### 2.12 Phase 1 code cleanup (4 parallel audit agents)
Evidence-verified dead code removed (`382922f`):
- Backend: shadowed imports in `app.py` and `decision_engine.py`, unused
  `effective_rain` import, unused `last_exc` in `cnn_client.py`.
- Mobile: `sourceLabel`, `feedbackEnabled`, `SkeletonList`, `Label` (+ its import).
- Admin CSS: `.gap`, `.stat .na`.
- tools/: `update_state.py`, `run_demo_test_cases.py`, `build_test_case_deck.py`.
- Checked and kept (look duplicated, are live): `/v1` + `/v2`, SQLite + Supabase stores,
  voice providers, `cnn-onnx` (deployed) + `cnn-inference` (not deployed, still tested).
- Verified: pytest 565 passed / 0 failed / 40 skipped; mobile `tsc` clean; CI green.

### 2.13 v1.7.0 release
Fresh build from `main @ 382922f`, `APP_CHANNEL=production`, 39.5 MB, `arm64-v8a`.
Released as **v1.7.0**; landing page links updated (`6b94c1c`). Not install-tested on a
phone this round (ADB session had expired). Debug-signed — no release keystore exists;
fine for sideloading, not Play Store eligible.

---

## 3. Advice given (not code)

- **Freelance handover** (friends' college demo, no contract, advance paid): send one
  written scope message; never share personal account passwords; hold final source
  handover until fully paid; without a written work-for-hire agreement the developer
  owns the code by default.
- **Sarvam voice**: the kill switch is server-side (`SARVAM_DISABLED`, default on, read
  in `src/agro_mirai/api/sarvam_client.py`). Set `SARVAM_DISABLED=0` on Render to turn
  it back on — no app update or reinstall needed.
- **Render** health-check timeout emails: typical free-tier cold start.
- **Vercel**: 75% of the 10 GB free deployment storage used — watch it.

---

## 4. Things refused, and why

| Request | Response |
|---|---|
| Public page with farmer phone numbers + OTPs | Refused twice (third-party privacy, account takeover). Built admin-only viewer. |
| Email telling GenZTech the author is from a different city/college and works at a different company | Declined — would give a journalist false identity details for publication. Drafted a request to remove institutional details instead. |
| Merge "push notifications" PR #6 (kitchen/household app) | Not done — different repo, not open in this session; won't merge from a pasted description without reading the diff. Waiting on the repo URL. |

---

## 5. Credentials and access (no secrets here)

- **Supabase read-only role** `demo_readonly` created on project `agro-mirai`
  (SELECT-only on `public`). Host `db.yzsemdauwafxssaknlzr.supabase.co`, port 5432,
  db `postgres`. Password was given in chat only — rotate it if this log is shared:
  `ALTER ROLE demo_readonly WITH PASSWORD '...';`
- `VERCEL_TOKEN` is a GitHub Actions secret on the repo.
- EAS: logged in as `ritesh.bonthalakoti`; channels `staging` and `production` exist.
- The owner's Supabase account holds many unrelated projects — that's why the read-only
  role exists instead of sharing the account.

---

## 6. Open items

1. **Phase 2** — new repo with `main` history only, ownership transferred to a friend.
   Needs the friend's GitHub username. Note: rewriting commit authorship to another
   person changes the real history; keep the original repo as the true record.
2. **Phase 3** — beginner docs: VS Code + SQLTools setup using `demo_readonly`, running
   locally, admin login, live URLs.
3. Create a fresh admin account for the friends (don't share the owner's).
4. Add `EXPO_TOKEN` secret if the OTA publish workflow is to run from GitHub.
5. Push-notification message wording in the app (asked early, never started).
6. Optional: a real release keystore; on-device test of v1.7.0.
7. GenZTech: send the "remove institutional details" email if wanted.
8. PR #6 (other repo): provide its URL to review before any merge.

---

## 7. Key commits on `main`

| Commit | What |
|---|---|
| `df02303` | OTA final-review fixes |
| `afc35ea` | Landing page bento/sticky/breather redesign |
| `bff5699` | Merge of worktree branch (OTA + landing) |
| `50931a2` | Remove Claude outputs + unused hero image |
| `249c114` | Remove decisions/docs/modules/notebooks |
| `aaf8030` | Remove remaining .md files |
| `069e995` | Remove prose spec docs (enums.md kept) |
| `da45b75` | New README |
| `f9cd54e` | Fix CI after doc removal |
| `382922f` | Phase 1 dead-code cleanup |
| `6b94c1c` | Landing links → v1.7.0 |
