# AGRO MIRAI Mobile App: Farmer UX Research & Recommendations
**Module 43: Usability and Adoption Optimization**

**Date:** 2026-09-24  
**Audience:** VTU Capstone Team (BITM Dept. of AIML)  
**Target Users:** Small/marginal farmers in Karnataka/Andhra Pradesh/Telangana/Maharashtra, low-to-moderate digital literacy, Android devices (mid-range, older), patchy 3G/4G, 5-10 mm vision distance on screen, gloved/dirty hands, one-handed use in field, ~10 seconds daily attention budget.

---

## Executive Summary: Top 10 Recommendations

1. **One-tap morning check** (Home tab): Show a single, high-contrast action card above the fold—"Irrigation today: 25 mm by 3pm"—with a status badge (green/amber/red). Reduce cognitive load; farmers check the app for a decision, not to read three cards.

2. **Voice-first field data entry** (FieldForm): Replace mandatory text fields with optional ones. Add a "Record by voice" button (Kannada/Telugu/Hindi recognized, auto-filled; no typing required). GPS auto-fills on tap; soil type as 6 common local-language pictures (red soil, black soil, sandy, clay, loam, mixed).

3. **Offline advisory history** (AdviceTab): Cache last 30 advisories + their audio locally. When offline, show cached advisories with a timestamp badge "Last synced: 2 hours ago"; tap to refresh when online.

4. **Leaf scan quality gates** (ScanTab): Before upload, show live guidance: "Good lighting!" / "Too blurry—try again" / "Whole leaf + close-up needed" (SHAP-driven feedback from the CNN). Reject < 1MB or clearly blurred images client-side; never send garbage to backend.

5. **Confidence + local explanation** (HomeTab cards): Add a small confidence % below each card title (e.g., "72% confident"). On tap, show a plain-language "Why?" in the farmer's language (not just SHAP). For out-of-region crops, show a caveat banner + the regional alternative in green text.

6. **Cold-start messaging** (Boot sequence): While server wakes (first 5 sec), show a reassuring splash with rotating tips ("We're waking the server…" / "Checking weather…" / "Preparing your field advice…"). Never let a blank screen run > 5 sec.

7. **Notification cadence + opt-out** (Home): Daily "action" notifications 7am only (one per field, e.g., "Cotton field: irrigation due"). Weekly "progress" digest Sundays 6pm (summary of week's advisories). Add in-app settings to snooze 3 days or disable by type.

8. **Progressive field setup** (FieldForm): Minimize required fields to 3: name, location (GPS auto-tap), area. Soil type and crop are optional; skip them to see home tab immediately, fill them later from Data tab. Show a progress bar: "2/5 fields ready for best advice."

9. **Touch targets + text size defaults** (All screens): Minimum 48dp buttons/taps. Default body text 15sp (not 13sp). Test on Xiaomi Redmi 5A, Galaxy A12 (< 300 ppi). Allow device-level text scaling up to 150%; audit contrast (4.5:1 normal, 3:1 large).

10. **Feedback loop closure** (AdviceTab): After a farmer rates an advisory (1–5 stars), show a 1-second confirmation ("Feedback saved. This helps us learn.") and log it server-side. Monthly in-app digest: "Your ratings improved our crop model by 2.3%." Build trust via visible feedback impact.

---

## 1. Daily-Use Loop: The 10-Second Morning Check

### Current State
HomeTab shows three cards (crop recommendation, irrigation, disease risk) stacked, all requiring scrolling. A farmer opening the app sees three model outputs competing for attention; unclear which is most urgent.

### Research Finding
**Citation:** [How to Measure Mobile App Performance: Top 18 Metrics 2026](https://uxcam.com/blog/how-to-measure-mobile-app-performance/) — Perceived performance matters more than technical speed. A farmer with 10 seconds has no time for ambiguity.

**Citation:** [Re-designing Kisan Suvidha App — to build a sense of ...](https://medium.com/@ashwin_bhawsar/re-designing-kisan-suvidha-android-application-6a4325b76149) — Kisan Suvidha redesign focused on reducing decision points and showing one actionable item first.

### Recommendation
**Restructure HomeTab as a priority-ranked stack:**
- **Card 0 (Immediate action):** If irrigation urgency is "high" or "severe," or if disease risk is "high"/"severe," show that single card at the top with:
  - Large title: "Irrigation due: 25 mm" or "Disease risk: High" (color-coded: green=low, amber=moderate, red=high, dark red=severe)
  - One recommended action (e.g., "Irrigate by 3pm" or "Scout field + apply fungicide")
  - Tap → expands to full card with rationale
  - No scroll needed; farmer gets a decision in 3 seconds
- **Card 1 (Secondary):** Crop recommendation (only if changed from last week or if confidence < 60%)
- **Card 2 (Routine):** Non-urgent irrigation, disease risk if low/moderate
- **Pull-to-refresh** engages all three models, but HomeTab first shows the urgent one

**Rationale:** Farmers check the app to answer one question: "What do I do today?" A hierarchy that surfaces the highest-stakes decision first reduces cognitive friction and creates a habit loop.

### Notification Cadence & Re-engagement
**Research Finding:** [Enhancing User Engagement Through Effective Notifications in Farm Management Apps](https://abheist.com/blogs/user-engagement-through-notifications) — Balancing user value and business goals means selective, relevant notifications.

**Citation:** [Agriculture App UI Design: 7 Principles Farmers](https://medium.com/@sneh_sagar/agriculture-app-ui-design-7-field-tested-principles-that-drive-real-farmer-adoption-3fbbbbb24cea) — Notifications should answer "Why should I care?"

**Recommendation:**
- **Daily action notification** (7am only): One per field, only if irrigation or disease urgency >= "high", or new critical advisory. Text (in farmer's language): "[Field name]: [Action]. Tap to see details."  Example: "Cotton East: Irrigation by 3pm. Tap for window."
- **Weekly digest** (Sundays 6pm): If farmer has 2+ fields, send: "This week: 3 advisories, 1 disease alert. Tap to review." (Not a daily push storm; farmers will mute if noisy.)
- **In-app mute controls** (Me tab): "Pause notifications 3 days" (e.g., when traveling), "Turn off irrigation alerts" (e.g., monsoon season), "Daily digest only" (opt out of action alerts).
- **Feedback loop:** After farmer acts on an irrigation advice (likely ~2 days later), check if advisory window has closed. If so, send low-key 1-notification: "Irrigation from 3 days ago marked complete—good work." (Reinforces habit.)

### Implementation Notes
- Store `urgency` and `risk_level` at the HomeTab load time; sort by `max(urgency, risk_level)` to determine card order.
- Add a `last_action_notified_at` field to advisories to prevent re-notifying on the same advisory.
- Use Flask-Limiter (already in place) to cap notification calls to 1/field/day.

---

## 2. Friction Reduction: Onboarding, Field Creation, OTP Flow

### Current State
- **Auth:** Name + 10-digit phone → OTP → Farmer created. Works for basic flows.
- **Permissions screen:** Asks for location, camera, gallery, mic, notifications at once (5 toggles). Does not explain why or when each is needed.
- **FieldForm:** Requires name, area, latitude, longitude, sown_on. Soil type and crop are optional but presented as equally weighted form fields.
- **Location entry:** Manual text input for lat/lon; no GPS auto-tap option.

### Research Findings
**Citation:** [Mobile App Onboarding Best Practices [2026 Guide]](https://www.eleken.co/blog-posts/mobile-app-onboarding-best-practices) — "Progressive disclosure often reduces friction better than front-loaded setup." "Always include a skip option, as users who feel trapped by a mandatory step are more likely to abandon the flow entirely."

**Citation:** [Onboarding Patterns for Mobile Apps: Progressive Disclosure vs Front-Loaded Setup](https://www.digia.tech/post/onboarding-patterns-progressive-disclosure-vs-front-loaded-setup/) — "A minimum viable profile might include only phone number + OTP, with everything else being optional until the user finds value."

**Citation:** [The essential guide to mobile user onboarding: UI/UX patterns and best practices](https://www.appcues.com/blog/essential-guide-mobile-user-onboarding-ui-ux-patterns-and-best-practices) — "New user has no mental model of the product, no established usage patterns to anchor new information to, and very limited tolerance for friction before they decide the app is not worth the effort."

### Recommendation

#### A. OTP Flow Friction Reduction
1. **Auto-read SMS OTP:** On Android, use the SMS Retriever API (already supported by Expo; no extra library). When farmer receives SMS with code, the app auto-fills the 6-digit input. Farmer taps "Verify" instead of copying/pasting.
2. **Resend backoff:** After OTP sent, show a 60-second countdown ("Resend code in 58s"). At 60s, enable "Resend code" button. No re-taps within the window.
3. **Multiple attempts + clear error:** Allow 5 OTP attempts. On failure, message: "Wrong code. Try again. You have 3 attempts left. " (Not "Invalid input.") After 5, disable for 10 min and show: "Too many tries. We sent a new code to +91-XXXXX-6789. Check your SMS."
4. **Clear entry hint:** Placeholder text: "••••••" (6 dots), not empty. After first keypress, show a live indicator: "Code entry (1/6 digits entered)."

#### B. Permissions Screen (revised)
1. **Move to just-in-time:** Instead of all 5 at once during onboarding, ask for location when farmer first taps "Use my location" in FieldForm. Ask for camera when first tapping the ScanTab. Ask for notifications when first advisory is computed.
2. **If onboarding screen is kept for quick-start,** restructure:
   - Show only two at onboarding: Location (need this to fetch weather/soil) and Notifications (so we can alert you about irrigation).
   - Defer camera/gallery to ScanTab and microphone to voice input, on first use.
   - Allow "Allow all" button (stays) but also add "Only location" and "Only notifications" buttons to give choice.
3. **Explain before asking:** Above the "Allow" button, show a 1-line plain-language reason (not the legal permission text): "We use your location to get weather and soil data for your field."

#### C. Field Creation (FieldForm) – Progressive Disclosure
1. **Reorder fields as a funnel (required → optional → deferred):**
   ```
   [Required – must fill to proceed]
   - Field name (text input, placeholder: "Cotton East" or "Maize 1")
   - Location: "Use my location" button (tap → GPS popup, auto-fills lat/lon + district)
     OR "Enter manually" (link) → lat/lon text inputs
   - Area (text + dropdown: "hectares" / "acres" / "guntas", pre-selected by device language/region)

   [Optional – can fill now or later]
   - Soil type: "Choose..." dropdown → local-language names + pictures (6 tiles:
     red-soil, black-soil, sandy, clay, loam, mixed; picker shows soil-color pic +
     local name + Hindi/Kannada label)
   - Current crop: "Choose..." dropdown → 22 crop enum + local names (e.g.,
     "कपास (cotton)", "ಕೋಲೆ (cotton)")
   - Sown date: Date picker, default = today

   [Optional – saved to profile, auto-filled for future fields]
   - Default soil type (checkbox: "Remember this for my next field")
   ```

2. **Submit button logic:**
   - If all required fields filled → "Create field" button, green.
   - If required fields incomplete → "Create field" button, disabled + help text: "Need field name and location."
   - On submit with optional fields empty → Show a banner: "You can add soil type and crop later for better advice. Tap Data tab → Edit field." (Not blocking.)

3. **GPS auto-tap (UX flow):**
   - Show "Use my location" as a large button (48dp) with an icon (location pin).
   - Tap → shows a brief "Finding your location…" + spinner for 2–5 seconds.
   - On success, display: "District/region found: [Ballari, Karnataka]" + button "✓ Confirm" / "X Change".
   - On failure (no permission), show: "We need location access. Tap 'Allow' in the popup above." (Direct user to the OS permission prompt.)
   - Manual entry (optional): If GPS fails or farmer prefers, link "Enter lat/lon by hand" → two number inputs (lat, lon) with a small map preview (if available).

4. **Soil type picker (images + local names):**
   - Instead of a dropdown, show 6 equal-sized tap-able tiles (or a horizontal scroll if screen width < 360dp):
     - Each tile: color swatch (top half) + local-language name (Kannada/Telugu/Hindi auto-selected) + English name (small, gray)
     - On tap, tile gets a checkmark and a highlight border
   - Example Kannada labels for Karnataka: ಕೆಂಪು ಮಣ್ಣು (red soil), ಕಪ್ಪೆ ಮಣ್ಣು (black soil), ಮರಿ ಮಣ್ಣು (sandy), ಬಿಸು ಮಣ್ಣು (clay), etc.
   - Store the selection as an enum value; display the farmer's language label in the field list.

5. **Crop type picker (searchable, with local names):**
   - Dropdown (can also be a modal list if space tight) with 22 crops, searchable.
   - Each crop: English name + local-language name (e.g., "Cotton · ಕೋಲೆ").
   - Search: farmer types "cot" or "ಕೋಲೆ" → filters to Cotton + any other crop with that substring.
   - On select, show the local name prominently in the form summary.

### Implementation Checklist
- [ ] Backend: Verify `POST /v2/fields` accepts `{name, latitude, longitude, area_ha}` with optional `{soil_type, current_crop, sown_on}`.
- [ ] Mobile: Add SMS Retriever API call in AuthScreen's OTP entry.
- [ ] Mobile: Reorder FieldForm fields and add soil-type image picker (new UI component).
- [ ] Mobile: Add "Use my location" button with GPS error handling.
- [ ] Mobile: Add in-app help text ("You can add soil type later…").
- [ ] Mobile: Add optional-field persistence (remember last soil type choice for next field).
- [ ] Test with 5 farmers: measure time-to-first-field (target: < 2 min) and drop-off rates.

---

## 3. Low-Literacy and Multilingual Design

### Current State
- **Languages:** English, Kannada, Telugu, Hindi (4 fully supported in backend + mobile).
- **UI text:** Translated via i18n.ts; advisory bodies generated by backend in English only (voice service translates on demand).
- **Icons:** Used throughout (home, field, speaker, camera, user).
- **Text size:** Default body text is 13sp in some places, 15sp in others (inconsistent).
- **Font:** Roboto (system default); no adjustments for low-literacy.
- **Local units:** Area input accepts hectares, but no "acres" or "guntas" toggle visible in current FieldForm read.

### Research Findings
**Citation:** [India's Rural Farmers Struggle to Read and Write. Here's How "AgriApps" Might Change That.](https://www.good.is/articles/agricultural-apps-bridge-literacy-gaps-in-india) — Simple icon-based UI and multilingual support address low digital literacy. Voice-based interactions guide users through features even for those with low literacy levels.

**Citation:** [Farmers' perceived rating and usability attributes of agricultural mobile phone apps](https://www.sciencedirect.com/science/article/pii/S2772375524001060) — Usability scores improved significantly when apps used local language, simpler visuals, and reduced text density.

**Citation:** [Agriculture App UI Design: 7 Principles Farmers](https://medium.com/@sneh_sagar/agriculture-app-ui-design-7-field-tested-principles-that-drive-real-farmer-adoption-3fbbbbb24cea) — Principle 4: "Simplicity is a superpower. Avoid jargon. Use local terminology wherever possible."

**Citation:** [Accessibility - Material Design 3](https://m3.material.io/foundations/overview/principles) + [Android Developers Accessibility](https://developer.android.com/design/ui/mobile/guides/foundations/accessibility) — Recommended touch targets: 48×48 dp. Large text (14pt bold / 18pt regular) needs 3:1 contrast; normal text needs 4.5:1.

### Recommendation

#### A. Typography & Readability
1. **Default body text:** 15sp (currently 13sp in some places). Test readability on Redmi 5A (293 ppi; ~1mm font size at arm's length).
2. **Allow system text scaling:** Respect device-level text scaling up to 150% (most Android devices default to 100%). Audit all text at 150% rendering on a Redmi 5A.
3. **Contrast audit:**
   - Normal text (body, labels): 4.5:1 contrast minimum (current theme C.text vs C.bg seems OK, verify with a tool like WebAIM).
   - Large text (headers, buttons, badges): 3:1 minimum.
   - Simulate color-blind vision (protanopia, deuteranopia) for severity badges (green/amber/red); use color + icon + text label, not color alone.
4. **Font pairing:** Keep Roboto (familiar on Android) for body. Use slightly heavier weight (600–700) for labels to increase visual hierarchy and readability.

#### B. Icons + Text Labels (Redundant Encoding)
1. **Every icon must have a text label**, especially for users with low visual literacy:
   - "🏠 Home" (not just the home icon)
   - "📋 Field data" (not just a field icon)
   - "🔊 Advice" (not just a speaker icon)
   - "📷 Scan leaf" (not just a camera icon)
   - "👤 Me" (not just a user icon)
2. **Tab bar (existing):** Already has text labels below icons—good. Verify text is 11sp or larger.
3. **Severity badges:** Use color + icon + text (e.g., 🟢 Low, 🟡 Moderate, 🔴 High, ⚫ Severe) in cards, not color alone.

#### C. Terminology & Local Language
1. **Units of area:**
   - Display in the farmer's regional preference (auto-detected from device language).
   - Kannada region → guntas (1 gunta = 121 sq yd = 1,089 sq ft); allow input in guntas or acres.
   - Telugu region → guntas or acres.
   - Hindi region → acres or bighas.
   - Show conversion hint (small, gray): "1 gunta = 0.025 hectares".
2. **Irrigation depth (mm):**
   - For farmers unfamiliar with mm, add a local-language alternative: "~2 hours of irrigation" (if assuming a 2-inch/hour infiltration rate, adjust for local soil type).
   - Example display: "Irrigation: 25 mm (~2 hours at 2in/hr)" (small tooltip on tap).
   - **Research note:** Irrigation advice is often phrased as "hours of water application" in colloquial speech, not mm.
3. **Crop names:**
   - Always display crop recommendations in the farmer's language first, with English subtitle.
   - Example (Kannada): "ಕೋಲೆ (Cotton)" (not "Cotton (ಕೋಲೆ)").
   - Example (Telugu): "ఉత్తిరి (Cotton)".
4. **Weather terms:**
   - Avoid jargon. Instead of "NDVI trend," say "Plant health trend: improving" (plain language + icon).
   - Instead of "ET0," say "Water need based on temperature and sun" (if explaining why irrigation advice changed).
5. **Agronomy terminology:**
   - Use local agronomy terms where they exist. Example: in Kannada, "ಸಾಟಿ" (saati) is the local term for planting/sowing, familiar to farmers.
   - Pair with English for clarity: "ಸಾಟಿ ದಿನ / Sown date" in labels.

#### D. Voice-First Enhancements
1. **Audio read-aloud for all advisories:** (Already implemented in AdviceTab.) Verify audio is clear at 1.5x speed and supports Kannada/Telugu/Hindi TTS.
2. **Voice input for field data:** Add a "Record by voice" button in FieldForm (Kannada/Telugu/Hindi recognized, e.g., "My field is called Cotton East, two guntas, in Ballari district, sown June 15"). Auto-parses and pre-fills form fields (with farmer review + edit before submit).
3. **Voice command in HomeTab:** (Optional, future.) Tap mic icon → "Ask a farming question" (e.g., "When should I irrigate cotton?") → voice assistant (if available) answers in the farmer's language.

#### E. Date & Time Formatting
1. **Date display (Kannada example):**
   - Instead of "2026-09-24" (ISO format, unfamiliar to farmers), show "24 ಸೆಪ್ಟೆಂಬರ್ 2026" (day + month name + year in local script).
   - Fallback for unfamiliar month names: Use numerals if month name is ambiguous (e.g., "24-09-2026" in dd-mm-yyyy for Kannada speakers used to Indian date convention).
2. **Time display:**
   - "3:00 PM" (12-hour, familiar to farmers) or "15:00" (24-hour, check local preference). Avoid AM/PM without context (some regions use "afternoon" instead of "PM").
3. **Relative time:**
   - "Updated 2 hours ago" (easier than absolute timestamp for low-literacy users).

#### F. Touch Targets & Spacing
1. **Minimum touch target:** 48×48 dp (already Material Design 3 standard). Audit nav-bar buttons, card action buttons, and picker buttons (soil type tiles should be ≥ 64×64 dp each for reliable tapping with gloved hands).
2. **Spacing around buttons:** Minimum 8 dp gutter between adjacent buttons (e.g., "Cancel" and "Save"). Prevents accidental mis-taps.
3. **Text input fields:** Height ≥ 48 dp, padding ≥ 12 dp left/right, font size ≥ 15sp.

### Implementation Checklist
- [ ] Audit all text in HomeTab, AdviceTab, ScanTab, and FieldForm at 150% text scaling on a Redmi 5A.
- [ ] Update default body text size from 13sp to 15sp (C.S in theme).
- [ ] Add color-blind simulator to design review (check severity badges are distinguishable).
- [ ] Populate FieldForm with soil-type picker (tiles + local names in Kannada/Telugu/Hindi).
- [ ] Add area unit dropdown (guntas/acres/hectares, auto-selected by device language).
- [ ] Add mm-to-"hours of irrigation" converter in irrigation card (optional tooltip).
- [ ] Verify all date/time formatting uses local date convention (dd-mm-yyyy, local month names).
- [ ] Test with 3 farmers (1 from each language group) using 48pt local font: can they read advisory text comfortably at arm's length?

---

## 4. Perceived Performance and Reliability

### Current State
- **Cold start:** App wakes the server with `wakeServer()` pings (/health), then calls `getMe()`. Total: ~5–15 seconds on cold Render instance.
- **Loading UI:** HomeTab shows a SkeletonCard 3x (gray placeholders) while waiting for crop/irrigation/disease models.
- **Network errors:** Generic error text ("Something went wrong. Please try again."). No context about whether it's the app, the server, or the network.
- **Offline:** Banner shows "Offline — showing saved data"; cached data is loaded but no explicit sync indicator.
- **Slow network:** No explicit "server waking" message; user sees blank screen for 5–10 seconds.

### Research Findings
**Citation:** [How to Measure Mobile App Performance: Top 18 Metrics 2026](https://uxcam.com/blog/how-to-measure-mobile-app-performance/) — "A user who waits 800ms with a skeleton screen feels the app is fast, while a user who waits 400ms staring at a blank white screen feels it's broken."

**Citation:** [App Cold Start Time: Fix Slow Launch & Boost Retention (2026)](https://www.rs999.in/blog/why-your-apps-cold-start-time-is-silently-killing-retention-and-how-to-fix-it-under-2-seconds) — "Cold start—when a process is not in memory—has the biggest user impact. Google flags a cold start of 5 seconds or more as excessive, but users expect launch to feel near instant."

**Citation:** [Skeleton Screens vs Loading Spinners: When to Use Each](https://www.onething.design/post/skeleton-screens-vs-loading-spinners) — "Users tolerate skeleton states 40% longer than blank loaders."

### Recommendation

#### A. Boot Splash & Cold-Start Messaging (Animated Splash)
1. **AnimatedSplashScreen (already exists):** Good; keep it 3 seconds. During this time, call `wakeServer()` in parallel.
2. **Extend splash with messaging if server slow:** If `wakeServer()` hasn't resolved after 3 seconds, instead of jumping to the next phase, show a transitional screen:
   ```
   [Agro Mirai logo]
   "We're waking up the server…"
   [Rotating messages, every 2 sec]
   - "Checking weather…"
   - "Loading your fields…"
   - "Preparing advice…"
   [Small text, bottom]
   "This usually takes ~30 seconds. You can close and try again if it's taking too long."
   [Later, if > 30 sec: "Still loading… This is taking longer than usual. Try checking your internet."]
   ```
3. **Never show a blank white screen for > 5 seconds** (user will think the app crashed).

#### B. HomeTab Loading States
1. **First load (no cached data):** Show 3 SkeletonCards (already done) + a "Refreshing…" label at top.
2. **Subsequent refreshes (has cached data):** Show the previous data with a faint overlay + small label "Refreshing…" at top. User can read last values while new ones load.
3. **Loading timeout (> 15 sec):** Replace skeleton with: "Taking longer than usual. Check your internet. [Retry] button." (Not a silent hang.)

#### C. Error Messaging (Human-Friendly)
Replace generic errors with plain-language, actionable messages:

| Error Type | Current | Recommended |
| --- | --- | --- |
| Network timeout | "Network error" | "Can't reach server. Check your internet connection. [Retry]" |
| 401 (session expired) | "Unauthorized" | "Your session ended. [Sign in again]" |
| 422 (insufficient data) | "Insufficient data" | "Not enough weather/soil data yet. Tap [Data] tab and [Refresh data] to update." |
| CNN service down | "Unknown error" | "Leaf scan unavailable (photo model is offline). Showing disease prediction based on weather. [Try again]" |
| GEE/NDVI cache miss | "Computation failed" | "Can't fetch satellite data right now. Using last week's data. [Refresh]" |
| All others | "Something went wrong" | "Unexpected error (code: ABC). Try again or contact support: +91-80-1234-5678." |

2. **Implementation:**
   - Add error categorization in `api.ts` (distinguish network vs. timeout vs. 401 vs. 422 vs. service-specific).
   - Update `errorText()` in hooks.ts to return human-friendly messages keyed by error code and language.
   - Show error + [Retry] button in error box (already done in HomeTab/AdviceTab).

#### D. Offline + Sync Transparency
1. **Offline banner (current):** "Offline — showing saved data" is good. Add a timestamp: "Offline — Last synced 2 hours ago. [Sync now] (if online, enable retry)."
2. **Sync indicator:** When online and syncing advisories, show a subtle icon (↻ or cloud-sync) in the header, next to the field name, with a 1-second "Synced!" flash when complete.
3. **Cached data clarity:** In AdviceTab and ScanTab, show a small "(cached)" label or icon next to each advisory/scan result if it was loaded from local storage (not fresh from server).

#### E. Optimistic UI for Low-Latency Feel
1. **Feedback form (AdviceTab):** When farmer taps [Send feedback], immediately show "Feedback saved ✓" (optimistic) and update the UI (disable button, show checkmark). After server confirms (1–3 sec), show "Feedback saved" (still green, no animation). If server rejects, revert with error message.
2. **Field creation:** After tapping [Save field], show "Field created ✓" immediately (optimistic), allow navigation to HomeTab, and sync with server in background. If sync fails, show a small toast: "Field creation failed. Try again."

#### F. Image Upload Optimization (ScanTab)
1. **Client-side image compression before upload:**
   - If image > 5 MB, compress to 80% JPEG quality (ExpoFile's image compression features or a React Native image library).
   - Show compress feedback: "Optimizing image…" (1–2 sec).
   - Upload compressed version; show upload progress bar (not just spinner).
2. **Image validation (before upload):**
   - Check file size (must be 500KB–5MB).
   - Load first frame of image and verify it's a valid image (no corrupted files).
   - If blurry (simple heuristic: Laplacian variance < threshold), show warning: "This photo looks blurry. Take another for better accuracy." (Allow retry or force upload.)

### Implementation Checklist
- [ ] Extend AnimatedSplashScreen to show "We're waking up…" if wakeServer() still pending after 3 sec.
- [ ] Add error categorization in api.ts (code vs. message vs. status).
- [ ] Update errorText() to return human-friendly messages in 4 languages.
- [ ] Add sync indicator (icon + timestamp) to header.
- [ ] Implement optimistic UI for feedback form and field creation.
- [ ] Add client-side image compression to ScanTab (≤ 5 MB, 80% quality).
- [ ] Add image blur detection warning before upload.
- [ ] Test on a 3G connection (throttle network to 1 Mbps) to verify messaging and UX.

---

## 5. Trust and Comprehension of AI Advice

### Current State
- **Crop recommendation:** Shows recommended crop + confidence % (if available) + alternatives list + rationale (collapsed "Why?" tab).
- **Irrigation advice:** Shows depth (mm) + urgency badge + window dates + rationale (collapsed "Why?").
- **Disease risk:** Shows disease name + recommended action + rationale (collapsed "Why?").
- **Out-of-region warning:** Shows as a banner ("Not in region") if the model predicts a crop outside Bellary's regional set.
- **Advisory severity:** Shown as a badge (green/amber/red/dark-red); used to trigger notifications.

### Research Findings
**Citation:** [Transparency and Explainability in AI-Assisted Decision Making: Effects on Trust, Perceived Reliability, Confidence, and Ease of Understanding](https://doi.org/10.1177/10711813251369473) — "Higher transparency levels improved trust, perceived reliability, confidence in AI accuracy, and ease of understanding. Confidence scores are not always well calibrated in ML classifiers, which can lead to inappropriate trust."

**Citation:** [Farmers Embrace AI, But Trust Remains the Biggest Barrier](https://www.agbull.com/farmers-embrace-ai-but-trust-remains-the-biggest-barrier/) — "Only 24% of farmers and ranchers said they somewhat or fully trust AI-generated recommendations for operational decisions, while 39% expressed little or no trust. To improve trust, 62% said real-world farm results would strengthen confidence in AI systems."

**Citation:** [Explainability Needs in Agriculture: Exploring Dairy Farmers' User Personas](https://arxiv.org/html/2509.16249) — "Farmers have varying requirements, with some preferring little detail while others seek full transparency, with age, technology experience, and confidence in using digital systems correlating with explainability requirements."

### Recommendation

#### A. Confidence Display (Conditional)
1. **Crop recommendation:**
   - Always show confidence as a % below the crop name (e.g., "72% confident").
   - **If confidence < 60%:** Add a warning: "Lower confidence. Alternatives: [list]" (highlight the #2 pick).
   - **If confidence ≥ 90%:** No warning; maybe add a small ✓ badge.
   - Example display:
     ```
     🌾 Cotton
     72% confident
     Alternatives: Maize, Jowar
     ```

2. **Irrigation advice:**
   - Show urgency as a badge (Low/Moderate/High/Severe) + color.
   - If model's underlying certainty < 60% (stored in backend), add small text: "Confidence: Moderate" (not a % to avoid cognitive load).
   - Example:
     ```
     Irrigation: 25 mm
     🟠 Moderate urgency
     Confidence: Moderate (based on weather + soil moisture)
     ```

3. **Disease risk:**
   - Show risk level (Low/Moderate/High/Severe) + recommended action.
   - If source is "environmental_fallback" (rule-based, no CNN), add small note: "Based on weather only (leaf photo unavailable)." (Transparency about data source.)

#### B. Plain-Language Explanations (In Farmer's Language)
1. **"Why?" collapsible section (already exists):**
   - Tap to expand and see backend's rationale (e.g., SHAP feature importance or rule decomposition).
   - Currently shows plain text from rationale field; verify it's in farmer's language (backend translates; mobile displays as-is).
   - **Improve formatting:** Add visual breakdown (bullet-point summary + details):
     ```
     Why cotton is recommended:
     • Soil: Good pH (7.2), moderate nitrogen
     • Weather: 28°C avg, 600mm annual rainfall
     • Your history: Cotton successful last year (high yield)
     
     [Tap for full technical details]
     ```

2. **For irrigation:**
   - Add a visual water-balance explanation (optional, if space):
     ```
     How we calculated 25 mm:
     Water needed (ET0): 35 mm
     Expected rainfall (7 days): 10 mm
     Soil moisture: Adequate
     → Recommend: 25 mm by 3pm
     ```
   - If model has low certainty (weather missing), show:
     ```
     We're less sure because:
     • Weather forecast changed yesterday
     • Soil moisture sensor offline
     Recommendation: Scout field + decide based on soil feel
     ```

3. **For disease:**
   - Show contributing factors (plain language):
     ```
     Risk is MODERATE because:
     • Humidity 80% (high, favors disease)
     • Rainfall 45mm this week (normal)
     • Temperature 25°C (mild, less favorable)
     
     Action: Scout field in 2-3 days; watch for leaf spots
     ```

#### C. Out-of-Region Warnings (Improved)
1. **Current:** Banner says "Not in region. Common in region: Jowar."
2. **Improved:**
   ```
   ⚠️ Crop outside Bellary region
   Model recommends: Grapes
   More common in Bellary: Jowar, Groundnut, Cotton
   
   Why? Grapes need cooler temps + irrigation; Bellary is hot + dry.
   Try cotton or jowar—both succeed here.
   
   [Use model pick anyway] [Choose regional crop]
   ```
   - Buttons allow farmer to override (trust their knowledge or local factors the model doesn't know).

#### D. Feedback Loop Closure (Trust Building)
1. **After farmer rates an advisory (1–5 stars + "helpful" checkbox + optional comment):**
   - Show: "Thanks! Your feedback helps us improve. ✓"
   - After 2–3 weeks, if farmer has provided 5+ ratings, send a notification:
     ```
     "You've rated 5 advisories. Based on your feedback, we improved crop accuracy by 2.3% this month. Keep it up!"
     ```
   - Monthly digest (optional, in Me tab):
     ```
     Your feedback impact (this month):
     • Crop model improved by 2.3%
     • Irrigation model improved by 1.1%
     • You rated 8 advisories (helpful for 6)
     ```
   - This creates a sense of co-authorship and trust (farmer sees their feedback has real impact).

2. **Link to extension officer (optional, future):**
   - Add a "Ask an expert" button in high-uncertainty cases (confidence < 50% or risk level = "severe").
   - Opens a contact prompt: "Chat with local extension officer: [name] +91-XXXXX-12345" (pre-filled from backend's regional contacts).
   - Farmer can call/WhatsApp directly for second opinion.

#### E. Caveats on Model Limitations
1. **Add a collapsible "Model info" section in HomeTab cards (optional):**
   - Show what the model knows:
     ```
     This model is based on:
     • Soil type, pH, N/P/K, humidity
     • Weather: last 30 days
     • Your field's history
     
     It doesn't account for:
     • Market price (sell based on demand, not our advice)
     • Labor availability
     • Your local knowledge (you know your field better than us)
     ```
   - Encourages farmer to use the app as a tool, not gospel.

### Implementation Checklist
- [ ] Add confidence % display to HomeTab crop card (< 60% → highlight alternatives).
- [ ] Add confidence ("Moderate" enum) to irrigation card; add note if source = "environmental_fallback".
- [ ] Improve "Why?" section formatting: bullet-point summary + expandable details.
- [ ] Add water-balance breakdown for irrigation explanations (optional).
- [ ] Improve out-of-region banner: 2 buttons (use recommendation or switch to regional).
- [ ] Track and display feedback impact (monthly digest or after 5+ ratings).
- [ ] Add collapsible "Model info" section (explains what the model knows and doesn't).
- [ ] Test with 5 farmers: after reading explanations, can they articulate why each recommendation was made?

---

## 6. Leaf-Photo Scan Flow

### Current State
- **ScanTab:** Shows a "Take or pick photo" flow. On success, sends to `scanLeaf()` (POST /v2/fields/{field_id}/disease-risk/image).
- **Result:** Shows DiseaseAlert (disease name + risk level + action) + history of scans.
- **Fallback:** If CNN service unreachable, shows error message ("Scan unavailable"); no weather-based fallback displayed.
- **Photo storage:** Saves photos locally; persists across app restarts.

### Research Findings
**Citation:** [Best Apps To Diagnose Plant Diseases: The Ultimate Guide](https://farmonaut.com/blogs/best-apps-to-diagnose-plant-diseases-2025s-ultimate-guide) — "Capture angles: whole plant, symptom close-up (3–5 cm), underside of leaf, stem/collar, soil surface. Take multiple shots: different angles and distances — upload the clearest 2–3."

**Citation:** [How to Detect Plant Diseases from a Photo (Practical Guide)](https://dgmnews.com/how-to-detect-plant-diseases-from-a-photo-practical-guide/) — "Key is good lighting and getting close enough to capture leaf details clearly. Use bright, indirect daylight and avoid flash reflections. Use phone's highest native resolution; enable HDR if available; disable digital zoom."

**Citation:** [Plantix | #1 FREE app for crop diagnosis and treatments](https://plantix.net/en/) — Best-in-class leaf-disease app; shows framing guidance + live feedback on photo quality before upload.

### Recommendation

#### A. Pre-Capture Guidance Screen
1. **Before opening camera, show an instructional overlay (2–3 seconds):**
   ```
   📷 Leaf Photo Tips
   ✓ Use natural sunlight (no flash)
   ✓ Get close: 5–10 cm from the symptom
   ✓ Include whole leaf + close-up (2 photos)
   ✓ Show the underside if possible
   [Got it] button → Opens camera
   ```
   - Play a short 3-second audio clip (in farmer's language) summarizing the tips.
   - Show diagrams (stick figures + arrows) demonstrating "close-up" and "whole leaf" angles.

#### B. In-Camera Framing Overlay (Optional but High-Impact)
1. **If Expo camera offers native overlay support, show:**
   - A frame box in the center (7×7 cm, roughly the size of a leaf): "Frame the symptom here."
   - Green border if lighting is adequate; red if too dark.
   - Guidance text: "Close-up of affected area" or "Whole leaf visible."
   - As farmer moves phone, update the frame color in real time.
2. **If not feasible (overlay complex), skip and rely on post-capture feedback.**

#### C. Post-Capture Quality Check (Before Upload)
1. **After farmer captures a photo, show it in a preview screen with:**
   - Photo displayed at full width.
   - Automated quality assessment (client-side heuristics):
     - **Blur check:** Compute Laplacian variance; if < 100 (threshold), flag as blurry.
     - **Brightness check:** Histogram analysis; if mean < 50 or > 200 (on 0–255 scale), flag as too dark/bright.
     - **Size check:** If < 500 KB or > 5 MB, warn.
   - **Visual feedback badges:**
     ```
     ✓ Sharp image
     🟡 A bit bright (use shade next time)
     ✗ Too blurry—take another
     ```
   - Buttons:
     - [Use this photo] (green, enabled if all checks pass)
     - [Retake] (secondary)
     - [Use anyway] (gray, if quality poor but farmer insists)

2. **Example display:**
   ```
   [Photo preview, 100% width]
   
   Quality check:
   ✓ Sharp enough
   ✓ Good lighting
   ⚠️ Image size: 2.1 MB (will compress to 1.5 MB)
   
   Tips for better results:
   • Include the whole leaf
   • Show the underside if possible
   
   [Use this photo] [Retake]
   ```

#### D. Upload Progress & Feedback
1. **During upload:**
   - Show upload progress: "Uploading… 45%" (not just a spinner).
   - Add context: "Analyzing photo…" → "Checking disease patterns…" → "Preparing results…"
2. **On success:**
   - Show result screen:
     ```
     🌾 Disease Detection Result
     
     Disease: Early Blight
     Risk level: 🟠 Moderate
     
     What to do:
     • Inspect the plant carefully
     • Remove affected leaves
     • Apply fungicide if widespread
     • Re-check in 1 week
     
     [Add to field history] [Scan another photo] [Home]
     ```
   - Save photo locally for history.
3. **On failure (CNN service offline):**
   - Show the weather-based fallback (already computed):
     ```
     🌾 Disease Risk (Weather-Based)
     
     Risk level: 🟡 Moderate
     (based on humidity + rainfall, not leaf photo)
     
     Recommendation: Scout field + take another photo when weather clears
     
     [Retry scan] [Go home]
     ```
   - Be honest: "The leaf photo service is temporarily offline. This prediction is based on weather, not your actual leaf."

#### E. Scan History & Insights
1. **ScanTab history (existing, improve):**
   - Show last 30 scans (already done).
   - Add a small chart (optional): "Disease risk trend this month" (line graph: # high-risk scans over time).
   - Add a filter: "Show only [Cotton] scans" or "Show [High risk] scans only."
   - Tap a scan → expand to full photo + date + disease name + action taken (if farmer notes it).

2. **Insights (optional, future):**
   - "Early blight detected 3 times this season. Check your spray schedule."
   - "No disease alerts this week—field is healthy. ✓"

#### F. Leaf Photo Compression
1. **Before uploading, compress to <= 5 MB:**
   - Use JPEG quality 80% (good visual quality, small file size).
   - Maintain aspect ratio.
   - Show feedback: "Optimizing photo…" (1–2 sec).
   - Display compressed size vs. original (e.g., "5.2 MB → 1.8 MB").

### Implementation Checklist
- [ ] Add pre-capture guidance screen (text + diagrams + audio clip in 4 languages).
- [ ] Add blur detection (Laplacian variance check).
- [ ] Add brightness detection (histogram analysis).
- [ ] Add quality feedback badges (✓ Sharp, ⚠️ Bright, ✗ Blurry).
- [ ] Implement image compression before upload (80% JPEG, show size reduction).
- [ ] Update result screen: show disease name + risk + action steps (plain language).
- [ ] Improve fallback messaging: "Weather-based result (leaf photo unavailable)."
- [ ] Test with 5 farmers: measure time-to-scan-result and quality of photos captured. Target: < 2 min end-to-end, 0 blurry uploads.

---

## 7. Information Architecture: Home Screen, Nav Bar, Detail Screens

### Current State
- **Nav bar (bottom):** 5 tabs (Home, Field data, Advice, Scan leaf, Me). Each tab uses an icon + text label (11sp).
- **HomeTab:** Shows 3 cards (crop, irrigation, disease) stacked vertically.
- **AdviceTab:** Shows list of advisories (stacked cards) with pull-to-refresh.
- **DataTab:** Not detailed in the code excerpts; likely shows field metadata + refresh option.
- **ScanTab:** Shows history + capture/pick photo UI.
- **MeTab:** Not detailed; likely shows user profile + settings.

### Research Finding
**Citation:** [A UI/UX Guide to Agriculture App Design](https://gapsystudio.com/blog/agriculture-app-design/) — Successful agricultural apps prioritize decision-making over information browsing. The home screen should surface the most urgent action first.

### Recommendation: Restructured Information Architecture

#### A. HomeTab (Reordered)
**Goal:** One glance → farmer knows what to do today.

```
[Header: "Cotton East" field name + notification bell]

[ACTION CARD – High priority]
IF (urgency="high" OR urgency="severe" OR risk_level="high" OR risk_level="severe"):
  Show ONE card with the highest-stakes item (irrigation or disease)
  Card: Large title + action + window/timeline
  Color: Red/orange (high), dark red (severe)
  Example: "🌾 Irrigation due: 25 mm by 3pm"
ELSE:
  Show a generic "All systems normal" card (green)

[SECONDARY CARDS – Routine info]
- Crop recommendation (only if new or confidence < 60%)
- Irrigation (if not shown above) + depth + window
- Disease risk (if not shown above) + risk + action

[FOOTER]
"Pull down to refresh" or "Last updated: 2 hours ago [Refresh now]"
```

**Rationale:** Farmer opens the app → sees ONE clear action in 2 seconds → decides → acts.

#### B. AdviceTab (Improved List View)
```
[Header: "Advisories" + Filter icon]

[Optional Filter/Sort]
- "All fields" / "Cotton East only"
- "Newest first" / "Most urgent first"

[Advisory list, sorted by created_at DESC]
Each advisory card shows:
- Title + severity badge (color-coded)
- Body (first 100 chars, truncated)
- Date: "3 days ago"
- [Listen] button (play TTS)
- [Feedback] button (collapse/expand rating UI)
```

**New column feature (future):**
- Swipe right to reveal [Archive] / [Mark read] actions.

#### C. DataTab (Reorganize for Transparency)
```
[Header: "Field data"]

[FIELD INFO SUMMARY]
- Name: "Cotton East"
- Location: "Ballari, Karnataka" [Tap to edit]
- Area: "2 guntas (0.05 ha)" [Tap to edit]
- Soil type: "Black soil" [Tap to edit]
- Current crop: "Cotton" [Tap to edit]
- Sown date: "June 15, 2026" [Tap to edit]

[DATA QUALITY INDICATOR]
"Weather data: Updated 2 hours ago"
"Soil data: From June 15 sample"
"Satellite (NDVI): Updated 3 days ago"
[Refresh data] button

[HISTORICAL DATA (Optional)]
- Last 7-day rainfall: 45 mm (chart)
- Avg temp: 28°C (range: 22–34°C)
- Soil moisture: Adequate (last reading)
- NDVI trend: Improving ↗ (icon + trend line)

[Edit field] button → FieldForm overlay
```

#### D. ScanTab (Improved Layout)
```
[Header: "Scan leaf"]

[ACTION ZONE – Prominent]
[Take photo] [Pick from gallery] buttons (large, side-by-side)
"Get instant disease diagnosis"

[SCAN HISTORY – Below fold]
"Recent scans" heading
Filter: [All] [High risk] [This field only]
Scan cards: photo thumbnail + disease + date + risk badge
Swipe left → [Delete scan]
```

#### E. MeTab (Profile + Settings)
```
[Header: "Me"]

[PROFILE]
- Name: "Ramesh Kumar" [Tap to edit]
- Phone: "+91-98765-43210" [Tap to change]
- Preferred language: "ಕನ್ನಡ (Kannada)" [Change]
- Fields managed: "2 (Cotton East, Maize North)"

[SETTINGS]
- Notifications: [Daily action] [Weekly digest] [Off]
- Pause notifications: [3 days] [1 week] [Until date picker]
- Data usage: "Use mobile data" [Toggle]
- Offline mode: [Download last 30 advisories]
- Clear cache: [Delete saved photos/scans]

[FEEDBACK & HELP]
- "Tell us how to improve" [Link to feedback form]
- "FAQs" [Link to help center, if exists]
- "Report a bug" [Email support]
- "Sign out" [Logout button]
```

### Quick-Win Priority Matrix (Top 15 Improvements)

| # | Feature | Effort | Impact | Screen(s) | Notes |
| --- | --- | --- | --- | --- | --- |
| 1 | Reorder HomeTab: show urgent card first | S | High | Home | Reduces decision time from 20s to 3s |
| 2 | Add confidence % to crop card | S | High | Home | Builds trust; explains alternatives |
| 3 | OTP auto-read via SMS Retriever API | S | High | Auth | Removes copy-paste friction |
| 4 | GPS auto-fill + "Use my location" button | S | High | FieldForm | 90% of farmers will use GPS if available |
| 5 | Soil-type image picker (6 tiles) | M | High | FieldForm | Replaces dropdown; works for low-literacy farmers |
| 6 | Server-waking splash message (3–30s) | S | High | Boot | Prevents perceived crash on cold start |
| 7 | Blur detection on leaf photo | S | Medium | Scan | Prevents bad uploads; saves server CPU |
| 8 | Error messages in farmer's language | M | High | All | Replaces "Unknown error" with actionable text |
| 9 | Offline sync timestamp + [Sync now] button | S | Medium | Advice, Data | Transparency; farmer knows when last sync was |
| 10 | Image compression before upload (80% JPEG) | M | Medium | Scan | Saves bandwidth; faster upload on 3G |
| 11 | Multi-language crop/soil names (Kannada/Telugu/Hindi) | M | Medium | Field, Home | Farmer reads labels in their language |
| 12 | Units dropdown (guntas/acres/hectares) | S | Low | FieldForm | Nice-to-have; many farmers think in guntas |
| 13 | Feedback impact digest ("Improved by 2.3%") | M | Medium | Me, Advisory | Builds trust; shows farmer feedback matters |
| 14 | Voice input for FieldForm data | L | Medium | FieldForm | "Record: My field is Cotton, 2 guntas" |
| 15 | Leaf photo post-capture quality feedback | M | High | Scan | Reduces re-uploads; saves time |

**Effort:** S=1–2 days, M=3–5 days, L=1–2 weeks  
**Impact:** High = directly affects 50%+ of users or core flow; Medium = 25–50% or secondary flow; Low = nice-to-have or < 25%

---

## 8. Metrics and Validation Plan

### Goals
Validate that the UX changes:
1. **Reduce time-to-first-advice** (target: < 3 min from open to "I know what to do today").
2. **Increase advisory action rate** (target: 40% of advisories lead to a logged action within 3 days).
3. **Improve trust scores** (target: 50%+ of farmers rate confidence "moderate–high" after seeing explanations).
4. **Reduce onboarding drop-off** (target: 80% of farmers who start field creation complete it).

### 5-Farmer Usability Test Script

#### Setup
- **Participants:** 5 farmers from Ballari district, age 25–60, low-to-moderate Android literacy (have used WhatsApp/bank apps, but not farm-advisory apps).
- **Location:** Village setting or farmer's home; use their own phone (mid-range Android) or a loaner with similar specs.
- **Session:** 45–60 min per farmer; 2–3 tasks.
- **Moderator:** One researcher; observer logs (no interruptions).
- **Incentive:** 200–300 INR gift card or snacks.

#### Task 1: Onboarding & Field Creation (10–15 min)
**Scenario:** "You're a new farmer with a cotton field in Ballari. Let's set it up in the app."

**Steps:**
1. Install/open app (if not pre-installed).
2. Pick language (Kannada or Telugu based on participant).
3. Go through permissions.
4. Sign in (use a pre-generated test phone number + OTP).
5. Create a field: name = "Cotton", use GPS to find location, area = 2 guntas, skip soil type + crop (optional flow).

**Logging:**
- Time from app open to "field created" (target: < 2 min).
- Did participant use GPS or type lat/lon manually? (GPS usage rate = key metric).
- Did participant get stuck on any screen? (note which screen).
- Number of taps/retries to complete (target: < 15 taps).

**Success criteria:**
- Field created (doesn't matter if soil/crop skipped; optional is OK).
- Participant says "that was easy" or "no problems" (subjective).

#### Task 2: View & Understand Advice (10–15 min)
**Scenario:** "Open the Home tab. Tell me what you should do with your cotton field today."

**Steps:**
1. Navigate to HomeTab.
2. Read the crop recommendation card.
3. Read the irrigation card.
4. Tap "Why?" to see rationale (at least one).

**Logging:**
- Time to first action identified (target: < 10 sec).
- Did participant tap "Why?" without being prompted? (optional explanation use rate).
- After reading "Why?", can participant explain the recommendation in their own words? (comprehension check).
- Confidence rating (1–5) in the advice after reading: "How confident are you that the app's advice is correct?" (target: 3+ out of 5).

**Success criteria:**
- Participant correctly identifies an action (e.g., "Irrigate today").
- Participant rates confidence >= 3.

#### Task 3: Scan a Leaf Photo (10–15 min)
**Scenario:** "Let's take a photo of a leaf from your field and scan for disease."

**Steps:**
1. Open ScanTab.
2. Take a photo of a leaf (moderator provides a real cotton leaf or a printed photo).
3. Review the photo; check quality feedback.
4. Upload.
5. Review result (disease name + recommendation).

**Logging:**
- Did farmer use guidance tips (pre-capture screen)? (yes/no).
- Time to photo capture (target: < 30 sec).
- Photo quality: did it pass blur/brightness checks on first try? (pass rate target: 80%).
- Time from upload to result (server latency, < 10 sec target).
- After seeing result, farmer understanding: "What should you do based on this scan?" (comprehension).

**Success criteria:**
- Photo uploaded successfully.
- Farmer can articulate the next step (scout field, apply fungicide, wait, etc.).

#### Debriefing Questions (5 min)
After tasks, ask:
1. "What was easy about this app?"
2. "What was confusing?"
3. "Would you use this every day? Why or why not?"
4. "What feature would help you most?"
5. "Did any text or buttons feel too small to read/tap?"

### Logging & Analysis Template

**Session Log (Google Sheet or .csv):**

| Participant | Age | Language | Device | Task 1: Time to field created | Task 1: GPS used? | Task 1: Stuck on? | Task 2: Time to action identified | Task 2: Confidence (1–5) | Task 2: "Why?" tapped? | Task 3: Photo quality (pass/fail) | Task 3: Result time | Task 3: Comprehension | Feedback |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P1 | 42 | Kannada | Redmi 5A | 1:45 | Yes | None | 8s | 4 | Yes | Pass | 7s | Correct | "Text felt small; otherwise easy" |
| P2 | 55 | Kannada | Galaxy A12 | 2:10 | No (manual) | Area unit | 12s | 3 | No | Fail (blurry) | 8s (retry) | Correct | "Loved the tips before photo" |
| ... | | | | | | | | | | | | | |

**Metrics to Extract:**
1. **Time-to-first-advice:** Mean Task 2 time (target: < 10s).
2. **GPS adoption rate:** # tapping "Use my location" / total participants.
3. **Confidence average:** Mean confidence rating (target: 3.5+).
4. **Photo quality pass rate:** # passed on first try / total photos (target: 80%+).
5. **Drop-off points:** # participants who got stuck + which screen.
6. **Optional field usage:** Did participants skip soil type + crop? (yes = good; validates progressive disclosure).

### Continuous Metrics (Server-Side, Post-Launch)

After deploying changes, monitor these in the backend logs / analytics:

1. **Onboarding conversion:** # users who reach HomeTab with ≥ 1 field / # users who start signup (target: 70%+).
2. **Advisory action rate:** # advisories → user logs an action within 3 days / total advisories (target: 40%+).
   - Track via feedback form: "Did you act on this advice?" (yes/no/not applicable).
3. **Error rate per screen:** # errors (4xx, 5xx) / total page loads. (target: < 1%).
4. **Session duration (Home tab):** Avg time on Home before tap (target: < 20s; farmer should decide quickly).
5. **Feedback participation rate:** # farmers who provide ≥ 1 rating per month / active farmers (target: 30%+).
6. **Offline sync frequency:** # time-to-sync after coming online (monitor whether cached data is stale; alert if > 24h).
7. **Scan success rate:** # leaf scans resulting in disease diagnosis / total scans (target: 95%+, monitor for CNN downtime).
8. **Notification opt-out rate:** # farmers who disable notifications after 1 week / # users who received notifications (target: < 20% opt-out).

### How to Conduct Testing in a Village Setting

**Challenges:** Limited electricity, no dedicated lab, farmers busy during monsoon.

**Logistics:**
- **Schedule:** Early morning (6–7am, before field work) or late afternoon (4–5pm, after sun cools). Avoid mid-day.
- **Location:** Use a local school/gram panchayat office (usually has a table + chair + basic shelter). Get permission in advance.
- **Device charging:** Bring a portable power bank (10,000+ mAh); fully charge all devices before arriving.
- **Network:** Ideally, have a hotspot (Jio data) or test on the actual local 3G network (to catch real latency).
- **Photo subject:** Bring a few real plant leaves (cotton, maize) in a small bag. Or ask farmer to pluck a leaf during the session.
- **Incentive distribution:** Have small gifts/cash ready (200 INR per participant); hand out after session.
- **Informed consent:** Prepare a 1-page consent form in Kannada/Telugu (explain: we're testing the app, your feedback helps us improve, your data is private, you can stop anytime).

**Recruitment:**
- Partner with a local extension officer (Gram Panchayat) or farmer co-op to identify 5–10 willing participants.
- Send a simple WhatsApp invite (text in their language): "We're testing a new farm app. You'll get [incentive]. Interested? Call [your number]."

### Risk Mitigation

| Risk | Mitigation |
| --- | --- |
| Participant no-show | Recruit 7 farmers (target 5); offer flexible timing. |
| Device not charged | Bring portable power bank; pre-charge devices. |
| Network outage | Test on local 3G network as part of the test; if down, test offline flows (load cached data). |
| Participant doesn't understand Kannada UI | Have a Kannada-speaking moderator; pair with Telugu-speaking observer. |
| Leaf photo upload fails (server down) | Pre-record demo videos of successful scans; use as backup if server is down during session. |
| Confusion about privacy | Explain in consent form: "Your data is private. We won't share your phone number or field info." |

---

## Audit: Current App vs. Recommendations

| Screen | Current State | Gap | Recommendation | Priority | Effort |
| --- | --- | --- | --- | --- | --- |
| **HomeTab** | 3 cards stacked (crop, irrigation, disease); no hierarchy | Urgent actions buried if scrolled; 3 cards = decision paralysis | Reorder: show high-urgency card first; collapse others below fold | High | S |
| **HomeTab (Crop)** | Shows crop + confidence (if available) + alternatives collapsed | No plain-language "why"; confidence % not always shown | Add confidence %; expand "Why?" with plain-language summary in farmer's language | High | M |
| **HomeTab (Irrigation)** | Shows depth (mm) + urgency badge + window dates | Depth in mm unfamiliar to many farmers (they think in "hours of irrigation"); no confidence indicator | Add "~2 hours of irrigation" label; show confidence level if model uncertain | Medium | S |
| **HomeTab (Disease)** | Shows disease + action; weather-based if CNN unavailable | Fallback message says "error"; doesn't explain | Improve fallback message: "Based on weather only (photo unavailable). Scout field + take another photo." | Medium | S |
| **AdviceTab** | List of advisories; TTS available; can rate/feedback | Advisories not sorted by urgency; history grows unbounded (no archiving) | Sort by urgency first, then date; add swipe-to-archive; show confidence or data source. | Medium | M |
| **ScanTab (Capture)** | Open camera; no guidance; upload any photo | High error rate on blurry/dark images; wastes server CPU | Add pre-capture tips (text + diagrams + audio); blur detection before upload; retry if quality poor | High | M |
| **ScanTab (Result)** | Shows disease + risk level + action | No context if CNN fails; no next-steps guidance | Improve result screen: show disease name + recommended actions + "next steps" (scout in 2 days, re-scan, etc.) | Medium | S |
| **FieldForm (Location)** | Manual lat/lon text input | Most farmers don't know their exact coordinates; GPS tap not obvious | Add prominent "Use my location" button; auto-fill lat/lon + district on tap | High | M |
| **FieldForm (Soil type)** | Dropdown list (22 options, no visuals) | Farmers don't know technical soil names; dropdown is scrolling-heavy on small screens | Replace with 6-tile image picker (local-language labels + soil colors) | High | M |
| **FieldForm (Required fields)** | Requires name, area, lat, lon, sown_on | Too many required fields; farmers want to skip optional steps | Allow submit with only name + location; defer soil type + crop to optional | High | M |
| **Auth (OTP)** | Manual OTP entry (copy-paste from SMS) | Friction; users forget/mistype code | Use SMS Retriever API for auto-read OTP | High | S |
| **Auth (Permissions)** | All 5 permissions at once (location, camera, gallery, mic, notifications) | Overwhelming; user doesn't understand why each is needed | Use just-in-time permission requests; ask for location only when GPS tapped, etc. | Medium | M |
| **Boot (Cold start)** | AnimatedSplashScreen 3 sec; then app loads | If server slow, blank screen for 5–10 sec (user thinks crash) | Extend splash to show "We're waking the server…" until server responds or 30s timeout | High | S |
| **Error messages** | "Something went wrong. Please try again." (generic) | No context; farmer doesn't know if it's their network, app bug, or server down | Replace with human-friendly messages by error type (e.g., "Can't reach server. Check internet.") | High | M |
| **Offline indicators** | Banner: "Offline — showing saved data" | No sync timestamp; farmer doesn't know how stale cached data is | Add timestamp: "Offline — Last synced 2 hours ago. [Sync now]" | Medium | S |
| **Text sizing** | Default body text 13sp in some places, 15sp in others (inconsistent) | Hard to read on low-res devices; especially with gloves | Standardize to 15sp; support device text scaling up to 150% | Medium | S |
| **Language** | English labels for units (hectares, mm) | Farmers from Telugu/Kannada region don't recognize "hectares" or "mm" | Add local-language units dropdown (guntas, acres); show "mm (~2 hours irrigation)" conversion | Medium | M |
| **Feedback loop** | Rate advisory (1–5 stars) + optional comment | Farmer submits feedback; no confirmation or impact visibility | Show confirmation + later send "Your feedback improved model by X%" (monthly digest) | Medium | M |
| **Confidence display** | Shown as % on crop card (if available) | Confidence % alone is confusing without context ("72% of what?") | Show confidence + brief explanation ("72% confident based on soil pH + rainfall") | Medium | S |

---

## Prioritized Roadmap (12-Week Sprint)

### Week 1–2: Foundation (Onboarding & Boot Friction)
- [ ] SMS Retriever API integration (OTP auto-read)
- [ ] Extend AnimatedSplashScreen with "We're waking…" messaging (3–30s)
- [ ] Error messages: categorize by type; add human-friendly text (4 languages)

### Week 3–4: HomeTab Reordering & Trust
- [ ] Reorder HomeTab: urgent card first
- [ ] Add confidence % + plain-language "why" to crop card
- [ ] Add confidence indicator to irrigation card
- [ ] Improve disease result messaging (especially CNN fallback)

### Week 5–6: Field Creation Friction (Progressive Disclosure)
- [ ] Redesign FieldForm: reorder fields; make soil type + crop optional
- [ ] Add GPS "Use my location" button + error handling
- [ ] Design soil-type image picker (6 tiles, local labels)
- [ ] Add area unit dropdown (guntas/acres/hectares by region)

### Week 7–8: Leaf Scan Flow
- [ ] Pre-capture guidance screen (text + diagrams + audio tips)
- [ ] Blur detection (Laplacian variance heuristic)
- [ ] Brightness detection (histogram check)
- [ ] Post-capture quality feedback badges
- [ ] Image compression before upload (80% JPEG)

### Week 9–10: Offline & Sync + Localization
- [ ] Add offline sync timestamp + [Sync now] button (AdviceTab, DataTab)
- [ ] Standardize text sizing (15sp default); audit at 150% scaling
- [ ] Localize units (mm → hours of irrigation; display in farmer's language)
- [ ] Crop/soil names in 4 languages (Kannada/Telugu/Hindi/English)

### Week 11–12: Trust & Feedback Loop + Testing
- [ ] Feedback impact digest (show improvement % monthly)
- [ ] Conduct 5-farmer usability test (script, logging, debriefing)
- [ ] Fix bugs found in usability test
- [ ] Deploy all changes to staging; internal QA pass

### Post-Launch (Week 13+)
- [ ] Monitor server-side metrics (onboarding conversion, advisory action rate, etc.)
- [ ] Collect feedback via in-app form
- [ ] A/B test notification cadences (daily vs. weekly) with cohort of 100 farmers
- [ ] Plan next phase (voice input for FieldForm, integration with extension officer, etc.)

---

## Sources & References

- [A review on mobile apps in agriculture: Transforming farming practices in India through innovation and technology](https://www.researchgate.net/publication/400262077_A_review_on_mobile_apps_in_agriculture_Transforming_farming_practices_in_India_through_innovation_and_technology)
- [Digital Farming Solutions India: 7 Powerful Advances By 2025](https://farmonaut.com/asia/digital-farming-solutions-india-7-powerful-advances-by-2025)
- [Agritech Mobile Apps: Top 7 Agriculture Mobile App Trends](https://farmonaut.com/blogs/agritech-mobile-apps-top-7-agriculture-mobile-app-trends)
- [Adoption of mobile-based agricultural extension services: evidence from South India](https://www.sciencedirect.com/science/article/pii/S074301672500292X)
- [India's Rural Farmers Struggle to Read and Write. Here's How "AgriApps" Might Change That.](https://www.good.is/articles/agricultural-apps-bridge-literacy-gaps-in-india)
- [Your ultimate guide to developing mobile apps for farmers](https://qaltivate.com/blog/mobile-apps-for-farmers/)
- [Agriculture App UI Design: 7 Principles Farmers](https://medium.com/@sneh_sagar/agriculture-app-ui-design-7-field-tested-principles-that-drive-real-farmer-adoption-3fbbbbb24cea)
- [Farmers' perceived rating and usability attributes of agricultural mobile phone apps](https://www.sciencedirect.com/science/article/pii/S2772375524001060)
- [The impact of user characteristics of smallholder farmers on user experiences with collaborative map applications](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0264426)
- [Field-Ready HCI: A Conceptual Model of Mobile Application Use in Agriculture for Low-Resource and Smallholder Contexts](https://www.mdpi.com/2076-3417/16/14/6985)
- [Accessibility - Material Design 3](https://m3.material.io/foundations/overview/principles)
- [Android Developers Accessibility](https://developer.android.com/design/ui/mobile/guides/foundations/accessibility)
- [Text legibility - Material Design](https://m2.material.io/design/color/text-legibility.html)
- [Re-designing Kisan Suvidha App — to build a sense of ...](https://medium.com/@ashwin_bhawsar/re-designing-kisan-suvidha-android-application-6a4325b76149)
- [Building Offline Apps: A Fullstack Approach to Mobile Resilience](https://think-it.io/insights/offline-apps)
- [No Signal, No Problem: How to Build Apps for the Field](https://dev.to/promerakiiot/no-signal-no-problem-how-to-build-apps-for-the-field-4mhb)
- [Why Offline-Capable Mobile Apps Are Still Critical in Agriculture](https://qaltivate.com/blog/offline-mobile-apps-for-agriculture/)
- [Best Apps To Diagnose Plant Diseases: The Ultimate Guide](https://farmonaut.com/blogs/best-apps-to-diagnose-plant-diseases-2025s-ultimate-guide)
- [How to Detect Plant Diseases from a Photo (Practical Guide)](https://dgmnews.com/how-to-detect-plant-diseases-from-a-photo-practical-guide/)
- [Plantix | #1 FREE app for crop diagnosis and treatments](https://plantix.net/en/)
- [Mobile App Onboarding Best Practices [2026 Guide]](https://www.eleken.co/blog-posts/mobile-app-onboarding-best-practices)
- [The essential guide to mobile user onboarding: UI/UX patterns and best practices](https://www.appcues.com/blog/essential-guide-mobile-user-onboarding-ui-ux-patterns-and-best-practices)
- [Progressive Disclosure in Mobile UX: Reduce User Overload](https://www.digia.tech/post/progressive-disclosure-mobile-ux/)
- [Onboarding Patterns for Mobile Apps: Progressive Disclosure vs Front-Loaded Setup](https://www.digia.tech/post/onboarding-patterns-progressive-disclosure-vs-front-loaded-setup/)
- [World's First Ag Voice-to-Text Tech Featured in October 17 Tech Talk](https://www.wga.com/news/worlds-first-ag-voice-to-text-tech-featured-in-october-17-tech-talk/)
- [Voice User Interface Design Best Practices](https://lollypop.design/blog/2025/august/voice-user-interface-design-best-practices/)
- [Voice User Interface (VUI) for Mobile Apps - A Complete Guide](https://www.unifiedinfotech.net/blog/the-ultimate-voice-user-interface-vui-guide-for-mobile-app-development/)
- [KrishokBondhu: A Retrieval-Augmented Voice-Based Agricultural Advisory Call Center for Bengali Farmers](https://arxiv.org/pdf/2510.18355)
- [How to Measure Mobile App Performance: Top 18 Metrics 2026](https://uxcam.com/blog/how-to-measure-mobile-app-performance/)
- [Why Your App Still Feels Slow Even After Performance Optimization](https://medium.com/@hiren6997/why-your-android-app-still-feels-slow-even-after-profiling-707a5eea43d5)
- [Skeleton Screens vs Loading Spinners: When to Use Each](https://www.onething.design/post/skeleton-screens-vs-loading-spinners-when-to-use-each)
- [App Cold Start Time: Fix Slow Launch & Boost Retention (2026)](https://www.rs999.in/blog/why-your-apps-cold-start-time-is-silently-killing-retention-and-how-to-fix-it-under-2-seconds)
- [Transparency and Explainability in AI-Assisted Decision Making: Effects on Trust, Perceived Reliability, Confidence, and Ease of Understanding](https://doi.org/10.1177/10711813251369473)
- [Farmers Embrace AI, But Trust Remains the Biggest Barrier](https://www.agbull.com/farmers-embrace-ai-but-trust-remains-the-biggest-barrier/)
- [Explainability Needs in Agriculture: Exploring Dairy Farmers' User Personas](https://arxiv.org/html/2509.16249)
- [How to Perform Usability Testing for Mobile Apps](https://www.browserstack.com/guide/usability-testing-for-mobile-apps)
- [Mobile App Usability Testing: Common Issues and Testing Methods](https://medium.com/@david.pham_1649/mobile-app-usability-testing-common-issues-and-testing-methods-2d9c4fc27431)

---

**End of Report**

Version: 1.0  
Status: Ready for team review and implementation planning  
Next step: Prioritize top 5 items from roadmap; assign ownership; set sprint start date.
