# Module 53: Dynamic Per-Account Notifications

## Features
1. **Clear on sign-out**: Scheduled notifications cancelled when user signs out
2. **Reschedule on sign-in/switch**: Notifications rescheduled; respects per-account settings (enabled/disabled, time)
3. **Per-account settings**: Reminder on/off + time stored per-account (auto-default: on @ 7 AM)
4. **Tap-to-route**: Notification tap checks if account still exists, switches to it, navigates home

## Implementation
- `App.tsx`: Listens to account lifecycle events, reschedules/routes on sign-in/switch/tap
- `NotificationsProvider`: Clears on sign-out, accepts accountId in daily reminder payload
- `reminderSettings.ts`: Per-account storage helpers (uses existing account-namespaced storage)
- `notificationScheduling.ts/test.ts`: Pure logic for "should schedule" decision (existing)
- `backgroundAlerts.ts`: No-op when signed out (existing)

## UI Presentation & Drawer
- **Bell Micro-animation**: Tapping the notification bell in the mobile top navigation triggers a smooth ±15-degree chime swing animation.
- **Slide-up Notification Sheet**: Replaced full-page modal/backdrop with a modern bottom drawer (`NotificationDrawer.tsx`) featuring gesture drag, unread badges, and direct navigation to alerts.

## Tests
- `notificationScheduling.test.ts`: 9 tests covering account/field/advice/settings conditions
- New: disabled reminders, multi-account switching with different settings

