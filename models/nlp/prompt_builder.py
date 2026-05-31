"""
Prompt construction helpers for Team C.

This module converts Team B's user-state dictionary and Team D's pet-state
dictionary into compact natural-language context for the LLM.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional


STATE_STYLE_HINTS = {
    "normal": "用户状态正常，可以轻松陪伴。",
    "focused": "用户正在专注，回复要短，不打扰。",
    "distracted": "用户可能分心，用轻松、不责备的方式提醒。",
    "tired": "用户可能疲劳，先关心，再建议短暂休息。",
    "away": "用户暂时离开，保持等待感。",
    "return": "用户刚回来，可以温柔欢迎。",
    "study_long": "用户学习较久，提醒休息眼睛和活动身体。",
    "low_light": "环境偏暗，提醒调亮灯光保护眼睛。",
    "camera_error": "检测异常，不要假装看见用户。",
    "unknown": "状态不确定，正常回应即可。",
}

ACTIVITY_STYLE_HINTS = {
    "gaming": "用户正在打游戏。主动点评要像朋友在旁边陪玩，短、轻松、别指挥过度。",
    "watching": "用户正在看剧或视频。主动点评要像一起追剧，短、自然、不要剧透。",
    "browsing": "用户正在浏览网页。保持安静陪伴即可。",
    "chatting": "用户正在聊天。不要插话打扰。",
    "coding": "用户正在编程。回复要克制，不打断思路。",
    "working": "用户正在办公。保持低打扰。",
    "idle": "电脑前台空闲，可以轻松陪伴。",
    "unknown": "电脑状态不确定，正常回应即可。",
}


def build_system_prompt(current_state: Optional[Dict[str, Any]] = None) -> str:
    state_context = build_state_context(current_state)
    return (
        "你是桌面宠物 Echo，是一个亲切、活泼、声音甜一点的可爱女孩。"
        "你正在和用户进行自然中文对话。"
        "说话要适合被语音朗读，句子短一点，语气软一点。"
        "可以自然地用“呀、呢、啦、哦”等语气词，但不要每句都撒娇，也不要堆颜文字。"
        "回复要短，通常控制在 80 个中文字符以内；除非用户明确要求长回答。"
        "不要说自己是大模型，不要暴露接口或状态字段名。"
        "如果用户状态需要关心，先共情，再给一个很小的行动建议。"
        f"\n\n当前上下文：{state_context}"
    )


def build_state_context(current_state: Optional[Dict[str, Any]]) -> str:
    if not current_state or not isinstance(current_state, dict):
        return "暂无用户状态信息。"

    parts = []

    state_code = str(current_state.get("state_code", "") or "").strip()
    if state_code:
        state_name = str(current_state.get("state_name", "") or "").strip()
        label = f"{state_code}（{state_name}）" if state_name else state_code
        parts.append(f"用户状态：{label}")
        parts.append(STATE_STYLE_HINTS.get(state_code, STATE_STYLE_HINTS["unknown"]))

    description = str(current_state.get("description", "") or "").strip()
    if description:
        parts.append(f"观察描述：{description}")

    suggestion = str(current_state.get("suggestion", "") or "").strip()
    if suggestion:
        parts.append(f"建议回应方向：{suggestion}")

    confidence = current_state.get("confidence")
    if isinstance(confidence, (int, float)):
        parts.append(f"置信度：{confidence:.2f}")

    duration = current_state.get("duration")
    if isinstance(duration, (int, float)) and duration > 0:
        parts.append(f"持续时间：{duration:.1f} 秒")

    tags = _format_tags(current_state.get("tags"))
    if tags:
        parts.append(f"标签：{tags}")

    activity_code = str(current_state.get("activity_code", "") or "").strip()
    if activity_code:
        activity_name = str(current_state.get("activity_name", "") or "").strip()
        label = f"{activity_code}（{activity_name}）" if activity_name else activity_code
        parts.append(f"电脑状态：{label}")
        parts.append(ACTIVITY_STYLE_HINTS.get(activity_code, ACTIVITY_STYLE_HINTS["unknown"]))
        app_name = str(current_state.get("app_name", "") or "").strip()
        if app_name:
            parts.append(f"前台应用：{app_name}")
        window_title = str(current_state.get("window_title", "") or "").strip()
        if window_title:
            parts.append(f"前台标题：{window_title[:60]}")

    pet_bits = []
    for key, label in (
        ("pet_id", "桌宠"),
        ("mood", "心情"),
        ("energy", "能量"),
        ("intimacy", "亲密度"),
        ("action", "当前动作"),
    ):
        if key in current_state:
            pet_bits.append(f"{label}={current_state[key]}")
    if pet_bits:
        parts.append("桌宠状态：" + "，".join(pet_bits))

    return "；".join(parts) if parts else "暂无用户状态信息。"


def build_proactive_prompt(event_data: Dict[str, Any]) -> str:
    event_type = event_data.get("event_type") or event_data.get("event") or "status_event"
    if event_type == "user_state_alert":
        suggestion = str(event_data.get("suggestion", "") or "").strip()
        state_code = str(event_data.get("state_code", "unknown") or "unknown")
        if suggestion:
            return f"用户当前状态是 {state_code}。请按这个方向主动说一句话：{suggestion}"
        return f"用户当前状态是 {state_code}。请主动说一句温柔、简短的话。"

    if event_type == "chat_finished":
        return "刚刚对话结束，保持安静，不需要主动说话。"

    if event_type == "computer_activity_comment":
        activity_code = str(event_data.get("activity_code", "unknown") or "unknown")
        activity_name = str(event_data.get("activity_name", "") or "").strip()
        app_name = str(event_data.get("app_name", "") or "").strip()
        window_title = str(event_data.get("window_title", "") or "").strip()
        suggestion = str(event_data.get("suggestion", "") or "").strip()
        label = activity_name or activity_code
        details = []
        if app_name:
            details.append(f"前台应用是 {app_name}")
        if window_title:
            details.append(f"窗口标题是《{window_title[:50]}》")
        detail_text = "，".join(details)
        base = f"用户电脑状态是 {label}"
        if detail_text:
            base += f"，{detail_text}"
        if suggestion:
            return f"{base}。{suggestion} 请只说一句，像朋友在旁边小声点评。"
        return f"{base}。请只说一句，像朋友在旁边小声点评。"

    return "根据当前状态，主动说一句简短自然的话。"


def _format_tags(tags: Any) -> str:
    if isinstance(tags, str):
        return tags
    if not isinstance(tags, Iterable):
        return ""
    result = []
    for item in tags:
        text = str(item).strip()
        if text and text not in result:
            result.append(text)
    return "、".join(result[:6])
