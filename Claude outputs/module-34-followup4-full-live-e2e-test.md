# MODULE 34 — FOLLOW-UP 4: Full manual, live, end-to-end test of the real app on Ritesh's phone — no code review, no curl, only what actually happens on the device

Continuing AGRO MIRAI. Ritesh's concern, stated directly: enough has been
"confirmed" by code review, curl, and isolated backend proofs across this
whole session that he no longer trusts the system is genuinely working as
one connected product. He wants it proven the only way that actually
counts: driven live, end to end, on his real phone, over his real wireless
connection, watching it happen — not a script, not a log, not a claim.

This module is a single continuous live test session. Do not report
anything as "confirmed" from code inspection in this module — if a step
can't be driven live on the device, say so plainly and mark it unverified,
don't substitute a curl call or a grep result as if it were equivalent.

## Setup

- Confirm the phone is connected (same wireless network as yesterday) and
  Artemis/device tools see it, same as prior sessions.
- Rebuild and install the dev client fresh (`expo run:android` or
  equivalent) so the device is running the actual current working-tree
  code, not a stale build from an earlier session today.
- Start the real backend bound to `0.0.0.0`, confirm the phone's app is
  pointed at the correct current LAN IP (this has changed at least once
  today already — verify, don't assume).
- Confirm `.env` currently has the real keys (Supabase, GEE, OpenWeatherMap)
  intact before starting — this got wiped twice earlier this session, so
  check it explicitly as step zero.

## The test script — walk through every one of these live, on the device, in order

For each numbered step: state what you did, what you saw on the actual
phone screen (a real screenshot, not a description), and pass/fail. If a
step fails, stop and report it precisely rather than skipping ahead — a
broken step earlier in the flow may explain failures later in it.

1. **Fresh install, first launch.** Confirm the app opens in English by
   default, before any location/language prompt appears.
2. **Language/location confirmation screen.** Confirm it appears once, in
   English, and correctly detects/suggests a regional language.
3. **Auth — real OTP flow.** Enter a real 10-digit number (confirm no `+91`
   needs to be typed), request OTP, read the real OTP from the backend log,
   enter it, confirm login succeeds and lands on Home.
4. **Add a field — the full acquisition pipeline, live.** Use "Use Current
   Location" (confirm real GPS coordinates + checkmark display correctly,
   per the earlier fix), pick a crop and soil type from the dropdown, name
   the field, submit. Watch what the app shows while weather/soil/NDVI are
   being acquired — confirm it's an honest loading/pending state, not a
   silent gap or a fake-instant result.
5. **Confirm real data landed**, from the app's own screens (not a DB
   query) — does the field's detail view show real soil/weather info once
   acquisition finishes?
6. **Crop recommendation card.** If it was built in follow-up 3, confirm it
   appears on this real field and shows a real recommendation with
   rationale text. If it was not built yet, state that plainly here as
   still-missing rather than skip the step silently.
7. **Irrigation advisory.** Confirm a real recommendation appears (not a
   422) now that the soil-moisture fallback is in place — screenshot the
   actual numbers shown.
8. **Disease-risk / AI Scan.** Take a real photo (or choose from gallery),
   submit, confirm a real result renders — correct loading state, correct
   result labeling (CNN vs. environmental-fallback, in plain language).
9. **Advisories tab / Records.** Confirm real advisories show up, confirm
   whether History/Records persistence has changed since the earlier
   session (it was confirmed client/session-only before) or is still that
   way — state current true status.
10. **Voice playback.** Tap play on a real advisory's audio. Confirm actual
    audible sound plays on the device speaker — this is the one step
    Ritesh himself should listen to and judge, not something Claude Code
    can self-certify. Tell him exactly which button to tap and what to
    listen for (does it produce real, understandable speech in the
    selected language).
11. **Language switch, full sweep.** Switch to each of the four languages
    from Settings' dropdown picker, and for each one, visit Home, Records,
    Settings, and the field detail/advisory screens — screenshot each,
    confirm visible text actually changes app-wide, not just on Home.
12. **Bug report flow.** Navigate to Settings → Report a Problem, submit a
    real test report (one of the preset reasons, plus a photo attach),
    confirm a real success state, and confirm via a real backend check
    that the row was actually created.
13. **Nav bar / status bar visual check.** On this real device, confirm the
    status bar is legible (not white-on-white) and the bottom nav bar
    doesn't overlap content on any screen visited above.
14. **Full navigation pass.** Tap through every tab and every card one more
    time, end to end, confirming nothing dead-ends, nothing throws a raw
    error to the screen, and every error state that does appear goes
    through the consolidated toast/notification system, not a bare crash
    or a silent no-op.

## What to explicitly flag, not silently skip

- Anything from this list that was previously "confirmed" by code review,
  curl, or a background agent's own self-report but is NOT re-confirmed
  live in this pass — say so by name, don't let a prior claim stand in for
  today's live proof.
- Any step where the phone's real behavior contradicts what was reported
  earlier this session (e.g. if the crop-rec card doesn't actually render
  despite being "reported complete") — this is exactly the kind of gap
  Ritesh is worried about, so surface it precisely, don't soften it.
- The OpenWeatherMap 401 — confirm current status (fixed or still blocked)
  since Ritesh may have rechecked the key by the time this runs.

## What Ritesh needs to do himself (tell him exactly, step by step, as you reach each one)

- **Step 10 (voice)**: listen to the actual audio and judge intelligibility
  — Claude Code can confirm a file played, only Ritesh can confirm it
  sounded right.
- **The OpenWeatherMap key**: if still 401ing at test time, tell him
  exactly what to check (copy-paste accuracy from the provider dashboard,
  or wait out the activation window) — don't guess on his behalf.
- Anything requiring a decision (e.g. if a step reveals a real product
  question, like whether History/Records should get real backend
  persistence) — surface it as a question for him, don't decide and build
  it silently in this module.

## What NOT to do in this module

- No new features. This is verification only — if a bug is found, name it
  precisely; only fix it if it's a one-line, obviously-safe fix blocking
  the test from continuing (state clearly that you did this and why).
- No UI/theme/onboarding/dashboard work.
- No commits — this stays a verification pass in the current working tree.

## Handoff format

```
Module: 34 (follow-up 4) — Full live device verification
Status: complete | blocked

Setup: <.env confirmed intact, backend IP confirmed, dev client rebuilt>

Step-by-step results (1-14): <pass/fail, real screenshot per step, exact
  on-device behavior observed>

Discrepancies found vs. prior "confirmed" claims: <named precisely>

Items needing Ritesh's own judgment/action: <voice intelligibility,
  OpenWeatherMap key, any product decisions surfaced>

Overall: does the real app on a real phone, talking to the real backend,
  actually deliver the full core loop end to end today: yes/no, and
  exactly what breaks if no

Next recommended step:
```
