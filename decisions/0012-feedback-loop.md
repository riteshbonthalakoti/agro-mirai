# ADR 0012 — Feedback Loop (Module 13)

**Status:** accepted  
**Date:** 2026-08-26  
**Author:** Ritesh Bonthalakoti

---

## Context

`POST /feedback` (Module 11) persists `FeedbackEntry` records — farmer rating (1–5),
a boolean `helpful` flag, and an optional comment tied to an `Advisory`. As of the
Module 11 commit we have the collection mechanism but no way to look at what was
collected. Module 13 closes that gap.

## Decision: aggregation and reporting now; retraining later

At this stage of the project (Nov 14 capstone deadline, single developer, ~50 synthetic
feedback rows), the right scope is:

1. **Aggregate** existing `FeedbackEntry` records into summary statistics.
2. **Report** those statistics via a CLI tool (`tools/feedback_report.py`) so a
   human can judge whether the models are helping farmers.
3. **Document** what would be needed before the feedback could actually retrain a model.

Automated retraining is explicitly **out of scope for v1**. We are not building a live
ML feedback loop. This ADR is honest about that.

## What the aggregation measures

Given the fields available in `FeedbackEntry` (`rating`, `helpful`, `advisory_id`,
`farmer_id`, `created_at`, `comment`) and the linked `Advisory` (`severity`,
`field_id`, `title`), `FeedbackAggregator` computes:

| Dimension | Metric |
|---|---|
| Overall | count, mean rating, helpful-rate (% where `helpful=True`) |
| By advisory severity | count, mean rating, helpful-rate per `low/medium/high/severe` |
| By field | count, mean rating, helpful-rate per `field_id` |
| Rating distribution | counts at each of 1–5 stars |

**Honest note on correlations:** the synthetic seed dataset
(`tests/fixtures/feedback_seed.json`) was constructed with deliberate variation —
lower ratings on `high`/`severe` severity advisories than on `low`/`medium` ones —
to make the aggregation non-trivial. Any correlation surfaced by the aggregator on
this seed data reflects the seed design, not real farmer behaviour. Do not interpret
synthetic results as empirical findings.

## What real retraining would require

To use farmer feedback to retrain `CropRecommendationModel` or `IrrigationPredictionModel`,
the following would need to exist — none of it is built here:

1. **Labeled outcome signal.** A 1–5 rating says "I liked this" but not "the model
   was wrong." We need a structured outcome: did the farmer follow the advice? Did
   the crop succeed? A corrected label ("the system said rice, I planted wheat, wheat
   worked") is far more useful than a rating.

2. **Minimum sample size.** The current two fixtures produce at most ~50 feedback
   entries per field, all synthetic. Retraining a RandomForest on 50 relabeled rows
   is overfitting territory. A conservative minimum is 500+ outcome-labeled samples
   per crop class.

3. **Retraining trigger.** What event triggers a retrain? Options:
   - Scheduled (e.g. weekly, if N new labeled samples arrived)
   - Drift detection (model output distribution vs. farmer-accepted-rate diverges)
   - Manual (faculty/researcher reviews feedback and decides to retrain)

4. **Artifact versioning.** `models/crop_rf.joblib` is a single file today. A
   retraining loop needs versioned artifacts, a rollback path, and an eval gate
   (new model must beat old model's held-out F1 before promotion).

5. **Farmer consent and data governance.** Feedback used for retraining must be
   scoped to consenting farmers. Not relevant for this capstone, but mandatory
   for any production deployment.

None of this is blocked on Module 13. The `FeedbackEntry` schema is already rich
enough to extend; the aggregation output gives a human the visibility to decide
*when* retraining is worth investing in.

## Alternatives considered

- **Expose a `GET /feedback/summary` API endpoint.** Deferred — the aggregator is a
  pure Python object; a CLI caller is sufficient for capstone reporting and avoids
  API surface bloat. The endpoint can be added additively (additive-only contract rule)
  in a future module if the frontend needs it.

- **Per-advisory helpfulness correlation with model confidence.** Would require
  joining `FeedbackEntry` → `Advisory` → `CropRecommendation`/`IrrigationAdvice` on
  `field_id + created_at` proximity. Interesting but out of scope given the small
  synthetic dataset and the Nov 14 deadline; documented here as a future analysis path.

## Consequences

- `DataStore` interface gains `list_feedback_for_farmer` (new method, additive) — both
  `SQLiteDataStore` and `SupabaseDataStore` implement it; `repository-interface.md` is
  updated in the same commit.
- `src/agro_mirai/feedback/aggregator.py` holds `FeedbackAggregator` — a pure function
  over a list of `(FeedbackEntry, Advisory)` pairs; no network, no DB calls.
- `tools/feedback_report.py` is the CLI caller; it loads the `DataStore`, fetches
  records, runs the aggregator, and prints JSON.
- `tests/fixtures/feedback_seed.json` provides ~30 synthetic rows, clearly labeled as
  synthetic in the file header.
