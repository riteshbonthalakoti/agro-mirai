# 0031 - Free-tier LLM cascade ahead of the trained/rule-based models

Status: accepted, 2026-10-25.

## Why
Disease detection, advisory, and crop recommendation each had exactly one model path serving
requests directly (the CNN, then a rule-based fallback for disease; EcoCrop rules alone for crop
recommendation; a rule-based compositor alone for advisory). Reliability improves when a result can
come from more than one independent source before falling back — the same reasoning already applied
to weather in `acquisition/weather_fallbacks.py` and to voice in `sarvam_client.py`/`gemini_client.py`.

## What changed
Each of the three use cases now tries a free-tier LLM tier first, falling back to the existing model
unchanged if the LLM tier is unavailable, times out, or returns something unusable:

- **Disease detection**: new vision-LLM tier (`gemini_client.ask_gemini_vision`) → existing CNN
  (`cnn_client.py`) → existing rule-based `DiseaseRiskModel` (unchanged, still the final fallback).
  Wired in `models/image_or_environmental_disease.py`.
- **Crop recommendation**: new LLM tier (`api/crop_llm.py`) → existing EcoCrop rule ranking
  (`models/crop_recommendation_model.py`, unchanged).
- **Advisory**: new LLM tier (`api/advisory_llm.py`) → existing `DecisionEngine` compositor
  (unchanged, still the only path that runs the crop/irrigation/disease sub-models).

Every result carries a `source` field recording which tier served it (`"vision_llm"`/`"cnn"`/
`"environmental_fallback"`, `"llm"`/`"ecocrop_rules"`, `"llm"`/`"rule_based"` — see
`specs/core/enums.md`). `api/key_pool.py` is a new shared, provider-agnostic module that round-robins
up to 9 keys per provider and cools down any key that returns a 429, reused by all three cascades.

## What did not change
Public function signatures, return types, and API response shapes are unchanged — this is additive,
not a rewrite. No existing CNN/rule-based code was modified; each stays as the fallback of record and
is what runs when no LLM key is configured at all (the default out of the box).

## Trade-off
The LLM tiers depend on free-tier quota (`.env.example`'s `GEMINI_API_KEY_1..9` and backup pools) that
can be empty, slow, or rate-limited; the system is designed to degrade silently to the pre-existing
path in that case, so correctness never depends on the LLM tier being available.
