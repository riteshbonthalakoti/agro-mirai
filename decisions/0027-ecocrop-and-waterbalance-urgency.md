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
