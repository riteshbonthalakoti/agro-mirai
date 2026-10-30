# Android Push Notifications — one-time setup

Everything code-side is already built and shipping in v2.8.15: token
registration, the backend sender, the immediate disease-scan push, and a
3-hourly background sweep for irrigation alerts. What's **not** done yet,
because it needs your own Google account and can't be automated, is
connecting this app to a real Firebase project so Google's push service
(FCM) will actually deliver anything. Two steps, ~10 minutes total, free.

## Step 1 — Create the Firebase project and get `google-services.json`

1. Go to https://console.firebase.google.com and sign in with your own
   Google account.
2. **Add project** → any name (e.g. "Agro Mirai") → you can skip Google
   Analytics → **Create project**.
3. On the project's home page, click the **Android icon** to add an Android
   app.
4. **Android package name**: enter exactly `com.ritesh1918.mobile` (must
   match `mobile/app.json`'s `android.package` exactly, or push silently
   won't work).
5. Nickname/SHA-1 are optional — skip them, **Register app**.
6. Download the `google-services.json` file it offers you.
7. Put that file at **`mobile/google-services.json`** in this repo (same
   folder as `app.json`). The build already looks for it there and wires
   it in automatically — nothing else to configure on this side.

## Step 2 — Give Expo's push service your Firebase credentials

This is the part that's easy to miss: `google-services.json` lets the
*app* talk to Firebase, but the *backend* sends pushes through Expo's
relay (`exp.host`), which needs its own permission to deliver to your
Firebase project on your behalf.

1. In the Firebase console, go to **Project settings** (gear icon) →
   **Service accounts** tab.
2. Click **Generate new private key** → confirm → it downloads a JSON file.
3. Go to https://expo.dev, open this project (agro-mirai, under your
   `ritesh.bonthalakoti` account — same one `app.json`'s `extra.eas.projectId`
   points at).
4. **Project settings** → **Credentials** → Android → **FCM V1 service
   account key** → upload the JSON file from step 2.

That's it. No code changes, no new build needed for this part —
Expo's push relay starts working for any device that already registered
a token (which happens automatically on sign-in, in `mobile/src/push.ts`)
the moment this is uploaded.

## Verifying it worked

1. Rebuild and install the app (needed once, so the `google-services.json`
   plugin actually takes effect — `./gradlew assembleRelease` from
   `mobile/android`).
2. Sign in on a phone. Check `Me tab → Report a bug` after a moment — if
   token registration failed for any reason, it'll show up there
   (`push.registerForPushNotifications` logs failures, same as the OTP
   diagnostic logging added this session).
3. Scan a leaf that comes back high/severe risk — a push should land
   within a few seconds, including on a *second* signed-in device if you
   have one (that's the real test: local notifications never could do that).
4. For the irrigation sweep, you don't have to wait 3 hours — trigger it
   manually from the repo's GitHub Actions tab: **Actions → Push
   Notification Sweep → Run workflow**.

## What this does NOT cover

- **iOS**: push notifications are Android-only in this codebase (see
  `docs/PROJECT_QA.md`'s notification-pipeline section) — this setup only
  applies to Android/FCM.
- **Cost**: both FCM and Expo's push relay are free at this project's scale,
  no billing account or card needed for anything in this doc.
