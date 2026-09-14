# AGRO MIRAI — Hybrid UI/UX Design Spec + Brand Theme (Mobile App)

Blends all three researched directions into one coherent design: Option C's hero-first entry point, Option B's severity-sorted conversational feed, Option A's direct-access icon row for repeat users who already know what they want. Plus a brand theme (name treatment, palette, type, iconography) built to be genuinely ours, not borrowed from FarmRise/Plantix/Kisan Suvidha — informed by them, not a copy of any one of them.

---

## 1. The hybrid navigation model

One home screen, three zones, top to bottom, in order of how a farmer actually uses the app:

```
┌─────────────────────────────┐
│  🌐 EN/ಕನ (switch)   🌾 Field ▾│  <- persistent header, always visible
├─────────────────────────────┤
│                               │
│      ⊙  PRESS TO HEAR         │  <- ZONE 1: Hero (from Option C)
│     "Today's Advisory"        │     Largest element on screen.
│         [big circular         │     One press → auto-plays the
│          play button]         │     most urgent advisory for the
│                               │     currently selected field.
├─────────────────────────────┤
│  🟢 Irrigation   🟡 Disease    │  <- ZONE 2: Direct-access row (Option A)
│  🟢 Crop Rec.    📋 History    │     4 compact icon+severity chips.
│                               │     For a farmer who already knows
│                               │     what they want, this is faster
│                               │     than listening through the feed.
├─────────────────────────────┤
│  ● Irrigate today — 33mm  ▶  │  <- ZONE 3: Feed (Option B)
│  ● Leaf spot risk: low    ▶  │     Chat-bubble cards, severity-
│  ● Maize suitable here    ▶  │     sorted (most urgent first, not
│  ○ Feedback on yesterday's… │     chronological), scrollable,
│                               │     each a tap-to-play voice note
└─────────────────────────────┘     with a one-line transcript.
```

**Why this specific order, not a different one:** the hero button answers the single most common question ("what should I do today") in one press with zero reading, matching Option C and the single-screen research finding. The icon row directly below it serves the farmer who already knows they specifically want the irrigation number or wants to check disease risk again — a real, common case FarmRise's own research flagged (returning users skip discovery, they want their answer fast). The feed at the bottom is where everything else lives — other fields, past advisories, disease history — in the exact visual language (chat bubbles, tap-to-play voice notes) this population already trusts from WhatsApp, so scrolling down feels like checking messages, not browsing a database.

**Field switcher** stays in the header, not a separate screen — switching fields re-sorts the hero + feed instantly, it never navigates away from home.

## 2. Screen-by-screen

### Language picker (first launch only)
Two large cards, side by side, each showing the language name in its own script only (ಕನ್ನಡ / English) with no translation of the other into it. Tapping once plays a spoken sample of that language saying its own name; tapping again (or a confirm button that appears after) commits. No back button needed — this screen only ever appears once, or from the header's language icon where it becomes a lightweight two-option switch, not a full onboarding replay.

### Home (described above)
Hero + icon row + feed, as laid out in §1.

### Advisory detail (from a feed tap or hero press)
Full-bleed severity color as a thin top band (never the whole background — keeps the brand palette dominant even on a red/urgent result), large numeral/icon combination, auto-playing audio with a visible transcript underneath in large type, one "why" tap that expands the `ExplanationService` reasoning (spoken + shown), one thumbs-up/thumbs-down feedback control at the bottom — the entire screen is one continuous read top to bottom, no tabs, no sub-navigation.

### Disease check
Opens directly to the camera, not a form. Big shutter button, no settings visible. On capture: same detail-screen pattern as above, with the `environmental_fallback` state rendered as its own honest "using field conditions" chip (not a red error state) when the CNN service is unreachable.

### Field management
A simple list, each field a card with its name, crop icon, and a small severity dot summarizing its current advisory state at a glance — tapping a card sets it as the active field on Home rather than opening a separate detail view. Add/edit/delete are large, clearly-labeled buttons, never icon-only, since this is a lower-frequency action worth spelling out in text under its icon.

## 3. Brand theme

### Name treatment
**AGRO MIRAI** stays as the full product name in Latin script everywhere it appears in the app (logo, splash, header), since "Mirai" (未来, "future") is a deliberate, memorable brand choice worth keeping intact rather than transliterating — but every functional label around it (button text, advisory content, navigation) is fully localized in Kannada/English per the user's chosen language. The brand name is the one piece of English text a Kannada-only user will still see; treat it as a logo/wordmark, not as copy they need to read.

### Color palette
Two separate palettes that never mix: a **brand palette** (calm, identity, backgrounds, chrome) and a **severity palette** (status only, never used decoratively). This separation is deliberate — FarmRise's research explicitly called out keeping severity/status color distinct from brand color so red never gets read as "this app is broken" instead of "this field needs attention."

**Brand palette — "Field & Grain"**
| Token | Hex | Use |
|---|---|---|
| `brand-green-900` | `#1B4332` | Header, hero button fill, primary text on light |
| `brand-green-600` | `#2D6A4F` | Primary buttons, active states |
| `brand-green-100` | `#D8F3DC` | Card backgrounds, subtle fills |
| `grain-cream` | `#FDF8EE` | App background (warm off-white, not clinical white — reads as "earth/harvest," not "hospital app") |
| `soil-brown` | `#7A5C3E` | Secondary accents, field icons, dividers — used sparingly |
| `ink-900` | `#22281F` | Primary text (a warm near-black, not pure `#000`, easier to read in bright outdoor sunlight glare) |

**Severity palette — status only, WCAG-checked against `grain-cream`**
| Token | Hex | Meaning |
|---|---|---|
| `status-good` | `#2E7D32` | Low risk / no action needed |
| `status-caution` | `#E8A33D` | Moderate — amber, not yellow, for outdoor-glare legibility |
| `status-urgent` | `#C1432A` | High risk / act now — a warm red-orange, not a pure alarm red, so it reads as "urgent" without triggering the same alarm reflex as a system error color |

Both palettes are warmer/earthier than FarmRise's pure green-and-white or a typical blue-and-white agri-tech palette — deliberate differentiation while still reading unmistakably as "agriculture," and the cream background specifically helps outdoor daylight legibility (a real, common use context this app has that an office-use app doesn't).

### Typography
**Noto Sans + Noto Sans Kannada**, same reasoning FarmRise validated: renders both scripts cleanly, loads fast as a variable/Google font, and Expo/React Native has first-class support for bundling it. Large base size (minimum 18sp for body text, 28sp+ for the hero numeral/severity readouts) — this is a non-negotiable given the target user and outdoor-use context, not a stylistic choice to revisit later.

### Iconography
Flat, single-weight line-and-fill icons (not photographic, not skeuomorphic) drawn specifically for AGRO MIRAI's four core actions — a stylized water drop for irrigation, a leaf-with-magnifier for disease check, a seedling for crop recommendation, a speech-bubble-with-waveform for the hero "press to hear" button. Commission or generate these as one consistent icon set (same stroke width, same corner radius) rather than mixing stock icon packs — a mismatched icon set is one of the most common "looks unfinished" signals in a demo, and it's cheap to avoid.

### Motion
Minimal, purposeful, never decorative: the hero button's press state, the waveform animating while audio plays, a gentle fade when the feed re-sorts after a field switch. No page-transition flourishes, no parallax, no loading spinners longer than a fraction of a second feel — every motion should communicate state (this is playing, this just updated), never just look nice. This mirrors the PRD's existing "near-zero motion" requirement for the farmer surface specifically, as distinct from the landing page where motion is welcome.

### Tone of voice (for any copy/prompts)
Direct, short sentences, second person, no jargon: "Water your field today" not "Irrigation is recommended for optimal yield outcomes." Every string should pass a read-aloud test — if a sentence is awkward spoken by AI4Bharat TTS, it needs a rewrite, since it will always be heard, not just read.

---

## 4. What this means for Antigravity

This spec is detailed enough to hand off as-is for component/screen building. It does not yet include exact spacing/grid values, component library mapping (`react-native-reusables` component-by-component), or the disease-camera/field-management flows' edge-state designs (empty states, the `422 NO_WEATHER_DATA` waiting state) — worth a follow-up pass once the first build exists to react to, same as the landing page's visual pass is deferred to your v3.

Want me to turn this into the actual Antigravity build prompt next (folding this hybrid spec and brand theme into the kickstart prompt I already gave you), or do you want to see a visual mockup first before locking it in?
