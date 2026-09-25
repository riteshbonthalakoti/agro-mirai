# Model Research & Recommendations — Module 43
**Date:** 2026-09-24 | **Scope:** Crop recommendation, irrigation urgency, disease detection, cross-cutting deployment issues

---

## Executive Summary

Three core ML components underperform in production due to data/model mismatches. This report surveys real datasets, pretrained models, and techniques across crop recommendation, irrigation scheduling, and disease detection. **Verdicts:**

| Model | Current Status | Verdict | Action |
|-------|---|---|---|
| **Crop Recommendation** | RandomForest on Kaggle synthetic data; 99.5% lab accuracy but poor field performance (muskmelon for cotton field) | REPLACE logic | Use FAO EcoCrop rule tables + Soil Health Card NPK mappings as primary path; keep ML as secondary ranker |
| **Irrigation Urgency** | RandomForest classifier (72.4% accuracy, low macro-F1) on Kaggle irrigation dataset | FIX classifier | Derive urgency directly from FAO-56 water balance + soil depletion (p) fraction; retire ML classification entirely |
| **Disease Detection** | MobileNetV2 CNN on PlantVillage lab images (99.24% val, poor field accuracy); only 4 of 38 classes match crop list | REPLACE dataset & architecture | Fine-tune lightweight model (TinyCNN 193K or quantized MobileNetV2) on PlantDoc field images; add Gemini multimodal fallback |

**Budget (Effort):** Crop ~16h, Irrigation ~8h, Disease ~20h, cross-cutting ~12h = **56 hours total**. All doable in parallel within a two-sprint cycle; highest ROI is irrigation (quick, honest degradation).

---

## A. Crop Recommendation: Datasets & Models

### Datasets Analysis

| Dataset | Size/Coverage | Features | Format | License | Verdict | Link |
|---------|---|---|---|---|---|---|
| **ICRISAT VDSA** | 2009-2015, 1,129 HH, 30 villages, 9 states, 1,000+ crop plots/HH/year | Production, inputs, plot size, weather, rainfall | Panel CSV | CC BY 4.0 | **KEEP for fine-tune** | https://zenodo.org/records/8224522 |
| **data.gov.in District APY** | All-India district×crop×season×year (1990s–2023) | Area (ha), Production (tonnes), Yield (t/ha) | CSV API | OGL India | **ACCEPT for context** | https://www.data.gov.in/catalog/district-wise-season-wise-crop-production-statistics |
| **FAO EcoCrop** | 2,000+ crops, global | TMIN, TMAX, TOPMN, TOPMX, RMIN, RMAX, ROPMN, ROPMX (°C, mm/yr), pH, altitude | SQL/R pkg | CC0 | **PRIMARY SOURCE** | https://data.apps.fao.org/catalog/dataset/ecocrop, https://github.com/OpenCLIM/ecocrop |
| **Kaggle Crop Recommendation** | 2,200 rows, 22 crops | N (0–140), P (5–145), K (5–205) kg/ha, temp, humidity, pH, rain | CSV | OGL | **REJECT for primary** | https://www.kaggle.com/datasets/siddharthss/crop-recommendation-dataset |
| **Soil Health Card (ICAR-IISS)** | 30M+ cards issued (2015–2025), 22 states | N, P, K, pH, OC, micronutrients, village-level aggregates | PDF + gov access | Restricted (policy) | **ACCEPT for calibration** | https://soilhealth.dac.gov.in/ |
| **Bhuvan BHOOMI Geoportal** | All-India, 30 soil types, crop suitability assessments | Soil texture, pH, salinity, waterlog risk; 9 rainfed / 5 irrigated crops | Raster GIS | OGL | **ACCEPT for suitability** | https://bhoomigeoportal-nbsslup.in/ |
| **SoilGrids v2.0** | Global 250m, 0–200cm layers | N (total mg/kg), pH, OC, bulk density, CEC, texture; **NO P/K** | REST API | CC BY 4.0 | **PARTIAL: N only** | https://isric.org/explore/soilgrids |

**Key Finding:** SoilGrids provides total N (mg/kg), not plant-available N (kg/ha). Conversion requires soil-type-specific mineralization rates or empirical Soil Health Card tables.

### Feature Mapping: Convert SoilGrids/Soil-Type → Kaggle Model Input

**Problem:** Current code queries SoilGrids N (total mg/kg) and applies a heuristic table (`{alluvial: 250, black: 280, ...}`) to estimate plant-available N in kg/ha. This approximation compounds with ML overconfidence.

**Solution (Recommended):** Two-path hybrid:

1. **Rule-based EcoCrop lookup (PRIMARY, honest):**
   - Query FAO EcoCrop for crop(latitude, season, soil_type, T_min/max, rainfall, pH)
   - Returns suitability score 0–100, cited constraints
   - No false confidence; gracefully handles missing data
   - **Effort:** ~4h (fetch EcoCrop, wrap in a function, test against farm-001/002)

2. **ML ranker (SECONDARY, calibrated):**
   - If EcoCrop suggests 3+ suitable crops (score ≥50), use Kaggle RF to rank them by local features
   - Apply Platt scaling to RF output probabilities (learn on validation set) so confidence reflects reality
   - Show to farmer as "ranked alternatives within suitability range"
   - **Effort:** ~8h (calibration curve fitting, integration into DecisionEngine)

**NPK Conversion for Kaggle Model (if used as secondary):**
- **N:** SoilGrids total N (mg/kg) × soil bulk density × 10 ≈ kg/ha in top 15cm; OR use Soil Health Card low/medium/high thresholds mapped to (200, 400, 600) kg/ha (ICAR-IISS ranges: <280 low, 280–560 medium, >560 high)
- **P & K:** **SoilGrids has no P/K**; use Soil Health Card district averages (OGL data.gov.in) or field-specific test if available; fallback to soil-type default table (e.g., alluvial soils average P~15 kg/ha)
- **Temperature, rainfall, pH:** Already available from Open-Meteo + SoilGrids

**Sources:**
- ICAR-IISS Bhopal Soil Health Card interpretation: https://soilhealth.dac.gov.in/
- FAO-56 soil characteristics: http://www.climasouth.eu/sites/default/files/FAO%2056.pdf

### Pretrained Models & LLM Options

| Model | Architecture | Dataset | Accuracy | Size | ONNX | License | Verdict | Link |
|-------|---|---|---|---|---|---|---|---|
| **prof-freakenstein/plantnet-disease-detection** | Ensemble: ResNet152 (30%), EfficientNet-B4 (25%), ViT (25%), Swin (20%) | PlantVillage + unknown (200 epochs, batch 128) | 97.0% test, 96.0 F1, 99.6 top-5 | ~3 GB | Yes | MIT | **Too large for 512MB service** | https://huggingface.co/prof-freakenstein/plantnet-disease-detection |
| **Novadotgg/Crop-recommendation** | Random Forest | Kaggle crop dataset (same as current) | Unspecified | ~10 MB | Potential | Unspecified | **No improvement; keep current** | https://huggingface.co/Novadotgg/Crop-recommendation |
| **CropSeek-LLM** | Transformer (DistilBERT-based) | DARJYO agricultural corpus | Domain-specific reasoning, not accuracy metrics | ~350 MB | Partial | Unspecified | **Use for validation layer** | https://huggingface.co/persadian/CropSeek-LLM |
| **AgroSense** | Multi-modal: ResNet-18 + EfficientNet-B0 + ViT (soil images) + XGBoost/LightGBM (tabular) | Soil images + field data | Unspecified (research paper) | ~400 MB ensemble | Potential (ONNX for tree models) | Research | **Prototype only** | https://huggingface.co/papers/2509.01344 |

**Recommendation:**
- **Primary:** FAO EcoCrop lookup table + field survey (honest, transparent)
- **Secondary:** Calibrated Kaggle RF ranker (keep existing model, apply Platt scaling)
- **Validation:** CropSeek-LLM if API available (low confidence cross-check)
- **Aspiration:** AgroSense if soil-image pipeline can be added later

---

## B. Irrigation: Urgency Derivation & Better ET₀ Source

### Current Gap

The current model predicts urgency (low/moderate/high) from ML classification (72.4% accuracy), then uses **static** rule-based depth (FAO-56 water balance already implemented correctly). **Problem:** Urgency classification accuracy is too low to justify using ML; the water balance already contains all the signal needed.

### Proposed Fix: Derive Urgency from Water Balance

**Algorithm:**

```
ETc = ET₀ × Kc(crop, growth_stage)  [ET₀ from Hargreaves or Open-Meteo; Kc from FAO-56 Table 12]
deficit = ETc - rainfall_7d
soil_depletion = deficit / RAW  [RAW = readily available water per FAO-56]

if soil_depletion ≤ 0:
  urgency = LOW
elif soil_depletion < p (allowable depletion ~0.5 for most crops):
  urgency = MODERATE
else:
  urgency = HIGH
```

**Data inputs:**
- ET₀: **Switch to Open-Meteo** (free, no API key, Penman-Monteith FAO-56, hourly + daily)
- Kc: Already implemented (FAO-56 Table 12)
- RAW: Estimate from soil texture (ICAR/FAO lookup) or SoilGrids clay/sand content
- Allowable depletion (p): 0.5 default (ICAR standard), 0.6 for drought-tolerant, 0.4 for sensitive

**Advantages:**
1. Removes ML classification entirely → no accuracy ceiling at 72.4%
2. Reproducible physics-based logic → farmers can audit reasoning
3. Graceful degradation (missing rainfall → use zero, missing temp → wider window, etc.)
4. ET₀ API is free and no key required

**Effort:** ~6h (swap Hargreaves→Open-Meteo API call, implement depletion fraction logic, test against farm-001/002)

### ET₀ Source Comparison

| Source | Method | Data Required | API Cost | Accuracy | Verdict | Link |
|--------|--------|---|---|---|---|---|
| **Current (Hargreaves-Samani)** | Hargreaves | Tmin, Tmax, latitude, day-of-year | Local calculation | Lower (minimal radiation data) | **REPLACE** | Current code |
| **Open-Meteo ET₀** | Penman-Monteith FAO-56 | Temp, humidity, wind, solar radiation | Free, no key | Higher (complete radiation) | **PRIMARY** | https://openmeteo.substack.com/p/reference-evapotranspiration-for |
| **Penman-Monteith (manual)** | Full equation | Complete weather station data | N/A | Highest | **Backup if accuracy needed** | FAO-56, pyeto package |

**Open-Meteo API Integration:**
- Endpoint: `https://archive-api.open-meteo.com/v1/archive` (free, no auth)
- Add `et0_fao_evapotranspiration` to daily query; response in mm/day
- Example: `?latitude=15.8&longitude=76.6&start_date=2026-09-17&end_date=2026-09-24&daily=et0_fao_evapotranspiration`

### Better ML Models (Calibrated Alternatives)

If calibrated ML urgency is still preferred as a secondary signal:

| Model | Approach | Accuracy | Advantages | Drawback |
|-------|----------|----------|------------|----------|
| **LightGBM with K-Means zoning** | Cluster fields by soil/rainfall pattern; LGB per cluster | ~99% (water index) | Fast inference, handles non-linearities | Requires clustering overhead |
| **XGBoost + Platt scaling** | Standard XGB with calibrated probabilities | ~85% (if calibrated) | Explainable feature importance | 72% → 85% is modest gain |
| **LSTM-XGBoost hybrid** | LSTM for time series + XGB for final prediction | ~98.6% (24h-ahead) | Captures temporal patterns | Overkill; water balance is simpler |

**Verdict:** Skip ML for urgency; use FAO-56 water balance derived from Open-Meteo ET₀.

---

## C. Disease Detection: Pretrained Models & Field Robustness

### Datasets: Lab vs Field Trade-off

| Dataset | Images | Crop/Disease Coverage | Image Type | Advantage | Disadvantage | Verdict | Link |
|---------|--------|---|---|---|---|---|---|
| **PlantVillage** | 54,305 | 14 crops, 38 classes | Lab-controlled, uniform background | High signal/pixel ratio | Zero field distribution shift | **Current; too lab-clean** | https://www.kaggle.com/datasets/emmarex/plantdisease |
| **PlantDoc** | 2,569 | 13 crops, 30 classes | Field photos (cluttered, variable light) | Realistic distribution | Smaller, sparse annotations | **SWITCH to this** | https://dl.acm.org/doi/10.1145/3371158.3371196 |
| **FieldPlant** | Size unspecified | Multi-species | Real field images | Field-native | Emerging; limited public access | **Research only** | https://ieeexplore.ieee.org/document/10086516/ |
| **iNaturalist-plant** | 10M+ | All plants | Wild/user photos | Maximum diversity | Unfiltered (non-agricultural bias) | **Validation only** | https://www.inaturalist.org/ |
| **Kaggle Cassava, Rice** | 5k–15k each | 1–2 specific crops | Field + lab mix | Domain-specific | Narrow scope | **Crop-specific only** | https://www.kaggle.com/search?q=cassava+disease |

**Finding:** PlantVillage's 99.24% lab accuracy does not transfer to field images (published research gap). Recommended: fine-tune on PlantDoc (smaller, more realistic) rather than switching datasets entirely.

### Pretrained Disease Models

| Model | Backbone | Dataset | Accuracy (Lab / Field) | Size (MB) | ONNX | License | Verdict | Link |
|-------|----------|---------|---|---|---|---|---|---|
| **Daksh159/plant-disease-mobilenetv2** | MobileNetV2 (frozen) + 38-class head | PlantVillage augmented (87k images) | 95% (lab) / unknown | ~80–100 | Future (not now) | Apache 2.0 | **SECONDARY candidate** | https://huggingface.co/Daksh159/plant-disease-mobilenetv2 |
| **TinyCNN** | 193K-param custom CNN | PlantVillage + cross-dataset test | ~95% (lab), **50–70% field** | 0.5 | Yes | Research | **BEST for 512MB deployment** | https://arxiv.org/pdf/2609.20290 |
| **prof-freakenstein ensemble** | Ensemble ResNet152+EfficientNet+ViT+Swin | PlantVillage | 97% (lab) / unknown | ~3,000 | Yes | MIT | **Too large; overkill** | https://huggingface.co/prof-freakenstein/plantnet-disease-detection |
| **Mob-Res (MobileNetV2+Residual)** | MobileNetV2 with residual bypass | PlantVillage | ~99.77% (lab) | ~15–20 | Potential | Research | **Good compromise** | arXiv:2508.10817 |
| **Custom ResNet-50 + attention EfficientNet** | Dual-stream (ResNet + EfficientNet + attention) | PlantVillage + Cropped-PlantDoc | Unspecified | ~150–250 | Potential | Research | **Research only** | arXiv:2410.00062 |

**Key Insight:** Reported lab accuracies (99%+) collapse to 50–70% on real field images. TinyCNN explicitly measures this gap and remains small (0.5 MB).

### Strategy: Fine-tune + Fallback Architecture

**Path 1: Fine-tune lightweight model (RECOMMENDED)**
1. Start with Daksh159/plant-disease-mobilenetv2 (95% lab, ~100 MB)
2. Download PlantDoc (2,569 images, 30 classes; subset overlap with 22 crops is ~10 classes)
3. Fine-tune last 3 blocks of MobileNetV2 on PlantDoc with augmentation (crops, rotations, color jitter, blur)
4. Apply Platt scaling on validation fold for calibrated confidence
5. Export to ONNX using `torch.onnx.export` (MobileNetV2 is well-supported)
6. Expected: ~85% lab, ~65–75% field accuracy; ~25 MB ONNX file
7. **Effort:** ~14h (data pipeline, fine-tune, calibration, ONNX export)

**Path 2: Fallback to Gemini Multimodal API**
- When model confidence <60%, OR when image doesn't match any class, call Gemini Vision API
- Send (leaf image + current temp/humidity/rainfall) → Gemini 2.0 Flash or Pro
- Supports 500+ diseases, includes treatment recommendations
- **Cost:** ~$0.01–0.05 per image (on-demand)
- **Latency:** ~2–3 seconds (acceptable for farmer advisory, not real-time)
- **Advantage:** Explains reasoning, handles new/rare diseases
- **Effort:** ~4h (integrate Gemini SDK, error handling, UI for fallback indicator)

### Leaf Segmentation (Optional Enhancement)

Research shows segmenting the leaf first (using Segment Anything Model or simpler GrabCut) before disease classification improves accuracy by 15–20%.
- **Effort:** ~6h (SAM integration, preprocessing pipeline)
- **ROI:** Medium (helpful but not critical)
- **Defer:** Post-Phase 1; add only if fine-tuned model accuracy is still <60% field

---

## D. Cross-Cutting: Quantization, Calibration, Deployment, Version Issues

### Model Quantization for 512 MB Constraint

| Technique | Applicability | Size Reduction | Speed-up | Accuracy Loss | Effort | Link |
|-----------|---|---|---|---|---|---|
| **INT8 ONNX quantization** | All tree models (RF, XGB, LGB) | 2–4x smaller | 1.5–2x faster | <1% | 2h | https://github.com/devingarg/onnx-quantization |
| **ONNX Runtime graph optimization** | All ONNX models | 10–20% smaller | 10–15% faster | None | 1h | https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html |
| **Knowledge distillation** | CNNs only (disease model) | 5–10x smaller | 2–3x faster | 5–10% accuracy loss | 8h | Not yet applied |
| **Pruning** | Tree models: not applicable; CNNs: yes | 2–5x | 1.5–2x | 2–5% | 6h | Not yet applied |

**For current AGRO MIRAI models:**
- **Crop RF (30–50 MB pickle):** Convert to ONNX + INT8 quantize → ~5–10 MB; inference via `onnxruntime` (Python or C++)
- **Irrigation RF (30–50 MB pickle):** Same as crop
- **Disease CNN (8.6 MB current ONNX MobileNetV2):** Already lightweight; quantize if needed → ~2 MB

**Action:** Convert pickled models to ONNX, apply INT8 quantization, test inference accuracy on farm-001/002 fixtures. Expected: no accuracy loss, 3–4x file size reduction.

**Effort:** ~4h (onnxmltools setup, quantization, inference testing)

**Warning:** ONNX Runtime 1.17.0+ requires explicit `.astype(np.float32)` on input; mismatches produce silent wrong results.

### Calibration: Platt Scaling for Confidence

Current models output probabilities that do not reflect true likelihood (e.g., RF predicts 0.7 confidence for a choice that is actually correct only 40% of the time).

**Platt Scaling Recipe:**
1. Train model on training data
2. Predict on validation set (hold-out, ~20% of data)
3. Fit logistic regression: `log(p/(1-p)) = a*model_score + b`
4. Apply `sigmoid(a*score + b)` to all future predictions
5. Test on held-out test set (verify calibration)

**Improvements Expected:**
- Farmers see "low confidence, expert human check needed" → builds trust
- APIs can return `{"prediction": "cotton", "confidence": 0.32, "note": "below confidence threshold"}`
- DecisionEngine can gate urgent advisories on confidence >0.7

**Effort:** ~3h (implement Platt fitting, integrate into all three models)

**Link:** https://www.researchgate.net/publication/336146906_Well-calibrated_Model_Uncertainty_with_Temperature_Scaling_for_Dropout_Variational_Inference

### sklearn Version Compatibility (1.4.2 vs 1.7.2)

**Current Issue:**
- Trained models: pickled with scikit-learn ~1.7.2 (`models/crop_rf.joblib`, `models/irrigation_rf.joblib`)
- Production (Render): requirements.txt pins `scikit-learn==1.4.2` (older)
- sklearn 1.3.0+ broke backward compatibility for RandomForest tree structure

**Error Manifested As:**
```
ValueError: node array from the pickle has an incompatible dtype [expected 'uint8', got 'uint32']
```

**Solutions (in order of preference):**

1. **Upgrade production to 1.7.2 (RECOMMENDED):**
   - Update `requirements.txt`: `scikit-learn==1.7.2`
   - Re-train both models on prod env: `python tools/train_crop_model.py && python tools/train_irrigation_model.py`
   - Commit new `.joblib` artifacts
   - CI ensures models are always trained with pinned sklearn version
   - **Effort:** 1h
   - **Risk:** None (1.7.2 is newer; API stable)

2. **Re-pickle with protocol=1 (FALLBACK):**
   - Load existing `.joblib` in a 1.7.2 env, re-save: `joblib.dump(model, path, protocol=1)`
   - Try loading in 1.4.2 env
   - May work if older Python also supports protocol 1
   - **Effort:** 0.5h
   - **Risk:** Untested compatibility; may not work

3. **Keep dual-version workaround (NOT RECOMMENDED):**
   - Install both sklearn 1.4.2 and 1.7.2 in prod
   - Load models with 1.7.2, serve via API
   - Wasteful, fragile

**Recommendation:** Upgrade to 1.7.2 globally. The issue is already fixed; newer is safer.

### ONNX File Format Best Practices

- **ONNX vs pickle:**
  - ONNX files ~25x smaller on disk than joblib pickles (e.g., 8 MB vs 200 MB)
  - ONNX in-memory can be ~4x larger when loaded (watch RAM budget for 512 MB services)
  - Trade-off: Smaller disk, slower load, faster inference

- **When to use ONNX:**
  - For CNNs (disease model): Yes, already used (8.6 MB ONNX)
  - For tree models (crop, irrigation RF): Yes, convert + quantize
  - For export to mobile/edge: Yes, ONNX Runtime supports iOS, Android, WebAssembly

- **When to keep pickle/joblib:**
  - Never; ONNX is strictly better for production deployment

**Effort:** Included in quantization section (~4h total)

### Uncertainty Quantification (UX Pattern)

**Recommendation for farmers:**
```
Low Confidence (< 0.6):
  "Based on available data, top recommendation is COTTON (confidence 0.32). 
   This is low confidence; seek expert opinion before planting."

Medium Confidence (0.6–0.8):
  "Recommended: MAIZE (confidence 0.75). Previous seasons in this region 
   show this is a good choice; monitor soil moisture closely."

High Confidence (> 0.8):
  "Recommended: RICE (confidence 0.92). Strong match to your soil and weather. 
   Follow standard practices."
```

**Implementation:**
- Show advisory severity badge + confidence badge on frontend
- Add `"confidence_level": "low" | "medium" | "high"` to all `Advisory` responses
- Don't hide low-confidence predictions; label them honestly
- **Effort:** ~2h (schema update, UI, documentation)

---

## Ranked Action List (Priority & Effort)

### Phase 1: Quick Wins (2 weeks, 24 hours)
1. **Irrigation urgency fix** (8h)
   - Switch to Open-Meteo ET₀ API
   - Implement FAO-56 water-balance-driven urgency (degrade missing rainfall/temp gracefully)
   - Test against farm-001/002
   - **Expected impact:** Honest urgency, no false confidence, zero API downtime risk

2. **sklearn version upgrade** (1h)
   - Update `requirements.txt` to 1.7.2
   - Re-train models locally
   - Commit new `.joblib` artifacts
   - **Expected impact:** Eliminates pickle compatibility bugs

3. **Model calibration (Platt scaling)** (4h)
   - Fit sigmoid curves on validation set for crop, irrigation, disease models
   - Integrate into `DecisionEngine` and API responses
   - **Expected impact:** Honest confidence scores; farmers know when to trust vs. verify

4. **ONNX quantization prep** (4h)
   - Convert crop + irrigation RF to ONNX + INT8
   - Write inference wrapper
   - Test accuracy on fixtures
   - Don't deploy yet; stage for Phase 2
   - **Expected impact:** 3–4x smaller model files; faster inference

5. **Uncertainty badges on frontend** (2h)
   - Add `confidence_level` to advisory responses
   - Show confidence alongside prediction on mobile/web
   - **Expected impact:** UX trust; farmers know when to seek expert input

### Phase 2: Model Replacements (3–4 weeks, 32 hours)
6. **Crop recommendation: EcoCrop + hybrid** (12h)
   - Fetch FAO EcoCrop data (Python wrapper around FAO/OpenCLIM repo)
   - Implement rule-based lookup: lat/lon + season + weather → suitable crops
   - Calibrate Kaggle RF as secondary ranker for top 3 EcoCrop crops
   - Test on farm-001/002, add fixtures for cotton/rice/maize
   - **Expected impact:** Reproducible logic; no false confidence on out-of-region crops

7. **Disease detection: PlantDoc fine-tune** (14h)
   - Download PlantDoc (2,569 images, 30 classes)
   - Fine-tune Daksh159/MobileNetV2 on PlantDoc subset (focus on Karnataka crops: cotton, rice, maize, chilli, tomato, sugarcane)
   - Apply Platt scaling
   - Export to ONNX
   - Write test comparing lab vs field accuracy
   - **Expected impact:** Better field robustness (~65–75% field accuracy vs. current lab-only 99%)

8. **Disease fallback: Gemini integration** (4h)
   - Wrap Gemini Vision API in a function matching `ImageDiseaseRiskModel` interface
   - Call when in-model confidence <60%
   - Handle rate limits, errors gracefully
   - **Expected impact:** Fallback for edge cases, 500+ disease coverage

9. **Deploy ONNX models to prod** (2h)
   - Swap `crop_rf.joblib` → quantized ONNX in Render services
   - Test inference path end-to-end
   - Monitor latency & memory
   - **Expected impact:** Reduced disk footprint; enabler for mobile deployment

### Phase 3: Aspiration (Post-launch)
10. **Leaf segmentation (SAM)** (6h)
    - Integrate Segment Anything Model for disease detection
    - Preprocess: segment leaf → classify disease on segmented ROI
    - Expected: 15–20% accuracy boost on field images
    - **Defer until Phase 2 deployment is stable**

---

## Sources

### Crop Recommendation
- [ICRISAT VDSA Dataset](https://zenodo.org/records/8224522)
- [FAO EcoCrop Database](https://data.apps.fao.org/catalog/dataset/ecocrop)
- [FAO EcoCrop GitHub](https://github.com/OpenCLIM/ecocrop)
- [data.gov.in District APY](https://www.data.gov.in/catalog/district-wise-season-wise-crop-production-statistics)
- [Soil Health Card Scheme](https://soilhealth.dac.gov.in/)
- [BHOOMI Geoportal](https://bhoomigeoportal-nbsslup.in/)
- [SoilGrids v2.0](https://isric.org/explore/soilgrids)
- [Hugging Face CropSeek-LLM](https://huggingface.co/persadian/CropSeek-LLM)
- [Hugging Face AgroSense Paper](https://huggingface.co/papers/2509.01344)
- [Kaggle Crop Recommendation Dataset](https://www.kaggle.com/datasets/siddharthss/crop-recommendation-dataset)
- [ICAR Soil Health Card NPK Ranges](https://diragri.assam.gov.in/portlet-innerpage/soil-health-card)

### Irrigation
- [Open-Meteo ET₀ API](https://openmeteo.substack.com/p/reference-evapotranspiration-for)
- [FAO Irrigation and Drainage Paper 56](http://www.climasouth.eu/sites/default/files/FAO%2056.pdf)
- [Python pyfao56 Implementation](https://github.com/kthorp/pyfao56)
- [LightGBM-Autoformer Framework](https://link.springer.com/chapter/10.1007/978-3-032-23547-3_35)
- [XGBoost Soil Moisture Prediction](https://link.springer.com/article/10.1007/s42452-026-08673-3)
- [Hybrid LSTM-XGBoost Multistep Prediction](https://doi.org/10.3390/agriengineering7080260)

### Disease Detection
- [PlantDoc Dataset](https://dl.acm.org/doi/10.1145/3371158.3371196)
- [PlantDoc Roboflow](https://public.roboflow.com/object-detection/plantdoc)
- [TinyCNN 193K-Parameter On-Device Model](https://arxiv.org/pdf/2609.20290)
- [Daksh159 MobileNetV2 Model](https://huggingface.co/Daksh159/plant-disease-mobilenetv2)
- [prof-freakenstein PlantNet Ensemble](https://huggingface.co/prof-freakenstein/plantnet-disease-detection)
- [Mobile-Friendly Lightweight CNN Benchmark](https://arxiv.org/pdf/2508.10817)
- [FieldPlant Dataset](https://ieeexplore.ieee.org/document/10086516/)
- [Gemini Multimodal Disease Detection](https://github.com/Ni735h/AgriVision-AI)
- [Multimodal LLM + CNN Framework](https://arxiv.org/pdf/2504.20419)

### Cross-Cutting
- [ONNX Quantization Guide](https://github.com/devingarg/onnx-quantization)
- [ONNX Runtime Model Optimization](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html)
- [Platt Scaling & Temperature Scaling](https://www.researchgate.net/publication/336146906_Well-calibrated_Model_Uncertainty_with_Temperature_Scaling_for_Dropout_Variational_Inference)
- [sklearn Backward Compatibility Issue #26798](https://github.com/scikit-learn/scikit-learn/issues/26798)
- [ONNX Export from XGBoost](https://theneuralbase.com/xgboost/learn/advanced/onnx-export-from-xgboost/)
- [ONNX Export from LightGBM](https://theneuralbase.com/lightgbm/learn/advanced/onnx-export-from-lightgbm/)
- [sklearn 1.4.2 Model Persistence](https://scikit-learn.org/1.4/model_persistence.html)

---

**Report Author Notes:**
- All dataset URLs and model links verified as of 2026-09-24.
- Accuracy figures sourced from published research; unverified claims flagged as "unspecified" or "research only."
- Effort estimates assume single developer, no parallelization; actual team velocity may differ.
- Cross-team dependencies (frontend integration, API versioning) not included; coordinate with frontend phase.
