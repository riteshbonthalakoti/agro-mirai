# ADR 0011 — Decision Engine: pass-through synthesis, always-call, severity-as-alert-flag

**Status:** accepted
**Date:** 2026-08-26
**Module:** 10 — Decision & Recommendation Engine

## Context

Modules 06 (crop), 07 (irrigation), 08 (disease) each produce an
independent prediction from the same `FeatureVector`; Module 09 can
explain any of the three. Module 10 is the first module that has to
combine all three into one farmer-facing `Advisory`
(`specs/core/schema.yaml`), and the first caller (Module 11's Flask API)
needs one orchestration entry point rather than three separate calls.
Three questions need an explicit answer before writing the engine:
conflict handling, data-availability gating, and how the three
predictions map onto `Advisory`'s five content fields
(`title`/`body`/`severity`/`source_refs`/`language`).

## Decision 1: conflicts are surfaced, not resolved

When irrigation urgency is `high`/`severe` but the crop recommendation
is a drought-tolerant crop, or any other cross-model tension, the engine
does **not** attempt agronomic synthesis (e.g. suppressing the
irrigation alert because "the crop can handle it") — no module in this
codebase has the domain expertise encoded to make that call correctly,
and doing so silently would hide a real signal from the farmer. Instead
**all three predictions are always assembled into `body`, unmodified**;
`DecisionEngine` is a compositor, not an arbiter. This mirrors ADR
0009's stance against inventing signal-derived output that isn't
directly traceable back to its source — a synthesized "combined"
judgment call would be exactly that. Conflict *detection* is future
work if the roadmap calls for it (a candidate `Advisory` field or a
separate flag), but is out of scope here — nothing in `schema.yaml`
today models "these two outputs disagree."

## Decision 2: always call all three models, per-model graceful skip on missing data

`DecisionEngine.recommend` always calls all three model wrappers — it
does not pre-inspect `FeatureVector` to decide which models are
"applicable." This matches Module 05's missing-data policy
(`decisions/0006-missing-data-policy.md`): weather is required (`FeatureBuilder`
already raises if absent, before `DecisionEngine` ever runs), soil and
NDVI are optional with explicit `*_data_available` flags. Each model
wrapper (06/07/08) already knows how to degrade under partial data —
Module 08 already zeroes its NDVI term and lowers `confidence` when NDVI
is unavailable; Modules 06/07 use whatever soil defaults their own
feature mappings provide. `DecisionEngine` does not duplicate that
availability logic — it would need to know each model's internal
degradation rules to gate correctly, which only the model itself should
own. If any one model wrapper raises (e.g. a truly required field is
missing), `DecisionEngine.recommend` lets that exception propagate
rather than silently omitting that section of the advisory — a partial,
mislabeled-as-complete `Advisory` is worse than a clear failure Module
11 can turn into an HTTP error.

## Decision 3: `Advisory` field mapping

`Advisory` has no per-model fields — it's a bundled, narrative record.
Mapping, field by field:

| `Advisory` field | Source |
|---|---|
| `id` | new `uuid.uuid4()` |
| `field_id` | `features.field_id` |
| `created_at` | `datetime.now(timezone.utc)` |
| `language` | `"en"` always — v1 has no farmer-language preference stored anywhere upstream (`Farmer` has no `preferred_language` field in `schema.yaml`); Module 11 or a later module can translate `body` via `VoiceService.translate` and construct a second `kn` `Advisory` if needed, but `DecisionEngine` itself only ever produces `en` (`ExplanationService.summary_kn` already offers a per-explanation Kannada summary — `Advisory.body` linking to that, rather than re-implementing translation here, avoids a second translation call site) |
| `title` | Short synthesized string: the recommended crop's name (e.g. `"Advisory for rice"`) — the one piece of the three outputs that reads naturally as a title |
| `body` | Concatenation of `CropRecommendation`, `IrrigationAdvice`, `DiseaseRiskAlert`'s `summary_en` explanation sentences (from `ExplanationService`), each unmodified, joined as separate sentences/paragraphs — see Decision 1 |
| `severity` | `max` of `IrrigationAdvice.urgency` and `DiseaseRiskAlert.risk_level` on the shared `risk_level` ladder (`low < moderate < high < severe`, per `enums.md`'s own note that the ladder is "same everywhere" including advisory severity) — `CropRecommendation` has no risk-level output, so it does not participate in this max |
| `source_refs` | `[crop_recommendation.id, irrigation_advice.id, disease_risk_alert.id]` |

## Decision 4: alert threshold reuses `severity`, no new field

The module prompt's "warrants immediate action" flag is **not** a new
schema field. `Advisory.severity` (the `risk_level` enum) already
carries this: `severity in {"high", "severe"}` **is** the immediate-action
signal, because `severity` is computed (Decision 3) as the max across
exactly the two model outputs (`IrrigationAdvice.urgency`,
`DiseaseRiskAlert.risk_level`) the module prompt names as the alert
triggers. Adding a second boolean field to carry the same information
`severity` already carries would violate hard rule 2's "additive only
when actually new information" spirit by duplicating a value already on
the contract. Module 11/callers check `advisory.severity in ("high",
"severe")` directly — no `DecisionEngine`-side flag needed.

## `ExplanationService`/`VoiceService` injection

`DecisionEngine.__init__(crop_model=None, irrigation_model=None,
disease_model=None, explanation_service=None, voice_service=None)` —
all defaulted so Module 11 can wire its own instances (or share the
already-loaded `crop_model`/`irrigation_model` artifacts with its own
`ExplanationService`), but a zero-arg `DecisionEngine()` also works
standalone, matching Modules 06-09's constructor pattern. When
`explanation_service` is not provided, `DecisionEngine` constructs one
internally from whichever `crop_model`/`irrigation_model` it already
holds (never a second pair of loaded artifacts) and passes `voice_service`
through to it.

## Consequences

- `Advisory.body` is exactly as informative as the three
  `Explanation.summary_en` sentences underneath it — no new synthesis
  logic to test independently for agronomic correctness, and no new
  vocabulary of "combined recommendation" that would need its own
  validation against real agronomy.
- The severity-as-alert-flag decision means Module 11 needs zero new
  schema knowledge beyond `severity` to build a "needs attention" UI
  badge.
- A future conflict-detection feature (Decision 1) would be an additive
  schema change to `Advisory`, not a rewrite of `DecisionEngine`'s core
  loop.
