"""
Demo-mode utilities: mock user states, mock cloud events, mock gesture events.

Used when DESKTOP_PET_MOCK_USER_STATE=true or DESKTOP_PET_MOCK_CLOUD=true.
"""

from __future__ import annotations

import random
import time
from typing import Any, Dict, Optional

from models.vision.user_state_detector import (
    STATE_NAME_MAP,
    STATE_NORMAL,
    STATE_FOCUSED,
    STATE_DISTRACTED,
    STATE_TIRED,
    STATE_AWAY,
    STATE_RETURN,
    STATE_STUDY_LONG,
    STATE_LOW_LIGHT,
    STATE_UNKNOWN,
)


DEFAULT_MOCK_USER_STATE_CYCLE = [
    STATE_NORMAL,
    STATE_FOCUSED,
    STATE_DISTRACTED,
    STATE_TIRED,
    STATE_AWAY,
    STATE_RETURN,
    STATE_LOW_LIGHT,
    STATE_STUDY_LONG,
]

MOCK_USER_STATE_TEMPLATES: Dict[str, Dict[str, Any]] = {
    STATE_NORMAL: {
        "description": "模拟状态：用户姿态正常，正在电脑前自然使用设备。",
        "tags": ["正常", "mock"],
        "confidence": 0.92,
        "need_response": False,
        "suggestion": "保持普通陪伴即可，不需要主动说话。",
    },
    STATE_FOCUSED: {
        "description": "模拟状态：用户正在专注学习或工作，视线稳定。",
        "tags": ["专注", "学习", "mock"],
        "confidence": 0.9,
        "need_response": False,
        "suggestion": "保持安静陪伴，不要打断用户思路。",
    },
    STATE_DISTRACTED: {
        "description": "模拟状态：用户注意力有些分散，疑似偏离当前任务。",
        "tags": ["分心", "提醒", "mock"],
        "confidence": 0.84,
        "need_response": True,
        "suggestion": "用轻松、不责备的方式提醒用户回到当前任务。",
    },
    STATE_TIRED: {
        "description": "模拟状态：用户看起来有些疲劳，可能需要短暂休息。",
        "tags": ["疲劳", "休息", "mock"],
        "confidence": 0.86,
        "need_response": True,
        "suggestion": "用温柔关心的语气提醒用户休息眼睛或喝水。",
    },
    STATE_AWAY: {
        "description": "模拟状态：用户暂时离开座位。",
        "tags": ["离开", "无人", "mock"],
        "confidence": 0.88,
        "need_response": False,
        "suggestion": "桌宠进入等待状态，不要频繁说话。",
    },
    STATE_RETURN: {
        "description": "模拟状态：用户刚刚回到座位。",
        "tags": ["返回", "欢迎", "mock"],
        "confidence": 0.87,
        "need_response": True,
        "suggestion": "用开心、简短的方式欢迎用户回来。",
    },
    STATE_LOW_LIGHT: {
        "description": "模拟状态：当前环境光线偏暗。",
        "tags": ["低光照", "用眼提醒", "mock"],
        "confidence": 0.85,
        "need_response": True,
        "suggestion": "提醒用户开灯或调整光线，保护眼睛。",
    },
    STATE_STUDY_LONG: {
        "description": "模拟状态：用户已经连续学习或工作较长时间。",
        "tags": ["长时间学习", "久坐", "mock"],
        "confidence": 0.83,
        "need_response": True,
        "suggestion": "提醒用户休息眼睛、起身活动一下。",
    },
}


class MockUserStateProvider:
    """Provider that returns UserStateDetector-compatible mock user states."""

    def __init__(
        self,
        cycle_seconds: float = 10.0,
        states: Optional[list[str]] = None,
        now_func=time.time,
    ):
        self.cycle_seconds = max(1.0, float(cycle_seconds))
        self.states = [
            state for state in (states or DEFAULT_MOCK_USER_STATE_CYCLE)
            if state in MOCK_USER_STATE_TEMPLATES
        ] or list(DEFAULT_MOCK_USER_STATE_CYCLE)
        self._now_func = now_func
        self._last_state_code: Optional[str] = None
        self._state_since = float(self._now_func())

    def get_state(self) -> Dict[str, Any]:
        now = float(self._now_func())
        idx = int(now / self.cycle_seconds) % len(self.states)
        state_code = self.states[idx]

        if state_code != self._last_state_code:
            self._last_state_code = state_code
            self._state_since = now

        template = MOCK_USER_STATE_TEMPLATES.get(state_code, MOCK_USER_STATE_TEMPLATES[STATE_NORMAL])
        return {
            "state_code": state_code,
            "state_name": STATE_NAME_MAP.get(state_code, STATE_NAME_MAP[STATE_UNKNOWN]),
            "description": str(template["description"]),
            "tags": list(template["tags"]),
            "confidence": float(template["confidence"]),
            "duration": round(max(0.0, now - self._state_since), 2),
            "need_response": bool(template["need_response"]),
            "suggestion": str(template["suggestion"]),
            "source": ["mock", "demo_mode"],
        }


_DEFAULT_MOCK_USER_STATE_PROVIDER = MockUserStateProvider()


def get_mock_user_state() -> Dict[str, Any]:
    """Return a mock state with exactly the same fields as UserStateDetector.get_state()."""
    return _DEFAULT_MOCK_USER_STATE_PROVIDER.get_state()


def mock_user_state(
    cycle_seconds: float = 10.0,
    custom_states: Optional[list[str]] = None,
) -> Dict[str, Any]:
    """
    Generate a mock user state that cycles through states over time.

    :param cycle_seconds: duration (seconds) before the state changes
    :param custom_states: optional list of state codes to cycle through;
                          defaults to normal/focused/distracted/tired/away/
                          return/low_light/study_long
    :returns: user_state dict compatible with api_apply_user_state
    """
    provider = MockUserStateProvider(cycle_seconds=cycle_seconds, states=custom_states)
    return provider.get_state()


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
