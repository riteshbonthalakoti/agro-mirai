# 0027 - EcoCrop crop ranking, water-balance irrigation urgency

Date: 2026-09-24. Supersedes the model parts of 0007 (crop feature mapping) and 0008 (irrigation model).

## What was wrong (checked on the live Render API)
- Crop: a cotton field near Bellary came back as watermelon / muskmelon, confidence 0.3. The RandomForest was trained on plant-available N/P/K (kg/ha, N 0-140) but live fields only have SoilGrids total nitrogen (no P/K) or a per-soil-type table, so N was ~250 - outside the training range. The 99.5% accuracy only holds on the Kaggle dataset itself.
- Irrigation: urgency came from a RandomForest with 72% accuracy / macro-F1 0.58, while the depth (mm) was already a proper FAO-56 water balance. Two sources of truth that could disagree.
- Fields with soil type "unknown" failed (no soil fallback) and the tabular-service 422 turned into a 500 (fixed separately in cddec04, 9f41202).

## Decision
1. Crop: rank the 22 crops with FAO EcoCrop ranges (temperature, soil pH, soil texture from the farmer's soil type, soft annual-rainfall check). Data: OpenCLIM/ecocrop EcoCrop_DB.csv (CC0), built into `src/agro_mirai/models/data/ecocrop_crops.json` by `tools/build_ecocrop_table.py`. In Karnataka, crops in the Bellary list (0016) get a small edge. `confidence` is now a suitability score, not a probability.
2. Irrigation: urgency = share of the 7-day crop water demand that rain did not cover (>=70% high, >=35% moderate, else low). Same numbers as the depth. No soil data needed any more.
3. Neither needs a model file, so the main API runs both in-process (no call to the tabular service).

## Not done / limits
- Thresholds (0.35 / 0.70) and the regional 0.85 factor are judgement calls, not fitted. Nothing here was validated against real farm outcomes.
- EcoCrop has no chilling-hours or altitude logic, so hill crops (apple) can look fine at the right temperature in the plains.
- N/P/K are not used at all until the farmer can enter real soil-test values.
- The old RandomForests, training scripts and the tabular service are left in the repo for now. The RF could come back as a second ranker once real soil-test inputs exist.

## Update, same day: v2 (use the data we already fetch)
An audit of what the APIs return vs what the models read found real gaps, all fixed in v2:
- Weather history was never fetched (only "current + 7-day forecast"), so "rain in the last 7/30 days" was near zero for new fields. Fixed: Open-Meteo call now uses `past_days=30` (same single request), and old/stale fields are refreshed lazily (`ensure_fresh_weather`, at most once per 3 h per field, never raises, `AGRO_WEATHER_REFRESH=0` disables it for tests).
- The 7-day forecast was stored and ignored. Now `FeatureVector` carries `rain_forecast_mm_3d/7d`, `forecast_days_available`, `wind_mps_mean_7d` and a per-day `daily_weather` list (all additive, defaults None/0).
- Raw rows were summed as-is, so re-fetched rows double counted. `processing/weather_series.py` keeps one row per day (daily row over instantaneous, observed over forecast).
- Irrigation is now a daily FAO-56 root-zone water balance (`models/soil_water_balance.py`): Penman-Monteith ET0 from the daily temperature/humidity/wind (radiation estimated from the temperature range), per-day Kc by growth stage, root depth and allowable depletion per crop, water holding by soil type, effective rain, then a projection through the forecast. It says how much soil water is used, when the crop will be stressed, and tells the farmer to wait when enough rain is forecast. Old 7-day shortcut stays as the fallback when there are fewer than 5 days of weather.
  - Check: my PM ET0 averaged 5.4 mm/day vs Open-Meteo's own radiation-based `et0_fao_evapotranspiration` 6.1 for Bellary, 30 days to 2026-09-24 (ratio 0.89, so slightly low, not inflated).
- Crop ranking adds: sowing-month calendar (ICAR style, approximate), a 0.9 factor for tree crops (multi-year commitment), the real 12-month rainfall at the field (Open-Meteo archive, cached per ~10 km cell, warmed in the background at field creation; Bellary 591 mm, Coorg 1889 mm), a comparison with the crop already in the field ("keep growing it" / "weak fit"), and a satellite-greenness warning.

Limits: irrigation assumes the farmer has not irrigated (rain-fed) since nothing records it; starting soil moisture is assumed 30% used; crop table values (root depth, p, sowing months) are approximate, not from a soil survey; the 12-month rain cache is per process so a Render restart costs one 2.5 s wait per location.
