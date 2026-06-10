"""Train a RandomForest user-state classifier from collected feature CSV."""

from __future__ import annotations

import csv
import json
import math
import pickle
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from models.vision.user_state_features import USER_STATE_FEATURE_FIELDS  # noqa: E402


DATASET_PATH = PROJECT_ROOT / "data" / "user_state_dataset" / "user_state_samples.csv"
MODEL_PATH = PROJECT_ROOT / "models" / "vision" / "user_state_rf.pkl"
FEATURES_PATH = PROJECT_ROOT / "models" / "vision" / "user_state_rf_features.json"
VALID_LABELS = {"normal", "focused", "distracted", "tired"}


def _load_rows(path: Path) -> tuple[list[list[float]], list[str], list[str]]:
    if not path.exists():
        print(f"[TrainUserStateClassifier] Dataset not found: {path}")
        return [], [], []

    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            print("[TrainUserStateClassifier] Dataset is empty.")
            return [], [], []

        feature_columns = [
            field
            for field in USER_STATE_FEATURE_FIELDS
            if field != "timestamp" and field in reader.fieldnames
        ]
        if not feature_columns:
            print("[TrainUserStateClassifier] No usable feature columns found.")
            return [], [], []

        rows: list[list[float]] = []
        labels: list[str] = []
        for item in reader:
            label = str(item.get("label", "")).strip()
            if label not in VALID_LABELS:
                continue
            values = [_to_float(item.get(field)) for field in feature_columns]
            missing = sum(1 for value in values if not math.isfinite(value))
            if missing / max(1, len(values)) > 0.3:
                continue
            rows.append(values)
            labels.append(label)

    return rows, labels, feature_columns


def _to_float(value: Any) -> float:
    try:
        result = float(value)
        return result if math.isfinite(result) else float("nan")
    except Exception:
        return float("nan")


def main() -> int:
    try:
        import numpy as np
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.impute import SimpleImputer
        from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
        from sklearn.model_selection import train_test_split
        from sklearn.pipeline import Pipeline
    except Exception as exc:
        print("[TrainUserStateClassifier] Missing training dependency.")
        print(f"[TrainUserStateClassifier] {exc}")
        print("[TrainUserStateClassifier] Install: pip install scikit-learn")
        return 1

    rows, labels, feature_columns = _load_rows(DATASET_PATH)
    if len(rows) < 20:
        print(f"[TrainUserStateClassifier] Not enough samples: {len(rows)}. Collect at least 20 rows.")
        return 1

    label_counts = {label: labels.count(label) for label in sorted(set(labels))}
    if len(label_counts) < 2:
        print(f"[TrainUserStateClassifier] Need at least two labels. Current labels: {label_counts}")
        return 1
    if any(count < 2 for count in label_counts.values()):
        print(f"[TrainUserStateClassifier] Each label needs at least 2 samples. Current labels: {label_counts}")
        return 1

    x = np.asarray(rows, dtype=float)
    y = np.asarray(labels)
    stratify = y if min(label_counts.values()) >= 2 else None
    try:
        x_train, x_test, y_train, y_test = train_test_split(
            x,
            y,
            test_size=0.25,
            random_state=42,
            stratify=stratify,
        )
    except Exception as exc:
        print(f"[TrainUserStateClassifier] Train/test split failed: {exc}")
        return 1

    model = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=200,
                    random_state=42,
                    class_weight="balanced",
                    min_samples_leaf=2,
                ),
            ),
        ]
    )
    model.fit(x_train, y_train)
    y_pred = model.predict(x_test)

    print("[TrainUserStateClassifier] labels:", label_counts)
    print("[TrainUserStateClassifier] accuracy:", round(float(accuracy_score(y_test, y_pred)), 4))
    print("[TrainUserStateClassifier] classification_report:")
    print(classification_report(y_test, y_pred, labels=sorted(label_counts), zero_division=0))
    print("[TrainUserStateClassifier] confusion_matrix:")
    print(confusion_matrix(y_test, y_pred, labels=sorted(label_counts)))

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MODEL_PATH.open("wb") as f:
        pickle.dump(model, f)
    with FEATURES_PATH.open("w", encoding="utf-8") as f:
        json.dump(feature_columns, f, ensure_ascii=False, indent=2)

    print(f"[TrainUserStateClassifier] model saved: {MODEL_PATH}")
    print(f"[TrainUserStateClassifier] features saved: {FEATURES_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
