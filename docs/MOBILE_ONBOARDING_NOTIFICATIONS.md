# Mobile onboarding flow, coach-mark tour & notification system

Date: 2026-09-24. Scope: `mobile/` (Expo SDK 57). Status: implemented, typechecked and bundled;
**not yet verified on a physical device** (see "Open items").

## 1. Launch flow (rule: "not signed in" => language screen)

```
not signed in : Splash animation -> Language -> Permissions (first time on device only) -> Sign in -> (add field) -> Coach tour -> Home
signed in     : Splash animation -> Home   (no language / permission / tour screens)
```

- `App.tsx` `RootInner` boot: wake server -> `GET /v2/farmers/me`. Success => main. 401 => clear farmer cache,
  `pendingPhase='lang'` (shown after the splash). Offline with no cached farmer => language (if none saved) or sign-in.
- The global 401 handler (`goAuth`) is a no-op during boot, so a fresh install never shows "session ended".
- Device-level flags kept across sign-out (`storage.clearFarmerCache`): `lang`, `permsAsked`, `tourSeen`.
- Sign-in screen (`AuthScreen`): cream background, logo mark top centre; notices (e.g. session ended) are
  dismissible with an X and auto-hide after 6 s (`Notice`); footer links open Terms & Conditions / Privacy
  Policy sheets (`LegalModal`, draft English text pending legal review; link labels translated).
- Permissions screen asks location, camera, gallery, microphone and notifications once (`permsAsked`).
- Expo Go (Android) skips `expo-notifications` entirely (it errors on import there); in-app banner/inbox still work.

## 2. Coach-mark tour (`src/components/CoachTour.tsx`)

- Spotlight overlay on the **real** app: measures the live tab-bar buttons (`measureInWindow`, corrected for
  the overlay's own origin), dims everything else, pulses a ring on the target, and shows a card
  (title, body, progress bar, Back / Next / Skip / Get started).
- Steps: Home, Field Data, Advice, Scan, Me. The tour switches the visible tab per step and plays the
  existing narrated clip (`assets/audio/tour_*`); the Me step has no clip.
- Starts when `tourSeen` is unset **and** the farmer has at least one field (the tab bar does not exist
  before the first field is added). Completion/skip stores `tourSeen=true` (device-local, AsyncStorage).
- Strings: `tourBack`, `tourBody_tour_me`, plus existing `tour*` keys, in en/kn/te/hi.
  New kn/te/hi strings need a native-speaker review before public release.
- The old full-screen `TourScreen` is still exported from `Onboarding.tsx` but unused.

## 3. Notification system (`src/notifications.tsx`)

Single entry point `useNotifications().notify({id?, title, body, severity?})`:

| App state | What the user sees |
|-----------|--------------------|
| Foreground | Themed in-app banner (logo, severity-coloured edge, 5 s, tap opens inbox). The OS banner is suppressed by `setNotificationHandler`. |
| Background | Real system notification via `expo-notifications` on the `alerts` Android channel (green light colour, high importance). |
| Always | Saved to a persistent inbox (last 50, AsyncStorage `inbox`); bell + unread badge in the header opens the inbox sheet. |

- De-duplication: the same `id` never notifies twice.
- Alert source today: `RootInner` polls `getAdvisories(field.id)` on entering the main app and every 15 min;
  advisories with severity `high`/`severe` created in the last 48 h become notifications (max 3 per check).
- `app.json`: `expo-notifications` plugin (icon `assets/notification-icon.png`, colour `#2E7D32`) and
  `POST_NOTIFICATIONS` permission (Android 13+).
- Strings: `permNotif*`, `notif*` in all four languages.

## 4. Open items (not built)

1. **Remote push (app fully closed).** Needs: (a) a dev/release build — Expo Go cannot receive remote push on
   Android; (b) a Firebase project + FCM credentials uploaded via EAS (human step, needs the owner's
   account); (c) backend: a `push_tokens` table behind the repository interface, `POST /v2/devices`
   (additive contract in `specs/`), and a sender triggered when a high/severe advisory is generated.
   The client already routes any push received in the foreground through `notify()`.
2. Device verification of the tour cut-out alignment, splash hand-off and notification channel.
3. Native-speaker review of new kn/te/hi strings.
