"""Feature extraction for offline user-state dataset collection.

This module does not classify user state and does not store face images. It only
converts a camera frame plus optional MediaPipe FaceLandmarker output into
numeric per-frame features and rolling-window statistics.
"""

from __future__ import annotations

import math
import time
from collections import deque
from statistics import mean, pstdev
from typing import Any, Deque, Iterable

try:
    import numpy as np
except Exception:  # pragma: no cover - tests run with numpy installed
    np = None  # type: ignore


FRAME_FEATURE_FIELDS = [
    "head_yaw",
    "head_pitch",
    "head_roll",
    "eye_aspect_ratio",
    "eye_closed",
    "mouth_open",
    "smile",
    "brow_raise",
    "face_confidence",
    "brightness",
    "face_bbox_area",
    "face_center_x",
    "face_center_y",
    "face_missing",
    "looking_down",
    "looking_side",
    "low_light",
    "timestamp",
]

WINDOW_FEATURE_FIELDS = [
    "head_yaw_mean",
    "head_yaw_std",
    "head_pitch_mean",
    "head_pitch_std",
    "eye_closed_ratio",
    "face_missing_ratio",
    "looking_down_ratio",
    "looking_side_ratio",
    "brightness_mean",
    "face_bbox_area_mean",
    "face_center_x_mean",
    "face_center_y_mean",
    "motion_stability",
    "recent_duration",
]

USER_STATE_FEATURE_FIELDS = FRAME_FEATURE_FIELDS + WINDOW_FEATURE_FIELDS


class UserStateFeatureExtractor:
    """Extract numeric user-state features and rolling 3-second statistics."""

    def __init__(self, window_seconds: float = 3.0) -> None:
        self.window_seconds = max(0.5, float(window_seconds))
        self._frames: Deque[dict[str, float]] = deque()

    def update(
        self,
        frame: Any = None,
        face_landmarker_result: Any = None,
        timestamp: float | None = None,
    ) -> dict[str, float]:
        """Extract one frame and return combined frame + window features."""
        frame_features = self.extract_frame_features(frame, face_landmarker_result, timestamp)
        self._frames.append(frame_features)
        self._prune(frame_features["timestamp"])
        output = dict(frame_features)
        output.update(self.get_window_features())
        return self._ordered_features(output)

    def extract_frame_features(
        self,
        frame: Any = None,
        face_landmarker_result: Any = None,
        timestamp: float | None = None,
    ) -> dict[str, float]:
        """Return per-frame numeric features. Missing face data stays stable."""
        ts = time.time() if timestamp is None else float(timestamp)
        brightness = self._brightness(frame)
        landmarks = self._first_face_landmarks(face_landmarker_result)
        blendshapes = self._blendshape_scores(face_landmarker_result)

        values = self._default_frame_features(ts, brightness)
        if not landmarks:
            return values

        bbox = self._landmark_bbox(landmarks)
        center_x = (bbox[0] + bbox[2]) / 2.0
        center_y = (bbox[1] + bbox[3]) / 2.0
        area = max(0.0, bbox[2] - bbox[0]) * max(0.0, bbox[3] - bbox[1])
        pitch, yaw, roll = self._head_pose(face_landmarker_result, landmarks)
        ear = self._eye_aspect_ratio(landmarks)
        mouth_open = self._mouth_open(landmarks, bbox, blendshapes)
        smile = self._smile(landmarks, bbox, blendshapes)
        brow_raise = self._brow_raise(landmarks, bbox, blendshapes)

        values.update(
            {
                "head_yaw": yaw,
                "head_pitch": pitch,
                "head_roll": roll,
                "eye_aspect_ratio": ear,
                "eye_closed": 1.0 if ear < 0.18 else 0.0,
                "mouth_open": mouth_open,
                "smile": smile,
                "brow_raise": brow_raise,
                "face_confidence": 1.0,
                "face_bbox_area": area,
                "face_center_x": center_x,
                "face_center_y": center_y,
                "face_missing": 0.0,
                "looking_down": 1.0 if pitch > 12.0 or center_y > 0.62 else 0.0,
                "looking_side": 1.0 if abs(yaw) > 18.0 or center_x < 0.35 or center_x > 0.65 else 0.0,
                "low_light": 1.0 if brightness < 55.0 else 0.0,
            }
        )
        return self._ordered_frame_features(values)

    def get_window_features(self) -> dict[str, float]:
        """Return rolling-window aggregate features as a stable dict."""
        if not self._frames:
            return {field: 0.0 for field in WINDOW_FEATURE_FIELDS}

        frames = list(self._frames)
        first_ts = frames[0]["timestamp"]
        last_ts = frames[-1]["timestamp"]
        center_x = [item["face_center_x"] for item in frames if item["face_missing"] < 0.5]
        center_y = [item["face_center_y"] for item in frames if item["face_missing"] < 0.5]
        motion_values = self._motion_deltas(center_x, center_y)
        motion_stability = 1.0 / (1.0 + self._mean(motion_values) * 20.0)

        values = {
            "head_yaw_mean": self._mean(item["head_yaw"] for item in frames),
            "head_yaw_std": self._std(item["head_yaw"] for item in frames),
            "head_pitch_mean": self._mean(item["head_pitch"] for item in frames),
            "head_pitch_std": self._std(item["head_pitch"] for item in frames),
            "eye_closed_ratio": self._mean(item["eye_closed"] for item in frames),
            "face_missing_ratio": self._mean(item["face_missing"] for item in frames),
            "looking_down_ratio": self._mean(item["looking_down"] for item in frames),
            "looking_side_ratio": self._mean(item["looking_side"] for item in frames),
            "brightness_mean": self._mean(item["brightness"] for item in frames),
            "face_bbox_area_mean": self._mean(item["face_bbox_area"] for item in frames),
            "face_center_x_mean": self._mean(center_x),
            "face_center_y_mean": self._mean(center_y),
            "motion_stability": motion_stability,
            "recent_duration": max(0.0, last_ts - first_ts),
        }
        return {field: float(values.get(field, 0.0)) for field in WINDOW_FEATURE_FIELDS}

    def reset(self) -> None:
        self._frames.clear()

    def _prune(self, now: float) -> None:
        cutoff = float(now) - self.window_seconds
        while self._frames and self._frames[0]["timestamp"] < cutoff:
            self._frames.popleft()

    @staticmethod
    def _default_frame_features(timestamp: float, brightness: float) -> dict[str, float]:
        return {
            "head_yaw": 0.0,
            "head_pitch": 0.0,
            "head_roll": 0.0,
            "eye_aspect_ratio": 0.0,
            "eye_closed": 0.0,
            "mouth_open": 0.0,
            "smile": 0.0,
            "brow_raise": 0.0,
            "face_confidence": 0.0,
            "brightness": float(brightness),
            "face_bbox_area": 0.0,
            "face_center_x": 0.0,
            "face_center_y": 0.0,
            "face_missing": 1.0,
            "looking_down": 0.0,
            "looking_side": 0.0,
            "low_light": 1.0 if brightness < 55.0 else 0.0,
            "timestamp": float(timestamp),
        }

    @staticmethod
    def _ordered_frame_features(values: dict[str, float]) -> dict[str, float]:
        return {field: float(values.get(field, 0.0)) for field in FRAME_FEATURE_FIELDS}

    @staticmethod
    def _ordered_features(values: dict[str, float]) -> dict[str, float]:
        return {field: float(values.get(field, 0.0)) for field in USER_STATE_FEATURE_FIELDS}

    @staticmethod
    def _brightness(frame: Any) -> float:
        if frame is None or np is None:
            return 0.0
        try:
            arr = np.asarray(frame)
            if arr.size == 0:
                return 0.0
            if arr.ndim == 3:
                return float(arr[:, :, :3].mean())
            return float(arr.mean())
        except Exception:
            return 0.0

    @staticmethod
    def _first_face_landmarks(result: Any) -> list[Any]:
        if result is None:
            return []
        if isinstance(result, (list, tuple)):
            return list(result)
        landmarks = getattr(result, "face_landmarks", None) or []
        if not landmarks:
            return []
        try:
            return list(landmarks[0])
        except Exception:
            return []

    @staticmethod
    def _blendshape_scores(result: Any) -> dict[str, float]:
        scores: dict[str, float] = {}
        if result is None:
            return scores
        groups = getattr(result, "face_blendshapes", None) or []
        if not groups:
            return scores
        try:
            categories = groups[0]
            if hasattr(categories, "categories"):
                categories = categories.categories
            for item in categories:
                name = getattr(item, "category_name", None) or getattr(item, "display_name", None)
                if not name:
                    continue
                scores[str(name)] = float(getattr(item, "score", 0.0) or 0.0)
        except Exception:
            return {}
        return scores

    @staticmethod
    def _landmark_bbox(landmarks: list[Any]) -> tuple[float, float, float, float]:
        xs = [UserStateFeatureExtractor._coord(lm, "x") for lm in landmarks]
        ys = [UserStateFeatureExtractor._coord(lm, "y") for lm in landmarks]
        if not xs or not ys:
            return 0.0, 0.0, 0.0, 0.0
        return max(0.0, min(xs)), max(0.0, min(ys)), min(1.0, max(xs)), min(1.0, max(ys))

    @staticmethod
    def _head_pose(result: Any, landmarks: list[Any]) -> tuple[float, float, float]:
        matrixes = getattr(result, "facial_transformation_matrixes", None) if result is not None else None
        if matrixes and np is not None:
            try:
                mat = np.asarray(matrixes[0], dtype=float).reshape(4, 4)
                rot = mat[:3, :3]
                sy = math.sqrt(rot[0, 0] * rot[0, 0] + rot[1, 0] * rot[1, 0])
                singular = sy < 1e-6
                if not singular:
                    pitch = math.degrees(math.atan2(rot[2, 1], rot[2, 2]))
                    yaw = math.degrees(math.atan2(-rot[2, 0], sy))
                    roll = math.degrees(math.atan2(rot[1, 0], rot[0, 0]))
                else:
                    pitch = math.degrees(math.atan2(-rot[1, 2], rot[1, 1]))
                    yaw = math.degrees(math.atan2(-rot[2, 0], sy))
                    roll = 0.0
                return pitch, yaw, roll
            except Exception:
                pass

        try:
            nose = landmarks[1]
            left = landmarks[234] if len(landmarks) > 234 else landmarks[0]
            right = landmarks[454] if len(landmarks) > 454 else landmarks[-1]
            chin = landmarks[152] if len(landmarks) > 152 else landmarks[-1]
            eye_mid_y = (
                UserStateFeatureExtractor._coord(landmarks[33], "y")
                + UserStateFeatureExtractor._coord(landmarks[263], "y")
            ) / 2.0 if len(landmarks) > 263 else UserStateFeatureExtractor._coord(nose, "y")
            yaw = (
                UserStateFeatureExtractor._coord(nose, "x")
                - (UserStateFeatureExtractor._coord(left, "x") + UserStateFeatureExtractor._coord(right, "x")) / 2.0
            ) * 120.0
            pitch = (UserStateFeatureExtractor._coord(chin, "y") - eye_mid_y - 0.25) * 90.0
            roll = (
                UserStateFeatureExtractor._coord(landmarks[263], "y")
                - UserStateFeatureExtractor._coord(landmarks[33], "y")
            ) * 120.0 if len(landmarks) > 263 else 0.0
            return pitch, yaw, roll
        except Exception:
            return 0.0, 0.0, 0.0

    @staticmethod
    def _eye_aspect_ratio(landmarks: list[Any]) -> float:
        try:
            left = UserStateFeatureExtractor._eye_ratio(landmarks, [33, 160, 158, 133, 153, 144])
            right = UserStateFeatureExtractor._eye_ratio(landmarks, [362, 385, 387, 263, 373, 380])
            return (left + right) / 2.0
        except Exception:
            return 0.0

    @staticmethod
    def _eye_ratio(landmarks: list[Any], idx: list[int]) -> float:
        pts = [(UserStateFeatureExtractor._coord(landmarks[i], "x"), UserStateFeatureExtractor._coord(landmarks[i], "y")) for i in idx]
        p1, p2, p3, p4, p5, p6 = pts
        vertical1 = math.dist(p2, p6)
        vertical2 = math.dist(p3, p5)
        horizontal = math.dist(p1, p4)
        if horizontal <= 1e-6:
            return 0.0
        return (vertical1 + vertical2) / (2.0 * horizontal)

    @staticmethod
    def _mouth_open(landmarks: list[Any], bbox: tuple[float, float, float, float], scores: dict[str, float]) -> float:
        if "jawOpen" in scores:
            return UserStateFeatureExtractor._clamp01(scores["jawOpen"])
        try:
            height = max(1e-6, bbox[3] - bbox[1])
            return UserStateFeatureExtractor._clamp01(
                abs(UserStateFeatureExtractor._coord(landmarks[14], "y") - UserStateFeatureExtractor._coord(landmarks[13], "y"))
                / height
                * 5.0
            )
        except Exception:
            return 0.0

    @staticmethod
    def _smile(landmarks: list[Any], bbox: tuple[float, float, float, float], scores: dict[str, float]) -> float:
        if "mouthSmileLeft" in scores or "mouthSmileRight" in scores:
            return UserStateFeatureExtractor._clamp01((scores.get("mouthSmileLeft", 0.0) + scores.get("mouthSmileRight", 0.0)) / 2.0)
        try:
            width = max(1e-6, bbox[2] - bbox[0])
            return UserStateFeatureExtractor._clamp01(
                math.dist(
                    (UserStateFeatureExtractor._coord(landmarks[61], "x"), UserStateFeatureExtractor._coord(landmarks[61], "y")),
                    (UserStateFeatureExtractor._coord(landmarks[291], "x"), UserStateFeatureExtractor._coord(landmarks[291], "y")),
                )
                / width
                - 0.35
            )
        except Exception:
            return 0.0

    @staticmethod
    def _brow_raise(landmarks: list[Any], bbox: tuple[float, float, float, float], scores: dict[str, float]) -> float:
        if "browOuterUpLeft" in scores or "browOuterUpRight" in scores:
            return UserStateFeatureExtractor._clamp01((scores.get("browOuterUpLeft", 0.0) + scores.get("browOuterUpRight", 0.0)) / 2.0)
        try:
            height = max(1e-6, bbox[3] - bbox[1])
            brow_y = (UserStateFeatureExtractor._coord(landmarks[105], "y") + UserStateFeatureExtractor._coord(landmarks[334], "y")) / 2.0
            eye_y = (UserStateFeatureExtractor._coord(landmarks[159], "y") + UserStateFeatureExtractor._coord(landmarks[386], "y")) / 2.0
            return UserStateFeatureExtractor._clamp01((eye_y - brow_y) / height * 3.0)
        except Exception:
            return 0.0

    @staticmethod
    def _motion_deltas(xs: list[float], ys: list[float]) -> list[float]:
        if len(xs) < 2 or len(xs) != len(ys):
            return []
        return [math.dist((xs[i - 1], ys[i - 1]), (xs[i], ys[i])) for i in range(1, len(xs))]

    @staticmethod
    def _mean(values: Iterable[float]) -> float:
        vals = [float(v) for v in values if UserStateFeatureExtractor._is_finite(v)]
        return float(mean(vals)) if vals else 0.0

    @staticmethod
    def _std(values: Iterable[float]) -> float:
        vals = [float(v) for v in values if UserStateFeatureExtractor._is_finite(v)]
        return float(pstdev(vals)) if len(vals) >= 2 else 0.0

    @staticmethod
    def _coord(landmark: Any, name: str) -> float:
        return float(getattr(landmark, name, 0.0) or 0.0)

    @staticmethod
    def _clamp01(value: Any) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except Exception:
            return 0.0

    @staticmethod
    def _is_finite(value: Any) -> bool:
        try:
            return math.isfinite(float(value))
        except Exception:
            return False


__all__ = [
    "FRAME_FEATURE_FIELDS",
    "WINDOW_FEATURE_FIELDS",
    "USER_STATE_FEATURE_FIELDS",
    "UserStateFeatureExtractor",
]
