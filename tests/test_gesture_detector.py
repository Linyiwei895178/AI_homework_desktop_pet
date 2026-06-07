import os
import sys
import time
from types import SimpleNamespace

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

    assert EXPECTED_FIELDS <= set(state)
    assert "zoom" in state
    assert state["gesture_code"] == GESTURE_NONE
    assert state["gesture_name"] == "无"
    assert state["confidence"] == 0.0
    assert state["need_response"] is False
    assert state["source"] == ["mock_gesture"]


def test_start_and_stop_do_not_require_camera():
    detector = GestureDetector(enable_real=False)

    detector.start()
    assert detector.is_running() is True

    detector.stop()
    assert detector.is_running() is False


def test_all_mock_gestures_return_stable_fields():
    detector = GestureDetector()

    for gesture_code in ALL_GESTURE_CODES:
        detector.set_mock_gesture(gesture_code)
        state = detector.get_state()
        assert EXPECTED_FIELDS <= set(state)
        assert "zoom" in state
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


def test_reads_frame_from_shared_provider_without_camera():
    frame = object()
    provider = SimpleNamespace(get_frame=lambda: frame)
    detector = GestureDetector(enable_real=False, frame_provider=provider)

    ok, got = detector._read_frame()

    assert ok is True
    assert got is frame


def test_classifies_ok_from_hand_landmarks_without_camera():
    detector = GestureDetector(enable_real=False)
    landmarks = _blank_hand()
    landmarks[4] = _point(0.50, 0.50)
    landmarks[8] = _point(0.53, 0.50)
    _set_finger_up(landmarks, 12, 10)
    _set_finger_up(landmarks, 16, 14)
    _set_finger_up(landmarks, 20, 18)

    code, confidence = detector._classify_hands([landmarks])

    assert code == "ok"
    assert confidence >= 0.8


def test_classifies_raised_hand_from_open_palm_landmarks():
    detector = GestureDetector(enable_real=False)
    landmarks = _blank_hand()
    landmarks[0] = _point(0.5, 0.9)
    for tip_idx, pip_idx in ((8, 6), (12, 10), (16, 14), (20, 18)):
        _set_finger_up(landmarks, tip_idx, pip_idx)

    code, confidence = detector._classify_hands([landmarks])

    assert code == "raised_hand"
    assert confidence >= 0.8


def test_classifies_two_hand_heart_landmarks():
    detector = GestureDetector(enable_real=False)
    left = _blank_hand()
    right = _blank_hand()
    left[0] = _point(0.40, 0.80)
    right[0] = _point(0.60, 0.80)
    left[4] = _point(0.48, 0.52)
    right[4] = _point(0.55, 0.52)
    left[8] = _point(0.48, 0.42)
    right[8] = _point(0.55, 0.42)

    code, confidence = detector._classify_hands([left, right])

    assert code == "heart"
    assert confidence >= 0.8


def test_classifies_wave_from_recent_horizontal_motion():
    detector = GestureDetector(enable_real=False)
    now = time.time()
    detector._hand_center_history.extend(
        (now - 0.7 + i * 0.1, 0.35 + (i % 2) * 0.2, 0.5)
        for i in range(8)
    )
    landmarks = _blank_hand()
    for tip_idx, pip_idx in ((8, 6), (12, 10), (16, 14), (20, 18)):
        _set_finger_up(landmarks, tip_idx, pip_idx)

    assert detector._is_wave(landmarks) is True


def _point(x: float, y: float):
    return SimpleNamespace(x=x, y=y)


def _blank_hand():
    return [_point(0.5, 0.5) for _ in range(21)]


def _set_finger_up(landmarks, tip_idx: int, pip_idx: int):
    landmarks[tip_idx] = _point(0.5, 0.2)
    landmarks[pip_idx] = _point(0.5, 0.5)
