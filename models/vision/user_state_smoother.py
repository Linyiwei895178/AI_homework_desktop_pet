"""State smoothing for Team B user-state perception."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any


ENTER_SECONDS = {
    "focused": 3.0,
    "distracted": 2.5,
    "tired": 1.5,
    "normal": 0.5,
    "away": 10.0,
    "low_light": 2.0,
    "return": 1.0,
}
EXIT_SECONDS = {
    "focused": 1.0,
    "distracted": 0.8,
    "tired": 0.8,
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
    enter_seconds: dict[str, float] = field(default_factory=lambda: _load_enter_seconds())
    exit_seconds: dict[str, float] = field(default_factory=lambda: _load_exit_seconds())
    debug_enabled: bool = field(
        default_factory=lambda: os.getenv("DESKTOP_PET_STATE_DEBUG", "false").strip().lower()
        in {"1", "true", "yes", "y", "on"}
    )
    _last_debug_log_at: float = 0.0

    def update(self, state_code: str, now: float | None = None) -> dict[str, Any]:
        """Update smoother and return current state metadata."""
        now = time.time() if now is None else float(now)
        input_state = self._normalize(state_code)
        before = self.current_state
        state_code = self._normalize(state_code)

        if state_code in IMMEDIATE_STATES:
            changed = self.current_state != state_code
            self.current_state = state_code
            self.candidate_state = None
            self.candidate_since = None
            result = self._result(changed, "immediate", now)
            self._debug_log(input_state, 0.0, result, "immediate")
            return result

        if state_code == self.current_state:
            self.candidate_state = None
            self.candidate_since = None
            result = self._result(False, "stable", now)
            self._debug_log(input_state, 0.0, result, "stable")
            return result

        if self.candidate_state != state_code:
            self.candidate_state = state_code
            self.candidate_since = now
            result = self._result(False, "candidate_started", now)
            self._debug_log(input_state, 0.0, result, "candidate_started")
            return result

        if self.candidate_since is None:
            self.candidate_since = now

        elapsed = max(0.0, now - self.candidate_since)
        required = self._required_seconds(state_code)
        if elapsed >= required:
            changed = self.current_state != state_code
            self.current_state = state_code
            self.candidate_state = None
            self.candidate_since = None
            result = self._result(changed, "changed", now, elapsed)
            self._debug_log(input_state, elapsed, result, f"changed_from_{before}")
            return result

        result = self._result(False, "waiting", now, elapsed)
        self._debug_log(input_state, elapsed, result, f"waiting_{elapsed:.2f}/{required:.2f}")
        return result

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

    def _required_seconds(self, target_state: str) -> float:
        if target_state == "normal" and self.current_state != "normal":
            return self.exit_seconds.get(self.current_state, self.enter_seconds.get("normal", 0.5))
        return self.enter_seconds.get(target_state, 1.0)

    def _debug_log(self, input_state: str, elapsed: float, result: dict[str, Any], action: str) -> None:
        if not self.debug_enabled:
            return
        now = float(result.get("timestamp", time.time()) or time.time())
        changed = bool(result.get("changed", False))
        if not changed and now - self._last_debug_log_at < 0.5:
            return
        self._last_debug_log_at = now
        print(
            "[UserStateSmootherDebug] "
            f"current={self.current_state}, candidate={self.candidate_state}, "
            f"input={input_state}, elapsed={elapsed:.2f}, action={action}"
        )

    @staticmethod
    def _normalize(state_code: str) -> str:
        state_code = str(state_code or "unknown")
        return state_code if state_code in VALID_STATES else "unknown"


def _load_enter_seconds() -> dict[str, float]:
    values = dict(ENTER_SECONDS)
    env_names = {
        "focused": "DESKTOP_PET_FOCUSED_ENTER_SECONDS",
        "distracted": "DESKTOP_PET_DISTRACTED_ENTER_SECONDS",
        "tired": "DESKTOP_PET_TIRED_ENTER_SECONDS",
        "normal": "DESKTOP_PET_NORMAL_ENTER_SECONDS",
        "away": "DESKTOP_PET_AWAY_ENTER_SECONDS",
        "low_light": "DESKTOP_PET_LOW_LIGHT_ENTER_SECONDS",
        "return": "DESKTOP_PET_RETURN_ENTER_SECONDS",
    }
    for state_code, env_name in env_names.items():
        raw = os.getenv(env_name)
        if raw is None:
            continue
        try:
            values[state_code] = max(0.0, float(raw))
        except Exception:
            pass
    return values


def _load_exit_seconds() -> dict[str, float]:
    values = dict(EXIT_SECONDS)
    env_names = {
        "focused": "DESKTOP_PET_FOCUSED_EXIT_SECONDS",
        "distracted": "DESKTOP_PET_DISTRACTED_EXIT_SECONDS",
        "tired": "DESKTOP_PET_TIRED_EXIT_SECONDS",
    }
    for state_code, env_name in env_names.items():
        raw = os.getenv(env_name)
        if raw is None:
            continue
        try:
            values[state_code] = max(0.0, float(raw))
        except Exception:
            pass
    return values


__all__ = ["UserStateSmoother", "ENTER_SECONDS", "EXIT_SECONDS", "VALID_STATES"]
