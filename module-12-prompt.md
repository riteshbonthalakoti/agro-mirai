# MODULE 12 — Voice & Language

Continuing AGRO MIRAI in the existing `agro-mirai` repo. Modules 01, 02,
and 04 are the only hard prerequisites for this module (it does not depend
on 03/05/06 — it may be running concurrently with Module 06 in a second
session). Read `CLAUDE.md` and `PROGRESS.md` first for current state.

NOTE: A second Claude Code session may be running Module 06 concurrently
in this folder — unrelated part of the tree (`src/agro_mirai/models/`).
`git pull` before you start and before you push; re-run the full suite
after pulling.

Confirm `git config user.name`/`user.email` are correct. Same commit
discipline as prior modules: one commit per real checkpoint (interface
defined → translation adapter working → ASR working → TTS working →
tests → docs — expect roughly 6-8 real commits, not one, not fifty).

## Scope

Build the `VoiceService` interface locked decision #3 (er, the voice
equivalent — see `CLAUDE.md`) requires: translation, speech-to-text, and
text-to-speech, with the AI4Bharat offline stack as the live
implementation now, and a stub adapter ready for Bhashini to drop in
behind the same interface once that access request clears (per our
earlier decision — don't block on Bhashini).

## Tasks

### 1. `specs/core/voice-interface.md`
Written spec, same pattern as Module 02's `repository-interface.md`:
- `translate(text, source_lang, target_lang) -> str`
- `speech_to_text(audio_bytes, expected_lang=None) -> (text, detected_lang)`
- `text_to_speech(text, lang) -> audio_bytes`
- Supported language set for v1 — start with `en` + `kn` (Kannada; matches
  the golden fixture farmer's `preferred_language: kn` and the project's
  Bellary/Karnataka setting) rather than trying to cover every language in
  `enums.md`'s `language_code` list at once. Document this as a deliberate
  v1 scope decision, with the rest of the enum's languages as a documented
  "not yet implemented" list, not silently unsupported.

### 2. AI4Bharat adapter (`ai4bharat_voice.py` or similar)
- Translation via IndicTrans2 (`hf` CLI already authenticated — pull the
  model weights, note the download size and first-run time in
  `docs/TOOLING.md` since it's non-trivial).
- ASR via IndicWav2Vec.
- TTS via Piper (lightweight, fits the project's low-spec hardware target
  better than a heavier alternative — note this reasoning in
  `docs/architecture.md`).
- Wrap all three behind the interface from step 1. If any model is too
  large/slow to be practical on the target hardware (i3/4GB RAM per the
  PPT), say so explicitly in your handoff rather than silently shipping
  something impractical — this is exactly the kind of real constraint
  worth surfacing, not hiding.

### 3. Bhashini adapter — stub, not blocked on
A `BhashiniVoiceAdapter` implementing the same interface, calling out to
Bhashini's API where credentials/access exist, and raising a clear typed
"not yet available" error otherwise. Don't spend time on this if access
hasn't come through yet — the point is the interface seam exists and
swapping it in later is a config change, not a rewrite.

### 4. Tests — three explicit stages
- **Unit**: interface conformance for both adapters, error handling for
  an unsupported language code.
- **Integration**: a real round trip — translate a short advisory-shaped
  sentence EN→KN and back, and a real ASR/TTS smoke test using a short
  fixture audio sample you generate and check in (small file, keep it
  brief). This proves the actual models work end to end, not just that
  the interface compiles.
- **Acceptance checklist** (manual, its own section in the handoff):
  - [ ] Translated text for a sample advisory reads as sensible Kannada
        (a genuine read, even if you're relying on back-translation or a
        native check later — flag if you can't fully verify this yourself)
  - [ ] TTS output is audible/valid audio (not silence or garbage) —
        actually listen to or inspect the waveform, don't just check the
        function returned bytes
  - [ ] Total model download size and first-run latency are noted and
        reasonable for a capstone demo environment

### 5. Update doctrine
`modules/12-voice/STATUS`, `CLAUDE.md` phase note (careful: don't
overwrite what Module 06 wrote if it finished first — merge, don't clobber,
check `PROGRESS.md`'s phase table for both entries before editing),
`python tools/update_state.py`, `python tools/check_specs.py`, commit.

## Definition of done
- [ ] `VoiceService` interface exists; AI4Bharat adapter fully implements
      it; Bhashini adapter stub exists behind the same interface
- [ ] Unit + integration tests pass (including a real, checked-in audio
      round trip); acceptance checklist completed in the handoff
- [ ] Hardware/latency constraints noted honestly, not glossed over
- [ ] Pulled/merged cleanly against any Module 06 changes before pushing
- [ ] Doctrine updated without clobbering Module 06's phase-table entry
- [ ] Pushed to `origin/main`

## Handoff format
```
Module: 12 — Voice & Language
Status: complete | blocked
Implemented:
Files changed:
Commits made:
Unit tests: <+pass/fail>
Integration tests: <+pass/fail>
Acceptance checklist: <each item, checked or not, with a one-line note>
Known limitations:
Remaining risks:
Next recommended module: (13 is gated on 11 — likely 07 or 08 if 06 isn't done yet, otherwise wait)
```
