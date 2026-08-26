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

## What's not decided yet

- API framework and routing (Module 11).
- Model-serving shape for IrrigationAdvice / DiseaseRiskAlert
  (Modules 07-08).
- Deployment split between Render (API) and Supabase (DB/auth) — open
  question tracked in `PROGRESS.md`.
