# ADR 0013 — Frontend platform sequencing and Module 14 stack choice

**Status:** accepted
**Date:** 2026-08-26
**Module:** 14 — Frontend (Web)

## Context

The product will eventually cover web, mobile, and WhatsApp/messaging.
Building all three at once for a solo-built VTU capstone risks
delivering none of them well before the Nov 14 deadline. Module 14 needs
to (a) lock a build order so this isn't re-litigated later, and (b) pick
a concrete stack for the web app itself.

## Decision 1 — platform build order

**Web first, mobile next, WhatsApp/messaging after.** Rationale:

1. Web is the fastest path to a demoable, gradable artifact — no app
   store review, no device provisioning, runs in any browser.
2. Module 11's Flask API is already contract-complete
   (`specs/core/openapi.yaml`); a web client is the cheapest way to
   prove that contract end-to-end (advisory retrieval, explanation,
   feedback loop).
3. Mobile (React Native/Flutter) and WhatsApp/messaging (Twilio/Meta
   Cloud API) both consume the *same* Module 11 API — nothing about
   this module's scope blocks either. They are explicitly **not**
   scaffolded here; this ADR exists so that decision isn't reopened.

No mobile or messaging-bot code is added in this module.

## Decision 2 — stack: Flask templates, same process as Module 11

The web frontend is **server-rendered Jinja2 templates + minimal
vanilla JS**, added as new blueprints/templates/static files inside the
existing `src/agro_mirai/api/` Flask app — **not** a separate
deployable service, and **not** a React/Vite SPA.

Reasoning:

- **Finishability.** No new build toolchain (npm/Vite/webpack), no new
  deploy target, no CORS configuration. One `flask run` serves both API
  and UI.
- **Solo capstone, not production.** The spec explicitly deprioritizes
  a large untested feature surface in favor of a working demo of the
  full pipeline.
- **Module 15 (deploy) impact.** Because this is the same Flask
  process, Module 15 deploys one service, not two. There is nothing
  new for Module 15 to provision (no static-site host, no separate
  origin, no additional env vars beyond what Module 11 already needs).
  This is the single fact Module 15 needs to know from this ADR.

### Auth: server-side, not client-side

The frontend routes never expose `API_KEY` to the browser. Each
frontend view handler calls the JSON API **in-process** via
`current_app.test_client()`, attaching
`Authorization: Bearer <API_KEY>` itself (same `API_KEY`/`FARMER_ID`
config Module 11 already reads from the environment — see
`.env.example`). This is a real request/response round trip through
the full blueprint/auth/error-handling stack (not a direct model or
`DecisionEngine` import), just without a second network hop — a
deliberate simplification since frontend and API share one process.
See `src/agro_mirai/api/frontend_client.py`.

### Not built: TTS "Listen in Kannada" button

`specs/core/openapi.yaml` has no endpoint that exposes
`Explanation.summary_kn` or a Module 12 `VoiceService.text_to_speech`
call — only `Advisory.body` (English) is served today. Wiring a TTS
button would require either a new API endpoint (an additive contract
change, out of this module's scope to introduce silently) or pulling
Module 12's AI4Bharat stack (heavy `torch`/`transformers` runtime deps)
directly into the frontend, which contradicts "no direct model
imports." This is recorded as a known limitation, not implemented; a
future `GET /fields/{id}/explanations` or similar endpoint is the
correct additive path if this is prioritized later.
