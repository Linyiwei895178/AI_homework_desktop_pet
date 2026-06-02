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
GESTURE_NONE = "none"

HAND_LANDMARKER_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)

ALL_GESTURE_CODES = {
    GESTURE_WAVE,
    GESTURE_OK,
    GESTURE_HEART,
    GESTURE_RAISED_HAND,
    GESTURE_NONE,
}

GESTURE_NAME_MAP = {
    GESTURE_WAVE: "挥手",
    GESTURE_OK: "OK",
    GESTURE_HEART: "比心",
    GESTURE_RAISED_HAND: "举手",
    GESTURE_NONE: "无",
}

GESTURE_DESCRIPTIONS = {
    GESTURE_WAVE: "模拟检测到用户挥手。",
    GESTURE_OK: "模拟检测到用户做出 OK 手势。",
    GESTURE_HEART: "模拟检测到用户比心。",
    GESTURE_RAISED_HAND: "模拟检测到用户举手。",
    GESTURE_NONE: "当前没有检测到明确手势。",
}

GESTURE_SUGGESTIONS = {
    GESTURE_WAVE: "给桌宠：开心回应用户挥手，可以说“我看到你啦”。",
    GESTURE_OK: "给桌宠：用轻快语气回应用户的 OK 手势，表示收到。",
    GESTURE_HEART: "给桌宠：用开心、亲近的语气回应用户比心。",
    GESTURE_RAISED_HAND: "给桌宠：回应用户举手，像被叫到一样注意用户。",
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

    need_response = gesture_code != GESTURE_NONE
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

        self._thread: Optional[threading.Thread] = None
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

    def set_callback(self, callback: Optional[Callable[[Dict[str, Any]], None]]) -> None:
        """Register a callback invoked when set_mock_gesture updates state."""
        self._callback = callback

    def set_mock_gesture(self, gesture_code: str) -> None:
        """Set a mock gesture and notify the callback once if present."""
        self._update_state(create_gesture_state(str(gesture_code or GESTURE_NONE).strip()), notify=True)

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
                    self._update_state(create_gesture_state(
                        GESTURE_NONE,
                        confidence=0.0,
                        source=["mediapipe_hands"],
                        description="摄像头暂时没有读到画面。",
                    ))
                    time.sleep(self.detect_interval)
                    continue

                state = self._detect_gesture(frame)
                self._update_state(state)
            except Exception as exc:
                print(f"[GestureDetector] detect loop failed: {exc}")
                self._update_state(create_gesture_state(
                    GESTURE_NONE,
                    confidence=0.0,
                    source=["mediapipe_hands"],
                    description="手势识别循环出现异常，暂未检测到手势。",
                ))

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
            return create_gesture_state(GESTURE_NONE, source=["mediapipe_hands"])

        rgb = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2RGB)
        if self._mp_mode == "solutions":
            result = self._hands.process(rgb)
            hands = [hand.landmark for hand in (getattr(result, "multi_hand_landmarks", None) or [])]
        else:
            image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
            result = self._hands.detect(image)
            hands = getattr(result, "hand_landmarks", None) or []

        if not hands:
            self._hand_center_history.clear()
            return create_gesture_state(
                GESTURE_NONE,
                confidence=0.0,
                source=["mediapipe_hands"],
                description="当前没有检测到手部。",
            )

        gesture_code, confidence = self._classify_hands(hands)
        description = f"MediaPipe Hands 检测到{GESTURE_NAME_MAP[gesture_code]}手势。"
        if gesture_code == GESTURE_NONE:
            description = "MediaPipe Hands 检测到手部，但没有匹配到明确手势。"
        return create_gesture_state(
            gesture_code,
            confidence=confidence,
            source=["mediapipe_hands"],
            description=description,
        )

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

    def _update_state(self, state: Dict[str, Any], notify: bool = False) -> None:
        with self._lock:
            old_code = self._state.get("gesture_code")
            self._state = copy.deepcopy(state)
            new_code = self._state.get("gesture_code")

        if notify or (new_code != old_code and new_code != GESTURE_NONE):
            self._notify_callback()
