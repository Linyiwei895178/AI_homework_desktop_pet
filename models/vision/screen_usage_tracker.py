"""
ScreenUsageTracker: tracks continuous and cumulative screen usage.

Uses the computer_activity_detector's activity_state to:
- Track the duration of the current session.
- Accumulate daily total screen time.
- Fire screen_time_reminder events when thresholds are exceeded.

# TODO: Persist daily totals across app restarts.
# TODO: Add configurable thresholds via settings.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from utils.time_utils import DailyAccumulator


class ScreenUsageTracker:
    """
    Tracks screen usage duration and generates reminders.

    Usage:
        tracker = ScreenUsageTracker()
        # In your main loop:
        result = tracker.update("coding", now)
        if result:
            print(result)  # screen_time_reminder event
    """

    # Reminder thresholds in minutes
    DEFAULT_REMINDER_THRESHOLDS = [60, 120, 180, 240]

    def __init__(self, reminder_thresholds: Optional[list[int]] = None):
        self._session_start: float = time.time()
        self._last_activity: Optional[str] = None
        self._daily_minutes = DailyAccumulator()
        self._last_threshold: int = 0
        self._thresholds = sorted(reminder_thresholds or self.DEFAULT_REMINDER_THRESHOLDS)

    def update(self, activity_code: str, now: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Update the tracker with the current activity state.

        :param activity_code: current activity code from ComputerActivityDetector
        :param now:           current timestamp (default: time.time())
        :returns:             screen_time_reminder event dict if a threshold was
                              just crossed, otherwise None
        """
        now = now or time.time()
        activity_code = str(activity_code or "unknown")

        # Reset session if activity changed
        if activity_code != self._last_activity and self._last_activity is not None:
            session_delta = (now - self._session_start) / 60.0
            self._daily_minutes.add(session_delta)
            self._session_start = now
            self._last_threshold = 0

        self._last_activity = activity_code

        # Calculate current session duration
        session_minutes = (now - self._session_start) / 60.0
        total_minutes = self._daily_minutes.total + session_minutes

        # Check thresholds
        for threshold in self._thresholds:
            if total_minutes >= threshold > self._last_threshold:
                self._last_threshold = threshold
                return {
                    "event_type": "screen_time_reminder",
                    "daily_minutes": round(total_minutes, 1),
                    "session_minutes": round(session_minutes, 1),
                    "threshold": threshold,
                    "activity_code": activity_code,
                    "suggestion": f"今天已经使用电脑 {int(total_minutes)} 分钟了，建议休息一下哦。",
                    "timestamp": now,
                }

        return None

    def get_daily_minutes(self) -> float:
        """Get total screen time today (so far)."""
        session = (time.time() - self._session_start) / 60.0
        return round(self._daily_minutes.total + session, 1)

    def get_session_minutes(self) -> float:
        """Get current session duration."""
        return round((time.time() - self._session_start) / 60.0, 1)
