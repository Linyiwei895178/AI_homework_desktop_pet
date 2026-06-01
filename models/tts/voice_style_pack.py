"""
Cross-language voice style presets for Edge TTS.

These presets keep "voice style" separate from the reply language. A style pack
selects a language-appropriate Edge voice plus a few synthesis parameters.
"""

from __future__ import annotations

from typing import Any

from models.nlp.prompt_builder import normalize_response_language


DEFAULT_STYLE_PACK_ID = "natural"

_DEFAULT_VOICES: dict[str, str] = {
    "zh-CN": "zh-CN-XiaoyiNeural",
    "zh-HK": "zh-HK-HiuGaaiNeural",
    "zh-TW": "zh-TW-HsiaoChenNeural",
    "en-US": "en-US-JennyNeural",
    "en-GB": "en-GB-SoniaNeural",
    "fr-FR": "fr-FR-DeniseNeural",
    "de-DE": "de-DE-KatjaNeural",
    "es-ES": "es-ES-ElviraNeural",
    "es-MX": "es-MX-DaliaNeural",
    "it-IT": "it-IT-ElsaNeural",
    "pt-BR": "pt-BR-FranciscaNeural",
    "ru-RU": "ru-RU-SvetlanaNeural",
    "nl-NL": "nl-NL-ColetteNeural",
    "hi-IN": "hi-IN-SwaraNeural",
    "ar-EG": "ar-EG-SalmaNeural",
    "ja-JP": "ja-JP-NanamiNeural",
    "ko-KR": "ko-KR-SunHiNeural",
}

VOICE_STYLE_PACKS: tuple[dict[str, Any], ...] = (
    {
        "id": "natural",
        "name": "自然音",
        "icon": "🎙️",
        "description": "清晰自然的默认音色，适合日常聊天和长文本朗读。",
        "sample_text": "我在呢，今天想聊点什么？",
        "voices": dict(_DEFAULT_VOICES),
        "edge_rate": "+0%",
        "edge_pitch": "+0Hz",
        "edge_volume": "+0%",
        "prosody_style": "natural",
        "prosody_label": "自然清晰",
        "voice_profile": "default",
        "cute_style": False,
    },
    {
        "id": "sweet_girl",
        "name": "甜妹音",
        "icon": "🍬",
        "description": "更轻快、更甜一点的女声风格，适合陪伴、撒娇感和轻松聊天。",
        "sample_text": "我在呀，今天也想陪你多待一会儿。",
        "voices": {
            **_DEFAULT_VOICES,
            "zh-CN": "zh-CN-XiaoyiNeural",
            "zh-HK": "zh-HK-HiuGaaiNeural",
            "zh-TW": "zh-TW-HsiaoChenNeural",
            "en-US": "en-US-JennyNeural",
            "ja-JP": "ja-JP-NanamiNeural",
            "ko-KR": "ko-KR-SunHiNeural",
        },
        "edge_rate": "+12%",
        "edge_pitch": "+18Hz",
        "edge_volume": "+6%",
        "prosody_style": "sweet",
        "prosody_label": "轻快偏甜",
        "voice_profile": "cute",
        "cute_style": True,
    },
    {
        "id": "mature_sister",
        "name": "御姐音",
        "icon": "💄",
        "description": "成熟、稳一点的女声风格，语速略慢，尾音更收。",
        "sample_text": "别急，我听着呢，我们慢慢处理。",
        "voices": {
            **_DEFAULT_VOICES,
            "zh-CN": "zh-CN-XiaomoNeural",
            "zh-HK": "zh-HK-HiuMaanNeural",
            "zh-TW": "zh-TW-HsiaoChenNeural",
            "en-US": "en-US-AriaNeural",
            "en-GB": "en-GB-SoniaNeural",
        },
        "edge_rate": "-8%",
        "edge_pitch": "-10Hz",
        "edge_volume": "+4%",
        "prosody_style": "mature",
        "prosody_label": "成熟稳缓",
        "voice_profile": "default",
        "cute_style": False,
    },
    {
        "id": "taiwan",
        "name": "台湾口音",
        "icon": "🌺",
        "description": "自然一点的台湾中文女声，重点放在顺畅断句，不刻意拉高尾音。",
        "sample_text": "我在这边陪你，慢慢说就好。",
        "voices": {
            **_DEFAULT_VOICES,
            "zh-CN": "zh-TW-HsiaoYuNeural",
            "zh-HK": "zh-TW-HsiaoYuNeural",
            "zh-TW": "zh-TW-HsiaoYuNeural",
            "en-US": "en-US-AriaNeural",
            "en-GB": "en-GB-SoniaNeural",
        },
        "edge_rate": "-2%",
        "edge_pitch": "+0Hz",
        "edge_volume": "+2%",
        "edge_playback_guard": False,
        "text_normalizer": "zh_tw_natural",
        "prosody_style": "taiwan",
        "prosody_label": "顺畅自然",
        "voice_profile": "default",
        "cute_style": False,
    },
    {
        "id": "dominator",
        "name": "主宰音",
        "icon": "👑",
        "description": "低沉、有压迫感的强势男声，适合命令感和戏剧化表达。",
        "sample_text": "安静，接下来交给我来掌控。",
        "voices": {
            **_DEFAULT_VOICES,
            "zh-CN": "zh-CN-YunjianNeural",
            "zh-HK": "zh-HK-WanLungNeural",
            "zh-TW": "zh-TW-YunJheNeural",
            "en-US": "en-US-GuyNeural",
            "en-GB": "en-GB-RyanNeural",
            "fr-FR": "fr-FR-HenriNeural",
            "de-DE": "de-DE-ConradNeural",
            "es-ES": "es-ES-AlvaroNeural",
            "es-MX": "es-MX-JorgeNeural",
            "it-IT": "it-IT-DiegoNeural",
            "pt-BR": "pt-BR-AntonioNeural",
            "ru-RU": "ru-RU-DmitryNeural",
            "nl-NL": "nl-NL-MaartenNeural",
            "hi-IN": "hi-IN-MadhurNeural",
            "ar-EG": "ar-EG-ShakirNeural",
            "ja-JP": "ja-JP-KeitaNeural",
            "ko-KR": "ko-KR-InJoonNeural",
        },
        "edge_rate": "-16%",
        "edge_pitch": "-24Hz",
        "edge_volume": "+9%",
        "prosody_style": "dominant",
        "prosody_label": "低沉强势",
        "voice_profile": "default",
        "cute_style": False,
    },
    {
        "id": "boss",
        "name": "霸总音",
        "icon": "🕴️",
        "description": "冷静、笃定、低沉克制的男声，语速更稳，停顿更有掌控感。",
        "sample_text": "别担心，这件事我会陪你稳稳拿下。",
        "voices": {
            **_DEFAULT_VOICES,
            "zh-CN": "zh-CN-YunxiNeural",
            "zh-HK": "zh-HK-WanLungNeural",
            "zh-TW": "zh-TW-YunJheNeural",
            "en-US": "en-US-DavisNeural",
            "en-GB": "en-GB-RyanNeural",
            "fr-FR": "fr-FR-HenriNeural",
            "de-DE": "de-DE-ConradNeural",
            "es-ES": "es-ES-AlvaroNeural",
            "ja-JP": "ja-JP-KeitaNeural",
            "ko-KR": "ko-KR-InJoonNeural",
        },
        "edge_rate": "-14%",
        "edge_pitch": "-20Hz",
        "edge_volume": "+7%",
        "prosody_style": "boss",
        "prosody_label": "冷静掌控",
        "voice_profile": "default",
        "cute_style": False,
    },
    {
        "id": "gentle_sister",
        "name": "温柔姐姐音",
        "icon": "🌙",
        "description": "柔和、耐心、语速略慢的姐姐感女声，适合安慰和陪伴。",
        "sample_text": "没关系，我在这里陪着你，慢慢来就好。",
        "voices": {
            **_DEFAULT_VOICES,
            "zh-CN": "zh-CN-XiaoxiaoNeural",
            "zh-HK": "zh-HK-HiuGaaiNeural",
            "zh-TW": "zh-TW-HsiaoChenNeural",
            "en-US": "en-US-AriaNeural",
            "en-GB": "en-GB-SoniaNeural",
            "ja-JP": "ja-JP-NanamiNeural",
            "ko-KR": "ko-KR-SunHiNeural",
        },
        "edge_rate": "-12%",
        "edge_pitch": "-2Hz",
        "edge_volume": "+3%",
        "prosody_style": "gentle",
        "prosody_label": "柔和慢语",
        "voice_profile": "calm",
        "cute_style": False,
    },
    {
        "id": "young_male",
        "name": "少年音",
        "icon": "✨",
        "description": "清亮、轻快的少年感男声，适合活泼和元气回复。",
        "sample_text": "走吧，我陪你把今天的任务搞定。",
        "voices": {
            **_DEFAULT_VOICES,
            "zh-CN": "zh-CN-YunxiNeural",
            "zh-HK": "zh-HK-WanLungNeural",
            "zh-TW": "zh-TW-YunJheNeural",
            "en-US": "en-US-GuyNeural",
            "en-GB": "en-GB-RyanNeural",
            "ja-JP": "ja-JP-KeitaNeural",
            "ko-KR": "ko-KR-InJoonNeural",
        },
        "edge_rate": "+8%",
        "edge_pitch": "+10Hz",
        "edge_volume": "+5%",
        "prosody_style": "young",
        "prosody_label": "清亮轻快",
        "voice_profile": "playful",
        "cute_style": True,
    },
    {
        "id": "sharp_tongue",
        "name": "毒舌音",
        "icon": "⚡",
        "description": "语速稍快、尾音更利落的吐槽风格，适合轻微毒舌和调侃。",
        "sample_text": "好啦，我知道你又在拖延了，现在开始还来得及。",
        "voices": {
            **_DEFAULT_VOICES,
            "zh-CN": "zh-CN-XiaomoNeural",
            "zh-HK": "zh-HK-HiuMaanNeural",
            "zh-TW": "zh-TW-HsiaoChenNeural",
            "en-US": "en-US-AriaNeural",
            "en-GB": "en-GB-SoniaNeural",
            "ja-JP": "ja-JP-NanamiNeural",
            "ko-KR": "ko-KR-SunHiNeural",
        },
        "edge_rate": "+6%",
        "edge_pitch": "-4Hz",
        "edge_volume": "+5%",
        "prosody_style": "sharp",
        "prosody_label": "利落短促",
        "voice_profile": "default",
        "cute_style": False,
    },
)


def normalize_voice_style_pack_id(value: Any) -> str:
    raw = str(value or "").strip().lower().replace("-", "_")
    ids = {str(pack["id"]) for pack in VOICE_STYLE_PACKS}
    aliases = {
        "default": "natural",
        "normal": "natural",
        "sweet": "sweet_girl",
        "girl": "sweet_girl",
        "yujie": "mature_sister",
        "sister": "mature_sister",
        "taiwanese": "taiwan",
        "tw": "taiwan",
        "master": "dominator",
        "ceo": "boss",
        "gentle": "gentle_sister",
        "young": "young_male",
        "boy": "young_male",
        "sharp": "sharp_tongue",
        "tsundere": "sharp_tongue",
    }
    raw = aliases.get(raw, raw)
    return raw if raw in ids else DEFAULT_STYLE_PACK_ID


def voice_style_pack_by_id(value: Any) -> dict[str, Any]:
    pack_id = normalize_voice_style_pack_id(value)
    return next((dict(pack) for pack in VOICE_STYLE_PACKS if pack["id"] == pack_id), dict(VOICE_STYLE_PACKS[0]))


def voice_style_pack_choices() -> list[dict[str, Any]]:
    choices: list[dict[str, Any]] = []
    for pack in VOICE_STYLE_PACKS:
        item = dict(pack)
        item["kind"] = "voice_style_pack"
        item["display_name"] = item.get("name", item.get("id", ""))
        choices.append(item)
    return choices


def resolve_voice_style_pack_settings(pack_id: Any, response_language: Any = None) -> dict[str, Any]:
    pack = voice_style_pack_by_id(pack_id)
    language = normalize_response_language(response_language) or "zh-CN"
    voices = pack.get("voices") if isinstance(pack.get("voices"), dict) else {}
    edge_voice = str(voices.get(language) or "").strip()
    if not edge_voice:
        family = language.split("-", 1)[0].lower()
        edge_voice = next(
            (str(voice).strip() for locale, voice in voices.items() if str(locale).lower().startswith(family)),
            "",
        )
    if not edge_voice:
        edge_voice = str(voices.get("zh-CN") or _DEFAULT_VOICES["zh-CN"])

    return {
        "edge_voice": edge_voice,
        "edge_rate": str(pack.get("edge_rate") or "+0%"),
        "edge_pitch": str(pack.get("edge_pitch") or "+0Hz"),
        "edge_volume": str(pack.get("edge_volume") or "+0%"),
        "edge_playback_guard": bool(pack.get("edge_playback_guard", True)),
        "text_normalizer": str(pack.get("text_normalizer") or ""),
        "prosody_style": str(pack.get("prosody_style") or "natural"),
        "prosody_label": str(pack.get("prosody_label") or ""),
        "voice_style_pack_locks_prosody": bool(pack.get("voice_style_pack_locks_prosody", True)),
        "voice_profile": str(pack.get("voice_profile") or "default"),
        "cute_style": bool(pack.get("cute_style", False)),
        "voice_style_pack": str(pack.get("id") or DEFAULT_STYLE_PACK_ID),
    }
