# Module 53: Dynamic, Account-Aware Notifications

## Bug Fixed
User logged out of the app but the 7 AM notification still arrived daily. The notification was static — scheduled once locally, never tied to the logged-in account state.

## Root Cause
1. `HomeTab` called `setDailyReminder()` when loading fresh field advice, which scheduled an OS-level notification with identifier `DAILY_ID` ('daily-advice') for 7 AM daily.
2. When user signed out, `App.tsx`'s `signOut()` only called the logout API — it never cancelled the scheduled OS notification.
3. The notification persisted in the OS and fired the next morning, even though no user was logged in.

## Design
**Local reschedule on account events** — simplest correct approach:
- Cancel all OS-level scheduled notifications on logout/session-end
- Clear background field tracking cache on logout
- Reschedule daily reminder only when user is logged in and HomeTab loads fresh advice
- Include field ID in notification data so tapping opens the right field

Why this design:
- Avoids new server-side notification infrastructure
- Leverages existing Expo local scheduling
- Works offline (scheduling happens locally)
- Faster (no network round-trip)
- Per-field isolation prevents cross-field notification leaks

## Changes Made

### Mobile App (`mobile/`)

#### `src/notifications.tsx`
- Added `clearScheduledNotifications()` to NotifCtx type and implementation
- Cancels `DAILY_ID` + all scheduled notifications via `cancelAllScheduledNotificationsAsync()`
- Made `setDailyReminder()` accept optional `fieldId` parameter to include in notification data

#### `src/screens/HomeTab.tsx`
- Updated `setDailyReminder()` call to pass current field ID
- Added `id` to useEffect dependencies so rescheduling happens on field switch

#### `App.tsx`
- Imported `clearScheduledNotifications` from notifications hook
- Updated `goAuth()` (session-end path) to call `clearScheduledNotifications()` and `setBackgroundField(undefined, undefined)` before clearing farmer cache
- Updated `signOut()` (explicit logout path) to call both cleanup functions before logout API call
- Added `clearScheduledNotifications` to dependency arrays

### Backend (`src/`)
No changes needed. The logout endpoint (`POST /v2/auth/logout`) already clears the session cookie; no notification tracking exists server-side.

## Testing

### Manual Verification
1. **Build + deploy APK** to test device/emulator
2. **Login** as a farmer with a field
3. **Go to Home tab** — confirms daily reminder is scheduled for 7 AM
4. **Sign out** via the "Sign out" button in Me tab
5. **Wait or fast-forward device clock to 7 AM** — notification should NOT appear
6. **Re-login** — daily reminder should reschedule

### Offline Scenario
1. Login, go offline
2. Home tab still shows advice (cached)
3. Daily reminder still schedules (local device)
4. Sign out while offline
5. Go back online
6. Notification should NOT appear (was cancelled before going offline)

### Field Switch
1. Login with multiple fields
2. Switch to Field A — reminder scheduled with fieldId=A
3. Switch to Field B — reminder updated with fieldId=B
4. Tap notification in future — opens Field B (contains fieldId in data)

## Known Limitations
1. **No per-account notification settings yet** — defaults to 7 AM daily, cannot customize via UI (future Module 54)
2. **No server-side push notifications** — only local scheduling; features like "send to all accounts at once" require backend infrastructure (future)
3. **Background task still uses cached field** — the WorkManager background task still reads the last-seen field from cache; if user switches accounts between app foreground and background wake, advisory fetches may target the old account's field. Fix: track account ID alongside field in background cache (future Module 55)
4. **No notification routing on tap** — tapping notification opens Home tab, doesn't auto-select the field from notification data yet (future)

## Files Modified
- `mobile/src/notifications.tsx` — +14 lines
- `mobile/src/screens/HomeTab.tsx` — +3 lines (add field ID to reminder call + dependency)
- `mobile/App.tsx` — +8 lines (cleanup on logout/session-end)

## Proof of Fix
The fix is verified by code inspection:
- `clearScheduledNotifications()` is always called before `goAuth()` or returning to auth screen
- Notification cancellation targets the OS's identifier system, guaranteed by Expo's API
- fieldId is now part of notification data, allowing future routing logic
- Background field is cleared alongside session data

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>
