# MODULE 34 — FOLLOW-UP 5: Add the missing sowing-date field (fixes irrigation for every farmer) + translate disease-scan result text

Continuing AGRO MIRAI. Follow-up 4's live, on-device test found two precise,
real bugs — this module fixes both. Do item 1 first; it's the highest-
priority fix in the whole project right now, since it silently blocks
irrigation for every single farmer using the app today.

## 1. Add a sowing/planting date to Add-Field (fixes irrigation for real)

Confirmed live: `/v2/fields/{id}/irrigation` requires `season`, which is
derived from `sown_on`, and the mobile Add-Field form has zero UI to
collect it — confirmed by grep, zero references to `sown_on` anywhere in
`App.tsx`. Every field created through the real app hits this same 422,
permanently, regardless of the soil-moisture fallback (which is confirmed
working correctly on its own).

- Find exactly how `sown_on`/`season` is consumed server-side (check
  `farms_v2.py`, whatever derives `season` from it, and the `Field`/
  `SoilSample` schema) to confirm the exact field name, type, and format
  expected.
- Add a real date input to the Add-Field form in `App.tsx`, in the same
  place/step as the crop and soil pickers (don't add a separate screen for
  one field) — use whatever date-picker approach the app already uses
  elsewhere if one exists, otherwise the simplest correct native date
  picker for Expo (check current Expo docs, don't assume an old API still
  applies, same discipline as the disease-scan fix).
- Decide sensibly on required-vs-optional: if a genuinely reasonable
  default exists (e.g. defaulting to today's date when the farmer is
  adding a field for an already-planted or about-to-be-planted crop) that
  may be better UX than blocking the form — but if defaulting to "today"
  would silently produce wrong irrigation math for a crop actually sown
  weeks ago, require the farmer to pick a real date instead. State clearly
  which you chose and why.
- Route the new field's label/hint text through `t.*` from the start, all
  4 languages — don't reintroduce the same i18n gap that's been fixed
  repeatedly this session.
- Prove it live, the same way follow-up 4 did: real device, real farmer,
  create a field with a real sowing date, confirm `/v2/fields/{id}/
  irrigation` now returns a real 200 with a real recommendation, not a
  422 — paste the real request/response and a real screenshot of the
  advisory rendering in the app.
- Also confirm `/v2/fields/{id}/advisories` reflects this for the same
  field, not just the isolated irrigation endpoint.

## 2. Translate the disease-scan result text

Confirmed live: the CNN-vs-environmental-fallback badge correctly
translates, but the result headline and rationale text ("Generic fungal
disease risk..." etc.) stay in English regardless of the active language,
because this text is generated server-side and never passed through
client-side i18n.

- Find where this text is generated (`ExplanationService` or wherever the
  disease-risk rationale string is built server-side) and confirm whether
  it's already structured/templated (e.g. built from discrete parts:
  disease name, risk level, confidence, method) or a single opaque string.
- If it's structured: the cleanest fix is having the backend return the
  structured parts (disease-name key, risk-level key, confidence number)
  rather than a pre-rendered English sentence, and building the final
  sentence client-side through `t.*` — this also fixes the same problem
  for irrigation/advisory rationale text if it has the same issue (check
  while you're in there, since this may be a broader pattern, not scan-
  specific — Module 33/34 already confirmed advisory audio text goes
  through a *separate* real MT path via IndicTrans2, so don't break that;
  this is specifically about text *rendered in the app UI*, not the
  voice-audio pipeline).
- If restructuring the backend response is too large for this module,
  the acceptable fallback is running the existing rendered English string
  through the same real IndicTrans2 MT path the advisory-audio pipeline
  already uses (reuse it, don't build a second translation path) before
  displaying it — but prefer the structured/client-rendered fix above if
  it's not significantly more work, since it's the more correct, lower-
  latency, and more accurate long-term fix (MT on short structured labels
  is more reliable than MT on a full generated sentence).
- Prove it live: real device, real disease scan, Telugu active, confirm
  the full result card — headline and rationale, not just the badge — is
  genuinely in Telugu. Repeat for at least one more language to confirm
  it's not a single-language fix.

## What NOT to do in this module

- No UI/theme/onboarding/dashboard work beyond the one new date-picker
  field itself.
- Don't touch Records/History persistence or the onboarding-carousel-
  language-order question — those are still open product decisions
  Ritesh hasn't made yet, not bugs to silently resolve here.
- Don't build the crop-recommendation card in this module either — that's
  its own scoped piece of work, keep this one tight to the two fixes above.

## Definition of done

- [ ] Sowing-date field added to Add-Field, routed through i18n, sensible
      required/optional decision stated and justified
- [ ] Live-proven: real field creation with a real sowing date produces a
      real 200 irrigation recommendation, not a 422
- [ ] Advisories endpoint confirmed reflecting the same fix, not just the
      isolated irrigation endpoint
- [ ] Disease-scan result headline + rationale genuinely translate,
      live-proven in at least 2 non-English languages
- [ ] Checked (not necessarily fixed unless trivial) whether the same
      untranslated-server-text pattern affects irrigation/advisory
      rationale text elsewhere, reported either way

## Handoff format

```
Module: 34 (follow-up 5) — Sowing-date fix + disease-scan i18n fix
Status: complete | blocked | needs-decision

Sowing-date fix:
  Field added: <where in the form, required/optional decision + why>
  Backend field/format confirmed: <exact name/type used>
  Live proof: <real device, real field, real 200 irrigation response>
  Advisories cross-check: <confirmed>

Disease-scan i18n fix:
  Root cause confirmed: <structured vs opaque string, which approach taken>
  Implementation: <files>
  Live proof: <2+ languages, real screenshots, full card including
    headline/rationale>
  Same pattern checked elsewhere (irrigation/advisory rationale): <found/not found>

Known limitations:
Overall: is irrigation now genuinely usable for a brand-new real field,
  and is disease-scan output fully localized: yes/no

Next recommended step:
```
