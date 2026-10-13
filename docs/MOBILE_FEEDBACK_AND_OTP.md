# Mobile: notifications, haptics/sounds, OTP auto-fill

Date: 2026-09-25. Scope: `mobile/` (Expo SDK 57). Extends `MOBILE_ONBOARDING_NOTIFICATIONS.md`.

## Notifications (real Android notifications)
- Every alert from `notify()` is a real system notification (heads-up banner, sound, vibration, notification
  shade), also while the app is open (`setNotificationHandler` now shows the banner). The inbox (bell) keeps
  the history. In Expo Go the OS layer is unavailable, so the in-app banner is used there.
- `setDailyReminder(title, body)` schedules a daily 07:00 notification (OS alarm, delivered when the app is
  closed). Home refreshes its text with the latest "Today" line whenever the advice changes. It only
  schedules if notification permission is granted.
- Permissions are asked once at start. Found on a real phone: an already-signed-in install had
  `POST_NOTIFICATIONS: granted=false` because that screen only ran for fresh installs. Boot now shows the
  permission screen once (`permsV2` flag) for existing users too.
- Me > "Sounds & vibration" has a switch and a "Send a test notification" button.
- Not built (needs the owner): server push while the app is closed and personalised on the server. Needs
  Firebase Cloud Messaging (free) + an Expo/EAS project, a `push_tokens` table behind the repository
  interface, `POST /v2/devices`, and a sender when a high/severe advisory is created.

## Haptics and sounds (`src/feedback.ts`)
- Buttons, chips, tabs: light haptic, no sound. Success / warning / error / camera shutter / clearing
  notifications / new alert (Expo Go): haptic + a short sound. Clearing the inbox also dismisses the Android
  notification shade (`dismissAllNotificationsAsync`) and vibrates.
- Sounds are synthesised by a script (`mobile/assets/sounds/*.wav`, original, no third-party audio).
- One preference (`feedbackOn`) turns everything off. Calls never throw.

## OTP auto-fill (not possible yet, by design)
- Do NOT request READ_SMS or notification-listener access: Google Play restricts SMS permissions to a few app
  types and "read all notifications" is a privacy red flag for farmers.
- The sanctioned way (used by Jio/banks) is Google's SMS Retriever / SMS User Consent API: no permission,
  but it needs a real SMS in a specific format (`<#> Your Agro Mirai code is 123456 <11-char app hash>`).
- Today OTPs are only logged on the server (`OTP_DELIVERY=log`, owner decision: no paid SMS provider), so
  nothing is sent and nothing can be captured. `autoComplete="sms-otp"` is already set on the code box so
  Android keyboards offer the code once a real SMS exists.
- When an SMS provider is added: send the Retriever-format SMS from `auth/otp.py::send_otp`, compute the app
  hash from the signing key, add a small native module (or `react-native-otp-verify`) that listens for the
  message and fills the box, and test on a real device with a real SMS.
