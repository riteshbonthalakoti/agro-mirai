import * as Updates from 'expo-updates';

export type AppUpdateInfo = {
  /** When this update was published, straight from its manifest -- the
   *  honest detail we actually have at runtime (there's no changelog-text
   *  mechanism wired up yet), shown in the update dialog so it's not just
   *  a bare "an update exists" with nothing to back it up. */
  publishedAt: Date | null;
};

/** Non-blocking OTA update check -- called once on app launch. Never throws
 *  into the caller: a failed check (offline, EAS unreachable, or running in
 *  Expo Go / a dev-client session where custom update servers aren't
 *  supported) is exactly as unremarkable as "no update available" -- the
 *  app just keeps running on its current bundle, matching this project's
 *  degrade-never-fail doctrine.
 *
 *  Resolves with update info once a new update has actually finished
 *  downloading and is ready to apply (null if there's nothing new) -- the
 *  caller (App.tsx) shows a dialog so the farmer can choose *when* to
 *  restart (mid-form, mid-advisory-read is a bad moment to yank the screen
 *  out from under them), rather than it silently applying on some future
 *  cold start they never notice. Applying it is a separate call:
 *  applyDownloadedUpdate(). */
export async function checkForAppUpdate(): Promise<AppUpdateInfo | null> {
  if (!Updates.isEnabled) return null; // Expo Go / dev-client / no update server configured
  try {
    const result = await Updates.checkForUpdateAsync();
    if (!result.isAvailable) return null;
    const fetched = await Updates.fetchUpdateAsync();
    const createdAt = (fetched.manifest as { createdAt?: string } | undefined)?.createdAt;
    return { publishedAt: createdAt ? new Date(createdAt) : null };
  } catch {
    return null; // Silent by design -- see doc comment above.
  }
}

/** Reloads the app on the update already fetched by checkForAppUpdate(). */
export async function applyDownloadedUpdate(): Promise<void> {
  await Updates.reloadAsync();
}
