import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.vision.screen_usage_tracker import ScreenUsageTracker


def activity(code: str) -> dict:
    return {
        "activity_code": code,
        "activity_name": code,
        "description": "",
        "confidence": 0.8,
        "source": ["test"],
    }


def test_update_tracks_current_activity_continuous_seconds_and_today_total():
    tracker = ScreenUsageTracker()

    summary = tracker.update(activity("coding"), now=1000.0)
    assert summary["activity_code"] == "coding"
    assert summary["continuous_seconds"] == 0.0
    assert summary["today_totals"]["coding"] == 0.0

    summary = tracker.update(activity("coding"), now=1600.0)
    assert summary["activity_code"] == "coding"
    assert summary["continuous_seconds"] == 600.0
    assert summary["today_totals"]["coding"] == 600.0
    assert summary["today_seconds"] == 600.0


def test_switching_activity_resets_continuous_time_and_keeps_totals():
    tracker = ScreenUsageTracker()

    tracker.update(activity("coding"), now=1000.0)
    tracker.update(activity("coding"), now=1120.0)
    summary = tracker.update(activity("working"), now=1180.0)

    assert summary["activity_code"] == "working"
    assert summary["continuous_seconds"] == 0.0
    assert summary["today_totals"]["coding"] == 180.0
    assert summary["today_totals"]["working"] == 0.0

    summary = tracker.update(activity("working"), now=1240.0)
    assert summary["continuous_seconds"] == 60.0
    assert summary["today_totals"]["working"] == 60.0


def test_builds_reminder_once_when_activity_crosses_threshold():
    tracker = ScreenUsageTracker(thresholds_seconds={"coding": 10.0})

    tracker.update(activity("coding"), now=1000.0)
    tracker.update(activity("coding"), now=1009.0)
    assert tracker.maybe_build_reminder_event(now=1009.0) is None

    tracker.update(activity("coding"), now=1010.0)
    event = tracker.maybe_build_reminder_event(now=1010.0)

    assert event == {
        "event_type": "screen_time_reminder",
        "activity_code": "coding",
        "continuous_seconds": 10.0,
        "today_seconds": 10.0,
        "need_response": True,
        "priority": "normal",
        "description": "用户已连续编程较长时间，建议适当休息。",
        "suggestion": (
            "给桌宠：用温和、不责备的语气提醒用户休息一下，"
            "可以建议站起来活动、喝水或看看远处。"
        ),
    }
    assert tracker.maybe_build_reminder_event(now=1011.0) is None


def test_reminder_priority_high_after_long_over_threshold_session():
    tracker = ScreenUsageTracker(thresholds_seconds={"gaming": 100.0})

    tracker.update(activity("gaming"), now=1000.0)
    tracker.update(activity("gaming"), now=1150.0)
    event = tracker.maybe_build_reminder_event(now=1150.0)

    assert event is not None
    assert event["activity_code"] == "gaming"
    assert event["priority"] == "high"
    assert event["continuous_seconds"] == 150.0


def test_no_reminder_for_unknown_activity():
    tracker = ScreenUsageTracker(thresholds_seconds={"coding": 1.0})

    tracker.update(activity("unknown"), now=1000.0)
    tracker.update(activity("unknown"), now=5000.0)

    assert tracker.maybe_build_reminder_event(now=5000.0) is None


def test_reset_today_if_needed_clears_daily_totals_without_ui_dependencies():
    tracker = ScreenUsageTracker()
    day_one = 1700000000.0
    day_two = day_one + 24 * 60 * 60 + 10

    tracker.update(activity("watching"), now=day_one)
    tracker.update(activity("watching"), now=day_one + 120.0)
    assert tracker.get_summary()["today_totals"]["watching"] == 120.0

    tracker.reset_today_if_needed(now=day_two)
    summary = tracker.get_summary()

    assert summary["today_totals"]["watching"] == 0.0
    assert summary["activity_code"] == "watching"
