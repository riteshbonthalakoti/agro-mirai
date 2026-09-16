# MODULE 34 — FOLLOW-UP 2: Wire the acquisition adapters into the live field-creation path (close the one real gap)

Continuing AGRO MIRAI. The last audit found exactly one critical, precise
gap, and it explains everything else that's felt "not working" across
recent modules: `WeatherAdapter`, `SoilAdapter` (SoilGrids/ISRIC), and
`NDVIAdapter` (GEE, now permanently keyed) are each real, correct, and
individually tested — but nothing in the live Flask app ever calls them.
`POST /v2/fields` just saves the field row. Every "real data" proof so far
was achieved by calling an adapter directly in a script or seeding
fixtures — never through the path an actual farmer's app exercises. A
fresh field today has zero weather, zero real soil, zero NDVI, and
everything downstream 422s or runs on nothing. This follow-up wires that
connection. This is the single highest-leverage fix in the project right
now — do this before anything else, still no UI/theme work.

## 1. Wire acquisition into field creation

- In `src/agro_mirai/api/routes/farms_v2.py`, after a field is successfully
  saved in `POST /v2/fields` (around line 120, per the last audit), call
  all three adapters for that field's lat/lon and persist the results
  through the existing `DataStore` write methods (`WeatherReading`,
  `SoilSample`, `NDVIReading` — these already exist and are used correctly
  elsewhere, per the audit; reuse them, don't invent new ones).
- Decide deliberately between synchronous (in the request) and background
  (fire-and-forget after responding) based on real measured latency: call
  all three adapters once directly and time them for a real coordinate. If
  the combined real-world latency is small (a few seconds), synchronous is
  simpler and means the farmer's advisories are ready the moment Add-Field
  succeeds — prefer this if it's genuinely fast enough not to feel broken
  to a farmer waiting on the form. If it's slow (GEE queries in particular
  can be slow), use a background task and make the mobile app handle the
  "still gathering data" state honestly (a real pending/loading state, not
  a fake instant result) rather than silently blocking the UI or lying
  about readiness.
- Apply the project's own degrade-not-fail doctrine at each adapter call:
  if one of the three fails (e.g. SoilGrids times out, or GEE has zero
  scenes for the date range like today's real Bellary query did), field
  creation must still succeed — log the partial failure, leave that one
  data type absent for now, and make sure downstream endpoints already
  handle "some but not all inputs present" gracefully (per the audit,
  ExplanationService and the decision engine already degrade honestly on
  missing data — confirm this still holds with partial data, not just
  all-or-nothing).
- Also add a way to refresh this data for an *existing* field over time —
  weather and NDVI both go stale (a farmer's field shouldn't run forever
  on the single weather reading captured the day it was added). Check
  whether a scheduled/periodic refresh mechanism already exists anywhere
  in the project (a cron job, a Celery-style task, anything in `tools/`)
  and either hook into it or, if nothing exists, add the simplest correct
  version (e.g. a `POST /v2/fields/{id}/refresh-data` endpoint the mobile
  app can call, or a scheduled job if the deployment target supports one)
  — state clearly which you built and why.

## 2. Resolve `Field.soil_type` — decide and act, don't leave it decorative

The farmer-picked soil dropdown is currently stored and displayed but
consumed by nothing; the real SoilGrids adapter is a separate, unused
data source. Pick one clear resolution and implement it:
- **Preferred**: keep the dropdown as a farmer-confirmable label but have
  the real SoilGrids-sourced value be what the models actually consume —
  use the dropdown value only as a fallback when SoilGrids has no data for
  that location, and note the discrepancy if the two disagree meaningfully
  (useful for the farmer and for demonstrating explainability).
- Whatever you choose, make sure the answer to "what soil data did this
  recommendation actually use" is unambiguous and reportable, not two
  disconnected values sitting side by side.

## 3. Give crop recommendation a real path in the mobile app

`GET /v2/fields/{id}/recommendation` is real and tested but unreachable
from the app today. Add a genuine display path for it — the simplest
correct option is surfacing it as another signal card on the field's
existing advisory/detail view (reuse the existing card pattern already in
`App.tsx`, don't invent new UI chrome for this — this is a data-wiring
fix, not a design pass). Confirm it renders the same real SHAP-based
rationale text already proven at the backend.

## 4. Confirm the PPT-vs-reality mismatch is intentional and note it

Open-Meteo (no API key, real data) is what's actually implemented and
working; the PPT's Tools & Technologies slide says OpenWeatherMap. This is
a legitimate implementation choice, not a bug — Open-Meteo is a credible,
free, real weather data source. Just confirm there's no `OPENWEATHER_*`
dead code/config left over implying a switch was half-made, and flag the
one-line documentation correction Ritesh should make in the PPT/report
(`Weather Data API: Open-Meteo`, not OpenWeatherMap) — don't change the
PPT yourself, that's Ritesh's academic document.

## 5. Voice service — get it running long enough to answer the one
   outstanding question

The last audit couldn't check real audio intelligibility or the Hindi
Piper voice-file status because `services/voice` wasn't running (needs its
own torch/.venv stack). Start it for real this session if the environment
allows (check `services/voice`'s own README/Dockerfile for the exact
setup — this project has done this before per Module 12/21/23/25, don't
guess): confirm whether the Hindi Piper voice file is present now or still
missing, and generate one real audio sample per language from a real
advisory's real English text run through the real MT+TTS path, so at
least file-existence and non-empty/non-silent output can be confirmed
mechanically (true native-speaker intelligibility still needs a human
listener — say so plainly, don't overclaim what a mechanical check proves).

## What NOT to do in this module

- No UI/theme/icon/onboarding/dashboard-layout work — the crop-
  recommendation card reuses existing components exactly, it is not a
  design pass.
- Don't re-litigate or redo Module 32/33's already-proven pieces (auth,
  endpoint existence, GEE-live/cache both directions, degrade-not-fail
  discipline) — build on them.
- Don't touch the PPT file itself.

## Definition of done

- [ ] `POST /v2/fields` (or an immediately-following background job)
      genuinely calls all three acquisition adapters and persists real
      results for a real new field — proven live, real farmer, real field,
      real weather/soil/NDVI rows present afterward without any manual
      seeding script
- [ ] Partial-failure degrade-not-fail behavior confirmed at the
      acquisition step itself, not just downstream
- [ ] A real data-refresh path exists for existing fields (documented
      which mechanism was chosen and why)
- [ ] `Field.soil_type` vs. real SoilGrids data: one clear, documented
      resolution, implemented
- [ ] Crop recommendation genuinely visible to a farmer in the mobile app,
      real SHAP rationale confirmed rendering
- [ ] PPT/reality weather-provider mismatch flagged to Ritesh, no dead
      OpenWeatherMap config left lying around
- [ ] Voice service actually run, Hindi Piper file status confirmed,
      one real audio sample generated per language

## Handoff format

```
Module: 34 (follow-up 2) — Wire acquisition adapters into the live field-creation path
Status: complete | blocked | needs-decision

Acquisition wiring:
  Sync vs background decision: <real measured latency, choice, why>
  Live proof: <real new field created, real weather/soil/NDVI rows shown
    present afterward, no manual seeding>
  Partial-failure handling: <confirmed how>
  Refresh mechanism for existing fields: <what was built/hooked into>

Field.soil_type resolution: <what was decided, implemented how>

Crop recommendation in mobile app: <screen/location added, real rationale
  confirmed rendering>

PPT/reality note: <confirmed no dead config, one-line correction stated>

Voice service: <Hindi Piper file status, sample generated per language,
  explicit caveat on what mechanical check does/doesn't prove>

Known limitations:
Overall: is the core PPT-defined loop now genuinely working end to end for
  a brand-new real field with zero manual intervention: yes/no

Next recommended step:
```
