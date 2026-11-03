# ADR 0032 — Pin `runtimeVersion` to an explicit string, not `fingerprint`

**Status:** accepted
**Date:** 2026-11-03

## Context

`runtimeVersion` is how `expo-updates` decides which OTA update a given
installed build is allowed to receive — an update only reaches a device
whose running binary's `runtimeVersion` matches the one the update was
published under. Since the project's introduction of EAS Update, this
was set to `{ policy: 'fingerprint' }`: a hash computed from the native-
relevant parts of the project (dependencies, native config, plugins),
chosen deliberately over the simpler `appVersion` policy specifically to
avoid a different failure mode — an OTA update silently reaching a build
with an incompatible native module set because someone forgot to bump
`version` after a native change.

In practice, `fingerprint` turned out to have a worse failure mode of its
own: **the hash isn't reproducible outside the exact machine and exact
moment a given APK was built.** This was discovered twice, independently,
while diagnosing why published OTA updates weren't reaching the shipped
v2.8.16 and then v2.8.17 APKs:

- The real fingerprint baked into a shipped APK (readable from its own
  `assets/fingerprint` file) never matched the fingerprint computed by
  `eas update` or `npx expo-updates fingerprint:generate` run from this
  checkout — not even when pinned to the *exact git commit* the APK was
  built from, with a clean `npm ci`. Something outside git state (local
  `node_modules` resolution, an environment value, a timestamp-sensitive
  input) drifts the computed hash even when the source tree is byte-for-
  byte identical.
- This wasn't a one-off: confirmed again on v2.8.17 with the same
  pinned-commit test, same result — a different hash than what the real
  APK shipped with.

The practical effect: **every OTA update published this way has had a
real chance of silently never reaching the installed app**, with no error
or warning anywhere in the publish flow — `eas update` reports success
regardless. That's strictly worse than the risk `fingerprint` was chosen
to avoid; a forgotten version bump is at least visible and fixable, while
a fingerprint mismatch fails completely silently.

## Decision

Switch `runtimeVersion` to an explicit, manually-set string:

```js
runtimeVersion: '1.0.0',
```

This never changes on its own — it changes only when a developer bumps it
by hand, and only needs to change when something genuinely native-facing
changes: a new native module, a permission, a native config plugin
edit, or an Expo SDK upgrade that touches the native layer. A pure JS/TS
change (screens, components, business logic, API client code, prompts,
styling) never needs a bump, and will always reach every installed build
still on `'1.0.0'` via a normal `eas update` publish — reliably, every
time, with no fingerprint guesswork.

This reintroduces the exact discipline requirement `fingerprint` was
chosen to avoid: remembering to bump `runtimeVersion` after a real native
change. That's the accepted tradeoff — a visible, documented manual step
beats an invisible, unreproducible one. Any PR touching `mobile/android`,
`mobile/ios`, native modules, or Expo config plugins must bump this
string as part of that same change; this is the enforcement mechanism
until/unless it's worth a CI check.

## Consequence

v2.8.18 is the first release built under this policy and establishes the
`'1.0.0'` baseline — this one release still requires a real APK
rebuild/reinstall (there is no way around that; nothing built before
this ADR has a runtime version this policy can match). Every OTA-eligible
change after v2.8.18 ships instantly via `eas update --branch production`
with no rebuild, as long as it doesn't touch anything native.
