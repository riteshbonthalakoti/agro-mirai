# MODULE 45 — Fix the production voice regression

Continuing AGRO MIRAI. Module 44's audit found one clear, high-priority
regression: `GET /v2/advisories/{id}/audio` and the translate path return
503 `VOICE_UNAVAILABLE` in production for all four languages (en/kn/te/
hi), even though voice was confirmed working live on 2026-09-21/22. This
is a headline feature in the PPT and the most visible thing likely to
break in front of faculty if left broken. Fix the regression, don't just
confirm it's broken again.

Read `docs/PPT_VS_CODE_AUDIT.md` (Module 44's report) first for the exact
evidence already gathered — don't re-derive it from scratch.

## 1. Find the real cause, don't guess

Module 44 inferred (from behavior, not a direct read) that either the
`SARVAM_API_KEY_*` variable(s) or `VOICE_SERVICE_URL` isn't set on the
deployed `agro-mirai` main service, likely lost when the tabular service
was removed and the 3-service split was reshaped (per
`decisions/0026-three-microservices-render-split.md` and the more recent
tabular-service removal Module 44 found). Confirm this directly:

- Check the Render dashboard/CLI for the `agro-mirai` service's actual
  current env vars (list keys, don't need to read secret values) against
  what `src/agro_mirai/api/voice_client.py` /
  `src/agro_mirai/voice/remote_voice.py` actually require to reach the
  voice service, and against what `.env.example` documents.
- Check whether the voice service/container itself (`services/voice`, or
  wherever it's actually hosted now — Oracle VM per Module 21, or
  wherever it currently runs) is up and reachable at all, independent of
  the env var question — a dead voice service would produce the same
  503 even with correct env vars.
- Check Render's deploy history around when this last worked
  (2026-09-21/22) vs. when the tabular-service removal happened, and
  correlate — confirm the regression's actual timing before assuming the
  cause.

## 2. Fix it

- If it's a missing/wrong env var on Render: set the correct value
  through Render's own env var config (CLI or dashboard) — never commit a
  real secret value anywhere.
- If the voice service itself is down or unreachable: bring it back up,
  or if it's no longer meant to be the voice backend (architecture may
  have shifted since Module 21), confirm what the current intended voice
  backend is and wire `VOICE_SERVICE_URL`/equivalent to point at it.
- If Sarvam (or whichever provider is now primary, per
  `docs/architecture.md`'s "Sarvam as primary voice provider" note found
  in git history) needs a real API key that was never actually
  provisioned, stop and tell Ritesh exactly what's needed — don't
  simulate success.

## 3. Verify live, all four languages

- Hit `GET /v2/advisories/{id}/audio` for en, kn, te, and hi against the
  real production URL and confirm a real 200 with real audio content
  (not just "not 503") for each.
- Confirm the translate path Module 44 flagged (`translated:false`) is
  also actually fixed, not just the audio endpoint.
- If practical, do one real device/Expo Go check of voice playback in at
  least one non-English language — if not practical in this session,
  say so plainly rather than claiming full verification.

## What NOT to do

- Don't touch the PPT, docs, admin dashboard, or any model logic in this
  module — voice regression only.
- Don't mark this done on a single successful curl if the other three
  languages weren't also actually re-checked.

## Handoff format

```
Module: 45 — Production voice regression fix
Status: complete | blocked | needs-decision

Root cause: <confirmed, not inferred — env var / dead service / missing key>
Fix applied: <what changed, where>

Live verification, all four languages:
  en: <real response>
  kn: <real response>
  te: <real response>
  hi: <real response>
Translate path (translated:false issue): <confirmed fixed>
Device check: <done, or explicitly not done and why>

Known limitations:
Next recommended step:
```
