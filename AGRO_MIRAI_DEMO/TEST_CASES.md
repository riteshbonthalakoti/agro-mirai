# AGRO MIRAI: Test Cases (Backend and Models)

Every case was executed live on the demo backend: **53 of 53 passed**. Columns follow the reference deck: Slno, Module, Test case, Expected result, Status, Work Done.

## Backend

### 13.1 Unit Testing: Backend

| Slno | Module | Test case | Expected result | Status | Work Done |
|---|---|---|---|---|---|
| 1. | Health endpoint | GET /health | HTTP 200 and {"status": "ok"} | Completed | Tested live: HTTP 200 {'status': 'ok'} |
| 2. | API key security | GET /fields with no key, then with a wrong key | Both rejected with HTTP 401 UNAUTHORIZED | Completed | Tested live: no key: HTTP 401, wrong key: HTTP 401 |
| 3. | Farmer profile | GET /farmers/me | HTTP 200 with the farmer's name and no password hash in the reply | Completed | Tested live: HTTP 200, name=Ritesh, language=hi |
| 4. | Field listing | GET /fields | HTTP 200, at least 4 fields, each with latitude, longitude and area | Completed | Tested live: HTTP 200, 4 fields |
| 5. | Field validation (range) | POST /fields with latitude 200 | HTTP 400 BAD_REQUEST, nothing is saved | Completed | Tested live: HTTP 400: latitude must be <= 90 |
| 6. | Field validation (missing data) | POST /fields without the name | HTTP 400 that names the missing field | Completed | Tested live: HTTP 400: Missing required fields: name |
| 7. | Unknown field | GET /fields/does-not-exist | HTTP 404 NOT_FOUND (not a 500) | Completed | Tested live: HTTP 404 NOT_FOUND |
| 8. | Image upload validation | Upload a text file (app.py) as the image | HTTP 400 "file is not a valid image" | Completed | Tested live: HTTP 400: file is not a valid image |
| 9. | Feedback validation | POST /feedback with rating 9 | HTTP 400 BAD_REQUEST | Completed | Tested live: HTTP 400: rating must be an integer between 1 and 5 |
| 10. | Weather adapter (Open-Meteo) | Fetch live weather for the Ballari field coordinates | Weather rows returned with temperature and humidity, source open_meteo | Completed | Tested live: 7 rows, source open_meteo, first temp 27.2 C |
| 11. | Soil adapter (SoilGrids) | Fetch live soil data for the Ballari field coordinates | A soil record returned with source soilgrids | Completed | Tested live: 1 record, source soilgrids, pH None |
| 12. | Satellite adapter (Google Earth Engine) | Fetch live NDVI for the Ballari field coordinates | NDVI between 0 and 1 from Sentinel-2, source gee_live | Completed | Tested live: source gee_live, NDVI 0.5136, scene date 2026-09-17, cloud 35.78% |
| 13. | NDVI fallback | Break the Earth Engine key, then fetch NDVI for a cached location | Adapter does not crash; it serves the stored (cache) value and reports source cache | Completed | Tested live: source cache, NDVI 0.2019 |
| 14. | Feature builder | Build model features for the Ballari field from stored readings | 7/14/30-day weather aggregates, soil values, NDVI and season are filled in | Completed | Tested live: temp7d 26.9 C, humidity14d 75%, rain30d 16.9 mm, season kharif |
| 15. | Data store ownership | Read a field using a different farmer's id | Nothing returned (a farmer cannot read another farmer's field) | Completed | Tested live: other farmer -> None, owner -> North Cotton Plot |

### 13.2 Integration Testing: Backend

| Slno | Integrated Modules | Test case | Expected result | Status | Work Done |
|---|---|---|---|---|---|
| 1. | Field API + live data adapters + data store | POST /fields, then GET /fields/<id>/live-data | HTTP 201 with weather, soil and NDVI all fetched; the readings are then stored and readable | Completed | Tested live: HTTP 201 in 20s; stored 7 weather rows, 1 soil, 1 NDVI |
| 2. | Live data + feature builder | GET /fields/<new field>/live-data | Model features are computed from the live readings and record where each came from | Completed | Tested live: temp7d 27.2 C, NDVI source gee_live, weather source open_meteo |
| 3. | API + crop model | GET /fields/<id>/recommendation | HTTP 200 with a recommended crop, confidence and alternatives | Completed | Tested live: HTTP 200, muskmelon (confidence 0.36), alternatives ['watermelon', 'grapes', 'chickpea'] |
| 4. | API + decision engine + explanations | GET /fields/<id>/advisories | HTTP 200; newest advisory has a plain-language explanation and a severity | Completed | Tested live: HTTP 200, severity moderate, title 'Advisory for muskmelon' |
| 5. | Image upload + CNN + data store | POST a leaf photo, then read the saved alert from the database | HTTP 200 with source cnn, and the same alert id is stored in the database | Completed | Tested live: HTTP 200, source cnn, stored in database: True |
| 6. | Advisory + feedback | POST /feedback for a real advisory, then GET /feedback | HTTP 201, and the rating appears in the feedback list | Completed | Tested live: HTTP 201, rating 4, listed: True |
| 7. | Feedback + data store integrity | POST /feedback for an advisory that does not exist | HTTP 404 (feedback cannot point at a missing advisory) | Completed | Tested live: HTTP 404: Advisory not found |
| 8. | Supabase (read only) + local demo database | Compare Supabase records with their local copy | The farmer and the real field exist in both, with identical names and coordinates | Completed | Tested live: Supabase field 'North Cotton Plot' (15.14, 76.92) matches the local copy |

### 13.3 System Testing: Backend

| Slno | System Function | Test case | Expected result | Status | Work Done |
|---|---|---|---|---|---|
| 1. | Complete farmer journey | Add a field, then live data, crop, irrigation, disease, advisory and feedback | Every step succeeds in one run without any manual data entry | Completed | Tested live: HTTP codes [201, 200, 200, 200, 200, 201], total 34s |
| 2. | Real data safety | Compare the real Supabase record counts before the test run and after it | No count changes: nothing done in the demo can modify the production database | Completed | Tested live: before {'farmers': 1, 'fields': 1, 'advisories': 16, 'alerts': 1, 'feedback': 0} / after {'farmers': 1, 'fields': 1, 'advisories': 16, 'alerts':... |
| 3. | Live data freshness | Check the age of the newest weather observation stored for the new field | Newest observed (non forecast) weather is not more than 3 days old | Completed | Tested live: newest observation 2026-09-20T14:30:00Z (0 days old) |
| 4. | Robustness to bad requests | Send malformed JSON, wrong data types, an empty body and a huge value | Every bad request gets a clean HTTP 4xx error, never a 500 crash | Completed | Tested live: HTTP codes [400, 400, 400, 400, 400, 404] |
| 5. | Response time | Time a simple request and the full advisory request | GET /fields under 1 second, advisory under 15 seconds | Completed | Tested live: /fields 0.01s, advisory 0.3s |
| 6. | Concurrent users | Send 8 requests at the same moment | All 8 answered HTTP 200 | Completed | Tested live: HTTP codes [200, 200, 200, 200, 200, 200, 200, 200] |

## Models

### 13.4 Unit Testing: Models

| Slno | Module | Test case | Expected result | Status | Work Done |
|---|---|---|---|---|---|
| 1. | Model files | Load the three trained model files | crop_rf.joblib, irrigation_rf.joblib and disease_cnn_mobilenetv2.pt all exist and load | Completed | Tested live: loaded; sizes in MB {'crop_rf.joblib': 7.3, 'irrigation_rf.joblib': 64.6, 'disease_cnn_mobilenetv2.pt': 9.3} |
| 2. | Crop model: training evaluation | Read the held-out evaluation report of each trained model | Crop accuracy >= 0.99, irrigation >= 0.70, disease CNN >= 0.99 on data not used for training | Completed | Tested live: crop 0.9955 (macro-F1 0.9955), irrigation 0.7240, disease CNN 0.9924 |
| 3. | Crop model: prediction | Predict the crop for 300 rows of the Kaggle dataset | At least 97% predicted correctly; probabilities of the 22 crops add up to 1 | Completed | Tested live: 99.7% correct on 300 rows, 22 classes, probabilities sum to 1.000 |
| 4. | Crop model: regional check | Check cotton and muskmelon against the Ballari district crop list | Cotton is in the regional list, muskmelon is not (so it would be flagged out_of_region) | Completed | Tested live: regional crops ['chickpea', 'cotton', 'maize', 'pigeonpeas', 'rice'] |
| 5. | Irrigation model: ET0 (FAO-56) | Compute ET0 for 15 N, day 200, mean 27 C, min 22 C, max 33 C and compare with a hand calculation | Matches the hand-calculated FAO-56 Hargreaves value and lies in the normal 2 to 8 mm/day range | Completed | Tested live: model 5.339 mm/day, hand calculation 5.339 mm/day |
| 6. | Irrigation model: crop coefficient | Growth stage and Kc for cotton at 81 days after sowing and for rice at 10 days | Cotton is in mid-season with Kc above 1.0; rice at 10 days is in the initial stage with a lower Kc | Completed | Tested live: cotton: mid_season, Kc 1.18; rice: initial, Kc 1.05 |
| 7. | Irrigation model: water balance | Same field, once with 0 mm rain and once with 60 mm rain in 7 days | Less water is recommended when more rain has fallen, and never below the 2 mm minimum | Completed | Tested live: 0 mm rain -> 36.6 mm, 60 mm rain -> 2.0 mm |
| 8. | Irrigation model: urgency | Predict irrigation urgency for the live features of all 4 fields | Urgency is one of low, moderate, high for every field | Completed | Tested live: urgency per field ['moderate', 'moderate', 'moderate', 'moderate'] |
| 9. | Disease model (weather based) | Score a hot, humid, rainy scenario and a dry scenario | Wet and humid scenario gives high or severe risk; dry hot scenario gives low risk | Completed | Tested live: wet/humid -> severe, dry/hot -> low |
| 10. | Disease CNN: classification | Classify 6 leaf photos (3 crops, healthy and diseased) | All 6 photos are classified as their correct disease or healthy class | Completed | Tested live: 6/6 correct |
| 11. | Disease CNN: risk level | Compare the risk level of a healthy leaf and a diseased leaf | Healthy leaf -> low; diseased leaf -> moderate or higher | Completed | Tested live: healthy apple -> low, tomato late blight -> severe |
| 12. | Disease CNN: output validity | Inspect the top-3 probabilities of a prediction | 3 classes, probabilities in 0..1, in descending order, top one equals the reported confidence | Completed | Tested live: top-3 [('Corn_(maize)___Common_rust_', 1.0), ('Tomato___Late_blight', 0.0), ('Pepper,_bell___Bacterial_spot', 0.0)] |
| 13. | Disease CNN: input handling | Send the same leaf as JPG, as PNG, and as a tiny 32x32 image | JPG and PNG give the same class; the tiny image is handled without error | Completed | Tested live: JPG Grape___Black_rot, PNG Grape___Black_rot, 32x32 Grape___healthy (0.2621) |

### 13.5 Integration Testing: Models

| Slno | Integrated Modules | Test case | Expected result | Status | Work Done |
|---|---|---|---|---|---|
| 1. | Live features + crop model | Get the crop recommendation for all 4 fields through the API | HTTP 200 for every field, each crop is one of the 22 known crops | Completed | Tested live: [(200, 'muskmelon'), (200, 'muskmelon'), (200, 'muskmelon'), (200, 'watermelon')] |
| 2. | Live features + FAO-56 + irrigation model | Get irrigation advice for all 4 fields through the API | Depth is at least 2 mm and the rationale shows the ET0, ETc and rainfall numbers used | Completed | Tested live: (depth mm, urgency, rationale ok) per field [(19.7, 'moderate', True), (32.7, 'moderate', True), (34.5, 'moderate', True), (39.3, 'moderate', True)] |
| 3. | Weather features + disease model | GET /fields/<id>/disease-risk for the real field | A complete alert with a risk level, action and 7-day window, source environmental | Completed | Tested live: risk moderate, source environmental, action 'Increase field scouting frequency; watch for ...' |
| 4. | Decision engine (three models combined) | Read irrigation urgency, disease risk and the advisory severity for one field | Advisory severity equals the higher of the irrigation urgency and the disease risk level | Completed | Tested live: irrigation moderate, disease moderate -> expected moderate, advisory moderate |
| 5. | SHAP explanations + decision engine | Read the text of the newest advisory | It names the biggest factors behind the recommendation and adds the regional caution when the crop is out of region | Completed | Tested live: The biggest factors behind this recommendation of muskmelon were: rainfall (16.90, increases the result); N (250.00, increases the result); P... |
| 6. | Disease CNN + alert record | POST a leaf photo and check the fields of the saved alert | Alert has id, disease name, risk level, confidence, action and time window | Completed | Tested live: disease 'Grape: Black rot', risk severe, confidence 1.000 |
| 7. | Models use each field's own data | Compare irrigation depth across the 4 fields | The fields do not all get the same answer, so the models react to the live data of each location | Completed | Tested live: irrigation depth (mm) per field [19.7, 32.7, 34.5, 39.3] |

### 13.6 System Testing: Models

| Slno | System Function | Test case | Expected result | Status | Work Done |
|---|---|---|---|---|---|
| 1. | All models on all fields | Run crop, irrigation, disease and advisory for every field | 16 model calls, all HTTP 200 | Completed | Tested live: 16/16 returned HTTP 200 |
| 2. | CNN honesty check | Upload a photo that is not a leaf (a farmer portrait) | The answer comes with a clearly lower confidence than a real leaf (below 0.9), so the low confidence can be flagged | Completed | Tested live: confidence 0.52 (real leaves score 0.99+), guess 'Strawberry: Leaf scorch' |
| 3. | Repeatability | Ask for the same crop recommendation and irrigation depth twice | Identical answers both times (the models are deterministic for the same data) | Completed | Tested live: first ('muskmelon', 19.7), second ('muskmelon', 19.7) |
| 4. | Image model accuracy on the demo set | Send all 6 leaf photos through the live API | All 6 correct through the full backend, each marked source cnn | Completed | Tested live: 6/6 correct; tomato_late_blight: Tomato: Late blight (1.00); maize_common_rust: Corn (maize): Common rust (1.00); grape_black_rot: Grape: Black... |
