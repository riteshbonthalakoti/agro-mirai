# OpenRouter free-tier quota — measured, not assumed

**Test date:** 2026-10-30
**Model:** `dots-studio/dots-3-note-preview:free` (the exact model the scan pipeline uses)
**Method:** real API calls, one request per second, against a single dedicated test key, until 5 consecutive failures.

## Result

**Hard limit: 55 successful requests per key per day.** Call 56 onward returned `429` every time:

```json
{"error":{"message":"Rate limit exceeded: free-models-per-day. Add 10 credits to unlock 1000 free model requests per day","code":429}}
```

No slowdown or soft throttling beforehand — the first 55 calls all succeeded in 2-10s each, then every call failed immediately (sub-second) once the limit hit.

## What this means for the app

- Each configured `OPENROUTER_VISION_API_KEY_*` gets its own 55/day allowance.
- With the 3 keys currently in rotation: **~165 scans/day** before OpenRouter is exhausted and the pipeline falls through to Groq.
- The limit resets once every 24 hours from... unconfirmed exactly when (OpenRouter doesn't document the reset window precisely — likely rolling or midnight UTC). Worth re-testing with the same key after 24h to confirm reset timing, not yet done.
- OpenRouter explicitly offers to raise this to 1000/day for a one-time $10 credit purchase, per their own error message — worth considering once real usage approaches 165/day.

## Raw log

Full call-by-call record: `quota_log.csv` (scratchpad, not committed — contains the test API key).
