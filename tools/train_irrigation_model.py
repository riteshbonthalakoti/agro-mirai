"""Trains the Module 07 irrigation urgency model.

Reads the Kaggle irrigation-water-requirement dataset (already
downloaded via ``kaggle datasets download
miadul/irrigation-water-requirement-prediction-dataset -p data/raw
--unzip``, per ``docs/architecture.md``), trains a
RandomForestClassifier on 6 columns (``Soil_pH, Soil_Moisture,
Temperature_C, Humidity, Rainfall_mm, Season``) against the 3-class
``Irrigation_Need`` label (``Low``/``Medium``/``High``), and writes:

- ``models/irrigation_rf.joblib`` — the trained artifact (gitignored,
  see ``decisions/0008-irrigation-model-feature-mapping.md`` and
  ``docs/architecture.md`` for why this is reproducible-not-committed).
- ``docs/eval/irrigation_rf_eval.json`` — accuracy, macro-F1, confusion
  matrix, and the exact column order the model expects (committed).

Only ``urgency`` is a trained output — ``recommended_depth_mm`` and the
advisory window are a documented rule-based lookup keyed off the
predicted urgency (ADR 0008), not part of this training script.

Fixed random seed (42) throughout for reproducibility: the train/test
split and the RandomForestClassifier itself. Re-running this script from
a clean checkout should reproduce identical eval numbers.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parent.parent
DATA_CSV = ROOT / "data" / "raw" / "irrigation_prediction.csv"
MODEL_DIR = ROOT / "models"
MODEL_PATH = MODEL_DIR / "irrigation_rf.joblib"
EVAL_DIR = ROOT / "docs" / "eval"
EVAL_PATH = EVAL_DIR / "irrigation_rf_eval.json"

RANDOM_SEED = 42
NUMERIC_FEATURE_COLUMNS = [
    "Soil_pH",
    "Soil_Moisture",
    "Temperature_C",
    "Humidity",
    "Rainfall_mm",
]
CATEGORICAL_FEATURE_COLUMNS = ["Season"]
FEATURE_COLUMNS = NUMERIC_FEATURE_COLUMNS + CATEGORICAL_FEATURE_COLUMNS
LABEL_COLUMN = "Irrigation_Need"


def load_dataset(csv_path: Path = DATA_CSV) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(
            f"{csv_path} not found. Run:\n"
            "  kaggle datasets download "
            "miadul/irrigation-water-requirement-prediction-dataset "
            "-p data/raw --unzip"
        )
    return pd.read_csv(csv_path)


def _one_hot_season(df: pd.DataFrame) -> pd.DataFrame:
    """One-hot encodes Season into the fixed 3-column layout the model
    expects, regardless of which seasons are present in a given slice
    of data (important for train/test splits and single-row inference
    alike, where not all seasons may appear)."""
    encoded = pd.get_dummies(df["Season"], prefix="season")
    for season in ("Kharif", "Rabi", "Zaid"):
        col = f"season_{season}"
        if col not in encoded.columns:
            encoded[col] = 0
    return encoded[["season_Kharif", "season_Rabi", "season_Zaid"]]


def build_model_matrix(df: pd.DataFrame) -> pd.DataFrame:
    return pd.concat([df[NUMERIC_FEATURE_COLUMNS], _one_hot_season(df)], axis=1)


def train(df: pd.DataFrame) -> dict:
    x = build_model_matrix(df)
    y = df[LABEL_COLUMN]

    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=0.2, random_state=RANDOM_SEED, stratify=y
    )

    model = RandomForestClassifier(
        n_estimators=200, random_state=RANDOM_SEED, class_weight="balanced"
    )
    model.fit(x_train, y_train)

    y_pred = model.predict(x_test)
    labels = sorted(y.unique())
    report = {
        "feature_columns": list(x.columns),
        "label_column": LABEL_COLUMN,
        "labels": labels,
        "random_seed": RANDOM_SEED,
        "n_train": len(x_train),
        "n_test": len(x_test),
        "accuracy": accuracy_score(y_test, y_pred),
        "macro_f1": f1_score(y_test, y_pred, average="macro"),
        "confusion_matrix": confusion_matrix(y_test, y_pred, labels=labels).tolist(),
    }
    return {"model": model, "report": report}


def main() -> int:
    df = load_dataset()
    result = train(df)

    MODEL_DIR.mkdir(exist_ok=True)
    EVAL_DIR.mkdir(parents=True, exist_ok=True)

    import joblib

    joblib.dump(result["model"], MODEL_PATH)
    EVAL_PATH.write_text(json.dumps(result["report"], indent=2), encoding="utf-8")

    report = result["report"]
    print(f"accuracy={report['accuracy']:.4f} macro_f1={report['macro_f1']:.4f}")
    print(f"model -> {MODEL_PATH}")
    print(f"eval report -> {EVAL_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
