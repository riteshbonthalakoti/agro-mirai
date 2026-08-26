# Architecture

High-level shape of AGRO MIRAI as it stands after Module 03. Fills in
what was a placeholder through Module 01/02; grows module by module.

## Component map

```
                        ┌─────────────────────────┐
                        │   API layer (Module 11)  │
                        │  FastAPI, /v1/... routes │
                        └────────────┬─────────────┘
                                     │
       ┌─────────────────────────────┼─────────────────────────────┐
       │                             │                              │
┌──────▼──────┐            ┌─────────▼─────────┐          ┌─────────▼─────────┐
│ Recommend/   │            │  Repository        │          │  Data acquisition │
│ advisory     │◄───────────│  interface          │◄─────────│  adapters          │
│ modules      │  domain    │  (DataStore,        │  domain  │  (Module 03,       │
│ (06-09)      │  records   │  Module 04)         │  records │  this module)      │
└──────────────┘            └──────┬─────┬────────┘          └──┬───────┬───────┬─┘
                                    │     │                       │       │       │
                             ┌──────▼┐  ┌─▼───────┐         ┌─────▼┐ ┌───▼───┐ ┌──▼────────┐
                             │SQLite │  │Supabase │         │Open- │ │Soil-  │ │Earth Engine│
                             │(dev)  │  │Postgres │         │Meteo │ │Grids  │ │(Sentinel-2)│
                             │       │  │(prod)   │         │      │ │       │ │ + NDVI     │
                             └───────┘  └─────────┘         └──────┘ └───────┘ │ cache      │
                                                                                 └────────────┘
```

Every arrow crossing a module boundary carries only the entities defined
in `specs/core/schema.yaml` — never an engine-specific row, an HTTP
response body, or a GEE `Image`. That's what makes the repository
interface (Module 04) and the data-acquisition adapters (Module 03, this
document) both load-bearing: they're the only two places allowed to know
what's on the other side.

## Data Acquisition (Module 03)

Three adapters, one shared interface, living in
`src/agro_mirai/acquisition/`:

| Adapter | Source | Entity produced | Key required |
|---|---|---|---|
| `WeatherAdapter` (`open_meteo.py`) | Open-Meteo (`api.open-meteo.com` current+forecast, `archive-api.open-meteo.com` historical) | `WeatherReading` | none |
| `SoilAdapter` (`soilgrids.py`) | ISRIC SoilGrids REST API v2 point query | `SoilSample` | none |
| `NDVIAdapter` (`earth_engine.py`) | Google Earth Engine, Sentinel-2 (`COPERNICUS/S2_SR_HARMONIZED`) | `NDVIReading` | service account (`EE_SERVICE_ACCOUNT_KEY`) |

### Common interface

All three implement `Adapter` (`src/agro_mirai/acquisition/base.py`):

```python
class Adapter(abc.ABC):
    source: str  # the *_source enum value this adapter stamps

    def fetch(self, field: FieldInput) -> list[dict]: ...
```

`FieldInput` is the minimal slice of a `Field` an adapter needs
(`latitude`, `longitude`, optional `field_id`) — built from a full
`Field` record via `FieldInput.from_field(...)`. `fetch` returns a list
of dicts, each conforming exactly to the corresponding schema entity:
correct field names, units (`docs/conventions.md` §5), and ISO 8601 UTC
timestamps (§2). Module 05+ depends on this interface, never on a raw
`requests` call or the `earthengine-api` client directly — those only
appear inside the three adapter modules.

Failures are typed: `SourceUnavailableError` (transport-level — timeout,
5xx, unreachable) and `SourceResponseError` (the source answered but the
payload didn't map to schema), both subclasses of `AcquisitionError`. No
adapter returns an empty list to signal failure.

### Soil: representative depth interval

SoilGrids predicts several depth intervals (0-5cm, 5-15cm, 15-30cm, …).
`SoilAdapter` uses **topsoil, 0-5cm**, as the single representative
sample — the layer closest to what a farmer's own lab test would
actually sample (the plough layer, where fertiliser is applied and pH /
available-nutrient readings most directly drive advice). Deeper
intervals describe subsoil and are out of scope for v1's single-sample
`SoilSample`. See the docstring in `soilgrids.py` for the exact
mapped-unit → schema-unit conversion per property.

**Known limitation:** SoilGrids' `nitrogen` property is *total* soil
nitrogen, not the *plant-available* nitrogen a lab report measures.
Both land in `nitrogen_mg_per_kg` (same schema field, same unit) but are
not directly comparable — SoilGrids' value reads roughly 10-100x higher
than a typical lab report. Downstream nitrogen logic must branch on
`source`, not assume one scale. See the `soilgrids.py` docstring.

### NDVI: GEE-live-with-cache fallback (CLAUDE.md hard rule #4)

This is a locked decision, not an implementation detail, so it's visible
here as well as in code:

```
        NDVIAdapter.fetch(field)
               │
               ▼
     ┌──────────────────────┐
     │ Try live GEE query    │   COPERNICUS/S2_SR_HARMONIZED, filtered to
     │ (bounded by timeout)  │   field point + lookback window + cloud
     └──────────┬────────────┘   ceiling; most-recent low-cloud scene;
                │                 NDVI = (B8-B4)/(B8+B4), mean over a
        success │  failure        small buffer around the point.
     ┌──────────▼──┐   ┌──────────▼─────────────────┐
     │ source=      │   │ Any exception, or timeout   │
     │ gee_live     │   │ exceeded → fall back        │
     └──────────────┘   └──────────┬───────────────────┘
                                    ▼
                         ┌─────────────────────┐
                         │ Local NDVI cache     │  specs/domains/fixtures/
                         │ lookup by field_id   │  ndvi_cache.json, seeded
                         │ (or lat/long)        │  via tools/seed_ndvi_
                         └──────────┬────────────┘  cache.json (real GEE
                                    │                 pull, never fabricated)
                         success    │    miss
                  ┌─────────────────▼┐  ┌────────────▼──────────────┐
                  │ source=cache      │  │ SourceUnavailableError —   │
                  │ (returned, not    │  │ nothing truthful to return │
                  │ an error)         │  │                            │
                  └────────────────────┘  └────────────────────────────┘
```

Which path served the result is always logged (`agro_mirai.acquisition.
ndvi` logger) and always recorded on `NDVIReading.source`
(`gee_live` vs `cache`, per `specs/core/enums.md` `ndvi_source`) — a
consumer of an `NDVIReading` can always tell which path served it without
inspecting logs.

The four fallback thresholds (call timeout, cloud-cover ceiling, lookback
window, buffer radius) are constructor parameters on `NDVIAdapter` with
defaults fixed by `decisions/0004-gee-timeout-and-fallback.md` — read
that ADR before changing any of them; the specific numbers were chosen
for reasons that matter again once traffic or crop mix changes.

## Persistence (Module 04, not yet built)

`DataStore` (`specs/core/repository-interface.md`) is the sole path from
any module to a database engine (CLAUDE.md hard rule #3). SQLite backs
local dev; Supabase Postgres backs prod. Both implementations pass the
same contract test suite against the golden fixture
(`specs/domains/fixtures/farm-001.json`).

## Crop recommendation model (Module 06)

`CropRecommendationModel` (`src/agro_mirai/models/crop_recommendation_model.py`)
wraps a `RandomForestClassifier` trained by `tools/train_crop_model.py`
on the Kaggle **Crop Recommendation Dataset**
(`atharvaingle/crop-recommendation-dataset`, Apache-2.0 license,
<https://www.kaggle.com/datasets/atharvaingle/crop-recommendation-dataset>):
2200 rows, 22 balanced crop labels (`specs/core/enums.md`'s `crop_type`
was sourced from this exact label set), 7 feature columns
(`N, P, K, temperature, humidity, ph, rainfall`).

The trained artifact (`models/crop_rf.joblib`) is **not committed** —
`/models/` is gitignored. It is reproducible by re-running
`python tools/train_crop_model.py` (fixed random seed 42 throughout;
downloads nothing itself — run
`kaggle datasets download atharvaingle/crop-recommendation-dataset -p data/raw --unzip`
first). The eval report (accuracy, macro-F1, confusion matrix) *is*
committed at `docs/eval/crop_rf_eval.json` — that's the diffable,
reviewable artifact; the binary model is not.

`FeatureVector` (Module 05's output) does not share a shape with the
Kaggle columns — `decisions/0007-crop-model-feature-mapping.md` documents
the exact mapping (`src/agro_mirai/models/crop_feature_mapping.py`) used
at prediction time. NDVI and season features are not consumed by this
model version; see that ADR for why.

## Voice & language (Module 12)

`VoiceService` (`specs/core/voice-interface.md`,
`src/agro_mirai/voice/interface.py`) is the sole path any module takes
for translation, speech-to-text, or text-to-speech — same shape as
`DataStore` for CLAUDE.md hard rule #3's spirit, applied to voice
vendors instead of DB engines. `AI4BharatVoiceService`
(`src/agro_mirai/voice/ai4bharat_voice.py`) is the live v1
implementation; `BhashiniVoiceAdapter`
(`src/agro_mirai/voice/bhashini_voice.py`) is a stub behind the same
interface, not blocked on Bhashini API access clearing.

v1 supports exactly two languages, `en` and `kn` — see
voice-interface.md for why. Three real gaps in the AI4Bharat model
catalogue forced substitutions away from what the module prompt
originally named:

| Capability | Named backend | What v1 actually uses | Why |
|---|---|---|---|
| Translation | IndicTrans2 | IndicTrans2 distilled 200M (`ai4bharat/indictrans2-en-indic-dist-200M`, `-indic-en-dist-200M`) | No substitution — the smaller distilled checkpoints were chosen over the 1B versions for the low-spec hardware target, that's the only deviation. |
| ASR | IndicWav2Vec | `ai4bharat/indic-conformer-600m-multilingual` | IndicWav2Vec's public checkpoints (`indicwav2vec_v1_*`) cover gu/hi/mr/ne/or/si/ta/te/bn — no Kannada. IndicConformer is AI4Bharat's current multilingual ASR line and does cover `kn`. |
| ASR (`en`) | (not specced — implied AI4Bharat-only) | `openai/whisper-tiny.en` | AI4Bharat's ASR line is Indian-languages-only by design; there is no AI4Bharat English model to substitute in. This is the one non-AI4Bharat model in the adapter. |
| TTS | Piper | Piper for `en`, `ai4bharat/vits_rasa_13` for `kn` | Piper's published voice set (`rhasspy/piper-voices`) has no Kannada voice at all. `vits_rasa_13` (plain VITS, not the heavier diffusion-based `IndicF5`) was picked for `kn` specifically to stay close to Piper's "lightweight, low-spec-friendly" rationale — a VITS forward pass is cheap compared to IndicF5's reference-audio-conditioned diffusion decoding. |

### AI4Bharat model / transformers version pin

Every `trust_remote_code=True` AI4Bharat model here was published against
transformers ~4.4x-era internals. This machine's global Python
environment has transformers 5.15 (current as of this module), and
against that version:

- IndicTrans2's `configuration_indictrans.py` imports
  `transformers.onnx` (`OnnxConfig`, `OnnxSeq2SeqConfigWithPast`,
  `transformers.onnx.utils.compute_effective_axis_dimension`) purely to
  define an unused ONNX-export config class — but `transformers.onnx`
  was deleted outright in 5.x (moved to the separate `optimum` package).
- IndicTrans2's `tokenization_indictrans.py`'s `IndicTransTokenizer`
  never calls `super().__init__()`; transformers 5.x's
  `PreTrainedTokenizerBase.__setattr__` requires
  `self._special_tokens_map` to already exist (normally set up by that
  skipped `__init__`) before `self.unk_token = ...` etc. can be assigned.
- IndicTrans2's `modeling_indictrans.py` defines a zero-arg
  `tie_weights(self)` override; transformers 5.x's
  `PreTrainedModel.init_weights()` unconditionally calls
  `self.tie_weights(recompute_mapping=False)`.
- `vits_rasa_13`'s `modeling_vits.py` imports
  `transformers.integrations.fsdp` — a module that doesn't exist yet in
  the *older* transformers 4.44 (it was added later than IndicTrans2's
  4.4x-era code expects), so the two models don't even agree on which
  side of the version line they need.

Rather than maintain a growing pile of import-time monkeypatches for
whichever transformers internals AI4Bharat's remote code happens to
touch, Module 12 uses a project-local virtualenv (`.venv/`, gitignored)
pinned to `transformers==4.49.0` — new enough for `vits_rasa_13`'s
`transformers.integrations.fsdp` import, old enough to still have
`transformers.onnx` and the looser special-tokens/`tie_weights`
contracts IndicTrans2 relies on. Run voice tests and tooling with
`.venv/Scripts/python.exe`, not the bare `python` used elsewhere in this
project (see `docs/TOOLING.md`). `tests/voice/test_ai4bharat_integration.py`
gates on `transformers.__version__.startswith("4.")` so it skips
cleanly (not falsely) under the global 5.x interpreter.

### IndicTransToolkit without a C++ compiler

IndicTrans2 requires a pre/postprocessing step (`IndicProcessor`) shipped
by the separate `IndicTransToolkit` package. That package's
`processor.pyx` is a Cython extension with no prebuilt Windows wheel on
PyPI, so `pip install IndicTransToolkit` requires the MSVC Build Tools
C++ compiler — not present on this machine, and not something to install
silently for a capstone dev environment. `src/agro_mirai/voice/_indic_processor.py`
is a line-for-line behavioral port of that same `.pyx` file (MIT
license, AI4Bharat/IndicTransToolkit 1.1.1) with the Cython type
declarations stripped, so it runs as plain CPython with no compiler
needed. Logic is otherwise unchanged from upstream.

### Language identification (`speech_to_text` with `expected_lang=None`)

There is no dedicated audio language-ID model in AI4Bharat's catalogue
(their `IndicLID` line classifies *text*, not audio), and IndicConformer
forced into a specific target language will always emit something in
that language's script regardless of what it actually heard, so neither
AI4Bharat component can drive this. `AI4BharatVoiceService._identify_language`
instead reuses `openai/whisper-tiny`'s own language-detection mechanism
(a single decoder step scores every Whisper-supported language as a
token) but restricts the comparison to just the `<|en|>` and `<|kn|>`
token logits instead of Whisper's full ~99-language argmax — Whisper's
unrestricted top-1 guess was tested and is not reliable enough on
synthetic Kannada TTS audio on its own (observed misclassifying it as
Sinhala), but comparing only the two languages this project actually
supports resolves that cleanly. A real multi-language expansion (v2)
would need either a proper audio LID model or a larger Whisper checkpoint
with better multilingual coverage — this binary comparison is a v1-scope
simplification, not a general solution.

### Hardware fit (i3 / 4GB RAM target, per the PPT)

All three model families are practical on that target, with caveats:

- **Translation** (IndicTrans2 distilled 200M, ×2 directions): ~2GB disk
  each, few-second CPU inference per sentence. Fine.
- **TTS**: Piper (`en`) is tiny (~60MB, ONNX, sub-second). `vits_rasa_13`
  (`kn`) is ~150MB and a VITS forward pass is fast (~1-2s for a short
  sentence on CPU in testing). Fine.
- **ASR**: `indic-conformer-600m-multilingual` is ONNX (not a raw
  PyTorch checkpoint), which is exactly what keeps it usable on CPU —
  but at ~2.5GB on disk and ~2 minutes cold-load time in testing (model
  graph + all 22 per-language decoder heads loaded together), it is the
  heaviest of the three, and 2 minutes of one-time load latency is worth
  surfacing explicitly for a live demo: **load it once at process
  startup, not per-request**, or the first request in any demo session
  will look hung. Steady-state inference after that load was ~3s per
  short utterance in testing — acceptable, not snappy, on a 4GB-RAM
  target.

None of the three needed to be ruled out as impractical, but the ASR
cold-load time is the one number worth remembering when wiring this
into a request-handling module later.

## What's not decided yet

- API framework and routing (Module 11).
- Model-serving shape for IrrigationAdvice / DiseaseRiskAlert
  (Modules 07-08).
- Deployment split between Render (API) and Supabase (DB/auth) — open
  question tracked in `PROGRESS.md`.
