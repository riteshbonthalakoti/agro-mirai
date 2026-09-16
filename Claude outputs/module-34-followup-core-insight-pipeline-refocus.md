# MODULE 34 — FOLLOW-UP: Refocus on the core insight pipeline only. Stop all UI work.

Continuing AGRO MIRAI. This is a course-correction, not a new module. Read
this whole thing before touching anything — the direction changed.

## Why this exists

The PPT (`AGRO_MIRAI2.1.pptx`, the actual VTU capstone deliverable this
project is graded against) states the project's entire purpose in one
line, repeated across the Abstract, Objectives, and Problem Statement
slides: **integrate satellite, weather, soil, and field data to deliver
hyper-localized, predictive farming insights — crop recommendation,
irrigation planning, and disease-risk detection — delivered through a
simple, multilingual, voice-enabled interface.** That is the whole
product. Nothing in the PPT's Scope, Objectives, or Functional
Requirements sections mentions app theming, icon sets, onboarding
sequences, dropdown pickers, or dashboard layout. Session time got spent
on exactly those things across recent modules, and Ritesh has called this
out directly: it's over-complicated, off the core mission, and time is
short. This follow-up stops that drift.

**Effective immediately: no UI, theme, icon, dropdown, onboarding, or
dashboard-layout work of any kind until this follow-up is complete and
reviewed.** Items 1, 2, 4, 5, 6, 7, 8 from the last message are explicitly
parked — not abandoned, just not now. Item 9 (dashboard) stays parked until
Ritesh sits down and decides on it, per his own instruction. Item 3
(language re-ask bug) already got fixed and is fine to keep, since it's a
functional bug not a design choice — don't revert it, just don't build on
it further right now.

## The actual goal, restated precisely

For a given farmer, field, and moment in time, the system must:
1. Pull real weather data for that field's location.
2. Pull real satellite data (NDVI via Google Earth Engine) for that
   field's location.
3. Pull real soil data for that field.
4. Combine those with the field's crop and history.
5. Produce a genuinely useful insight — crop suitability, irrigation
   need, or disease risk — grounded in that real data, with an honest
   explanation of why (the PPT's own "Explainable AI — SHAP and feature
   importance" requirement).
6. Deliver that insight to the farmer as both text and real spoken audio,
   in whichever of the four languages the farmer has selected.

That loop, done correctly and provably, end to end, for a real field with
real data, is the entire deliverable. Everything else is secondary.

## What Module 32/33 already proved works (don't redo this)

Real endpoints exist and were live-tested: `GET /v2/fields/{id}/irrigation`,
`GET /v2/fields/{id}/disease-risk`, `GET /v2/fields/{id}/advisories`,
`GET /v2/fields/{id}/recommendation` (crop), the GEE live/cache NDVI path
(both directions proven), real SHAP/rule-based rationale text, and audio
delivery (backend TTS for remote advisories, on-device `Speech.speak()`
for local ones). Auth, field creation, and language switching for app
chrome all proved out too. This is real, substantial, working coverage of
the core loop — Ritesh should know that clearly, since the frustration in
the last message reads as "we're not focusing on the main function," but a
large amount of the main function is actually already built and verified.
State this plainly in your handoff so it's not lost.

## What this follow-up actually needs to verify and close

This is an audit-and-close pass on the core pipeline specifically, not a
new feature build, and not a repeat of Module 32/33's already-done backend
proof:

1. **Weather data — genuinely real, not fixture-only.** Confirm the
   `OpenWeatherMap API` integration (per the PPT's own Tools &
   Technologies slide) is live-callable with a real API key today, for a
   real field's real lat/lon, not only served from seeded/fixture rows in
   testing. If it's currently fixture-only in practice (no real weather
   API key configured, or the code path never actually calls out), that's
   the single most important gap to name clearly — the whole irrigation
   and disease-risk pipeline is only as real as its weather input.
2. **Satellite (NDVI/GEE) — confirm it's the default path, not the
   exception.** Module 33 proved GEE-live works when a key is present but
   the key was temporary and deleted after. Confirm current real status:
   is a permanent GEE service account key now configured so the live path
   is the normal case, or does the app still run on NDVI cache by default?
   State this plainly — if it's cache-by-default, that's a real, current
   limitation to report honestly, not something to imply is "live."
3. **Soil data — confirm what "soil data" currently means in the running
   system.** Is it genuinely measured/looked-up per field, or is it
   farmer-entered at Add-Field time (a dropdown/typed value with no
   external soil-data source)? Either is fine as a documented MVP choice,
   but confirm which one is actually true today and state it precisely —
   don't let "soil data" stay ambiguous.
4. **End-to-end accuracy check, not just "did it return 200."** For one
   real field with real weather + real GEE NDVI + real soil input, walk
   through the irrigation and disease-risk outputs and confirm the numbers
   are actually reasonable given the real inputs (e.g. does a real high-
   rainfall week actually lower the recommended irrigation depth; does a
   real low-NDVI reading actually raise disease risk) — this checks the
   pipeline's *correctness*, not just that it doesn't crash. If the model
   logic is rule-based/heuristic rather than a trained model in places,
   confirm that's accurately reflected in what the app tells the farmer
   (no claiming ML sophistication the current implementation doesn't have).
5. **Voice delivery — confirm the full loop, not just that TTS exists.**
   For a real advisory in each of the four languages, confirm real audio
   is actually produced and understandable (native-speaker-plausible, not
   just "a file was returned") — this ties back to the `// unsure, verify`
   flags Module 34's UI pass left on some kn/te/hi crop/soil terms; that
   kind of unverified translation is a genuine risk if it's feeding TTS
   pronunciation too, so check whether it does.
6. **Crop recommendation module — confirm this exists and is reachable.**
   The PPT lists crop recommendation as a first-class module alongside
   irrigation and disease-risk. Module 32/33 tested `GET /v2/fields/{id}/
   recommendation` at the backend, but confirm the mobile app actually
   surfaces this to the farmer somewhere real (not just Home's severity
   cards for irrigation/disease) — if it's backend-only right now with no
   mobile UI path to see it, name that as a real functional gap (not a UI
   *polish* gap — a farmer literally cannot see this output today, which
   is different from the button looking ugly).

## CLI/API/account setup — yes, use what's installed

Ritesh has installed relevant CLIs/MCPs and is offering to provision
whatever's missing (Google Cloud/Earth Engine, OpenWeatherMap, any other
real API this loop needs). Use them:

- If a permanent GEE service account key is the blocker for item 2, set
  one up properly this time (not a temporary key deleted after one test)
  — check what's already available via the installed Google Cloud CLI
  before asking Ritesh to do anything manually.
- If a real OpenWeatherMap (or equivalent) API key is missing or unset,
  say exactly what's needed and, if a CLI/account path exists to get it
  without a manual browser flow, use it; otherwise tell Ritesh precisely
  what to go get and where.
- Do not fabricate, mock, or hardcode a "looks real" substitute for a
  missing key — an honestly-reported gap is fine, a fake credential
  pretending to be real is not, per this project's whole doctrine.

## Definition of done

- [ ] Weather data source confirmed real-live vs fixture-only, precisely
- [ ] GEE/NDVI confirmed live-by-default vs cache-by-default, precisely,
      and if live-by-default isn't set up yet, do it now with a permanent
      key (not another temporary one)
- [ ] Soil data source confirmed (measured/looked-up vs farmer-entered)
- [ ] One real field's full pipeline walked through end to end with real
      inputs, output correctness sanity-checked against those real inputs
- [ ] Voice output for a real advisory checked in all 4 languages for
      actual intelligibility, not just file-existence
- [ ] Crop recommendation module confirmed reachable by a real farmer in
      the mobile app, or reported as a real gap if it isn't
- [ ] Zero UI/theme/icon/onboarding/dashboard work performed

## Handoff format

```
Module: 34 (follow-up) — Core insight pipeline verification and close-out
Status: complete | blocked | needs-decision

What's already real and working (recap from Module 32/33, not redone):
  <list>

Weather data: <real-live confirmed how, or fixture-only, precisely>
GEE/NDVI: <live-by-default confirmed how, or cache-by-default; permanent
  key set up: yes/no>
Soil data: <what it actually is today>
End-to-end pipeline correctness check: <real field, real inputs, output
  sanity vs. inputs, any correctness issues found>
Voice output in all 4 languages: <intelligibility check results>
Crop recommendation reachability in mobile app: <confirmed reachable, or
  named as a real gap>

Real gaps found (functional, not cosmetic):
Overall: is the core PPT-defined loop (location+crop -> real data ->
  insight -> voice+text in preferred language) genuinely working end to
  end today: yes/no, and exactly what's missing if no

Next recommended step:
```
