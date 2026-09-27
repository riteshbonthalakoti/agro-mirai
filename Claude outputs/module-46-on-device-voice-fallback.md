# MODULE 46 — On-device TTS fallback when server voice is unavailable

Continuing AGRO MIRAI. Module 45 fixed the production voice regression
(Sarvam keys were missing on Render) and confirmed all four languages
return real audio live. Two real risks remain, both from Module 45's own
handoff: Sarvam's free tier is ~500 requests/day across 3 keys with no
fallback voice service in production, and the in-memory audio cache
clears on every Render restart. If the quota is hit — during a demo, or
from teammates/faculty poking around beforehand — voice goes straight
back to a 503 with no graceful degrade today. This module closes that
gap before the real review, without touching the Sarvam integration
itself (don't spend quota testing it here — see item 3).

## 1. Confirm the current 503 behavior in the mobile app

- Find exactly how the app currently handles a 503 `VOICE_UNAVAILABLE`
  from `GET /v2/advisories/{id}/audio` (and the STT/translate paths if
  they're used the same way) — check `mobile/src/screens/AdviceTab.tsx`
  and wherever audio playback is triggered from `HomeTab.tsx`'s "why
  this" explanations.
- Confirm whether this is currently a silent failure, an error toast, or
  nothing at all — cite the actual code, don't assume.

## 2. Build the on-device fallback

- On a 503 (or any other real failure) from the server voice endpoint,
  fall back to the device's own built-in text-to-speech
  (`expo-speech`'s `Speech.speak()`, already a common Expo dependency —
  check if it's already installed before adding it) reading the same
  advisory text that would otherwise have been sent for server-side
  audio.
- Map the app's four supported languages (en/kn/te/hi) to the closest
  available on-device TTS voice/locale for each — Android's built-in TTS
  engine coverage for Kannada/Telugu/Hindi varies by device, so check
  what's actually available and degrade sensibly (e.g. if a specific
  language voice truly isn't available on-device either, fall back to
  showing the text prominently with a clear "voice unavailable, showing
  text" note rather than reading it in the wrong language or failing
  silently).
- Make this feel like a real, intentional two-tier system to the farmer,
  not a broken feature: a brief, honest indicator when it's using
  on-device speech instead of the higher-quality server voice (something
  like a small "offline voice" label), not a jarring silent switch.
- Reuse the existing toast/banner system already in the app rather than
  building a new one.

## 3. Test without burning Sarvam quota

- Ritesh does not want Sarvam quota spent on testing right now — it needs
  to stay available for the actual demo. Test the fallback path by
  forcing/mocking a 503 locally (a local env flag, a temporarily wrong
  API key in a dev-only config, or intercepting the response in a test
  build) rather than by actually exhausting the real quota.
- Confirm the fallback triggers correctly under that forced condition, in
  at least English and one other language, using Expo Go or a local dev
  build — not a Sarvam call.

## 4. Don't touch anything else

- No changes to `voice_client.py`, the Sarvam integration, or the Render
  env vars from Module 45 — this module is purely the client-side
  fallback.
- No PPT/docs changes here — that's a separate, already-agreed-on task.

## What NOT to do

- Don't call the real production Sarvam-backed endpoint repeatedly to
  "prove" the primary path still works — Module 45 already proved that
  live; re-confirming it here just spends quota for no reason.
- Don't silently swallow a voice failure with no indication to the
  farmer — the whole point is honesty about which voice source is
  playing.

## Handoff format

```
Module: 46 — On-device TTS fallback
Status: complete | blocked | needs-decision

Current 503 handling (before this module): <what was found>
Fallback implemented: <expo-speech or equivalent, files changed>
Language/voice mapping: <en/kn/te/hi -> on-device voice, gaps if any>
Farmer-facing indicator: <what it looks like>

Tested via forced/mocked 503 (no real Sarvam quota used): <confirmed,
  which languages, Expo Go or dev build>

Known limitations:
Next recommended step:
```
