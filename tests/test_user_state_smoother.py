import os
import sys


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.vision.user_state_smoother import UserStateSmoother  # noqa: E402


def test_initial_state_is_normal():
    smoother = UserStateSmoother()

    assert smoother.current_state == "normal"
    assert smoother.candidate_state is None


def test_distracted_requires_stable_candidate_time():
    smoother = UserStateSmoother()

    first = smoother.update("distracted", now=0.0)
    second = smoother.update("distracted", now=2.0)
    third = smoother.update("distracted", now=3.1)

    assert first["state_code"] == "normal"
    assert second["state_code"] == "normal"
    assert third["state_code"] == "distracted"
    assert third["changed"] is True


def test_tired_enters_faster_than_distracted():
    smoother = UserStateSmoother()

    smoother.update("tired", now=0.0)
    waiting = smoother.update("tired", now=1.5)
    changed = smoother.update("tired", now=2.1)

    assert waiting["state_code"] == "normal"
    assert changed["state_code"] == "tired"


def test_camera_error_is_immediate():
    smoother = UserStateSmoother(current_state="focused")

    result = smoother.update("camera_error", now=10.0)

    assert result["state_code"] == "camera_error"
    assert result["changed"] is True
    assert result["reason"] == "immediate"


def test_normal_has_short_enter_time():
    smoother = UserStateSmoother(current_state="focused")

    first = smoother.update("normal", now=0.0)
    second = smoother.update("normal", now=1.1)

    assert first["state_code"] == "focused"
    assert second["state_code"] == "normal"
