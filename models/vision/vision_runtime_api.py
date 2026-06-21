"""Read-only runtime snapshot API for Team A vision/status panels."""

from __future__ import annotations

import copy
import time
from typing import Any, Callable


MOOD_NAME_MAP = {
    "happy": "开心",
    "neutral": "普通",
    "sad": "难过",
    "tired": "疲惫",
    "excited": "兴奋",
    "angry": "生气",
    "hungry": "饥饿",
}

ACTION_NAME_MAP = {
    "happy": "开心动作",
    "idle": "待机",
    "rest": "休息",
    "speak": "说话",
    "sad": "难过动作",
    "angry": "生气动作",
    "hungry": "饥饿动作",
    "empty": "空动作",
    "": "无动作",
}

USER_STATE_DEFAULT = {
    "state_code": "unknown",
    "state_name": "未知",
    "confidence": 0.0,
    "source": "detector_disabled",
}

GESTURE_NONE = {
    "gesture_code": "none",
    "gesture_name": "无手势",
    "confidence": 0.0,
    "active": False,
}

GESTURE_DISABLED = {
    "gesture_code": "disabled",
    "gesture_name": "手势识别未开启",
    "confidence": 0.0,
    "active": False,
}

EXPRESSION_NAME_MAP = {
    "happy": "开心",
    "neutral": "平静",
    "sad": "难过",
    "angry": "生气",
    "surprise": "惊讶",
    "surprised": "惊讶",
    "fear": "紧张",
    "disgust": "不适",
    "tired": "疲惫",
    "unknown": "未知",
}

USER_EXPRESSION_DEFAULT = {
    "expression_code": "unknown",
    "expression_name": "未知",
    "confidence": 0.0,
    "source": "face_mimic_unavailable",
    "face_mimic": {},
}


class VisionRuntimeAPI:
    """Small read-only adapter around existing runtime objects.

    The adapter never starts cameras or detectors. It only reads state through
    callables provided by app/main.py and returns JSON-friendly dictionaries.
    """

    def __init__(
        self,
        *,
        shared_camera_getter: Callable[[], Any],
        camera_enabled_getter: Callable[[], bool],
        user_detector_running_getter: Callable[[], bool],
        gesture_detector_running_getter: Callable[[], bool],
        user_state_getter: Callable[[], dict | None],
        gesture_state_getter: Callable[[], dict | None],
        pet_state_getter: Callable[[], Any],
        action_state_getter: Callable[[], dict | None],
        user_expression_getter: Callable[[], dict | None] | None = None,
    ) -> None:
        self._shared_camera_getter = shared_camera_getter
        self._camera_enabled_getter = camera_enabled_getter
        self._user_detector_running_getter = user_detector_running_getter
        self._gesture_detector_running_getter = gesture_detector_running_getter
        self._user_state_getter = user_state_getter
        self._user_expression_getter = user_expression_getter
        self._gesture_state_getter = gesture_state_getter
        self._pet_state_getter = pet_state_getter
        self._action_state_getter = action_state_getter

    def get_latest_camera_frame_rgb(self) -> Any:
        """Return the latest shared-camera frame in RGB order, or None."""
        if not self._safe_bool(self._camera_enabled_getter):
            return None

        camera = self._safe_call(self._shared_camera_getter)
        if camera is None:
            return None

        is_running = getattr(camera, "is_running", None)
        if callable(is_running):
            try:
                if not bool(is_running()):
                    return None
            except Exception:
                return None

        get_frame = getattr(camera, "get_frame", None)
        if not callable(get_frame):
            return None

        try:
            frame = get_frame()
        except Exception:
            return None
        if frame is None:
            return None

        try:
            if getattr(frame, "ndim", 0) >= 3 and frame.shape[2] >= 3:
                return frame[:, :, :3][:, :, ::-1].copy()
        except Exception:
            pass

        try:
            return frame.copy()
        except Exception:
            return copy.deepcopy(frame)

    def get_latest_runtime_snapshot(self) -> dict:
        """Return a JSON-friendly snapshot for UI status panels."""
        now = time.time()
        return {
            "camera_enabled": self._safe_bool(self._camera_enabled_getter),
            "user_detector_running": self._safe_bool(self._user_detector_running_getter),
            "gesture_detector_running": self._safe_bool(self._gesture_detector_running_getter),
            "user_state": self.get_latest_user_state(now),
            "user_expression": self.get_latest_user_expression(now),
            "gesture": self.get_latest_gesture_state(now),
            "pet_emotion": self.get_latest_pet_emotion(now),
            "action": self.get_latest_action_state(),
            "timestamp": now,
        }

    def get_latest_user_state(self, timestamp: float | None = None) -> dict:
        if not self._safe_bool(self._user_detector_running_getter):
            return dict(USER_STATE_DEFAULT)

        state = self._safe_call(self._user_state_getter)
        if not isinstance(state, dict):
            return dict(USER_STATE_DEFAULT)

        return {
            "state_code": str(state.get("state_code", "unknown") or "unknown"),
            "state_name": str(state.get("state_name", "未知") or "未知"),
            "confidence": self._float(state.get("confidence", 0.0)),
            "source": self._source_text(state.get("source", "detector")),
        }

    def get_latest_user_expression(self, timestamp: float | None = None) -> dict:
        if not callable(self._user_expression_getter):
            return dict(USER_EXPRESSION_DEFAULT)

        payload = self._safe_call(self._user_expression_getter)
        if not isinstance(payload, dict):
            return dict(USER_EXPRESSION_DEFAULT)

        mimic = payload.get("face_mimic") if isinstance(payload.get("face_mimic"), dict) else {}

        mimic_code = str(mimic.get("expression") or "unknown").lower()
        mimic_confidence = self._float(mimic.get("confidence", 0.0))
        mimic_available = bool(mimic.get("available")) and mimic_code != "unknown"

        if not mimic_available:
            result = dict(USER_EXPRESSION_DEFAULT)
            result["face_mimic"] = self._json_safe_copy(mimic)
            return result

        return {
            "expression_code": mimic_code,
            "expression_name": EXPRESSION_NAME_MAP.get(mimic_code, mimic_code),
            "confidence": mimic_confidence,
            "source": self._source_text(mimic.get("source", "face_mimic")),
            "face_mimic": self._json_safe_copy(mimic),
        }

    def get_latest_gesture_state(self, timestamp: float | None = None) -> dict:
        if not self._safe_bool(self._gesture_detector_running_getter):
            return dict(GESTURE_DISABLED)

        state = self._safe_call(self._gesture_state_getter)
        if not isinstance(state, dict):
            return dict(GESTURE_NONE)

        gesture_code = str(state.get("gesture_code", "none") or "none")
        zoom = state.get("zoom") if isinstance(state.get("zoom"), dict) else {}
        if gesture_code == "pinch_zoom":
            gesture_code = "pinch"
        elif zoom.get("active"):
            gesture_code = "pinch"

        if gesture_code in {"none", ""}:
            active = False
        else:
            active = True

        gesture_name = state.get("gesture_name")
        if gesture_code == "pinch":
            gesture_name = "捏合缩放"

        return {
            "gesture_code": gesture_code or "none",
            "gesture_name": str(gesture_name or ("无手势" if not active else gesture_code)),
            "confidence": self._float(state.get("confidence", zoom.get("confidence", 0.0))),
            "active": bool(active),
        }

    def get_latest_pet_emotion(self, timestamp: float | None = None) -> dict:
        pet_state = self._safe_call(self._pet_state_getter)
        if pet_state is None:
            return {
                "mood": "neutral",
                "mood_name": MOOD_NAME_MAP["neutral"],
                "energy": None,
                "intimacy": None,
            }

        mood = str(getattr(pet_state, "mood", "neutral") or "neutral")
        return {
            "mood": mood,
            "mood_name": MOOD_NAME_MAP.get(mood, mood),
            "energy": self._optional_int(getattr(pet_state, "energy", None)),
            "intimacy": self._optional_int(getattr(pet_state, "intimacy", None)),
        }

    def get_latest_action_state(self) -> dict:
        action_state = self._safe_call(self._action_state_getter)
        if not isinstance(action_state, dict):
            return {
                "action_code": "",
                "action_name": ACTION_NAME_MAP[""],
                "last_trigger_time": None,
            }

        action_code = str(action_state.get("action_code", "") or "")
        last_trigger_time = action_state.get("last_trigger_time")
        return {
            "action_code": action_code,
            "action_name": ACTION_NAME_MAP.get(action_code, f"{action_code}动作" if action_code else ACTION_NAME_MAP[""]),
            "last_trigger_time": self._optional_float(last_trigger_time),
        }

    @staticmethod
    def _safe_call(func: Callable[[], Any]) -> Any:
        try:
            return func()
        except Exception:
            return None

    @classmethod
    def _safe_bool(cls, func: Callable[[], Any]) -> bool:
        return bool(cls._safe_call(func))

    @staticmethod
    def _source_text(source: Any) -> str:
        if isinstance(source, str):
            return source
        if isinstance(source, (list, tuple)):
            parts = [str(item) for item in source if item is not None and str(item)]
            return "+".join(parts) if parts else ""
        if source is None:
            return ""
        return str(source)

    @staticmethod
    def _float(value: Any) -> float:
        try:
            return float(value)
        except Exception:
            return 0.0

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except Exception:
            return None

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except Exception:
            return None

    @staticmethod
    def _json_safe_copy(value: Any) -> Any:
        try:
            return copy.deepcopy(value)
        except Exception:
            return {}


__all__ = ["VisionRuntimeAPI"]
