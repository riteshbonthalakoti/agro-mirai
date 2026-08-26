# Feature Spec — Module 05 Processing & Feature Engineering

Documents every feature `FeatureBuilder` (`src/agro_mirai/processing/feature_builder.py`)
computes from raw `Field_` + `WeatherReading`/`SoilSample`/`NDVIReading`
history. Additive-only, same as `schema.yaml`: a new field is fine, a
rename or removal needs a new version and an ADR.

`FeatureBuilder` is a pure function of its inputs — a `Field_`, plain
lists of readings (already fetched by the caller via `DataStore`), and an
`as_of: date` anchor. It never calls the `DataStore`, never calls
`datetime.now()` internally, and makes no network calls. Same inputs,
same `as_of` → same output, always.

## Output shape: `FeatureVector`

One dataclass, `agro_mirai.processing.feature_builder.FeatureVector`,
holding every feature below plus the availability flags. Field names in
this doc are exact dataclass field names.

## 1. Weather aggregates

Source: `WeatherReading` list for the field, filtered to
`observed_at.date() <= as_of` (readings after the anchor — forecasts —
are excluded from these backward-looking aggregates), then windowed by
`as_of - window_days < observed_at.date() <= as_of`.

Windows: 7, 14, 30 days. For each window `W`:

| Feature | Computation | Unit | Range | Missing-data policy |
|---|---|---|---|---|
| `rainfall_mm_sum_{W}d` | sum of `rainfall_mm` over readings in window | mm | `>= 0.0` | reading with `rainfall_mm is None` contributes 0 to the sum (absent rainfall report, not proof of no rain, but sum needs a number — see decision below) |
| `temp_c_mean_{W}d` | mean of `temp_c` over readings in window | °C | unbounded | `temp_c` is required on `WeatherReading` (schema), so never missing per-reading |
| `humidity_pct_mean_{W}d` | mean of `humidity_pct` over readings in window, skipping `None` values | % | `[0.0, 100.0]` | if every reading in the window has `humidity_pct is None`, the mean is `None` |

Weather is the one required data source (Module 03's acquisition design
asserts weather is always available). If the field has **zero**
`WeatherReading` records at all, `FeatureBuilder.build()` raises
`ValueError` — it does not emit a mostly-`None` vector. If the field has
readings but none fall inside a particular window (e.g. only 3 days of
history and a 30-day window requested), that window's sums/means are
still computed over whatever subset falls in range; an empty window
(zero readings in range) yields `rainfall_mm_sum=0.0` and
`temp_c_mean=None`/`humidity_pct_mean=None` — an empty sum is
legitimately 0, an empty mean has no defined value.

## 2. Soil features

Source: latest `SoilSample` by `observed_at` with
`observed_at.date() <= as_of` (falls back to the single latest sample
overall if none is `<= as_of`, since a lab report is often entered once
and stays valid going forward — see decision below).

| Feature | Computation | Unit | Range |
|---|---|---|---|
| `soil_ph` | pass-through `ph` | pH | `[0.0, 14.0]` |
| `soil_nitrogen_mg_per_kg` | pass-through `nitrogen_mg_per_kg` | mg/kg | `>= 0.0` |
| `soil_phosphorus_mg_per_kg` | pass-through `phosphorus_mg_per_kg` | mg/kg | `>= 0.0` |
| `soil_potassium_mg_per_kg` | pass-through `potassium_mg_per_kg` | mg/kg | `>= 0.0` |
| `soil_organic_carbon_pct` | pass-through `organic_carbon_pct` | % | `[0.0, 100.0]` |
| `soil_moisture_pct` | pass-through `moisture_pct` | % | `[0.0, 100.0]` |
| `soil_npk_balance_index` | derived: `N / (N + P + K)` using the three NPK values above, `None` if any of the three is `None` or `N+P+K == 0` | ratio | `[0.0, 1.0]` |

`soil_npk_balance_index` is a normalized nitrogen share of total N+P+K —
a simple, documented v1 derived feature. It is intentionally not a
crop-specific "ideal ratio" score; that judgment call belongs to Module
06's recommendation model, not to feature extraction.

**Missing-data policy:** if the field has zero `SoilSample` records,
every `soil_*` field is `None` and `soil_data_available` is `False`. If
a sample exists, individual pass-through fields still follow the
schema's own per-field optionality (e.g. a sample missing `ph` yields
`soil_ph = None` even though `soil_data_available = True`).

## 3. NDVI features

Source: `NDVIReading` list for the field, filtered to
`observed_at.date() <= as_of`, sorted by `observed_at` ascending.

| Feature | Computation | Unit | Range |
|---|---|---|---|
| `ndvi_latest` | `ndvi` of the most recent reading in range | index | `[-1.0, 1.0]` |
| `ndvi_trend` | `ndvi_latest - ndvi` of the second-most-recent reading in range; `None` if fewer than 2 readings in range | index delta | `[-2.0, 2.0]` |
| `ndvi_confidence_source` | `source` of the most recent reading (`gee_live` / `cache` / `manual`) | enum passthrough | n/a |

**Explicit scope decision:** Module 05 does **not** use
`ndvi_confidence_source` to weight or discount `ndvi_latest`/`ndvi_trend`
itself — it passes the flag through unmodified on the vector.
Confidence-weighting (e.g. trusting a `gee_live` reading more than a
`cache` reading in a downstream model) is explicitly deferred to
Modules 06–08, which consume the vector and have the domain context to
decide how much to discount a cached value.

**Missing-data policy:** if the field has zero `NDVIReading` records in
range, `ndvi_latest`, `ndvi_trend`, and `ndvi_confidence_source` are all
`None`, and `ndvi_data_available` is `False`. A missing NDVI is never
represented as `0.0` — `0.0` is a real, meaningful NDVI value (bare
soil/no vegetation), not the same thing as "we have no reading."

## 4. Season / derived context

Source: `Field_.sown_on` (date, optional) mapped against `as_of` using a
fixed, documented v1 heuristic — **not** agro-climatic-zone-aware, and
not sensitive to actual monsoon onset, elevation, or crop-specific
duration. It is a calendar-month lookup only.

| `sown_on` month | `season` |
|---|---|
| June, July | `kharif` |
| October, November, December | `rabi` |
| March, April, May | `zaid` |
| August, September (in-between/transition months, no clean v1 mapping) | `None` |
| January, February (tail of rabi/lead-in to zaid, ambiguous) | `None` |

Rationale for the two `None` bands: forcing every month into one of the
three buckets would silently misclassify transition-month sowings;
`season = None` is more honest than a wrong guess, and downstream
modules can special-case it.

| Feature | Computation | Unit |
|---|---|---|
| `season` | month-lookup of `sown_on` per the table above | enum (`kharif`/`rabi`/`zaid`) or `None` |
| `days_since_sowing` | `(as_of - sown_on).days`, `None` if `sown_on` is `None` or in the future relative to `as_of` | days |

**Missing-data policy:** if `Field_.sown_on` is `None` (schema allows
this — it's an optional field), `season` and `days_since_sowing` are
both `None`. This is not gated by a separate availability flag since it
mirrors the optionality already declared in `schema.yaml` for `sown_on`
itself.

## 5. Availability flags

Two booleans on every `FeatureVector`, computed purely from whether the
corresponding input list was non-empty (after the `as_of` filter):

- `soil_data_available: bool`
- `ndvi_data_available: bool`

There is no `weather_data_available` flag — weather is asserted as
always-available (Module 03) and its absence is a hard error, not a
flagged-and-degraded state (see §1).

## Missing-data policy summary (the actual decision, ADR 0006)

1. **Weather is required.** Zero `WeatherReading` rows for the field →
   `FeatureBuilder.build()` raises `ValueError`. No mostly-`None` vector
   is ever emitted for a field with no weather history.
2. **Soil is optional, all-or-nothing per sample.** Zero `SoilSample`
   rows → every `soil_*` feature is `None`, `soil_data_available=False`.
   A present sample still respects the schema's own per-field
   optionality.
3. **NDVI is optional, all-or-nothing per reading set.** Zero
   `NDVIReading` rows (in range) → `ndvi_latest`, `ndvi_trend`,
   `ndvi_confidence_source` are all `None`, `ndvi_data_available=False`.
   `None` is never conflated with the real value `0.0`.
4. **`ndvi_confidence_source` is passed through, never used to weight
   anything inside Module 05.** Weighting is explicitly out of scope
   here; deferred to Modules 06–08.
5. **`season`/`days_since_sowing` follow `sown_on`'s own optionality** —
   no separate flag, `None` propagates directly.

See `decisions/0006-missing-data-policy.md` for the ADR.
