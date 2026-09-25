# 0028 - Disease: field-photo fine-tune, honest photo answers, crop-specific weather risk

Date: 2026-09-25. Extends 0018 (disease CNN) and 0009 (rule-based risk).

## What was wrong (measured)
The PlantVillage-only MobileNetV2 scores 99% on PlantVillage but PlantVillage is single leaves on plain backgrounds. On PlantDoc's test split (internet photos with real backgrounds, the closest free stand-in for a phone photo) it got **22.5% top-1** (top-3 43.6%, macro-F1 0.20), while its mean confidence was 82%. Calibration error (ECE) was 0.60, and even when it was "confident" (>= 0.55) it was right only 25% of the time. So a confident-looking wrong answer was the normal case on real photos.

## What we did
1. **Fine-tune on PlantDoc** (`tools/train_disease_cnn_plantdoc.py`, Colab T4 via the colab CLI). Cropped-PlantDoc train (2,342 images; every PlantDoc folder mapped onto an existing PlantVillage class, none skipped) x2 plus a PlantVillage replay (90 images/class) so lab photos are not forgotten, distillation from the old model (w=0.5), label smoothing 0.1, last 6 blocks unfrozen, 12 epochs. Best epoch picked on a 10% PlantDoc validation slice, never the test split.
2. **Temperature calibration** (`tools/calibrate_disease_cnn.py`): T = 1.35 fitted on the PlantDoc validation slice, stored in `services/cnn-onnx/model/disease_cnn_calibration.json` (service reads it; no file = T 1.0).
3. **Honest photo answers** (`disease_cnn_labels.py`, CNN service): below 0.55 confidence the answer is "Not sure. Best guess: X" with the runners-up and retake advice, never a confident "severe"/"healthy". The main API adds a note when the photo model was not trained on the field's crop (e.g. cotton) or the photo looks like a different crop.
4. **Crop-specific weather risk** (`disease_named_risks.py`): for 20 crops, the disease(s) usually said to be favoured by the recent week of real weather (humid days, wet days, temperature band) plus the rain forecast, with a trend. Named "(weather-based risk, not a diagnosis)". Unlisted crops keep the generic score. The bands are typical textbook infection conditions, approximate, not fitted to this project's data.

## Results (held out, `docs/eval/disease_cnn_plantdoc_eval.json`)
| | old model | shipped (run 2) | run 1, not shipped |
|---|---|---|---|
| PlantDoc test top-1 (236 images) | 22.5% | **45.8%** | 52.1% |
| PlantDoc test top-3 | 43.6% | **76.7%** | 77.1% |
| PlantDoc test macro-F1 | 0.20 | **0.46** | 0.53 |
| PlantDoc calibration error (ECE) | 0.60 | 0.23 -> **0.11** after T=1.35 | 0.12 |
| PlantVillage lab photos (1,512 test-split images) | 99.4% | **98.7%** | 78.6% |

Run 1 had no PlantVillage replay (the loader failed) and forgot lab photos, so run 2 was trained and shipped instead. With T=1.35 and the 0.55 cut-off the model answers about 48% of field-style photos and is right 59% of the time when it does; below that it says "not sure".

## Limits
- PlantDoc is small and internet-scraped; 236 test images means roughly +/-6 points of noise on the numbers above. It is not photos from Karnataka fields.
- Only 4 of the 22 crops (apple, maize, grapes, orange) are covered by the photo model; cotton, rice, chickpea etc. get a "rough guide only" note. Covering them needs a labelled dataset of those crops, which we did not find free.
- The PlantVillage column measures forgetting, not generalisation: the old model saw those files in training.
- Named weather diseases say conditions favour a disease, not that it is present.
- Gemini/vision fallback was not built: it would send farmer photos to a third party, which needs an explicit decision.

## Data licences / attribution
- PlantDoc (Cropped-PlantDoc): Singh, Jain, Jain, Kayal, Kumawat, Batra, "PlantDoc: A Dataset for Visual Plant Disease Detection", ACM CoDS-COMAD 2020, CC BY 4.0. https://github.com/pratikkayal/PlantDoc-Dataset
- PlantVillage: Hughes & Salathe 2015, Mohanty et al. 2016; copy used for replay/evaluation: huggingface.co/datasets/mohanty/PlantVillage (CC BY-SA 3.0).
