"""
UserProfile: user preference/behavior profile with JSON persistence.

Tracks:
- Display name and preferences.
- Emotion history snapshot from chat analysis.
- Activity history snapshot from vision.
- Settings for TTS/UI/notification preferences.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


_PROFILE_PATH = Path(__file__).resolve().parents[2] / "data" / "user_profile.json"


class UserProfile:
    """
    User preference and behavior profile.

    Usage:
        profile = UserProfile()
        profile.load()
        profile.update_from_chat_emotion({"emotion_label": "sad", "confidence": 0.8})
        profile.update_from_activity({"activity_code": "coding", "duration": 3600})
        profile.save()
        ctx = profile.to_prompt_context()
    """

    def __init__(self, filepath: Optional[str | Path] = None):
        self._path = Path(filepath or _PROFILE_PATH)
        self._data: Dict[str, Any] = {
            "display_name": "",
            "preferred_response_language": "zh-CN",
            "last_emotion": "neutral",
            "last_emotion_confidence": 0.0,
            "last_emotion_timestamp": 0.0,
            "recent_activities": [],
            "disturb_preference": "normal",  # "low" | "normal" | "high"
            "daily_interaction_count": 0,
            "daily_chat_count": 0,
            "last_active_date": "",
            "tts_enabled": True,
            "auto_reply_enabled": True,
            "created_at": "",
        }

    def load(self) -> "UserProfile":
        """Load profile from JSON file. Returns self."""
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._data.update(data)
            except (json.JSONDecodeError, OSError) as exc:
                print(f"[UserProfile] Load error: {exc}")
        return self

    def save(self) -> bool:
        """Save profile to JSON file. Returns True on success."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            return True
        except OSError as exc:
            print(f"[UserProfile] Save error: {exc}")
            return False

    def update_from_chat_emotion(self, emotion_result: Dict[str, Any]) -> None:
        """
        Update profile from chat emotion analysis result.

        :param emotion_result: output from emotion_analyzer.analyze_chat_emotion()
        """
        if not isinstance(emotion_result, dict):
            return
        label = emotion_result.get("emotion_label", "neutral")
        confidence = float(emotion_result.get("confidence", 0.0))
        self._data["last_emotion"] = label
        self._data["last_emotion_confidence"] = confidence
        self._data["last_emotion_timestamp"] = __import__("time").time()
        self._data["daily_chat_count"] = int(self._data.get("daily_chat_count", 0)) + 1

    def update_from_activity(self, activity_state: Dict[str, Any]) -> None:
        """
        Update profile from computer activity detection.

        :param activity_state: output from ComputerActivityDetector.get_state()
        """
        if not isinstance(activity_state, dict):
            return
        code = str(activity_state.get("activity_code", "") or "")
        if code:
            activities: list = self._data.setdefault("recent_activities", [])
            activities.append({
                "code": code,
                "timestamp": __import__("time").time(),
            })
            # Keep only last 20 entries
            if len(activities) > 20:
                self._data["recent_activities"] = activities[-20:]

    def update_from_settings(self, settings: Dict[str, Any]) -> None:
        """
        Update profile from UI settings.

        :param settings: UI personalization settings dict
        """
        if not isinstance(settings, dict):
            return
        for key in ("display_name", "preferred_response_language", "tts_enabled", "auto_reply_enabled", "disturb_preference"):
            if key in settings:
                self._data[key] = settings[key]

    def to_prompt_context(self) -> Dict[str, Any]:
        """
        Convert profile to a compact dict for prompt_builder.

        :returns: dict with user context info
        """
        return {
            "display_name": self._data.get("display_name", ""),
            "last_emotion": self._data.get("last_emotion", "neutral"),
            "disturb_preference": self._data.get("disturb_preference", "normal"),
            "daily_interaction_count": self._data.get("daily_interaction_count", 0),
        }

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    @property
    def data(self) -> Dict[str, Any]:
        return dict(self._data)
