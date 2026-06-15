"""Lightweight RandomForest user-state classifier wrapper.

The classifier only predicts: normal, focused, distracted, tired.
Hard states such as away, return, low_light, study_long, camera_error, unknown
remain owned by the rule layer in UserStateDetector.
"""

from __future__ import annotations

import json
import math
import pickle
from pathlib import Path
from typing import Any


MODEL_PATH = Path(__file__).resolve().parent / "user_state_rf.pkl"
FEATURES_PATH = Path(__file__).resolve().parent / "user_state_rf_features.json"
MODEL_STATE_CODES = {"normal", "focused", "distracted", "tired"}


class UserStateClassifier:
    """Load and run the trained RandomForest classifier with safe fallback."""

    def __init__(
        self,
        model_path: str | Path = MODEL_PATH,
        features_path: str | Path = FEATURES_PATH,
    ) -> None:
        self.model_path = Path(model_path)
        self.features_path = Path(features_path)
        self.model: Any = None
        self.feature_names: list[str] = []
        self.load_error: str = ""
        self._load()

    @property
    def available(self) -> bool:
        return self.model is not None and bool(self.feature_names)

    def predict(self, features: dict[str, Any] | None) -> dict[str, Any]:
        """Return a stable classification dict without raising to callers."""
        features = features or {}
        if not self.available:
            return self._rule_fallback(features, self.load_error or "model_unavailable")

        try:
            row = [[self._to_float(features.get(name, 0.0)) for name in self.feature_names]]
            classes = getattr(self.model, "classes_", None)
            labels = list(classes) if classes is not None else []
            if hasattr(self.model, "predict_proba"):
                probabilities = list(self.model.predict_proba(row)[0])
                scored = {
                    str(label): float(probabilities[index])
                    for index, label in enumerate(labels)
                    if index < len(probabilities)
                }
            else:
                label = str(self.model.predict(row)[0])
                scored = {label: 1.0}

            state_code, confidence = self._best_valid_label(scored)
            return self._threshold_result(state_code, confidence, "rf_classifier")
        except Exception as exc:
            return self._rule_fallback(features, f"predict_failed:{exc}")

    def _load(self) -> None:
        if not self.model_path.exists() or not self.features_path.exists():
            self.load_error = "model_or_features_missing"
            return
        try:
            with self.model_path.open("rb") as f:
                self.model = pickle.load(f)
            with self.features_path.open("r", encoding="utf-8") as f:
                loaded = json.load(f)
            self.feature_names = [str(item) for item in loaded if str(item)]
        except Exception as exc:
            self.model = None
            self.feature_names = []
            self.load_error = f"load_failed:{exc}"

    @staticmethod
    def _best_valid_label(scored: dict[str, float]) -> tuple[str, float]:
        valid = {
            label: float(confidence)
            for label, confidence in scored.items()
            if label in MODEL_STATE_CODES and math.isfinite(float(confidence))
        }
        if not valid:
            return "normal", 0.0
        state_code = max(valid, key=valid.get)
        return state_code, max(0.0, min(1.0, valid[state_code]))

    @staticmethod
    def _threshold_result(state_code: str, confidence: float, source: str) -> dict[str, Any]:
        confidence = max(0.0, min(1.0, float(confidence)))
        original = state_code if state_code in MODEL_STATE_CODES else "normal"
        accepted = original
        reason = f"{source}:{original}:{confidence:.2f}"

        if confidence < 0.65:
            accepted = "normal"
            reason = f"low_confidence:{original}:{confidence:.2f}"
        elif original == "distracted" and confidence < 0.70:
            accepted = "normal"
            reason = f"distracted_below_threshold:{confidence:.2f}"
        elif original == "tired" and confidence < 0.65:
            accepted = "normal"
            reason = f"tired_below_threshold:{confidence:.2f}"
        elif original == "focused" and confidence < 0.65:
            accepted = "normal"
            reason = f"focused_below_threshold:{confidence:.2f}"

        return {
            "state_code": accepted,
            "confidence": confidence if accepted == original else min(confidence, 0.64),
            "reason": reason,
            "source": source,
        }

    def _rule_fallback(self, features: dict[str, Any], reason: str) -> dict[str, Any]:
        eye_closed_ratio = self._to_float(features.get("eye_closed_ratio", features.get("eye_closed", 0.0)))
        looking_down_ratio = self._to_float(features.get("looking_down_ratio", features.get("looking_down", 0.0)))
        looking_side_ratio = self._to_float(features.get("looking_side_ratio", features.get("looking_side", 0.0)))
        motion_stability = self._to_float(features.get("motion_stability", 0.0))
        face_missing_ratio = self._to_float(features.get("face_missing_ratio", features.get("face_missing", 1.0)))

        state_code = "normal"
        confidence = 0.55
        if eye_closed_ratio >= 0.55:
            state_code = "tired"
            confidence = 0.68
        elif looking_down_ratio >= 0.70 or looking_side_ratio >= 0.75:
            state_code = "distracted"
            confidence = 0.70
        elif face_missing_ratio <= 0.15 and motion_stability >= 0.80:
            state_code = "focused"
            confidence = 0.66

        result = self._threshold_result(state_code, confidence, "rule_fallback")
        result["reason"] = f"rule_fallback:{reason}:{result['reason']}"
        return result

    @staticmethod
    def _to_float(value: Any) -> float:
        try:
            result = float(value)
            return result if math.isfinite(result) else 0.0
        except Exception:
            return 0.0


__all__ = ["UserStateClassifier", "MODEL_PATH", "FEATURES_PATH", "MODEL_STATE_CODES"]
