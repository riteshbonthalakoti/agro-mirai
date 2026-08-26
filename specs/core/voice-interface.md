# Voice Interface

`VoiceService` is the abstraction every module goes through for
translation, speech-to-text, and text-to-speech. Module 12 implements it
against the AI4Bharat offline stack as the live v1 backend, with a
`BhashiniVoiceAdapter` stub behind the same interface ready to swap in once
Bhashini API access clears (CLAUDE.md hard rule #1: CLI/API-first, no
undocumented dashboard state — same spirit applied here: no module talks
to a specific voice vendor directly).

This document is the contract, same pattern as
`specs/core/repository-interface.md`. Method signatures below are
Python-flavoured pseudocode; Module 12 lands the real `Protocol` in
`src/agro_mirai/voice/interface.py`.

## Design rules

1. **Callers depend on plain Python types** (`str`, `bytes`, `tuple`), not
   an adapter-specific SDK object. Nothing model- or vendor-specific leaks
   out of the interface.
2. **Language codes are `language_code` enum values** from
   `specs/core/enums.md` (ISO 639-1). An adapter that doesn't support a
   requested code raises `UnsupportedLanguageError`, never a silent
   fallback or a garbled translation.
3. **Adapters are stateless per call.** No adapter method depends on a
   previous call's result; a fresh `VoiceService` instance is safe to
   construct per request or share across requests.
4. **Unavailable capability is a typed error, not an exception from deep
   inside a vendor SDK.** `VoiceUnavailableError` covers "model not
   downloaded", "API credentials missing", "backend unreachable" — the
   caller can catch one exception type regardless of which adapter is
   wired in.

## Errors

```python
class VoiceServiceError(Exception):
    """Base class for all VoiceService errors."""

class UnsupportedLanguageError(VoiceServiceError):
    """Raised when a requested language_code is not in the adapter's
    supported set. Carries `.language_code` and `.supported` (the
    adapter's supported set) for caller-side messaging."""

class VoiceUnavailableError(VoiceServiceError):
    """Raised when the underlying model/API is not usable right now
    (not downloaded, credentials missing, backend unreachable). Carries
    `.reason`, a short machine-readable string."""
```

## Method signatures

```python
class VoiceService(Protocol):
    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate `text` from source_lang to target_lang. Both must be
        in the adapter's supported set, checked independently (an adapter
        may support a language as a source but not as a target, or vice
        versa — see 'Supported language set' below for the v1 restriction
        to two languages, which sidesteps this asymmetry for now).
        Raises UnsupportedLanguageError, VoiceUnavailableError."""

    def speech_to_text(
        self, audio_bytes: bytes, expected_lang: str | None = None
    ) -> tuple[str, str]:
        """Transcribe `audio_bytes` (mono 16kHz PCM WAV). Returns
        (transcript, detected_lang). If expected_lang is given, the
        adapter decodes against that language directly (faster, no
        language ID step) and detected_lang echoes it back unchanged. If
        expected_lang is None, the adapter must attempt language
        identification within its supported set. Raises
        UnsupportedLanguageError (for a given expected_lang not
        supported), VoiceUnavailableError."""

    def text_to_speech(self, text: str, lang: str) -> bytes:
        """Synthesize `text` in `lang`. Returns mono 16kHz (or the
        adapter's native rate — see per-adapter docs) PCM WAV bytes.
        Raises UnsupportedLanguageError, VoiceUnavailableError."""
```

## Supported language set for v1

CLAUDE.md hard rule #2 (additive-only contracts) applies here too: the v1
scope below is a deliberate subset of `enums.md`'s full `language_code`
list, not a redefinition of it. Adding a language later means an adapter
starts supporting a code already in the enum — additive, no version bump
needed on the enum itself.

**v1 implemented (both adapters must support these two, all three
methods):**

- `en` — English
- `kn` — Kannada — matches the golden fixture farmer's
  `preferred_language: kn` (`specs/domains/fixtures/farm-001.json`,
  `farm-002.json`) and the project's Bellary/Karnataka setting.

**Not yet implemented (present in `enums.md`, no adapter supports them
in v1 — calling any `VoiceService` method with one of these raises
`UnsupportedLanguageError`, not a silent failure):**

- `hi` — Hindi
- `ta` — Tamil
- `te` — Telugu
- `mr` — Marathi
- `bn` — Bengali
- `gu` — Gujarati

Rationale for starting at two: every AI4Bharat model in the v1 stack
(IndicTrans2, IndicConformer, VITS/Piper — see
`docs/architecture.md` for the per-capability model choice) supports all
eight `enums.md` languages to varying degrees, so widening past `en`+`kn`
is a config/testing change, not a rewrite, once there's fixture and
review bandwidth to verify quality in the other six.

## Per-capability implementation notes (informative, not part of the contract)

- **Translation:** IndicTrans2 is trained many-to-many across the full
  Indic set; `en`<->`kn` is one language pair among many it already
  handles, so no substitution was needed here.
- **Speech-to-text:** the module prompt named IndicWav2Vec as the ASR
  backend. AI4Bharat's `indicwav2vec_v1_*` model family does **not**
  include a Kannada checkpoint (it covers Gujarati, Hindi, Marathi,
  Nepali, Odia, Sinhala, Tamil, Telugu, Bengali — no `kn`). The AI4Bharat
  adapter uses `ai4bharat/indic-conformer-600m-multilingual` instead,
  which is AI4Bharat's current (2025) multilingual ASR model and does
  cover Kannada. See `docs/architecture.md` for the full reasoning and
  the hardware-fit caveat.
- **Text-to-speech:** the module prompt named Piper as the TTS backend
  for its low-spec-hardware fit. Piper's published voice set
  (`rhasspy/piper-voices`) has no Kannada voice at all. The AI4Bharat
  adapter uses Piper for `en` (as specced) and
  `ai4bharat/vits_rasa_13` (a VITS model, not the heavier
  diffusion-based `IndicF5`) for `kn`. See `docs/architecture.md`.

## Testing contract

Module 12 must ship:

- Unit tests: interface conformance for both adapters (every method
  exists with the right signature) and `UnsupportedLanguageError` for a
  language outside the adapter's supported set (e.g. `hi`).
- Integration tests: a real `en`->`kn`->`en` round trip through
  `translate`, and a real `speech_to_text`/`text_to_speech` round trip
  against a short checked-in fixture audio clip
  (`tests/voice/fixtures/`).
