# ADR 0020 — `/v2` value endpoints + a client-facing voice API

**Status:** accepted
**Date:** 2026-09-04
**Module:** 23 — `/v2` value endpoints + voice API (frontend contract completion)
**Related:** supplements ADR 0017 (multi-tenant `/v2`), ADR 0019
(deployment architecture — the Oracle-hosted `services/cnn-inference` and
`services/voice` containers this module's routes call into), ADR 0021's
disease-image precedent for the fallback contract shape.

## Context

This is the last backend module before the frontend phase (React Native +
Expo mobile app, Next.js landing page). Inspecting the actual route
registrations and `specs/core/openapi.yaml` — not taking the module
brief's description on trust — turned up two independently confirmed
blockers that would have made the mobile app unbuildable:

**Blocker A.** `/v2` (Module 19's session-authenticated multi-tenant
surface) has real per-farmer auth but no product: `grep`ping
`src/agro_mirai/api/routes/` showed `/v2` exposed only
`auth/register`, `auth/login`, `auth/logout`, `farmers/me`, and
`fields`/`fields/{id}` (GET/POST). Every endpoint carrying the actual
value — recommendation, irrigation, disease-risk (+ image), advisories,
feedback — existed only under `/v1`, behind `require_auth`, which maps
every request to one server-wide `FARMER_ID` env var. A farmer who
registers and logs in via `/v2` had no authenticated path to their own
advisory at all. This was not a Module 19 defect — that module's scope
was the data model, auth, and Admin, and `/v1` staying alive was
deliberate (ADR 0017) — it is an unnoticed gap *between* modules.
`tests/api/test_v2_auth_integration.py::test_full_cross_tenant_isolation_flow`
passed honestly the whole time; it only ever exercised `/v2/fields`,
which genuinely is isolated, so the gap in the endpoints that matter was
invisible to the existing suite.

**Blocker B.** `grep -rn "voice\|tts\|speech" src/agro_mirai/api/`
returned nothing. `src/agro_mirai/voice/` (Module 12) and
`services/voice` (Module 21's container) both exist and work, but no
route anywhere in the main Flask API exposes them to an external client.
The decided mobile design — pre-cached TTS audio with Android's built-in
TTS as the offline fallback — needs an endpoint to cache *from*; there
wasn't one.

## Decision

### 1. Shared handler bodies, not six duplicated routes

`/v1` stays alive per ADR 0017, so the six value endpoints are now
reachable through two auth models. Copy-pasting the `/v1` handlers into
new `/v2` ones would guarantee the two drift — a fix landing in one and
not the other is exactly the failure class Module 22 already cost this
project (a `ValueError` handled at the `/v1` route boundary that would
have silently been unhandled on a naive `/v2` copy).

`src/agro_mirai/api/value_endpoints.py` holds the actual logic —
`compute_recommendation`, `compute_irrigation`, `compute_disease_risk`,
`compute_disease_risk_image`, `compute_advisories`, `submit_feedback` —
each taking an explicit `farmer_id` argument instead of reading
`g.farmer_id` itself. `routes/advisory.py`/`feedback.py`/
`disease_image.py` (`/v1`, `@require_auth`) and the new
`routes/value_v2.py` (`/v2`, `@require_session_auth`) are both thin
wrappers around the same functions, differing only in the auth decorator
and URL prefix. Module 22's degrade-not-fail contracts (422 on
data-exhaustion `ValueError`s, `environmental_fallback` when the CNN
service is unreachable) live inside `value_endpoints.py` itself, so both
surfaces get them automatically — verified directly in
`tests/api/test_v2_value_endpoints.py`, not assumed from the refactor.

An alternative considered: a class-based service layer injected via
`current_app.extensions`. Rejected as unnecessary indirection — plain
functions taking `store`/`ext`/`farmer_id` are enough here, and match
this codebase's existing style (`api/features.py`,
`image_or_environmental_disease.py`) better than introducing a new
pattern for one module.

### 2. Ownership: reuse the store's existing farmer-scoping, not a new check

`DataStore.get_field(farmer_id, field_id)` and
`DataStore.get_advisory(farmer_id, advisory_id)` were already
farmer-scoped (Module 19's `repository-interface.md` design rule). Every
new `/v2` route — value endpoints, `PATCH /v2/fields/{id}`, the two voice
routes — reuses exactly that scoping, so a record that exists but belongs
to a different farmer returns 404, never 403, never a leak, with no new
ownership-check code written for this module. Verified per-endpoint in
`tests/api/test_v2_value_endpoints.py` (the specific blind spot Blocker A
exposed — `test_full_cross_tenant_isolation_flow` only ever covered
`/v2/fields`) and in `test_voice_routes.py::test_audio_cross_tenant_404`.

### 3. Field mutation (A5): add `PATCH`, scoped to `/v2` only

The mobile app will need to edit a field it already created (re-sowing a
different crop, correcting `sown_on`) and `/v2/fields` had no
PUT/PATCH/DELETE. Decided to add `PATCH /v2/fields/{field_id}` in this
module rather than defer it — deferring would have surfaced it as a
third mid-UI-build blocker, the exact failure mode this module exists to
close for A and B. Chose `PATCH` (partial update — only the keys present
in the body change) over `PUT` (full replace) since the mobile client's
natural interaction is "change one field," not "resubmit the whole
record." `/v1` deliberately does **not** get this route: it stays frozen
per ADR 0017, and no `/v1` caller (the Module 14 demo frontend, `/v1`
integration tests) has ever needed field mutation.

### 4. TTS endpoint shape: per-advisory, not generic

Two shapes were considered:

- **Per-advisory**: `GET /v2/advisories/{advisory_id}/audio` — the audio
  for one specific, already-generated `Advisory`.
- **Generic**: `POST /v2/tts {text, language}` — synthesize any string.

Chose **per-advisory**. It maps directly onto the decided pre-caching
design ("cache this week's advisories' audio on the device") with a
stable, cacheable URL and a real `ETag` (advisory id + `created_at` +
language) — the client can revalidate with `If-None-Match` for free, and
a 304 costs nothing beyond a cache lookup. Generic TTS would need its own
abuse-surface reasoning (arbitrary text, arbitrary cost) and gives up
free caching (every distinct string is a cache miss), for a capability
this project has no other use for yet — nothing besides
advisory playback needs to speak arbitrary text today. If a future
module needs to speak something that isn't an `Advisory` (e.g. a UI
label), a generic endpoint is additive and can be added then.

Language: defaults to the farmer's `preferred_language`, overridable via
`?language=`. `Advisory.body` is always generated in one fixed language
(`ExplanationService`'s `summary_en` concatenation per ADR 0011), so
speaking it in a different language needs a translate hop (via the same
`RemoteVoiceService.translate`) before TTS — `voice_client.py`'s
`synthesize_advisory_audio` does this only when the requested language
differs from `Advisory.language`, so the common case (English farmer,
English advisory) never pays for an unnecessary translate call.

### 5. Audio format: OGG/Vorbis, transcoded in `services/voice`, not the main API

`services/voice`'s Piper backend produces raw WAV (confirmed by reading
`services/voice/app.py` before this module: `mimetype="audio/wav"`).
"Mobile-friendly compressed format, not WAV" ruled that out as-is. Two
places to transcode: the main API process, or `services/voice` itself.
Chose `services/voice` — it already carries the heavy audio dependency
weight (Module 21's isolation boundary exists specifically so the
Render-hosted main API stays free of that), so adding a system `ffmpeg`
binary there (via `apt-get`, `services/voice/Dockerfile`) costs nothing
architecturally, versus pulling an audio-transcoding Python dependency
into the 512MB Render process. Chose **OGG/Vorbis over MP3**: ffmpeg's
built-in `libvorbis` encoder needs no extra codec install, unlike
`libmp3lame`, which some ffmpeg builds omit for licensing reasons — OGG
avoids that variability without giving up meaningful compression or
mobile-client support (both Android's `MediaPlayer` and Expo's `expo-av`
play OGG natively).

**Known gap, not hidden:** this transcoding step is unverified end-to-end
in this session. The dev machine used for this module (Windows, no
system `ffmpeg` on `PATH`) cannot run it locally —
`services/voice/tests/test_routes.py::test_text_to_speech_success`
fails there with the documented, intentional 422 `VOICE_ERROR` a missing
`ffmpeg` produces (`shutil.which("ffmpeg") is None` -> `RuntimeError`,
caught by the route's existing exception handler). It is expected to
pass in CI: `.github/workflows/ci.yml`'s `ubuntu-latest` runner ships
`ffmpeg` preinstalled, and that workflow already runs
`pytest services/voice/tests -q` as its own step — this module changed
neither the CI job nor the runner. This is the same class of honest,
documented-not-hidden gap Module 21 flagged for its own Dockerfiles'
ARM64 wheel availability: real code, a real system dependency, not
verified against real infrastructure in this session.

### 6. Degradation contract: 503 `VOICE_UNAVAILABLE`, distinguishable from every other error

The CNN image path (Module 21) falls back *inside the server* — an
unreachable CNN service still returns a 200 `DiseaseRiskAlert`, just
tagged `environmental_fallback`, because a substitute (the rule-based
model) exists. There is no server-side substitute for spoken audio, so
the fallback has to happen on the client (Android's on-device TTS/STT),
which means the server's job is different: return a response the client
can reliably tell apart from "this request itself was bad" or "genuine
server bug." Both `GET /v2/advisories/{id}/audio` and `POST /v2/stt`
return `503` with `{"error": {"code": "VOICE_UNAVAILABLE", ...}}` for
every voice-service failure mode (`VOICE_SERVICE_URL` unset, unreachable,
timeout, malformed response) — never a bare 500, never an empty body.
`voice_client.py` mirrors `cnn_client.py`'s never-raise contract (returns
`None` on any failure) so this can't be an unhandled exception at the
route layer, the same shape that made Module 21's CNN fallback provably
never-500 rather than merely "shouldn't 500."

### 7. Rate limiting: dedicated limiter, same mechanical reason as login's

TTS/STT calls are more expensive per request than a JSON read — a live
model call on the Oracle VM, not a local prediction. `voice_rate_limit.py`
creates its own module-level `Limiter`, decorated onto the view functions
at *import time* in `routes/voice_v2.py`, then `init_app(app)`'d once in
`create_app` — the identical pattern `login_rate_limit.py` established in
Module 19, for the identical reason documented there: this version of
Flask-Limiter silently no-ops `.limit(...)` applied to a view function
*after* it's registered on a Flask app, so the decorator cannot live
inside `create_app` itself. Keyed by remote address (not `farmer_id`):
`g.farmer_id` isn't set until `require_session_auth` runs inside the view
function chain, after Flask-Limiter's key function has already been
called.

### 8. STT upload validation: magic-byte check, not a full decode

`image_validation.py` (Module 21) does a full Pillow decode-and-verify —
a genuine "is this actually a valid image" check. No equivalent
lightweight, already-in-this-stack audio-decoding library exists;
adding one (`pydub`, `ffmpeg-python`) to the main API process would
undercut the exact Render-512MB/no-heavy-deps reasoning that put
`services/voice` in its own container in the first place. `stt_validation.py`
checks magic bytes for WAV/OGG/MP3 instead — catches "this isn't audio at
all," not "this WAV is truncated mid-stream." Documented as a real,
smaller gap than the image path's, not a silent one.

## Consequences

- `specs/core/openapi.yaml` now documents 9 new paths
  (`/v2/fields/{id}/{recommendation,irrigation,disease-risk,
  disease-risk/image,advisories}`, `/v2/feedback`,
  `PATCH /v2/fields/{id}`, `/v2/advisories/{id}/audio`, `/v2/stt`) —
  this is the frontend contract the mobile app and Antigravity get built
  against, so it is treated as a freeze from this commit forward the same
  way ADR 0017 froze `/v1`.
- The two Oracle-hosted services (`services/cnn-inference`,
  `services/voice`) still have no authentication of their own — the same
  open gap ADR 0019 flagged, unchanged by this module. They are reachable
  only from the main API by URL today; adding service-to-service auth is
  real follow-on scope, not silently assumed safe.
- `/v1` is unmodified in behavior; every `/v1` route in
  `tests/api/test_routes_unit.py`/`test_integration.py` passes unchanged
  against the refactored shared logic (see the module handoff for the
  exact regression numbers).
- Next: frontend phase — PRD, then Antigravity (React Native + Expo).
