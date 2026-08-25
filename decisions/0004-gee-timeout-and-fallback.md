# ADR 0004 — Earth Engine timeout and NDVI fallback thresholds

**Status:** accepted
**Date:** 2026-08-25
**Module:** 03 — Data Acquisition

## Context

CLAUDE.md hard rule #4 requires every NDVI read to try live Google Earth
Engine first and fall back to a local cache on timeout, quota exhaustion,
or any GEE exception — never a hard failure. That rule fixes the
*behaviour*; it doesn't fix the *numbers*. Four thresholds needed picking
in `src/agro_mirai/acquisition/earth_engine.py`:

- How long to wait for the live `getInfo()` call before treating it as
  failed.
- How much cloud cover in a Sentinel-2 scene is still usable.
- How far back to search for a usable scene.
- How large an area around the field's point to average NDVI over.

The `earthengine-api` Python client has no built-in per-call timeout —
`getInfo()` blocks on the underlying HTTP call using the library's own
retry/backoff, which can run well past what a request-serving path can
tolerate. Wrapping the call in a bounded worker thread
(`concurrent.futures.ThreadPoolExecutor` + `future.result(timeout=...)`)
was the only way to get an explicit ceiling.

## Decision

| Parameter | Value | Rationale |
|---|---|---|
| `timeout_s` | **20.0 s** | Generous enough for a cold GEE call (auth + query + `reduceRegion`) observed in manual testing to take a few seconds once authenticated, but short enough that a request-serving caller (Module 05+) isn't left hanging; a farmer-facing advisory endpoint should fail over well under typical HTTP gateway timeouts (usually 30s). |
| `max_cloud_cover_pct` | **20.0 %** | Sentinel-2's `CLOUDY_PIXEL_PERCENTAGE` scene-level metadata field is a coarse whole-scene estimate, not a per-pixel mask over the field. 20% keeps most monsoon-season scenes (relevant for Karnataka kharif fields, see the golden fixture) usable while excluding scenes where the metric itself becomes unreliable. |
| `lookback_days` | **30 days** | Sentinel-2's 5-day revisit cadence means 30 days is normally enough to find at least one low-cloud scene even during a cloudy stretch of monsoon season, without searching so far back that the returned NDVI is stale for irrigation/disease timing (Module 07/08 consume this data on a days-not-months cadence). |
| `buffer_m` | **30 m** | Small enough to stay inside a typical smallholder field (the golden fixture's `North Plot` is 1.75 ha, i.e. roughly 130m×135m if square) so the average doesn't bleed into a neighbouring plot, large enough to smooth over Sentinel-2's 10m pixel grid and geolocation jitter around the field's stored point. |

All four are constructor parameters on `NDVIAdapter`
(`src/agro_mirai/acquisition/earth_engine.py`), not hardcoded constants,
so a later module can tune them per-crop or per-region without a schema
or contract change — this ADR fixes the *defaults*, not a hard ceiling.

## Consequences

- A slow-but-eventually-successful GEE call is indistinguishable from a
  truly failed one once it exceeds 20s; it will be retried live on the
  next read rather than this one waiting longer. Acceptable: the cache
  fallback keeps the caller unblocked either way.
- A field with no low-cloud Sentinel-2 scene in the last 30 days (e.g.
  sustained heavy monsoon cover) falls back to cache even though GEE
  itself is healthy. This is intentional — "no usable scene" and "GEE is
  down" both mean "serve the last known-good NDVI value."
- These numbers are a starting point for a capstone project, not a
  production SLO; if Module 05+ usage shows the timeout too tight (cold
  start) or too loose (slow degraded responses), revisit here — additive
  change, not a silent tweak.
