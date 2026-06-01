"""
Demo-mode utilities: mock user states, mock cloud events, mock gesture events.

Used when DESKTOP_PET_MOCK_USER_STATE=true or DESKTOP_PET_MOCK_CLOUD=true.
"""

from __future__ import annotations

import random
import time
from typing import Any, Dict, Optional

from models.vision.user_state_detector import (
    STATE_NORMAL,
    STATE_FOCUSED,
    STATE_DISTRACTED,
    STATE_TIRED,
    STATE_AWAY,
    STATE_RETURN,
)


def mock_user_state(
    cycle_seconds: float = 10.0,
    custom_states: Optional[list[str]] = None,
) -> Dict[str, Any]:
    """
    Generate a mock user state that cycles through states over time.

    :param cycle_seconds: duration (seconds) before the state changes
    :param custom_states: optional list of state codes to cycle through;
                          defaults to [normal, focused, distracted, tired, return]
    :returns: user_state dict compatible with api_apply_user_state
    """
    states = custom_states or [
        STATE_NORMAL,
        STATE_FOCUSED,
        STATE_DISTRACTED,
        STATE_TIRED,
        STATE_RETURN,
    ]
    idx = int(time.time() / cycle_seconds) % len(states)
    state_code = states[idx]

    state_names = {
        STATE_NORMAL: "正常状态",
        STATE_FOCUSED: "专注学习",
        STATE_DISTRACTED: "疑似分心",
        STATE_TIRED: "疑似疲劳",
        STATE_AWAY: "暂时离开",
        STATE_RETURN: "回到座位",
    }

    need_response = state_code in (STATE_DISTRACTED, STATE_TIRED)

    suggestions = {
        STATE_NORMAL: "用户状态正常，可以轻松陪伴。",
        STATE_FOCUSED: "用户正在专注，保持安静陪伴。",
        STATE_DISTRACTED: "用户可能分心了，用轻松的方式提醒回到状态。",
        STATE_TIRED: "用户看起来很疲惫，先关心一下。",
        STATE_RETURN: "用户刚回来，可以温柔欢迎一下。",
    }

    return {
        "state_code": state_code,
        "state_name": state_names.get(state_code, "未知"),
        "description": f"模拟状态: {state_code}",
        "tags": [state_code, "mock"],
        "confidence": round(random.uniform(0.75, 0.95), 2),
        "duration": round(random.uniform(5.0, 15.0), 1),
        "need_response": need_response,
        "suggestion": suggestions.get(state_code, "根据当前状态做出合适的回应。"),
        "source": ["mock"],
    }


def mock_cloud_event(
    event_type: str = "cloud_pet_event",
    actor_name: str = "CloudFriend",
) -> Dict[str, Any]:
    """
    Generate a mock cloud pet interaction event.

    :param event_type: event type string
    :param actor_name: pretend remote user name
    :returns: cloud event dict
    """
    actions = ["pet", "feed", "play", "wave", "poke"]
    return {
        "event_type": event_type,
        "actor": actor_name,
        "action": random.choice(actions),
        "timestamp": time.time(),
        "payload": {
            "message": f"{actor_name} 摸了摸你的桌宠！",
            "delta_mood": random.choice([1, 2, -1]),
            "delta_energy": random.choice([0, 5, 10]),
            "delta_intimacy": random.choice([1, 2, 3]),
        },
        "is_mock": True,
    }


def mock_gesture_event() -> Dict[str, Any]:
    """
    Generate a mock gesture recognition event.

    :returns: gesture event dict
    """
    gestures = ["wave", "thumbs_up", "peace", "point", "none"]
    gesture = random.choice(gestures)
    return {
        "event_type": "gesture_event",
        "gesture": gesture,
        "confidence": round(random.uniform(0.6, 0.95), 2),
        "timestamp": time.time(),
        "is_mock": True,
        "description": {
            "wave": "用户挥手",
            "thumbs_up": "用户点赞",
            "peace": "用户比耶",
            "point": "用户指向",
            "none": "无手势",
        }.get(gesture, "未知手势"),
    }


def mock_screen_time_reminder(daily_minutes: float = 180.0) -> Dict[str, Any]:
    """
    Generate a mock screen-time reminder event.

    :param daily_minutes: pretend daily screen time in minutes
    :returns: screen_time_reminder event dict
    """
    return {
        "event_type": "screen_time_reminder",
        "daily_minutes": daily_minutes,
        "suggestion": "今天已经使用电脑一段时间了，建议站起来活动一下。",
        "timestamp": time.time(),
        "is_mock": True,
    }
