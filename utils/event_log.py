"""
Event log: JSONL-based event recording for desktop pet lifecycle events.

Supports structured logging of interaction events, cloud sync events,
state changes, and errors. Each line is a JSON object.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_LOG_PATH = Path(__file__).resolve().parents[1] / "logs" / "event_log.jsonl"


class EventLog:
    """
    Thread-safe JSONL event log.

    Usage:
        log = EventLog()
        log.write({"event_type": "chat", "user_input": "你好", "word_count": 10})
        events = log.read_recent(limit=20)
    """

    def __init__(self, filepath: Optional[str | Path] = None):
        self._lock = threading.Lock()
        self._path = Path(filepath or DEFAULT_LOG_PATH)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def write(self, data: Dict[str, Any]) -> None:
        """
        Append one JSON line to the log.

        :param data: dict with at least an "event_type" key.
        """
        record = dict(data)
        record.setdefault("timestamp", datetime.now().isoformat())
        record.setdefault("event_type", "unknown")
        with self._lock:
            try:
                with open(self._path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
            except OSError as exc:
                print(f"[EventLog] Write error: {exc}")

    def read_recent(self, limit: int = 50) -> list[Dict[str, Any]]:
        """
        Read the most recent `limit` events from the log.

        :param limit: max number of events to return
        :return: list of event dicts (newest first)
        """
        if not self._path.exists():
            return []
        lines: list[str] = []
        with self._lock:
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            except OSError:
                return []
        events: list[Dict[str, Any]] = []
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
            if len(events) >= limit:
                break
        return events

    def count_events(self, event_type: Optional[str] = None) -> int:
        """
        Count events, optionally filtered by type.

        :param event_type: if given, only count events with this type
        :return: count
        """
        if not self._path.exists():
            return 0
        count = 0
        with self._lock:
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        if event_type is None:
                            count += 1
                        else:
                            try:
                                obj = json.loads(line)
                                if obj.get("event_type") == event_type:
                                    count += 1
                            except json.JSONDecodeError:
                                continue
            except OSError:
                pass
        return count

    def clear(self) -> None:
        """Delete the log file."""
        with self._lock:
            if self._path.exists():
                self._path.unlink(missing_ok=True)

    # ── 兼容别名（用户要求的标准 API 名称） ──

    def append_event(self, event: Dict[str, Any]) -> None:
        """与 write() 等价的标准接口。"""
        self.write(event)

    def read_recent_events(self, n: int = 10) -> list[Dict[str, Any]]:
        """与 read_recent() 等价的标准接口。"""
        return self.read_recent(limit=n)

    def clear_events(self) -> None:
        """与 clear() 等价的标准接口。"""
        self.clear()

    def __repr__(self) -> str:
        return f"EventLog(path={self._path})"


# Singleton for application-wide use
_event_log_instance: Optional[EventLog] = None
_event_log_lock = threading.Lock()


def get_event_log(filepath: Optional[str | Path] = None) -> EventLog:
    """Get or create the application-wide EventLog singleton."""
    global _event_log_instance
    if _event_log_instance is None:
        with _event_log_lock:
            if _event_log_instance is None:
                _event_log_instance = EventLog(filepath)
    return _event_log_instance
