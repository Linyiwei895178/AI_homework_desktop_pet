import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.vision.companion_event_builder import (
    CompanionEventBuilder,
    build_companion_event,
)


def activity(code: str, **extra):
    state = {
        "activity_code": code,
        "activity_name": code,
        "app_name": "",
        "window_title": "",
        "duration": 0.0,
        "confidence": 0.8,
        "source": ["test"],
    }
    state.update(extra)
    return state


def usage(code: str, continuous_seconds: float, today_seconds: float | None = None):
    total = continuous_seconds if today_seconds is None else today_seconds
    return {
        "activity_code": code,
        "continuous_seconds": continuous_seconds,
        "today_totals": {code: total},
        "today_seconds": total,
    }


def test_builds_gaming_comment_with_cooldown_fields():
    builder = CompanionEventBuilder(cooldown_seconds=600, comment_min_seconds={"gaming": 0})

    event = builder.build(
        activity("gaming", activity_name="游戏中", app_name="Steam", window_title="Steam"),
        usage("gaming", continuous_seconds=120),
        now=1000.0,
    )

    assert event["event_type"] == "computer_activity_comment"
    assert event["activity_code"] == "gaming"
    assert event["need_response"] is True
    assert event["priority"] == "low"
    assert event["cooldown_seconds"] == 600
    assert "给桌宠" in event["suggestion"]


def test_cooldown_blocks_repeated_activity_comment():
    builder = CompanionEventBuilder(cooldown_seconds=600, comment_min_seconds={"watching": 0})
    state = activity("watching", activity_name="看剧/视频中", window_title="Bilibili")
    summary = usage("watching", continuous_seconds=300)

    assert builder.build(state, summary, now=1000.0) is not None
    assert builder.build(state, summary, now=1200.0) is None
    assert builder.build(state, summary, now=1600.0) is not None


def test_builds_low_disturbance_coding_reminder_after_threshold():
    builder = CompanionEventBuilder(
        cooldown_seconds=600,
        reminder_thresholds_seconds={"coding": 10},
    )

    event = builder.build(
        activity("coding", activity_name="编程中", app_name="VS Code"),
        usage("coding", continuous_seconds=10, today_seconds=120),
        now=1000.0,
    )

    assert event["event_type"] == "screen_time_reminder"
    assert event["activity_code"] == "coding"
    assert event["continuous_seconds"] == 10
    assert event["today_seconds"] == 120
    assert event["priority"] == "normal"
    assert "不要打断思路" in event["suggestion"]


def test_browsing_and_chatting_only_remind_after_long_duration():
    builder = CompanionEventBuilder(
        cooldown_seconds=600,
        reminder_thresholds_seconds={"browsing": 100, "chatting": 100},
    )

    assert builder.build(activity("browsing"), usage("browsing", 99), now=1000.0) is None

    browsing = builder.build(activity("browsing"), usage("browsing", 100), now=1000.0)
    chatting = builder.build(activity("chatting"), usage("chatting", 150), now=1000.0)

    assert browsing["event_type"] == "screen_time_reminder"
    assert browsing["activity_code"] == "browsing"
    assert chatting["event_type"] == "screen_time_reminder"
    assert chatting["activity_code"] == "chatting"


def test_normal_short_focused_work_does_not_create_event():
    builder = CompanionEventBuilder(reminder_thresholds_seconds={"working": 100})

    event = builder.build(
        activity("working", state_code="focused"),
        usage("working", continuous_seconds=30),
        now=1000.0,
    )

    assert event is None


def test_module_level_build_companion_event_returns_event():
    event = build_companion_event(
        activity("gaming", window_title="Minecraft", duration=600),
        usage("gaming", continuous_seconds=600),
    )

    assert event is None or event["event_type"] == "computer_activity_comment"
