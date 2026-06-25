"""Intent routing and reply cleanup for natural chat turns.

The router is deliberately small and deterministic. It catches turns where a
generic LLM prompt often goes wrong: live facts, language-specific replies,
user complaints about templated speech, and emotionally loaded messages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReplyRoute:
    intent: str
    mode: str
    memory_policy: str = "keep"
    direct_reply: str = ""
    system_hint: str = ""
    avoid_templates: tuple[str, ...] = field(default_factory=tuple)

    def to_state(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "mode": self.mode,
            "memory_policy": self.memory_policy,
            "system_hint": self.system_hint,
            "avoid_templates": list(self.avoid_templates),
        }


TEMPLATE_PHRASES = (
    "你刚才说",
    "你剛才講",
    "我听到你说",
    "我聽到你講",
    "我听到的是",
    "我们来聊聊",
    "我哋嚟傾下",
    "关于这个",
    "关于你说的",
    "我理解你的意思是",
    "收到你的意思",
    "先给你一个短短的想法",
    "作为一个",
)


def route_user_message(
    text: str,
    current_state: dict[str, Any] | None = None,
    response_language: str = "",
) -> ReplyRoute:
    value = str(text or "").strip()
    language = _language(response_language, current_state)
    if not value:
        return _route("empty", "chat", "skip", language)

    if _is_weather_query(value):
        return _route(
            "weather",
            "realtime",
            "keep",
            language,
            direct_reply=_weather_direct_reply(language),
            hint=(
                "用户在问实时天气/气温/降雨。没有实时天气数据时必须明说，"
                "不要编造城市天气，也不要绕到安慰或闲聊。"
            ),
        )

    if _contains(value, _META_WORDS):
        return _route(
            "quality_complaint",
            "meta",
            "keep",
            language,
            hint=(
                "用户在反馈回复像模板或答非所问。先承认体验问题，再具体说明这次会怎样接话；"
                "不要自夸，不要复述用户原句。"
            ),
        )

    if _contains(value, _SETTINGS_WORDS):
        return _route(
            "settings",
            "settings",
            "skip",
            language,
            hint="用户像是在改声音、语言或开关设置。只确认具体设置需求；不要假装已经改成功。",
        )

    if _contains(value, _AFFECTION_WORDS):
        return _route(
            "affection",
            "affection",
            "keep",
            language,
            hint="用亲近但不过界的方式回应喜欢、想念、抱抱这类表达，别端着说教。",
        )

    if _contains(value, _EMOTION_WORDS):
        return _route(
            "emotional_support",
            "care",
            "keep",
            language,
            hint="先接住情绪，再给一个很轻的小问题或很小的下一步。不要总结成心理报告。",
        )

    if _contains(value, _TASK_WORDS):
        return _route(
            "task_help",
            "task",
            "keep",
            language,
            hint="给一个能马上开始的下一步，短句、具体，不要把事情讲成一整套大道理。",
        )

    if _contains(value, _GREETING_WORDS) and len(value) <= 12:
        return _route(
            "greeting",
            "chat",
            "keep",
            language,
            hint="自然打招呼，像熟人接话，别把问候展开成说明书。",
        )

    return _route(
        "casual",
        "chat",
        "keep",
        language,
        hint="顺着用户这一句往前接，给一点自己的判断或好奇心；不要复述用户原话。",
    )


def repair_template_reply(reply: str, route: ReplyRoute | dict[str, Any] | None, response_language: str = "") -> str:
    value = str(reply or "").strip()
    if not value:
        return value
    route_obj = _coerce_route(route)
    language = _language(response_language, None)
    banned = tuple(route_obj.avoid_templates) if route_obj else TEMPLATE_PHRASES
    if not _contains(value, banned):
        return value
    if route_obj and route_obj.intent == "quality_complaint":
        return _quality_direct_reply(language)
    if route_obj and route_obj.intent == "weather":
        return _weather_direct_reply(language)
    if route_obj and route_obj.mode == "care":
        return _care_direct_reply(language)
    if route_obj and route_obj.mode == "task":
        return _task_direct_reply(language)
    return _casual_direct_reply(language)


def _route(
    intent: str,
    mode: str,
    memory_policy: str,
    language: str,
    direct_reply: str = "",
    hint: str = "",
) -> ReplyRoute:
    return ReplyRoute(
        intent=intent,
        mode=mode,
        memory_policy=memory_policy,
        direct_reply=direct_reply,
        system_hint=hint,
        avoid_templates=TEMPLATE_PHRASES,
    )


def _coerce_route(route: ReplyRoute | dict[str, Any] | None) -> ReplyRoute | None:
    if isinstance(route, ReplyRoute):
        return route
    if not isinstance(route, dict):
        return None
    return ReplyRoute(
        intent=str(route.get("intent") or "casual"),
        mode=str(route.get("mode") or "chat"),
        memory_policy=str(route.get("memory_policy") or "keep"),
        direct_reply=str(route.get("direct_reply") or ""),
        system_hint=str(route.get("system_hint") or ""),
        avoid_templates=tuple(route.get("avoid_templates") or TEMPLATE_PHRASES),
    )


def _language(response_language: str = "", state: dict[str, Any] | None = None) -> str:
    value = str(response_language or "").strip()
    if value:
        return value
    if isinstance(state, dict):
        for key in ("response_language", "reply_language", "language", "lang"):
            candidate = str(state.get(key) or "").strip()
            if candidate:
                return candidate
    return "zh-CN"


def _contains(text: str, words: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(word and (word.lower() in lowered or word in text) for word in words)


def _is_weather_query(text: str) -> bool:
    lowered = text.lower()
    return (
        _contains(text, _WEATHER_WORDS)
        and (_contains(text, _TIME_WORDS) or _contains(text, _QUESTION_WORDS) or "weather" in lowered)
    ) or "weather" in lowered


def _is_cantonese(language: str) -> bool:
    return str(language or "").lower() in {"zh-hk", "yue", "cantonese"}


def _weather_direct_reply(language: str) -> str:
    if _is_cantonese(language):
        return "我而家未接到即時天氣資料，唔敢亂報。你話我知邊個城市，我可以幫你整理要查啲咩。"
    return "我现在还没接到实时天气数据，不能可靠地报今天的天气。你告诉我城市后，我可以先帮你整理该查哪些信息。"


def _quality_direct_reply(language: str) -> str:
    if _is_cantonese(language):
        return "係，呢種模板感會好出戲。我會先分清你係問資料、講情緒，定係想閒傾，再用一句真係接得住嘅話回你。"
    return "对，这种模板感会很出戏。我会先分清你是在问信息、表达情绪，还是想闲聊，再用一句真正接得住的话回你。"


def _care_direct_reply(language: str) -> str:
    if _is_cantonese(language):
        return "聽落真係有啲頂住。你唔使即刻整理好，我喺度聽你慢慢講。"
    return "听起来确实有点压住人。你不用马上整理好，我在这儿听你慢慢说。"


def _task_direct_reply(language: str) -> str:
    if _is_cantonese(language):
        return "得，先唔好諗到成座山咁大。我哋搵最細嗰一步開頭。"
    return "可以，先别把它想成一整座山。我们只抓最小的第一步开始。"


def _casual_direct_reply(language: str) -> str:
    if _is_cantonese(language):
        return "明，你呢句我接到。你想先講重點，定係想我陪你慢慢拆？"
    return "明白，这句我接到了。你想先讲重点，还是让我陪你慢慢拆？"


_GREETING_WORDS = ("你好", "嗨", "在吗", "在嗎", "hello", "hi", "hey", "早晨", "喂")
_WEATHER_WORDS = (
    "天气",
    "天氣",
    "气温",
    "氣溫",
    "温度",
    "溫度",
    "下雨",
    "下雪",
    "刮风",
    "颱風",
    "台风",
    "空气质量",
    "空氣質素",
    "weather",
)
_TIME_WORDS = (
    "今天",
    "今日",
    "明天",
    "聽日",
    "现在",
    "而家",
    "实时",
    "即時",
    "最近",
    "这几天",
    "呢幾日",
    "周末",
)
_QUESTION_WORDS = (
    "怎么样",
    "怎麼樣",
    "点样",
    "點樣",
    "如何",
    "咋样",
    "幾多度",
    "多少度",
    "?",
    "？",
)
_EMOTION_WORDS = (
    "难过",
    "難過",
    "压力",
    "壓力",
    "焦虑",
    "焦慮",
    "不开心",
    "唔開心",
    "委屈",
    "害怕",
    "烦",
    "煩",
    "崩溃",
    "崩潰",
    "累",
    "攰",
)
_TASK_WORDS = (
    "学习",
    "學習",
    "作业",
    "功課",
    "工作",
    "代码",
    "代碼",
    "程式",
    "项目",
    "項目",
    "考试",
    "考試",
    "论文",
    "論文",
)
_AFFECTION_WORDS = (
    "喜欢你",
    "鍾意你",
    "鐘意你",
    "爱你",
    "愛你",
    "想你",
    "掛住你",
    "抱抱",
    "攬",
)
_SETTINGS_WORDS = (
    "设置",
    "設定",
    "音色",
    "声音",
    "聲音",
    "语言",
    "語言",
    "粤语",
    "粵語",
    "普通话",
    "普通話",
    "开启",
    "关闭",
    "打開",
    "關掉",
)
_META_WORDS = (
    "模板",
    "不像真人",
    "唔似真人",
    "机械",
    "機械",
    "答非所问",
    "答非所問",
    "复读",
    "覆讀",
    "不自然",
    "智能",
    "没以前",
    "冇以前",
)
