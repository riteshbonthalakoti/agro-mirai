# MODULE 23 — Frontend contract completion: `/v2` value endpoints + a real voice API

Continuing AGRO MIRAI in the existing `agro-mirai` repo. Modules 01–22
are done (`e19beb9` on `origin/main`). Read `CLAUDE.md`, `PROGRESS.md`,
`decisions/0003-*.md`, `decisions/0017-multi-tenant-v2.md`,
`decisions/0019-deployment-architecture.md`,
`src/agro_mirai/api/auth.py`, `src/agro_mirai/api/session_auth.py`,
`src/agro_mirai/api/routes/{advisory,farms_v2,disease_image,feedback}.py`,
and `src/agro_mirai/voice/interface.py` first.

**This is the last backend module before the frontend phase.** Ritesh
has decided the stack: a React Native + Expo mobile app for farmers
(APK distribution), a Next.js landing page, and the existing Jinja2
admin (Module 19) kept as-is. The mobile app is voice-first, offline-
tolerant, and per-farmer authenticated.

Two hard blockers were found by inspecting the actual route registrations
and `specs/core/openapi.yaml` — **both prevent that app from being built
at all**, and both must be closed here. Verify each yourself before
fixing; do not take this description on trust.

---

## Blocker A — `/v2` has authentication but no product

`grep` the blueprints and `openapi.yaml`. Today `/v2` exposes only:
`auth/register`, `auth/login`, `auth/logout`, `farmers/me`, `fields`
(GET/POST), `fields/{id}` (GET), and `admin/*`.

Every endpoint that carries the product's actual value is `/v1`-only,
behind `require_auth`:

- `GET /fields/{field_id}/recommendation`
- `GET /fields/{field_id}/irrigation`
- `GET /fields/{field_id}/disease-risk`
- `POST /fields/{field_id}/disease-risk/image`
- `GET /fields/{field_id}/advisories`
- `POST /feedback` (check `routes/feedback.py` for the exact surface)

And `require_auth` ends with:

```python
g.farmer_id = current_app.config["FARMER_ID"]
```

A single, server-wide, env-var farmer id. So a farmer who registers and
logs in through `/v2` has **no authenticated path to an advisory at
all**; and if the client falls back to the shared `API_KEY`, every
farmer on every device is scoped to the same hardcoded `FARMER_ID` and
sees the same person's data.

This is not a Module 19 defect — Module 19's scope was the data model,
auth, and admin, and keeping `/v1` alive was a deliberate documented
decision (ADR 0017). It's an unnoticed gap *between* modules: the
multi-tenant surface got authentication but never got the endpoints
worth authenticating to. Note also **why the existing test suite didn't
catch it**: `test_full_cross_tenant_isolation_flow` only exercises
`/v2/fields`, which genuinely is isolated. The advisory endpoints were
never in its scope. Fixing that blind spot is part of this module.

## Blocker B — the voice stack has no client-facing API

`grep -rn "voice\|tts\|speech" src/agro_mirai/api/` returns **nothing**.

`src/agro_mirai/voice/` exists (`ai4bharat_voice.py`, `remote_voice.py`,
`interface.py`, `bhashini_voice.py`) and Module 21 containerized the
standalone voice service for the Oracle VM — but the main Flask API
exposes no HTTP route for an external client to request TTS audio or
submit STT. The voice stack is reachable only from inside the backend
process via `RemoteVoiceService`.

The mobile app is **voice-first**, and Ritesh's decided design is
**pre-cached TTS audio with Android's built-in TTS as the offline
fallback**. Pre-caching requires an endpoint to cache *from*. Right now
there isn't one, so the app's primary interaction model is unbuildable.

---

## Confirm `git config user.name`/`user.email` before committing.

Several focused commits — Part A and Part B are independent and should
not be blurred into one history.

---

## Part A — Port the value endpoints to `/v2` under session auth

### A1. Do not copy-paste the handlers
The single most important design decision in this module. `/v1` stays
alive unchanged (ADR 0017), so the same logic will now be reachable
through two auth models. Copy-pasting six handlers guarantees they drift
— a bug fixed in one and not the other is exactly the class of problem
Module 22 already cost you.

Factor the handler bodies into shared, auth-agnostic functions that take
`farmer_id` as an argument (or an equivalent structure — a shared
service layer, or thin route wrappers over common functions). The `/v1`
and `/v2` routes should differ **only** in their auth decorator and URL
prefix, not in their logic. Document the approach you chose.

### A2. The six endpoints
Expose under `/v2`, all decorated with `require_session_auth` (not
`require_auth`), all scoped to the session's `g.farmer_id`:

- `GET /v2/fields/{field_id}/recommendation`
- `GET /v2/fields/{field_id}/irrigation`
- `GET /v2/fields/{field_id}/disease-risk`
- `POST /v2/fields/{field_id}/disease-risk/image`
- `GET /v2/fields/{field_id}/advisories`
- `POST /v2/feedback` (match whatever `/v1` feedback actually exposes)

### A3. Ownership enforcement — match the established pattern
A field not owned by the session's farmer must return **404, not 403**,
consistent with `test_full_cross_tenant_isolation_flow`'s existing
assertion and with ADR 0003's rule (never leak the existence of another
farmer's records). Check `_get_field_or_404` in `advisory.py` — confirm
it actually scopes by `g.farmer_id` through the store and doesn't just
look up by id.

### A4. Preserve Module 22's degrade-not-fail behavior
The `/v2` copies must keep the 422-not-500 handling for data-exhaustion
`ValueError`s from `_water_balance`, and the CNN-service-unreachable →
`source: "environmental_fallback"` behavior on the image endpoint. If
the shared-logic refactor in A1 is done properly this comes for free —
verify it rather than assuming it.

### A5. Field mutation — decide and document
The mobile app will likely need to edit a field (change `current_crop`,
`sown_on`) — today `/v2/fields` has GET and POST but no PUT/PATCH or
DELETE. Decide whether to add them in this module or defer, and write
the decision down. Don't let it be discovered mid-UI-build the way
these two blockers were.

---

## Part B — A real voice API for the mobile client

### B1. TTS endpoint
Design and build an authenticated endpoint the app can use to fetch
spoken audio. Two shapes are reasonable — pick one, justify it in the
ADR:

- **Per-advisory audio**: a stable URL like
  `GET /v2/advisories/{advisory_id}/audio` — highly cacheable, ETag-
  friendly, maps cleanly onto "pre-cache this week's advisory".
- **Generic TTS**: `POST /v2/tts` taking `{text, language}` — flexible,
  reusable for any string, but harder to cache and a broader abuse
  surface.

The per-advisory shape is the better fit for the decided pre-caching
design; if you choose generic TTS, explain why and how caching and abuse
are handled.

Requirements either way:
- Session-authenticated, per-farmer scoped (a farmer must not be able to
  fetch audio for another farmer's advisory).
- Language honours the farmer's `preferred_language` (en/kn), overridable
  per-request.
- A mobile-friendly compressed format (mp3 or ogg — not raw wav), with
  the chosen format and rough size-per-advisory documented.
- Proper HTTP caching headers (`ETag` / `Cache-Control`) so the app can
  cache and revalidate cheaply rather than re-downloading.
- **Graceful degradation, client-distinguishable**: if the Oracle voice
  service is unreachable, return a specific, documented error the client
  can recognise as "voice unavailable, fall back to on-device TTS" —
  never a bare 500, and never a silent empty body. This is the same
  degrade-not-fail contract as the CNN fallback; the client's Android-TTS
  fallback depends on being able to tell this case apart from a real
  failure.
- Its own rate limit. TTS is far more expensive per call than a JSON
  read, and Module 16's general limiter is not tuned for it.

### B2. STT endpoint
`POST /v2/stt` (or similar): accepts an uploaded audio clip, returns
transcribed text. Same session auth, same graceful-degradation contract,
same dedicated rate limit, and the same real upload validation the image
endpoint got in Module 21 (size cap, real content sniffing, not
extension trust). Document accepted audio formats and the max clip
length.

### B3. Do not put the models in the main API process
The main Flask API runs on Render's 512MB free tier. These routes must
call the Oracle-hosted voice service over HTTP via the existing
`RemoteVoiceService` / `VoiceService` Protocol — the same client pattern
as `cnn_client.py`. Do not import AI4Bharat or torch into the main API
process; that would break the deployment architecture ADR 0019 set out.

---

## Tests

The gap in existing coverage is as important as the code:

- **Cross-tenant isolation for every new `/v2` endpoint**, not just
  fields — farmer A must get 404 on farmer B's field for
  `recommendation`, `irrigation`, `disease-risk`, `disease-risk/image`,
  and `advisories`. This is the specific blind spot that let Blocker A
  ship unnoticed; close it deliberately.
- Session-required tests: each new endpoint returns 401 with no session.
- `/v1` regression: confirm every `/v1` endpoint still behaves exactly as
  before (ADR 0017's promise). The shared-logic refactor must not change
  `/v1` semantics at all.
- Module 22 behaviors preserved on the `/v2` copies: 422 on exhausted
  weather history, `environmental_fallback` when the CNN service is down.
- Voice: TTS/STT success paths, voice-service-unreachable returning the
  documented distinguishable error (mocked at the HTTP boundary — no
  live Oracle VM in CI), upload validation on STT, rate-limit tests.
- Full regression, `check_specs.py`, CI green — with no live infra
  dependency anywhere.

## Live verification — required, not optional

Module 22's bug was invisible to pytest and obvious in one curl. Repeat
that discipline here:

1. `python tools/seed_fixture.py --backend sqlite --db-path /tmp/m23.db`
2. Run the real Flask server against it.
3. With **real curl**: register two farmers → log in as farmer A →
   fetch A's advisory (expect 200 with real content) → attempt farmer
   B's field with A's session (expect 404) → fetch advisory audio
   (expect 200 audio, or the documented degradation error if no voice
   service is running locally) → log out → confirm the session is dead.
4. Paste the actual output into the handoff. Not a pytest summary.

## Update doctrine

`specs/core/openapi.yaml` (additively — this is the contract the mobile
app and Antigravity will be built against, so it must be complete and
accurate; treat it as a **frontend contract freeze**), `specs/core/
schema.yaml`/`enums.md` if new shapes are needed, `CLAUDE.md`,
`PROGRESS.md`, `docs/ROADMAP_PRODUCTION.md`, a new ADR
(`decisions/0020-v2-value-endpoints-and-voice-api.md` or next free
number) documenting the shared-logic approach, the TTS endpoint shape
decision, and the field-mutation decision from A5. `.env.example` /
`render.yaml` for any new config (voice service URL/timeout).

## Definition of done
- [ ] Both blockers independently confirmed before being fixed
- [ ] Six value endpoints live under `/v2` with real per-farmer session
      scoping; `/v1` unchanged and still passing its own tests
- [ ] Handler logic shared between `/v1` and `/v2`, not duplicated
- [ ] Cross-tenant isolation tested on **every** new endpoint (404, not
      403, not a leak)
- [ ] Module 22's 422 and CNN-fallback behaviors verified intact on `/v2`
- [ ] TTS endpoint built, cacheable, rate-limited, with a
      client-distinguishable degradation error
- [ ] STT endpoint built with real upload validation
- [ ] No AI4Bharat/torch imported into the main API process
- [ ] Field mutation (A5) decided and documented either way
- [ ] `openapi.yaml` complete and accurate — the frontend contract
- [ ] Live curl verification run and pasted into the handoff
- [ ] Full regression + `check_specs.py` green, no live-infra dependency
- [ ] Pushed to `origin/main`

## Commit attribution
End every commit message with:

```
Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_019tyUuaMLre8xkkjFxu7Uzw
```

## Handoff format
```
Module: 23 — /v2 value endpoints + voice API (frontend contract completion)
Status: complete | blocked

--- Blockers ---
Blocker A confirmed: <what you found, independently>
Blocker B confirmed: <what you found, independently>

--- Part A ---
Shared-logic approach: <how /v1 and /v2 share handler bodies>
Endpoints added: <list>
Ownership enforcement: <how, and confirmation it's 404 not 403>
Module 22 behaviors on /v2: <422 + environmental_fallback, verified how>
/v1 regression: <confirmed unchanged, how>
Field mutation (A5): <added | deferred, why>

--- Part B ---
TTS endpoint shape: <per-advisory | generic, why>
Audio format + size: <format, rough bytes per advisory>
Caching: <ETag/Cache-Control approach>
Degradation error: <exact status + body the client keys off>
STT endpoint: <route, formats, validation, limits>
Rate limits: <what was set for TTS/STT and why>

--- Both ---
Files changed:
Commits made:
Tests: <new/updated counts, pass/fail; confirm per-endpoint cross-tenant coverage>
Live curl verification: <paste the actual session output>
Full regression: <pass/fail>
check_specs.py: pass/fail
openapi.yaml: <confirmed complete as the frontend contract>
Known limitations:
Next: frontend phase — PRD, then Antigravity (React Native + Expo)
```
