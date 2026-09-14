# AGRO MIRAI — Antigravity Kickstart Prompt (v2, with finalized UI/UX + brand theme)

Paste everything below into Antigravity. You already have the `AGRO MIRAI` folder open — read `CLAUDE.md`, `PROGRESS.md`, and `specs/core/openapi.yaml` first, before writing any code, so you understand the real project history and the real API surface rather than working from this prompt alone.

---

## Step 1 — Understand the project before building anything

Before touching the mobile app, read and internalize:
- `CLAUDE.md` — full doctrine and project history
- `PROGRESS.md` — every module built so far, in order
- `specs/core/openapi.yaml` — the **frozen frontend contract**, every route and shape
- `specs/core/schema.yaml`, `specs/core/enums.md` — the data model
- `decisions/0017-multi-tenant-v2.md`, `decisions/0020-v2-value-endpoints-and-voice-api.md` — why `/v2` is shaped the way it is

Once you've read these, summarize back to me (briefly) what you understand the backend to do and how `/v2` auth works, so I can confirm you're building against reality before real screens get written. Don't skip this step or start scaffolding screens first — I will independently verify anything you build against the live backend myself, the same way I verified this contract before writing this prompt.

## Step 2 — Tooling

Use **Expo (managed workflow) via the Expo CLI**, not a bare React Native project. Set up with `npx create-expo-app`, TypeScript template. Use `react-native-reusables` (shadcn ported to RN via NativeWind) as the component foundation — check whether a `shadcn-ui-mcp-server` MCP is configured in this environment before hand-rolling any component, so component APIs aren't guessed. Use `expo-sqlite` + Drizzle for local storage, Expo SecureStore for the session cookie.

## Step 3 — The backend contract, in full

**Auth (`/v2`, session-based, not the old `/v1` shared-key path — do not build against `/v1`):**
- `POST /v2/auth/register` — does **not** auto-login; call `POST /v2/auth/login` explicitly afterward, don't assume a session exists post-register.
- `POST /v2/auth/login`, `POST /v2/auth/logout`.
- Session cookie is `HttpOnly`, `SameSite=None` by default, `Secure` in production. Store it via SecureStore, attach on every request, handle a global 401 by routing back to login rather than letting each screen reinvent that logic.

**Six value endpoints, all session-scoped, all confirmed to 404 (never 403) on cross-tenant access:**
- `GET /v2/fields/{id}/recommendation`
- `GET /v2/fields/{id}/irrigation`
- `GET /v2/fields/{id}/disease-risk`
- `POST /v2/fields/{id}/disease-risk/image` — image bytes in, CNN-based detection out; falls back to `source: "environmental_fallback"` when the CNN service is unreachable. This is a **designed degraded state** — render it as "using field conditions instead of photo analysis," not as an error.
- `GET /v2/fields/{id}/advisories`
- `POST /v2/feedback` — body needs `advisory_id`, `rating`, `helpful` (boolean), optional `comment`.

**Field CRUD:** `GET/POST /v2/fields`, `GET /v2/fields/{id}`, `PATCH /v2/fields/{id}` (field is `current_crop`, not `crop`), `DELETE /v2/fields/{id}` (204 success, 404 not-found-or-not-yours).

**Farmer profile:** `GET /v2/farmers/me`, `PATCH /v2/farmers/me` (`name`, `preferred_language` — validated against `{en, kn}` only, 400 on anything else).

**Voice — core to this app, not an add-on:**
- `GET /v2/advisories/{advisory_id}/audio` — per-advisory OGG/Vorbis, ETag + `Cache-Control: private, max-age=86400`, genuinely client-cacheable. Defaults to the farmer's `preferred_language`, overridable via `?language=`.
- `POST /v2/stt` — multipart WAV/OGG/MP3, magic-byte validated, 10MB cap.
- **Both return real `503 {"error":{"code":"VOICE_UNAVAILABLE",...}}` when the voice service is unreachable — I confirmed this live myself.** Catch this specific code and fall back to Android's on-device TTS for output; there's no STT fallback beyond letting the user type.
- Rate limits: TTS 20/min, STT 10/min, separate from the general limiter and the 5/min login limiter. Respect these on retry — never hammer.

**Known real, correct behavior — don't treat these as bugs:**
- A field with under 7 days of weather history returns `422 {"error":{"code":"NO_WEATHER_DATA",...}}` on every value endpoint. Design an honest "gathering data" empty state for it (see §5 below) — this was a real, fixed bug (used to 500), now correct behavior.
- `/v1` exists only for backward-compat demo purposes. Not part of this build.

## Step 4 — The UI/UX direction (finalized, build to this exactly)

We researched real shipped farmer apps (FarmRise/Cargill, Kisan Suvidha, Plantix, Farmer.Chat/Digital Green) plus academic low-literacy UX research before landing here. This is a **hybrid of three patterns**, and each element below exists for a specific reason — don't simplify it back down to a generic dashboard.

### Home screen — three stacked zones, in this exact order

**Zone 1 — Hero ("press to hear"):** the largest element on the screen. A big circular play button labeled "Today's Advisory" (localized). One press auto-plays the current field's most urgent advisory via `GET /v2/advisories/{id}/audio`, with the transcript animating in as large-type text underneath. This answers "what should I do today" in one press with zero reading — the single most common need.

**Zone 2 — Direct-access row:** 4 compact icon+severity chips directly below the hero — Irrigation, Disease, Crop Recommendation, History — for a returning farmer who already knows what they want and doesn't need to go through the feed. Each chip shows a small severity dot (red/amber/green) reflecting current state at a glance.

**Zone 3 — Feed:** below the direct-access row, a scrollable list of chat-bubble-style cards — one per advisory/field/event — **severity-sorted (most urgent first), not chronological**. Each bubble has a tap-to-play voice-note-style control (waveform + duration, like a WhatsApp voice note) and a one-line transcript. This deliberately mirrors WhatsApp's message-bubble pattern because that's the interaction model this user population already has deep fluency in — don't redesign it into a generic card list.

**Persistent header (always visible, never scrolls away):** language switch icon (🌐/ಕನ🡒EN toggle) on one side, field switcher (dropdown showing the active field's name) on the other. Switching fields re-sorts the hero + feed in place — it never navigates to a new screen.

### Other screens
- **Language picker (first launch):** two large side-by-side cards, ಕನ್ನಡ and English, each shown in its own script only, each tap-to-preview a spoken sample of the language naming itself before committing. No scrollable list, no translation-of-the-other-language text anywhere on this screen.
- **Advisory detail:** thin top band of severity color (never the full background), large numeral/icon, auto-playing audio + large-type transcript, one "why" expand for the `ExplanationService` reasoning (spoken + shown), one thumbs-up/down feedback control. One continuous top-to-bottom read, no tabs.
- **Disease check:** opens directly to the camera (no intermediate form/settings screen), big shutter button. Result reuses the advisory-detail pattern, with `environmental_fallback` rendered as its own honest chip, not an error state.
- **Field management:** simple list, each field a card (name, crop icon, severity dot), tapping sets it active on Home. Add/edit/delete are labeled buttons, not icon-only — this is low-frequency enough to spell out.

### Brand theme — "Field & Grain" (use these values exactly, don't substitute a generic Material green)

Two palettes, kept strictly separate — brand color never doubles as status color:

**Brand palette:**
- `brand-green-900` `#1B4332` — header, hero button fill, primary text on light backgrounds
- `brand-green-600` `#2D6A4F` — primary buttons, active states
- `brand-green-100` `#D8F3DC` — card backgrounds, subtle fills
- `grain-cream` `#FDF8EE` — app background (warm off-white, deliberately not pure white — better outdoor-sunlight legibility)
- `soil-brown` `#7A5C3E` — secondary accents/dividers, used sparingly
- `ink-900` `#22281F` — primary text (warm near-black, not pure `#000`)

**Severity palette (status only — never decorative, never mixed with brand color):**
- `status-good` `#2E7D32`
- `status-caution` `#E8A33D` (amber, not yellow — outdoor-glare legible)
- `status-urgent` `#C1432A` (warm red-orange, deliberately not alarm-red)

**Typography:** Noto Sans + Noto Sans Kannada, bundled as variable fonts. Minimum 18sp body text, 28sp+ for hero numerals/severity readouts — non-negotiable given outdoor use and the target literacy range, not a later polish item.

**Iconography:** one consistent, custom flat line-and-fill icon set (same stroke width, same corner radius throughout) — a water drop for irrigation, a leaf-with-magnifier for disease, a seedling for recommendation, a speech-bubble-with-waveform for the hero button. Do not mix in a stock icon pack; a mismatched icon set is one of the fastest ways this reads as unfinished in a demo.

**Motion:** minimal and purposeful only — a press state on the hero button, the waveform animating during audio playback, a gentle fade when the feed re-sorts after switching fields. No page-transition flourishes, no decorative animation, no loading spinners that run longer than a fraction of a second feels like. This is intentionally different from the (separate, not-yet-built) landing page, which is allowed more motion — the farmer app stays close to zero.

**Tone of voice for any copy:** short, second person, no jargon — "Water your field today," never "Irrigation is recommended for optimal yield outcomes." Every string should pass a read-aloud test against AI4Bharat TTS output before it ships, since it will always be heard, not just read.

## Step 5 — Offline behavior (build this in from the start, not after)

- Cache the last-fetched advisory **and its audio file** locally with a visible staleness timestamp ("as of [date]"). The app must render something correct with zero network on open — never blank, never a crash.
- Bundle pre-recorded audio for every static UI string, including the language picker itself, directly in the APK — first launch must work with zero network at all.
- Feedback and disease-photo submissions queue locally when offline; on reconnect, retry with exponential backoff + jitter, treat HTTP 429 as "back off," not "failed," and **serialize** retries — don't fire them in parallel and trip the backend's own rate limiters.
- On `503 VOICE_UNAVAILABLE` (or no network), fall back to Android's on-device TTS reading the advisory's text fields, after a device-capability check.

## Step 6 — Explicit non-goals, don't build these

- WhatsApp integration (costs money, deferred)
- Play Store packaging (APK-link distribution for now)
- Pricing/ROI/monetization UI
- A separate "simple mode" literacy toggle (the voice-first default should already cover this)
- Anything implying real farmer usability testing happened — it hasn't, before this deadline. If asked, say so plainly.

## Step 7 — How I'll check your work

I independently verify against the live backend myself before trusting a report — real curl calls against a freshly seeded database, not just "tests pass." Expect the same standard here: tell me specifically which endpoint/response/error state you tested a screen against, and flag anything built around a guess rather than a confirmed contract detail (including anything in this prompt that turns out to not match what you find in `openapi.yaml` when you actually read it — the spec file wins over this prompt if they ever disagree).

## Open questions — flag to me, don't silently decide

- EAS Build's free-tier monthly quota wasn't confirmed — `eas build --local` is the fallback if cloud quota runs out mid-project.
- The bundled static-string audio set needs a defined string list and a generation plan (batch AI4Bharat TTS, most likely) before APK size/build pipeline decisions lock in.
- Whether farmer registration itself needs a literacy-friendly redesign, or whether "a helper does one-time setup" extends from install to registration too.
