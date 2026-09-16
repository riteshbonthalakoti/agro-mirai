# ADR 0024 — User-entered content and the language switcher

**Status:** accepted
**Date:** 2026-09-15
**Module:** 34 — mobile disease-scan fix, adaptive nav bar, complete
language switching
**Related:** `decisions/0021-language-expansion-te-hi.md` (the four
operational UI languages this decision assumes), `specs/core/schema.yaml`
(`Field.current_crop`/`recommended_crop` enum, `Field.name`/`notes` free
text)

## Context

Module 34 swept `mobile/App.tsx` for hardcoded, untranslated
user-facing strings so the language switcher (en/kn/te/hi) covers every
screen. That sweep raised the real architectural question this ADR
answers: when a farmer enters content in the UI (a field name, a crop
selection) while the app is set to one language, what should another
farmer — or the same farmer after switching languages — see later?

Two categories of farmer-facing content exist in this app, and they
needed two different answers:

1. **Fixed-enum fields** — `current_crop` (`Field.current_crop`,
   `specs/core/schema.yaml` line 83, `enum: crop_type`) and `soil_type`
   (line matching `SOIL_TYPES` in `mobile/App.tsx`). These are not free
   text — the farmer picks from a fixed chip list
   (`CROP_TYPES`/`SOIL_TYPES` in `App.tsx`), and the backend's OpenAPI
   contract constrains them to the same 22/9-value enums the crop and
   irrigation models were trained against (Module 06/18).
2. **Genuinely free text** — `Field.name` (`type: string, required: true`,
   schema.yaml line 22/77) and any farmer-written notes. No enum, no
   fixed vocabulary; the farmer can type anything.

## Finding: the enum fields were a real, if silent, bug

`App.tsx` already stored `current_crop`/`soil_type` correctly — the
literal enum key (`'rice'`, `'black'`, etc.), never a translated
display string; `analyzeLeafImage`/`submitField`'s payload construction
sends `addFieldCrop`/`addFieldSoilType` straight through unmodified, and
`specs/core/schema.yaml` confirms the backend only ever sees and stores
that same key. So the stored value was already language-independent —
no migration, no backend change needed.

The bug was on the **display** side only: the Add Field screen's chip
labels (`CROP_TYPES.map(c => ... <Text>{c}</Text>)`) and the Crop
Health screen's `renderCropFacts()` (`selectedField.current_crop`) both
rendered the raw English enum key directly, in every UI language — a
Kannada-language farmer would see `"kidneybeans"` printed literally
next to their own-language advisory text. Fixed in this module by
adding `CROP_TYPE_LABELS`/`SOIL_TYPE_LABELS` (`App.tsx`, near the
`CROP_TYPES`/`SOIL_TYPES` constants) — one display-string map per
language, looked up by the stable key at render time in three places
(the crop chip list, the soil chip list, and `renderCropFacts`'s value
row) — while every write path continues to send the untouched key.

## Decision: free text is shown as-is, not auto-translated

For `Field.name` and any future free-text field, the two options
considered:

- **Option A — auto-translate via machine translation.** The backend
  already has a live AI4Bharat/IndicTrans2 translation model wired up
  for advisory audio (`voice_client.py`, Module 23/25) — technically
  reachable from a new field-name translation call. Rejected for this
  content: MT would silently alter a farmer's own words (their field's
  name, in their own language or script, possibly a proper noun or a
  transliterated dialect term IndicTrans2 was never evaluated against)
  every time another farmer or an admin viewer's language differs from
  the entry language. That is a real trust and data-integrity risk for
  content that is supposed to be *this farmer's own label for their own
  land* — wrong here even if the MT quality were perfect, because the
  farmer never asked their words to be rewritten. It also adds a new
  paid/compute-cost dependency (translation calls) to a plain read path
  that has never needed one, and it is not reversible without storing
  a second, translated copy no one asked for.
- **Option B — always display the farmer's own text as-is, regardless
  of UI language.** No new infrastructure, no new dependency, no
  possibility of the app putting words in a farmer's mouth. The only
  cost is that a field named in Kannada script stays in Kannada script
  when a different-language viewer (an admin, or the same farmer after
  switching languages) looks at it — expected and correct: it is the
  farmer's own label, not app chrome.

**Chosen: Option B.** No code change was needed for this — `App.tsx`
already renders `selectedField.name` verbatim everywhere (e.g. the
Settings screen's active-field row, fixed in the same pass to fall back
to a *translated* crop label instead of a raw enum key rather than
touching the `name` path at all). This ADR exists to record that this
is a deliberate, considered choice for this module, not an oversight —
so a future module does not "fix" it by wiring in auto-translation
without repeating this tradeoff discussion.

## Tradeoff Ritesh should know

Auto-translating free text is the direction that scales better for a
future multi-region deployment (e.g. an admin in one state genuinely
unable to read a farmer's notes written in another script) — Option B
punts that problem rather than solving it. If that need becomes real,
revisit as a new, explicit opt-in ("translate this note" button/toggle
showing both the original and the MT output side by side, never
silently replacing the original), not a blanket always-on translation
of stored farmer text. This is the safer, reversible default the
module brief asked for, not a claim that MT is unwanted forever.

## What did NOT need changing

- `Field.name`/`notes` storage and API contract — already correctly
  typed as free-text `string` in `schema.yaml`; no backend change.
- `Field.current_crop`/`soil_type` storage — already correctly stored
  as the stable enum key; no backend or payload change, display-only
  fix in `mobile/App.tsx`.

## Known limitations

- The kn/te/hi entries in `CROP_TYPE_LABELS`/`SOIL_TYPE_LABELS`
  (`mobile/App.tsx`) are standard agricultural terms but were not
  reviewed by a native speaker in this session; `kidneybeans`,
  `mothbeans`, `jute` (Telugu), and `laterite`/`peaty` (all three
  languages) are flagged inline in the source with a `// unsure,
  verify` comment as the ones most likely to need correction.
- This ADR covers `Field.name`/`notes` and the crop/soil enums only —
  it did not audit every free-text field that may exist elsewhere in
  the schema (e.g. feedback comments); the same Option B default should
  apply there unless a future module finds a reason to reconsider.
