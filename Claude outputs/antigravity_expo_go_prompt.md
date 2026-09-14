Wire the mobile app to the new Supabase Auth (Module 26 — this replaces the old `/v2/auth/register|login|logout` calls the auth screens were built against) and get it running in Expo Go on my phone so I can test the actual UI/UX, not just the simulator.

## 1. Replace the auth calls

Read `decisions/0022-supabase-auth-migration.md` first — it documents exactly what changed. Summary: `/v2/auth/*` no longer exists. The app must now use the Supabase JS SDK (`@supabase/supabase-js`, with an Expo-compatible storage adapter — `expo-secure-store` or `AsyncStorage` per Supabase's RN setup docs, don't hand-roll token storage) directly:

- Sign-up/sign-in/sign-out go through `supabase.auth.signUp()` / `signInWithPassword()` / `signOut()`, not any Flask endpoint.
- Every `/v2` request (fields, advisories, irrigation, recommendation, disease-risk, feedback, farmers/me, advisories/{id}/audio, stt) now sends `Authorization: Bearer <session.access_token>` from the Supabase SDK's session object — replace whatever cookie-based request logic exists with this.
- There's no more "logged in" cookie state to manage manually — `supabase.auth.onAuthStateChange()` is the source of truth for session state; wire the app's AUTH→HOME state transition off that listener, not off a custom flag.
- Session persistence across app restarts is the SDK's job (with the storage adapter configured) — don't reimplement it with SecureStore directly the way the old cookie approach needed.
- Farmer profile note: Flask auto-provisions the farmer profile row on first authenticated request — there's no explicit "create profile" call after sign-up, don't add one.

## 2. Get me testing on my actual phone via Expo Go

- Confirm the project runs with `npx expo start` and that Expo Go on my phone can connect to it — same Wi-Fi network as this machine, scan the QR code from the terminal/Dev Tools.
- Point the app's API base URL at wherever the Flask backend is actually reachable from my phone on this network (not `localhost` — that won't resolve from a physical device; use this machine's LAN IP, and tell me what to set it to).
- If the backend isn't running locally right now, tell me exactly what to start (and how) before I scan the QR code — don't assume it's already up.
- Confirm no native modules are in use that Expo Go can't handle (Expo Go only supports what's in the default Expo SDK — if `expo-sqlite`, `expo-secure-store`, `expo-speech`, `expo-av` etc. all still work fine in Expo Go, say so explicitly; if anything needs a dev build instead, tell me now rather than after I've already tried scanning the QR code).

## 3. What I'm checking for once it's running

- Language picker: both cards, in-script only, tap-to-preview audio actually plays on a real device speaker.
- Home screen: hero button, icon row, feed — actually matches the "Field & Grain" spec (colors, spacing, font) on a real screen, not just the simulator.
- Real sign-up → real sign-in against the live Supabase project → real Home screen with real data from a seeded field.
- Voice playback and the on-device TTS fallback both actually produce audio on the phone's speaker.

Report back once it's running and I can scan the QR code — tell me the exact URL/IP to point my phone at and whether the backend needs to be started first.
