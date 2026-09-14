# MODULE 28 — Fix the mobile app: fake disease-scan fallback, broken language switching, then UI cleanup

Continuing AGRO MIRAI's mobile app (`mobile/`, Expo/React Native). This
follows real Metro logs from a live device session showing the disease
scanner is not actually working — read this whole prompt before touching
anything, it's sequenced: fix the two functional bugs and prove they're
fixed with real evidence first, only then touch UI.

## The evidence (from a real `npx expo start` session, not a guess)

```
LOG  Posting image to http://10.105.30.242:5000/v2/fields/f1/disease-risk/image
LOG  Image upload exception, using local AI model result: Unsupported FormDataPart implementation
```

Every disease-scan result the app has shown is fabricated. The app is
catching a real upload exception and silently substituting a canned/local
"AI model result" instead of surfacing the failure — this is the same
never-show-a-failure-fake-success-instead pattern the backend audit found
in `value_endpoints.py`. It has to go, in both places.

Also reported directly: switching the language pill (EN/ಕನ್ನಡ/etc.) does
not change any visible text in the app.

## Bug 1 — Disease image upload is broken, and the fallback lies about it

1. Find the exact upload call (grep for `"Image upload exception"` and
   `"using local AI model result"` — read the full surrounding function,
   probably in a disease-scan screen or a shared API client file).
2. Root-cause the actual `FormData` bug. "Unsupported FormDataPart
   implementation" is the classic RN symptom of appending a web-style
   `File`/`Blob` object to `FormData` instead of React Native's required
   shape: `formData.append('image', { uri: asset.uri, name: 'photo.jpg',
   type: 'image/jpeg' })`. Check whatever `expo-image-picker` /
   `expo-camera` result object is being appended today and fix the append
   call to use the RN shape. Don't guess — read the actual object shape
   `ImagePicker`/`Camera` returns in this Expo SDK version and confirm
   against Expo's own docs before changing the append call.
3. **Delete the "local AI model result" fallback entirely, or replace it
   with an honest one.** Silently faking a disease diagnosis is not
   acceptable — a farmer could act on a fabricated "severe" or a
   fabricated "low risk" result. On a genuine upload/network failure, the
   app must show a real error state ("couldn't reach the server, try
   again" / "check your connection") — never a substitute prediction
   presented as if it came from the model. If there's a legitimate
   on-device fallback model planned for true offline use, it must be
   clearly labeled in the UI as on-device/offline, not indistinguishable
   from a server result — but confirm with me before building that; for
   now, an honest failure state is the fix.
4. Also grep the whole `mobile/` tree for any other `catch` block that
   substitutes fabricated/hardcoded data instead of surfacing an error —
   the audit already found one such pattern in the backend; check the app
   doesn't have others (e.g. hardcoded advisory text, hardcoded field
   data) hiding behind a similar "except: use fallback" line.
5. **Prove the fix with real evidence, not a claim**: run the app on a
   real device again, take a real photo, upload it, and paste the actual
   Metro log output showing a successful `POST .../disease-risk/image`
   with a real 200 response body (or, separately, a genuine, clearly
   different error state if you force a network failure) — screenshot or
   log text, not a description of what should happen.

## Bug 2 — Language switching does nothing

1. Find the language-picker component and trace exactly what it does on
   tap: does it update a state variable / AsyncStorage key? Does it call
   `PATCH /v2/farmers/me` with `preferred_language`? Does any screen
   actually read that state to choose which string table to render, or
   is all UI copy hardcoded in English regardless of the stored value?
2. Report which of these is broken — it's likely one of: (a) no i18n
   string table exists at all and every screen has English hardcoded
   inline, in which case this is a real feature gap, not a bug, and
   needs to be built; or (b) a string table exists but the picker's
   selection isn't propagated to whatever hook/context reads it (missing
   re-render, stale closure, or written to the wrong storage key than
   what's read at render time).
3. If (a): build a minimal real i18n layer (a `strings.ts`/locale-JSON
   approach, `en`/`kn`/`te`/`hi` per the backend's `V1_LANGUAGES`) and
   wire every static UI string currently hardcoded through it — this
   touches every screen, so do it once, correctly, not screen-by-screen
   later.
4. If (b): fix the propagation bug and confirm state actually flows:
   picker tap → stored → context/hook updates → screens re-render with
   new strings.
5. Confirm server-driven text (advisory bodies, `Explanation.summary_en`/
   voice audio) also genuinely uses the selected/farmer's
   `preferred_language` on every relevant request — not just the static
   UI chrome.
6. Prove it: real device, switch language, screenshot before/after
   showing actual visible text change on at least two screens (Home and
   one detail screen), not just the language pill itself changing.

## Then — UI cleanup, once Bugs 1 and 2 are proven fixed

Everything below is real feedback from real screenshots of the current
app, not invented — go through each one:

1. **Cut redundant navigation.** Home's Field Actions grid currently
   duplicates the bottom tab bar (a "History" card in the grid *and* a
   History tab; Irrigation/Disease/Crop Health cards that overlap with
   the Advisories tab). Pick one hierarchy: Home = today's single most
   urgent advisory (keep this, it's good) + a max-3-icon row for direct
   model access (Irrigation / Disease / Crop Health, each with its
   existing severity dot). Drop the redundant History card from the grid
   — it's already a tab.
2. **Kill every model/architecture string from user-facing copy.**
   "Embedded ChatGPT-Style AI Scanner," "Seamless ChatGPT-Style Viewfinder
   Sheet," "Real-time 38-class MobileNetV2 PyTorch Disease Detection" —
   grep the whole `mobile/` tree for "ChatGPT", "MobileNet", "PyTorch",
   "38-class", and any other implementation-detail string, and replace
   each with plain farmer-facing language (e.g. "Scan a Leaf" / "Point
   your camera at the affected leaf"). This is copy-only, low risk, do it
   everywhere in one pass.
3. **Turn the static-fact modals into something useful or remove them.**
   "Crop Health Summary" (Crop Type / Field Area / Growth Phase) and
   "Irrigation Advisory Details" (Recommended Depth / Soil Moisture /
   Weather Forecast) currently just restate three facts with no action
   and no trend. Either inline this content directly in the card (no
   modal needed for 3 static facts) or add real value to justify a modal
   tap — e.g. Irrigation Details showing depth-over-time or a simple
   before/after soil-moisture comparison, sourced from real data the
   backend already returns, not fabricated.
4. **Remove dev/debug UI leakage.** The `[expo-image-picker]
   ImagePicker.MediaTypeOptions deprecated` warning toast is visible in
   the live camera view — that's a console warning rendering as an
   in-app toast/banner. Fix the underlying deprecation (migrate off
   `MediaTypeOptions` to `MediaType` per Expo's current API, which you're
   already touching in Bug 1) so the warning disappears, and confirm no
   other console warnings are rendering as user-visible UI anywhere else
   in the app (grep for whatever toast/banner component is picking up
   console output, if any — if one exists, it should never surface raw
   library warnings to farmers).
5. Do **not** re-theme colors/fonts/spacing wholesale in this pass — the
   Field & Grain palette and typography are fine as specified; this is
   about information hierarchy and copy, not a visual redesign.

## Definition of done

- [ ] Root cause of "Unsupported FormDataPart implementation" identified
      and fixed, with the actual object-shape bug named
- [ ] Fake "local AI model result" fallback removed; failures now show an
      honest error state
- [ ] Whole `mobile/` tree grepped for other silent-fallback-fakes-success
      patterns; any found are listed and fixed
- [ ] Real device proof: successful image upload + real model response
      logged/screenshotted
- [ ] Language-switch root cause identified (missing i18n vs. broken
      propagation) and fixed
- [ ] Real device proof: visible text changes on 2+ screens after a
      language switch
- [ ] Server-driven advisory/voice content confirmed to use the selected
      language on real requests, not just static UI chrome
- [ ] Home grid redundancy removed (no duplicate History entry point)
- [ ] All model/architecture-name strings removed from user-facing copy
- [ ] Static-fact modals either inlined or given real added value
- [ ] Deprecated `MediaTypeOptions` warning fixed, no console warnings
      rendering as in-app UI anywhere

## Handoff format

```
Module: 28 — Fix fake disease-scan fallback, broken language switching, UI cleanup
Status: complete | blocked | needs-decision
Bug 1 root cause: <exact object-shape issue found>
Bug 1 fix: <what changed, files>
Bug 1 proof: <real log/screenshot of a genuine successful upload>
Other silent-fallback patterns found in mobile/: <list, or "none found — confirmed via grep for X">
Bug 2 root cause: <missing i18n vs. broken propagation, which>
Bug 2 fix: <what changed, files>
Bug 2 proof: <real screenshots, before/after, which screens>
UI changes made: <list>
Known limitations:
Next recommended step:
```
