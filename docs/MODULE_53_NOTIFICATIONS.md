# Module 53: Dynamic Per-Account Notifications

## Bug Fixed
User logged out but the 7 AM notification still arrived. Notifications were never cancelled on session end.

## Root Cause
`App.tsx` sign-out paths didn't cancel OS-scheduled notifications; the reminder persisted and fired after logout.

## Solution
- Account lifecycle events (`accountSignedIn`, `accountSignedOut`) emitted from App.tsx
- NotificationsProvider subscribes to sign-out, clears all scheduled notifications
- Background task checks cached farmer exists before processing (no unauth alerts)
- Notification data includes fieldId for future field routing
- Pure scheduling decision function: tests verify "no account" / "no field" → no schedule

## Files
- `mobile/src/accountEvents.ts` — event emitter (compatible with Module 52)
- `mobile/src/notificationScheduling.ts` — pure scheduling decision logic
- `mobile/src/notificationScheduling.test.ts` — unit tests
- `mobile/App.tsx` — emit events on sign-in/sign-out
- `mobile/src/notifications.tsx` — listen to account sign-out
- `mobile/src/backgroundAlerts.ts` — check farmer cached before processing

## Known Limitations
- No per-account settings storage yet (future)
- Notification tap doesn't route to field (data present, routing deferred)
- When Module 52 merges: accountEvents.ts will be identical, no code changes needed
