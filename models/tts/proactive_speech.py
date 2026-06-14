"""
Cooldown and fallback replies for Team C proactive speech.
"""

from __future__ import annotations

import time
from typing import Any


PROACTIVE_COOLDOWNS_SECONDS = {
    "gesture_event": 3.0,
    "user_state_alert": 120.0,
    "screen_time_reminder": 300.0,
    "computer_activity_comment": 120.0,
    "pet_state_event": 240.0,
    "cloud_room_event": 45.0,
    "cloud_pet_event": 45.0,
}

CHAT_EVENT_TYPES = {"user_chat", "chat_reply", "chat_finished"}


class ProactiveSpeechPolicy:
    """Small stateful guard that keeps proactive TTS from spamming the user."""

    def __init__(self, cooldowns: dict[str, float] | None = None):
        self.cooldowns = dict(PROACTIVE_COOLDOWNS_SECONDS)
        if cooldowns:
            self.cooldowns.update({str(k): max(0.0, float(v)) for k, v in cooldowns.items()})
        self._last_event_at: dict[str, float] = {}
        self._last_text_at: dict[str, float] = {}

    def should_speak(
        self,
        event_data: dict[str, Any],
        *,
        user_chat_active: bool = False,
        now: float | None = None,
    ) -> bool:
        event_type = _event_type(event_data)
        if not event_type or event_type in CHAT_EVENT_TYPES:
            return True
        if user_chat_active:
            return False

        current = time.time() if now is None else float(now)
        key = self.event_key(event_data)
        cooldown = self.cooldowns.get(event_type, 180.0)
        if current - self._last_event_at.get(key, 0.0) < cooldown:
            return False
        return True

    def mark_spoken(
        self,
        event_data: dict[str, Any],
        text: str,
        *,
        now: float | None = None,
    ) -> None:
        current = time.time() if now is None else float(now)
        self._last_event_at[self.event_key(event_data)] = current
        normalized = _normalize_text(text)
        if normalized:
            self._last_text_at[normalized] = current

    def should_repeat_text(self, text: str, *, within_seconds: float = 180.0, now: float | None = None) -> bool:
        normalized = _normalize_text(text)
        if not normalized:
            return False
        current = time.time() if now is None else float(now)
        return current - self._last_text_at.get(normalized, 0.0) < max(0.0, within_seconds)

    @staticmethod
    def event_key(event_data: dict[str, Any]) -> str:
        event_type = _event_type(event_data) or "status_event"
        if event_type == "gesture_event":
            return f"{event_type}:{event_data.get('gesture_type') or 'unknown'}"
        if event_type == "user_state_alert":
            return f"{event_type}:{event_data.get('state_code') or event_data.get('state') or 'unknown'}"
        if event_type == "screen_time_reminder":
            return f"{event_type}:{event_data.get('activity_code') or event_data.get('activity_name') or 'computer'}"
        if event_type in {"cloud_room_event", "cloud_pet_event"}:
            return f"{event_type}:{event_data.get('action_type') or event_data.get('action') or 'update'}"
        if event_type == "pet_state_event":
            return f"{event_type}:{event_data.get('state') or event_data.get('state_code') or event_data.get('mood') or 'pet'}"
        return event_type


def build_local_event_reply(event_data: dict[str, Any]) -> str:
    """Return one short TTS-friendly sentence for supported proactive events."""
    event_type = _event_type(event_data)
    if event_type == "gesture_event":
        gesture = str(event_data.get("gesture_type") or "").strip().lower()
        return {
            "wave": "看到你挥手啦，我也在这儿。",
            "ok": "收到 OK，状态很好。",
            "thumbs_up": "这个点赞我收下啦。",
            "heart": "比心收到，心情加一。",
            "raised_hand": "举手收到，有事叫我。",
            "stretch": "伸展一下很好，肩膀也放松点。",
        }.get(gesture, "我看到你的手势啦。")

    if event_type == "user_state_alert":
        state = str(event_data.get("state_code") or event_data.get("state") or "").strip().lower()
        return {
            "focused": "你在专注，我小声陪着。",
            "distracted": "先别急，挑一件小事做完就好。",
            "tired": "看起来有点累，歇半分钟也算前进。",
            "away": "我先安静等你回来。",
            "return": "欢迎回来，刚好继续。",
            "study_long": "学很久啦，抬头看看远处吧。",
            "low_light": "光线有点暗，调亮一点更护眼。",
        }.get(state, "我在这儿，慢慢来。")

    if event_type == "screen_time_reminder":
        minutes = event_data.get("minutes")
        try:
            minutes_text = str(int(float(minutes)))
        except (TypeError, ValueError):
            minutes_text = ""
        if bool(event_data.get("low_light")):
            return "光线偏暗，调亮一点再继续吧。"
        if minutes_text:
            return f"已经连续看屏幕 {minutes_text} 分钟啦，休息一下眼睛吧。"
        return "看屏幕有一会儿了，眨眨眼放松下。"

    if event_type == "computer_activity_comment":
        activity = str(event_data.get("activity_code") or "").strip().lower()
        return {
            "coding": "代码先稳住，别忘了喝口水。",
            "working": "工作节奏不错，记得留点缓冲。",
            "gaming": "打得开心，但别忘了休息眼睛。",
            "watching": "我陪你看一会儿，不剧透。",
            "chatting": "你先聊，我不插话。",
        }.get(activity, "我小声提醒一下，别坐太久。")

    if event_type in {"cloud_room_event", "cloud_pet_event"}:
        actor = str(event_data.get("actor_name") or event_data.get("actor") or "队友").strip()
        action = str(event_data.get("action_type") or event_data.get("action") or "update").strip().lower()
        return {
            "feed": f"{actor}刚刚喂了宠物，状态更新啦。",
            "play": f"{actor}陪宠物玩了一会儿。",
            "level_up": "宠物升级啦，干得漂亮。",
            "join": f"{actor}加入房间啦。",
            "leave": f"{actor}暂时离开房间。",
        }.get(action, "云端共养状态已同步。")

    if event_type == "pet_state_event":
        state = str(event_data.get("state") or event_data.get("state_code") or event_data.get("mood") or "").lower()
        if "hungry" in state:
            return "有点饿啦，等会儿喂我一口吧。"
        if "tired" in state:
            return "我有点困，慢慢陪你就好。"
        if "happy" in state:
            return "现在心情不错，继续保持。"
        return "宠物状态有变化，我记下啦。"

    return "我在这儿，轻轻提醒一下。"


def _event_type(event_data: dict[str, Any]) -> str:
    if not isinstance(event_data, dict):
        return ""
    return str(event_data.get("event_type") or event_data.get("event") or "").strip()


def _normalize_text(text: str) -> str:
    return " ".join(str(text or "").strip().split())
