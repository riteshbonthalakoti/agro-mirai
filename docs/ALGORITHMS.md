# AGRO MIRAI — Algorithms Used, and Why

What actually computes each answer in this app, and why that approach was chosen over the obvious alternative. Written from the real, current code — not from an earlier design that later changed.

## Quick reference: what's learned vs. what's rules vs. what's an LLM call

| Feature | Approach | Live path? |
|---|---|---|
| Crop recommendation | LLM (Gemini) first, falls back to a deterministic rule engine (FAO EcoCrop) | Yes |
| Irrigation (depth + urgency) | Deterministic soil-water-balance calculation (FAO-56 style) | Yes |
| Leaf disease detection (Scan tab) | Vision LLM (OpenRouter primary, Groq fallback) | Yes |
| Leaf disease detection (CNN) | Trained MobileNetV2 CNN (PlantVillage dataset) | No — exists in the codebase as an earlier/alternate path, not the live Scan tab |
| Soil-type suggestion | Nearest-match lookup (not learned, not an LLM) | Yes |
| Chatbot | LLM (OpenRouter/Groq cascade) with a rule-based fallback reply | Yes |
| Voice (STT/TTS/translate) | Cloud API (Sarvam) primary, self-hosted AI4Bharat models as a heavier fallback tier | Yes |
| OTP delivery/autofill | SMS relay + Android system APIs (not an "algorithm" in the ML sense) | Yes |
| API key rotation | Round-robin with per-key cooldown | Yes, used by every external AI call in the app |
| Push notification sweep | Rule-based threshold check (irrigation urgency == "high") | Yes |

---

## Crop Recommendation

**What it is now:** an LLM call (Google Gemini, via `crop_llm.py`) is tried first — it's given the field's live weather, soil, location and season, and asked to pick the best crop plus alternatives. If that fails, is unreachable, or replies with something that can't be trusted (a crop name outside the known 22-crop list, malformed JSON), the system falls back to a fully deterministic rule engine: **FAO EcoCrop** climate-range matching (`ecocrop.py`), which scores all 22 known crops against the field's temperature, soil pH, soil texture, and a soft rainfall check, and returns whichever fits best for the current season.

**Why not a trained classifier?** The original plan was a RandomForest trained on a public Kaggle crop dataset. It needed plant-available N/P/K soil values to make a real prediction — data this project can almost never reliably get (SoilGrids, the free global soil-data source used here, doesn't provide phosphorus or potassium at all). Live picks from the trained model were wrong in ways that were obvious even without expert knowledge — the project's own code comment literally says it recommended **watermelon for a cotton field**. EcoCrop's climate-range matching only needs temperature, pH, rainfall, and soil texture — all data this project genuinely has — so it replaced the trained model outright. See `decisions/0027-ecocrop-and-waterbalance-urgency.md`.

**The regional-suitability check:** a separate, Bellary/Karnataka-specific sanity layer (`regional_suitability.py`) checks whether the picked crop is actually grown at meaningful scale in that district, based on cited government agriculture sources. If not, it flags the pick as "not commonly grown in your region" and suggests the closest regionally-common alternative — but it never overrides the pick itself. See `decisions/0016-regional-crop-suitability.md`.

---

## Irrigation Advice

**What it is:** a deterministic **FAO-56-style soil water balance** calculation, not a trained model at all. Daily crop water use (ETc) is computed from reference evapotranspiration (ET0, via the Hargreaves-Samani formula, using temperature and day-of-year) multiplied by a crop-and-growth-stage coefficient (Kc). That daily water use is tracked against actual rainfall received, day by day, to estimate how much of the soil's easily-available water has already been used up. Both the recommended depth-in-mm **and** the urgency level (low/moderate/high) come out of this same balance — there is no separate classifier.

**Why not a trained classifier?** There used to be one — a RandomForest for the urgency tier. Its own measured accuracy was 72%, "barely useful" per the project's own assessment. The water-balance approach answers a more precise, physically-grounded question ("how much of the crop's available soil water is actually gone, and how fast") instead of a coarse three-class guess, and it naturally explains itself (the farmer sees the real numbers: ET0, rainfall received, days until stress) rather than just a label. See `decisions/0015-et0-water-balance.md`.

---

## Leaf Disease Detection (Scan tab — the live path)

**What it is:** a **vision-capable LLM** call — a photo goes to OpenRouter (model: `dots-studio/dots-3-note-preview:free`) first, with Groq (`qwen/qwen3.8-27b`) as the fallback if OpenRouter's key pool is exhausted or the request fails. A separate, stricter prompt first checks "is this actually a plant leaf?" before any diagnosis is attempted, to reject blurry photos, random objects, or screens.

**Why not Gemini (the earlier design)?** Gemini's `generateContent` endpoint was repeatedly unreachable in live testing — connection-level timeouts reproduced from two separate networks, not a key or quota problem, plus its own 503 responses reporting "high demand." OpenRouter and Groq were both verified live with real crop-disease photos (correct, specific diagnoses, not generic guesses) before being wired in.

**Why not the trained CNN?** A MobileNetV2 CNN trained on the public PlantVillage dataset (38 disease classes, ~99% accuracy on its own held-out test set) does exist in the codebase (`image_disease_risk_model.py`, `disease_cnn_labels.py`) as an earlier, self-contained path — but it is **not** what the live Scan tab uses. PlantVillage's training images are clean, lab-background, single-leaf photos; a general vision LLM generalizes far better to what a real farmer's phone camera actually captures in a real field (uneven lighting, background clutter, multiple leaves). The CNN remains available as an alternate/offline-capable classifier, not the production path.

---

## Soil Type Suggestion (new — raised directly by a teammate)

**What it is:** when a farmer picks a soil type (Alluvial/Black/Red/Laterite/...), the app compares the field's real, measured soil chemistry (pH and organic carbon %, fetched from SoilGrids) against each of the 8 soil orders' typical pH/organic-carbon profile, and finds whichever profile is the closest numeric match (a normalized squared-distance comparison, not machine learning). If the farmer's pick differs from the closest match, a non-blocking hint is shown.

**Why a lookup, not a classifier or an LLM?** SoilGrids doesn't predict an Indian soil-order label at all (that's a local agronomic classification, not something a global soil-property model outputs) — there is no single "correct answer" to assert, so this is deliberately framed as a suggestion based on the closest typical profile, not a hard validation rule. A farmer may genuinely know their own field better than a coarse global soil model.

---

## Chatbot

**What it is:** an LLM call (OpenRouter primary, Groq fallback, same key-pool-cascade pattern as the vision pipeline) answers the farmer's question, grounded with the farmer's own real saved data (their fields, latest advisories, recent scans) injected into the prompt so answers reference their actual situation. If every configured key across both providers is exhausted, a **rule-based fallback** builds a reply directly from the farmer's own most recent saved advisory — never a fabricated answer, and clearly distinguishable via a `source` field (`"llm"` vs `"rule_based"`).

---

## Voice (Speech-to-Text, Text-to-Speech, Translation)

**What it is:** **Sarvam AI** (`saaras` for STT, `bulbul` for TTS, `sarvam-translate`) is the primary cloud provider, called via REST with the same key-pool rotation pattern used everywhere else. A second, fully self-hosted tier exists on **AI4Bharat's** open models (IndicTrans2 for translation, IndicConformer for ASR, Whisper-tiny.en for English specifically, Piper/`vits_rasa_13` for TTS) — this heavier stack runs as a **separate microservice** (`services/voice`), never imported into the main API process directly, so the main process stays lightweight (see `decisions/0019-deployment-architecture.md`). If the cloud tier is exhausted or unreachable, the system degrades to a clear "voice unavailable, here's the text" message in the farmer's own language — never a silent failure or a wrong-language response.

---

## OTP Delivery & Auto-fill

Not a machine-learning algorithm — two real mechanisms worth documenting precisely since they came up as a real bug this session:

- **Delivery:** a spare Android phone running the SMS Gateway app relays the OTP as a real SMS, via the `sms_gateway` provider in `otp_providers.py`. The message is kept under Google's **140-byte limit** for the SMS Retriever API specifically (a real bug: the Hindi/Kannada/Telugu templates used to exceed this once UTF-8's 3-bytes-per-character cost was counted, silently breaking auto-fill for non-English farmers).
- **Auto-fill:** two Android system mechanisms run in parallel — **SMS Retriever API** (fully automatic, but requires the app's signing-certificate hash to appear in the message) and **SMS User Consent API** (needs one tap on a system "Allow this app to read this SMS?" dialog, but needs no hash match at all). Whichever resolves first fills the code; manual entry always still works as the ultimate fallback.

---

## API Key Rotation (used by every external AI call in this project)

**What it is:** a provider-agnostic round-robin pool (`key_pool.py`) loads up to N keys from env vars (`{PREFIX}_1`, `{PREFIX}_2`, ...), hands out the next key in rotation on each call, and puts a key on a 60-second cooldown if it comes back rate-limited — skipping cooled-down keys until they recover. Used identically for every OpenRouter/Groq pool (chat, vision, voice/STT) and for Gemini.

**Why round-robin with cooldown, not something smarter?** This project runs on free-tier API keys with per-key daily/per-minute limits. A key that just got rate-limited is very likely to still be limited a second later, so skipping it for a short cooldown (rather than retrying it immediately) avoids wasting requests on a key that's going to fail anyway, while still giving it a chance to recover without needing to track exact reset times per provider.

---

## Push Notification Sweep

**What it is:** a scheduled job (`tools/push_sweep.py`, run every 3 hours via GitHub Actions) runs the same irrigation water-balance calculation described above for every field with a registered device, and sends a push notification if the result is `urgency == "high"` — deduplicated against the field's own saved advice history so a multi-day dry spell doesn't push every single run. Not machine-learned; a direct reuse of the irrigation model's own real output as the trigger condition.
