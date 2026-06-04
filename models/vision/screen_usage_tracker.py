"""
Screen usage tracking for Team B computer activity states.

The tracker consumes ComputerActivityDetector.get_state() dictionaries and keeps
only local timing data. It does not call UI, LLM, or TTS code.
"""

from __future__ import annotations

import time
from datetime import date, datetime
from typing import Any, Dict, Optional


ACTIVITY_CODING = "coding"
ACTIVITY_WORKING = "working"
ACTIVITY_GAMING = "gaming"
ACTIVITY_WATCHING = "watching"
ACTIVITY_BROWSING = "browsing"
ACTIVITY_CHATTING = "chatting"
ACTIVITY_IDLE = "idle"
ACTIVITY_UNKNOWN = "unknown"

TRACKED_ACTIVITIES = (
    ACTIVITY_CODING,
    ACTIVITY_WORKING,
    ACTIVITY_GAMING,
    ACTIVITY_WATCHING,
    ACTIVITY_BROWSING,
    ACTIVITY_CHATTING,
    ACTIVITY_IDLE,
    ACTIVITY_UNKNOWN,
)

DEFAULT_THRESHOLDS_SECONDS = {
    ACTIVITY_CODING: 45 * 60,
    ACTIVITY_WORKING: 45 * 60,
    ACTIVITY_GAMING: 60 * 60,
    ACTIVITY_WATCHING: 45 * 60,
    ACTIVITY_BROWSING: 60 * 60,
    ACTIVITY_CHATTING: 60 * 60,
}

ACTIVITY_NAME_MAP = {
    ACTIVITY_CODING: "编程",
    ACTIVITY_WORKING: "办公",
    ACTIVITY_GAMING: "游戏",
    ACTIVITY_WATCHING: "视频",
    ACTIVITY_BROWSING: "浏览网页",
    ACTIVITY_CHATTING: "聊天",
    ACTIVITY_IDLE: "空闲",
    ACTIVITY_UNKNOWN: "未知活动",
}


class ScreenUsageTracker:
    """Track continuous and daily screen usage by activity_code."""

    def __init__(self, thresholds_seconds: Optional[Dict[str, float]] = None):
        self.thresholds_seconds = dict(DEFAULT_THRESHOLDS_SECONDS)
        if thresholds_seconds:
            for code, seconds in thresholds_seconds.items():
                self.thresholds_seconds[str(code)] = max(0.0, float(seconds))

        self.today_totals: Dict[str, float] = {code: 0.0 for code in TRACKED_ACTIVITIES}
        self.current_activity_code = ACTIVITY_UNKNOWN
        self._activity_started_at: Optional[float] = None
        self._last_update_at: Optional[float] = None
        self._today = self._date_for_time(time.time())
        self._last_activity_state: Dict[str, Any] = {}
        self._reminded_session_key: Optional[tuple[str, float]] = None

    def update(self, activity_state: dict, now: float | None = None) -> dict:
        """
        Update usage counters with a ComputerActivityDetector activity_state.

        :returns: current summary dict. Call maybe_build_reminder_event() after
                  update() when the caller wants to emit a reminder event.
        """
        now = self._coerce_now(now)
        self.reset_today_if_needed(now)

        activity_code = self._activity_code_from_state(activity_state)

        if self._last_update_at is None:
            self.current_activity_code = activity_code
            self._activity_started_at = now
            self._last_update_at = now
            self._last_activity_state = dict(activity_state or {})
            self._ensure_total_key(activity_code)
            return self.get_summary()

        delta = max(0.0, now - self._last_update_at)
        self._ensure_total_key(self.current_activity_code)
        self.today_totals[self.current_activity_code] += delta

        if activity_code != self.current_activity_code:
            self.current_activity_code = activity_code
            self._activity_started_at = now
            self._reminded_session_key = None
            self._ensure_total_key(activity_code)

        self._last_update_at = now
        self._last_activity_state = dict(activity_state or {})
        return self.get_summary()

    def get_summary(self) -> dict:
        """Return current activity, continuous duration, and today's totals."""
        now = self._last_update_at if self._last_update_at is not None else time.time()
        continuous_seconds = self._continuous_seconds(now)
        today_totals = {code: round(seconds, 2) for code, seconds in self.today_totals.items()}
        activity_code = self.current_activity_code

        return {
            "activity_code": activity_code,
            "continuous_seconds": round(continuous_seconds, 2),
            "today_totals": today_totals,
            "today_seconds": round(today_totals.get(activity_code, 0.0), 2),
            "updated_at": now,
        }

    def reset_today_if_needed(self, now: float | None = None):
        """Reset daily totals when the local calendar day changes."""
        now = self._coerce_now(now)
        today = self._date_for_time(now)
        if today == self._today:
            return

        self._today = today
        self.today_totals = {code: 0.0 for code in TRACKED_ACTIVITIES}
        if self._last_update_at is not None:
            self._last_update_at = now
        self._reminded_session_key = None

    def maybe_build_reminder_event(self, now: float | None = None) -> dict | None:
        """Build a screen_time_reminder event once per over-threshold session."""
        now = self._coerce_now(now)
        activity_code = self.current_activity_code
        threshold = self.thresholds_seconds.get(activity_code)
        if threshold is None or threshold <= 0:
            return None

        continuous_seconds = self._continuous_seconds(now)
        if continuous_seconds < threshold:
            return None

        started_at = self._activity_started_at or now
        session_key = (activity_code, started_at)
        if self._reminded_session_key == session_key:
            return None

        self._reminded_session_key = session_key
        today_seconds = self.today_totals.get(activity_code, 0.0)
        priority = "high" if continuous_seconds >= threshold * 1.5 else "normal"
        activity_name = ACTIVITY_NAME_MAP.get(activity_code, activity_code)

        return {
            "event_type": "screen_time_reminder",
            "activity_code": activity_code,
            "continuous_seconds": round(continuous_seconds, 2),
            "today_seconds": round(today_seconds, 2),
            "need_response": True,
            "priority": priority,
            "description": f"用户已连续{activity_name}较长时间，建议适当休息。",
            "suggestion": (
                "给桌宠：用温和、不责备的语气提醒用户休息一下，"
                "可以建议站起来活动、喝水或看看远处。"
            ),
        }

    def get_daily_minutes(self) -> float:
        """Backward-compatible helper: total tracked screen time today in minutes."""
        return round(sum(self.today_totals.values()) / 60.0, 1)

    def get_session_minutes(self) -> float:
        """Backward-compatible helper: current activity continuous time in minutes."""
        now = self._last_update_at if self._last_update_at is not None else time.time()
        return round(self._continuous_seconds(now) / 60.0, 1)

    def _continuous_seconds(self, now: float) -> float:
        if self._activity_started_at is None:
            return 0.0
        return max(0.0, now - self._activity_started_at)

    def _ensure_total_key(self, activity_code: str) -> None:
        self.today_totals.setdefault(activity_code, 0.0)

    @staticmethod
    def _activity_code_from_state(activity_state: dict) -> str:
        if isinstance(activity_state, dict):
            activity_code = str(activity_state.get("activity_code") or ACTIVITY_UNKNOWN).strip()
        else:
            activity_code = str(activity_state or ACTIVITY_UNKNOWN).strip()
        return activity_code or ACTIVITY_UNKNOWN

    @staticmethod
    def _coerce_now(now: float | None) -> float:
        return time.time() if now is None else float(now)

    @staticmethod
    def _date_for_time(timestamp: float) -> date:
        return datetime.fromtimestamp(timestamp).date()
