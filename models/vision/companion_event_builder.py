"""
Vision-side proactive event helpers.
"""

from __future__ import annotations

import time
from typing import Any

from models.nlp.proactive_event_builder import (
    build_cloud_pet_event,
    build_gesture_event,
    build_screen_time_event,
)
from models.vision.computer_activity_detector import build_companion_event as build_computer_activity_event


COMMENT_ACTIVITIES = {"gaming", "watching"}
REMINDER_ACTIVITIES = {"coding", "working", "browsing", "chatting"}

DEFAULT_COOLDOWN_SECONDS = 600
DEFAULT_REMINDER_THRESHOLDS_SECONDS = {
    "coding": 45 * 60,
    "working": 45 * 60,
    "browsing": 60 * 60,
    "chatting": 60 * 60,
}
DEFAULT_COMMENT_MIN_SECONDS = {
    "gaming": 5 * 60,
    "watching": 5 * 60,
}

ACTIVITY_NAME_MAP = {
    "coding": "编程",
    "working": "办公",
    "gaming": "游戏",
    "watching": "视频",
    "browsing": "浏览网页",
    "chatting": "聊天",
}


class CompanionEventBuilder:
    """Build vision-side companion events with a simple per-activity cooldown."""

    def __init__(
        self,
        cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS,
        reminder_thresholds_seconds: dict[str, float] | None = None,
        comment_min_seconds: dict[str, float] | None = None,
    ):
        self.cooldown_seconds = max(0.0, float(cooldown_seconds))
        self.reminder_thresholds_seconds = dict(DEFAULT_REMINDER_THRESHOLDS_SECONDS)
        if reminder_thresholds_seconds:
            for code, seconds in reminder_thresholds_seconds.items():
                self.reminder_thresholds_seconds[str(code)] = max(0.0, float(seconds))

        self.comment_min_seconds = dict(DEFAULT_COMMENT_MIN_SECONDS)
        if comment_min_seconds:
            for code, seconds in comment_min_seconds.items():
                self.comment_min_seconds[str(code)] = max(0.0, float(seconds))

        self._last_event_at: dict[str, float] = {}

    def set_cooldown(self, seconds: float) -> None:
        self.cooldown_seconds = max(0.0, float(seconds))

    def build(
        self,
        activity_state: dict[str, Any],
        usage_summary: dict[str, Any] | None = None,
        now: float | None = None,
    ) -> dict[str, Any] | None:
        if not isinstance(activity_state, dict):
            return None

        now = time.time() if now is None else float(now)
        usage_summary = usage_summary if isinstance(usage_summary, dict) else {}
        activity_code = str(activity_state.get("activity_code") or "").strip()
        if not activity_code:
            return None

        continuous_seconds = _continuous_seconds(activity_state, usage_summary)
        today_seconds = _today_seconds(activity_code, usage_summary)

        if activity_code in COMMENT_ACTIVITIES:
            if continuous_seconds < self.comment_min_seconds.get(activity_code, 0.0):
                return None
            event = self._build_activity_comment(
                activity_state,
                continuous_seconds=continuous_seconds,
                today_seconds=today_seconds,
                now=now,
            )
        elif activity_code in REMINDER_ACTIVITIES:
            threshold = self.reminder_thresholds_seconds.get(activity_code)
            if threshold is None or continuous_seconds < threshold:
                return None
            event = self._build_screen_time_reminder(
                activity_state,
                continuous_seconds=continuous_seconds,
                today_seconds=today_seconds,
                threshold_seconds=threshold,
                now=now,
            )
        else:
            return None

        cooldown_key = f"{event['event_type']}:{activity_code}"
        last_event_at = self._last_event_at.get(cooldown_key)
        if last_event_at is not None and now - last_event_at < self.cooldown_seconds:
            return None

        self._last_event_at[cooldown_key] = now
        return event

    def _build_activity_comment(
        self,
        activity_state: dict[str, Any],
        continuous_seconds: float,
        today_seconds: float,
        now: float,
    ) -> dict[str, Any]:
        activity_code = str(activity_state.get("activity_code") or "")
        activity_name = str(activity_state.get("activity_name") or ACTIVITY_NAME_MAP.get(activity_code, activity_code))
        app_name = str(activity_state.get("app_name") or "")
        window_title = str(activity_state.get("window_title") or "")
        target = _target_text(app_name, window_title)

        if activity_code == "gaming":
            description = f"检测到用户正在{activity_name}，可以轻松陪玩但不要频繁打扰。"
            suggestion = (
                f"给桌宠：用户正在玩{target}，像朋友在旁边轻松点评一句，"
                "可以夸操作或吐槽局势，短一点，别指挥太多。"
            )
        else:
            description = f"检测到用户正在{activity_name}，可以像一起看视频一样轻松陪伴。"
            suggestion = (
                f"给桌宠：用户正在看{target}，像朋友一起看视频一样小声点评一句，"
                "短、自然、不要剧透。"
            )

        return {
            "event_type": "computer_activity_comment",
            "activity_code": activity_code,
            "activity_name": activity_name,
            "app_name": app_name,
            "window_title": window_title,
            "continuous_seconds": round(continuous_seconds, 2),
            "today_seconds": round(today_seconds, 2),
            "need_response": True,
            "priority": "low",
            "cooldown_seconds": int(self.cooldown_seconds),
            "description": description,
            "suggestion": suggestion,
            "timestamp": now,
        }

    def _build_screen_time_reminder(
        self,
        activity_state: dict[str, Any],
        continuous_seconds: float,
        today_seconds: float,
        threshold_seconds: float,
        now: float,
    ) -> dict[str, Any]:
        activity_code = str(activity_state.get("activity_code") or "")
        activity_name = str(activity_state.get("activity_name") or ACTIVITY_NAME_MAP.get(activity_code, activity_code))
        app_name = str(activity_state.get("app_name") or "")
        priority = "high" if continuous_seconds >= threshold_seconds * 1.5 else "normal"

        if activity_code in {"coding", "working"}:
            description = f"用户已连续{activity_name}较长时间，建议低打扰提醒休息。"
            suggestion = (
                "给桌宠：用户正在专注，不要打断思路。用很短、温和的语气提醒休息眼睛、"
                "喝水或伸展一下。"
            )
        elif activity_code == "browsing":
            description = "用户连续浏览网页时间较长，建议轻提醒休息。"
            suggestion = "给桌宠：轻轻提醒用户浏览一段时间了，可以看看远处或整理一下当前任务。"
        else:
            description = "用户连续聊天时间较长，建议低频提醒休息。"
            suggestion = "给桌宠：用不打扰的方式提醒用户聊久了可以喝口水、活动一下。"

        return {
            "event_type": "screen_time_reminder",
            "activity_code": activity_code,
            "activity_name": activity_name,
            "app_name": app_name,
            "continuous_seconds": round(continuous_seconds, 2),
            "today_seconds": round(today_seconds, 2),
            "need_response": True,
            "priority": priority,
            "cooldown_seconds": int(self.cooldown_seconds),
            "description": description,
            "suggestion": suggestion,
            "timestamp": now,
        }


_DEFAULT_BUILDER = CompanionEventBuilder()


def build_companion_event(
    state: dict[str, Any],
    usage_summary: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Build a companion event, preserving the old one-argument compatibility path."""
    if usage_summary is None:
        return build_computer_activity_event(state)
    return _DEFAULT_BUILDER.build(state, usage_summary)


def _continuous_seconds(activity_state: dict[str, Any], usage_summary: dict[str, Any]) -> float:
    value = usage_summary.get("continuous_seconds")
    if isinstance(value, (int, float)):
        return max(0.0, float(value))
    value = activity_state.get("duration")
    if isinstance(value, (int, float)):
        return max(0.0, float(value))
    return 0.0


def _today_seconds(activity_code: str, usage_summary: dict[str, Any]) -> float:
    totals = usage_summary.get("today_totals")
    if isinstance(totals, dict):
        value = totals.get(activity_code, 0.0)
        if isinstance(value, (int, float)):
            return max(0.0, float(value))

    value = usage_summary.get("today_seconds")
    if isinstance(value, (int, float)):
        return max(0.0, float(value))
    return 0.0


def _target_text(app_name: str, window_title: str) -> str:
    title = window_title.strip()
    app = app_name.strip()
    if title:
        return f"《{title[:40]}》"
    if app:
        return app
    return "当前内容"


__all__ = [
    "CompanionEventBuilder",
    "build_companion_event",
    "build_computer_activity_event",
    "build_screen_time_event",
    "build_cloud_pet_event",
    "build_gesture_event",
]
