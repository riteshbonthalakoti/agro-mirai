# AGRO MIRAI — Antigravity Kickstart Prompt

Paste everything below into Antigravity after opening the `AGRO MIRAI` folder.

---

## Who I am and what this project is

I'm building AGRO MIRAI, an AI-driven smart agriculture advisory system, as a VTU Semester 7 AIML capstone (22AIP76, 2022 scheme) at Ballari Institute of Technology & Management. The backend is done and independently verified — real trained models, a real multi-tenant API, real ET0 irrigation math, a real disease-detection CNN. Your job is the frontend: three separate products sharing that one backend. Read this whole prompt before writing any code — it tells you what exists, what's frozen, what's decided, and what's genuinely still open.

## The backend contract — read this first, treat it as law

`specs/core/openapi.yaml` is the **frozen frontend contract** as of commit `66b003d` on `origin/main`. Frozen means additive-only from here: don't propose backend changes to make the frontend easier to build — build against what's there, and if something is genuinely missing, tell me before working around it, don't invent an endpoint.

Read these files before writing any frontend code:
- `specs/core/openapi.yaml` — every route, request/response shape, error code
- `specs/core/schema.yaml` and `specs/core/enums.md` — the data model
- `decisions/0017-multi-tenant-v2.md`, `decisions/0020-v2-value-endpoints-and-voice-api.md` — why `/v2` is shaped the way it is
- `CLAUDE.md` and `PROGRESS.md` — full project history and doctrine

**Auth:** `/v2` uses real per-farmer session auth (bcrypt-hashed passwords, signed Flask session cookies) — `POST /v2/auth/register`, `POST /v2/auth/login`, `POST /v2/auth/logout`. Registration does **not** auto-log-in — call login explicitly after register, don't assume a session cookie exists after registering. Session cookies are `HttpOnly`, `SameSite=None` by default (configurable via `SESSION_COOKIE_SAMESITE`), `Secure` in production.

**The six value endpoints** (all session-scoped under `/v2`, all farmer-owned, all confirmed to return 404 — never 403 — on cross-tenant access, so a wrong ID never leaks whether it exists):
- `GET /v2/fields/{id}/recommendation`
- `GET /v2/fields/{id}/irrigation`
- `GET /v2/fields/{id}/disease-risk`
- `POST /v2/fields/{id}/disease-risk/image` — send image bytes, get CNN-based detection; falls back to `source: "environmental_fallback"` if the CNN service (Oracle VM) is unreachable — this is a **designed degraded state**, render it as "using field conditions instead of photo analysis," not as an error banner
- `GET /v2/fields/{id}/advisories`
- `POST /v2/feedback` — body needs `advisory_id`, `rating`, `helpful` (boolean), optional `comment`

**Field CRUD:** `GET/POST /v2/fields`, `GET /v2/fields/{id}`, `PATCH /v2/fields/{id}` (partial update — field is `current_crop`, not `crop`), `DELETE /v2/fields/{id}` (204 on success, 404 on not-found-or-not-yours).

**Farmer profile:** `GET /v2/farmers/me`, `PATCH /v2/farmers/me` — partial update of `name` and `preferred_language` (validated against `{en, kn}` — nothing else is accepted, 400 on anything else).

**Voice — the two endpoints your offline/voice-first design depends on:**
- `GET /v2/advisories/{advisory_id}/audio` — per-advisory (not generic text-to-speech), OGG/Vorbis, ETag + `Cache-Control: private, max-age=86400` so it's genuinely cacheable client-side. Defaults to the farmer's `preferred_language`, overridable with `?language=`.
- `POST /v2/stt` — multipart audio upload (WAV/OGG/MP3, magic-byte validated, 10MB cap).
- **Both return `503 {"error":{"code":"VOICE_UNAVAILABLE",...}}` when the voice service (a separate Oracle VM container) is unreachable.** I confirmed this live myself — it's a real, working degradation contract, not aspirational. Your client must catch this specific code and fall back to Android's on-device TTS for spoken output. There is no client-side fallback for STT input beyond letting the user type instead.
- Rate limits: TTS 20/min, STT 10/min, separate from the general API limiter and the login limiter (5/min). Respect these — don't hammer on retry.

**Known real behavior, not bugs, don't "fix" them:**
- A field with under 7 days of weather history returns `422 {"error":{"code":"NO_WEATHER_DATA",...}}` on every value endpoint. This is correct, intentional behavior (a genuinely fixed bug from Module 22 — it used to 500). Design an honest "gathering data" empty state for this, don't treat it as an error.
- `/v1` still exists (single shared API key, one hardcoded demo farmer) purely for backward-compat/demo purposes. **Do not build the farmer app against `/v1`.** It has no real per-farmer auth and isn't part of this frontend's scope.
- CORS is enabled via `CORS_ORIGINS` env var, scoped to `/v2/*` only, `supports_credentials=True`. If you're building the landing page as a separate origin hitting the API directly (you're not — see below), this is already handled; it's not handled for `/v1`.

## The three products — build them as three products, not one

Do not let one design system leak across all three. They have different audiences and different constraints.

### 1. Farmer app — React Native + Expo (the real build effort)

**Audience:** Bellary-district Karnataka farmers. Mixed literacy — some can't read fluently in Kannada or English. Budget Android phones, often shared within a household. Real, not hypothetical, 2G/3G dead zones. High trust in voice and human intermediaries over dense text.

**Non-negotiable design posture — voice-first, not text-first-with-voice-bolted-on:**
- First-launch language picker: ಕನ್ನಡ and English shown **in their own script**, each tappable to hear a spoken sample before committing, no scrollable list, device locale used only as a weak initial guess.
- Every advisory speaks itself automatically (or on one tap) before the user has to read anything. Body text on screen is a **transcript** of what's spoken, not the primary channel.
- Numbers and icons over sentences: irrigation depth as "33.2 mm" with a water-drop row, not a paragraph. Map `risk_level`/`urgency` to a consistent red/amber/green system everywhere, not just once.
- One primary action per screen. Don't build a generic bottom-tab-bar-first navigation without questioning it — bottom nav bars are frequently invisible to first-time rural users; prefer in-flow, in-context buttons embedded in the content they act on.
- A persistent, icon-only, always-visible language switch — never buried in a settings menu.

**Offline is not optional — design for it from the start, not bolted on later:**
- Cache the last-fetched advisory **and its audio** locally (`expo-sqlite` + Drizzle recommended) with a visible staleness timestamp. The app must render something correct and usable with zero network on open — never a blank screen or crash.
- Bundle pre-recorded audio for every static UI string (including the language picker itself) directly in the APK, so first launch works with zero network at all.
- Feedback and disease-photo submissions queue locally when offline. On reconnect: exponential backoff with jitter, treat HTTP 429 as "back off and retry," not "failed" — and **serialize** these retries, don't fire them in parallel, because a reconnect burst hitting the backend's own rate limiters is a self-inflicted thundering herd.
- Android's built-in on-device TTS is the fallback whenever `VOICE_UNAVAILABLE` (503) comes back or the device has no network — structurally the same fallback pattern the backend already uses for CNN→rule-based disease detection, so treat it with the same seriousness, not as an afterthought.

**Auth/session handling:** store the session cookie securely (Expo SecureStore), persist across app restarts, handle 401 globally by routing back to login — don't let individual screens each reinvent "what happens when my session expired."

**Cross-tenant safety in the client:** a 404 on any farmer-scoped resource means "not yours or doesn't exist" — never render a generic error that could leak whether something exists. Treat it the same as "not found," full stop.

### 2. Landing page — Next.js + Tailwind + shadcn/ui, hybrid 3D/restrained

**Audience:** evaluators, examiners, recruiters — and separately, the non-technical helper who sideloads the APK for a farmer. **Not** farmers themselves.

- Above-the-fold: what this is and who it's for, readable in under 10 seconds — restrained here even if the rest of the page leans 3D/motion. Don't let hero motion sit on top of content that needs careful reading.
- A real, honest product story: three real trained models (crop recommendation RandomForest with regional-suitability sanity checks, ET0/FAO-56 irrigation math, a MobileNetV2 CNN at 99.24% val accuracy on PlantVillage). State it as capstone-grade work, not oversold as commercial-scale infrastructure.
- Prominent APK download: a button and a QR code, both pointing at the current build. This is the only distribution channel for now — no Play Store yet.
- A dedicated, illustrated, plain-language install-flow section walking through Android's "install from unknown sources" security prompts, written for the helper doing the install, not the farmer using the app afterward. Ideally with a Kannada-narrated screen recording, since the same trust/literacy considerations apply to whoever's doing the sideload.
- Fully mobile-responsive — people will view this on a phone during a demo.
- Design inspiration already gathered from Godly.design, a Behance "Hecta Agriculture Website" case study, and an agriculture-landing-page Pinterest board — check with me before finalizing visual direction if you want those references, I have them saved.
- Free component libraries to actually use: `shadcn/ui` (MIT, CLI-installed, source-copied) as the foundation; Magic UI / Aceternity UI / Skiper UI for motion and landing-specific visual components (free tiers). If a `shadcn-ui-mcp-server` MCP is configured in this environment, use it so component APIs aren't hallucinated — check before assuming component props.

### 3. Admin dashboard — do not touch

The existing server-rendered Jinja2 admin (built in Module 19) is reused as-is. It is dense, functional, and boring on purpose — its only user is me. No redesign, no migration to React, no new admin features as part of this frontend work. If you find a genuine admin gap while building the other two surfaces, flag it to me — it becomes its own future backend module, not scope creep here.

## Explicit non-goals for this phase — don't build these

- WhatsApp integration (costs money, deferred until there's funding)
- Play Store packaging/signing (APK-link distribution only, for now)
- Any pricing, ROI, or monetization UI
- A literacy-tier "simple mode" toggle (voice-first-by-default should already cover this; revisit only if real usage data says otherwise)
- Real farmer usability testing — there is no testing group available before the report deadline. This means every UX decision above is a research-grounded hypothesis, not a field-validated one. Say so if it comes up; don't imply testing happened.

## Full detail

The complete PRD (problem statement, goals, non-goals, user stories per persona, prioritized requirements with acceptance criteria, success metrics, open questions, suggested phasing) is in `docs/` — read `agro_mirai_frontend_prd.md` if it's been placed there, or ask me for it if it isn't in the repo yet. Two research documents (`agro_mirai_uiux_research.md`, `frontend_research.md`) go deeper on the sourcing behind every UX call above — worth reading before you disagree with one of them.

## Open questions you'll hit — flag them, don't silently decide

- EAS Build's free-tier monthly quota wasn't confirmed from Expo's docs — `eas build --local` is the safety valve if cloud quota runs out mid-project. Check which build path we're actually using before setting up CI around it.
- The static-UI-string bundled-audio set needs a defined string list and a generation plan (batch AI4Bharat TTS output, most likely) before APK size and build pipeline work locks in — don't record/generate ad hoc as you go.
- Whether farmer registration itself needs a literacy-friendly redesign, or whether "a helper does the one-time setup" (already assumed for install) extends to registration too — open, needs my input.

## How I'll be checking your work

I independently verify everything against the live backend before trusting a report — I don't take "tests pass" at face value, I run real curl calls against a freshly seeded database myself. Expect the same discipline on the frontend side: don't just say a screen "works," tell me what you actually tested it against (which endpoint, which response, which error state), and flag anything you built around a guess rather than a confirmed contract detail.
