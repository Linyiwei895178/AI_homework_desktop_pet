"""
Rule-based chat emotion analysis for Team C.

The analyzer intentionally stays deterministic and dependency-free so it can
run for every user message before the LLM/TTS path starts.
"""

from __future__ import annotations

import re
from typing import Any


EMOTION_LABELS = ("positive", "neutral", "stress", "sad", "angry", "tired", "confused")

_KEYWORDS: dict[str, tuple[str, ...]] = {
    "positive": (
        "开心",
        "高兴",
        "舒服",
        "喜欢",
        "爱你",
        "太好了",
        "棒",
        "顺利",
        "谢谢",
        "哈哈",
        "嘿嘿",
        "happy",
        "great",
        "thanks",
        "love",
    ),
    "stress": (
        "压力",
        "焦虑",
        "紧张",
        "崩溃",
        "忙不过来",
        "来不及",
        "ddl",
        "deadline",
        "考试",
        "项目",
        "加班",
        "撑不住",
        "stress",
        "stressed",
        "anxious",
    ),
    "sad": (
        "难过",
        "伤心",
        "委屈",
        "想哭",
        "孤独",
        "失落",
        "不开心",
        "心累",
        "sad",
        "upset",
        "lonely",
        "cry",
    ),
    "angry": (
        "生气",
        "愤怒",
        "气死",
        "烦死",
        "讨厌",
        "恶心",
        "火大",
        "别烦",
        "滚",
        "angry",
        "mad",
        "hate",
    ),
    "tired": (
        "累",
        "困",
        "疲惫",
        "没精神",
        "睡不醒",
        "熬夜",
        "想睡",
        "休息",
        "tired",
        "sleepy",
        "exhausted",
    ),
    "confused": (
        "不懂",
        "不会",
        "迷茫",
        "困惑",
        "搞不懂",
        "怎么办",
        "为什么",
        "怎么回事",
        "不知道",
        "confused",
        "why",
        "how",
        "what",
    ),
}

_SUGGESTIONS = {
    "positive": "接住用户的好心情，轻快回应，可以一起庆祝一下。",
    "neutral": "自然陪聊，保持简短友好。",
    "stress": "先安抚压力，再建议把事情拆成一个很小的下一步。",
    "sad": "先共情陪伴，不急着讲道理，给一个温柔的小建议。",
    "angry": "先承认用户的不爽，避免火上浇油，引导慢慢说。",
    "tired": "提醒用户放松和休息，语气放轻。",
    "confused": "帮用户把问题理清楚，先问或给一个最小起点。",
}

_CARE_LABELS = {"stress", "sad", "angry", "tired", "confused"}


def analyze_chat_emotion(text: str, history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """
    Classify one user message into a small, stable emotion label.

    Returns a dict containing emotion_label, confidence, reason, suggestion and
    need_care. `history` is accepted for future model-backed analysis.
    """
    value = str(text or "").strip()
    if not value:
        return _result("neutral", 0.45, "用户没有输入有效内容。")

    # TODO: use DeepSeek for better analysis.
    scores: dict[str, float] = {label: 0.0 for label in EMOTION_LABELS}
    lowered = value.lower()
    for label, keywords in _KEYWORDS.items():
        for keyword in keywords:
            if keyword and keyword.lower() in lowered:
                scores[label] += 1.0 + min(0.4, len(keyword) / 12)

    punctuation_boost = min(0.25, value.count("!") * 0.06 + value.count("！") * 0.06)
    if punctuation_boost:
        if scores["angry"] > 0:
            scores["angry"] += punctuation_boost
        elif scores["positive"] > 0:
            scores["positive"] += punctuation_boost

    if re.search(r"(吗|嘛|么|？|\?)\s*$", value):
        scores["confused"] += 0.35
    if re.search(r"(呜|唉|哎|唔|哭|555|www)", lowered):
        scores["sad"] += 0.45
    if re.search(r"(啊啊+|烦+|草+)", lowered):
        scores["angry"] += 0.35
    if len(value) <= 3 and not any(scores.values()):
        scores["neutral"] = 0.45

    label, raw_score = max(scores.items(), key=lambda item: item[1])
    if raw_score <= 0:
        label = "neutral"
        raw_score = 0.5

    confidence = _confidence(raw_score, value)
    reason = _reason(label, value, raw_score)
    return _result(label, confidence, reason)


def _result(label: str, confidence: float, reason: str) -> dict[str, Any]:
    emotion_label = label if label in EMOTION_LABELS else "neutral"
    return {
        "emotion_label": emotion_label,
        "confidence": round(max(0.0, min(1.0, float(confidence))), 2),
        "reason": reason,
        "suggestion": _SUGGESTIONS[emotion_label],
        "need_care": emotion_label in _CARE_LABELS,
    }


def _confidence(score: float, text: str) -> float:
    base = 0.52 + min(0.36, score * 0.13)
    if len(text) >= 12:
        base += 0.04
    return base


def _reason(label: str, text: str, score: float) -> str:
    if label == "neutral":
        return "没有明显情绪关键词，按普通聊天处理。"
    matched = [
        keyword
        for keyword in _KEYWORDS.get(label, ())
        if keyword and keyword.lower() in text.lower()
    ]
    if matched:
        return f"检测到“{matched[0]}”等表达，倾向 {label}。"
    return f"根据语气和上下文线索，倾向 {label}。"
