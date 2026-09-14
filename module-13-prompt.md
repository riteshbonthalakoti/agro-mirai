# MODULE 13 — Feedback Loop

Continuing AGRO MIRAI in the existing `agro-mirai` repo. Modules 01–11
are done and committed (`822251b` on `origin/main`). Read `CLAUDE.md`
and `PROGRESS.md` first.

This module runs in parallel with Module 14 (Frontend) — a different
Claude Code session is building the web frontend against the same
`origin/main` at the same time. Stay inside `src/agro_mirai/feedback/`
and `tools/` for new code, avoid touching `src/agro_mirai/api/` beyond
what's strictly needed (the feedback route already exists and works —
`POST /feedback` — check `routes/feedback.py` before assuming you need
to change it), and pull before you push in case M14 has already merged
something. If you hit a real conflict with M14's work, stop and report
it in the handoff rather than resolving it blindly.

Confirm `git config user.name`/`user.email` are correct. Same commit
discipline as prior modules.

## Scope

`FeedbackEntry` records already flow in via `POST /feedback` (Module
11) and persist via the `DataStore` (Module 04). This module closes the
loop: aggregate that feedback into something that (a) a human can look
at to judge whether the models are actually helping farmers, and (b)
could plausibly inform a future retraining pass — without actually
retraining anything yet. Full automated retraining is out of scope for
this module; a documented, honest path toward it is in scope.

## Tasks

### 1. ADR first — `decisions/0012-feedback-loop.md`
Cover:
- What "using feedback" means at this stage of the project (aggregation
  and reporting, not live retraining) and why that's the right scope
  given the Nov 14 deadline — be honest that this is v1, not a
  production ML feedback loop.
- What the aggregation actually measures: per-crop / per-advisory-type
  helpfulness rate, rating distribution, and any correlation you can
  surface between low ratings and specific model outputs (e.g. "low
  ratings cluster around high-urgency irrigation advisories" — only
  claim a correlation if the data in the fixtures/synthetic set
  actually shows one, don't invent a finding).
- The concrete future path: what would need to exist for this feedback
  to actually retrain `CropRecommendationModel`/`IrrigationPredictionModel`
  (e.g. minimum sample size, a labeled-outcome signal beyond a 1-5
  rating, a retraining trigger) — sketch it, don't build it.

### 2. `FeedbackAggregator` (or similar)
`src/agro_mirai/feedback/aggregator.py`:
- Reads `FeedbackEntry` records via the `DataStore` (add a
  `list_feedback` / `get_feedback_for_farmer` method to the `DataStore`
  interface + both implementations if one doesn't already exist —
  check `repository-interface.md` and the SQLite/Supabase stores first).
- Produces a summary structure: counts, average rating, helpful-rate,
  broken down by whatever dimensions are meaningful given the schema
  (crop, advisory severity, date range).
- Keep it a pure function/class over data the `DataStore` already
  returns — no new schema.yaml fields needed for this; if you find you
  need one, treat it like Module 11 treated the `/health` gap: propose
  it, get it into `schema.yaml`/`enums.md` in its own commit, and note
  it explicitly in the handoff — don't silently add fields.

### 3. A way to see the aggregation
Doesn't need to be fancy — a CLI script (`tools/feedback_report.py`)
that prints/dumps the `FeedbackAggregator` output is enough for this
module. If Module 11's API should also expose it (e.g.
`GET /feedback/summary`), that's an additive endpoint — same discipline
as above: add to `openapi.yaml` first, its own commit, call it out.
Your call whether it's worth doing now or leaving as a "future work"
note in the ADR; don't feel obligated to add API surface that isn't
needed yet.

### 4. Seed some realistic feedback data
The fixtures (farm-001/farm-002) don't include feedback. Generate a
small, clearly-labeled synthetic feedback dataset (e.g.
`tests/fixtures/feedback_seed.json` or similar) — enough rows to make
the aggregation meaningful (a few dozen), with honest variation (not
all 5-star), documented as synthetic/for-testing in a comment or
adjacent README note. Don't present synthetic data as if it came from
real farmers anywhere in code, tests, or docs.

### 5. Tests — three explicit stages, report each separately
- **Unit**: `FeedbackAggregator` against a small hand-built list of
  `FeedbackEntry`-shaped records — confirm counts/averages are computed
  correctly for known inputs (including edge cases: zero feedback,
  all-5-star, all-1-star).
- **Integration**: seed the synthetic feedback set into a real
  `DataStore` (SQLite), run the aggregator end to end, confirm the
  report reflects what was seeded.
- **Acceptance checklist**:
  - [ ] Aggregation report runs against seeded data and produces
        sane, non-crashing output for zero, one, and many feedback
        entries
  - [ ] ADR explicitly separates "what this module does now" from
        "what real retraining would require" — no overclaiming
  - [ ] Synthetic feedback data is clearly labeled as synthetic
        wherever it appears

### 6. Update doctrine
`modules/13-feedback-loop/STATUS`, `CLAUDE.md` phase (note this ran in
parallel with M14), `PROGRESS.md` row 13, `python tools/update_state.py`,
`python tools/check_specs.py`, commit and push. Before your final push,
`git pull` and resolve/report anything from M14 that landed while you
were working.

## Definition of done
- [ ] ADR 0012 written, honest about scope (aggregation, not retraining)
- [ ] `FeedbackAggregator` works against real `DataStore` data
- [ ] Synthetic feedback seed data, clearly labeled
- [ ] Unit + integration tests pass; acceptance checklist in handoff
- [ ] Doctrine updated, pushed to `origin/main`, no unresolved conflicts
      with M14's parallel work

## Handoff format
```
Module: 13 — Feedback Loop
Status: complete | blocked
Implemented:
Files changed:
Commits made:
Unit tests: <+pass/fail>
Integration tests: <+pass/fail>
Acceptance checklist: <each item, checked or not, with a one-line note>
Known limitations:
Remaining risks:
Conflicts with Module 14: <none | describe>
Next recommended module: 15 — Integration, deploy, docs (after M14 also lands)
```
