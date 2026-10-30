# AGRO MIRAI — Project Q&A

100+ questions a faculty member, evaluator, or curious teammate might actually ask, with honest, verified answers grounded in the current codebase (not the older `PROJECT_DEEP_DIVE.md`, which has drifted out of date in a few places — see the correction notes at the bottom). Read a few of these aloud before a demo; they're written to be said, not just read.

---

## 1. Architecture & Stack

**Q: What's the overall architecture?**
A Flask (Python) backend exposes a REST API (`/v1` and `/v2`), talking to either SQLite (local dev) or Supabase Postgres (production) through one shared repository interface. A React Native/Expo mobile app is the only real client. Three external data adapters (weather, soil, satellite NDVI) sit behind one shared interface so the rest of the backend never talks to a specific vendor directly.

**Q: Why Flask and not FastAPI/Django?**
Flask was already the established choice early in the project and the team never hit a limitation that justified a rewrite. It's thin enough that the actual architecture — the repository interface, the AI-provider cascades — does the real work, not the framework.

**Q: Why React Native/Expo instead of a native Android app or Flutter?**
One codebase targets Android (the realistic target for the farmer audience) while keeping the option open for iOS later, and Expo's managed-but-extensible workflow (config plugins, custom native modules when needed — see the SMS Retriever module) gave native capability without hand-maintaining a full native project for day-to-day feature work.

**Q: What's the mobile app's state management?**
A single React context (`AppCtx`/`ctx.tsx`) holds farmer, field, language, and account state; each screen fetches its own data via a small `useLoad` hook that handles loading/error/cache states consistently rather than a global store like Redux — the app's data needs are per-screen, not deeply shared.

**Q: Why TypeScript strict mode?**
Catches an entire class of bugs (wrong field names, null handling) before they reach a farmer's phone, where a crash is much harder to debug than in development.

**Q: Why MapLibre instead of Google Maps?**
No Google Maps API key/billing dependency, and no Google Play Services requirement for the map itself — important for a low-end-Android, rural-connectivity target audience where every added dependency is a new failure point.

**Q: What does the account/auth model actually look like?**
Phone number + OTP, no password. A farmer signs in with their phone, receives an OTP via SMS, and a session is established server-side (Module 19's `/v2` session auth) rather than issuing a long-lived client-side token that would need its own refresh/revocation logic.

**Q: Can one phone/device hold multiple farmer accounts?**
Yes — the app has an "add account" flow (`AddAccountScreen`) that lets a device switch between multiple signed-in farmer profiles, each with its own session, useful for one family member helping another set up the app.

---

## 2. Database & Multi-Tenancy

**Q: How is one farmer's data kept separate from another's?**
Every table that holds farmer data has Row-Level Security enabled directly in Postgres (`supabase/migrations/20261015000001_add_rls.sql`), not just an application-level filter. Tables with a direct `farmer_id` column (fields, conversations) are scoped `farmer_id = auth.uid()`; tables one hop away (advisories, crop recommendations, disease alerts, irrigation advice) are scoped via a sub-select through `fields`. Even a bug in the application code can't leak another farmer's row, because the database itself refuses the query.

**Q: Why enforce this at the database level instead of just checking in the API code?**
Defense in depth. An application-level check is one `if` statement away from a mistake; a database-level RLS policy is enforced on every single query regardless of what code path reached it, including a future endpoint nobody remembers to add the check to.

**Q: What's `auth.uid()` — how does Postgres know which farmer is making the request?**
Supabase's auth layer embeds the authenticated user's ID in the JWT used for that connection; `auth.uid()` reads it directly from the current session, so the RLS policy doesn't need to trust anything the application claims.

**Q: Why SQLite for local dev and Postgres/Supabase for production — doesn't that risk behavior differences?**
The `DataStore` repository interface (`persistence/`) is implemented once for each backend against the exact same method signatures and the exact same domain dataclasses (`Farmer`, `Field_`, `WeatherReading`, etc.) — nothing above that interface (API routes, business logic) knows or cares which one is active. `tools/seed_fixture.py` round-trips the same fixture through both backends specifically to catch any divergence.

**Q: Is the admin dashboard a separate database, or the same one?**
Same database — it's a thin read/write UI over the same `DataStore`, authenticated separately (an admin role check), not a parallel data store.

**Q: What happens on a schema change — do you edit old migrations?**
No — migrations are append-only (new files only, see the project's own hard rule in `CLAUDE.md`). Editing a migration that's already run against a real database silently desyncs anyone who already applied the old version.

---

## 3. AI/ML — What's Actually Learned vs. Rule-Based

**Q: Is the crop recommendation a trained machine-learning model?**
Not anymore — this is the single biggest thing that changed since the project's own older internal notes. It used to be a Random Forest trained on a generic Kaggle dataset, but that model needed plant-available N/P/K data the system never actually has for a real field, so live picks were wrong (it suggested watermelon for a cotton field). It now ranks all 22 known crops with FAO EcoCrop agronomic ranges — temperature, soil pH, soil texture, a seasonal/rainfall check (`models/ecocrop.py`) — pure rule-based scoring, no training data, no model file.

**Q: So there's no AI/LLM involved in crop recommendation at all?**
There is, but as a parallel first opinion, not the old trained classifier. `api/crop_llm.py` asks a free-tier LLM (via the same OpenRouter/Groq key-rotation pool described below) to recommend a crop from the same live weather/soil/NDVI/location data, with a strict JSON-only response schema. If that succeeds and returns a crop within the 22 known labels, it's used (`source: "llm"`); if the LLM tier fails, returns malformed JSON, or names a crop outside the known set, the system falls back to the deterministic EcoCrop ranking (`source: "ecocrop_rules"`) — never a hard failure either way.

**Q: How do you know the LLM's pick isn't nonsense for the farmer's actual region?**
A separate "regional-suitability sanity layer" (`models/regional_suitability.py`) checks the top pick against a small, source-cited list of crops actually confirmed grown at scale in the target district (cross-checked against three independent agricultural sources — an ICAR/state-university contingency plan, Wikipedia's district agriculture census figures, and an agricultural statistics site). If the recommended crop isn't on that list, the response is flagged `out_of_region: true` with a regional alternative suggested — this is deliberately a flag, never a silent override, so the farmer still sees what the model actually picked plus an honest caveat, not a result the system quietly substituted. This flag used to only apply when the EcoCrop rule-based tier produced the pick; a bug meant an LLM-tier pick skipped the check entirely (fixed this session — see §9).

**Q: Is the irrigation recommendation learned or rule-based?**
Hybrid, and deliberately so. A trained Random Forest classifier (scikit-learn, Kaggle's "Irrigation Water Requirement Prediction Dataset," 10,000 rows) predicts a 3-class urgency tier — Low/Medium/High — nothing more. The literal "how many millimetres of water" figure a farmer actually sees comes from a separate, transparent FAO-56-style soil-water-balance calculation, keyed off that predicted urgency. The model was never trained to output a depth-in-mm number, so the system doesn't pretend it was.

**Q: What's the irrigation model's actual accuracy?**
72.4% accuracy, 0.58 macro-F1 on held-out data (documented alongside the training script, not just claimed). The macro-F1 gap versus raw accuracy is because the "High" urgency class is a small slice of the source data (336 of 10,000 rows) even with class-balanced training weights — a known, honestly-documented property of the dataset, not something papered over.

**Q: Why hybrid instead of just training a regression model to output mm directly?**
No dataset available maps real field conditions to a verified mm figure; inventing a fake regression target to make a model "look" like it predicts a number it was never actually trained to predict would be dishonest about what the model learned. The soil-water-balance calculation is an established agronomic method (FAO-56), transparent and auditable, rather than a black box pretending to be more sophisticated than it is.

**Q: Where do the live water/rain/soil numbers on the Home screen actually come from?**
`models/irrigation_prediction_model.py`'s `method: "soil_water_balance"` computation over real weather history and forecast data (via the Open-Meteo adapter) for that specific field's location — not hardcoded, not a placeholder. Verified directly in the model code, not assumed.

**Q: Is the leaf disease detection a trained model?**
The live path is a vision-model pipeline (an LLM with image input), not a classically trained image classifier — see §5 below for the full flow. A self-contained CNN (MobileNetV2, trained on the public PlantVillage dataset, 38 disease classes, ~99% accuracy on its own held-out test set) does exist in the codebase as an earlier, alternate path, but it's not the one live in the app today.

**Q: Why move off the CNN if it had 99% accuracy?**
That 99% is on PlantVillage's own curated, clean-background training images — not representative of what a real farmer's phone camera captures in an actual field (poor lighting, cluttered background, motion blur). The vision-model pipeline generalizes far better to real conditions, at the cost of needing a network call instead of running fully offline.

---

## 4. The SMS OTP System

**Q: How does a farmer actually receive the OTP — do you use a paid SMS gateway like Twilio?**
No — a specific low-cost setup for this scale of project: a spare Android phone with an Indian SIM runs the free "SMS Gateway for Android" app in cloud-relay mode. The backend POSTs the message to that app's hosted API, and the phone relays it as a genuine SMS from its own number. It's free, but throttled by whatever the carrier allows and depends on that spare phone staying powered and connected — a real, documented tradeoff for a demo/early-stage project, not something hidden.

**Q: How does OTP autofill actually work — is the farmer typing the code in manually?**
Two real Android mechanisms run in parallel, both of which need no SMS/phone permission at all (a key reason they're used over just reading the inbox directly):
1. **SMS Retriever API** — the OS silently hands the full SMS body to the app, but only for a message containing an 11-character hash computed from the app's own package name + signing certificate, appended to the message text. It requires Google Play Services and the message to stay under a hard 140-byte limit.
2. **SMS User Consent API** (added this session as a fallback) — shows a one-tap system dialog, "Allow AGRO MIRAI to read this SMS?", for the next matching message. It needs no hash match in the message at all, which is exactly why most Indian banking apps lean on it as the more reliable of the two.
Whichever resolves first fills in the code automatically; manual entry always still works as the ultimate fallback regardless of either succeeding.

**Q: Why did OTP autofill not work for a while even with the hash correctly set?**
Two real, found-and-fixed bugs, not one. First, the hash itself was wrong for months (computed from the wrong value) — recomputed directly from the real release-signing certificate via `keytool` + the documented Google algorithm. Second — found after that fix still didn't resolve it — the Hindi/Kannada/Telugu SMS templates ran 193–251 bytes once UTF-8's 3-bytes-per-character cost for those scripts was counted, which silently blows past the SMS Retriever API's 140-byte hard limit (English stayed under it the whole time, which is why it looked like a partial fix). Both are fixed; the templates are now short enough in every language to leave headroom for the hash.

**Q: What's the app-signing hash, concretely, and how is it computed?**
`base64(SHA-256(package_name + " " + SHA-256(signing_certificate_DER_bytes)))`, truncated to the first 11 characters — the standard Google "AppSignatureHelper" algorithm, computed identically on both sides: once on the backend (an env var, `SMS_APP_HASH`) and once on-device at runtime by the app's own native module (`mobile/modules/sms-retriever`, `getAppSignatures()`), so the two can be directly compared if they ever drift.

**Q: Does the SMS Retriever mechanism require any special user permission?**
No — that's the entire point of using it over directly reading the SMS inbox, which would require the sensitive `READ_SMS` permission (a real privacy/Play-Store-policy concern for inbox-wide access). Both Retriever and User Consent are scoped to exactly one incoming message, with no standing permission grant.

---

## 5. The Leaf Disease Vision Pipeline

**Q: Walk through what happens end-to-end when a farmer scans a leaf.**
1. A cheap, fully local pixel-level pre-check on the device rules out an obviously-wrong photo (near-solid-color, etc.) before spending any network call on it.
2. The image is sent to a vision-capable LLM with a strict yes/no prompt: "is this genuinely a plant leaf?" — this gate exists because an earlier, more permissive version of the pipeline would occasionally return a confident diagnosis for a photo of literally anything.
3. If it passes, a second, purpose-built vision prompt identifies the plant, decides whether it shows disease symptoms, names the likely disease, gives a confidence level, and a recommended action.
4. In parallel/as a fallback, Kindwise's specialist plant-ID APIs (crop.health for disease, plant.id for species) add a second, independently-sourced opinion.
5. If no tier can produce a real result, the API returns an honest "analysis unavailable" response — never a cached or guessed diagnosis dressed up as real.

**Q: What model actually powers the vision gate and analysis today?**
OpenRouter (primary) with Groq as a fallback — not Gemini, which an earlier internal doc still describes; that changed this project cycle after Gemini proved unreliable in live testing (slow, inconsistent retries on transient errors). `api/vision_client.py` tries every configured OpenRouter key, then every Groq key, on any retryable failure (429 rate limit, 5xx, timeout, network error) before giving up.

**Q: Why rotate across multiple API keys instead of just one?**
Every provider used here (OpenRouter, Groq, Gemini, Sarvam) is on a free tier with a modest per-key daily request cap. A shared `KeyPool` utility (`api/key_pool.py`) reads `{PROVIDER}_API_KEY_1`..`_N` from the environment and round-robins across them, marking a key rate-limited (with a cooldown) or successful as it goes — the same pattern used identically everywhere a cascade of external AI keys exists in this codebase, not a one-off hack.

**Q: Does adding more keys multiply your quota? Can't you just add 10 keys from the same account?**
No — and this was a real point of confusion resolved directly this session. The free-tier quota (e.g. OpenRouter's ~50 requests/day) is tied to the underlying account, not the key string. Ten keys generated from the same account still share one account's quota; only keys from genuinely different accounts add up. This was verified directly against OpenRouter's own `/api/v1/auth/key` endpoint, which returns a `creator_user_id` — the only reliable way to tell two keys apart by account rather than by string.

**Q: Does the system store the photo anywhere, or just the diagnosis?**
The scanned photo itself is stored server-side (resized, compressed to a base64 data URI — no separate file-storage service exists yet) so it survives a reinstall, a new device, or logging in again — added specifically because farmers wanted their scan history to persist, not just the text result.

---

## 6. Deployment & Hosting

**Q: What's actually deployed where?**
- **Backend** (Flask API): Render, free tier.
- **Database**: Supabase-managed Postgres in production; SQLite for local dev — same `DataStore` interface either way.
- **Landing page + APK download**: Vercel, as a static site; the APK itself is hosted on Vercel Blob storage (a CDN-backed object store), not committed to the git repo.
- **Admin dashboard**: also Vercel, proxying API calls back to the Render backend via `vercel.json` rewrites.

**Q: How does CI/CD actually work — is it fully automated on every push?**
Honestly, partially. The Render backend auto-deploys on a push to `main` via its own GitHub integration. The Vercel landing page, in its current state, deploys via the Vercel CLI run manually rather than through a GitHub-webhook auto-deploy — a real, specific thing to be upfront about if asked "show me your CI/CD pipeline," rather than claiming a fully automated pipeline that isn't quite there yet for that one piece.

**Q: Why Render specifically, and what's the one non-obvious operational lesson from running it?**
Render was chosen for a genuinely free, always-on (not serverless-cold-start-per-request) tier suited to a small Flask app. The one real lesson learned the hard way: Render's `/restart` endpoint does not reliably reload environment variables for a running service — a changed API key can silently keep using the old value. A `POST /deploys` with `clearCache: "do_not_clear"` creates a genuinely fresh deploy that's guaranteed to read the current environment, and is now the only way this project ever rotates a credential in production.

**Q: Does the free Render tier have a cold-start problem?**
Yes, normally — Render's free tier spins a service down after 15 minutes of no traffic, producing a 50-60 second delay on the next real request. A scheduled GitHub Actions workflow pings the backend's `/health` endpoint on a fixed interval, forever, at zero cost, so the service is effectively never actually asleep when a farmer opens the app.

**Q: Why Vercel Blob for the APK instead of just committing it to the repo or GitHub Releases?**
GitHub itself works fine as a secondary distribution point (every release is tagged and published there too), but Vercel Blob gives the landing page's direct-download button and a dedicated `/download` page genuine CDN-backed delivery (Accept-Ranges, proper Content-Disposition, no-transform headers) tuned specifically so Android's download manager doesn't stall or get stuck at 99% on a large binary — a real, previously-encountered failure mode this setup exists to avoid.

---

## 7. Security & Privacy

**Q: What prevents one farmer from reading another farmer's field/advisory data?**
Covered in depth in §2 — Postgres Row-Level Security, enforced at the database layer regardless of which API code path is hit.

**Q: Are API keys and secrets committed to the repository?**
No — all of them live in environment variables (`.env`, gitignored locally; set directly in Render's/Vercel's own environment configuration in production), with `.env.example` documenting every variable's purpose without real values.

**Q: Is there a password anywhere a farmer has to remember?**
No — phone number + OTP only. No password to leak, forget, or reuse across services.

**Q: What happens if a required third-party AI service is down or a key is exhausted?**
The project-wide rule is to degrade honestly, never fabricate. Every AI-backed feature (voice, vision, crop/irrigation advice, chat) returns a clear "unavailable right now" response once every configured key/provider in its cascade is exhausted or failing — never a cached, guessed, or placeholder answer presented as if it were real.

---

## 8. Offline/Reliability Design

**Q: Does the app work with no internet connection?**
Partially, by design — it's local-first for already-fetched state (cached field data, advisories, scan history render from on-device storage even offline), but anything needing a fresh computation or AI call genuinely requires connectivity; the app is explicit with the farmer about which is which rather than pretending to work offline end-to-end.

**Q: What happens to NDVI (satellite vegetation index) data if the live Earth Engine query fails?**
A live Google Earth Engine query against Sentinel-2 imagery is attempted first, bounded by a timeout. On failure, it falls back to a local cache seeded ahead of time from real Earth Engine pulls (never fabricated). If even the cache misses, the system returns an honest "unavailable" rather than inventing a plausible-looking number. Every reading carries a `source` field (`gee_live` vs. `cache`) so this is traceable, not hidden.

**Q: How are push notifications implemented — a custom in-app inbox?**
No — real Android OS notifications via a proper notification channel (`expo-notifications`), deliberately with no separate in-app notification center to maintain as a second piece of state that could drift out of sync with what actually happened.

---

## 9. Known Limitations & Honest Tradeoffs

**Q: What's the biggest known weakness in the system right now?**
The SMS OTP delivery path (a spare Android phone relaying via a free gateway app) is inherently less reliable than a paid SMS provider — it depends on that phone staying powered, connected, and not carrier-throttled. It's a deliberate cost tradeoff for a free/early-stage deployment, with the SMS User Consent fallback added specifically to reduce how much that fragility shows up as a farmer-facing failure.

**Q: What's a bug you found and fixed recently that's worth being upfront about?**
The crop-recommendation "regional fit" sanity check (§3) only ever ran for the rule-based EcoCrop tier — an LLM-tier pick could land outside the known-grown-in-region crop list with no caveat shown at all, which is exactly the kind of silent gap that erodes trust in an agricultural advisory tool. Fixed by running the same check regardless of which tier produced the pick.

**Q: Is every number shown to the farmer backed by a real computation, or is some of it still placeholder/demo data?**
A specific, explicit audit was run this session for exactly this question across the whole codebase. Six functions in the mobile client were found fabricating plausible-looking fallback data in a `catch` block instead of propagating a real error (disease scans, crop/irrigation recommendations, advisories, voice Q&A) — all six were found and fixed to let the real error surface honestly instead. A follow-up full-codebase sweep for any further mock/hardcoded data or dead/unwired UI turned up nothing further.

**Q: Why wasn't the irrigation model trained to higher accuracy?**
72.4%/0.58 macro-F1 reflects genuine class imbalance in the only suitable public dataset found (the "High" urgency class is 336 of 10,000 rows) — documented as a known property rather than hidden or inflated, and acceptable given the actual depth-in-mm number shown to the farmer comes from the separate, more trustworthy water-balance calculation rather than the classifier's raw output.

**Q: What would you build next if you had more time?**
A paid, higher-reliability SMS provider to remove the spare-phone dependency; a true git-webhook CI/CD pipeline for the landing page to match the backend's; and extending the regional-suitability crop list beyond the one currently-covered district, since it's currently sourced and verified for only one specific region.

---

## 10. Field Mapping & Location

**Q: How does the map tab show a farmer's field?**
During registration a farmer sets their field's GPS coordinates and enters how many acres it covers; the map then draws a circular boundary centered on that pin, sized so its area matches the farmer-entered acreage — a visual sense of the field's extent without asking the farmer to trace an actual polygon by hand on a small phone screen.

**Q: Does the map show the farmer's live phone location too, or just the field?**
Both, but as two separate, deliberately non-overlapping layers the farmer can toggle between — "my phone" (live device GPS) and "my field" (the fixed, farmer-entered boundary) — fixed this session after they were rendering on top of each other with no way to view just one.

**Q: Why a circular approximation instead of letting the farmer draw the real field shape?**
Hand-tracing an accurate polygon on a small phone touchscreen, often outdoors in bright sunlight, is a genuinely hard input task for the target audience; a circle sized to the farmer's own stated acreage gives an honest visual sense of scale without demanding a precision the input method can't reliably deliver.

**Q: Can a farmer have more than one field?**
Yes — the account/field model supports multiple fields per farmer, each independently tracked for weather, soil, crop, and advisory purposes.

---

## 11. Voice & Multilingual Support

**Q: What languages does the app actually support?**
Four: English, Hindi, Kannada, and Telugu — chosen as a first-run language picker before anything else, since the target farmer may not be comfortable in English at all.

**Q: How does voice input/output actually work?**
A single internal voice interface sits in front of whichever backend does the real work, so no screen talks to a vendor SDK directly. In production that's Sarvam AI — `saaras` for speech-to-text, `bulbul` for text-to-speech, `sarvam-translate` for translation — called via REST, rotating across multiple API keys through the same `KeyPool` pattern used for every other AI provider in this project.

**Q: Is there a self-hosted/offline alternative to the cloud voice stack?**
Yes, built end-to-end as a heavier alternative tier on AI4Bharat's open models (IndicTrans2 for translation, IndicConformer for multilingual ASR, Whisper-tiny.en for English specifically since AI4Bharat's own ASR line is Indic-languages-only, Piper for text-to-speech) — validated to run on a modest 4GB-RAM machine, with one honestly-documented caveat: the ASR model takes roughly two minutes to load into memory the first time a process starts, which is why it's loaded once at startup rather than per request.

**Q: What happens if the voice cloud tier is exhausted or unreachable?**
A clear, localized "voice unavailable, here's the text" message in the farmer's own language — never a silent failure, and never falling back to English when the farmer's language is something else.

**Q: Does the app translate farmer-facing advisory text on the fly, or is everything pre-translated?**
A mix. UI strings are pre-translated (a per-language lookup table). Server-generated free text — an AI-written disease description, a crop recommendation's rationale — is translated on demand via the same voice/translation interface and cached once translated, rather than pre-translating every possible AI-generated sentence ahead of time, which wouldn't be possible when the text itself is generated per request.

---

## 12. The Chat Assistant

**Q: Is the chat assistant a separate product from the rest of the advisory features, or does it share data?**
It's grounded in the farmer's own real stored records — it attaches structured "cards" built from the farmer's actual saved crop recommendation, irrigation advice, or disease alerts where relevant, rather than answering purely from the LLM's general knowledge with no connection to that specific farmer's actual field.

**Q: What happens if every chat LLM key is exhausted?**
A rule-based fallback reply is built directly from the farmer's own most recent real saved advisory — still real stored data, clearly labeled with its own `source` field, never a fabricated answer standing in for the LLM.

**Q: Does chat history persist, or does it reset every time the app restarts?**
It persists server-side per session (`chat_sessions`/`chat_messages`, Module 58) — a farmer can close the app, reopen it later, or even switch devices, and their conversation history is still there.

**Q: How many free-tier chat API keys does the system rotate across, and does adding more always help?**
As many as are configured via the same `KeyPool` env-var pattern as every other AI cascade in this project — but only if each key is confirmed from a genuinely different underlying provider account; this was directly and specifically verified this session (via OpenRouter's own account-identity endpoint) after discovering that several previously-configured keys all traced back to one account and were not actually adding any quota at all.

---

## 13. Admin Dashboard & Operations

**Q: What can the admin dashboard actually do?**
A read/write operational view over the same `DataStore` — farmer/field lookups, and administrative write actions, each one recorded to an append-only audit log (`AuditLogEntry`: who, what action, what target, a before/after JSON snapshot) so every admin change is independently traceable after the fact.

**Q: Who can access the admin dashboard — is it the same login as the farmer app?**
A separate admin-role check, not the regular farmer phone+OTP flow — the admin surface is an internal operational tool, not a farmer-facing feature.

**Q: Is admin activity itself subject to the same RLS isolation as farmer data?**
The audit log table is explicitly service-role-only — the admin write path is reached only by the backend's own service account, never routed through the regular farmer-scoped client connection.

---

## 14. Testing & Code Quality

**Q: What does the test suite actually cover?**
Backend: `pytest` over the API routes, the repository interface (both SQLite and Supabase-backed, via the shared fixture round-trip), and the business logic in the models/advisory layer. Mobile: `jest` plus TypeScript's own strict-mode compiler check (`tsc --noEmit`), run after every change as a baseline correctness gate before anything ships.

**Q: What's the project's own stated policy on hardcoded/mock data in real (non-test) code?**
An explicit, zero-tolerance rule, repeated throughout this session's own work: no fabricated response data standing in for a real computation or a real error, anywhere in a live code path. When something genuinely can't be computed (a missing key, an unreachable service), the honest answer is a clear "unavailable" response, never a plausible-looking guess.

**Q: How do you verify a bug fix actually worked, versus just assuming the code change is correct?**
Wherever possible, against the real, live thing — a real API call against a real external service to confirm a key works, a real device recording to confirm a visual bug is actually gone, a real computed hash compared byte-for-byte against what the running app computes — rather than trusting that a code change "looks right" on inspection alone. Several bugs this session (a wrong SMS hash, a byte-length limit, a missing regional check) were only caught by this kind of direct verification, not by reading the code and assuming it was fine.

---

## 15. Notifications & Reminders

**Q: How do disease-risk or reminder notifications actually get to the farmer?**
Real Android OS notifications through a proper notification channel (`expo-notifications`) — not a custom in-app inbox. A farmer can also set a daily reminder time for general crop advice, handled by a local scheduled notification rather than a server-side push for something that doesn't need network round-tripping.

**Q: Can a farmer turn notifications off?**
Yes — a settings toggle controls both haptic/sound feedback and the daily reminder independently; declining notification permission at the OS level also degrades gracefully rather than breaking the rest of the app.

---

## 16. Data Sources

**Q: Where does the weather data come from, and does it cost anything?**
Open-Meteo — current conditions, forecast, and historical data, no API key required at all, chosen specifically because a free, keyless weather source removes one entire class of "ran out of quota" failure for a core, constantly-needed feature.

**Q: Where does soil data come from — does the app read an actual soil sensor?**
No physical sensor — ISRIC SoilGrids v2, a global soil-property grid (pH, texture, N/P/K-adjacent properties), also free and keyless. The system specifically uses the topsoil band (0–5cm), the layer closest to where a farmer's own hand soil test would actually sample.

**Q: What's NDVI and why does the app need Google Earth Engine for it?**
NDVI (Normalized Difference Vegetation Index) is computed from satellite imagery — `(near-infrared − red) / (near-infrared + red)` — as a proxy for how healthy/green a crop canopy currently looks, pulled from the most recent low-cloud Sentinel-2 scene over the field via Google Earth Engine, the one data source in the stack that does need a paid-tier-adjacent service account key.

---

## 17. Scaling & Cost

**Q: What's the actual monthly cost to run this today?**
Effectively free at current scale — Render's free backend tier, Supabase's free Postgres tier, Vercel's free hosting/Blob tier, and every AI provider (OpenRouter, Groq, Sarvam) on a free-tier key-rotation pool. The real constraint isn't dollars, it's free-tier request quotas, which is exactly why the `KeyPool` rotation pattern exists everywhere.

**Q: What would actually need to change to support, say, 10,000 farmers?**
Paid tiers across the board — a real SMS provider instead of the spare-phone relay, paid AI API tiers instead of free-key rotation, and Render/Supabase's paid tiers for guaranteed uptime and higher connection limits. None of the current architecture would need a rewrite to get there; it's a configuration/budget change, not a redesign, because the repository-interface and provider-cascade patterns were built to make exactly that kind of swap low-risk.

---

## 18. "Why X Over Y" Comparison Questions

**Q: Why Supabase over a self-managed Postgres instance?**
Managed Postgres plus built-in auth, Row-Level Security tooling, and a generous free tier — avoids operating database infrastructure directly for a project at this scale.

**Q: Why SQLite for local dev instead of running a local Postgres too?**
Zero setup — no separate database server to install/run locally — while the shared `DataStore` interface guarantees it exercises the exact same code path as production, just a different backend underneath.

**Q: Why OpenRouter/Groq over calling OpenAI or Anthropic directly?**
Free-tier access to capable models without a paid API commitment, suited to an early-stage/student project's budget — with the explicit tradeoff (documented and tested directly, not assumed) that free tiers cap out around 50 requests/day per account, which is exactly why the key-rotation pool pattern exists everywhere in this codebase.

**Q: Why EcoCrop agronomic rules over re-training a better crop classifier?**
No reliable labeled dataset exists that maps real field conditions (as actually measurable for this app — no real soil N/P/K sensor, for instance) to a verified best-crop outcome for the target region; a transparent, explainable rules engine grounded in established agronomic science (FAO EcoCrop ranges) was judged more trustworthy for farmer-facing advice than a model trained on a mismatched proxy dataset, which is exactly what went wrong with the original Random Forest approach.

**Q: Why MapLibre over Google Maps or Mapbox?**
No Google billing/API-key dependency (MapLibre); genuinely open-source and self-hostable tile rendering, which matters for a project that may not always have a Mapbox-style paid tile budget.

**Q: Why build a custom native module for SMS Retriever instead of using an existing Expo/React Native library?**
The specific combination needed — SMS Retriever and SMS User Consent integrated together, with a signature-hash dev utility built in for debugging — wasn't available as a single well-maintained existing package; a small, purpose-built native module (under 150 lines of Kotlin) kept full control over exactly how both APIs interact, which mattered once Retriever alone proved unreliable.

**Q: Why phone+OTP login instead of email+password?**
No password to forget, reset, or reuse unsafely, and a phone number is a far more universal, always-on identifier for this specific audience than an email address many farmers may rarely check. An earlier version of the app actually used email+password and was deliberately migrated off it for exactly this reason.

**Q: Why Vercel for the landing page instead of GitHub Pages or Netlify?**
Vercel Blob storage gives genuine CDN-backed binary delivery for the APK download in the same platform as the static site hosting, plus a CLI-driven deploy workflow the team was already comfortable with — one platform for both pieces rather than wiring a CDN and a static host together separately.

**Q: Why render the irrigation depth as a rule-based calculation instead of just trusting the classifier's confidence score as a proxy for "how much water"?**
A classification confidence score answers "how sure is the model this is High urgency," not "how many millimetres" — those are different questions, and conflating them would mean displaying a number with no real agronomic grounding. The FAO-56 water-balance calculation is a separate, purpose-built answer to the actual question being asked.

**Q: Why not just use one single AI provider everywhere instead of maintaining OpenRouter, Groq, Gemini, and Sarvam all at once?**
Each sits in a different part of the system for a reason: Sarvam specifically covers Indic-language speech/translation quality that a general-purpose model doesn't match; OpenRouter/Groq's free-tier vision models power the leaf-scan and chat cascades; Gemini remains in use for other, non-vision features. Consolidating onto one provider would mean accepting its specific free-tier limits everywhere at once, with no fallback diversity if that one provider has an outage.

---

## 19. Team & Process Questions

**Q: How is a new feature or schema change actually built and reviewed in this project?**
Database migrations are additive-only (new files, never editing one already applied); API response field names are treated as a mobile-app contract, so renaming one is a breaking change handled deliberately, not casually; and refactors follow a stated discipline of one file per commit, running the full test suite after every change, with read-only planning before edits on anything non-trivial.

**Q: Is there a written decision log for major design choices, or is reasoning only in code comments?**
Both — a `decisions/` directory holds written rationale for specific architectural calls (e.g. the regional-suitability sanity layer's sourcing, the three-Render-services-to-one consolidation), and the code itself is deliberately comment-heavy at exactly the points where a design choice isn't self-evident from reading the code alone.

**Q: What happens when an AI coding assistant (like the one used to build parts of this) makes a mistake?**
The same verification discipline applies regardless of who/what wrote the code: a claimed fix is checked against a real, live signal (an actual API response, an actual device recording, an actual computed value) before being trusted, and several real mistakes this project cycle — a stale wrong fallback value left in otherwise-fixed code, a build shipped before a just-made fix had actually landed in its bundle — were caught exactly this way, not assumed away.

---

## 20. Quick-Fire Questions

**Q: What's the app's package name/identity on Android?**
`com.ritesh1918.mobile`.

**Q: What Android version does the app target?**
A minimum of Android 9.0+ (API 28+) for the download page's stated compatibility; the release build targets `arm64-v8a` specifically (the dominant architecture on real-world Android phones), keeping the APK smaller than a universal multi-architecture build.

**Q: How is the release APK actually signed?**
A dedicated release keystore (`android/app/release.keystore`), consistently used for every release build via Gradle's signing config — the same certificate every time, which matters directly for the SMS-hash mechanism described in §4, since a different signing certificate would compute a different (wrong) hash.

**Q: Does the backend rate-limit requests?**
Yes — a general per-API-key rate limit (`RATE_LIMIT`, default 60/minute) plus a stricter, separate limit specifically on the OTP-request endpoint (`OTP_RATE_LIMIT`, default 5/minute) to prevent SMS-sending abuse.

**Q: What happens on a request that's too large (e.g. a big bug-report photo)?**
Capped explicitly at the Flask app level (`MAX_CONTENT_LENGTH`, 20MB) — bug-report photos travel as base64-encoded JSON (roughly 14MB for a typical photo), and nothing else in the API needs anywhere near that much.

**Q: Is there error monitoring in production, or do you only find out about a crash when a farmer reports it?**
Sentry integration exists server-side (`SENTRY_DSN` config, wired in at app-factory time) for backend errors; the mobile app also has its own local error log plus an in-app bug-report flow a farmer can use directly, including attaching a photo.

**Q: Does the backend sit directly on the internet, or is there a reverse proxy/load balancer in front of it?**
Render puts one load balancer in front of it, which is specifically why `ProxyFix` is applied in `create_app` — without it, every farmer's request would appear to originate from the load balancer's single IP, making the per-IP rate limits effectively global instead of per-farmer.

**Q: How does the system decide which language to reply in for AI-generated text (chat, disease descriptions)?**
An explicit resolution order: the request's own language override if given, else the farmer's saved `preferred_language`, else English as the final fallback — the same order applied consistently across both the `/v1` and `/v2` route surfaces rather than two separately-maintained implementations that could drift apart.

**Q: Is the project open-source, and under what license is each dataset used?**
The Kaggle crop-recommendation dataset credited in the project's model documentation is Apache-2.0 licensed; the irrigation dataset is MIT licensed — both compatible with the project's own use, and both credited rather than silently used.

**Q: What's the single most important design principle to describe if asked to summarize the whole project in one sentence?**
Every external dependency — a database, a weather source, an AI provider — sits behind one shared interface so it can fail, degrade, or be swapped without the rest of the system needing to know or care, and the system is honest about an "I don't know right now" rather than ever fabricating an answer to look more complete than it is.

**Q: If a faculty member asks "show me, live, that this actually works" — what's the safest live demo path?**
Phone-number sign-in → OTP (manual entry always works as a guaranteed fallback even if autofill doesn't catch it live) → viewing a field's crop recommendation and irrigation numbers (purely computed, no external AI call needed, so it works even with zero API keys configured) → the Scan tab with a real leaf photo, which is the one step genuinely dependent on a live AI-provider key being configured and that key's quota not being exhausted that day.

---

## Corrections made to the older internal `PROJECT_DEEP_DIVE.md` while writing this document

That document is a good architectural overview but has drifted out of date in specific, verifiable ways:

1. **Crop recommendation model**: described as a Random Forest classifier. It is not — it's now a rule-based EcoCrop ranking with an LLM-cascade first opinion (§3). The Random Forest approach was explicitly abandoned after live testing showed it recommending agronomically wrong crops (watermelon for a cotton field).
2. **Leaf disease detection**: described as using Gemini for the vision gate/analysis. The live pipeline now uses OpenRouter (primary) with Groq (fallback) — Gemini was moved off after proving unreliable in live testing (§5).
3. The regional-suitability sanity check and the LLM-tier crop-recommendation path are not mentioned there at all, since they were added after that document was last updated.

This Q&A document reflects the verified current state of the code as of this write-up; treat it as the more current source if the two ever disagree.
