# Module 53: Dynamic Per-Account Notifications

## Features
1. **Clear on sign-out**: Scheduled notifications cancelled when user signs out
2. **Reschedule on sign-in/switch**: Notifications rescheduled with new account's field/language
3. **Per-account settings**: Reminder on/off + time stored per-account (auto-default: on @ 7 AM)
4. **Tap-to-route**: Notification tap checks if account still exists, switches to it, navigates home

## Implementation
- `App.tsx`: Listens to account lifecycle events, reschedules/routes on sign-in/switch/tap
- `NotificationsProvider`: Clears on sign-out, accepts accountId in daily reminder payload
- `reminderSettings.ts`: Per-account storage helpers (uses existing account-namespaced storage)
- `notificationScheduling.ts/test.ts`: Pure logic for "should schedule" decision (existing)
- `backgroundAlerts.ts`: No-op when signed out (existing)

## Tests
- `notificationScheduling.test.ts`: 6 tests covering account/field/advice conditions
