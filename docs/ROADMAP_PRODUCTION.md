# AGRO MIRAI — PPT Gap Analysis & Production-Grade Roadmap

Generated from a full read of `AGRO_MIRAI2.1.pdf` (40 slides) cross-referenced
against the actual 15-module build (`5bdf6aa`, `origin/main`). Scope for the
production push, per your answers: **reliability/correctness hardening**,
**multi-tenant + Admin role**, and **closing PPT-vs-build gaps**. Authorship
(README "Solo-built" vs. PPT's 4 named co-presenters) is parked for later —
flagging it once more here so it doesn't get lost before Nov 14.

---

## Part 1 — What the PPT promised vs. what actually got built

| # | PPT says | Actually built | Verdict |
|---|---|---|---|
| 1 | Disease detection via **TensorFlow + CNN (MobileNet)** on leaf images | Rule-based weighted-threshold scorer (humidity/rainfall/temp/NDVI-trend), documented in ADR 0009, CNN explicitly deferred | **Real gap** — closing this is in scope now |
| 2 | **OpenWeatherMap** for weather data | Open-Meteo (free, no key required) | Substitution, functionally equivalent — defensible, not a gap to close |
| 3 | **MySQL** database | SQLite (dev) + Supabase Postgres (prod) | Substitution, arguably better — defensible |
| 4 | Use-case diagram includes an **Admin actor** (update advisory rules, monitor farmer data, manage system) | No admin interface exists; system is single-tenant (ADR 0003) | **Real gap** — in scope now |
| 5 | Actors are implicitly multi-farmer (a farmer registers, has fields) | Single hardcoded farmer (`FARMER_ID` env var), no auth/registration | **Real gap** — in scope now |
| 6 | 28-week Waterfall work plan tied to the academic calendar | Compressed agent-driven parallel build across ~2 sessions | Process difference only, not a functionality gap — no action needed, but the final report should describe the actual (agent-assisted) methodology honestly rather than pretend it followed the PPT's week-by-week plan |
| 7 | Bhashini for regional language | AI4Bharat (IndicTrans2/IndicConformer/Piper/vits_rasa_13) primary, Bhashini stubbed as future swap-in | Substitution, documented — defensible |
| 8 | Expected-outcomes mockup shows a "Market Prices" button | Scope slide explicitly excludes market-price systems | Internal PPT inconsistency, not a build gap — no action, just don't be surprised if an evaluator asks |
| 9 | Scope excludes hardware/automation control and financial/market systems | Nothing built in those areas | Consistent — no action |
| 10 | Team of 4 + 3 guides | README says "Solo-built by Ritesh" | **Unresolved** — parked per your answer, revisit before Nov 14 |

**Net read:** rows 2, 3, 7, 8, 9 are non-issues — reasoned substitutions or
consistent scope, and worth stating plainly as design decisions (you already
have ADRs for most of them) rather than apologizing for them at review.
Rows 1, 4, 5 are the real gaps the "production grade" push should close.
Row 6 is a framing note for the final report. Row 10 stays parked.

---

## Part 2 — Production-grade workstreams (your selected scope)

### A. Reliability & correctness hardening — done, Module 16 (`docs/TOOLING.md`/`PROGRESS.md` have the full handoff)
1. [x] **CI pipeline** (GitHub Actions): runs `pytest --ignore=tests/voice`
   (global interpreter only — see note below) and `check_specs.py` on every
   push/PR to `main`, gating the build; a non-blocking `ruff` lint pass
   runs alongside. `tests/voice` needs the project-local `.venv/` (torch
   pinned stack) and was judged impractical to stand up in CI within a
   reasonable time/cost budget — noted here rather than silently dropped.
2. [x] **Error monitoring**: `sentry-sdk[flask]` wired in, no-op without a
   `SENTRY_DSN` env var; tags request_id/route/farmer_id when configured.
3. [x] **Structured logging**: request-id-tagged logs via a stdlib
   `logging.Filter`, header echoed back as `X-Request-Id`.
4. [x] **Input validation hardening**: audited `/fields` and `/feedback`
   against `openapi.yaml` — found and fixed real gaps (range/type/enum
   checks missing, a malformed date crashing to a 500).
5. [x] **Backup strategy**: `tools/backup_supabase.py` + `docs/BACKUPS.md`
   — manual-only, honestly documented (Render free tier has no easy cron).
6. [x] **Rate limiting**: Flask-Limiter, 60/min per API key by default,
   429 on exceed.

### B. Multi-tenant + Admin role
This is the biggest single piece of new scope, and it touches the data
model, auth, and every layer above it — worth sequencing carefully:
1. **Data model**: extend `farmers`/`fields` to support many farmers
   properly (largely already shaped for it — ADR 0003 chose single-tenant
   *behavior*, not necessarily a single-tenant *schema* — needs verifying
   against the actual schema.yaml).
2. **Auth**: replace the single static `API_KEY` with per-farmer
   credentials (simplest realistic option: per-farmer API keys issued at
   registration; a full login system is heavier than this timeline
   probably supports — flag if you want that instead).
3. **Admin role** (matches PPT's use-case diagram): a small admin
   surface — list all farmers/fields, view system-wide feedback
   aggregates, and a stubbed/simple "update advisory rule thresholds"
   control (the PPT doesn't specify what "update rules" concretely means,
   so this needs a concrete definition before it's buildable — see open
   question below).
4. **Farmer registration flow**: currently there's no way to add a new
   farmer except via `seed_fixture.py` / direct DB writes.

### C. Close remaining PPT gaps
1. **CNN disease model**: train a real MobileNet-based image classifier
   on a Kaggle plant-disease dataset (PlantVillage is the standard
   choice), behind the same `DiseaseRiskModel` interface so the rule-based
   version can stay as a documented fallback rather than being thrown
   away. This is realistically the largest single item — image upload
   handling, a new endpoint or extension to the existing one, model
   training/eval, and updating ADR 0009 to reflect the upgrade actually
   happening.
2. Update `decisions/0009-*.md` to record the CNN as shipped, not just
   planned.

---

## Part 3 — Sequencing against the calendar

- **Review-1: Sep 21-26** (< 4 weeks away). Realistic goal: CI pipeline +
  error monitoring + input validation hardening (workstream A, items 1-4)
  done and demoable; multi-tenant/Admin and the CNN model are bigger and
  should be described as "in progress, planned for Review-2" rather than
  rushed.
- **Review-2: Oct 26-31**: multi-tenant + Admin role (workstream B) and the
  CNN disease model (workstream C) are realistic targets for this window.
- **Final report: Nov 14**: backups/rate-limiting polish, authorship
  resolution, final write-up describing the actual agent-assisted
  methodology honestly.

## Open questions before I write module prompts

1. For the Admin "update advisory rules" feature — do you want this to
   actually change live model behavior (e.g. adjustable disease-risk
   thresholds), or is a read-only admin dashboard (view farmers, view
   feedback trends) enough to satisfy the PPT's use-case diagram for
   review purposes?
2. For multi-tenant auth — per-farmer API keys (simple, fits the
   timeline) or a real login/session system (heavier, more "production")?
3. Should I start with workstream A (CI + hardening) as the next module
   prompt, since it's lowest-risk and fits before Review-1? I'd suggest
   yes, then sequence B and C after.
