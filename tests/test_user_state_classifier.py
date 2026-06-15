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

    result = classifier.predict(
        {
            "looking_side_ratio": 0.8,
            "eye_closed_ratio": 0.0,
            "face_missing_ratio": 0.0,
            "brightness_mean": 120.0,
        }
    )

    assert result["source"] == "rule_fallback"
    assert result["state_code"] == "distracted"
    assert result["confidence"] >= 0.70


def test_low_confidence_model_returns_normal(tmp_path, monkeypatch):
    monkeypatch.setenv("DESKTOP_PET_STATE_MIN_CONF", "0.50")
    model_path, features_path = _write_fake_model(
        tmp_path,
        classes=["normal", "focused", "distracted", "tired"],
        probabilities=[0.40, 0.10, 0.30, 0.20],
    )
    classifier = UserStateClassifier(model_path=model_path, features_path=features_path)

    result = classifier.predict({"feature_a": 1.0})

    assert result["source"] == "rf_classifier"
    assert result["state_code"] == "normal"
    assert result["reason"].startswith("top_conf_below")
    assert result["debug_info"]["raw_probs"]["normal"] == 0.40
    assert result["debug_info"]["raw_top_label"] == "normal"


def test_distracted_requires_configured_threshold(tmp_path, monkeypatch):
    monkeypatch.setenv("DESKTOP_PET_DISTRACTED_CONF", "0.70")
    model_path, features_path = _write_fake_model(
        tmp_path,
        classes=["normal", "focused", "distracted", "tired"],
        probabilities=[0.20, 0.05, 0.68, 0.07],
    )
    classifier = UserStateClassifier(model_path=model_path, features_path=features_path)

    result = classifier.predict({"feature_a": 1.0})

    assert result["state_code"] == "normal"
    assert "distracted_below_0.70" in result["reason"]


def test_accepts_high_confidence_focused(tmp_path):
    model_path, features_path = _write_fake_model(
        tmp_path,
        classes=["normal", "focused", "distracted", "tired"],
        probabilities=[0.10, 0.76, 0.08, 0.06],
    )
    classifier = UserStateClassifier(model_path=model_path, features_path=features_path)

    result = classifier.predict({"feature_a": 1.0, "face_missing_ratio": 0.0, "brightness_mean": 120.0})

    assert result["state_code"] == "focused"
    assert result["confidence"] == 0.76


def test_focused_uses_relaxed_threshold_at_026(tmp_path):
    model_path, features_path = _write_fake_model(
        tmp_path,
        classes=["normal", "focused", "distracted", "tired"],
        probabilities=[0.25, 0.26, 0.24, 0.25],
    )
    classifier = UserStateClassifier(model_path=model_path, features_path=features_path)

    result = classifier.predict(
        {
            "feature_a": 1.0,
            "eye_closed_ratio": 0.0,
            "face_missing_ratio": 0.0,
            "brightness_mean": 120.0,
        }
    )

    assert result["state_code"] == "focused"
    assert result["reason"] == "focused_prob_above_0.26"


def test_focused_prob_overrides_normal_raw_top(tmp_path):
    model_path, features_path = _write_fake_model(
        tmp_path,
        classes=["normal", "focused", "distracted", "tired"],
        probabilities=[0.44, 0.35, 0.01, 0.20],
    )
    classifier = UserStateClassifier(model_path=model_path, features_path=features_path)

    result = classifier.predict(
        {
            "feature_a": 1.0,
            "eye_closed_ratio": 0.0,
            "face_missing_ratio": 0.0,
            "brightness_mean": 120.0,
        }
    )

    assert result["debug_info"]["raw_top_label"] == "normal"
    assert result["state_code"] == "focused"
    assert result["confidence"] == 0.35
    assert result["reason"] == "focused_prob_above_0.26"


def test_focused_prob_at_026_overrides_normal_raw_top(tmp_path):
    model_path, features_path = _write_fake_model(
        tmp_path,
        classes=["normal", "focused", "distracted", "tired"],
        probabilities=[0.50, 0.26, 0.12, 0.12],
    )
    classifier = UserStateClassifier(model_path=model_path, features_path=features_path)

    result = classifier.predict(
        {
            "feature_a": 1.0,
            "eye_closed_ratio": 0.0,
            "face_missing_ratio": 0.0,
            "brightness_mean": 120.0,
        }
    )

    assert result["debug_info"]["raw_top_label"] == "normal"
    assert result["state_code"] == "focused"
    assert result["confidence"] == 0.26


def test_focused_below_relaxed_threshold_returns_normal(tmp_path):
    model_path, features_path = _write_fake_model(
        tmp_path,
        classes=["normal", "focused", "distracted", "tired"],
        probabilities=[0.50, 0.25, 0.13, 0.12],
    )
    classifier = UserStateClassifier(model_path=model_path, features_path=features_path)

    result = classifier.predict(
        {
            "feature_a": 1.0,
            "eye_closed_ratio": 0.0,
            "face_missing_ratio": 0.0,
            "brightness_mean": 120.0,
        }
    )

    assert result["state_code"] == "normal"
    assert result["debug_info"]["raw_probs"]["focused"] == 0.25


def test_relaxed_focused_does_not_override_tired(tmp_path):
    model_path, features_path = _write_fake_model(
        tmp_path,
        classes=["normal", "focused", "distracted", "tired"],
        probabilities=[0.44, 0.35, 0.01, 0.20],
    )
    classifier = UserStateClassifier(model_path=model_path, features_path=features_path)

    result = classifier.predict(
        {
            "feature_a": 1.0,
            "eye_closed_ratio": 0.5,
            "face_missing_ratio": 0.0,
            "brightness_mean": 120.0,
        }
    )

    assert result["state_code"] == "tired"


def test_relaxed_focused_blocked_by_high_face_missing(tmp_path):
    model_path, features_path = _write_fake_model(
        tmp_path,
        classes=["normal", "focused", "distracted", "tired"],
        probabilities=[0.44, 0.35, 0.01, 0.20],
    )
    classifier = UserStateClassifier(model_path=model_path, features_path=features_path)

    result = classifier.predict(
        {
            "feature_a": 1.0,
            "eye_closed_ratio": 0.0,
            "face_missing_ratio": 0.8,
            "face_missing": 0.0,
            "brightness_mean": 120.0,
        }
    )

    assert result["state_code"] == "normal"
    assert result["state_code"] != "focused"


def test_mid_face_missing_with_current_face_does_not_block_high_focused(tmp_path):
    model_path, features_path = _write_fake_model(
        tmp_path,
        classes=["normal", "focused", "distracted", "tired"],
        probabilities=[0.10, 0.76, 0.08, 0.06],
    )
    classifier = UserStateClassifier(model_path=model_path, features_path=features_path)

    result = classifier.predict(
        {
            "feature_a": 1.0,
            "face_missing_ratio": 0.5,
            "face_missing": 0.0,
            "brightness_mean": 120.0,
        }
    )

    assert result["state_code"] == "focused"
    assert not result["reason"].startswith("rule_block:face_missing")


def test_high_face_missing_blocks_high_focused_model(tmp_path):
    model_path, features_path = _write_fake_model(
        tmp_path,
        classes=["normal", "focused", "distracted", "tired"],
        probabilities=[0.10, 0.76, 0.08, 0.06],
    )
    classifier = UserStateClassifier(model_path=model_path, features_path=features_path)

    result = classifier.predict(
        {
            "feature_a": 1.0,
            "face_missing_ratio": 0.8,
            "face_missing": 0.0,
            "brightness_mean": 120.0,
        }
    )

    assert result["state_code"] == "normal"
    assert result["reason"] == "rule_block:face_missing"


def test_mid_face_missing_with_current_face_missing_blocks_focused(tmp_path):
    model_path, features_path = _write_fake_model(
        tmp_path,
        classes=["normal", "focused", "distracted", "tired"],
        probabilities=[0.10, 0.76, 0.08, 0.06],
    )
    classifier = UserStateClassifier(model_path=model_path, features_path=features_path)

    result = classifier.predict(
        {
            "feature_a": 1.0,
            "face_missing_ratio": 0.5,
            "face_missing": 1.0,
            "brightness_mean": 120.0,
        }
    )

    assert result["state_code"] == "normal"
    assert result["reason"] == "rule_block:face_missing"


def test_stable_looking_down_does_not_trigger_distracted(tmp_path):
    classifier = UserStateClassifier(
        model_path=tmp_path / "missing.pkl",
        features_path=tmp_path / "missing.json",
    )

    result = classifier.predict(
        {
            "looking_down_ratio": 0.9,
            "looking_side_ratio": 0.0,
            "head_yaw_range": 8.0,
            "eye_closed_ratio": 0.0,
            "face_missing_ratio": 0.0,
            "brightness_mean": 120.0,
            "motion_stability": 0.9,
        }
    )

    assert result["state_code"] in {"focused", "normal"}
    assert result["state_code"] != "distracted"


def test_looking_side_rule_outputs_distracted_candidate(tmp_path):
    classifier = UserStateClassifier(
        model_path=tmp_path / "missing.pkl",
        features_path=tmp_path / "missing.json",
    )

    result = classifier.predict(
        {
            "looking_side_ratio": 0.6,
            "eye_closed_ratio": 0.0,
            "face_missing_ratio": 0.0,
            "brightness_mean": 120.0,
        }
    )

    assert result["state_code"] == "distracted"
    assert "looking_side_or_yaw_range" in result["reason"]


def test_head_yaw_range_rule_outputs_distracted_candidate(tmp_path):
    classifier = UserStateClassifier(
        model_path=tmp_path / "missing.pkl",
        features_path=tmp_path / "missing.json",
    )

    result = classifier.predict(
        {
            "head_yaw_range": 35.0,
            "eye_closed_ratio": 0.0,
            "face_missing_ratio": 0.0,
            "brightness_mean": 120.0,
        }
    )

    assert result["state_code"] == "distracted"
    assert "looking_side_or_yaw_range" in result["reason"]


def test_eye_closed_has_priority_over_distracted_rules(tmp_path):
    classifier = UserStateClassifier(
        model_path=tmp_path / "missing.pkl",
        features_path=tmp_path / "missing.json",
    )

    result = classifier.predict(
        {
            "eye_closed_ratio": 0.5,
            "looking_side_ratio": 0.9,
            "face_missing_ratio": 0.0,
            "brightness_mean": 120.0,
        }
    )

    assert result["state_code"] == "tired"


def test_phone_detected_rule_outputs_distracted_candidate(tmp_path):
    classifier = UserStateClassifier(
        model_path=tmp_path / "missing.pkl",
        features_path=tmp_path / "missing.json",
    )

    result = classifier.predict(
        {
            "phone_detected_ratio": 0.7,
            "eye_closed_ratio": 0.0,
            "face_missing_ratio": 0.0,
            "brightness_mean": 120.0,
        }
    )

    assert result["state_code"] == "distracted"
    assert "phone_detected" in result["reason"]


def test_default_phone_ratio_does_not_trigger_distracted(tmp_path):
    classifier = UserStateClassifier(
        model_path=tmp_path / "missing.pkl",
        features_path=tmp_path / "missing.json",
    )

    result = classifier.predict(
        {
            "eye_closed_ratio": 0.0,
            "face_missing_ratio": 0.0,
            "brightness_mean": 120.0,
        }
    )

    assert result["state_code"] == "normal"


def test_high_face_missing_blocks_focused_and_distracted(tmp_path):
    classifier = UserStateClassifier(
        model_path=tmp_path / "missing.pkl",
        features_path=tmp_path / "missing.json",
    )

    result = classifier.predict(
        {
            "looking_side_ratio": 0.9,
            "motion_stability": 0.9,
            "eye_closed_ratio": 0.0,
            "face_missing_ratio": 0.8,
            "brightness_mean": 120.0,
        }
    )

    assert result["state_code"] == "normal"


def _write_fake_model(tmp_path, classes, probabilities):
    model_path = tmp_path / "model.pkl"
    features_path = tmp_path / "features.json"
    with model_path.open("wb") as f:
        pickle.dump(FakeProbabilityModel(classes, probabilities), f)
    with features_path.open("w", encoding="utf-8") as f:
        json.dump(["feature_a"], f)
    return model_path, features_path
