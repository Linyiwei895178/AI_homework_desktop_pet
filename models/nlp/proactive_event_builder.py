"""
ProactiveEventBuilder: converts external events into prompt-friendly dicts.

Builds events for screen_time_reminder, cloud_pet_event, gesture_event,
and chat_emotion_alert that can be fed into prompt_builder.build_proactive_prompt.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional


def build_screen_time_event(
    daily_minutes: float,
    activity_code: str = "working",
    app_name: str = "",
) -> Dict[str, Any]:
    """
    Build a screen-time reminder event for the prompt builder.

    :param daily_minutes: total screen time today (minutes)
    :param activity_code: current activity code
    :param app_name:      current foreground app name
    :returns: event dict with event_type="screen_time_reminder"
    """
    return {
        "event_type": "screen_time_reminder",
        "daily_minutes": daily_minutes,
        "activity_code": activity_code,
        "app_name": app_name,
        "suggestion": "用户使用电脑已经有一段时间了，请像朋友一样自然提醒休息。",
        "timestamp": time.time(),
    }


def build_cloud_pet_event(
    actor_name: str,
    action_type: str = "pet",
    message: str = "",
    delta: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Build a cloud pet interaction event for the prompt builder.

    :param actor_name:  who interacted with the pet
    :param action_type: e.g. "feed", "play", "pet", "wave"
    :param message:     optional message from the remote user
    :param delta:       state changes dict
    :returns: event dict with event_type="cloud_pet_event"
    """
    return {
        "event_type": "cloud_pet_event",
        "actor": actor_name,
        "action_type": action_type,
        "message": message or f"{actor_name} 和你的桌宠互动了一下！",
        "delta": delta or {},
        "timestamp": time.time(),
    }


def build_gesture_event(
    gesture: str,
    confidence: float = 0.0,
) -> Dict[str, Any]:
    """
    Build a gesture recognition event for the prompt builder.

    :param gesture:    recognized gesture name (e.g. "wave", "thumbs_up")
    :param confidence: recognition confidence (0-1)
    :returns: event dict with event_type="gesture_event"
    """
    gesture_descriptions = {
        "wave": "用户挥手",
        "thumbs_up": "用户点赞",
        "peace": "用户比耶",
        "point": "用户指向",
        "none": "无手势",
    }
    return {
        "event_type": "gesture_event",
        "gesture": gesture,
        "confidence": round(confidence, 2),
        "description": gesture_descriptions.get(gesture, f"检测到手势: {gesture}"),
        "timestamp": time.time(),
    }


def build_chat_emotion_alert(
    emotion_label: str,
    confidence: float,
    need_care: bool,
    suggestion: str,
) -> Dict[str, Any]:
    """
    Build a chat emotion alert event for the prompt builder.

    :param emotion_label: detected emotion (positive/neutral/stress/sad/etc.)
    :param confidence:    emotion analysis confidence
    :param need_care:     whether the user needs emotional care
    :param suggestion:    care suggestion text
    :returns: event dict with event_type="chat_emotion_alert"
    """
    return {
        "event_type": "chat_emotion_alert",
        "emotion": emotion_label,
        "confidence": round(confidence, 2),
        "need_care": need_care,
        "suggestion": suggestion,
        "timestamp": time.time(),
    }
