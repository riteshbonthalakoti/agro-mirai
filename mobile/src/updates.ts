import * as Updates from 'expo-updates';

/** Non-blocking OTA update check -- called once on app launch. Never throws
 *  into the caller: a failed check (offline, EAS unreachable, or running in
 *  Expo Go / a dev-client session where custom update servers aren't
 *  supported) is exactly as unremarkable as "no update available" -- the
 *  app just keeps running on its current bundle, matching this project's
 *  degrade-never-fail doctrine.
 *
 *  Returns true once a new update has actually finished downloading and is
 *  ready to apply -- the caller (App.tsx) shows a dismissable "Update
 *  available" banner so the farmer can choose *when* to restart (mid-form,
 *  mid-advisory-read is a bad moment to yank the screen out from under
 *  them), rather than it silently applying on some future cold start they
 *  never notice. Applying it is a separate call: applyDownloadedUpdate(). */
export async function checkForAppUpdate(): Promise<boolean> {
  if (!Updates.isEnabled) return false; // Expo Go / dev-client / no update server configured
  try {
    const result = await Updates.checkForUpdateAsync();
    if (!result.isAvailable) return false;
    await Updates.fetchUpdateAsync();
    return true;
  } catch {
    return false; // Silent by design -- see doc comment above.
  }
}

/** Reloads the app on the update already fetched by checkForAppUpdate(). */
export async function applyDownloadedUpdate(): Promise<void> {
  await Updates.reloadAsync();
}
