"""
Time utility helpers for cooling, daily stats, and duration tracking.
"""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from typing import Dict, Optional


# ── Cooldown Tracker ──────────────────────────────────────

class CooldownTracker:
    """
    Simple per-key cooldown tracker.

    Usage:
        cd = CooldownTracker()
        if cd.is_ready("companion_comment", cooldown_secs=150):
            do_something()
            cd.track("companion_comment")
    """

    def __init__(self):
        self._records: Dict[str, float] = {}

    def track(self, key: str, timestamp: Optional[float] = None) -> None:
        """
        Record the current time (or given timestamp) for a key.

        :param key: event key
        :param timestamp: optional unix timestamp, default time.time()
        """
        self._records[key] = timestamp if timestamp is not None else time.time()

    def is_ready(self, key: str, cooldown_secs: float = 0.0) -> bool:
        """
        Check if `cooldown_secs` has elapsed since the last record for `key`.

        :param key: event key
        :param cooldown_secs: minimum interval in seconds
        :returns: True if ready (or never tracked)
        """
        last = self._records.get(key)
        if last is None:
            return True
        return (time.time() - last) >= cooldown_secs

    def remaining(self, key: str, cooldown_secs: float = 0.0) -> float:
        """
        Seconds remaining before `key` is ready again.

        :returns: 0.0 if ready
        """
        last = self._records.get(key)
        if last is None:
            return 0.0
        remaining = cooldown_secs - (time.time() - last)
        return max(0.0, remaining)

    def clear(self) -> None:
        self._records.clear()


# ── Daily Accumulator ─────────────────────────────────────

class DailyAccumulator:
    """
    Tracks a daily running total, resetting at midnight.

    Usage:
        acc = DailyAccumulator()
        acc.add(15)              # add 15 units today
        print(acc.total)         # today's total so far
        print(acc.reset_if_new_day())
    """

    def __init__(self, initial_total: float = 0.0):
        self._date = date.today()
        self._total = max(0.0, float(initial_total))

    @property
    def total(self) -> float:
        """Return today's accumulated total (auto-resets if new day)."""
        self.reset_if_new_day()
        return self._total

    def add(self, amount: float) -> float:
        """
        Add amount (seconds, count, etc.) to today's total.

        :param amount: non-negative number
        :returns: the new total
        """
        self.reset_if_new_day()
        self._total += max(0.0, float(amount))
        return self._total

    def reset_if_new_day(self) -> bool:
        """If today is a new calendar day, reset the total to 0. Returns True if reset."""
        today = date.today()
        if self._date < today:
            self._date = today
            self._total = 0.0
            return True
        return False

    def reset(self, total: float = 0.0) -> None:
        self._date = date.today()
        self._total = max(0.0, float(total))

    def to_dict(self) -> dict:
        return {"date": self._date.isoformat(), "total": self._total}

    @classmethod
    def from_dict(cls, data: dict) -> "DailyAccumulator":
        inst = cls(initial_total=float(data.get("total", 0)))
        try:
            inst._date = date.fromisoformat(str(data.get("date", "")))
        except (ValueError, TypeError):
            inst._date = date.today()
        return inst


# ── Formatting Helpers ────────────────────────────────────

def format_duration(seconds: float) -> str:
    """
    Format a duration in seconds into a human-readable string.

    Examples:
        format_duration(45)        → "45秒"
        format_duration(150)       → "2分钟30秒"
        format_duration(7260)      → "2小时1分钟"

    :param seconds: duration in seconds
    :returns: human-readable Chinese string
    """
    seconds = max(0.0, float(seconds))
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours}小时")
    if minutes:
        parts.append(f"{minutes}分钟")
    if secs or not parts:
        parts.append(f"{secs}秒")
    return "".join(parts)


def format_timestamp(ts: float, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format a unix timestamp into a readable string."""
    return datetime.fromtimestamp(ts).strftime(fmt)


def to_unix(dt: Optional[datetime] = None) -> float:
    """Convert a datetime to a unix timestamp; defaults to now."""
    if dt is None:
        return time.time()
    return dt.timestamp()
