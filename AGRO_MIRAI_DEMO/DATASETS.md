# Datasets behind AGRO MIRAI

## A. The three datasets we trained on (from Kaggle)

| # | Model | Kaggle dataset (link) | What is in it | How we trained | Result on held-out data |
|---|-------|-----------------------|---------------|----------------|-------------------------|
| 1 | Crop recommendation | https://www.kaggle.com/datasets/atharvaingle/crop-recommendation-dataset | 2,200 rows, 22 crops (100 each), 7 inputs: soil N, P, K, temperature, humidity, pH, rainfall | Random Forest classifier (scikit-learn), 80/20 split, seed 42. Notebook: `notebooks/01_crop_recommendation.ipynb` | accuracy 0.9955, macro-F1 0.9955 |
| 2 | Irrigation advisory | https://www.kaggle.com/datasets/miadul/irrigation-water-requirement-prediction-dataset | 10,000 rows: soil pH, soil moisture, organic carbon, temperature, humidity, rainfall, crop type, growth stage, season, and an irrigation-need label (Low / Medium / High) | Random Forest classifier predicts the urgency. The water depth in mm is not learned: it is computed with the FAO-56 water balance (reference evapotranspiration times crop coefficient, minus rainfall). Notebook: `notebooks/02_irrigation_advisory.ipynb` | accuracy 0.7240, macro-F1 0.5796 (the High class has only 336 rows) |
| 3 | Plant disease from a leaf photo (CNN) | https://www.kaggle.com/datasets/abdallahalidev/plantvillage-dataset | About 54,300 leaf images, 38 classes (14 crops, healthy and diseased). We used the `color/` folder only | MobileNetV2 (ImageNet pre-trained, last 3 blocks fine-tuned, new 38-way output layer), 85/15 split, 8 epochs, Adam, trained on a free Google Colab T4 GPU. Notebook: `notebooks/03_disease_risk_detection.ipynb` | validation accuracy 0.9924 |

The two CSV files for datasets 1 and 2 are included in this folder under `data/raw/`
(`Crop_recommendation.csv`, `irrigation_prediction.csv`). The PlantVillage images are about 1 GB,
so they are not included; download them from the Kaggle link.

Downloading with the Kaggle command line (needs a free Kaggle account and API token):

    kaggle datasets download -d atharvaingle/crop-recommendation-dataset
    kaggle datasets download -d miadul/irrigation-water-requirement-prediction-dataset
    kaggle datasets download -d abdallahalidev/plantvillage-dataset

Honest notes to say if the faculty asks:
- The 99.24% CNN accuracy is on a random hold-out from PlantVillage's own lab-style photos
  (single leaf, plain background). Published work shows accuracy drops on real field photos.
- Only apple, maize, grape and orange from PlantVillage overlap with the 22 crops the
  crop-recommendation model knows; the other classes (tomato, potato, etc.) are still recognised
  by the CNN.
- The crop-recommendation data is a general dataset, not Karnataka specific, so we add a
  regional check that flags a suggestion that is not grown in Ballari (Bellary) district.

## B. Other good datasets (related work, and options to improve the models)

| Dataset | Why it matters | Link |
|---------|----------------|------|
| PlantVillage, original source (Hughes and Salathe, 2015) | The original paper and image repository behind dataset 3 | Paper: https://arxiv.org/abs/1511.08060 , images: https://github.com/spMohanty/PlantVillage-Dataset , archive: https://figshare.com/articles/dataset/PlantVillage_dataset/28234004 |
| PlantDoc | 2,598 cropped images, 13 species, up to 17 disease classes, taken from real-world internet photos with cluttered backgrounds. The best next step to make the CNN work on real field photos | https://github.com/pratikkayal/PlantDoc-Dataset , paper: https://arxiv.org/abs/1911.10317 |
| ICRISAT District Level Database (India) | District-wise crop area, production and yield for 571 districts in 20 states, including Karnataka, 1966 to 2020. Useful for a Karnataka-specific crop model | http://data.icrisat.org/dld/src/crops.html |
| Kaggle: District wise major crops production in India | A ready-made CSV of district crop production | https://www.kaggle.com/datasets/ankanhore545/district-wise-major-crops-production-in-india |
| Kaggle: Predicting Irrigation Need (Playground S6E4) | A larger irrigation-need dataset from a Kaggle competition, useful to compare with dataset 2 | https://www.kaggle.com/competitions/playground-series-s6e4 |
| Kaggle: Smart Irrigation data | Sensor style irrigation data | https://www.kaggle.com/datasets/chineduchukwuemeka/smart-irrigation-data-derive-dataset |
| PlantVillage variants on Kaggle | Cleaned and updated copies of PlantVillage | https://www.kaggle.com/datasets/tushar5harma/plant-village-dataset-updated |

## C. Live data sources the backend uses at run time (no training, real-time)

| Source | What we take | Link |
|--------|--------------|------|
| Open-Meteo | Weather: temperature, humidity, rainfall for the field's coordinates | https://open-meteo.com |
| ISRIC SoilGrids | Soil pH, nitrogen, organic carbon at the field's coordinates | https://soilgrids.org |
| Google Earth Engine, Sentinel-2 (`COPERNICUS/S2_SR_HARMONIZED`) | Satellite NDVI (crop greenness) around the field | https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED |
| OpenWeatherMap | Backup weather source | https://openweathermap.org/api |
| FAO Irrigation and Drainage Paper 56 | The method behind our irrigation water balance (evapotranspiration and crop coefficients) | https://www.fao.org/4/x0490e/x0490e00.htm |
