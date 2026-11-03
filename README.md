# AGRO MIRAI

**What should I grow, and when do I need to water it?**

That's the whole app, really. A farmer in Bellary points their phone at a field, and AGRO MIRAI pulls real soil, weather, and satellite data for that exact plot, runs it through an FAO-56 water balance and a crop-suitability model, and tells them — in their own language, spoken out loud if they'd rather not read — what to plant and how much to irrigate today. Point a camera at a sick leaf and it'll tell you what's wrong with it too.

<div align="center">

[![Android APK](https://img.shields.io/badge/Download-agromirai2.8.18.apk-3DDC84?logo=android&logoColor=white&style=flat-square)](https://agromirai.vercel.app/app-release.apk)
[![React Native](https://img.shields.io/badge/mobile-Expo_SDK_57-61DAFB?logo=react&logoColor=black&style=flat-square)](https://reactnative.dev)
[![Flask](https://img.shields.io/badge/backend-Flask_3.1-3776AB?logo=python&logoColor=white&style=flat-square)](https://www.python.org)
[![Supabase](https://img.shields.io/badge/db-Supabase_Postgres-3ECF8E?logo=supabase&logoColor=white&style=flat-square)](https://supabase.com)
[![Google Earth Engine](https://img.shields.io/badge/satellite-Sentinel--2_NDVI-4285F4?logo=googleearthengine&logoColor=white&style=flat-square)](https://earthengine.google.com)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg?style=flat-square)](LICENSE)

<p>
  <a href="https://agromirai.vercel.app/app-release.apk"><img src="https://img.shields.io/badge/⚡_Download_APK-v2.8.18-2ea44f?style=for-the-badge&logo=android&logoColor=white" alt="Download Mobile APK"/></a>
  &nbsp;
  <a href="https://agromirai.vercel.app/download"><img src="https://img.shields.io/badge/📱_Download_Page-agromirai.vercel.app-0070f3?style=for-the-badge&logo=vercel&logoColor=white" alt="Web Download Portal"/></a>
  &nbsp;
  <a href="docs/INDEX.md"><img src="https://img.shields.io/badge/📚_Docs-Master_Index-6f42c1?style=for-the-badge&logo=readme&logoColor=white" alt="Documentation Master Index"/></a>
  &nbsp;
  <a href="docs/NEXT_TEAM_HANDOVER.md"><img src="https://img.shields.io/badge/🛠️_Handover-Guide-d73a49?style=for-the-badge&logo=gitbook&logoColor=white" alt="Engineering Handover"/></a>
</p>

</div>

---

<div align="center">
  <img src="docs/images/agro_mirai_logo_animation.gif" alt="AGRO MIRAI app-launch logo animation" width="40%" style="border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.12);"/>
  <p><em>The actual splash screen from the shipping app — not a mockup.</em></p>
</div>

<br/>

### The app, screen by screen (v2.8.18)

<div align="center">
  <table border="0" cellspacing="10" cellpadding="0">
    <tr>
      <td width="25%" align="center">
        <img src="docs/screenshots/01_home_screen.png" width="95%" style="border-radius: 10px; border: 1px solid #d0d7de;"/><br/>
        <b>Home</b><br/>
        <sub>Weather, soil and field status at a glance</sub>
      </td>
      <td width="25%" align="center">
        <img src="docs/screenshots/02_advisory_screen.png" width="95%" style="border-radius: 10px; border: 1px solid #d0d7de;"/><br/>
        <b>Advisory</b><br/>
        <sub>Crop pick and today's irrigation number</sub>
      </td>
      <td width="25%" align="center">
        <img src="docs/screenshots/03_leaf_scanner_screen.png" width="95%" style="border-radius: 10px; border: 1px solid #d0d7de;"/><br/>
        <b>Scan</b><br/>
        <sub>Photo a leaf, get a diagnosis</sub>
      </td>
      <td width="25%" align="center">
        <img src="docs/screenshots/04_field_map_screen.png" width="95%" style="border-radius: 10px; border: 1px solid #d0d7de;"/><br/>
        <b>Field map</b><br/>
        <sub>Draw the field boundary on satellite view</sub>
      </td>
    </tr>
    <tr>
      <td width="25%" align="center">
        <img src="docs/screenshots/05_field_telemetry_screen.png" width="95%" style="border-radius: 10px; border: 1px solid #d0d7de;"/><br/>
        <b>Field data</b><br/>
        <sub>Weekly weather and soil history</sub>
      </td>
      <td width="25%" align="center">
        <img src="docs/screenshots/06_multilingual_voice_screen.png" width="95%" style="border-radius: 10px; border: 1px solid #d0d7de;"/><br/>
        <b>Voice</b><br/>
        <sub>Ask a question out loud, hear the answer back</sub>
      </td>
      <td width="25%" align="center">
        <img src="docs/screenshots/07_kannada_profile_screen.png" width="95%" style="border-radius: 10px; border: 1px solid #d0d7de;"/><br/>
        <b>ಕನ್ನಡ</b><br/>
        <sub>Full Kannada UI, not just translated strings</sub>
      </td>
      <td width="25%" align="center">
        <img src="docs/screenshots/08_telugu_profile_screen.png" width="95%" style="border-radius: 10px; border: 1px solid #d0d7de;"/><br/>
        <b>తెలుగు</b><br/>
        <sub>Same for Telugu</sub>
      </td>
    </tr>
  </table>
</div>

---

## Why this exists

Three things kept coming up when I looked at what's actually available to a smallholder farmer in India right now:

- **The advice isn't for your field.** Government extension advisories are published district-wide. They don't know your soil's actual pH, what your satellite imagery looked like this week, or what the weather did at your specific coordinates — they're the same bulletin for everyone in a 50km radius.
- **Irrigation is guesswork, and guesswork wastes water.** Most farmers water on a fixed schedule because nobody's handed them a real evapotranspiration number. That overwaters some fields, underwaters others, and depletes groundwater either way.
- **By the time a leaf disease gets noticed by a human, it's often too late** — and most diagnostic tools assume you can read English and fill out a form, which rules out a lot of the people who'd actually benefit most.

AGRO MIRAI tries to close that gap with real data instead of defaults: live soil and weather APIs, actual Sentinel-2 satellite imagery for the field you drew, a physics-based water balance instead of a fixed schedule, and a voice interface so literacy and English fluency aren't a requirement to use it.

---

## How it actually works

**Crop and irrigation advice.** When you add a field, the backend pulls soil texture and pH from ISRIC SoilGrids, rainfall and temperature history from Open-Meteo, and NDVI (a vegetation-health signal) from Sentinel-2 via Google Earth Engine, for that field's exact boundary. That feeds two things: an FAO EcoCrop matrix that ranks which of 22 crops actually suit the season and soil, and a daily FAO-56 soil water balance (Hargreaves-Samani ET₀, adjusted for crop stage and root depth) that says precisely how many millimetres of water the field needs today, not "water it sometime this week."

**Leaf disease scanning.** A photo first goes through a biological gate — an OpenCV check on chlorophyll color ratio and leaf-shaped contours — before anything is classified, so a photo of a person or a piece of paper gets rejected instead of producing a confident wrong answer. Leaves that pass go to a MobileNetV2 CNN trained on the PlantVillage dataset (38 classes), with a weather/NDVI-based rule fallback if the model's unavailable.

**Voice and language.** English, Hindi, Kannada, and Telugu, both directions — speech in, spoken advisory out — through a tiered pipeline (self-hosted AI4Bharat models first, Sarvam AI cloud as backup), degrading to a clearly-labeled text message if both are unreachable rather than failing silently.

**Login.** Name and phone number, no password. Android's SMS Retriever API reads the OTP off an incoming SMS and fills it in automatically — nothing to type, nothing to remember.

Every external call in this stack — weather, soil, satellite, the CNN, voice — has a documented fallback. The rule the whole backend is built around: degrade gracefully, never hand back a 500.

---

## Architecture

```mermaid
flowchart TD
    subgraph Data_Acquisition ["Field data sources"]
        Meteo["Open-Meteo<br/>(weather, rainfall history)"]
        Soil["ISRIC SoilGrids v2.0<br/>(pH, texture, nutrients)"]
        GEE["Google Earth Engine<br/>(Sentinel-2 NDVI)"]
        Cache[("Cached NDVI raster<br/>(offline fallback)")]
        GEE -.->|timeout / cloud cover > 40%| Cache
    end

    subgraph Core_Backend ["Flask API (/v2)"]
        FeatureVector["Field feature builder"]
        Data_Acquisition --> FeatureVector

        Store[("SQLite (dev) /<br/>Supabase Postgres (prod)")]
        Store <--> FeatureVector

        EcoCrop["EcoCrop matrix<br/>(22 crops)"]
        FAO56["FAO-56 water balance"]

        FeatureVector --> EcoCrop
        FeatureVector --> FAO56

        DecisionEngine["Advisory engine"]
        EcoCrop --> DecisionEngine
        FAO56 --> DecisionEngine
    end

    subgraph Vision_Pipeline ["Leaf scan"]
        Upload["Camera / gallery photo"]
        Gate{"Biological leaf gate<br/>(OpenCV)"}
        CNN["MobileNetV2 CNN<br/>(PlantVillage)"]
        Rules["Weather/NDVI risk scorer"]

        Upload --> Gate
        Gate -->|valid leaf| CNN
        Gate -->|rejected| Rules
        CNN --> DecisionEngine
        Rules --> DecisionEngine
    end

    subgraph Multilingual_Voice ["Voice pipeline"]
        VoiceIn["Voice input"]
        Tier1["AI4Bharat<br/>(self-hosted)"]
        Tier2["Sarvam AI<br/>(cloud)"]
        Tier3["Text fallback<br/>(localized)"]

        VoiceIn --> Tier1
        Tier1 -.->|unavailable| Tier2
        Tier2 -.->|unavailable| Tier3
    end

    subgraph Mobile_App ["Android app (Expo SDK 57)"]
        DecisionEngine --> AppAPI["Mobile sync endpoints"]
        Tier1 & Tier2 & Tier3 --> AppAPI
        AppAPI --> MapLibre["MapLibre GL field map"]
        AppAPI --> OTP["SMS Retriever auto-fill"]
        AppAPI --> Drawer["Notification drawer"]
    end

    style Data_Acquisition fill:#f6f8fa,stroke:#d0d7de,stroke-width:2px
    style Core_Backend fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    style Vision_Pipeline fill:#fff3e0,stroke:#e65100,stroke-width:2px
    style Multilingual_Voice fill:#ede7f6,stroke:#512da8,stroke-width:2px
    style Mobile_App fill:#e1f5fe,stroke:#0288d1,stroke-width:2px
```

---

## Models and algorithms, and why those over something trained

| Layer | Approach | Why not the obvious ML alternative |
|---|---|---|
| Crop recommendation | LLM (Gemini) first, falls back to a deterministic FAO EcoCrop rule engine | A trained classifier needs N/P/K soil values that SoilGrids simply doesn't provide. An earlier RandomForest version recommended watermelon for a cotton field. EcoCrop only needs data this project actually has. |
| Irrigation | Deterministic FAO-56 soil water balance, not a model | A RandomForest urgency classifier measured 72% accuracy — "barely useful." The water balance answers a more precise physical question and shows its work (ET₀, rainfall, days to stress) instead of a label. |
| Leaf disease (live Scan tab) | Vision LLM (OpenRouter, Groq fallback) | Gemini's vision endpoint was unreliable in testing — real timeouts across networks. The CNN below exists and works, but a general vision LLM generalized far better to messy real-field phone photos than a model trained on clean lab-background leaves. |
| Leaf disease (CNN, alternate path) | MobileNetV2, PlantVillage dataset | Kept in the codebase as an offline-capable option; not what the live app calls today. |
| Soil type suggestion | Nearest-match lookup against the 8 soil orders' pH/organic-carbon profile | SoilGrids doesn't output an Indian soil-order label at all — there's no ground truth to classify against, just a closest-match hint. |
| Voice | Sarvam AI cloud primary, AI4Bharat self-hosted fallback | Keeps the main API process light; the heavy self-hosted models run as a separate microservice. |

Full writeups with the actual reasoning and decision history live in [docs/ALGORITHMS.md](docs/ALGORITHMS.md) and [decisions/](decisions/).

---

## Where things stand

- **714 tests passing, 0 failing** (40 skipped — live third-party API calls that need network/credentials not present in CI). See [docs/TEST_CASES.md](docs/TEST_CASES.md) for what's actually covered, and what isn't (mobile UI has no automated test suite yet — that's been manual device testing so far).
- SMS OTP auto-fill lands in under 650ms on real devices.
- CNN inference is ~72ms on-device.
- A GitHub Actions job pings the Render backend every 12 minutes so it doesn't cold-start on a farmer's first request.
- The universal release APK is 53.8MB, covers `arm64-v8a`, `armeabi-v7a`, `x86`, and `x86_64`.

---

## Repository layout

```text
AGRO MIRAI/
├── decisions/                       # 31 architecture decision records — the reasoning behind the bigger calls
├── docs/                            # Documentation, research notes, handoffs, runbooks
│   ├── INDEX.md                     # Start here
│   ├── NEXT_TEAM_HANDOVER.md        # Build, deploy, and ops instructions
│   ├── LOCAL_SETUP.md               # Full local dev setup (backend, mobile, tests)
│   ├── architecture.md              # Full system architecture and data flows
│   ├── ALGORITHMS.md                # What's learned vs. rule-based vs. an LLM call, and why
│   ├── TEST_CASES.md                # What the test suite actually checks
│   ├── SMS_OTP_SETUP.md             # SMS Retriever / Gateway integration
│   ├── screenshots/                 # App screenshots used above
│   └── images/                      # Logo animation and other graphics
│
├── mobile/                          # React Native app (Expo SDK 57)
│   ├── src/screens/                 # HomeTab, AdviceTab, ScanTab, FieldMapScreen, DataTab, MeTab
│   ├── src/components/              # VoiceMode, ChatAssistant, Charts, AnimatedSplashScreen
│   ├── modules/sms-retriever/       # Native Android SMS Retriever module
│   └── android/                     # Native Android project (Gradle, signing config)
│
├── src/agro_mirai/                  # Python 3.12 backend (Flask)
│   ├── acquisition/                 # Open-Meteo, SoilGrids, Earth Engine adapters
│   ├── api/                         # App factory + all /v2 route modules (auth, routes/, voice, vision, LLM clients)
│   ├── auth/                        # OTP providers, session auth
│   ├── models/                      # EcoCrop matrix, FAO-56 water balance, disease risk, leaf gate
│   ├── persistence/                 # DataStore repository (SQLite dev / Supabase prod)
│   ├── processing/                  # Feature building and data normalization
│   └── voice/                       # Tiered voice client and translation
│
├── services/                        # Standalone inference containers
│   ├── cnn-inference/ & cnn-onnx/   # PlantVillage MobileNetV2 serving (ONNX)
│   └── voice/                       # AI4Bharat speech/translation service
│
├── migrations/                      # SQLite + Postgres schema migrations (local dev)
├── supabase/migrations/             # Supabase (production Postgres) migrations
├── specs/
│   ├── core/                        # CI-enforced schema, enum, and OpenAPI contracts
│   └── domains/                     # Domain fixtures
├── tools/                           # CLI utilities (spec checks, fixture seeding)
├── web/
│   ├── landing/                     # Marketing site + APK download portal (Vercel)
│   └── admin/                       # Admin dashboard frontend
├── tests/                           # Backend test suite (api, auth, models, persistence, e2e, ...)
├── render.yaml                      # Render deployment blueprint (backend + services)
└── docker-compose.yml               # Local multi-service container setup
```

---

## Running it locally

Full step-by-step setup — backend, mobile dev client, tests, the works — lives in its own doc rather than cluttering this page: **[docs/LOCAL_SETUP.md](docs/LOCAL_SETUP.md)**.

---

## Author

Built by [Ritesh Bonthalakoti](https://github.com/riteshbonthalakoti) — an experiment in how far real agronomic data and a bit of care about degradation paths could take a farmer-facing app, without pretending to be smarter than it is.

Licensed under [MIT](LICENSE).
