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
    third = smoother.update("distracted", now=2.6)

    assert first["state_code"] == "normal"
    assert second["state_code"] == "normal"
    assert third["state_code"] == "distracted"
    assert third["changed"] is True


def test_tired_enters_after_stable_candidate_time():
    smoother = UserStateSmoother()

    smoother.update("tired", now=0.0)
    waiting = smoother.update("tired", now=1.0)
    changed = smoother.update("tired", now=1.6)

    assert waiting["state_code"] == "normal"
    assert changed["state_code"] == "tired"


def test_tired_exits_to_normal_quickly():
    smoother = UserStateSmoother(current_state="tired")

    first = smoother.update("normal", now=0.0)
    second = smoother.update("normal", now=0.9)

    assert first["state_code"] == "tired"
    assert second["state_code"] == "normal"
    assert second["changed"] is True


def test_tired_normal_jitter_does_not_switch_back_and_forth():
    smoother = UserStateSmoother()

    assert smoother.update("tired", now=0.0)["state_code"] == "normal"
    assert smoother.update("normal", now=0.4)["state_code"] == "normal"
    assert smoother.update("tired", now=0.8)["state_code"] == "normal"
    assert smoother.update("normal", now=1.0)["state_code"] == "normal"
    assert smoother.current_state == "normal"


def test_distracted_exits_to_normal_quickly():
    smoother = UserStateSmoother()

    smoother.update("distracted", now=0.0)
    entered = smoother.update("distracted", now=2.6)
    first_normal = smoother.update("normal", now=3.0)
    exited = smoother.update("normal", now=3.9)

    assert entered["state_code"] == "distracted"
    assert first_normal["state_code"] == "distracted"
    assert exited["state_code"] == "normal"


def test_camera_error_is_immediate():
    smoother = UserStateSmoother(current_state="focused")

    result = smoother.update("camera_error", now=10.0)

    assert result["state_code"] == "camera_error"
    assert result["changed"] is True
    assert result["reason"] == "immediate"


def test_focused_exits_to_normal_after_exit_time():
    smoother = UserStateSmoother(current_state="focused")

    first = smoother.update("normal", now=0.0)
    second = smoother.update("normal", now=1.1)

    assert first["state_code"] == "focused"
    assert second["state_code"] == "normal"
