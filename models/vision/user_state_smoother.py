"""State smoothing for Team B user-state perception."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


ENTER_SECONDS = {
    "focused": 5.0,
    "distracted": 3.0,
    "tired": 2.0,
    "normal": 1.0,
    "away": 10.0,
    "low_light": 2.0,
    "return": 1.0,
}
IMMEDIATE_STATES = {"camera_error"}
VALID_STATES = {
    "normal",
    "focused",
    "distracted",
    "tired",
    "away",
    "return",
    "study_long",
    "low_light",
    "camera_error",
    "unknown",
}
PRIORITY = {
    "camera_error": 100,
    "away": 90,
    "return": 85,
    "low_light": 80,
    "study_long": 70,
    "tired": 60,
    "distracted": 50,
    "focused": 40,
    "normal": 10,
    "unknown": 0,
}


@dataclass
class UserStateSmoother:
    """Debounce noisy frame-level state predictions."""

    current_state: str = "normal"
    candidate_state: str | None = None
    candidate_since: float | None = None
    enter_seconds: dict[str, float] = field(default_factory=lambda: dict(ENTER_SECONDS))

    def update(self, state_code: str, now: float | None = None) -> dict[str, Any]:
        """Update smoother and return current state metadata."""
        now = time.time() if now is None else float(now)
        state_code = self._normalize(state_code)

        if state_code in IMMEDIATE_STATES:
            changed = self.current_state != state_code
            self.current_state = state_code
            self.candidate_state = None
            self.candidate_since = None
            return self._result(changed, "immediate", now)

        if state_code == self.current_state:
            self.candidate_state = None
            self.candidate_since = None
            return self._result(False, "stable", now)

        if self.candidate_state != state_code:
            self.candidate_state = state_code
            self.candidate_since = now
            return self._result(False, "candidate_started", now)

        if self.candidate_since is None:
            self.candidate_since = now

        elapsed = max(0.0, now - self.candidate_since)
        required = self.enter_seconds.get(state_code, 1.0)
        if elapsed >= required:
            changed = self.current_state != state_code
            self.current_state = state_code
            self.candidate_state = None
            self.candidate_since = None
            return self._result(changed, "changed", now, elapsed)

        return self._result(False, "waiting", now, elapsed)

    def reset(self, state_code: str = "normal", now: float | None = None) -> None:
        self.current_state = self._normalize(state_code)
        self.candidate_state = None
        self.candidate_since = None

    def _result(self, changed: bool, reason: str, now: float, candidate_elapsed: float = 0.0) -> dict[str, Any]:
        return {
            "state_code": self.current_state,
            "changed": bool(changed),
            "candidate_state": self.candidate_state,
            "candidate_elapsed": round(float(candidate_elapsed), 3),
            "reason": reason,
            "timestamp": now,
        }

    @staticmethod
    def _normalize(state_code: str) -> str:
        state_code = str(state_code or "unknown")
        return state_code if state_code in VALID_STATES else "unknown"


__all__ = ["UserStateSmoother", "ENTER_SECONDS", "VALID_STATES"]
