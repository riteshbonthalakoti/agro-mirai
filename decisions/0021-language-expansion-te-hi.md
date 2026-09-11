# ADR 0021 — Language expansion: `V1_LANGUAGES` {en, kn} -> {en, kn, te, hi}

**Status:** accepted
**Date:** 2026-09-11
**Module:** 25 — extend language support from {en, kn} to {en, kn, te, hi}
**Related:** supersedes the `V1_LANGUAGES = {en, kn}` scope decision
documented in `specs/core/voice-interface.md`'s "Supported language set
for v1" section (no standalone ADR exists for the original Module 12
scope call — it lives in that spec file, updated alongside this ADR) and
referenced in `decisions/0019-deployment-architecture.md`;
`specs/core/enums.md`'s `language_code` list (unchanged, already listed
all 8 candidate languages).

## Context

The mobile app (built separately in Antigravity, outside this repo) now
offers Telugu and Hindi alongside English/Kannada in its language
picker. `V1_LANGUAGES = {en, kn}` (`src/agro_mirai/voice/interface.py`)
was a deliberate, documented Module 12 decision, not an arbitrary
default — widening it needed the same evidence-before-code discipline
every prior module used, not an assumption that "AI4Bharat is Indic, so
it must already work."

## What was actually verified (not assumed)

Checked against the real HuggingFace model cards for the two AI4Bharat
models already loaded, plus the TTS models this module wired in:

| Capability | Model | `te` | `hi` | Evidence |
|---|---|---|---|---|
| Translation | IndicTrans2 dist-200M (en-indic / indic-en) | yes | yes | Model card usage example; FLORES-200 tags `tel_Telu`/`hin_Deva`, added to `_FLORES_TAGS` |
| STT | `ai4bharat/indic-conformer-600m-multilingual` | yes | yes | Model card: trained on 22 official Indian languages, explicitly lists `hi`/`te` in its language-code set |
| TTS | `ai4bharat/vits_rasa_13` (already used for `kn`) | **yes** | **no** | Model card's 13-language set: Assamese, Bengali, Bodo, Dogri, **Kannada**, Maithili, Malayalam, Marathi, Nepali, Punjabi, Sanskrit, Tamil, **Telugu** — no Hindi |
| TTS | Piper (already used for `en`) | n/a | **yes** | `rhasspy/piper-voices` ships `hi_IN-rohan-medium` |

**Real finding, not a partial-coverage case:** every one of translation/
STT/TTS is individually confirmed real for both `te` and `hi` — but TTS
splits across two different backends per language (`kn`/`te` ->
vits_rasa_13, `en`/`hi` -> Piper), the same shape the `en`/`kn` split
already had for a different reason (Piper has no Kannada voice; here
vits_rasa_13 has no Hindi voice). This is not a gap to hold behind a
capability flag — both backends are real, loaded models, just not the
same one for every language. Language ID (Whisper-tiny's restricted
first-decoder-token comparison) also extends cleanly: Whisper's standard
~99-language token vocabulary already includes `<|hi|>`/`<|te|>`
alongside the `<|en|>`/`<|kn|>` tokens already compared.

## Decision

Widen `V1_LANGUAGES` to `{en, kn, te, hi}` and wire every touchpoint
(`ai4bharat_voice.py`'s translate/ASR/TTS/LID, `bhashini_voice.py`
generically via the shared constant, `voice_v2.py`'s dynamic
`sorted(V1_LANGUAGES)` error messages, `openapi.yaml`'s three
`V1_LANGUAGES`-scoped enums, `PATCH /v2/farmers/me` and `POST
/v2/auth/register` validation) to the new set. `ta`/`mr`/`bn`/`gu`
remain in `enums.md`'s full `language_code` list as future scope, not
wired to any voice adapter — `V1_LANGUAGES` stays the single source of
truth for what's operational today.

## Stale hardcoded gaps found and fixed (real, not hypothetical)

- **`farms_v2.py`'s `_ALLOWED_LANGUAGE_CODES = {"en", "kn"}`** — a
  second, locally-hardcoded copy of the language allowlist that had
  silently drifted from `V1_LANGUAGES` (both were `{en, kn}` at the
  time, so no observable bug yet, but two sources of truth for the same
  set is exactly how they *would* drift). Replaced with a direct import
  of `V1_LANGUAGES`.
- **`POST /v2/auth/register` had zero `preferred_language`
  validation** — despite `openapi.yaml`'s `RegisterRequest` schema
  already declaring an 8-value enum, the route accepted any string
  unvalidated. Added real validation against `V1_LANGUAGES` (the
  voice-operational set, not the full 8-language aspirational schema
  enum — accepting `ta`/`mr`/`bn`/`gu` today would register farmers
  whose `preferred_language` the voice stack can never actually honor,
  which is the exact "silently expand past what's actually working"
  failure mode this module was told to avoid). `PATCH /v2/farmers/me`'s
  inline openapi enum (`[en, kn]`, narrower than `Farmer`'s own 8-value
  schema enum) is widened to match — both mutation points are now
  consistent with each other and with reality.
- **`field.html`'s "Listen in Kannada" known-limitation note** — stale
  since Module 23 shipped `GET /v2/advisories/{id}/audio`; the note
  claimed no endpoint exposes TTS audio at all, which stopped being true
  two modules ago. Corrected wording (this legacy `/v1`-era dashboard
  still doesn't wire up playback itself, but the endpoint exists and now
  serves all four languages) — not in scope to add real audio playback
  to this template.

## What did NOT need changing

- `specs/core/enums.md`'s `language_code` list — already listed all 8
  candidate languages (`en, hi, kn, ta, te, mr, bn, gu`), was never
  `{en, kn}`-only. Clarified its text to point at `V1_LANGUAGES` as the
  operational subset instead of the stale "tracks what the AI4Bharat
  stack covers" claim.
- `voice_client.py`'s `synthesize_advisory_audio` / `transcribe_audio`
  and `voice_v2.py`'s error-message construction — both already derive
  their language handling generically from `V1_LANGUAGES` /
  farmer-supplied codes rather than hardcoding `en`/`kn`, so they widen
  automatically with no code change.
- `Advisory`/`Field`/`Farmer` schemas in `specs/core/schema.yaml` and
  `openapi.yaml`'s `Farmer`/`RegisterRequest` — already declared the
  full 8-language enum.

## `Explanation.summary_kn` — additive fields, not a rename

`Explanation` (`src/agro_mirai/models/explanation.py`) is internal-only:
never persisted, never exposed via any API response (`Advisory.body`
concatenates `summary_en` unmodified per ADR 0011). Real end-user audio
localization for `te`/`hi` already flows entirely through the generic
`GET /v2/advisories/{id}/audio` translate-then-synthesize path, which
needed no `Explanation`-level changes at all. Per the additive-only
contract rule, `summary_kn` (frozen at its existing hardcoded en->kn
meaning) was not renamed or repurposed. Two new optional fields were
added instead — `summary_translated: str | None` and
`summary_translated_lang: str | None` — and `explain_crop`/
`explain_irrigation`/`explain_disease` gained an optional
`target_lang: str = "kn"` parameter (default preserves every existing
caller's behavior exactly, including the exact `voice.translate.assert_called_once_with(..., "en", "kn")`
test assertion) that drives the new fields.

## Known limitations

- **Hindi TTS needs one real, not-yet-done download** — Piper's
  `hi_IN-rohan-medium` voice is not present under `models/voice/piper/`
  on any machine yet (it didn't exist before this module; Kannada/
  Telugu/English needed no new downloads). `text_to_speech(text, "hi")`
  raises `VoiceUnavailableError` until `hf download
  rhasspy/piper-voices hi/hi_IN/rohan/medium/hi_IN-rohan-medium.onnx ...`
  is run (exact command in `docs/TOOLING.md`) — the existing lazy-load
  degrade-not-fail pattern, not a crash, and nothing here fakes that
  step as done.
- The integration tests added for `hi` TTS/STT round trips
  (`tests/voice/test_ai4bharat_integration.py`) are gated behind that
  same voice-file presence check and auto-skip until it's downloaded,
  same "auto-skip, never fail for absence" pattern the rest of that file
  already uses.
- `ta`/`mr`/`bn`/`gu` remain unimplemented in every voice adapter and
  are rejected by `V1_LANGUAGES`-based validation everywhere — a future
  language expansion needs the same verify-before-code pass this module
  did, not an assumption that "it's the same AI4Bharat family."
