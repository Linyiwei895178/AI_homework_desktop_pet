"""
Lightweight user profile memory for personalization and care signals.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


DEFAULT_PROFILE_PATH = Path(__file__).resolve().parents[2] / "data" / "user_profile.json"


class UserProfile:
    """Small mutable profile that can be fed into prompt construction."""

    def __init__(
        self,
        nickname: str = "",
        tone: str = "",
        catchphrase: str = "",
        relationship: str = "陪伴伙伴",
        comfort_level: int = 50,
        recent_emotions: list[dict[str, Any]] | None = None,
        activity_stats: dict[str, Any] | None = None,
        updated_at: float | None = None,
    ) -> None:
        self.nickname = str(nickname or "").strip()
        self.tone = str(tone or "").strip()
        self.catchphrase = str(catchphrase or "").strip()
        self.relationship = str(relationship or "陪伴伙伴").strip()
        self.comfort_level = _clamp_int(comfort_level, 0, 100)
        self.recent_emotions = list(recent_emotions or [])
        self.activity_stats = dict(activity_stats or {})
        self.updated_at = float(updated_at or time.time())

    def update_from_chat_emotion(self, emotion_result: dict[str, Any]) -> None:
        """Update profile counters and comfort level from one emotion result."""
        result = _extract_emotion_result(emotion_result)
        label = str(result.get("emotion_label") or "neutral").strip() or "neutral"
        confidence = _float(result.get("confidence"), 0.0)
        need_care = bool(result.get("need_care"))

        self.recent_emotions.append(
            {
                "emotion_label": label,
                "confidence": round(confidence, 2),
                "need_care": need_care,
                "timestamp": time.time(),
            }
        )
        self.recent_emotions = self.recent_emotions[-12:]

        counts = self.activity_stats.setdefault("emotion_counts", {})
        counts[label] = int(counts.get(label, 0)) + 1
        self.activity_stats["chat_count"] = int(self.activity_stats.get("chat_count", 0)) + 1
        if need_care:
            self.activity_stats["care_needed_count"] = int(self.activity_stats.get("care_needed_count", 0)) + 1

        delta = {
            "positive": 3,
            "neutral": 1,
            "stress": -3,
            "sad": -4,
            "angry": -4,
            "tired": -2,
            "confused": -1,
        }.get(label, 0)
        self.comfort_level = _clamp_int(round(self.comfort_level + delta), 0, 100)
        self.updated_at = time.time()

    def to_prompt_context(self) -> dict[str, Any]:
        """Return a compact dict for prompt_builder without persistence details."""
        return {
            "nickname": self.nickname,
            "tone": self.tone,
            "catchphrase": self.catchphrase,
            "relationship": self.relationship,
            "comfort_level": self.comfort_level,
            "recent_emotions": list(self.recent_emotions[-6:]),
            "activity_stats": dict(self.activity_stats),
        }

    def to_dict(self) -> dict[str, Any]:
        data = self.to_prompt_context()
        data["updated_at"] = self.updated_at
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "UserProfile":
        raw = data if isinstance(data, dict) else {}
        return cls(
            nickname=raw.get("nickname", ""),
            tone=raw.get("tone", ""),
            catchphrase=raw.get("catchphrase", ""),
            relationship=raw.get("relationship", "陪伴伙伴"),
            comfort_level=raw.get("comfort_level", 50),
            recent_emotions=raw.get("recent_emotions") if isinstance(raw.get("recent_emotions"), list) else [],
            activity_stats=raw.get("activity_stats") if isinstance(raw.get("activity_stats"), dict) else {},
            updated_at=raw.get("updated_at"),
        )

    @classmethod
    def load(cls, filepath: str | Path = DEFAULT_PROFILE_PATH) -> "UserProfile":
        path = Path(filepath)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            return cls()
        return cls.from_dict(data if isinstance(data, dict) else {})

    def save(self, filepath: str | Path = DEFAULT_PROFILE_PATH) -> None:
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def load_user_profile(filepath: str | Path = DEFAULT_PROFILE_PATH) -> UserProfile:
    return UserProfile.load(filepath)


def _extract_emotion_result(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    nested = value.get("emotion_result")
    if isinstance(nested, dict):
        return nested
    return value


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp_int(value: Any, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = minimum
    return max(minimum, min(maximum, number))
