"""
GestureDetector: interface skeleton for camera-based gesture recognition.

# TODO: Implement real MediaPipe Hands gesture recognition.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional


class GestureDetector:
    """
    Camera-based gesture detector.

    Current version is a stub that always reports "none" gesture.
    """

    def __init__(self):
        self._running = False
        self._callback: Optional[Callable[[Dict[str, Any]], None]] = None
        self._state: Dict[str, Any] = {
            "gesture": "none",
            "confidence": 0.0,
            "hand_landmarks": None,
        }

    def start(self) -> None:
        """
        Start the gesture detection loop.

        # TODO: Initialize MediaPipe Hands and start camera capture.
        """
        self._running = True
        print("[GestureDetector] Started (stub).")

    def stop(self) -> None:
        """
        Stop the gesture detection loop.

        # TODO: Release camera and MediaPipe resources.
        """
        self._running = False
        print("[GestureDetector] Stopped.")

    def get_state(self) -> Dict[str, Any]:
        """
        Get the latest recognized gesture state.

        :returns: dict with keys: gesture, confidence, hand_landmarks
        """
        return dict(self._state)

    def set_callback(self, callback: Optional[Callable[[Dict[str, Any]], None]]) -> None:
        """
        Register a callback for gesture recognition results.

        The callback receives a dict with keys: gesture, confidence, timestamp.

        :param callback: callable(gesture_dict)
        """
        self._callback = callback

    def is_running(self) -> bool:
        return self._running

    # ── Internal (TODO) ──

    def _detect_gesture(self) -> None:
        """
        # TODO: Use MediaPipe Hands to:
        #   1. Capture a frame from the camera.
        #   2. Run MediaPipe Hands inference.
        #   3. Classify gesture (wave, thumbs_up, peace, point, none).
        #   4. Update self._state and call self._callback.
        """
        pass
