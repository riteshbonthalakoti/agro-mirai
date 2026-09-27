# MODULE 43 — Fix the three broken models for real, fix the top-of-dashboard UI

You are starting a fresh Claude Code session on AGRO MIRAI with no memory
of prior sessions. Read this whole prompt before doing anything — it has
the context you need. Do not assume anything about prior "complete"
reports; verify everything yourself, live, before trusting it.

## Project context (read first)

AGRO MIRAI is a VTU Sem 7 AIML capstone (BITM) — an AI farm advisory app.
Repo: `C:\Projects\AGRO MIRAI` (github.com/riteshbonthalakoti/agro-mirai,
branch `main`). Read `CLAUDE.md` at the repo root for the full doctrine
(CLI-first, additive-only contracts, SQLite-dev/Supabase-prod, degrade-
never-fail, module-gating) and `PROGRESS.md` for the module history before
changing anything. Backend is Flask, split across 3 Render free-tier
services (`agro-mirai` main API, `agro-mirai-tabular` for crop/irrigation
models, `agro-mirai-cnn` for the disease image model, see
`decisions/0026-three-microservices-render-split.md`). Mobile app is Expo/
React Native under `mobile/`.

**Standing rules, apply without being asked again:**
- No "Co-Authored-By: Claude" or any AI-attribution anywhere — not in
  commits, code comments, README, or PRs. This repo is submitted by a
  5-person student team; it must read as normal student work.
- Commit messages: short, plain, human, inconsistent style — one line
  each, no conventional-commits formatting, no bullet-pointed bodies.
- Code comments: ordinary student-level, not AI-formal or over-thorough.
- CLI-first: use the Render CLI, GitHub CLI, etc. directly rather than
  describing dashboard click-paths, per `CLAUDE.md`.

## The actual problem, reported directly by Ritesh after testing himself

Ritesh personally tested the real app on his own phone and confirmed: the
three models — crop recommendation, irrigation, disease risk — are **not
working** right now. Not "unverified," actually broken when he uses the
app. This needs a real root-cause, not a guess and not another report
that says "should be working" without live proof Ritesh can see himself.

Known relevant facts already in the repo's own history (verify these are
still true, don't assume):
- `docs/PROJECT_WALKTHROUGH.md` (uncommitted, check if still present)
  documents a prior fix for advisories 500-ing because the main API
  service no longer ships model files but tried to load them anyway —
  check whether this fix (commit `b9e3dc2`) is actually deployed and
  working on Render right now, not just merged to `main`.
- The most recent installable APK (GitHub release `v1.3.0`, tagged
  2026-09-22) predates 5 later commits on `main`, including
  `09aa48c` (onboarding/notifications) and `760a510` (irrigation SHAP
  rationale fallback). If Ritesh tested via that APK, he was testing
  stale code — confirm which build he actually tested on his phone
  before concluding anything about current `main`.
- Crop recommendation model: trained RandomForest, 99.55% held-out
  accuracy (`docs/eval/crop_rf_eval.json`).
- Irrigation urgency model: trained RandomForest, 72.4% accuracy,
  macro-F1 0.58 — the weakest of the three, worth extra scrutiny.
  Irrigation depth (mm) is a rule-based FAO-56 water-balance formula,
  not ML.
- Disease risk: weather-based path is a rule-based weighted score;
  leaf-photo path is a trained CNN (MobileNetV2, 99.24% on PlantVillage
  lab images — expected to be lower on real field photos), served by the
  `agro-mirai-cnn` ONNX service.

## 1. Root-cause each of the three models, live, for real

For each of crop recommendation, irrigation, and disease risk:

- Hit the real deployed Render endpoint directly (curl or the Render CLI
  against the live URL, not localhost) with a real or realistic field
  input and see the actual response — status code, actual body, actual
  error if any.
- Check the real Render service logs for that request (`render logs` or
  equivalent) — don't guess at the failure, read the actual stack trace
  or error.
- Then reproduce the same flow through the real mobile app (fresh install
  if needed — see item 3) and confirm whether the app-level symptom
  matches the API-level one, or whether the bug is actually in how the
  app calls/renders the API response (a real, different class of bug).
- Common suspects to check first, based on this project's own history:
  are the trained model artifacts (`crop_rf.joblib`,
  `irrigation_rf.joblib`, the CNN ONNX file) actually present and loaded
  on the relevant Render service right now (they're gitignored — confirm
  they were committed/built per `decisions/0026` and
  `45b72be`/`be4ceb0`'s "commit tabular model joblib artifacts" fix); is
  `TABULAR_SERVICE_URL`/`CNN_SERVICE_URL` actually set and reachable from
  the main API service; did a Render free-tier cold start or memory limit
  kill the request (512MB per service); is the CNN service token
  (`CNN_SERVICE_TOKEN`) actually matching between services, per open item
  #3 in `PROJECT_WALKTHROUGH.md`.

## 2. Retrain vs. switch to a pretrained model — decide per-model, with evidence

Ritesh raised two options: retrain the existing models, or find a
pretrained alternative on the internet. Don't default to either — for
each of the three, make a real, evidenced call:

- **If the root cause from step 1 is an infra/wiring bug** (missing
  artifact, bad service URL, memory kill, stale deploy), the fix is
  fixing that — not retraining or switching models that were never
  actually broken. Say so plainly if that's what you find.
- **If a model's real accuracy is genuinely too weak to be useful**
  (irrigation's 72.4%/macro-F1 0.58 is the most likely candidate),
  investigate real alternatives: is there a better-labeled dataset
  available (Kaggle, UCI, ICAR/data.gov.in — do a real search, cite what
  you find and why you accept/reject it, same rigor as
  `decisions/0016-regional-crop-suitability.md`'s investigation did); is
  there a genuinely reputable pretrained model or API for this specific
  task; is a better feature set or a different model class (not just
  RandomForest) worth trying with the data already in hand. Don't adopt
  a "pretrained model from the internet" without checking it actually
  fits this project's real feature schema and license — a mismatched
  model would just be a new kind of broken.
- **If the CNN's real-world accuracy on field photos is the concern**,
  that was already a documented, expected gap (lab images vs. field
  images) — confirm whether this is actually today's failure mode before
  treating it as one; if it genuinely is, look at whether a stronger
  pretrained plant-disease model (there are several real ones — do a real
  search, don't assume) is a better base to fine-tune from than the
  current MobileNetV2 run.
- Whatever you decide, retrain or re-deploy through this project's real
  CLI-first pipeline (Colab CLI for GPU training, same as
  `tools/train_disease_cnn.py` used before — don't hand-wave a new
  process), and produce a real new eval report the same format as the
  existing ones in `docs/eval/`, not a hand-typed accuracy number.

## 3. Fix the top-of-dashboard UI (only the top section)

Ritesh's instruction is specific: fix the **top part of the mobile Home
dashboard** — not the nav bar, not the middle section (the crop/
irrigation/disease cards themselves, per `mobile/src/screens/HomeTab.tsx`,
stay as they are structurally). Look at what's actually at the top of the
Home screen today (header/greeting/field-selector area — check
`HomeTab.tsx` and whatever wraps it, e.g. `App.tsx`'s tab header) and ask
Ritesh what specifically looks wrong there if it's not obvious from a real
screenshot — don't guess at "improve" without a concrete before/after.
Keep changes minimal and presentation-only; no route or data changes.

## 4. Prove all of this live, with Ritesh watching, not just internally

Same standard as every prior verification module in this project: build a
fresh APK or use a fresh Expo Go session if that's faster to iterate, and
walk Ritesh through each of the three model outputs appearing correctly
on his real phone before calling this done. Internal curl/pytest checks
are necessary along the way but are not the definition of done here —
Ritesh confirming he sees it working is.

## What NOT to do

- Don't touch the admin dashboard, notebooks, or landing page.
- Don't redesign the nav bar or the middle dashboard section.
- Don't switch or retrain a model that turns out to be working fine —
  fix the real infra bug instead if that's what step 1 finds.

## Handoff format

```
Module: 43 — Fix the three models for real, fix top-of-dashboard UI
Status: complete | blocked | needs-decision

Root cause per model:
  Crop recommendation: <what was actually broken, evidence>
  Irrigation: <same>
  Disease risk: <same>

Fix applied per model: <infra fix / retrain / pretrained swap, and why>
New eval numbers (if retrained/swapped): <real report, path>

Top-of-dashboard UI: <what changed, why, screenshot>

Live proof with Ritesh:
  Crop recommendation working on his phone: <confirmed>
  Irrigation working on his phone: <confirmed>
  Disease risk working on his phone: <confirmed>

Known limitations:
Next recommended step:
```
