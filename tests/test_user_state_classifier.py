import json
import os
import pickle
import sys


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.vision.user_state_classifier import UserStateClassifier  # noqa: E402


class FakeProbabilityModel:
    def __init__(self, classes, probabilities):
        self.classes_ = classes
        self._probabilities = probabilities

    def predict_proba(self, rows):
        return [self._probabilities]


def test_missing_model_uses_rule_fallback(tmp_path):
    classifier = UserStateClassifier(
        model_path=tmp_path / "missing.pkl",
        features_path=tmp_path / "missing.json",
    )

    result = classifier.predict({"looking_down_ratio": 0.8})

    assert result["source"] == "rule_fallback"
    assert result["state_code"] == "distracted"
    assert result["confidence"] >= 0.70


def test_low_confidence_model_returns_normal(tmp_path):
    model_path, features_path = _write_fake_model(
        tmp_path,
        classes=["normal", "focused", "distracted", "tired"],
        probabilities=[0.40, 0.10, 0.30, 0.20],
    )
    classifier = UserStateClassifier(model_path=model_path, features_path=features_path)

    result = classifier.predict({"feature_a": 1.0})

    assert result["source"] == "rf_classifier"
    assert result["state_code"] == "normal"
    assert result["reason"].startswith("low_confidence")


def test_distracted_requires_higher_threshold(tmp_path):
    model_path, features_path = _write_fake_model(
        tmp_path,
        classes=["normal", "focused", "distracted", "tired"],
        probabilities=[0.20, 0.05, 0.68, 0.07],
    )
    classifier = UserStateClassifier(model_path=model_path, features_path=features_path)

    result = classifier.predict({"feature_a": 1.0})

    assert result["state_code"] == "normal"
    assert "distracted_below_threshold" in result["reason"]


def test_accepts_high_confidence_focused(tmp_path):
    model_path, features_path = _write_fake_model(
        tmp_path,
        classes=["normal", "focused", "distracted", "tired"],
        probabilities=[0.10, 0.76, 0.08, 0.06],
    )
    classifier = UserStateClassifier(model_path=model_path, features_path=features_path)

    result = classifier.predict({"feature_a": 1.0})

    assert result["state_code"] == "focused"
    assert result["confidence"] == 0.76


def _write_fake_model(tmp_path, classes, probabilities):
    model_path = tmp_path / "model.pkl"
    features_path = tmp_path / "features.json"
    with model_path.open("wb") as f:
        pickle.dump(FakeProbabilityModel(classes, probabilities), f)
    with features_path.open("w", encoding="utf-8") as f:
        json.dump(["feature_a"], f)
    return model_path, features_path
