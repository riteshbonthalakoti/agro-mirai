# Datasets

| Dataset | File | Used for |
|---|---|---|
| Crop recommendation | [`raw/Crop_recommendation.csv`](raw/Crop_recommendation.csv) | Original crop-recommendation model training (2,200 rows) |
| Irrigation prediction | [`raw/irrigation_prediction.csv`](raw/irrigation_prediction.csv) | Original irrigation/urgency model training (10,000 rows) |
| Leaf disease (PlantVillage) | not stored here — too large (~55,000 images) | Disease CNN training (`services/cnn-onnx/model/disease_cnn_mobilenetv2.onnx`) |

The leaf disease dataset is the standard PlantVillage corpus — Kaggle dataset
[`abdallahalidev/plantvillage-dataset`](https://www.kaggle.com/datasets/abdallahalidev/plantvillage-dataset),
`color/` split, 38 classes, ~55,000 images. See
[`decisions/0018-disease-cnn.md`](../decisions/0018-disease-cnn.md) for the full training
write-up and [`models/disease_cnn_class_names.json`](../services/cnn-onnx/model/disease_cnn_class_names.json)
for the class list.

Note: the crop and irrigation CSVs above are kept for reference/reproducibility, but the
live app no longer uses the models trained on them — both were replaced by rule-based
engines (FAO EcoCrop, FAO-56 water balance). See
[`decisions/0029-remove-tabular-service-and-rf-models.md`](../decisions/0029-remove-tabular-service-and-rf-models.md)
and [`docs/ALGORITHMS.md`](../docs/ALGORITHMS.md) for why.
