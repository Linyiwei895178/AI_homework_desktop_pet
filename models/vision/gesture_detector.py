"""GestureDetector: mock-compatible gesture recognition interface."""

from __future__ import annotations

import copy
import math
import os
import tempfile
import threading
import time
import urllib.request
from collections import deque
from typing import Any, Callable, Dict, Optional


GESTURE_WAVE = "wave"
GESTURE_OK = "ok"
GESTURE_HEART = "heart"
GESTURE_RAISED_HAND = "raised_hand"
GESTURE_PINCH_ZOOM = "pinch_zoom"
GESTURE_NONE = "none"

ZOOM_MIN_PINCH_DISTANCE = 0.03
ZOOM_MAX_PINCH_DISTANCE = 0.35
ZOOM_MIN_SCALE = 0.6
ZOOM_MAX_SCALE = 1.8

HAND_LANDMARKER_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)

ALL_GESTURE_CODES = {
    GESTURE_WAVE,
    GESTURE_OK,
    GESTURE_HEART,
    GESTURE_RAISED_HAND,
    GESTURE_PINCH_ZOOM,
    GESTURE_NONE,
}

GESTURE_NAME_MAP = {
    GESTURE_WAVE: "挥手",
    GESTURE_OK: "OK",
    GESTURE_HEART: "比心",
    GESTURE_RAISED_HAND: "举手",
    GESTURE_PINCH_ZOOM: "手势缩放",
    GESTURE_NONE: "无",
}

GESTURE_DESCRIPTIONS = {
    GESTURE_WAVE: "模拟检测到用户挥手。",
    GESTURE_OK: "模拟检测到用户做出 OK 手势。",
    GESTURE_HEART: "模拟检测到用户比心。",
    GESTURE_RAISED_HAND: "模拟检测到用户举手。",
    GESTURE_PINCH_ZOOM: "检测到用户正在用拇指和食指控制缩放。",
    GESTURE_NONE: "当前没有检测到明确手势。",
}

GESTURE_SUGGESTIONS = {
    GESTURE_WAVE: "给桌宠：开心回应用户挥手，可以说“我看到你啦”。",
    GESTURE_OK: "给桌宠：用轻快语气回应用户的 OK 手势，表示收到。",
    GESTURE_HEART: "给桌宠：用开心、亲近的语气回应用户比心。",
    GESTURE_RAISED_HAND: "给桌宠：回应用户举手，像被叫到一样注意用户。",
    GESTURE_PINCH_ZOOM: "给桌宠：手势缩放是控制指令，不需要主动说话。",
    GESTURE_NONE: "给桌宠：无手势，不需要主动回应。",
}


def create_gesture_state(
    gesture_code: str = GESTURE_NONE,
    confidence: float | None = None,
    source: Optional[list[str]] = None,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a stable gesture_state dict for Team B/C integration."""
    if gesture_code not in ALL_GESTURE_CODES:
        gesture_code = GESTURE_NONE

    need_response = gesture_code not in {GESTURE_NONE, GESTURE_PINCH_ZOOM}
    if confidence is None:
        confidence = 0.0 if gesture_code == GESTURE_NONE else 0.9
    return {
        "gesture_code": gesture_code,
        "gesture_name": GESTURE_NAME_MAP[gesture_code],
        "description": description or GESTURE_DESCRIPTIONS[gesture_code],
        "confidence": round(max(0.0, min(1.0, float(confidence))), 2),
        "need_response": need_response,
        "suggestion": GESTURE_SUGGESTIONS[gesture_code],
        "source": source or ["mock_gesture"],
    }


class GestureDetector:
    """
    Mock-first gesture detector.

    The public interface is intentionally small:
        start(), stop(), get_state(), set_callback(), set_mock_gesture()
    """

    def __init__(
        self,
        initial_gesture: str = GESTURE_NONE,
        camera_index: int = 0,
        detect_interval: float = 0.12,
        enable_real: bool = True,
        frame_provider: Any = None,
    ):
        self._running = False
        self._callback: Optional[Callable[[Dict[str, Any]], None]] = None
        self._lock = threading.RLock()
        self._state: Dict[str, Any] = create_gesture_state(initial_gesture)
        self.camera_index = int(camera_index)
        self.detect_interval = max(0.03, float(detect_interval))
        self.enable_real = bool(enable_real)
        self._frame_provider = frame_provider
        self._last_zoom_scale = 1.0
        self._last_zoom_active_at = 0.0
        self._pinch_distance_history: deque[tuple[float, float]] = deque(maxlen=8)
        self._state["zoom"] = self._inactive_zoom_state()

        self._thread: Optional[threading.Thread] = None
        self._debug_snapshot: Dict[str, Any] = self._build_debug_snapshot(
            self._state,
            hands=[],
            handedness=[],
            source=self._state.get("source", ["mock_gesture"]),
        )
        self._cv2: Any = None
        self._mp: Any = None
        self._hands: Any = None
        self._cap: Any = None
        self._owns_camera = frame_provider is None
        self._mp_mode: Optional[str] = None
        self._real_active = False
        self._hand_center_history: deque[tuple[float, float]] = deque(maxlen=14)

    def start(self) -> None:
        """Start the detector. Uses MediaPipe Hands when camera access works."""
        if self._running:
            return
        self._running = True
        if self.enable_real and self._init_real_detector():
            self._real_active = True
            self._thread = threading.Thread(target=self._detect_loop, daemon=True)
            self._thread.start()
            print("[GestureDetector] Started (MediaPipe Hands).")
            return

        self._real_active = False
        print("[GestureDetector] Started (mock mode; camera/MediaPipe unavailable).")

    def stop(self) -> None:
        """Stop the detector and release camera/MediaPipe resources."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._release_real_detector()
        self._real_active = False
        print("[GestureDetector] Stopped.")

    def get_state(self) -> Dict[str, Any]:
        """Return the latest gesture state."""
        with self._lock:
            return copy.deepcopy(self._state)

    def get_debug_snapshot(self) -> Dict[str, Any]:
        """Return latest MediaPipe Hands landmarks for visual debug preview."""
        with self._lock:
            return copy.deepcopy(self._debug_snapshot)

    def set_callback(self, callback: Optional[Callable[[Dict[str, Any]], None]]) -> None:
        """Register a callback invoked when set_mock_gesture updates state."""
        self._callback = callback

    def set_mock_gesture(self, gesture_code: str) -> None:
        """Set a mock gesture and notify the callback once if present."""
        state = create_gesture_state(str(gesture_code or GESTURE_NONE).strip())
        state["zoom"] = self._inactive_zoom_state()
        self._cache_debug_snapshot(state, hands=[], handedness=[], source=state.get("source", ["mock_gesture"]))
        self._update_state(state, notify=True)

    def is_running(self) -> bool:
        """Small helper for tests and future app integration."""
        return self._running

    def is_real_active(self) -> bool:
        """Return True when MediaPipe Hands is actively reading the camera."""
        return self._real_active

    def _notify_callback(self) -> None:
        if self._callback is None:
            return
        try:
            self._callback(self.get_state())
        except Exception as exc:
            print(f"[GestureDetector] gesture callback failed: {exc}")

    def _init_real_detector(self) -> bool:
        try:
            import cv2  # type: ignore
            import mediapipe as mp  # type: ignore
        except Exception as exc:
            print(f"[GestureDetector] MediaPipe/OpenCV unavailable: {exc}")
            return False

        try:
            self._cv2 = cv2
            self._mp = mp

            if self._frame_provider is None:
                cap = cv2.VideoCapture(self.camera_index)
                if not cap or not cap.isOpened():
                    if cap:
                        cap.release()
                    print("[GestureDetector] Camera unavailable; falling back to mock mode.")
                    return False

                try:
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                except Exception:
                    pass

                self._cap = cap

            solutions = getattr(mp, "solutions", None)
            if solutions is not None and hasattr(solutions, "hands"):
                self._hands = solutions.hands.Hands(
                    static_image_mode=False,
                    max_num_hands=2,
                    model_complexity=0,
                    min_detection_confidence=0.55,
                    min_tracking_confidence=0.55,
                )
                self._mp_mode = "solutions"
                return True

            self._hands = self._create_tasks_hand_landmarker()
            self._mp_mode = "tasks"
            return True
        except Exception as exc:
            print(f"[GestureDetector] Real detector init failed: {exc}")
            self._release_real_detector()
            return False

    def _release_real_detector(self) -> None:
        try:
            if self._cap is not None:
                self._cap.release()
        except Exception:
            pass
        try:
            if self._hands is not None:
                self._hands.close()
        except Exception:
            pass
        self._cap = None
        self._hands = None
        self._mp_mode = None

    def _create_tasks_hand_landmarker(self) -> Any:
        from mediapipe.tasks.python import vision  # type: ignore
        from mediapipe.tasks.python.core.base_options import BaseOptions  # type: ignore

        model_path = self._ensure_hand_landmarker_model()
        options = vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=model_path),
            running_mode=vision.RunningMode.IMAGE,
            num_hands=2,
            min_hand_detection_confidence=0.55,
            min_hand_presence_confidence=0.55,
            min_tracking_confidence=0.55,
        )
        return vision.HandLandmarker.create_from_options(options)

    def _ensure_hand_landmarker_model(self) -> str:
        cache_root = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
        model_dir = os.path.join(cache_root, "AI_homework_desktop_pet", "models")
        model_path = os.path.join(model_dir, "hand_landmarker.task")

        if os.path.exists(model_path) and os.path.getsize(model_path) > 1_000_000:
            return model_path

        os.makedirs(model_dir, exist_ok=True)
        temp_path = model_path + ".download"
        print("[GestureDetector] Downloading MediaPipe hand landmark model...")
        urllib.request.urlretrieve(HAND_LANDMARKER_MODEL_URL, temp_path)
        os.replace(temp_path, model_path)
        return model_path

    def _detect_loop(self) -> None:
        while self._running and self._hands is not None:
            loop_start = time.time()
            try:
                ret, frame = self._read_frame()
                if not ret or frame is None:
                    state = create_gesture_state(
                        GESTURE_NONE,
                        confidence=0.0,
                        source=["mediapipe_hands"],
                        description="摄像头暂时没有读到画面。",
                    )
                    state["zoom"] = self._inactive_zoom_state()
                    self._cache_debug_snapshot(state, hands=[], handedness=[], source=["mediapipe_hands"])
                    self._update_state(state)
                    time.sleep(self.detect_interval)
                    continue

                state = self._detect_gesture(frame)
                self._update_state(state)
            except Exception as exc:
                print(f"[GestureDetector] detect loop failed: {exc}")
                state = create_gesture_state(
                    GESTURE_NONE,
                    confidence=0.0,
                    source=["mediapipe_hands"],
                    description="手势识别循环出现异常，暂未检测到手势。",
                )
                state["zoom"] = self._inactive_zoom_state()
                self._cache_debug_snapshot(state, hands=[], handedness=[], source=["mediapipe_hands"])
                self._update_state(state)

            elapsed = time.time() - loop_start
            time.sleep(max(0.01, self.detect_interval - elapsed))

    def _read_frame(self) -> tuple[bool, Any]:
        if self._frame_provider is not None:
            getter = getattr(self._frame_provider, "get_frame", None)
            if not callable(getter):
                return False, None
            frame = getter()
            return frame is not None, frame

        if self._cap is None:
            return False, None
        return self._cap.read()

    def _detect_gesture(self, frame: Any) -> Dict[str, Any]:
        """Run MediaPipe Hands on one frame and classify a simple gesture."""
        if self._cv2 is None or self._hands is None:
            state = create_gesture_state(GESTURE_NONE, source=["mediapipe_hands"])
            state["zoom"] = self._inactive_zoom_state()
            self._cache_debug_snapshot(state, hands=[], handedness=[], source=["mediapipe_hands"])
            return state

        rgb = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2RGB)
        if self._mp_mode == "solutions":
            result = self._hands.process(rgb)
            hands = [hand.landmark for hand in (getattr(result, "multi_hand_landmarks", None) or [])]
            handedness = [
                self._extract_handedness(item)
                for item in (getattr(result, "multi_handedness", None) or [])
            ]
        else:
            image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
            result = self._hands.detect(image)
            hands = getattr(result, "hand_landmarks", None) or []
            handedness = [
                self._extract_handedness(item)
                for item in (getattr(result, "handedness", None) or [])
            ]

        if not hands:
            self._hand_center_history.clear()
            self._pinch_distance_history.clear()
            state = create_gesture_state(
                GESTURE_NONE,
                confidence=0.0,
                source=["mediapipe_hands"],
                description="当前没有检测到手部。",
            )
            state["zoom"] = self._inactive_zoom_state()
            self._cache_debug_snapshot(state, hands=[], handedness=[], source=["mediapipe_hands"])
            return state

        zoom_state = self._calculate_zoom_state(hands[0])
        gesture_code, confidence = self._classify_hands(hands)
        description = f"MediaPipe Hands 检测到{GESTURE_NAME_MAP[gesture_code]}手势。"
        if gesture_code == GESTURE_NONE:
            description = "MediaPipe Hands 检测到手部，但没有匹配到明确手势。"
        if zoom_state.get("active") and gesture_code == GESTURE_OK:
            gesture_code = GESTURE_PINCH_ZOOM
            confidence = max(confidence, float(zoom_state.get("confidence", 0.0) or 0.0))
            description = "MediaPipe Hands 检测到拇指和食指距离变化，正在控制桌宠缩放。"
        state = create_gesture_state(
            gesture_code,
            confidence=confidence,
            source=["mediapipe_hands"],
            description=description,
        )
        state["zoom"] = zoom_state
        self._cache_debug_snapshot(state, hands=hands, handedness=handedness, source=["mediapipe_hands"])
        return state

    def _classify_hands(self, hands: list[Any]) -> tuple[str, float]:
        if len(hands) >= 2 and self._is_heart(hands[0], hands[1]):
            return GESTURE_HEART, 0.86

        primary = hands[0]
        self._track_hand_motion(primary)

        if self._is_ok(primary):
            return GESTURE_OK, 0.84
        if self._is_wave(primary):
            return GESTURE_WAVE, 0.82
        if self._is_raised_hand(primary):
            return GESTURE_RAISED_HAND, 0.8
        return GESTURE_NONE, 0.35

    def _track_hand_motion(self, landmarks: Any) -> None:
        xs = [float(lm.x) for lm in landmarks]
        ys = [float(lm.y) for lm in landmarks]
        self._hand_center_history.append((time.time(), sum(xs) / len(xs), sum(ys) / len(ys)))

    def _is_wave(self, landmarks: Any) -> bool:
        if len(self._hand_center_history) < 8:
            return False
        recent = [item for item in self._hand_center_history if time.time() - item[0] <= 1.4]
        if len(recent) < 6:
            return False
        xs = [x for _, x, _ in recent]
        return max(xs) - min(xs) >= 0.16 and self._extended_finger_count(landmarks) >= 3

    def _is_ok(self, landmarks: Any) -> bool:
        thumb_tip = landmarks[4]
        index_tip = landmarks[8]
        middle_up = self._finger_is_up(landmarks, 12, 10)
        ring_up = self._finger_is_up(landmarks, 16, 14)
        pinky_up = self._finger_is_up(landmarks, 20, 18)
        return self._distance(thumb_tip, index_tip) <= 0.055 and sum([middle_up, ring_up, pinky_up]) >= 2

    def _is_heart(self, left: Any, right: Any) -> bool:
        index_close = self._distance(left[8], right[8]) <= 0.13
        thumb_close = self._distance(left[4], right[4]) <= 0.16
        wrists_apart = self._distance(left[0], right[0]) >= 0.12
        return index_close and thumb_close and wrists_apart

    def _is_raised_hand(self, landmarks: Any) -> bool:
        extended = self._extended_finger_count(landmarks)
        tips_above_wrist = sum(landmarks[idx].y < landmarks[0].y for idx in (8, 12, 16, 20))
        return extended >= 4 and tips_above_wrist >= 3

    def _extended_finger_count(self, landmarks: Any) -> int:
        count = 0
        for tip_idx, pip_idx in ((8, 6), (12, 10), (16, 14), (20, 18)):
            if self._finger_is_up(landmarks, tip_idx, pip_idx):
                count += 1
        return count

    @staticmethod
    def _finger_is_up(landmarks: Any, tip_idx: int, pip_idx: int) -> bool:
        return float(landmarks[tip_idx].y) < float(landmarks[pip_idx].y) - 0.025

    @staticmethod
    def _distance(a: Any, b: Any) -> float:
        return math.dist((float(a.x), float(a.y)), (float(b.x), float(b.y)))

    def _calculate_zoom_state(self, landmarks: Any) -> Dict[str, Any]:
        if len(landmarks) <= 8:
            return self._inactive_zoom_state()

        pinch_distance = self._distance(landmarks[4], landmarks[8])
        now = time.time()
        self._pinch_distance_history.append((now, pinch_distance))
        recent = [distance for ts, distance in self._pinch_distance_history if now - ts <= 0.8]
        movement = (max(recent) - min(recent)) if len(recent) >= 3 else 0.0
        moving = movement >= 0.012
        if moving:
            self._last_zoom_active_at = now

        active = moving or (len(recent) >= 2 and now - self._last_zoom_active_at <= 0.6)
        target_scale = self._pinch_distance_to_scale(pinch_distance)
        smooth_scale = self._last_zoom_scale * 0.75 + target_scale * 0.25
        if active:
            self._last_zoom_scale = smooth_scale

        return {
            "gesture_code": GESTURE_PINCH_ZOOM,
            "active": bool(active),
            "pinch_distance": round(float(pinch_distance), 4),
            "target_scale": round(float(target_scale), 3),
            "scale_ratio": round(float(self._last_zoom_scale), 3),
            "confidence": 0.82 if active else 0.35,
            "min_pinch_distance": ZOOM_MIN_PINCH_DISTANCE,
            "max_pinch_distance": ZOOM_MAX_PINCH_DISTANCE,
            "min_scale": ZOOM_MIN_SCALE,
            "max_scale": ZOOM_MAX_SCALE,
            "source": ["mediapipe_hands"],
        }

    @staticmethod
    def _pinch_distance_to_scale(pinch_distance: float) -> float:
        span = max(0.001, ZOOM_MAX_PINCH_DISTANCE - ZOOM_MIN_PINCH_DISTANCE)
        t = (float(pinch_distance) - ZOOM_MIN_PINCH_DISTANCE) / span
        t = max(0.0, min(1.0, t))
        return ZOOM_MIN_SCALE + t * (ZOOM_MAX_SCALE - ZOOM_MIN_SCALE)

    def _inactive_zoom_state(self) -> Dict[str, Any]:
        return {
            "gesture_code": GESTURE_PINCH_ZOOM,
            "active": False,
            "pinch_distance": None,
            "target_scale": round(float(self._last_zoom_scale), 3),
            "scale_ratio": round(float(self._last_zoom_scale), 3),
            "confidence": 0.0,
            "min_pinch_distance": ZOOM_MIN_PINCH_DISTANCE,
            "max_pinch_distance": ZOOM_MAX_PINCH_DISTANCE,
            "min_scale": ZOOM_MIN_SCALE,
            "max_scale": ZOOM_MAX_SCALE,
            "source": ["mediapipe_hands"],
        }

    def _cache_debug_snapshot(
        self,
        state: Dict[str, Any],
        hands: list[Any],
        handedness: list[str],
        source: list[str],
    ) -> None:
        snapshot = self._build_debug_snapshot(state, hands=hands, handedness=handedness, source=source)
        with self._lock:
            self._debug_snapshot = snapshot

    def _build_debug_snapshot(
        self,
        state: Dict[str, Any],
        hands: list[Any],
        handedness: list[str],
        source: Any,
    ) -> Dict[str, Any]:
        source_list = source if isinstance(source, list) else [str(source)]
        hand_items: list[dict[str, Any]] = []
        for index, landmarks in enumerate(hands or []):
            label = handedness[index] if index < len(handedness) else "Unknown"
            hand_items.append({
                "landmarks": [self._landmark_to_dict(lm) for lm in landmarks],
                "handedness": label or "Unknown",
            })
        primary_handedness = hand_items[0]["handedness"] if hand_items else "Unknown"
        return {
            "gesture_code": state.get("gesture_code", GESTURE_NONE),
            "confidence": float(state.get("confidence", 0.0) or 0.0),
            "handedness": primary_handedness,
            "hands": hand_items,
            "zoom": copy.deepcopy(state.get("zoom") or self._inactive_zoom_state()),
            "source": source_list,
            "timestamp": time.time(),
        }

    @staticmethod
    def _landmark_to_dict(landmark: Any) -> Dict[str, float]:
        return {
            "x": float(getattr(landmark, "x", 0.0) or 0.0),
            "y": float(getattr(landmark, "y", 0.0) or 0.0),
            "z": float(getattr(landmark, "z", 0.0) or 0.0),
        }

    @staticmethod
    def _extract_handedness(item: Any) -> str:
        categories = item
        if hasattr(item, "classification"):
            categories = getattr(item, "classification", [])
        if not isinstance(categories, (list, tuple)):
            categories = [categories]
        if not categories:
            return "Unknown"
        first = categories[0]
        label = (
            getattr(first, "category_name", None)
            or getattr(first, "display_name", None)
            or getattr(first, "label", None)
            or ""
        )
        return str(label or "Unknown")

    def _update_state(self, state: Dict[str, Any], notify: bool = False) -> None:
        with self._lock:
            old_code = self._state.get("gesture_code")
            self._state = copy.deepcopy(state)
            new_code = self._state.get("gesture_code")

        if notify or (new_code != old_code and new_code != GESTURE_NONE):
            self._notify_callback()
