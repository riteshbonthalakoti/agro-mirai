# Multi-account switching (Module 52)

A farmer can save up to 5 accounts on one phone and switch between them
without an OTP each time.

## Auth

The backend had only a session cookie, which can't be held per-account in
one shared cookie jar. `verify-otp` now also returns a signed bearer
token (`session_auth.issue_session`), and `require_session_auth` accepts
either the cookie or an `Authorization: Bearer` header. The cookie stays
24h; the bearer token lives 180 days (env `BEARER_TOKEN_LIFETIME_DAYS`),
since a saved account should stay signed in until the farmer removes it,
not re-ask for an OTP once a day.

## Mobile storage

- `accounts.ts`: the saved-account list and active pointer (AsyncStorage),
  one token per account (`expo-secure-store`).
- `storage.ts`: cache keys are prefixed with the active account's id, so
  one account never sees another's cached data. Device prefs (language,
  permissions, tour) stay unprefixed, shared across accounts.
- `api.ts`: every request attaches the active account's token. A 401 is
  tagged with the account id it was sent under, so a stale request from
  an account you've since switched away from can't log out the new one.

## Known limits

- OS permission dialogs aren't themed (platform-drawn).
- A bearer token has no server-side revoke list -- logout clears the
  cookie session, but a captured token stays valid until it expires on
  its own.
- A farmer signed in before this shipped keeps working on the plain
  cookie until their next sign-in.
