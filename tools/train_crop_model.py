"""Trains the Module 06 crop recommendation model.

Reads the Kaggle crop-recommendation dataset (already downloaded via
``kaggle datasets download atharvaingle/crop-recommendation-dataset -p
data/raw --unzip``, per ``docs/architecture.md``), trains a
RandomForestClassifier on its native 7 columns (``N, P, K, temperature,
humidity, ph, rainfall``), and writes:

- ``models/crop_rf.joblib`` — the trained artifact (gitignored, see
  ``decisions/0007-crop-model-feature-mapping.md`` and
  ``docs/architecture.md`` for why this is reproducible-not-committed).
- ``docs/eval/crop_rf_eval.json`` — accuracy, macro-F1, confusion matrix,
  and the exact column order the model expects (committed — this is
  the diffable, reviewable part).

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
DATA_CSV = ROOT / "data" / "raw" / "Crop_recommendation.csv"
MODEL_DIR = ROOT / "models"
MODEL_PATH = MODEL_DIR / "crop_rf.joblib"
EVAL_DIR = ROOT / "docs" / "eval"
EVAL_PATH = EVAL_DIR / "crop_rf_eval.json"

RANDOM_SEED = 42
FEATURE_COLUMNS = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]
LABEL_COLUMN = "label"


def load_dataset(csv_path: Path = DATA_CSV) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(
            f"{csv_path} not found. Run:\n"
            "  kaggle datasets download atharvaingle/crop-recommendation-dataset "
            "-p data/raw --unzip"
        )
    return pd.read_csv(csv_path)


def train(df: pd.DataFrame) -> dict:
    x = df[FEATURE_COLUMNS]
    y = df[LABEL_COLUMN]

    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=0.2, random_state=RANDOM_SEED, stratify=y
    )

    model = RandomForestClassifier(n_estimators=200, random_state=RANDOM_SEED)
    model.fit(x_train, y_train)

    y_pred = model.predict(x_test)
    labels = sorted(y.unique())
    report = {
        "feature_columns": FEATURE_COLUMNS,
        "random_seed": RANDOM_SEED,
        "n_train": len(x_train),
        "n_test": len(x_test),
        "accuracy": accuracy_score(y_test, y_pred),
        "macro_f1": f1_score(y_test, y_pred, average="macro"),
        "labels": labels,
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
