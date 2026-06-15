"""Lightweight RandomForest user-state classifier wrapper.

The classifier only predicts: normal, focused, distracted, tired.
Hard states such as away, return, low_light, study_long, camera_error, unknown
remain owned by the rule layer in UserStateDetector.
"""

from __future__ import annotations

import json
import math
import os
import pickle
import time
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
        self.min_conf = self._env_float("DESKTOP_PET_STATE_MIN_CONF", 0.50)
        self.distracted_conf = self._env_float("DESKTOP_PET_DISTRACTED_CONF", 0.60)
        self.focused_conf = self._env_float("DESKTOP_PET_FOCUSED_CONF", 0.26)
        self.tired_conf = self._env_float("DESKTOP_PET_TIRED_CONF", 0.50)
        self.debug_enabled = os.getenv("DESKTOP_PET_STATE_DEBUG", "false").strip().lower() in {
            "1", "true", "yes", "y", "on"
        }
        self._last_debug_log_at = 0.0
        self._last_feature_debug_log_at = 0.0
        self._last_face_missing_debug_log_at = 0.0
        self._last_rule_debug_log_at = 0.0
        self._last_rule_debug_message = ""
        self._load()

    @property
    def available(self) -> bool:
        return self.model is not None and bool(self.feature_names)

    def predict(self, features: dict[str, Any] | None) -> dict[str, Any]:
        """Return a stable classification dict without raising to callers."""
        features = features or {}
        if not self.available:
            result = self._rule_fallback(features, self.load_error or "model_unavailable")
            self._feature_debug(features)
            self._debug_log(result.get("debug_info", {}))
            return result

        try:
            feature_stats = self._feature_stats(features)
            if feature_stats["missing_features"] and len(feature_stats["missing_features"]) == len(self.feature_names):
                result = self._rule_fallback(features, "feature_mismatch_all")
                self._feature_debug(features)
                self._debug_log(result.get("debug_info", {}))
                return result

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
            raw_probs = {label: round(float(scored.get(label, 0.0) or 0.0), 4) for label in sorted(MODEL_STATE_CODES)}
            result = self._threshold_result(state_code, confidence, "rf_classifier", raw_probs, feature_stats)
            result = self._apply_semantic_rules(result, features)
            self._feature_debug(features)
            self._debug_log(result.get("debug_info", {}))
            return result
        except Exception as exc:
            result = self._rule_fallback(features, f"predict_failed:{exc}")
            self._feature_debug(features)
            self._debug_log(result.get("debug_info", {}))
            return result

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

    def _threshold_result(
        self,
        state_code: str,
        confidence: float,
        source: str,
        raw_probs: dict[str, float] | None = None,
        feature_stats: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        confidence = max(0.0, min(1.0, float(confidence)))
        original = state_code if state_code in MODEL_STATE_CODES else "normal"
        accepted = original
        reason = f"{source}:{original}:{confidence:.2f}"
        threshold_reason = "accepted"

        if original == "focused":
            if confidence >= self.focused_conf:
                accepted = "focused"
                threshold_reason = f"focused_prob_above_{self.focused_conf:.2f}"
                reason = threshold_reason
            else:
                accepted = "normal"
                threshold_reason = f"focused_below_{self.focused_conf:.2f}"
                reason = f"{threshold_reason}:{confidence:.2f}"
        elif confidence < self.min_conf:
            accepted = "normal"
            threshold_reason = f"top_conf_below_{self.min_conf:.2f}"
            reason = f"{threshold_reason}:{original}:{confidence:.2f}"
        elif original == "distracted" and confidence < self.distracted_conf:
            accepted = "normal"
            threshold_reason = f"distracted_below_{self.distracted_conf:.2f}"
            reason = f"{threshold_reason}:{confidence:.2f}"
        elif original == "tired" and confidence < self.tired_conf:
            accepted = "normal"
            threshold_reason = f"tired_below_{self.tired_conf:.2f}"
            reason = f"{threshold_reason}:{confidence:.2f}"
        final_confidence = confidence if accepted == original else max(0.0, min(confidence, self.min_conf - 0.01))
        debug_info = self._build_debug_info(
            raw_probs=raw_probs or {label: 0.0 for label in sorted(MODEL_STATE_CODES)},
            raw_top_label=original,
            raw_top_confidence=confidence,
            final_state_code=accepted,
            final_confidence=final_confidence,
            threshold_reason=threshold_reason,
            source=source,
            feature_stats=feature_stats or {},
        )

        return {
            "state_code": accepted,
            "confidence": final_confidence,
            "reason": reason,
            "source": source,
            "debug_info": debug_info,
        }

    def _rule_fallback(self, features: dict[str, Any], reason: str) -> dict[str, Any]:
        eye_closed_ratio = self._to_float(features.get("eye_closed_ratio", features.get("eye_closed", 0.0)))
        motion_stability = self._to_float(features.get("motion_stability", 0.0))
        face_missing_ratio = self._to_float(features.get("face_missing_ratio", features.get("face_missing", 1.0)))

        state_code = "normal"
        confidence = 0.55
        if eye_closed_ratio >= 0.50 and face_missing_ratio < 0.5:
            state_code = "tired"
            confidence = 0.70
        elif face_missing_ratio <= 0.15 and motion_stability >= 0.80:
            state_code = "focused"
            confidence = 0.66

        feature_stats = self._feature_stats(features)
        raw_probs = {label: 0.0 for label in sorted(MODEL_STATE_CODES)}
        raw_probs[state_code] = confidence
        result = self._threshold_result(state_code, confidence, "rule_fallback", raw_probs, feature_stats)
        result = self._apply_semantic_rules(result, features)
        result["reason"] = f"rule_fallback:{reason}:{result['reason']}"
        result["debug_info"]["threshold_reason"] = result["reason"]
        return result

    def _apply_semantic_rules(self, result: dict[str, Any], features: dict[str, Any]) -> dict[str, Any]:
        eye_closed_ratio = self._to_float(features.get("eye_closed_ratio", features.get("eye_closed", 0.0)))
        face_missing_ratio = self._to_float(features.get("face_missing_ratio", features.get("face_missing", 1.0)))
        looking_down_ratio = self._to_float(features.get("looking_down_ratio", features.get("looking_down", 0.0)))
        looking_side_ratio = self._to_float(features.get("looking_side_ratio", features.get("looking_side", 0.0)))
        brightness_mean = self._to_float(features.get("brightness_mean", features.get("brightness", 0.0)))
        head_yaw_mean = self._to_float(features.get("head_yaw_mean", features.get("head_yaw", 0.0)))
        head_yaw_range = self._to_float(features.get("head_yaw_range", 0.0))
        face_center_x_std = self._to_float(features.get("face_center_x_std", 0.0))
        phone_detected_ratio = self._phone_detected_ratio(features)
        debug_info = result.get("debug_info", {}) if isinstance(result.get("debug_info"), dict) else {}
        raw_probs = debug_info.get("raw_probs", {}) if isinstance(debug_info.get("raw_probs"), dict) else {}
        focused_prob = self._to_float(raw_probs.get("focused", 0.0))
        current_face_missing = self._to_float(features.get("face_missing", 0.0)) >= 0.5
        block_attention_state = self._should_block_attention_state(
            result=result,
            face_missing_ratio=face_missing_ratio,
            current_face_missing=current_face_missing,
        )
        self._face_missing_debug(face_missing_ratio, current_face_missing, block_attention_state)

        if block_attention_state:
            return self._with_final_state(
                result,
                state_code="normal",
                confidence=0.55,
                reason="rule_block:face_missing",
                threshold_reason="rule_block:face_missing",
            )

        if eye_closed_ratio >= 0.50 and face_missing_ratio < 0.50:
            return self._with_final_state(
                result,
                state_code="tired",
                confidence=max(float(result.get("confidence", 0.0) or 0.0), 0.70),
                reason="rule_override:tired:eye_closed",
                threshold_reason="rule_override=tired reason=eye_closed",
            )

        if result.get("state_code") == "focused" and eye_closed_ratio >= 0.35:
            return self._with_final_state(
                result,
                state_code="normal",
                confidence=min(float(result.get("confidence", 0.0) or 0.0), 0.49),
                reason="rule_block:focused_eye_closed",
                threshold_reason="rule_block=focused reason=eye_closed",
            )

        stable_looking_down = (
            looking_down_ratio >= 0.50
            and looking_side_ratio < 0.30
            and head_yaw_range < 25.0
            and eye_closed_ratio < 0.25
            and face_missing_ratio < 0.50
        )
        if stable_looking_down and result.get("state_code") == "distracted":
            self._rule_debug("block_distracted reason=stable_looking_down_treated_as_focused")
            return self._with_final_state(
                result,
                state_code="focused",
                confidence=0.66,
                reason="rule_block:stable_looking_down_treated_as_focused",
                threshold_reason="block_distracted reason=stable_looking_down_treated_as_focused",
            )

        if phone_detected_ratio >= 0.50 and eye_closed_ratio < 0.35 and face_missing_ratio < 0.50:
            self._rule_debug("rule_override=distracted reason=phone_detected")
            return self._with_final_state(
                result,
                state_code="distracted",
                confidence=max(float(result.get("confidence", 0.0) or 0.0), 0.72),
                reason="rule_override:distracted_candidate:phone_detected",
                threshold_reason="rule_override=distracted reason=phone_detected",
            )

        looking_side_or_yaw_range = (
            abs(head_yaw_mean) >= 20.0
            or head_yaw_range >= 30.0
            or looking_side_ratio >= 0.50
            or face_center_x_std >= 0.08
        )
        if (
            result.get("state_code") != "tired"
            and face_missing_ratio < 0.50
            and eye_closed_ratio < 0.25
            and looking_side_or_yaw_range
        ):
            self._rule_debug("rule_override=distracted reason=looking_side_or_yaw_range")
            return self._with_final_state(
                result,
                state_code="distracted",
                confidence=max(float(result.get("confidence", 0.0) or 0.0), 0.72),
                reason="rule_override:distracted_candidate:looking_side_or_yaw_range",
                threshold_reason="rule_override=distracted reason=looking_side_or_yaw_range",
            )

        if focused_prob >= self.focused_conf and eye_closed_ratio < 0.35 and face_missing_ratio < 0.70:
            return self._with_final_state(
                result,
                state_code="focused",
                confidence=focused_prob,
                reason=f"focused_prob_above_{self.focused_conf:.2f}",
                threshold_reason=f"focused_prob_above_{self.focused_conf:.2f}",
            )

        return result

    def _should_block_attention_state(
        self,
        result: dict[str, Any],
        face_missing_ratio: float,
        current_face_missing: bool,
    ) -> bool:
        if result.get("state_code") not in {"focused", "distracted"}:
            return False
        if face_missing_ratio >= 0.70:
            return True
        if 0.40 <= face_missing_ratio < 0.70 and current_face_missing:
            return True
        return False

    def _with_final_state(
        self,
        result: dict[str, Any],
        state_code: str,
        confidence: float,
        reason: str,
        threshold_reason: str,
    ) -> dict[str, Any]:
        confidence = max(0.0, min(1.0, float(confidence)))
        result["state_code"] = state_code
        result["confidence"] = confidence
        result["reason"] = reason
        debug_info = result.setdefault("debug_info", {})
        debug_info["final_state_code"] = state_code
        debug_info["final_confidence"] = confidence
        debug_info["threshold_reason"] = threshold_reason
        return result

    def _feature_stats(self, features: dict[str, Any]) -> dict[str, Any]:
        missing_features: list[str] = []
        nan_feature_count = 0
        zero_feature_count = 0
        for name in self.feature_names:
            if name not in features:
                missing_features.append(name)
                zero_feature_count += 1
                continue
            value = features.get(name)
            try:
                numeric = float(value)
                if not math.isfinite(numeric):
                    nan_feature_count += 1
                elif abs(numeric) <= 1e-12:
                    zero_feature_count += 1
            except Exception:
                nan_feature_count += 1
        return {
            "missing_features": missing_features,
            "nan_feature_count": nan_feature_count,
            "zero_feature_count": zero_feature_count,
        }

    @staticmethod
    def _build_debug_info(
        raw_probs: dict[str, float],
        raw_top_label: str,
        raw_top_confidence: float,
        final_state_code: str,
        final_confidence: float,
        threshold_reason: str,
        source: str,
        feature_stats: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "raw_probs": {str(k): float(v) for k, v in raw_probs.items()},
            "raw_top_label": raw_top_label,
            "raw_top_confidence": float(raw_top_confidence),
            "final_state_code": final_state_code,
            "final_confidence": float(final_confidence),
            "threshold_reason": threshold_reason,
            "source": source,
            "missing_features": list(feature_stats.get("missing_features", []) or []),
            "nan_feature_count": int(feature_stats.get("nan_feature_count", 0) or 0),
            "zero_feature_count": int(feature_stats.get("zero_feature_count", 0) or 0),
        }

    def _debug_log(self, debug_info: dict[str, Any]) -> None:
        if not self.debug_enabled:
            return
        now = time.monotonic()
        if now - self._last_debug_log_at < 1.0:
            return
        self._last_debug_log_at = now
        probs = debug_info.get("raw_probs", {})
        prob_text = ", ".join(f"{k}:{float(v):.2f}" for k, v in sorted(probs.items()))
        raw_label = debug_info.get("raw_top_label", "unknown")
        raw_conf = float(debug_info.get("raw_top_confidence", 0.0) or 0.0)
        final_state = debug_info.get("final_state_code", "unknown")
        reason = debug_info.get("threshold_reason", "")
        print(
            "[UserStateClassifierDebug] "
            f"probs={{{prob_text}}}, raw={raw_label}({raw_conf:.2f}), "
            f"final={final_state}, reason={reason}"
        )
        missing = debug_info.get("missing_features", []) or []
        if missing or debug_info.get("nan_feature_count") or debug_info.get("zero_feature_count"):
            preview = missing[:8]
            suffix = "..." if len(missing) > 8 else ""
            print(
                "[UserStateClassifierDebug] "
                f"missing_features={preview}{suffix}, "
                f"nan_count={debug_info.get('nan_feature_count', 0)}, "
                f"zero_count={debug_info.get('zero_feature_count', 0)}"
            )

    def _rule_debug(self, message: str) -> None:
        if not self.debug_enabled:
            return
        now = time.monotonic()
        if message == self._last_rule_debug_message and now - self._last_rule_debug_log_at < 1.0:
            return
        self._last_rule_debug_message = message
        self._last_rule_debug_log_at = now
        print(f"[UserStateClassifierDebug] {message}")

    def _face_missing_debug(
        self,
        face_missing_ratio: float,
        current_face_missing: bool,
        block_attention_state: bool,
    ) -> None:
        if not self.debug_enabled:
            return
        now = time.monotonic()
        if now - self._last_face_missing_debug_log_at < 1.0:
            return
        self._last_face_missing_debug_log_at = now
        print(
            "[UserStateClassifierDebug] "
            f"face_missing_ratio={face_missing_ratio:.3f}, "
            f"current_face_missing={current_face_missing}, "
            f"block_focused={block_attention_state}"
        )

    def _feature_debug(self, features: dict[str, Any]) -> None:
        if not self.debug_enabled:
            return
        now = time.monotonic()
        if now - self._last_feature_debug_log_at < 1.0:
            return
        self._last_feature_debug_log_at = now
        phone_detector = "provided" if "phone_detected_ratio" in features or "phone_detected" in features else "disabled"
        phone_ratio = self._phone_detected_ratio(features)
        print(
            "[UserStateFeatureDebug] "
            f"yaw_mean={self._to_float(features.get('head_yaw_mean', features.get('head_yaw', 0.0))):.3f}, "
            f"yaw_range={self._to_float(features.get('head_yaw_range', 0.0)):.3f}, "
            f"side_ratio={self._to_float(features.get('looking_side_ratio', features.get('looking_side', 0.0))):.3f}, "
            f"down_ratio={self._to_float(features.get('looking_down_ratio', features.get('looking_down', 0.0))):.3f}, "
            f"face_center_x_std={self._to_float(features.get('face_center_x_std', 0.0)):.3f}, "
            f"face_missing={self._to_float(features.get('face_missing_ratio', features.get('face_missing', 1.0))):.3f}, "
            f"eye_closed={self._to_float(features.get('eye_closed_ratio', features.get('eye_closed', 0.0))):.3f}, "
            f"phone_detector={phone_detector}, phone_ratio={phone_ratio:.3f}, "
            f"brightness={self._to_float(features.get('brightness_mean', features.get('brightness', 0.0))):.3f}"
        )

    @staticmethod
    def _env_float(name: str, default: float) -> float:
        try:
            return float(os.getenv(name, str(default)) or default)
        except Exception:
            return float(default)

    @staticmethod
    def _to_float(value: Any) -> float:
        try:
            result = float(value)
            return result if math.isfinite(result) else 0.0
        except Exception:
            return 0.0

    @classmethod
    def _phone_detected_ratio(cls, features: dict[str, Any]) -> float:
        ratio = cls._to_float(features.get("phone_detected_ratio", 0.0))
        detected = features.get("phone_detected", False)
        if isinstance(detected, str):
            detected_value = detected.strip().lower() in {"1", "true", "yes", "y", "on"}
        else:
            detected_value = bool(detected)
        if detected_value:
            ratio = max(ratio, 1.0)
        return max(0.0, min(1.0, ratio))


__all__ = ["UserStateClassifier", "MODEL_PATH", "FEATURES_PATH", "MODEL_STATE_CODES"]
