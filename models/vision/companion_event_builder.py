"""
Build companion events from computer activity and screen usage summaries.

This module only creates event_data for Team C/D. It does not call DeepSeek,
TTS, UI, or any side-effectful service.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional


ACTIVITY_CODING = "coding"
ACTIVITY_WORKING = "working"
ACTIVITY_GAMING = "gaming"
ACTIVITY_WATCHING = "watching"
ACTIVITY_BROWSING = "browsing"
ACTIVITY_CHATTING = "chatting"

COMMENT_ACTIVITIES = {ACTIVITY_GAMING, ACTIVITY_WATCHING}
REMINDER_ACTIVITIES = {
    ACTIVITY_CODING,
    ACTIVITY_WORKING,
    ACTIVITY_BROWSING,
    ACTIVITY_CHATTING,
}

DEFAULT_COOLDOWN_SECONDS = 600
DEFAULT_REMINDER_THRESHOLDS_SECONDS = {
    ACTIVITY_CODING: 45 * 60,
    ACTIVITY_WORKING: 45 * 60,
    ACTIVITY_BROWSING: 60 * 60,
    ACTIVITY_CHATTING: 60 * 60,
}
DEFAULT_COMMENT_MIN_SECONDS = {
    ACTIVITY_GAMING: 5 * 60,
    ACTIVITY_WATCHING: 5 * 60,
}

ACTIVITY_NAME_MAP = {
    ACTIVITY_CODING: "编程",
    ACTIVITY_WORKING: "办公",
    ACTIVITY_GAMING: "游戏",
    ACTIVITY_WATCHING: "视频",
    ACTIVITY_BROWSING: "浏览网页",
    ACTIVITY_CHATTING: "聊天",
}


class CompanionEventBuilder:
    """Stateful event builder with per-activity cooldown."""

    def __init__(
        self,
        cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS,
        reminder_thresholds_seconds: Optional[Dict[str, float]] = None,
        comment_min_seconds: Optional[Dict[str, float]] = None,
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

        self._last_event_at: Dict[str, float] = {}

    def set_cooldown(self, seconds: float) -> None:
        self.cooldown_seconds = max(0.0, float(seconds))

    def build(
        self,
        activity_state: Dict[str, Any],
        usage_summary: Optional[Dict[str, Any]] = None,
        now: float | None = None,
    ) -> Optional[Dict[str, Any]]:
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
            min_seconds = self.comment_min_seconds.get(activity_code, 0.0)
            if continuous_seconds < min_seconds:
                return None
            event = self._build_activity_comment(
                activity_state=activity_state,
                continuous_seconds=continuous_seconds,
                today_seconds=today_seconds,
                now=now,
            )
        elif activity_code in REMINDER_ACTIVITIES:
            threshold = self.reminder_thresholds_seconds.get(activity_code)
            if threshold is None or continuous_seconds < threshold:
                return None
            event = self._build_screen_time_reminder(
                activity_state=activity_state,
                continuous_seconds=continuous_seconds,
                today_seconds=today_seconds,
                threshold_seconds=threshold,
                now=now,
            )
        else:
            return None

        cooldown_key = f"{event['event_type']}:{activity_code}"
        if not self._cooldown_ready(cooldown_key, now):
            return None

        self._last_event_at[cooldown_key] = now
        return event

    def _build_activity_comment(
        self,
        activity_state: Dict[str, Any],
        continuous_seconds: float,
        today_seconds: float,
        now: float,
    ) -> Dict[str, Any]:
        activity_code = str(activity_state.get("activity_code") or "")
        activity_name = str(activity_state.get("activity_name") or ACTIVITY_NAME_MAP.get(activity_code, activity_code))
        app_name = str(activity_state.get("app_name") or "")
        window_title = str(activity_state.get("window_title") or "")
        target = _target_text(app_name, window_title)

        if activity_code == ACTIVITY_GAMING:
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
        activity_state: Dict[str, Any],
        continuous_seconds: float,
        today_seconds: float,
        threshold_seconds: float,
        now: float,
    ) -> Dict[str, Any]:
        activity_code = str(activity_state.get("activity_code") or "")
        activity_name = str(activity_state.get("activity_name") or ACTIVITY_NAME_MAP.get(activity_code, activity_code))
        app_name = str(activity_state.get("app_name") or "")
        priority = "high" if continuous_seconds >= threshold_seconds * 1.5 else "normal"

        if activity_code in {ACTIVITY_CODING, ACTIVITY_WORKING}:
            description = f"用户已连续{activity_name}较长时间，建议低打扰提醒休息。"
            suggestion = (
                "给桌宠：用户正在专注，不要打断思路。用很短、温和的语气提醒休息眼睛、"
                "喝水或伸展一下。"
            )
        elif activity_code == ACTIVITY_BROWSING:
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

    def _cooldown_ready(self, key: str, now: float) -> bool:
        last = self._last_event_at.get(key)
        return last is None or now - last >= self.cooldown_seconds


_DEFAULT_BUILDER = CompanionEventBuilder()


def build_companion_event(
    activity_state: Dict[str, Any],
    usage_summary: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Build a companion event using the default cooldown-aware builder."""
    return _DEFAULT_BUILDER.build(activity_state, usage_summary)


def _continuous_seconds(activity_state: Dict[str, Any], usage_summary: Dict[str, Any]) -> float:
    value = usage_summary.get("continuous_seconds")
    if isinstance(value, (int, float)):
        return max(0.0, float(value))
    value = activity_state.get("duration")
    if isinstance(value, (int, float)):
        return max(0.0, float(value))
    return 0.0


def _today_seconds(activity_code: str, usage_summary: Dict[str, Any]) -> float:
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
