# Voice inference service

Standalone Flask service wrapping Module 12's `AI4BharatVoiceService`
behind HTTP, meant to run as its own Docker container on the Oracle VM
(`docs/deploy/oracle-vm-setup.md`) alongside `services/cnn-inference`.

## Decision: kept AI4Bharat, did not switch to faster-whisper + Kokoro

See `decisions/0019-deployment-architecture.md` §3 for the full writeup.
Short version, grounded in a web search rather than asserted:

- **Kokoro TTS does not support Kannada.** Kokoro v1.0 ships 54 voices
  across 8 languages (English x2, Spanish, French, Hindi, Italian,
  Japanese, Brazilian Portuguese) — Kannada is not among them, as of
  2026. This project's v1 language scope
  (`specs/core/voice-interface.md`'s `V1_LANGUAGES = {en, kn}`) requires
  Kannada TTS, so Kokoro is a hard non-starter for the TTS half of the
  stack regardless of its CPU-friendliness.
- **faster-whisper doesn't add anything for this project's ASR gap.**
  It's a CTranslate2 reimplementation of OpenAI Whisper — same
  language/checkpoint coverage as `whisper-tiny.en`, which Module 12
  already uses for English ASR. It does not have a Kannada checkpoint,
  which is exactly the gap `ai4bharat/indic-conformer-600m-multilingual`
  fills today. Swapping to faster-whisper would speed up the English
  path (not currently a bottleneck) while providing no Kannada ASR
  improvement.
- **The real problem faster-whisper/Kokoro would have solved —
  dependency-isolation pain — is solved by containerizing AI4Bharat
  instead**, which this service does. Module 12's `.venv/` workaround
  (transformers pinned to 4.49.0, incompatible with the main app's
  dependency set) existed because there was no clean process boundary on
  a single dev machine. A separate Docker container on the Oracle VM
  *is* that boundary in production — a genuine improvement over the
  local workaround, not just a repackaging of it.

## Endpoints (adapt 1:1 to the `VoiceService` Protocol)

- `GET /health` — same shape as the main API's health route and
  `services/cnn-inference`'s.
- `POST /translate` — `{"text", "source_lang", "target_lang"}` ->
  `{"text"}`.
- `POST /speech-to-text` — multipart `audio` file + optional
  `expected_lang` form field -> `{"text", "detected_lang"}`.
- `POST /text-to-speech` — `{"text", "lang"}` -> raw `audio/wav` bytes.

`src/agro_mirai/voice/remote_voice.py`'s `RemoteVoiceService` is the
`VoiceService`-Protocol-conforming HTTP client for this container —
callers elsewhere in the codebase (e.g. `ExplanationService`) can accept
a `RemoteVoiceService` anywhere they currently accept
`AI4BharatVoiceService`/`BhashiniVoiceAdapter`, with zero code changes
beyond which adapter gets constructed.

## Model weights

AI4Bharat's ~6.8GB of weights (IndicTrans2, IndicConformer,
Piper/vits_rasa_13 — see Module 12's `docs/TOOLING.md`) are downloaded
from Hugging Face on first run, not baked into the image. The
`Dockerfile` sets `HF_HOME=/hf-cache` and declares it a volume — mount a
persistent host directory there (see `docker-compose.yml` at the repo
root) so the download only happens once per VM, not on every container
restart.

## Local testing without torch/AI4Bharat installed

`tests/test_routes.py` injects a stub `VoiceService` via
`create_app(service_factory=...)`, covering the route logic (400/503
branches, request/response shapes) without needing the real stack
installed — same pattern as `services/cnn-inference/tests`. Run:
`pytest services/voice/tests`. `src/agro_mirai/voice/remote_voice.py`'s
own tests (`tests/voice_remote/test_remote_voice.py`) mock
`requests.post` directly and run in the main pytest suite (no `--ignore`
needed — this adapter has no torch dependency of its own).
