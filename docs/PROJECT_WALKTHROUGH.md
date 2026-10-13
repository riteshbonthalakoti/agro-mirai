# AGRO MIRAI: Project Walkthrough (for the Project Manager)

Status as of 2026-09-24. VTU Sem 7 capstone, BITM Dept. of AIML.

## 1. What it is

An AI-driven farm advisory system for smallholder farmers (pilot region: Bellary / Karnataka).
A farmer signs in on a mobile app, registers a field, and receives:

- a **crop recommendation** (which crop suits this field),
- **irrigation advice** (how much to water and when),
- a **disease-risk alert**, plus **leaf-photo disease scanning**,
- a combined **daily advisory** that can be read aloud in English, Kannada, Telugu or Hindi.

## 2. How it works (one paragraph)

The backend pulls live **weather** (Open-Meteo), **soil** (SoilGrids) and **satellite NDVI** (Google Earth Engine,
with a local cache as fallback). It turns these into a feature set and feeds trained models. A decision engine combines
the model outputs into one advisory, and each output carries a plain-language reason ("what mattered most: rainfall,
humidity, nitrogen"). The mobile app talks only to the REST API.

## 3. What is a trained model and what is a rule (honest breakdown)

| Capability | How it is produced |
|---|---|
| Crop recommendation | Trained RandomForest (22 crops). Held-out accuracy 99.55%. Explained with SHAP. |
| Irrigation urgency | Trained RandomForest. Held-out accuracy 72.4%, macro-F1 0.58. |
| Irrigation depth (mm) | Formula: FAO-56 water balance (ET0 x crop coefficient minus rainfall). Not ML. |
| Disease risk from weather | Rule-based weighted score. Not trained (no labelled dataset exists). |
| Leaf-photo disease check | Trained CNN (MobileNetV2, 38 classes, 99.24% on PlantVillage). Runs as its own service. |
| Voice (translate / speech-to-text / text-to-speech) | AI4Bharat models in a separate container. |

Known model limitations: PlantVillage accuracy is from lab-style images and is expected to drop on real field photos;
only 4 of its crops overlap with the app's crop list; the crop model can suggest crops uncommon in Bellary, in which
case the app shows a regional caveat.

## 4. Architecture and deployment (Render, all live)

| Service | Role |
|---|---|
| `agro-mirai` | Main API (Flask): auth, fields, advisories, admin, feedback |
| `agro-mirai-tabular` | Crop and irrigation models plus SHAP explanations |
| `agro-mirai-cnn` | Leaf-disease image model (ONNX) |

- Database: Supabase Postgres in production, SQLite in development, behind one repository interface.
- A GitHub Actions job pings all three services every 12 minutes so the free tier does not sleep.
- CI runs the test suite and contract checks on every push. Backend suite: 311 tests passing in the areas touched today.
- Every external dependency degrades instead of failing (satellite -> cache, image model -> weather rules,
  tabular service -> retry then local, voice down -> clear 503 so the app falls back to on-device speech).

## 5. Mobile app (Expo / React Native)

Launch flow:

- **Not signed in:** logo animation -> language choice (English, Telugu, Hindi, Kannada) -> permissions (location,
  camera, gallery, microphone, notifications) -> sign in with name + phone + OTP -> add first field -> guided tour.
- **Signed in:** logo animation -> straight to Home.

Screens: Home (crop, irrigation, disease risk, each with the model's reasoning and confidence), Field Data
(weather, soil, satellite), Advice (daily advisories, voice, feedback), Scan (leaf photo), Me (profile, language, fields).

Added this cycle: spotlight app tour on the real tabs; notification system (themed in-app banner, inbox with bell
and unread badge, system notifications when backgrounded); dismissible sign-in notices; Terms and Privacy sheets;
splash video hand-off fixes.

## 6. This cycle: what was found and fixed

- **Advisories were crashing (HTTP 500) in production.** The main service no longer ships model files, but the
  explanation step still tried to load them. Fixed: explanations now come from the tabular service (real SHAP),
  with a safe fallback. Also added a retry for dropped connections between services.
- **Verified in production** via the Render CLI and live calls: all three services healthy; recommendation,
  irrigation, disease-risk and advisories all return 200 for a fresh test farmer; advisory text now cites real
  model factors and water-balance numbers. No errors in the post-deploy logs.
- **Scan "422" was not a bug:** the photo failed the built-in "does this look like a leaf" check.

## 7. Open items and risks (please track)

| # | Item | Owner needed |
|---|---|---|
| 1 | **Real push notifications** (app fully closed) need a dev/release build, a Firebase/FCM project, and a backend device-token endpoint. Not built. | Ritesh (Firebase account) + dev |
| 2 | **OTP is written to server logs**; no SMS provider is wired up. Must be replaced before real users. | Dev + SMS vendor decision |
| 3 | **CNN service token**: confirm `CNN_SERVICE_TOKEN` matches on the main and CNN services, then test with a real leaf photo. | Ritesh (Render dashboard) |
| 4 | **New APK not yet built**; latest app changes are tested through Expo Go only. Full Gradle build has been dry-run validated, not executed. | Dev |
| 5 | **Terms / Privacy text is a draft**; needs legal review. Kannada/Telugu/Hindi strings need a native-speaker read. | PM / legal / reviewers |
| 6 | Irrigation SHAP explanation is disabled on the 512 MB free tier (shows the water-balance numbers instead). | Infra decision (paid tier) |
| 7 | Free-tier hosting limits: memory-bound, cold starts mitigated only by the keep-alive job. | Infra decision |
| 8 | One test farmer (+919000000042) remains in the production database. | Ritesh (delete in Supabase) |

## 8. Suggested next steps

1. Build the release APK and run a field-user test on a real device (tour alignment, notifications, splash).
2. Close items 2 and 3 above (they gate any real-user pilot).
3. Decide on push notifications: approve the Firebase setup and the small backend addition.
4. Collect pilot-farmer feedback through the in-app feedback and rating flow already built.

## 9. Where to look

- Architecture: `docs/architecture.md`; decisions: `decisions/` (ADR 0001 to 0026)
- Mobile onboarding / tour / notifications: `docs/MOBILE_ONBOARDING_NOTIFICATIONS.md`
- Progress log: `PROGRESS.md`; API contract: `specs/core/openapi.yaml`
- Live API: https://agro-mirai.onrender.com
