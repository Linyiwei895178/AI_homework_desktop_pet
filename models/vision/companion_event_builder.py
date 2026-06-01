"""
CompanionEventBuilder: converts activity_state into companion/reminder events.

Produces dicts with cooldown support that can be fed to prompt_builder.build_proactive_prompt.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from utils.time_utils import CooldownTracker


# Activities for which we generate companion comments
COMPANION_ACTIVITIES = {"gaming", "watching"}

# Activities for which we generate gentle reminders
REMINDER_ACTIVITIES = {"coding", "working", "browsing"}


class CompanionEventBuilder:
    """
    Builds companion/reminder events from activity states with built-in cooldown.

    Usage:
        builder = CompanionEventBuilder(cooldown_secs=150)
        event = builder.build("gaming", {"duration": 60, "app_name": "Steam"})
        if event:
            prompt_builder.build_proactive_prompt(event)
    """

    def __init__(self, cooldown_secs: float = 150.0):
        """
        :param cooldown_secs: minimum seconds between companion comments per activity
        """
        self._cooldown = CooldownTracker()
        self._cooldown_secs = max(30.0, float(cooldown_secs))

    def set_cooldown(self, seconds: float) -> None:
        self._cooldown_secs = max(30.0, float(seconds))

    def build(self, activity_state: Dict[str, Any], usage_summary: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Build an event from an activity state.

        :param activity_state: output of ComputerActivityDetector.get_state()
        :param usage_summary:  optional additional context from ScreenUsageTracker
        :returns:              event dict with event_type, or None if cooldown active
        """
        if not isinstance(activity_state, dict):
            return None

        activity_code = str(activity_state.get("activity_code", "") or "")
        duration = float(activity_state.get("duration", 0.0))

        # Check cooldown per activity
        if not self._cooldown.is_ready(f"companion_{activity_code}", self._cooldown_secs):
            return None

        if activity_code in COMPANION_ACTIVITIES:
            event = self._build_companion(activity_state)
        elif activity_code in REMINDER_ACTIVITIES and duration > 1800:
            event = self._build_reminder(activity_state)
        else:
            return None

        self._cooldown.track(f"companion_{activity_code}")
        return event

    def _build_companion(self, state: Dict[str, Any]) -> Dict[str, Any]:
        activity_code = state.get("activity_code", "unknown")
        app_name = str(state.get("app_name", "") or "")
        window_title = str(state.get("window_title", "") or "")

        suggestions = {
            "gaming": (
                f"用户正在玩{app_name}，前台是《{window_title[:30]}》。"
                "请像朋友在旁边陪玩一样点评一句，轻松短小，别指挥太多。"
            ),
            "watching": (
                f"用户正在看{app_name}，前台是《{window_title[:30]}》。"
                "请像一起追剧的朋友一样点评一句，短、自然、不要剧透。"
            ),
        }

        return {
            "event_type": "computer_activity_comment",
            "activity_code": activity_code,
            "activity_name": state.get("activity_name", ""),
            "app_name": app_name,
            "window_title": window_title,
            "duration": state.get("duration", 0.0),
            "suggestion": suggestions.get(activity_code, "根据电脑状态主动说一句简短自然的话。"),
            "need_response": True,
            "state_code": "normal",
            "timestamp": time.time(),
        }

    def _build_reminder(self, state: Dict[str, Any]) -> Dict[str, Any]:
        activity_code = state.get("activity_code", "unknown")
        app_name = str(state.get("app_name", "") or "")
        return {
            "event_type": "screen_time_reminder",
            "activity_code": activity_code,
            "app_name": app_name,
            "suggestion": f"用户已经专注{app_name}很久了，请简短关心，提醒休息。",
            "need_response": True,
            "state_code": "normal",
            "timestamp": time.time(),
        }
