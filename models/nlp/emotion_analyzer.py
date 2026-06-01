"""
EmotionAnalyzer: lightweight rule-based chat emotion analysis.

Supports positive, neutral, stress, sad, angry, tired, confused.
# TODO: use DeepSeek for better emotion analysis.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


# Keyword rules for each emotion category
_EMOTION_KEYWORDS: Dict[str, List[str]] = {
    "positive": [
        "开心", "高兴", "好", "棒", "赞", "喜欢", "爱", "哈哈", "嘿嘿",
        "不错", "谢谢", "感谢", "完美", "厉害", "漂亮", "舒服", "放松",
        "happy", "great", "love", "nice", "good", "wow", "awesome",
    ],
    "stress": [
        "压力", "焦虑", "紧张", "忙", "累死了", "赶", "deadline", "ddl",
        "烦", "爆", "撑不住", "好难", "崩溃", "stress", "anxious", "overwhelmed",
    ],
    "sad": [
        "难过", "伤心", "哭", "泪", "失落", "失望", "孤单", "寂寞",
        "想哭", "心累", "没意思", "sad", "cry", "lonely", "depressed",
    ],
    "angry": [
        "生气", "烦死了", "气死", "讨厌", "火大", "暴躁", "愤怒",
        "受不了", "怒", "angry", "mad", "annoyed", "frustrated",
    ],
    "tired": [
        "困", "累", "想睡", "没精神", "乏力", "疲劳", "倦",
        "不想动", "tired", "sleepy", "exhausted", "drained",
    ],
    "confused": [
        "?", "不懂", "什么", "为啥", "怎么", "奇怪", "迷", "疑惑",
        "confused", "what", "why", "huh", "puzzled",
    ],
    "neutral": [],  # fallback
}


def analyze_chat_emotion(
    text: str,
    history: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Analyze the emotion of a chat message using keyword rules.

    :param text:    user's input text
    :param history: optional list of recent chat messages (not yet used)
    :returns: dict with keys:
        - emotion_label: str (positive/neutral/stress/sad/angry/tired/confused)
        - confidence:     float (0.0-1.0)
        - reason:         str
        - suggestion:     str (action suggestion for the pet)
        - need_care:      bool

    # TODO: use DeepSeek for better emotion analysis (check deepseek_api availability).
    """
    if not text or not text.strip():
        return {
            "emotion_label": "neutral",
            "confidence": 0.8,
            "reason": "用户没有输入文本。",
            "suggestion": "保持安静陪伴。",
            "need_care": False,
        }

    cleaned = text.lower().strip()

    # Score each emotion category
    scores: Dict[str, int] = {}
    for emotion, keywords in _EMOTION_KEYWORDS.items():
        if not keywords:
            continue
        score = 0
        for kw in keywords:
            # Count keyword occurrences
            score += len(re.findall(re.escape(kw.lower()), cleaned))
        if score > 0:
            scores[emotion] = score

    if not scores:
        return _neutral_result()

    # Pick the highest-scored emotion
    best_emotion = max(scores, key=scores.get)
    best_score = scores[best_emotion]
    total_score = sum(scores.values())

    confidence = min(1.0, (best_score / max(total_score, 1)) * 0.6 + 0.3)

    result = _build_result(best_emotion, confidence)
    return result


def _neutral_result() -> Dict[str, Any]:
    return {
        "emotion_label": "neutral",
        "confidence": 0.8,
        "reason": "未检测到明显情绪关键词。",
        "suggestion": "保持自然陪伴。",
        "need_care": False,
    }


def _build_result(emotion: str, confidence: float) -> Dict[str, Any]:
    suggestions = {
        "positive": "用户心情不错，可以一起开心互动。",
        "stress": "用户有压力，先用温暖的话安抚，再简短鼓励。",
        "sad": "用户有点低落，温柔陪伴，不要追问原因。",
        "angry": "用户有点烦躁，先安抚情绪，不要讲道理。",
        "tired": "用户很疲惫，建议简短关心，鼓励休息。",
        "confused": "用户有些困惑，可以简单解释或询问是否需要帮助。",
    }
    need_care_map = {
        "positive": False,
        "neutral": False,
        "stress": True,
        "sad": True,
        "angry": True,
        "tired": True,
        "confused": False,
    }
    reasons = {
        "positive": "检测到开心/积极词汇。",
        "stress": "检测到压力/焦虑相关词汇。",
        "sad": "检测到难过/失落相关词汇。",
        "angry": "检测到生气/烦躁相关词汇。",
        "tired": "检测到疲惫/困倦相关词汇。",
        "confused": "检测到困惑/疑问相关词汇。",
    }
    return {
        "emotion_label": emotion,
        "confidence": round(confidence, 2),
        "reason": reasons.get(emotion, "关键词匹配结果。"),
        "suggestion": suggestions.get(emotion, "根据当前状态自然回应。"),
        "need_care": need_care_map.get(emotion, False),
    }
