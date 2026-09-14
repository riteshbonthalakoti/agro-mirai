# AGRO MIRAI — Frontend PRD (Farmer App, Landing Page, Admin)

**Status:** Draft v1 — ready for Antigravity build
**Backend contract:** `specs/core/openapi.yaml` @ commit `66b003d` (frozen frontend contract per `decisions/0020-v2-value-endpoints-and-voice-api.md`), independently live-verified
**Author:** Ritesh, with Claude (Cowork) as orchestrator/verifier
**Target:** VTU Semester 7 AIML capstone (22AIP76, 2022 scheme), final report due Nov 14

---

## 0. What this PRD covers

Three separate products sharing one backend, not one product with three views. Building them as one design system is the single biggest UX risk this project has already identified and rejected — each gets its own section below because each has a different audience, different constraints, and a different bar for "done."

| Surface | Audience | Built with | Distribution |
|---|---|---|---|
| Farmer app | Bellary-district farmers, mixed literacy, budget Android, patchy connectivity | React Native + Expo | APK download link on the landing page (Play Store later, post-funding) |
| Landing page | Evaluators, examiners, recruiters, and the "assisted install" helper who sideloads the APK for a farmer | Next.js + Tailwind + shadcn/ui, hybrid 3D/restrained | Public URL |
| Admin dashboard | Ritesh only | Existing server-rendered Jinja2 (Module 19) | Already live — reused, not rebuilt |

---

## 1. Problem Statement

AGRO MIRAI's backend is verified production-grade: real ET0-based irrigation math, a 99.24%-val-accuracy CNN for disease detection, regionally-sane crop recommendations, and now (Module 23) a genuine per-farmer authenticated API surface with voice endpoints. None of that is reachable by an actual farmer today — there is no client. A Bellary-district farmer with a basic Android phone, inconsistent literacy in Kannada or English, and intermittent 2G/3G connectivity has no way to ask AGRO MIRAI "should I irrigate today" and hear an answer in their own language. Every week without a client is a week the backend's real value is invisible to the people it was built for, and to the evaluators judging whether this is a demo or a product.

## 2. Goals

1. A farmer with zero prior app-store experience can install the APK (with one assisted install) and reach a spoken, correct advisory for a real field in under 5 taps from first open — no reading required to get there.
2. Every advisory the app shows is voice-first: spoken automatically or on one tap, in the farmer's chosen language, before any body text is the primary channel.
3. The app is usable — not just installable — on a patchy connection: a farmer with no signal can still open the app and hear the last cached advisory and its audio.
4. The landing page converts an evaluator's first 10 seconds into "this is a real product," and gets a real APK into a real hand via QR/download link with an install flow a non-technical helper can follow start to finish.
5. Zero rebuild of the admin surface — Module 19's Jinja2 dashboard remains Ritesh's single pane of glass, untouched by this PRD's scope.

## 3. Non-Goals

- **WhatsApp integration.** Costs money (Twilio/WhatsApp Business API), explicitly deferred until there's funding. Rationale: user decision, not a technical blocker.
- **Play Store distribution.** APK-via-link only for v1; Play Store review/signing/ASO is a distribution problem for a funded phase, not a capstone-report problem.
- **Pricing, ROI, monetization UI.** Explicitly parked by the user — "not right now at all."
- **Real farmer usability testing before the report deadline.** No testing group is available in this timeline. Every UX decision below is a research-grounded hypothesis, not a validated one — the PRD and the final report must say so plainly, not imply field validation that didn't happen.
- **Rebuilding the admin dashboard as a React SPA.** Module 19's server-rendered Jinja2 admin already works and is scoped to an audience of one (Ritesh). Rebuilding it spends effort the farmer app and landing page need more.
- **A "simple mode" / literacy-tier toggle.** Flagged as an open question in earlier research (household literacy varies by user and day) but out of scope for v1 — the voice-first default should already degrade gracefully for lower-literacy users without a separate mode; revisit only if usage data or a future testing round shows it's insufficient.

## 4. User Stories

### Farmer (primary persona — mixed literacy, Kannada or English, budget Android, patchy connectivity)
- As a farmer opening the app for the first time, I want to hear both language options spoken aloud and pick by tapping a script I recognize, so that I never have to read to get started.
- As a farmer, I want today's advisory spoken to me automatically when I open the app, so that I don't have to read anything to know what to do today.
- As a farmer, I want irrigation and disease results shown as big numbers, icons, and red/amber/green severity — not paragraphs — so that I can act on them at a glance.
- As a farmer, I want to take a photo of a diseased leaf and get a result, so that I don't need to describe symptoms in words.
- As a farmer with no signal right now, I want to still open the app and hear my most recent advisory, so that a bad-connectivity day doesn't mean a useless app.
- As a farmer, I want to tell the app whether an advisory was actually helpful with one tap, so that giving feedback doesn't cost me more effort than the advisory itself.
- As a farmer, I want to switch language at any time from one visible icon, so that I'm never stuck in the wrong language.
- As a farmer, I want to add or remove a field I farm, so that the app reflects the land I actually work.

### Evaluator / first-time visitor (landing page persona)
- As an evaluator, I want to see in seconds what AGRO MIRAI does and who it's for, so that I understand the product before I read a line of code.
- As an evaluator or helper, I want a QR code or direct link to download the APK, so that I can get the real app on a real phone during a demo.
- As a non-technical helper installing the app for a farmer, I want a plain, illustrated (ideally Kannada-narrated) walkthrough of the Android "install from unknown source" flow, so that the security warnings don't stop the install.

### Admin (Ritesh — out of scope for new build, listed for completeness)
- As the admin, I continue using the existing Jinja2 dashboard for farmer/field/feedback oversight — no new stories, no new screens.

## 5. Requirements

### 5.1 Farmer App (React Native + Expo)

**Must-Have (P0)**
- Voice-first language picker on first launch: ಕನ್ನಡ / English shown in-script, each with a tap-to-preview spoken sample, no scrollable list, default guess from device locale only.
- Persistent, one-tap language switch (icon, always visible, not buried in settings) — calls `PATCH /v2/farmers/me`.
- Login/session flow against `/v2/auth/{register,login,logout}` with the existing bcrypt+session-cookie mechanism; session persists across app restarts (secure storage of the session cookie).
- Field list and field detail, backed by `GET /v2/fields`, `POST /v2/fields`, `PATCH /v2/fields/{id}`, `DELETE /v2/fields/{id}`.
- Advisory screen: fetches `GET /v2/fields/{id}/advisories`, renders severity/urgency as a consistent red/amber/green system, auto-plays or one-tap-plays the advisory's cached audio via `GET /v2/advisories/{id}/audio`.
- Irrigation screen: `GET /v2/fields/{id}/irrigation`, numeric depth + icon row over prose.
- Recommendation screen: `GET /v2/fields/{id}/recommendation`.
- Disease detection: camera capture → `POST /v2/fields/{id}/disease-risk/image`; must handle and clearly surface the `environmental_fallback` state (CNN service unreachable) without looking like an error — this is a designed degraded state, not a failure.
- Feedback: one-tap thumbs-style capture → `POST /v2/feedback` (`advisory_id`, `rating`, `helpful`, optional `comment`).
- Offline read path: last-fetched advisory + its audio cached locally (expo-sqlite) with a visible staleness indicator ("as of [date]"); app must render correctly with zero network on open, not blank/crash.
- Offline write queue: feedback and disease-photo submissions queue locally when offline, retry with exponential backoff + jitter on reconnect, explicitly treat HTTP 429 as backoff-not-failure, serialize (not parallelize) retries to respect the backend's rate limits (login 5/min, TTS 20/min, STT 10/min, general limiter).
- Android on-device TTS fallback: when `GET /v2/advisories/{id}/audio` (or the underlying voice service) returns `503 VOICE_UNAVAILABLE`, fall back to Android's built-in TTS reading the advisory's text fields, with a device-capability check before attempting it.
- Bundled, pre-recorded audio (shipped in the APK, zero network required) for all static UI strings, including the first-launch language picker itself.
- 404-vs-403 awareness in the client: a 404 on any farmer-scoped resource means "not yours or doesn't exist," never surfaced as a generic error — the app should never let a farmer believe another farmer's data exists.

**Nice-to-Have (P1)**
- Voice input for STT-backed interactions (`POST /v2/stt`) as an alternative to typed feedback comments — nice-to-have because the core loop (advisory in, feedback out) doesn't require typed or spoken free text at all.
- A single "why" tap on any advisory that surfaces the existing `ExplanationService` reasoning, spoken and shown, to build trust through visible reasoning rather than a polished UI alone.
- A share action (image/text summary suitable for forwarding) even without WhatsApp API integration — just a native share-sheet intent, since WhatsApp is this population's actual trust/distribution channel even without a paid integration.

**Future Considerations (P2)**
- WhatsApp Business API integration as a parallel lightweight surface.
- A literacy-tier "simple mode" toggle, if usage data post-launch shows the voice-first default isn't sufficient on its own.
- Play Store packaging and signing.
- Multi-user-per-device handling beyond a single logged-in session.

### 5.2 Landing Page (Next.js + Tailwind + shadcn/ui)

**Must-Have (P0)**
- Above-the-fold: what AGRO MIRAI is, who it's for, in under 10 seconds of reading — restrained, not maximal, at this one spot even within a hybrid 3D aesthetic elsewhere on the page.
- Clear, prominent APK download: a button and a QR code, both pointing at the current APK build.
- A short, real product story: the three real models (crop recommendation, ET0 irrigation, CNN disease detection), stated honestly as capstone-grade, not oversold as production-scale commercial infrastructure.
- An install-flow section: illustrated, step-by-step, plain-language walkthrough of Android's "install from unknown sources" prompts — written for the helper doing an assisted install, not the farmer.
- Mobile-responsive — a meaningful share of visitors on a demo day will view this on a phone.

**Nice-to-Have (P1)**
- The restrained-vs-3D hybrid treatment: 3D/motion elements reserved for hero/storytelling sections, restrained typography and layout for the install-flow and technical-credibility sections — motion should never sit on top of the one section that needs to be read carefully (the install walkthrough).
- A short embedded demo video/GIF of the app in actual use.

**Future Considerations (P2)**
- Localization of the landing page itself into Kannada (currently out of scope — its audience is evaluators/helpers, not farmers directly).
- A dealer/KVK-officer-facing variant of the page.

### 5.3 Admin Dashboard

**Must-Have (P0):** none — no new work. Existing Module 19 Jinja2 admin is reused as-is.

**Explicitly out of scope:** any redesign, any migration to a JS framework, any new admin-facing feature as part of this PRD. If a genuine admin gap surfaces during frontend work, it gets its own future module, not scope creep here.

## 6. Success Metrics

Framed as capstone-appropriate leading indicators (weeks, not months) plus honesty about what can't be measured without real users.

**Leading indicators (demonstrable before/at report deadline):**
- Time-to-first-spoken-advisory from cold app install: target under 60 seconds end to end (install → language pick → login/register → first advisory heard), stretch target under 30 seconds.
- Taps-to-first-advisory from app open (already-logged-in state): target ≤ 5 taps, matching Goal 1.
- Offline resilience: advisory + audio genuinely renders with the device in airplane mode after one prior online session — binary pass/fail, demoed live.
- APK install-flow completion: a non-technical person (family member, classmate — anyone who is not Ritesh or a developer) completes a sideload install unaided using only the landing page's walkthrough — binary pass/fail, demoed before submission.

**Lagging indicators (explicitly not measurable in this timeline — stated honestly in the report):**
- Real farmer adoption, retention, satisfaction. No real-farmer testing group exists before the deadline (Non-Goal, §3); the report should present the above leading indicators as the evidence available, and name real-user validation as explicit future work.

## 7. Open Questions

- **[Design]** Exact motion/3D treatment for the landing page hero — how much is "hybrid," concretely, before it starts working against the restrained sections? Needs a first draft to react to rather than resolving in the abstract.
- **[Engineering]** EAS Build free-tier monthly quota could not be confirmed from Expo's docs during research — `eas build --local` was flagged as the safety valve. Confirm which build path (cloud EAS vs. local) before CI/build automation is set up, so it isn't discovered mid-build.
- **[Engineering]** Bundled pre-recorded audio for static UI strings needs a defined string list and a recording/generation plan (AI4Bharat TTS batch-generated once, or real voice recordings?) before APK size and build pipeline work starts.
- **[Product]** Does farmer registration require an assisted flow (a helper enters details) or can a farmer self-register voice-first? Current `/v2/auth/register` is a standard email/password form-shaped endpoint — worth deciding whether registration itself needs a literacy-friendly redesign or whether "helper does the one-time setup" (already the assumption for install) extends to registration too.
- **[Product]** What happens for a brand-new field with insufficient weather history (the `422 NO_WEATHER_DATA` case, confirmed live via my own verification)? The app needs an explicit, honest empty/waiting state for this — not a generic error — and that state hasn't been designed yet.

## 8. Timeline Considerations

- **Hard deadline:** final report due Nov 14 — the farmer app's P0 list and the landing page's P0 list are the real scope; everything in P1/P2 is fast-follow or explicitly future work in the report, not a promise for Nov 14.
- **Dependency:** none of this blocks on further backend work — `openapi.yaml` is frozen and independently verified live as of this PRD.
- **Suggested phasing within the deadline:**
  1. Landing page skeleton + APK download mechanism first (even before the app is feature-complete, so there's always something demoable).
  2. Farmer app P0 core loop: language picker → login → field list → advisory (text + audio) → feedback. This is the minimum that proves the concept end to end.
  3. Offline read/write resilience (cache + queue) — layered onto the working core loop, not built in parallel with it.
  4. Disease-image capture and the `environmental_fallback` state.
  5. Landing page polish (3D/motion, install-flow walkthrough content, demo video) once the app exists to film/screenshot.
- **Explicit risk:** the offline-first work (§5.1, write queue with backoff/jitter) is the single most engineering-heavy P0 item and the one most likely to get cut under deadline pressure. If it must be cut, degrade gracefully to "online-only, cached-read-only" rather than dropping the read-side offline cache entirely — losing write-offline is a smaller UX hit than losing read-offline for this user.

---

*Grounded in `/tmp/agro_mirai_uiux_research.md` and `/tmp/frontend_research.md`, and the user's seven numbered platform decisions (React Native + Expo; hybrid 3D/restrained landing page; no real farmer testing available; reuse Jinja2 admin; APK-link distribution for now, Play Store later; no pricing/ROI yet; pre-cached TTS + Android on-device fallback for voice). Backend surface verified live by Claude (Cowork) against a freshly seeded database, not from Claude Code's self-reported transcript alone.*
