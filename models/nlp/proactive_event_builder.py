"""
Builders for Team C proactive speech events.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any


def build_screen_time_event(
    minutes: int | float,
    activity_code: str = "",
    activity_name: str = "",
    is_focused: bool = False,
    low_light: bool = False,
    personalization_settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "event_type": "screen_time_reminder",
        "minutes": round(float(minutes or 0), 1),
        "activity_code": str(activity_code or ""),
        "activity_name": str(activity_name or ""),
        "is_focused": bool(is_focused),
        "low_light": bool(low_light),
        "need_response": True,
        "personalization_settings": personalization_settings or {},
    }


def build_chat_emotion_event(
    emotion_result: dict[str, Any],
    personalization_settings: dict[str, Any] | None = None,
    user_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "event_type": "chat_emotion_alert",
        "emotion_result": dict(emotion_result or {}),
        "need_response": bool((emotion_result or {}).get("need_care")),
        "personalization_settings": personalization_settings or {},
        "user_profile": user_profile or {},
    }


def build_gesture_event(
    gesture_type: str,
    confidence: float = 0.0,
    duration: float = 0.0,
    personalization_settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "event_type": "gesture_event",
        "gesture_type": str(gesture_type or "unknown"),
        "confidence": round(float(confidence or 0.0), 2),
        "duration": round(float(duration or 0.0), 1),
        "need_response": True,
        "personalization_settings": personalization_settings or {},
    }


def build_cloud_pet_event(cloud_event: Any) -> dict[str, Any]:
    data = _as_dict(cloud_event)
    return {
        "event_type": "cloud_pet_event",
        "actor_name": data.get("actor_name") or data.get("actor") or "队友",
        "action_type": data.get("action_type") or data.get("action") or "update",
        "pet_name": data.get("pet_name") or data.get("pet") or "小宠物",
        "level": data.get("level"),
        "exp_gain": data.get("exp_gain", data.get("exp")),
        "coins_gain": data.get("coins_gain", data.get("coins")),
        "bond_bonus": data.get("bond_bonus", data.get("bond")),
        "need_response": True,
        "personalization_settings": data.get("personalization_settings") or {},
        "user_profile": data.get("user_profile") or {},
    }


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if is_dataclass(value):
        return asdict(value)
    raw: dict[str, Any] = {}
    for key in ("actor_name", "action_type", "pet_name", "level", "exp_gain", "coins_gain", "bond_bonus"):
        if hasattr(value, key):
            raw[key] = getattr(value, key)
    return raw
