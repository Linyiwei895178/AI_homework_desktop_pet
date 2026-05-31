"""
Prompt construction helpers for Team C.

This module converts Team B's user-state dictionary and Team D's pet-state
dictionary into compact natural-language context for the LLM.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional


RESPONSE_LANGUAGE_NAMES = {
    "zh-CN": "Chinese",
    "zh-HK": "Cantonese / Traditional Chinese",
    "zh-TW": "Taiwan Mandarin / Traditional Chinese",
    "en-US": "English",
    "en-GB": "British English",
    "fr-FR": "French",
    "de-DE": "German",
    "es-ES": "Spanish",
    "es-MX": "Mexican Spanish",
    "it-IT": "Italian",
    "pt-BR": "Brazilian Portuguese",
    "ru-RU": "Russian",
    "nl-NL": "Dutch",
    "hi-IN": "Hindi",
    "ar-EG": "Arabic",
    "ja-JP": "Japanese",
    "ko-KR": "Korean",
}


def normalize_response_language(language: Any) -> str:
    value = str(language or "").strip()
    if not value:
        return ""
    key = value.replace("_", "-").lower()
    canonical = {locale.lower(): locale for locale in RESPONSE_LANGUAGE_NAMES}
    if key in canonical:
        return canonical[key]
    aliases = {
        "cn": "zh-CN",
        "zh": "zh-CN",
        "zh-cn": "zh-CN",
        "chinese": "zh-CN",
        "中文": "zh-CN",
        "mandarin": "zh-CN",
        "zh-hk": "zh-HK",
        "zh-tw": "zh-TW",
        "yue": "zh-HK",
        "cantonese": "zh-HK",
        "粤语": "zh-HK",
        "粵語": "zh-HK",
        "en": "en-US",
        "en-us": "en-US",
        "en-gb": "en-GB",
        "english": "en-US",
        "british english": "en-GB",
        "英文": "en-US",
        "英语": "en-US",
        "英式英语": "en-GB",
        "英音": "en-GB",
        "fr": "fr-FR",
        "fr-fr": "fr-FR",
        "french": "fr-FR",
        "法语": "fr-FR",
        "法文": "fr-FR",
        "de": "de-DE",
        "de-de": "de-DE",
        "german": "de-DE",
        "德语": "de-DE",
        "德文": "de-DE",
        "es": "es-ES",
        "es-es": "es-ES",
        "es-mx": "es-MX",
        "spanish": "es-ES",
        "西班牙语": "es-ES",
        "西语": "es-ES",
        "it": "it-IT",
        "it-it": "it-IT",
        "italian": "it-IT",
        "意大利语": "it-IT",
        "pt": "pt-BR",
        "pt-br": "pt-BR",
        "portuguese": "pt-BR",
        "葡萄牙语": "pt-BR",
        "ru": "ru-RU",
        "ru-ru": "ru-RU",
        "russian": "ru-RU",
        "俄语": "ru-RU",
        "nl": "nl-NL",
        "nl-nl": "nl-NL",
        "dutch": "nl-NL",
        "荷兰语": "nl-NL",
        "hi": "hi-IN",
        "hi-in": "hi-IN",
        "hindi": "hi-IN",
        "印地语": "hi-IN",
        "ar": "ar-EG",
        "ar-eg": "ar-EG",
        "arabic": "ar-EG",
        "阿拉伯语": "ar-EG",
        "ja": "ja-JP",
        "jp": "ja-JP",
        "ja-jp": "ja-JP",
        "japanese": "ja-JP",
        "日语": "ja-JP",
        "日文": "ja-JP",
        "ko": "ko-KR",
        "kr": "ko-KR",
        "ko-kr": "ko-KR",
        "korean": "ko-KR",
        "韩语": "ko-KR",
        "韩文": "ko-KR",
    }
    if key in aliases:
        return aliases[key]
    if key.startswith("en"):
        return "en-GB" if key.startswith("en-gb") else "en-US"
    if key.startswith("fr"):
        return "fr-FR"
    if key.startswith("de"):
        return "de-DE"
    if key.startswith("es-mx"):
        return "es-MX"
    if key.startswith("es"):
        return "es-ES"
    if key.startswith("it"):
        return "it-IT"
    if key.startswith("pt"):
        return "pt-BR"
    if key.startswith("ru"):
        return "ru-RU"
    if key.startswith("nl"):
        return "nl-NL"
    if key.startswith("hi"):
        return "hi-IN"
    if key.startswith("ar"):
        return "ar-EG"
    if key.startswith("ja"):
        return "ja-JP"
    if key.startswith("ko"):
        return "ko-KR"
    if key.startswith("zh-hk") or key.startswith("zh-tw"):
        return "zh-TW" if key.startswith("zh-tw") else "zh-HK"
    if key.startswith("zh"):
        return "zh-CN"
    return ""


def response_language_from_edge_voice(edge_voice: Any) -> str:
    value = str(edge_voice or "").strip()
    if not value:
        return ""
    lowered = value.lower()
    for locale in RESPONSE_LANGUAGE_NAMES:
        if locale.lower() in lowered:
            return locale
    parts = value.split("-")
    if len(parts) >= 2:
        return normalize_response_language(f"{parts[0]}-{parts[1]}")
    return normalize_response_language(value)


def _response_language_from_state(current_state: Optional[Dict[str, Any]]) -> str:
    if not isinstance(current_state, dict):
        return ""
    for key in ("response_language", "reply_language", "language", "lang"):
        language = normalize_response_language(current_state.get(key))
        if language:
            return language
    tts_settings = current_state.get("tts_settings")
    if isinstance(tts_settings, dict):
        language = normalize_response_language(tts_settings.get("response_language") or tts_settings.get("language"))
        if language:
            return language
        language = response_language_from_edge_voice(tts_settings.get("edge_voice"))
        if language:
            return language
    return response_language_from_edge_voice(current_state.get("edge_voice"))


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


def build_system_prompt(
    current_state: Optional[Dict[str, Any]] = None,
    response_language: Any = None,
) -> str:
    state_context = build_state_context(current_state)
    language = (
        normalize_response_language(response_language)
        or _response_language_from_state(current_state)
        or "zh-CN"
    )
    if language == "zh-HK":
        return (
            "你是桌面宠物 Echo，是一个亲切、活泼、声音甜一点的可爱女孩。"
            "请优先用自然粤语/繁体中文和用户对话，除非用户明确要求其他语言。"
            "说话要适合被语音朗读，句子短一点，语气软一点。"
            "回复要短；不要说自己是大模型，不要暴露接口或状态字段名。"
            "如果用户状态需要关心，先共情，再给一个很小的行动建议。"
            f"\n\n当前上下文：{state_context}"
        )
    if language == "zh-TW":
        return (
            "你是桌面宠物 Echo，是一个亲切、活泼、声音甜一点的可爱女孩。"
            "请优先用自然繁体中文和用户对话，除非用户明确要求其他语言。"
            "说话要适合被语音朗读，句子短一点，语气软一点。"
            "回复要短；不要说自己是大模型，不要暴露接口或状态字段名。"
            "如果用户状态需要关心，先共情，再给一个很小的行动建议。"
            f"\n\n当前上下文：{state_context}"
        )
    if language != "zh-CN":
        language_name = RESPONSE_LANGUAGE_NAMES.get(language, "the selected language")
        return (
            f"You are Echo, a friendly, lively desktop pet with a slightly sweet voice. "
            f"You are having a natural {language_name} conversation with the user. "
            f"Always answer in natural {language_name} unless the user explicitly asks for another language. "
            "Make replies suitable for spoken TTS: short sentences, warm tone, no dense formatting. "
            "Keep replies brief unless the user clearly asks for more. "
            "Do not say you are a large language model, and do not expose API or state field names. "
            "If the user's state needs care, empathize first, then offer one tiny next step. "
            f"\n\nCurrent context: {state_context}"
        )
    return (
        "你是桌面宠物 Echo，是一个亲切、活泼、声音甜一点的可爱女孩。"
        "你正在和用户进行自然中文对话。"
        "除非用户明确要求其他语言，否则始终用中文回复。"
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
