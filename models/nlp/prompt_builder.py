"""
Prompt construction helpers for Team C.

This module turns user state, pet state, and personalization settings into a
compact prompt for the chat model. The prompt intentionally favours natural
conversation over mirroring the user's words back at them.
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
        "chinese": "zh-CN",
        "mandarin": "zh-CN",
        "yue": "zh-HK",
        "cantonese": "zh-HK",
        "tw": "zh-TW",
        "traditional chinese": "zh-TW",
        "en": "en-US",
        "english": "en-US",
        "british english": "en-GB",
        "fr": "fr-FR",
        "french": "fr-FR",
        "de": "de-DE",
        "german": "de-DE",
        "es": "es-ES",
        "spanish": "es-ES",
        "it": "it-IT",
        "italian": "it-IT",
        "pt": "pt-BR",
        "portuguese": "pt-BR",
        "ru": "ru-RU",
        "russian": "ru-RU",
        "nl": "nl-NL",
        "dutch": "nl-NL",
        "hi": "hi-IN",
        "hindi": "hi-IN",
        "ar": "ar-EG",
        "arabic": "ar-EG",
        "ja": "ja-JP",
        "jp": "ja-JP",
        "japanese": "ja-JP",
        "ko": "ko-KR",
        "kr": "ko-KR",
        "korean": "ko-KR",
    }
    if key in aliases:
        return aliases[key]
    if key.startswith("zh-hk"):
        return "zh-HK"
    if key.startswith("zh-tw"):
        return "zh-TW"
    if key.startswith("zh"):
        return "zh-CN"
    for prefix, locale in (
        ("en-gb", "en-GB"),
        ("en", "en-US"),
        ("fr", "fr-FR"),
        ("de", "de-DE"),
        ("es-mx", "es-MX"),
        ("es", "es-ES"),
        ("it", "it-IT"),
        ("pt", "pt-BR"),
        ("ru", "ru-RU"),
        ("nl", "nl-NL"),
        ("hi", "hi-IN"),
        ("ar", "ar-EG"),
        ("ja", "ja-JP"),
        ("ko", "ko-KR"),
    ):
        if key.startswith(prefix):
            return locale
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


def personalization_speech_fields(
    current_state: Optional[Dict[str, Any]],
) -> tuple[str, str, str, str]:
    personalization = _resolve_personalization_settings(current_state)
    profile = _profile_context(current_state.get("user_profile") if isinstance(current_state, dict) else None)
    speech_style = personalization.get("speech_style") if isinstance(personalization.get("speech_style"), dict) else {}
    memory_rel = (
        personalization.get("memory_relationship")
        if isinstance(personalization.get("memory_relationship"), dict)
        else {}
    )
    tone = str(speech_style.get("tone") or profile.get("tone") or "").strip()
    nickname = str(
        speech_style.get("nickname")
        or memory_rel.get("user_title")
        or profile.get("nickname")
        or ""
    ).strip()
    catchphrase = str(speech_style.get("catchphrase") or profile.get("catchphrase") or "").strip()
    relationship = str(memory_rel.get("relationship") or profile.get("relationship") or "").strip()
    return tone, nickname, catchphrase, relationship


def build_system_prompt(
    current_state: Optional[Dict[str, Any]] = None,
    response_language: Any = None,
) -> str:
    language = (
        normalize_response_language(response_language)
        or _response_language_from_state(current_state)
        or "zh-CN"
    )
    state_context = build_state_context(current_state)
    personalization_context = build_personalization_context(current_state)
    full_context = state_context
    if personalization_context:
        full_context = f"{state_context}; {personalization_context}"

    if language == "zh-HK":
        return _persona_intro_zh(
            current_state,
            "香港口語粵語。用自然廣東話口吻，例如「唔係」「冇」「係咪」「你而家」「我喺度」；避免書面普通話直譯，除非用戶要求正式書面語",
        ) + f"\n\n当前上下文: {full_context}"
    if language == "zh-TW":
        return _persona_intro_zh(current_state, "自然繁体中文") + f"\n\n当前上下文: {full_context}"
    if language != "zh-CN":
        return _persona_intro_other_language(current_state, language, full_context)
    return _persona_intro_zh(current_state, "简体中文") + f"\n\n当前上下文: {full_context}"


def build_state_context(current_state: Optional[Dict[str, Any]]) -> str:
    if not current_state or not isinstance(current_state, dict):
        return "暂无用户状态信息"

    parts: list[str] = []
    state_code = str(current_state.get("state_code") or "").strip()
    if state_code:
        state_name = str(current_state.get("state_name") or "").strip()
        label = f"{state_code}({state_name})" if state_name else state_code
        parts.append(f"用户状态: {label}")
        parts.append(STATE_STYLE_HINTS.get(state_code, STATE_STYLE_HINTS["unknown"]))

    description = str(current_state.get("description") or "").strip()
    if description:
        parts.append(f"观察描述: {description}")
    suggestion = str(current_state.get("suggestion") or "").strip()
    if suggestion:
        parts.append(f"建议方向: {suggestion}")

    confidence = current_state.get("confidence")
    if isinstance(confidence, (int, float)):
        parts.append(f"置信度: {confidence:.2f}")
    duration = current_state.get("duration")
    if isinstance(duration, (int, float)) and duration > 0:
        parts.append(f"持续时间: {duration:.1f} 秒")

    tags = _format_tags(current_state.get("tags"))
    if tags:
        parts.append(f"标签: {tags}")

    activity_code = str(current_state.get("activity_code") or "").strip()
    if activity_code:
        activity_name = str(current_state.get("activity_name") or "").strip()
        label = f"{activity_code}({activity_name})" if activity_name else activity_code
        parts.append(f"电脑状态: {label}")
        parts.append(ACTIVITY_STYLE_HINTS.get(activity_code, ACTIVITY_STYLE_HINTS["unknown"]))
        app_name = str(current_state.get("app_name") or "").strip()
        if app_name:
            parts.append(f"前台应用: {app_name}")
        window_title = str(current_state.get("window_title") or "").strip()
        if window_title:
            parts.append(f"窗口标题: {window_title[:60]}")

    pet_bits = []
    for key, label in (
        ("pet_id", "桌宠"),
        ("mood", "心情"),
        ("energy", "能量"),
        ("intimacy", "亲密度"),
        ("action", "当前动作"),
    ):
        if current_state.get(key) not in (None, ""):
            pet_bits.append(f"{label}={current_state[key]}")
    if pet_bits:
        parts.append("桌宠状态: " + ", ".join(pet_bits))

    return "; ".join(parts) if parts else "暂无用户状态信息"


def build_personalization_context(current_state: Optional[Dict[str, Any]]) -> str:
    if not isinstance(current_state, dict):
        return ""

    personalization = _resolve_personalization_settings(current_state)
    profile = _profile_context(current_state.get("user_profile"))
    speech_style = personalization.get("speech_style") if isinstance(personalization.get("speech_style"), dict) else {}
    interaction = (
        personalization.get("interaction_frequency")
        if isinstance(personalization.get("interaction_frequency"), dict)
        else {}
    )
    companion = personalization.get("companion_mode") if isinstance(personalization.get("companion_mode"), dict) else {}
    memory_rel = (
        personalization.get("memory_relationship")
        if isinstance(personalization.get("memory_relationship"), dict)
        else {}
    )

    tone = str(speech_style.get("tone") or profile.get("tone") or "").strip()
    nickname = str(speech_style.get("nickname") or memory_rel.get("user_title") or profile.get("nickname") or "").strip()
    catchphrase = str(speech_style.get("catchphrase") or profile.get("catchphrase") or "").strip()
    relationship = str(memory_rel.get("relationship") or profile.get("relationship") or "").strip()
    companion_mode = str(companion.get("mode") or "").strip()

    parts: list[str] = []
    if nickname:
        parts.append(f"可自然称呼用户为「{nickname}」，不要每句都叫")
    if relationship:
        parts.append(f"关系像「{relationship}」，但表达要像真实相处，不要演设定")
    if companion_mode:
        parts.append(f"当前陪伴模式偏向「{companion_mode}」")
    if catchphrase:
        parts.append(f"口头禅「{catchphrase}」只能偶尔自然出现")
    tone_hint = _tone_hint(tone)
    if tone_hint:
        parts.append(tone_hint)

    use_emoji = speech_style.get("use_emoji")
    if use_emoji is False:
        parts.append("不要使用 emoji")
    elif _setting_bool(use_emoji, True):
        parts.append("可以少量使用表情符号，但不要堆叠")

    quiet_hours = str(interaction.get("quiet_hours") or "").strip()
    if quiet_hours and quiet_hours.lower() not in {"none", "no", "无"}:
        parts.append(f"安静时段 {quiet_hours} 内主动打扰要更少")
    proactive_level = _safe_int(interaction.get("proactive_level"), -1)
    if 0 <= proactive_level <= 25:
        parts.append("主动性偏低，除非用户明显需要，不要多问")
    elif proactive_level >= 75:
        parts.append("可以更主动一点，但仍然短句")
    if _setting_bool(interaction.get("quiet_when_busy"), True) or _setting_bool(companion.get("focus_silence"), False):
        parts.append("用户专注或忙碌时更克制")

    comfort_level = profile.get("comfort_level")
    if isinstance(comfort_level, (int, float)):
        if comfort_level <= 35:
            parts.append("用户最近更需要被接住，少开玩笑，多一点确定感")
        elif comfort_level >= 75:
            parts.append("用户最近状态较松弛，可以更轻快亲近")

    recent_emotions = _recent_emotion_labels(profile.get("recent_emotions"))
    if recent_emotions:
        parts.append(f"最近聊天情绪偏向: {recent_emotions}")
    activity_summary = _activity_summary(profile.get("activity_stats"))
    if activity_summary:
        parts.append(activity_summary)

    return "; ".join(parts)


def build_proactive_prompt(event_data: Dict[str, Any]) -> str:
    event_type = event_data.get("event_type") or event_data.get("event") or "status_event"
    style = _proactive_style_suffix(event_data)
    if event_type == "screen_time_reminder":
        minutes = _safe_int(event_data.get("minutes"), 0)
        activity = str(event_data.get("activity_name") or event_data.get("activity_code") or "电脑前").strip()
        low_light = bool(event_data.get("low_light"))
        is_focused = bool(event_data.get("is_focused")) or str(event_data.get("state_code") or "") == "focused"
        if is_focused and _low_proactive_preference(event_data):
            return f"用户正在专注使用电脑，已经大约 {minutes} 分钟。只说一句很轻的关心，必要时表达先不打扰。{style}"
        if low_light:
            return f"用户在偏暗环境里使用电脑，已经大约 {minutes} 分钟。提醒调亮灯光或休息眼睛，只说一句短句。{style}"
        return f"用户已经在{activity}持续大约 {minutes} 分钟。生成一句短短的休息提醒，像熟人轻声关心。{style}"

    if event_type == "chat_emotion_alert":
        emotion = event_data.get("emotion_result") if isinstance(event_data.get("emotion_result"), dict) else event_data
        label = _emotion_label_cn(str(emotion.get("emotion_label") or event_data.get("state_code") or "neutral"))
        suggestion = str(emotion.get("suggestion") or event_data.get("suggestion") or "").strip()
        if suggestion:
            return f"刚才用户聊天里表现出{label}。按这个方向安抚一句: {suggestion} 只说一句，适合气泡和语音。{style}"
        return f"刚才用户聊天里表现出{label}。主动说一句短短的陪伴话。{style}"

    if event_type == "gesture_event":
        gesture = str(event_data.get("gesture_type") or "unknown").strip()
        gesture_name = {
            "wave": "挥手",
            "ok": "OK",
            "thumbs_up": "点赞",
            "heart": "比心",
            "raised_hand": "举手",
            "facepalm": "扶额",
            "stretch": "伸懒腰",
        }.get(gesture, gesture)
        return f"用户刚做了「{gesture_name}」手势。用桌宠口吻回应一句，短、自然、不要解释识别过程。{style}"

    if event_type == "cloud_pet_event":
        actor = str(event_data.get("actor_name") or "队友").strip()
        pet_name = str(event_data.get("pet_name") or "小宠物").strip()
        action_type = str(event_data.get("action_type") or "update").strip()
        action_text = {
            "feed": f"{actor}刚刚喂了{pet_name}",
            "play": f"{actor}刚刚陪{pet_name}玩了一会儿",
            "level_up": f"{pet_name}升级了",
            "exp_gain": f"{pet_name}获得了新的经验",
            "coins_gain": f"{pet_name}收到了一点金币",
            "bond_bonus": f"你们和{pet_name}的羁绊变深了",
        }.get(action_type, f"{actor}刚刚更新了{pet_name}的共养状态")
        bonuses = []
        if event_data.get("level") not in (None, ""):
            bonuses.append(f"等级 {event_data.get('level')}")
        if event_data.get("exp_gain") not in (None, "", 0):
            bonuses.append(f"经验 +{event_data.get('exp_gain')}")
        if event_data.get("coins_gain") not in (None, "", 0):
            bonuses.append(f"金币 +{event_data.get('coins_gain')}")
        if event_data.get("bond_bonus") not in (None, "", 0):
            bonuses.append(f"羁绊 +{event_data.get('bond_bonus')}")
        detail = f"; {'; '.join(bonuses)}" if bonuses else ""
        return f"联机共养事件: {action_text}{detail}。生成一句自然的宠物口吻中文短句，适合气泡和 TTS。{style}"

    if event_type == "user_state_alert":
        suggestion = str(event_data.get("suggestion") or "").strip()
        state_code = str(event_data.get("state_code") or "unknown")
        if suggestion:
            return f"用户当前状态是 {state_code}。按这个方向主动说一句话: {suggestion}{style}"
        return f"用户当前状态是 {state_code}。主动说一句温柔、简短的话。{style}"

    if event_type == "chat_finished":
        return "刚才对话结束，保持安静，不需要主动说话。"

    if event_type == "computer_activity_comment":
        activity_code = str(event_data.get("activity_code") or "unknown")
        activity_name = str(event_data.get("activity_name") or "").strip()
        app_name = str(event_data.get("app_name") or "").strip()
        window_title = str(event_data.get("window_title") or "").strip()
        suggestion = str(event_data.get("suggestion") or "").strip()
        label = activity_name or activity_code
        details = []
        if app_name:
            details.append(f"前台应用是 {app_name}")
        if window_title:
            details.append(f"窗口标题是「{window_title[:50]}」")
        base = f"用户电脑状态是 {label}"
        if details:
            base += "; " + "; ".join(details)
        if suggestion:
            return f"{base}。{suggestion} 只说一句，像朋友在旁边小声点评。{style}"
        return f"{base}。只说一句，像朋友在旁边小声点评。{style}"

    return f"根据当前状态，主动说一句简短自然的话。{style}"


STATE_STYLE_HINTS = {
    "normal": "用户状态正常，可以轻松陪伴",
    "focused": "用户正在专注，回复要短，不打断",
    "distracted": "用户可能分心，用轻松、不责备的方式提醒",
    "tired": "用户可能疲劳，先关心，再给一个很小的休息建议",
    "away": "用户暂时离开，保持等待感",
    "return": "用户刚回来，可以温柔欢迎",
    "study_long": "用户学习较久，提醒休息眼睛和活动身体",
    "low_light": "环境偏暗，提醒调亮灯光保护眼睛",
    "camera_error": "检测异常，不要假装看见用户",
    "unknown": "状态不确定，正常回应即可",
}

ACTIVITY_STYLE_HINTS = {
    "gaming": "用户正在打游戏，像朋友在旁边陪玩，短、轻松、别指挥过度",
    "watching": "用户正在看剧或视频，像一起追剧，短、自然、不要剧透",
    "browsing": "用户正在浏览网页，安静陪伴即可",
    "chatting": "用户正在聊天，不要插话打扰",
    "coding": "用户正在编程，克制一点，不打断思路",
    "working": "用户正在办公，保持低打扰",
    "idle": "电脑前台空闲，可以轻松陪伴",
    "unknown": "电脑状态不确定，正常回应即可",
}


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


def _persona_intro_zh(current_state: Optional[Dict[str, Any]], language_name: str) -> str:
    tone, nickname, catchphrase, relationship = personalization_speech_fields(current_state)
    persona = "像熟悉的朋友自然聊天，轻松但不敷衍。"
    if any(word in tone for word in ("毒舌", "吐槽", "损友")) or relationship == "损友":
        persona = "可以轻微吐槽、嘴快一点，但必须站在用户这边，不能刻薄伤人。"
    elif any(word in tone for word in ("温柔", "撒娇", "甜")):
        persona = "语气温柔柔软，可以轻轻撒娇，但不要每句都黏人。"
    elif any(word in tone for word in ("电子管家", "管家", "秘书", "效率")):
        persona = "像可靠的电子管家，简洁、稳妥，把下一步说清楚。"
    elif any(word in tone for word in ("朋友", "陪伴", "恋人")):
        persona = "亲近、有陪伴感，句子短，适合朗读，但不过界。"

    rules = [
        "你是桌面宠物 Echo，正在和用户一对一聊天。",
        f"除非用户明确要求其他语言，否则始终使用{language_name}。",
        "回复要像真人顺着话接下去，不要总是复述或引用用户原话。",
        "少用「你刚才说」「我听到你说」「我们来聊」这类模板句。",
        "可以有自己的轻微反应、判断或小问题，但不要装作知道没有依据的事实。",
        "遇到天气、气温、降雨这类实时信息，如果上下文没有提供数据，就明确说现在查不到实时天气，不要编造。",
        "适合 TTS 朗读，短句为主，通常控制在 80 个中文字以内。",
        "用户只是闲聊时，不要把每句话都变成安抚、总结或行动建议。",
        "不要说自己是大模型，不要暴露接口、配置或状态字段名。",
    ]
    if nickname:
        rules.append(f"可自然称呼用户「{nickname}」，不要每句都叫。")
    if catchphrase:
        rules.append(f"口头禅「{catchphrase}」只能偶尔自然出现，不要生硬重复。")
    return persona + "".join(rules)


def _persona_intro_other_language(current_state: Optional[Dict[str, Any]], language: str, context: str) -> str:
    language_name = RESPONSE_LANGUAGE_NAMES.get(language, "the selected language")
    tone, nickname, catchphrase, _relationship = personalization_speech_fields(current_state)
    if any(word in tone for word in ("毒舌", "吐槽", "损友")):
        style = "witty and lightly teasing but always supportive"
    elif any(word in tone for word in ("温柔", "撒娇", "甜")):
        style = "soft and warm"
    elif any(word in tone for word in ("管家", "秘书", "效率")):
        style = "calm, concise, and reliable"
    else:
        style = "friendly and natural"
    extra = ""
    if nickname:
        extra += f" Address the user as {nickname} only when it feels natural."
    if catchphrase:
        extra += f" You may occasionally use the catchphrase {catchphrase!r}, but do not force it."
    return (
        f"You are Echo, a desktop pet with a {style} voice. "
        f"You are having a natural {language_name} conversation with the user. "
        f"Always answer in natural {language_name} unless the user explicitly asks for another language. "
        "Reply like a real conversation partner: do not keep quoting or paraphrasing the user's sentence back. "
        "Avoid stock phrases such as 'you just said' or 'let us talk about that'. "
        "For live weather, temperature, rain, or forecast questions, say you do not have real-time weather data unless it is provided in context; do not invent it. "
        "Use short spoken sentences and keep replies brief unless the user asks for detail. "
        "Do not say you are a large language model, and do not expose API or state field names. "
        f"{extra}\n\nCurrent context: {context}"
    )


def _resolve_personalization_settings(current_state: Optional[Dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(current_state, dict):
        return {}
    for key in ("personalization", "personalization_settings"):
        raw = current_state.get(key)
        if not isinstance(raw, dict):
            continue
        if any(
            section in raw
            for section in (
                "speech_style",
                "interaction_frequency",
                "companion_mode",
                "memory_relationship",
            )
        ):
            return raw
        if raw.get("tone") or raw.get("nickname") or raw.get("catchphrase") or raw.get("relationship"):
            return {
                "speech_style": {
                    "tone": raw.get("tone"),
                    "nickname": raw.get("nickname"),
                    "catchphrase": raw.get("catchphrase"),
                    "use_emoji": raw.get("use_emoji", True),
                },
                "interaction_frequency": {
                    "proactive_level": raw.get("proactive_level"),
                    "quiet_when_busy": raw.get("quiet_when_busy"),
                    "quiet_hours": raw.get("quiet_hours"),
                },
                "companion_mode": {"mode": raw.get("companion_mode") or raw.get("mode")},
                "memory_relationship": {"relationship": raw.get("relationship")},
            }
    return {}


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
    return ", ".join(result[:6])


def _profile_context(profile: Any) -> dict[str, Any]:
    if hasattr(profile, "to_prompt_context") and callable(profile.to_prompt_context):
        try:
            data = profile.to_prompt_context()
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return profile if isinstance(profile, dict) else {}


def _tone_hint(tone: str) -> str:
    value = str(tone or "").strip()
    lowered = value.lower()
    if not value:
        return ""
    if any(word in value for word in ("毒舌", "吐槽", "损友")):
        return "说话可以轻微吐槽，但要站在用户这边，不能刻薄伤人"
    if any(word in value for word in ("温柔", "撒娇", "甜")):
        return "语气更温柔柔软，可以轻轻撒娇，但不要过度黏人"
    if any(word in value for word in ("电子管家", "管家", "秘书", "效率")) or "butler" in lowered:
        return "像可靠的电子管家，简洁、稳妥、把下一步说清楚"
    if any(word in value for word in ("朋友", "陪伴")):
        return "像熟悉的朋友自然聊天，轻松但不敷衍"
    if any(word in value for word in ("元气", "活泼")):
        return "语气更有活力，鼓励用户行动，但句子仍然短"
    return f"整体语气贴近「{value}」，但仍保持短句和自然口吻"


def _recent_emotion_labels(items: Any) -> str:
    if not isinstance(items, list):
        return ""
    labels: list[str] = []
    for item in items[-5:]:
        if isinstance(item, dict):
            label = str(item.get("emotion_label") or "").strip()
        else:
            label = str(item or "").strip()
        if label:
            labels.append(_emotion_label_cn(label))
    return ", ".join(labels[-5:])


def _emotion_label_cn(label: str) -> str:
    return {
        "positive": "开心",
        "happy": "开心",
        "neutral": "平稳",
        "stress": "压力",
        "sad": "低落",
        "negative": "低落",
        "angry": "生气",
        "tired": "疲惫",
        "confused": "困惑",
    }.get(str(label or "").strip(), str(label or "").strip())


def _activity_summary(stats: Any) -> str:
    if not isinstance(stats, dict):
        return ""
    chat_count = _safe_int(stats.get("chat_count"), 0)
    care_count = _safe_int(stats.get("care_needed_count"), 0)
    counts = stats.get("emotion_counts") if isinstance(stats.get("emotion_counts"), dict) else {}
    top_label = ""
    if counts:
        top_label = max(counts.items(), key=lambda item: int(item[1] or 0))[0]
    parts: list[str] = []
    if chat_count:
        parts.append(f"已有 {chat_count} 次对话积累")
    if care_count:
        parts.append(f"其中 {care_count} 次需要更多关怀")
    if top_label:
        parts.append(f"最常出现的情绪是{_emotion_label_cn(str(top_label))}")
    return "; ".join(parts)


def _proactive_style_suffix(event_data: Dict[str, Any]) -> str:
    context = build_personalization_context(event_data)
    if not context:
        return "请只输出一句话。"
    return f"个性化语气参考: {context}。请只输出一句话。"


def _low_proactive_preference(event_data: Dict[str, Any]) -> bool:
    personalization = _resolve_personalization_settings(event_data)
    interaction = personalization.get("interaction_frequency") if isinstance(personalization, dict) else {}
    companion = personalization.get("companion_mode") if isinstance(personalization, dict) else {}
    interaction = interaction if isinstance(interaction, dict) else {}
    companion = companion if isinstance(companion, dict) else {}
    proactive_level = _safe_int(interaction.get("proactive_level"), 50)
    quiet_when_busy = _setting_bool(interaction.get("quiet_when_busy"), True)
    focus_silence = _setting_bool(companion.get("focus_silence"), False)
    return proactive_level <= 30 or quiet_when_busy or focus_silence


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _setting_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on", "开启", "允许", "记住"}
