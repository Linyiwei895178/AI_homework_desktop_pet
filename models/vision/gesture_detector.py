"""
GestureDetector: simple mock-first gesture recognition interface.

First version only supports mock gestures. Real MediaPipe Hands recognition is
left as a TODO so app/main.py can integrate against a stable interface first.
"""

from __future__ import annotations

import copy
from typing import Any, Callable, Dict, Optional


GESTURE_WAVE = "wave"
GESTURE_OK = "ok"
GESTURE_HEART = "heart"
GESTURE_RAISED_HAND = "raised_hand"
GESTURE_NONE = "none"

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


def create_gesture_state(gesture_code: str = GESTURE_NONE) -> Dict[str, Any]:
    """Create a stable gesture_state dict for Team B/C integration."""
    if gesture_code not in ALL_GESTURE_CODES:
        gesture_code = GESTURE_NONE

    need_response = gesture_code != GESTURE_NONE
    return {
        "gesture_code": gesture_code,
        "gesture_name": GESTURE_NAME_MAP[gesture_code],
        "description": GESTURE_DESCRIPTIONS[gesture_code],
        "confidence": 0.0 if gesture_code == GESTURE_NONE else 0.9,
        "need_response": need_response,
        "suggestion": GESTURE_SUGGESTIONS[gesture_code],
        "source": ["mock_gesture"],
    }


class GestureDetector:
    """
    Mock-first gesture detector.

    The public interface is intentionally small:
        start(), stop(), get_state(), set_callback(), set_mock_gesture()
    """

    def __init__(self, initial_gesture: str = GESTURE_NONE):
        self._running = False
        self._callback: Optional[Callable[[Dict[str, Any]], None]] = None
        self._state: Dict[str, Any] = create_gesture_state(initial_gesture)

    def start(self) -> None:
        """Start the detector. Mock version does not open a camera."""
        self._running = True
        # TODO: Initialize MediaPipe Hands and camera capture in a real detector.
        print("[GestureDetector] Started (mock mode).")

    def stop(self) -> None:
        """Stop the detector. Mock version has no resources to release."""
        self._running = False
        # TODO: Release MediaPipe Hands and camera resources in a real detector.
        print("[GestureDetector] Stopped.")

    def get_state(self) -> Dict[str, Any]:
        """Return the latest gesture state."""
        return copy.deepcopy(self._state)

    def set_callback(self, callback: Optional[Callable[[Dict[str, Any]], None]]) -> None:
        """Register a callback invoked when set_mock_gesture updates state."""
        self._callback = callback

    def set_mock_gesture(self, gesture_code: str) -> None:
        """Set a mock gesture and notify the callback once if present."""
        self._state = create_gesture_state(str(gesture_code or GESTURE_NONE).strip())
        self._notify_callback()

    def is_running(self) -> bool:
        """Small helper for tests and future app integration."""
        return self._running

    def _notify_callback(self) -> None:
        if self._callback is None:
            return
        try:
            self._callback(self.get_state())
        except Exception as exc:
            print(f"[GestureDetector] gesture callback failed: {exc}")

    def _detect_gesture(self) -> None:
        """
        TODO: Real MediaPipe Hands recognition.

        Future steps:
        1. Capture a camera frame.
        2. Run MediaPipe Hands inference.
        3. Classify wave/ok/heart/raised_hand/none from hand landmarks.
        4. Update self._state and notify callback when gesture changes.
        """
        pass
