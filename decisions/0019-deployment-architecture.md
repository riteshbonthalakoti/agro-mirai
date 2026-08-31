# ADR 0019 — Deployment architecture: Render for API, Oracle VM for heavy inference

**Status:** accepted
**Date:** 2026-09-01
**Module:** 21 — Deployment architecture (CNN wiring, voice stack, Oracle split)

## Context

Module 20 shipped `ImageDiseaseRiskModel` (MobileNetV2 on PlantVillage)
but explicitly left it unwired — no upload path anywhere in the API, and
no plan for where the torch/torchvision runtime would actually run in
production (`decisions/0018-disease-cnn.md`'s "additive, not integrated
yet" section). Separately, Module 12's AI4Bharat voice stack has been
demoed locally from a project-only `.venv/` since Module 15
(`decisions/0014-deploy-target-and-voice-scope.md`) because Render's
free tier (512MB) can't hold ~6.8GB of model weights plus torch. Both
gaps share a root cause: this project's only deployed compute today
(Render) is sized for the lightweight sklearn models and Flask app, not
for CNN/transformer inference.

Two platform options were considered for where the heavy inference
actually runs:

1. **Hugging Face Spaces (free CPU tier).** Ruled out — verified via web
   search that HF eliminated the free CPU Basic Space flavor for new
   compute-based (Docker/Gradio) Spaces in 2026 (multiple corroborating
   sources: HF's own community forum threads, third-party pricing
   write-ups dated 2026). Not a viable free option any more, and this
   project has no budget for a paid tier.
2. **Oracle Cloud Always Free, Ampere A1 shape.** Still free, still the
   best available free CPU/RAM envelope found — but smaller than it used
   to be: verified via web search that Oracle cut the Always Free A1
   allocation from 4 OCPU/24GB to **2 OCPU/12GB**, effective June 15,
   2026, with no public announcement (confirmed across Oracle's own
   Cloud Customer Connect forum and independent reporting/community
   detection of the change). This is the option chosen, with that
   shrinkage explicitly acknowledged rather than assumed away.

## Decision: split deployment

- **Render** keeps running the main `agro_mirai` Flask API + rule-based
  `DiseaseRiskModel` + all `/v1`/`/v2` routes, exactly as today — no
  change to what's already deployed there.
- **A single Oracle Ampere A1 VM** (2 OCPU/12GB, `docs/deploy/oracle-vm-setup.md`)
  runs two new standalone Docker containers, `services/cnn-inference`
  and `services/voice`, each wrapping the existing model code
  (`ImageDiseaseRiskModel`, `AI4BharatVoiceService`) behind a small
  Flask HTTP API. The main API calls them over HTTP via
  `CNN_SERVICE_URL`/`VOICE_SERVICE_URL` with a bounded timeout — see
  `.env.example`/`render.yaml`.
- **Hard fallback requirement for the CNN path**: if the CNN service is
  unreachable, times out, or errors, `POST /fields/{field_id}/disease-risk/image`
  falls back to the existing rule-based `DiseaseRiskModel` and still
  returns a valid 200 `DiseaseRiskAlert` (tagged
  `source="environmental_fallback"`) — never a 500. See
  `src/agro_mirai/models/image_or_environmental_disease.py`.

## Section 3: voice stack — kept AI4Bharat

Considered switching to faster-whisper (ASR) + Kokoro (TTS) as a
lighter-weight alternative to Module 12's AI4Bharat stack
(IndicTrans2/IndicConformer/Piper). Web-searched rather than assumed:

- **Kokoro TTS does not support Kannada.** Its v1.0 release ships 54
  voices across 8 languages — American/British English, Spanish,
  French, Hindi, Italian, Japanese, Brazilian Portuguese. Kannada is
  absent, as of 2026. This project's v1 language scope
  (`specs/core/voice-interface.md`'s `V1_LANGUAGES = {en, kn}`) requires
  Kannada TTS — a hard blocker, not a quality tradeoff.
- **faster-whisper doesn't close this project's actual ASR gap.** It's a
  CTranslate2 reimplementation of OpenAI Whisper, same language
  coverage as the `whisper-tiny.en` Module 12 already uses for English.
  It has no Kannada checkpoint — exactly the capability
  `ai4bharat/indic-conformer-600m-multilingual` provides today. Switching
  would speed up the (already-fine) English path while providing zero
  improvement on the language that actually needed a non-Whisper model
  in the first place.
- **Decision: keep AI4Bharat.** The dependency-isolation pain that made
  a lighter stack tempting is solved a different way instead:
  `services/voice/` containerizes AI4Bharat with its own pinned
  `transformers==4.49.0`, moving the isolation boundary from "a `.venv/`
  on one developer's machine" (Module 15's workaround) to "a separate
  container in production" — a real infrastructure improvement, not a
  repackaging of the same limitation. `src/agro_mirai/voice/remote_voice.py`'s
  `RemoteVoiceService` implements the existing `VoiceService` Protocol
  by calling this container, so any future caller (e.g. wiring
  `Explanation.summary_kn` into the API, still not done as of this ADR)
  can swap in remote voice with zero interface changes.

## Honest limitations

1. **Oracle's free tier has changed before (this module documents the
   change) and could change again** — this deployment architecture is
   built on a resource that Oracle has already silently halved once in
   2026. No contractual guarantee it stays at 2 OCPU/12GB.
2. **No autoscaling.** A single VM running both `cnn-inference` and
   `voice` is the only heavy-inference capacity that exists; a burst of
   concurrent image-classification or voice requests queues or fails,
   it does not scale out.
3. **Single point of failure, scoped correctly.** The Oracle VM going
   down takes out the CNN image-upload path and remote voice — but NOT
   the core API, crop/irrigation recommendations, the rule-based
   disease-risk path, or `/v1`/`/v2` auth/admin routes, all of which run
   independently on Render/Supabase and don't call the Oracle VM at all.
   This was a deliberate split, not an accident: the modules judged most
   essential for a live demo (crop/irrigation/auth) have zero dependency
   on the newest, least-tested piece of infrastructure.
4. **The two Oracle-hosted services have no authentication of their
   own** today — `docs/deploy/oracle-vm-setup.md` recommends scoping the
   security list to Render's egress IPs rather than leaving both ports
   open to `0.0.0.0/0`, but this is a real gap, not fully closed in this
   module. A follow-up should add a shared-secret header check (mirroring
   the main API's `API_KEY` pattern) before this is genuinely production-
   hardened.
5. **ARM64 CPU torch wheel availability for both services is
   unverified** — see `services/cnn-inference/README.md`'s and
   `services/voice/Dockerfile`'s own caveats. This is the single biggest
   technical risk in this ADR and is explicitly not resolved here; it
   needs a real build on the real VM.
6. **`services/voice`'s `requirements.txt` pins were not re-derived from
   a real `.venv/` freeze** in this session (no live `.venv/` was
   available to inspect under this task's no-live-infra constraint) —
   flagged in that file's own header comment as a starting point to
   verify, not a guaranteed-correct pin set.

## Consequences

- `specs/core/schema.yaml`/`enums.md`/`openapi.yaml` gained additive-only
  changes: `DiseaseRiskAlert.source`, the new `disease_alert_source`
  enum, and the new `POST /fields/{field_id}/disease-risk/image` path —
  no existing field/path changed shape.
- `migrations/{sqlite,postgres}/003_disease_alert_source.sql` is the
  upgrade path for databases created before this module.
- `.env.example`/`render.yaml` gained `CNN_SERVICE_URL`,
  `CNN_SERVICE_TIMEOUT_S`, `VOICE_SERVICE_URL`,
  `VOICE_SERVICE_TIMEOUT_S` — all optional; their absence degrades to
  "CNN/remote-voice path unavailable," never a crash, per this project's
  degrade-not-fail doctrine (CLAUDE.md hard rule #4's spirit, extended
  here from GEE to these two new external services).
