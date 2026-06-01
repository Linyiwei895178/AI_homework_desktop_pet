import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.vision.gesture_detector import (
    ALL_GESTURE_CODES,
    GESTURE_NONE,
    GestureDetector,
)


EXPECTED_FIELDS = {
    "gesture_code",
    "gesture_name",
    "description",
    "confidence",
    "need_response",
    "suggestion",
    "source",
}


def test_default_state_is_none_gesture():
    detector = GestureDetector()
    state = detector.get_state()

    assert set(state) == EXPECTED_FIELDS
    assert state["gesture_code"] == GESTURE_NONE
    assert state["gesture_name"] == "无"
    assert state["confidence"] == 0.0
    assert state["need_response"] is False
    assert state["source"] == ["mock_gesture"]


def test_start_and_stop_do_not_require_camera():
    detector = GestureDetector()

    detector.start()
    assert detector.is_running() is True

    detector.stop()
    assert detector.is_running() is False


def test_all_mock_gestures_return_stable_fields():
    detector = GestureDetector()

    for gesture_code in ALL_GESTURE_CODES:
        detector.set_mock_gesture(gesture_code)
        state = detector.get_state()
        assert set(state) == EXPECTED_FIELDS
        assert state["gesture_code"] == gesture_code
        assert 0.0 <= state["confidence"] <= 1.0
        assert state["source"] == ["mock_gesture"]


def test_set_mock_gesture_triggers_callback_once():
    detector = GestureDetector()
    seen = []
    detector.set_callback(lambda state: seen.append(state))

    detector.set_mock_gesture("wave")

    assert len(seen) == 1
    assert seen[0]["gesture_code"] == "wave"
    assert seen[0]["gesture_name"] == "挥手"
    assert seen[0]["need_response"] is True
    assert "给桌宠" in seen[0]["suggestion"]


def test_unknown_mock_gesture_falls_back_to_none():
    detector = GestureDetector()

    detector.set_mock_gesture("unknown_gesture")
    state = detector.get_state()

    assert state["gesture_code"] == GESTURE_NONE
    assert state["need_response"] is False
