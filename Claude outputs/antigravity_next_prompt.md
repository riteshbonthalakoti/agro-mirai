One correction before you start: drop the "60% self-register / 40% assisted-registration" split from your plan — that number wasn't given to you by me or by the user, don't invent adoption statistics. Build one single, accessible registration flow (large touch targets, voice hints, works for a farmer alone or with a helper) rather than branching UI for an assumed user split we have no data for.

Proceed in this order. Design each screen in Stitch MCP first (Field & Grain palette: `brand-green-900 #1B4332`, `brand-green-600 #2D6A4F`, `brand-green-100 #D8F3DC`, `grain-cream #FDF8EE` background, `soil-brown #7A5C3E`, `ink-900 #22281F` text; severity `status-good #2E7D32` / `status-caution #E8A33D` / `status-urgent #C1432A` kept visually separate from brand color; Noto Sans + Noto Sans Kannada, 18sp+ body / 28sp+ hero numerals) before converting each to code — don't write component code ahead of a Stitch design existing for that screen.

1. Scaffold the Expo project via CLI (`create-expo-app`, TypeScript template), then configure NativeWind + `react-native-reusables` via their CLI installers. Confirm the toolchain builds and runs on a simulator/device before any screen work starts.

2. Set up the offline data layer: `expo-sqlite` + Drizzle schema covering cached fields, cached advisories (with their audio file blobs/paths and a fetched-at timestamp for staleness display), and a local write-queue table for pending feedback/disease-photo submissions (status: pending/syncing/failed, retry count, next-retry-at for backoff+jitter).

3. Build the API client: base URL config, cookie-based session handling via Expo SecureStore, a global 401 handler that routes to login, and typed request/response functions for every `/v2` route from `openapi.yaml` — generate these from the spec if tooling allows, don't hand-type shapes that can drift from the contract.

4. Design and build the language picker screen (first-launch): ಕನ್ನಡ / English cards in-script only, tap-to-preview spoken sample, confirm-to-commit. Wire it to `PATCH /v2/farmers/me` for language changes post-registration, and to local storage for the pre-login first-launch case.

5. Design and build the single registration/login flow (no invented user-segment branching, per the correction above): register → explicit login call (register does not auto-session) → session stored → route to Home.

6. Design and build the Home screen exactly as the three-zone spec: hero press-to-hear button (Zone 1), 4-icon direct-access row with severity dots (Zone 2), severity-sorted chat-bubble feed (Zone 3), persistent header with language switch + field switcher. Wire Zone 1 and Zone 3 to `GET /v2/fields/{id}/advisories` and `GET /v2/advisories/{id}/audio`; wire Zone 2's icons to their respective endpoints on tap-through.

Stop after Home is built and wired to real data (a real seeded field, real advisory, real audio playback including the on-device-TTS fallback on a real `503`) and report back before moving on to the advisory-detail, disease-check, and field-management screens — I want to see and verify Home working end to end first.
