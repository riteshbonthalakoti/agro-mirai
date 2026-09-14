# MODULE 25 — Extend language support from {en, kn} to {en, kn, te, hi}

Continuing AGRO MIRAI in the existing `agro-mirai` repo. Modules 01–24 are
done (`66b003d` on `origin/main`, `/v2` verified live). This module exists
because the mobile app (built separately in Antigravity) now offers Telugu
and Hindi alongside English/Kannada — the backend needs to genuinely
support them, not just accept the codes.

Read `CLAUDE.md`, `PROGRESS.md`, `decisions/0012-voice-interface.md` (or
wherever `V1_LANGUAGES` is originally defined and justified — grep for it,
don't assume the filename), `src/agro_mirai/voice/`, and
`specs/core/enums.md` first.

Confirm `git config user.name`/`user.email`.

## Do not assume — verify, the same discipline every prior module used

`V1_LANGUAGES = {en, kn}` was a deliberate, documented decision, not an
arbitrary default. Before writing any code:

1. **Check what the actual voice stack supports.** AI4Bharat's components
   (IndicTrans2 for translation, IndicConformer for STT, Piper/vits_rasa_13
   for TTS) are multilingual Indic-language projects — grep their model
   configs / loaded checkpoints in `src/agro_mirai/voice/ai4bharat_voice.py`
   and `services/voice/` to confirm Telugu and Hindi are actually among the
   loaded/supported languages for STT, TTS, and translation, not just
   plausible in theory. If a language is missing a model checkpoint or
   voice, that's a real blocker to report back, not something to silently
   work around.
2. **Check the models that produce advisory content itself** — crop
   recommendation, irrigation, disease risk. Confirm whether any
   farmer-facing strings/explanations are hardcoded to `en`/`kn` anywhere
   (`ExplanationService`, any hardcoded crop-name translation dictionaries,
   any `enums.md` values with only two localized labels) that would need
   `te`/`hi` entries added.
3. **Report exactly what you find before changing validation rules** — if
   the voice stack genuinely covers all four languages, proceed with the
   full change below. If TTS/STT/translation only genuinely covers a subset
   (e.g. voice works for `te` but not `hi`, or vice versa), tell me that
   explicitly and we'll decide together whether to ship partial voice
   coverage with a clear per-language capability flag, or hold `te`/`hi` to
   text-only until the voice side catches up. Do not silently downgrade
   silently or silently expand past what's actually working.

## If genuinely supported, make the change

- `V1_LANGUAGES` (wherever canonically defined) becomes `{en, kn, te, hi}`.
- `PATCH /v2/farmers/me` and the registration flow's `preferred_language`
  validation accept all four; the 400 error message listing valid values
  needs updating too (I've seen it hardcode "en, kn" — check it, don't
  leave a stale error message that undersells what's actually supported).
- `GET /v2/advisories/{id}/audio`'s `?language=` override and its default
  language derivation both need to accept `te`/`hi`.
- `POST /v2/stt` — confirm request/response language handling (if any
  language hint is passed) covers the new codes.
- `specs/core/openapi.yaml` — enum values for language fields, additive
  per the frozen-contract rule (this is exactly what "additive-only"
  exists for). `specs/core/enums.md` updated to match.
- Any UI-facing static string set (language names shown in-script,
  e.g. "తెలుగు" / "हिन्दी") — confirm correct native-script spelling,
  don't guess.

## Tests

- Update/extend the existing language-validation tests
  (`preferred_language` accept/reject cases) to cover `te`/`hi` in both
  the accept and reject-invalid-code paths.
- If voice coverage is genuinely full for all four: extend
  `services/voice` tests to include `te`/`hi` cases matching the existing
  `en`/`kn` test shape.
- Full regression pass — confirm nothing in the existing `en`/`kn`-only
  test suite silently broke from a broadened enum.
- `check_specs.py` pass.

## Update doctrine

`CLAUDE.md`, `PROGRESS.md` (new module row), a new ADR
(`decisions/0021-language-expansion-te-hi.md` or similar) documenting
what was verified working vs. what (if anything) is partial, and why.
Commit and push. **No `Co-Authored-By` line** per current instruction —
confirm this is still the standing rule before you commit; if it's
changed since, use whatever the current rule is.

## Definition of done

- [ ] Actual voice-stack coverage for `te`/`hi` verified, not assumed —
      findings reported explicitly, including any partial-coverage case
- [ ] `V1_LANGUAGES` and all validation paths updated to match what's
      genuinely supported (not silently wider than what's real)
- [ ] `openapi.yaml` / `enums.md` updated additively
- [ ] Stale "en, kn"-only error messages found and fixed
- [ ] Tests extended for the new languages, full regression green
- [ ] `check_specs.py` pass
- [ ] ADR documents the real coverage state
- [ ] Pushed to `origin/main`

## Handoff format

```
Module: 25 — Extend language support to {en, kn, te, hi}
Status: complete | blocked | partial (specify which language/capability)
Voice stack coverage found: <what's genuinely supported per language,
  with evidence — model configs, not assumptions>
Changes made: <files, what changed>
Stale hardcoded en/kn references found and fixed: <list>
Tests: <new/updated, pass/fail>
Full regression: <pass/fail>
check_specs.py: pass/fail
Known limitations:
Next recommended step:
```
