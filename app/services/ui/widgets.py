"""
PySide6 UI 控件：右键菜单、弧形动作菜单、气泡、输入框、控制台等。
"""
from __future__ import annotations

import datetime
import json
import math
import os
import re
import shutil
import sys
import threading
import time
from collections import defaultdict
from typing import Any, Callable, Optional

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QFontDatabase,
    QIcon,
    QMouseEvent,
    QMovie,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QTabWidget,
    QTextEdit,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from models.tts.voice_pack import (
    AUDIO_SAMPLE_EXTENSIONS,
    IMPORT_SAMPLE_EXTENSIONS,
    VOICE_PACK_LANGUAGE_PRESETS,
    create_imported_voice_pack,
)
from models.tts.voice_style_pack import (
    DEFAULT_STYLE_PACK_ID,
    normalize_voice_style_pack_id,
    resolve_voice_style_pack_settings,
    voice_style_pack_by_id,
    voice_style_pack_choices,
)
from models.tts.long_text_reader import (
    BOOK_FILE_DIALOG_FILTER,
    BookDocument,
    combine_documents,
    read_book_files,
)
from models.tts.language_match import (
    detect_text_language,
    language_from_edge_voice,
    language_label,
    normalize_language_id,
)
from utils.config import config
from utils.logger import get_logger

# ---------------------------------------------------------------------------
# 样式常量
# ---------------------------------------------------------------------------

GLASS_FRAME = """
QFrame#glass {{
    background-color: rgba(255, 255, 255, 248);
    border: 1px solid rgba(226, 232, 240, 220);
    border-radius: {radius}px;
}}
"""

D_ACTION_CODES = ("happy", "sad", "hungry", "angry", "idle")
D_ACTION_LABELS = {
    "happy": "开心",
    "sad": "伤心",
    "hungry": "吃饭",
    "angry": "生气",
    "idle": "待机",
}


def _glass_style(radius: int) -> str:
    return GLASS_FRAME.format(radius=radius)

BTN_GLASS = """
QPushButton {
    background-color: rgba(255, 255, 255, 230);
    border: 1px solid rgba(226, 232, 240, 200);
    border-radius: 12px;
    padding: 8px 14px;
    color: #23232d;
}
QPushButton:hover {
    background-color: rgba(220, 235, 255, 230);
}
"""

BTN_PRIMARY = """
QPushButton {
    background-color: #1e293b;
    color: white;
    border: none;
    border-radius: 12px;
    padding: 8px 14px;
}
QPushButton:hover { background-color: #334155; }
"""

BTN_ICON = """
QPushButton {
    background-color: transparent;
    border: none;
    border-radius: 12px;
    padding: 2px;
}
QPushButton:hover {
    background-color: rgba(255, 228, 236, 210);
}
QPushButton:pressed {
    background-color: rgba(255, 208, 220, 230);
}
"""

BTN_SWITCH = """
QPushButton#switchPetBtn {
    background-color: #7c3aed;
    color: white;
    border: none;
    border-radius: 12px;
    padding: 10px 22px;
    font-weight: bold;
}
QPushButton#switchPetBtn:hover {
    background-color: #6d28d9;
}
QPushButton#switchPetBtn:pressed {
    background-color: #5b21b6;
}
"""

DEFAULT_TTS_UI_SETTINGS: dict[str, Any] = {
    "enabled": True,
    "provider": "auto",
    "quality": "basic",
    "edge_voice": "",
    "response_language": "",
    "voice_style_pack": DEFAULT_STYLE_PACK_ID,
    "voice_style_pack_enabled": True,
    "edge_playback_guard": True,
    "text_normalizer": "",
    "prosody_style": "",
    "voice_style_pack_locks_prosody": True,
    "voice_profile": "default",
    "emotion_style": "auto",
    "cute_style": True,
    "voice_pack_mode": "off",
    "edge_rate": "",
    "edge_pitch": "",
    "edge_volume": "",
    "openvoice_enabled": False,
    "openvoice_python": "",
    "openvoice_repo_dir": "",
    "openvoice_checkpoint_dir": "",
    "openvoice_device": "auto",
    "tts_rate": "",
    "tts_volume": "",
}

DEFAULT_PET_PERSONALIZATION_SETTINGS: dict[str, dict[str, Any]] = {
    "speech_style": {
        "tone": "朋友感",
        "nickname": "用户",
        "catchphrase": "我在呢",
        "use_emoji": True,
    },
    "interaction_frequency": {
        "proactive_level": 45,
        "quiet_when_busy": True,
        "quiet_hours": "23:00-08:00",
    },
    "desktop_access": {
        "foreground_observation_authorized": False,
        "proactive_comment_enabled": True,
        "include_window_title": True,
        "comment_interval_seconds": 150,
    },
    "appearance_actions": {
        "theme_color": "樱花粉",
        "idle_action": "轻轻晃动",
        "transparency": 92,
    },
    "companion_mode": {
        "mode": "学习陪伴",
        "auto_switch": True,
        "focus_silence": True,
    },
    "emotion_system": {
        "enable_emotion": True,
        "mood_sensitivity": 60,
        "intimacy_growth": 50,
    },
    "reminders": {
        "water": True,
        "rest": True,
        "pomodoro": False,
        "meal": False,
        "sleep": True,
        "style": "温柔提醒",
    },
    "memory_relationship": {
        "relationship": "朋友",
        "remember_preferences": True,
        "remember_projects": True,
        "user_title": "用户",
    },
    "voice_expression": {
        "voice_enabled": True,
        "voice_style": "台湾口音",
        "speech_rate": 55,
        "bubble_density": 50,
    },
    "desktop_behavior": {
        "activity_range": "屏幕边缘和空白处",
        "avoid_windows": True,
        "follow_mouse": False,
        "multi_screen": True,
    },
    "boundaries": {
        "no_disturb_when_fullscreen": True,
        "safe_topics": "不过度亲密、不讨论隐私",
        "comfort_level": "轻度安慰",
        "allow_close_expression": False,
    },
}

PET_PERSONALIZATION_SECTIONS: tuple[dict[str, Any], ...] = (
    {
        "key": "speech_style",
        "icon": "💬",
        "title": "说话风格",
        "summary": "称呼、口头禅、语气和表情使用。",
        "fields": (
            {"key": "tone", "label": "语气模板", "type": "combo", "options": ("朋友感", "温柔撒娇", "电子管家", "毒舌吐槽", "恋人陪伴")},
            {"key": "nickname", "label": "怎么称呼你", "type": "line", "placeholder": "用户 / 主人 / 同学"},
            {"key": "catchphrase", "label": "口头禅", "type": "line", "placeholder": "我在呢"},
            {"key": "use_emoji", "label": "表情符号", "type": "check", "text": "允许使用"},
        ),
    },
    {
        "key": "interaction_frequency",
        "icon": "⏱️",
        "title": "互动频率",
        "summary": "主动打招呼、安静时段和忙碌时的打扰程度。",
        "fields": (
            {"key": "proactive_level", "label": "主动程度", "type": "slider", "min": 0, "max": 100, "suffix": "%"},
            {"key": "quiet_when_busy", "label": "忙碌识别", "type": "check", "text": "检测到忙碌时少打扰"},
            {"key": "quiet_hours", "label": "安静时段", "type": "combo", "options": ("无", "22:00-07:00", "23:00-08:00", "00:00-09:00")},
        ),
    },
    {
        "key": "desktop_access",
        "icon": "🔐",
        "title": "桌面授权",
        "summary": "授权后仅读取前台应用和窗口标题，用来判断你正在做什么。",
        "fields": (
            {"key": "foreground_observation_authorized", "label": "前台观察", "type": "check", "text": "允许读取前台应用"},
            {"key": "proactive_comment_enabled", "label": "主动聊天", "type": "check", "text": "偶尔聊当前正在做的事"},
            {"key": "include_window_title", "label": "窗口标题", "type": "check", "text": "允许作为聊天上下文"},
            {"key": "comment_interval_seconds", "label": "最短间隔", "type": "slider", "min": 30, "max": 900, "suffix": "秒"},
        ),
    },
    {
        "key": "appearance_actions",
        "icon": "🎀",
        "title": "外观与动作",
        "summary": "颜色主题、透明度、待机动作和被点击时的表现。",
        "fields": (
            {"key": "theme_color", "label": "颜色主题", "type": "combo", "options": ("樱花粉", "薄荷绿", "天空蓝", "暖阳橙", "极简灰")},
            {"key": "idle_action", "label": "待机动作", "type": "combo", "options": ("轻轻晃动", "原地眨眼", "小步走动", "贴边休息", "安静站立")},
            {"key": "transparency", "label": "不透明度", "type": "slider", "min": 30, "max": 100, "suffix": "%"},
        ),
    },
    {
        "key": "companion_mode",
        "icon": "🧭",
        "title": "陪伴模式",
        "summary": "工作、学习、摸鱼、睡前和游戏陪伴的行为模式。",
        "fields": (
            {"key": "mode", "label": "默认模式", "type": "combo", "options": ("工作陪伴", "学习陪伴", "摸鱼搭子", "睡前陪伴", "游戏陪伴")},
            {"key": "auto_switch", "label": "模式切换", "type": "check", "text": "允许自动切换"},
            {"key": "focus_silence", "label": "专注保护", "type": "check", "text": "专注时减少气泡"},
        ),
    },
    {
        "key": "emotion_system",
        "icon": "💗",
        "title": "情绪系统",
        "summary": "心情、精力、亲密度的响应强度。",
        "fields": (
            {"key": "enable_emotion", "label": "情绪状态", "type": "check", "text": "启用"},
            {"key": "mood_sensitivity", "label": "心情敏感度", "type": "slider", "min": 0, "max": 100, "suffix": "%"},
            {"key": "intimacy_growth", "label": "亲密度成长", "type": "slider", "min": 0, "max": 100, "suffix": "%"},
        ),
    },
    {
        "key": "reminders",
        "icon": "🔔",
        "title": "提醒偏好",
        "summary": "喝水、休息、番茄钟、吃饭和睡觉提醒。",
        "fields": (
            {"key": "water", "label": "喝水", "type": "check", "text": "开启"},
            {"key": "rest", "label": "休息", "type": "check", "text": "开启"},
            {"key": "pomodoro", "label": "番茄钟", "type": "check", "text": "开启"},
            {"key": "meal", "label": "吃饭", "type": "check", "text": "开启"},
            {"key": "sleep", "label": "睡觉", "type": "check", "text": "开启"},
            {"key": "style", "label": "提醒语气", "type": "combo", "options": ("温柔提醒", "严格督促", "搞笑吐槽", "安静弹窗")},
        ),
    },
    {
        "key": "memory_relationship",
        "icon": "🧠",
        "title": "记忆与关系",
        "summary": "关系定位、称呼、偏好和项目记忆。",
        "fields": (
            {"key": "relationship", "label": "关系定位", "type": "combo", "options": ("朋友", "搭档", "管家", "姐姐感", "妹妹感", "损友")},
            {"key": "user_title", "label": "用户称呼", "type": "line", "placeholder": "用户"},
            {"key": "remember_preferences", "label": "偏好记忆", "type": "check", "text": "记住"},
            {"key": "remember_projects", "label": "项目记忆", "type": "check", "text": "记住"},
        ),
    },
    {
        "key": "voice_expression",
        "icon": "🎙️",
        "title": "声音与表达",
        "summary": "语音开关、音色风格、语速和气泡密度。",
        "fields": (
            {"key": "voice_enabled", "label": "语音播报", "type": "check", "text": "开启"},
            {"key": "voice_style", "label": "声音风格", "type": "combo", "options": ("台湾口音", "自然音", "甜妹音", "御姐音", "主宰音", "霸总音", "温柔姐姐音", "少年音", "毒舌音", "自然可爱", "温柔安静", "元气活泼", "冷静可靠", "轻微毒舌")},
            {"key": "speech_rate", "label": "语速", "type": "slider", "min": 0, "max": 100, "suffix": "%"},
            {"key": "bubble_density", "label": "气泡密度", "type": "slider", "min": 0, "max": 100, "suffix": "%"},
        ),
    },
    {
        "key": "desktop_behavior",
        "icon": "🖥️",
        "title": "桌面行为",
        "summary": "活动范围、避让窗口、跟随鼠标和多屏移动。",
        "fields": (
            {"key": "activity_range", "label": "活动范围", "type": "combo", "options": ("屏幕边缘和空白处", "只在当前屏幕", "固定在角落", "跟随活跃窗口")},
            {"key": "avoid_windows", "label": "窗口避让", "type": "check", "text": "开启"},
            {"key": "follow_mouse", "label": "跟随鼠标", "type": "check", "text": "开启"},
            {"key": "multi_screen", "label": "多屏移动", "type": "check", "text": "允许"},
        ),
    },
    {
        "key": "boundaries",
        "icon": "🛡️",
        "title": "边界设置",
        "summary": "不打扰、话题边界、安慰尺度和亲密表达。",
        "fields": (
            {"key": "no_disturb_when_fullscreen", "label": "全屏不打扰", "type": "check", "text": "开启"},
            {"key": "safe_topics", "label": "话题边界", "type": "line", "placeholder": "不过度亲密、不讨论隐私"},
            {"key": "comfort_level", "label": "安慰尺度", "type": "combo", "options": ("只给建议", "轻度安慰", "明显关心", "高亲密陪伴")},
            {"key": "allow_close_expression", "label": "亲密表达", "type": "check", "text": "允许更亲近的表达"},
        ),
    },
)

TTS_QUALITY_PRESETS: tuple[dict[str, Any], ...] = (
    {
        "id": "basic",
        "label": "基础语音合成",
        "provider": "auto",
        "enabled": True,
    },
    {
        "id": "neural",
        "label": "高拟真神经语音",
        "provider": "edge",
        "enabled": True,
    },
    {
        "id": "openvoice",
        "label": "OpenVoice 声纹增强",
        "provider": "edge",
        "enabled": True,
        "openvoice_enabled": True,
    },
    {
        "id": "gpt_sovits",
        "label": "GPT-SoVITS 专属克隆语音",
        "provider": "gpt-sovits",
        "enabled": True,
    },
    {
        "id": "offline",
        "label": "离线语音",
        "provider": "pyttsx3",
        "enabled": True,
    },
    {
        "id": "off",
        "label": "关闭语音",
        "provider": "off",
        "enabled": False,
    },
)

TTS_VOICE_PRESETS: tuple[tuple[str, str], ...] = (
    ("跟随语音包 / 默认", ""),
    ("中文女声 Xiaoyi", "zh-CN-XiaoyiNeural"),
    ("中文女声 Xiaoxiao", "zh-CN-XiaoxiaoNeural"),
    ("中文女声 Xiaomo", "zh-CN-XiaomoNeural"),
    ("中文男声 Yunxi", "zh-CN-YunxiNeural"),
    ("粤语女声 HiuGaai", "zh-HK-HiuGaaiNeural"),
    ("英语女声 Jenny（美音）", "en-US-JennyNeural"),
    ("英语男声 Guy（美音）", "en-US-GuyNeural"),
    ("英语女声 Sonia（英音）", "en-GB-SoniaNeural"),
    ("英语男声 Ryan（英音）", "en-GB-RyanNeural"),
    ("法语女声 Denise", "fr-FR-DeniseNeural"),
    ("法语男声 Henri", "fr-FR-HenriNeural"),
    ("德语女声 Katja", "de-DE-KatjaNeural"),
    ("德语男声 Conrad", "de-DE-ConradNeural"),
    ("西班牙语女声 Elvira", "es-ES-ElviraNeural"),
    ("西班牙语男声 Alvaro", "es-ES-AlvaroNeural"),
    ("墨西哥西语女声 Dalia", "es-MX-DaliaNeural"),
    ("意大利语女声 Elsa", "it-IT-ElsaNeural"),
    ("葡萄牙语女声 Francisca", "pt-BR-FranciscaNeural"),
    ("俄语女声 Svetlana", "ru-RU-SvetlanaNeural"),
    ("荷兰语女声 Colette", "nl-NL-ColetteNeural"),
    ("印地语女声 Swara", "hi-IN-SwaraNeural"),
    ("阿拉伯语女声 Salma", "ar-EG-SalmaNeural"),
    ("日文女声 Nanami", "ja-JP-NanamiNeural"),
    ("韩文女声 SunHi", "ko-KR-SunHiNeural"),
)

TTS_STYLE_PRESETS: tuple[dict[str, Any], ...] = (
    {"id": "auto", "label": "自动跟随情绪", "voice_profile": "default", "cute_style": True},
    {"id": "neutral", "label": "自然", "voice_profile": "default", "cute_style": False},
    {"id": "cheerful", "label": "开心活泼", "voice_profile": "cute", "cute_style": True},
    {"id": "comfort", "label": "温柔安抚", "voice_profile": "calm", "cute_style": False},
    {"id": "serious", "label": "严肃专业", "voice_profile": "default", "cute_style": False},
    {"id": "story", "label": "故事旁白", "voice_profile": "default", "cute_style": False},
    {"id": "news", "label": "新闻播报", "voice_profile": "default", "cute_style": False},
)


def normalize_tts_settings(settings: dict[str, Any] | None) -> dict[str, Any]:
    data = dict(DEFAULT_TTS_UI_SETTINGS)
    if isinstance(settings, dict):
        for key in data:
            if key in settings:
                data[key] = settings[key]
        if not data.get("response_language"):
            data["response_language"] = (
                settings.get("reply_language")
                or settings.get("language")
                or settings.get("lang")
                or ""
            )

    data["enabled"] = bool(data.get("enabled", True))
    data["provider"] = str(data.get("provider") or "auto").strip().lower().replace("_", "-")
    if data["provider"] in {"gptsovits", "sovits", "voice-clone"}:
        data["provider"] = "gpt-sovits"
    if data["provider"] in {"disabled", "none", "false"}:
        data["provider"] = "off"
    data["quality"] = str(data.get("quality") or "").strip().lower()
    if data["provider"] == "off":
        data["quality"] = "off"
        data["enabled"] = False
    if data["quality"] not in {str(p["id"]) for p in TTS_QUALITY_PRESETS}:
        if data["provider"] in {"edge", "edge-tts", "neural", "edge-neural", "high-realism"}:
            data["quality"] = "neural"
        elif data["provider"] in {"gpt-sovits", "gptsovits", "sovits", "voice-clone"}:
            data["quality"] = "gpt_sovits"
        elif data["provider"] in {"pyttsx3", "offline", "local"}:
            data["quality"] = "offline"
        else:
            data["quality"] = "basic"
    if data["quality"] == "openvoice":
        data["provider"] = "edge"
        data["enabled"] = True
        data["openvoice_enabled"] = True
    elif data["quality"] == "gpt_sovits":
        data["provider"] = "gpt-sovits"
        data["enabled"] = True
        data["openvoice_enabled"] = False
    else:
        data["openvoice_enabled"] = str(
            data.get("openvoice_enabled", False)
        ).strip().lower() in {"1", "true", "yes", "y", "on", "开启", "启用"}
    data["edge_voice"] = str(data.get("edge_voice") or "").strip()
    data["response_language"] = normalize_language_id(data.get("response_language"))
    data["voice_style_pack"] = normalize_voice_style_pack_id(data.get("voice_style_pack"))
    data["voice_style_pack_enabled"] = str(
        data.get("voice_style_pack_enabled", False)
    ).strip().lower() not in {"0", "false", "no", "off"}
    data["emotion_style"] = str(data.get("emotion_style") or "").strip().lower()
    if not data["emotion_style"]:
        legacy_profile = str(data.get("voice_profile") or "default").strip().lower()
        data["emotion_style"] = {
            "cute": "cheerful",
            "calm": "comfort",
        }.get(legacy_profile, "auto")
    valid_styles = {str(p["id"]) for p in TTS_STYLE_PRESETS}
    if data["emotion_style"] not in valid_styles:
        data["emotion_style"] = "auto"
    preset = next((p for p in TTS_STYLE_PRESETS if str(p["id"]) == data["emotion_style"]), TTS_STYLE_PRESETS[0])
    data["voice_profile"] = str(preset.get("voice_profile") or data.get("voice_profile") or "default").strip() or "default"
    data["cute_style"] = bool(data.get("cute_style"))
    if "cute_style" in preset:
        data["cute_style"] = bool(preset["cute_style"])
    if data.get("voice_style_pack_enabled", False):
        if not data.get("response_language"):
            data["response_language"] = language_from_edge_voice(config.EDGE_TTS_VOICE) or "zh-CN"
        style_settings = resolve_voice_style_pack_settings(data.get("voice_style_pack"), data.get("response_language"))
        data["voice_style_pack"] = str(style_settings.get("voice_style_pack") or DEFAULT_STYLE_PACK_ID)
        data["edge_voice"] = ""
        data["voice_pack_mode"] = "off"
        for key in (
            "edge_rate",
            "edge_pitch",
            "edge_volume",
            "edge_playback_guard",
            "text_normalizer",
            "prosody_style",
            "voice_style_pack_locks_prosody",
        ):
            if style_settings.get("voice_style_pack_locks_prosody", True) or not str(data.get(key) or "").strip():
                data[key] = style_settings.get(key, data.get(key, ""))
        data["voice_profile"] = str(style_settings.get("voice_profile") or data.get("voice_profile") or "default")
        data["cute_style"] = bool(style_settings.get("cute_style", data.get("cute_style", False)))
    data["voice_pack_mode"] = str(data.get("voice_pack_mode") or "prefer").strip().lower() or "prefer"
    for key in (
        "edge_rate",
        "edge_pitch",
        "edge_volume",
        "openvoice_python",
        "openvoice_repo_dir",
        "openvoice_checkpoint_dir",
        "openvoice_device",
        "tts_rate",
        "tts_volume",
        "text_normalizer",
        "prosody_style",
    ):
        data[key] = str(data.get(key) or "").strip()
    return data


def _parse_signed_int_setting(value: Any, default: str = "+0") -> int:
    raw = str(value or default).strip()
    raw = raw.replace("Hz", "").replace("%", "").strip()
    try:
        return int(round(float(raw)))
    except ValueError:
        return 0


def _parse_tts_rate_setting(value: Any) -> int:
    raw = str(value or os.getenv("TTS_RATE", "168")).strip()
    try:
        return max(80, min(260, int(round(float(raw)))))
    except ValueError:
        return 168


def _parse_tts_volume_setting(value: Any) -> int:
    raw = str(value or os.getenv("TTS_VOLUME", "0.95")).strip()
    try:
        number = float(raw)
    except ValueError:
        number = 0.95
    if number <= 1:
        number *= 100
    return max(0, min(100, int(round(number))))


def _signed_percent(value: int) -> str:
    return f"{int(value):+d}%"


def _signed_hz(value: int) -> str:
    return f"{int(value):+d}Hz"


def _scaled_int(value: float, scale: float, minimum: int = 1) -> int:
    return max(minimum, int(round(value * scale)))


class ScalableOverlay:
    """桌宠窗口缩小时，overlay 控件按比例缩放。"""

    _ui_scale: float = 1.0

    def apply_ui_scale(self, scale: float) -> None:
        self._ui_scale = max(0.28, min(1.25, scale))


def _app_font(size: int, bold: bool = False) -> QFont:
    if sys.platform == "win32":
        for name in ("Microsoft YaHei UI", "Microsoft YaHei", "SimHei", "Arial"):
            if QFontDatabase.hasFamily(name):
                f = QFont(name, size)
                f.setBold(bold)
                return f
    f = QFont("Arial", size)
    f.setBold(bold)
    return f


def _load_pixmap(path: str, size: QSize | None = None) -> QPixmap:
    pm = QPixmap(path) if path and os.path.isfile(path) else QPixmap()
    if pm.isNull():
        pm = QPixmap(size or QSize(64, 64))
        pm.fill(QColor(220, 230, 255))
    elif size:
        pm = pm.scaled(size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    return pm


# ---------------------------------------------------------------------------
# 右键菜单 & 二级菜单（自绘 overlay）
# ---------------------------------------------------------------------------


class ConsoleDragBar(QFrame):
    """设置面板顶部标题栏：可拖拽移动窗口。"""

    def __init__(self, window: QMainWindow, title: str = "桌面宠物控制台") -> None:
        super().__init__()
        self._window = window
        self._dragging = False
        self._drag_offset = QPoint()
        self.setObjectName("consoleDragBar")
        self.setFixedHeight(40)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 6, 8, 6)
        self._title_lbl = QLabel(title)
        self._title_lbl.setFont(_app_font(14, True))
        lay.addWidget(self._title_lbl, 1)
        for label, slot in (
            ("—", window.showMinimized),
            ("□", getattr(window, "_toggle_max", window.showMaximized)),
            ("×", window.close),
        ):
            b = QPushButton(label)
            b.setFixedSize(28, 28)
            b.clicked.connect(slot)
            lay.addWidget(b)
        self.setStyleSheet(
            "QFrame#consoleDragBar { background: rgba(255,255,255,235);"
            " border-bottom: 1px solid rgba(226,232,240,200); }"
        )

    def _is_drag_area(self, pos: QPoint) -> bool:
        child = self.childAt(pos)
        if child is None or child is self._title_lbl:
            return True
        return False

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._is_drag_area(
            event.position().toPoint()
        ):
            self._dragging = True
            self._drag_offset = event.globalPosition().toPoint() - self._window.frameGeometry().topLeft()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging and event.buttons() & Qt.MouseButton.LeftButton:
            self._window.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._dragging = False
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)


class RightClickMenu(QFrame, ScalableOverlay):
    ITEMS = (
        "状态栏",
        "AI对话",
        "设置面板",
        "动作展示",
        "待机",
        "置顶设置",
        "悬停淡出",
        "退出",
        "关闭",
    )
    _BASE_WIDTH = 200
    _BASE_ITEM_HEIGHT = 40
    _BASE_PADDING = 8
    WIDTH = 200
    ITEM_HEIGHT = 40
    PADDING = 8
    item_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("glass")
        self.setStyleSheet(_glass_style(16))
        self.visible = False
        self.x = self.y = 0
        self.hover_index = -1
        self._selected: Optional[str] = None
        self._font = _app_font(16)
        self._corner_radius = 16
        self.setMouseTracking(True)
        self.hide()

    def apply_ui_scale(self, scale: float) -> None:
        super().apply_ui_scale(scale)
        self.WIDTH = _scaled_int(self._BASE_WIDTH, self._ui_scale, 120)
        self.ITEM_HEIGHT = _scaled_int(self._BASE_ITEM_HEIGHT, self._ui_scale, 28)
        self.PADDING = _scaled_int(self._BASE_PADDING, self._ui_scale, 4)
        px = _scaled_int(16, self._ui_scale, 11)
        self._font = _app_font(px)
        self._corner_radius = _scaled_int(16, self._ui_scale, 10)
        self.setStyleSheet(_glass_style(self._corner_radius))
        if self.visible:
            h = self.PADDING * 2 + len(self.ITEMS) * self.ITEM_HEIGHT
            self.setGeometry(self.x, self.y, self.WIDTH, h)

    @property
    def rect(self) -> QRect:
        return self.geometry()

    def show(self, x: int, y: int) -> None:
        self.x, self.y = x, y
        h = self.PADDING * 2 + len(self.ITEMS) * self.ITEM_HEIGHT
        self.setGeometry(x, y, self.WIDTH, h)
        self.visible = True
        self.hover_index = -1
        self._selected = None
        self.raise_()
        super().show()

    def hide(self) -> None:
        self.visible = False
        self.hover_index = -1
        super().hide()

    def update_hover(self, mouse_pos: tuple[int, int]) -> None:
        if not self.visible:
            self.hover_index = -1
            return
        self.hover_index = -1
        if not self.rect.contains(QPoint(*mouse_pos)):
            return
        local_y = mouse_pos[1] - self.y - self.PADDING
        idx = local_y // self.ITEM_HEIGHT
        if 0 <= idx < len(self.ITEMS):
            self.hover_index = int(idx)
        self.repaint()

    def handle_click(self, mouse_pos: tuple[int, int]) -> Optional[str]:
        if not self.visible:
            return None
        self.update_hover(mouse_pos)
        if self.hover_index < 0:
            return None
        self._selected = self.ITEMS[self.hover_index]
        return self._selected

    def item_rect(self, index: int) -> QRect:
        return QRect(
            self.x,
            self.y + self.PADDING + index * self.ITEM_HEIGHT,
            self.WIDTH,
            self.ITEM_HEIGHT,
        )

    def _index_at(self, local_y: float) -> int:
        idx = int((local_y - self.PADDING) // self.ITEM_HEIGHT)
        if 0 <= idx < len(self.ITEMS):
            return idx
        return -1

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.visible:
            self.hover_index = self._index_at(event.position().y())
            self.repaint()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.visible:
            idx = self._index_at(event.position().y())
            if idx >= 0:
                self._selected = self.ITEMS[idx]
                self.item_selected.emit(self._selected)
                event.accept()
                return
        super().mousePressEvent(event)

    def paintEvent(self, _event) -> None:
        if not self.visible:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setFont(self._font)
        bg = QPainterPath()
        r = float(self._corner_radius)
        bg.addRoundedRect(QRectF(0, 0, self.width(), self.height()), r, r)
        p.fillPath(bg, QColor(255, 255, 255, 248))
        p.setPen(QPen(QColor(226, 232, 240, 220), 1))
        p.drawPath(bg)
        pad_l = _scaled_int(16, self._ui_scale, 10)
        hover_r = _scaled_int(8, self._ui_scale, 5)
        for i, label in enumerate(self.ITEMS):
            item_r = QRect(0, self.PADDING + i * self.ITEM_HEIGHT, self.WIDTH, self.ITEM_HEIGHT)
            if i == self.hover_index:
                path = QPainterPath()
                path.addRoundedRect(QRectF(item_r.adjusted(4, 2, -4, -2)), hover_r, hover_r)
                p.fillPath(path, QColor(220, 235, 255, 230))
            p.setPen(QColor(35, 35, 45))
            p.drawText(item_r.adjusted(pad_l, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, label)
        p.end()


class SubMenu(QFrame, ScalableOverlay):
    _BASE_WIDTH = 160
    _BASE_ITEM_HEIGHT = 36
    _BASE_PADDING = 6
    WIDTH = 160
    ITEM_HEIGHT = 36
    PADDING = 6
    item_selected = Signal(str)

    def __init__(
        self,
        items: tuple[str, ...] = ("开始置顶", "关闭置顶"),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.ITEMS = items
        self.setObjectName("glass")
        self.setStyleSheet(_glass_style(12))
        self.visible = False
        self.x = self.y = 0
        self.hover_index = -1
        self._selected: Optional[str] = None
        self.active_index = 1
        self._font = _app_font(15)
        self._corner_radius = 12
        self.setMouseTracking(True)
        self.hide()

    def apply_ui_scale(self, scale: float) -> None:
        super().apply_ui_scale(scale)
        self.WIDTH = _scaled_int(self._BASE_WIDTH, self._ui_scale, 100)
        self.ITEM_HEIGHT = _scaled_int(self._BASE_ITEM_HEIGHT, self._ui_scale, 26)
        self.PADDING = _scaled_int(self._BASE_PADDING, self._ui_scale, 4)
        self._font = _app_font(_scaled_int(15, self._ui_scale, 10))
        self._corner_radius = _scaled_int(12, self._ui_scale, 8)
        self.setStyleSheet(_glass_style(self._corner_radius))
        if self.visible:
            h = self.PADDING * 2 + len(self.ITEMS) * self.ITEM_HEIGHT
            self.setGeometry(self.x, self.y, self.WIDTH, h)

    @property
    def rect(self) -> QRect:
        return self.geometry()

    def set_active(self, enabled: bool) -> None:
        self.active_index = 0 if enabled else 1

    def show(self, x: int, y: int) -> None:
        self.x, self.y = x, y
        h = self.PADDING * 2 + len(self.ITEMS) * self.ITEM_HEIGHT
        self.setGeometry(x, y, self.WIDTH, h)
        self.visible = True
        self.hover_index = -1
        self._selected = None
        self.raise_()
        super().show()

    def hide(self) -> None:
        self.visible = False
        self.hover_index = -1
        super().hide()

    def update_hover(self, mouse_pos: tuple[int, int]) -> None:
        if not self.visible:
            self.hover_index = -1
            return
        self.hover_index = -1
        if not self.rect.contains(QPoint(*mouse_pos)):
            return
        local_y = mouse_pos[1] - self.y - self.PADDING
        idx = local_y // self.ITEM_HEIGHT
        if 0 <= idx < len(self.ITEMS):
            self.hover_index = int(idx)
        self.repaint()

    def handle_click(self, mouse_pos: tuple[int, int]) -> Optional[str]:
        if not self.visible:
            return None
        self.update_hover(mouse_pos)
        if self.hover_index < 0:
            return None
        if self.hover_index == self.active_index:
            return None
        self._selected = self.ITEMS[self.hover_index]
        self.active_index = self.hover_index
        return self._selected

    def _index_at(self, local_y: float) -> int:
        idx = int((local_y - self.PADDING) // self.ITEM_HEIGHT)
        if 0 <= idx < len(self.ITEMS):
            return idx
        return -1

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.visible:
            self.hover_index = self._index_at(event.position().y())
            self.repaint()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.visible:
            idx = self._index_at(event.position().y())
            if idx >= 0 and idx != self.active_index:
                self._selected = self.ITEMS[idx]
                self.active_index = idx
                self.item_selected.emit(self._selected)
                self.repaint()
                event.accept()
                return
        super().mousePressEvent(event)

    def paintEvent(self, _event) -> None:
        if not self.visible:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setFont(self._font)
        bg = QPainterPath()
        r = float(self._corner_radius)
        bg.addRoundedRect(QRectF(0, 0, self.width(), self.height()), r, r)
        p.fillPath(bg, QColor(255, 255, 255, 248))
        p.setPen(QPen(QColor(226, 232, 240, 220), 1))
        p.drawPath(bg)
        pad_l = _scaled_int(12, self._ui_scale, 8)
        hover_r = _scaled_int(8, self._ui_scale, 5)
        for i, label in enumerate(self.ITEMS):
            item_r = QRect(0, self.PADDING + i * self.ITEM_HEIGHT, self.WIDTH, self.ITEM_HEIGHT)
            color = QColor(150, 150, 160) if i == self.active_index else QColor(35, 35, 45)
            if i == self.hover_index and i != self.active_index:
                path = QPainterPath()
                path.addRoundedRect(QRectF(item_r.adjusted(4, 2, -4, -2)), hover_r, hover_r)
                p.fillPath(path, QColor(220, 235, 255, 230))
            p.setPen(color)
            p.drawText(item_r.adjusted(pad_l, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, label)
        p.end()


# ---------------------------------------------------------------------------
# 弧形动作菜单
# ---------------------------------------------------------------------------


def _ease_out_back(t: float) -> float:
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    c1, c3 = 1.70158, 2.70158
    return 1.0 + c3 * (t - 1.0) ** 3 + c1 * (t - 1.0) ** 2


class ArcMotionMenu(QWidget, ScalableOverlay):
    _BASE_RADIUS = 170
    _BASE_BUTTON_SIZE = 52
    _BASE_RING_GAP = 85
    RADIUS = 170
    BUTTON_SIZE = 52
    RING_GAP = 85
    MAX_ITEMS_PER_RING = 9
    MIN_BUTTON_GAP = 12
    HOVER_SCALE = 1.1
    ANIM_DURATION = 0.42
    STAGGER = 0.045

    picked = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.visible = False
        self.center_x = self.center_y = 0
        self.items: list[dict[str, Any]] = []
        self.hover_index = -1
        self._selected: Optional[dict[str, Any]] = None
        self._elapsed = 0.0
        self._font = _app_font(12)
        self.hide()

    def apply_ui_scale(self, scale: float) -> None:
        super().apply_ui_scale(scale)
        self.RADIUS = _scaled_int(self._BASE_RADIUS, self._ui_scale, 60)
        self.BUTTON_SIZE = _scaled_int(self._BASE_BUTTON_SIZE, self._ui_scale, 28)
        self.RING_GAP = _scaled_int(self._BASE_RING_GAP, self._ui_scale, 52)
        self._font = _app_font(_scaled_int(12, self._ui_scale, 9))

    def show_menu(self, center_x: int, center_y: int, items: list[dict[str, Any]]) -> None:
        self.center_x, self.center_y = center_x, center_y
        self.items = list(items)
        self.visible = True
        self.hover_index = -1
        self._elapsed = 0.0
        ring_count = len(self._rings())
        max_radius = self.RADIUS + max(0, ring_count - 1) * self.RING_GAP
        pad = max_radius + self.BUTTON_SIZE + 36
        self.setGeometry(center_x - pad, center_y - pad, pad * 2, pad * 2)
        super().show()
        self.raise_()

    def show(self, center_x: int, center_y: int, items: list[dict[str, Any]]) -> None:
        self.show_menu(center_x, center_y, items)

    def hide(self) -> None:
        self.visible = False
        super().hide()

    def tick(self, dt: float) -> None:
        if self.visible:
            self._elapsed += dt
            self.update()

    def _rings(self) -> list[list[int]]:
        """Group item indices into rings. Each ring has at most MAX_ITEMS_PER_RING items."""
        n = len(self.items)
        if n == 0:
            return []
        cap = self.MAX_ITEMS_PER_RING
        if n <= cap:
            return [list(range(n))]
        # Determine number of rings
        nrings = max(2, (n + cap - 1) // cap)
        # Distribute items as evenly as possible
        rings: list[list[int]] = [[] for _ in range(nrings)]
        for i in range(n):
            # Fill from outer rings inward, but keep order
            rings[i % nrings].append(i)
        return rings

    def _ring_for_index(self, index: int) -> tuple[int, int, int]:
        """Return (ring_index, index_in_ring, count_in_ring) for a given global index."""
        rings = self._rings()
        for ri, ring in enumerate(rings):
            if index in ring:
                return (ri, ring.index(index), len(ring))
        return (0, 0, 0)

    @staticmethod
    def _angle_deg_in_ring(index_in_ring: int, count_in_ring: int) -> float:
        if count_in_ring <= 1:
            return 0.0
        return -90.0 + 180.0 * index_in_ring / (count_in_ring - 1)

    def _angle_deg(self, index: int) -> float:
        _, idx_in_r, cnt_in_r = self._ring_for_index(index)
        return self._angle_deg_in_ring(idx_in_r, cnt_in_r)

    def _btn_center(self, index: int) -> tuple[int, int]:
        ring_index, idx_in_r, cnt_in_r = self._ring_for_index(index)
        radius = self.RADIUS + ring_index * self.RING_GAP
        deg = math.radians(self._angle_deg_in_ring(idx_in_r, cnt_in_r))
        x = self.center_x + int(radius * math.sin(deg))
        y = self.center_y - int(radius * math.cos(deg))
        return x - self.x(), y - self.y()

    def _pop_scale(self, index: int) -> float:
        start = index * self.STAGGER
        if self._elapsed < start:
            return 0.0
        return _ease_out_back(min(1.0, (self._elapsed - start) / self.ANIM_DURATION))

    def button_rect(self, index: int, hover: bool = False) -> QRect:
        pop = self._pop_scale(index)
        if pop <= 0.01:
            return QRect(0, 0, 0, 0)
        scale = pop * (self.HOVER_SCALE if hover else 1.0)
        size = max(4, int(self.BUTTON_SIZE * scale))
        cx, cy = self._btn_center(index)
        return QRect(cx - size // 2, cy - size // 2, size, size)

    def hit_region(self) -> QRect:
        if not self.items:
            return QRect()
        pts = [self._btn_center(i) for i in range(len(self.items))]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        ring_count = len(self._rings())
        max_radius = self.RADIUS + max(0, ring_count - 1) * self.RING_GAP
        pad = max_radius + self.BUTTON_SIZE
        return QRect(min(xs) - pad, min(ys) - pad, max(xs) - min(xs) + pad * 2, max(ys) - min(ys) + pad * 2)

    def hover_at(self, mouse_pos: tuple[int, int] | None = None) -> None:
        if not self.visible:
            self.hover_index = -1
            return
        lp = self.mapFromGlobal(QPoint(*mouse_pos)) if mouse_pos else None
        self.hover_index = -1
        if lp:
            pick = self._pick_item_at(lp)
            if pick is not None:
                for i, item in enumerate(self.items):
                    if item is pick:
                        self.hover_index = i
                        break
        QWidget.update(self)

    def update(self, mouse_pos: tuple[int, int] | None = None) -> None:
        self.hover_at(mouse_pos)

    def _pick_item_at(self, local_pos: QPoint) -> Optional[dict[str, Any]]:
        """Find the closest item near local_pos using distance-based picking."""
        candidates: list[tuple[int, int]] = []
        for i in range(len(self.items)):
            if self._pop_scale(i) <= 0.2:
                continue
            r = self.button_rect(i)
            if r.adjusted(-4, -4, 4, 4).contains(local_pos):
                cx, cy = self._btn_center(i)
                dx = local_pos.x() - cx
                dy = local_pos.y() - cy
                dist2 = dx * dx + dy * dy
                candidates.append((dist2, i))
        if not candidates:
            return None
        _, best_i = min(candidates)
        return self.items[best_i]

    def handle_click(self, mouse_pos: tuple[int, int]) -> Optional[dict[str, Any]]:
        lp = self.mapFromGlobal(QPoint(*mouse_pos))
        self.hover_index = -1
        pick = self._pick_item_at(lp)
        if pick is not None:
            self._selected = pick
            return pick
        return None

    def paintEvent(self, _event) -> None:
        if not self.visible:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setFont(self._font)
        for i, item in enumerate(self.items):
            pop = self._pop_scale(i)
            if pop <= 0.01:
                continue
            hovered = i == self.hover_index
            r = self.button_rect(i, hovered)
            path = QPainterPath()
            path.addEllipse(QRectF(r))
            p.fillPath(path, QColor(230, 240, 255, 220) if hovered else QColor(255, 255, 255, 180))
            label = str(item.get("label", ""))
            if len(label) > 5:
                label = label[:4] + "…"
            p.setPen(QColor(30, 30, 40))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, label)
        p.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        pick = self._pick_item_at(event.pos())
        if pick is not None:
            self._selected = pick
            self.picked.emit(pick)
            return
        self.hide()


RadialMenu = ArcMotionMenu


# ---------------------------------------------------------------------------
# 气泡 & 输入框
# ---------------------------------------------------------------------------


class InfoBubble(QFrame, ScalableOverlay):
    _BASE_MAX_WIDTH = 200

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("glass")
        self.setAutoFillBackground(True)
        self.setStyleSheet(_glass_style(14))
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.visible = False
        self.mood, self.energy, self.affection = 85, 72, 90
        self._max_outer_w = 0
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(12, 12, 12, 12)
        self._lbl = QLabel()
        self._lbl.setFont(_app_font(15))
        self._lbl.setWordWrap(True)
        self._lbl.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding
        )
        self._lay.addWidget(self._lbl)
        self.hide()

    def set_max_width(self, max_outer_w: int) -> None:
        self._max_outer_w = max(80, max_outer_w)
        self._sync_label_geometry()

    def _bubble_outer_width(self) -> int:
        base = _scaled_int(self._BASE_MAX_WIDTH, self._ui_scale, 100)
        if self._max_outer_w > 0:
            return min(base, self._max_outer_w)
        return base

    def _sync_label_geometry(self) -> None:
        margins = self._lay.contentsMargins()
        outer_w = self._bubble_outer_width()
        inner_w = max(60, outer_w - margins.left() - margins.right())
        self._lbl.setFixedWidth(inner_w)
        text_h = self._lbl.heightForWidth(inner_w)
        if text_h <= 0:
            self._lbl.adjustSize()
            text_h = self._lbl.sizeHint().height()
        h = text_h + margins.top() + margins.bottom() + 4
        self.setFixedSize(outer_w, max(h, _scaled_int(52, self._ui_scale, 36)))

    def apply_ui_scale(self, scale: float) -> None:
        super().apply_ui_scale(scale)
        m = _scaled_int(12, self._ui_scale, 6)
        self._lay.setContentsMargins(m, m, m, m)
        font_px = _scaled_int(15, self._ui_scale, 9)
        self._lbl.setFont(_app_font(font_px))
        self._lbl.setStyleSheet(
            f"font-size: {font_px}px; color: #23232d; background: transparent;"
        )
        self.setStyleSheet(_glass_style(_scaled_int(14, self._ui_scale, 8)))
        if self.visible:
            self._lbl.setText(
                f"心情❤️{self.mood}\n好感度⭐{self.affection}\n能量⚡{self.energy}"
            )
            self._sync_label_geometry()

    @property
    def rect(self) -> QRect:
        return self.geometry()

    def show(self, x: int, y: int) -> None:
        self._lbl.setText(
            f"心情❤️{self.mood}\n好感度⭐{self.affection}\n能量⚡{self.energy}"
        )
        self._sync_label_geometry()
        self.move(x, y)
        self.visible = True
        super().show()
        self.raise_()

    def hide(self) -> None:
        self.visible = False
        super().hide()


class ChatBubble(QFrame, ScalableOverlay):
    _BASE_WIDTH = 280
    _BASE_RADIUS = 20
    WIDTH = 280
    RADIUS = 20

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("glass")
        self.setStyleSheet(_glass_style(self.RADIUS))
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.visible = False
        self.text = ""
        self._max_outer_w = 0
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(14, 14, 14, 14)
        self._lbl = QLabel()
        self._lbl.setFont(_app_font(15))
        self._lbl.setWordWrap(True)
        self._lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._lbl.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding
        )
        self._lay.addWidget(self._lbl)
        self.hide()

    def set_max_width(self, max_outer_w: int) -> None:
        self._max_outer_w = max(100, max_outer_w)
        self._sync_label_geometry()

    def _bubble_outer_width(self) -> int:
        base = _scaled_int(self._BASE_WIDTH, self._ui_scale, 120)
        if self._max_outer_w > 0:
            return min(base, self._max_outer_w)
        return base

    def _sync_label_geometry(self) -> None:
        margins = self._lay.contentsMargins()
        self.WIDTH = self._bubble_outer_width()
        inner_w = max(48, self.WIDTH - margins.left() - margins.right())
        self._lbl.setFixedWidth(inner_w)
        text_h = self._lbl.heightForWidth(inner_w)
        if text_h <= 0:
            self._lbl.adjustSize()
            text_h = self._lbl.sizeHint().height()
        total_h = text_h + margins.top() + margins.bottom() + 4
        self.setFixedSize(self.WIDTH, max(total_h, _scaled_int(36, self._ui_scale, 28)))

    def apply_ui_scale(self, scale: float) -> None:
        super().apply_ui_scale(scale)
        self.RADIUS = _scaled_int(self._BASE_RADIUS, self._ui_scale, 10)
        m = _scaled_int(14, self._ui_scale, 6)
        self._lay.setContentsMargins(m, m, m, m)
        font_px = _scaled_int(15, self._ui_scale, 9)
        self._lbl.setFont(_app_font(font_px))
        self._lbl.setStyleSheet(
            f"font-size: {font_px}px; color: #23232d; background: transparent;"
        )
        self.setStyleSheet(_glass_style(self.RADIUS))
        if self.text or self.visible:
            self._sync_label_geometry()

    @property
    def rect(self) -> QRect:
        return self.geometry()

    def set_text(self, text: str) -> None:
        self.text = text
        self._lbl.setText(text)
        self._sync_label_geometry()

    def show(self, x: int, y: int, text: str) -> None:
        self.set_text(text)
        self.move(x, y)
        self.visible = True
        super().show()
        self.raise_()

    def hide(self) -> None:
        self.visible = False
        super().hide()


def _make_mic_icon(color: str = "#64748b") -> QIcon:
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 2)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(QRectF(8, 3, 8, 11), 4, 4)
    path = QPainterPath()
    path.moveTo(5, 10)
    path.cubicTo(5, 16, 19, 16, 19, 10)
    painter.drawPath(path)
    painter.drawLine(12, 17, 12, 21)
    painter.drawLine(8, 21, 16, 21)
    painter.end()
    return QIcon(pixmap)


def _clean_voice_text(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


_VOICE_LOGGER = get_logger("VoiceInput")
_VOICE_INPUT_DEFAULT_LANGUAGES = ("zh-CN", "zh-TW", "en-US")
_VOICE_INPUT_SR_BACKENDS = {"google", "whisper"}


def _voice_input_list_env(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    values: list[str] = []
    seen: set[str] = set()
    for item in re.split(r"[,;|，；\s]+", raw):
        value = item.strip()
        key = value.lower()
        if value and key not in seen:
            values.append(value)
            seen.add(key)
    return tuple(values) or default


def _voice_input_float_env(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(os.getenv(name, "").strip() or default)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, value))


def _voice_input_backends() -> tuple[str, ...]:
    default = ("whisper", "google", "sapi") if os.getenv("VOICE_INPUT_WHISPER_MODEL", "").strip() else ("google", "sapi")
    values = _voice_input_list_env("VOICE_INPUT_BACKENDS", default)
    allowed = {"google", "sapi", "whisper"}
    backends = tuple(value.lower() for value in values if value.lower() in allowed)
    return backends or default


def _voice_input_languages() -> tuple[str, ...]:
    return _voice_input_list_env("VOICE_INPUT_LANGUAGES", _VOICE_INPUT_DEFAULT_LANGUAGES)


def _voice_error_summary(message: str) -> str:
    if any(keyword in message for keyword in ("SpeechRecognition", "speech_recognition", "PyAudio", "pyaudio")):
        return "语音输入缺少依赖，请安装 SpeechRecognition 和 PyAudio 后重启。"
    if any(keyword in message for keyword in ("麦克风", "Microphone", "Input Device", "输入设备")):
        return "无法打开麦克风，请检查系统权限和默认输入设备。"
    if "在线语音识别" in message or "在线 Google" in message:
        return "在线语音识别不可用，请检查网络或稍后再试。"
    if "Windows 本地识别" in message or "SAPI" in message or "类型不匹配" in message:
        return "Windows 本地语音识别不可用，请检查语音语言包和麦克风权限。"
    if "没有识别" in message or "没有听清" in message:
        return "没有识别到语音，请再试一次。"
    return message or "语音识别失败，请再试一次。"


def _load_speech_recognition():
    try:
        import speech_recognition as sr  # type: ignore
    except ImportError as exc:
        missing = getattr(exc, "name", "") or str(exc)
        if missing and missing != "speech_recognition":
            raise RuntimeError(f"SpeechRecognition 依赖缺失：{missing}。请重新安装语音输入依赖。") from exc
        raise RuntimeError("未安装 SpeechRecognition，无法启用语音输入。") from exc
    return sr


def _configure_voice_recognizer(recognizer: Any) -> None:
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = _voice_input_float_env("VOICE_INPUT_PAUSE_THRESHOLD", 0.9, 0.35, 2.0)
    recognizer.phrase_threshold = _voice_input_float_env("VOICE_INPUT_PHRASE_THRESHOLD", 0.25, 0.05, 1.0)
    recognizer.non_speaking_duration = _voice_input_float_env("VOICE_INPUT_NON_SPEAKING_SECONDS", 0.45, 0.1, 1.5)
    recognizer.operation_timeout = _voice_input_float_env("VOICE_INPUT_OPERATION_TIMEOUT", 10.0, 2.0, 30.0)


def _capture_speech_recognition_audio(sr: Any, recognizer: Any, timeout_sec: float, phrase_time_limit: float) -> Any:
    try:
        with sr.Microphone() as source:
            ambient_seconds = _voice_input_float_env("VOICE_INPUT_AMBIENT_SECONDS", 0.45, 0.0, 2.0)
            if ambient_seconds > 0:
                recognizer.adjust_for_ambient_noise(source, duration=ambient_seconds)
            _VOICE_LOGGER.info(
                "语音输入已开始监听，energy_threshold=%.1f, pause=%.2fs",
                float(getattr(recognizer, "energy_threshold", 0.0) or 0.0),
                float(getattr(recognizer, "pause_threshold", 0.0) or 0.0),
            )
            return recognizer.listen(
                source,
                timeout=timeout_sec,
                phrase_time_limit=phrase_time_limit,
            )
    except sr.WaitTimeoutError as exc:
        raise RuntimeError("没有识别到语音，请靠近麦克风再试一次。") from exc
    except AttributeError as exc:
        if "PyAudio" in str(exc):
            raise RuntimeError("未安装 PyAudio，无法读取麦克风音频。") from exc
        raise
    except OSError as exc:
        raise RuntimeError(f"无法打开麦克风设备：{exc}") from exc


def _recognize_audio_with_google(sr: Any, recognizer: Any, audio: Any) -> str:
    errors: list[str] = []
    for language in _voice_input_languages():
        try:
            text = recognizer.recognize_google(audio, language=language)
        except sr.UnknownValueError:
            errors.append(f"{language}: 没有听清")
            continue
        except sr.RequestError as exc:
            errors.append(f"{language}: 在线语音识别不可用：{exc}")
            break
        cleaned = _clean_voice_text(text)
        if cleaned:
            _VOICE_LOGGER.info("在线 Google 语音识别成功，language=%s", language)
            return cleaned
        errors.append(f"{language}: 没有识别到文字")
    detail = "；".join(errors) if errors else "没有识别到文字"
    raise RuntimeError(f"在线 Google 语音识别未成功：{detail}")


def _recognize_audio_with_whisper(recognizer: Any, audio: Any) -> str:
    model = os.getenv("VOICE_INPUT_WHISPER_MODEL", "").strip()
    if not model:
        raise RuntimeError("未配置 VOICE_INPUT_WHISPER_MODEL，已跳过本地 Whisper。")
    method = getattr(recognizer, "recognize_faster_whisper", None) or getattr(recognizer, "recognize_whisper", None)
    if not callable(method):
        raise RuntimeError("当前 SpeechRecognition 版本不支持本地 Whisper 识别。")
    language = os.getenv("VOICE_INPUT_WHISPER_LANGUAGE", "zh").strip() or None
    try:
        if language:
            text = method(audio, model=model, language=language)
        else:
            text = method(audio, model=model)
    except TypeError:
        text = method(audio, model=model)
    cleaned = _clean_voice_text(text)
    if not cleaned:
        raise RuntimeError("本地 Whisper 没有识别到文字。")
    _VOICE_LOGGER.info("本地 Whisper 语音识别成功，model=%s", model)
    return cleaned


def _recognize_with_speech_recognition(timeout_sec: float, phrase_time_limit: float, backends: tuple[str, ...]) -> str:
    sr = _load_speech_recognition()
    recognizer = sr.Recognizer()
    _configure_voice_recognizer(recognizer)
    audio = _capture_speech_recognition_audio(sr, recognizer, timeout_sec, phrase_time_limit)
    errors: list[str] = []
    for backend in backends:
        try:
            if backend == "whisper":
                return _recognize_audio_with_whisper(recognizer, audio)
            if backend == "google":
                return _recognize_audio_with_google(sr, recognizer, audio)
        except Exception as exc:
            errors.append(str(exc))
    detail = "；".join(error for error in errors if error)
    raise RuntimeError(detail or "语音识别不可用。")


def _create_windows_sapi_recognizer(win32com_client: Any) -> Any:
    errors: list[str] = []
    try:
        return win32com_client.Dispatch("SAPI.SpSharedRecognizer")
    except Exception as exc:
        errors.append(f"SpSharedRecognizer: {exc}")

    try:
        recognizer = win32com_client.Dispatch("SAPI.SpInprocRecognizer")
        try:
            category = win32com_client.Dispatch("SAPI.SpObjectTokenCategory")
            category.SetId(r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\AudioInput", False)
            tokens = category.EnumerateTokens()
            if getattr(tokens, "Count", 0):
                recognizer.AudioInput = tokens.Item(0)
        except Exception as exc:
            errors.append(f"默认麦克风输入: {exc}")
        return recognizer
    except Exception as exc:
        errors.append(f"SpInprocRecognizer: {exc}")

    raise RuntimeError("Windows 本地识别启动失败：" + "；".join(errors))


def _recognize_with_windows_sapi(timeout_sec: float) -> str:
    if sys.platform != "win32":
        raise RuntimeError("当前系统没有可用的本地语音识别后端。")

    try:
        import pythoncom  # type: ignore
        import win32com.client  # type: ignore
    except ImportError as exc:
        raise RuntimeError("缺少 pywin32，无法调用 Windows 语音识别。") from exc

    result: dict[str, str] = {"text": ""}
    done = threading.Event()

    class _SapiEvents:
        def OnRecognition(self, _stream_number, _stream_position, _recognition_type, recognition_result):
            try:
                result["text"] = _clean_voice_text(recognition_result.PhraseInfo.GetText())
            except Exception:
                result["text"] = ""
            if result["text"]:
                done.set()

    pythoncom.CoInitialize()
    grammar = None
    try:
        try:
            recognizer = _create_windows_sapi_recognizer(win32com.client)
            context = win32com.client.DispatchWithEvents(
                recognizer.CreateRecoContext(),
                _SapiEvents,
            )
            grammar = context.CreateGrammar()
            grammar.DictationSetState(1)
        except Exception as exc:
            raise RuntimeError(f"Windows 本地识别启动失败：{exc}") from exc

        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline and not done.is_set():
            pythoncom.PumpWaitingMessages()
            time.sleep(0.05)

        text = _clean_voice_text(result["text"])
        if text:
            return text
        raise RuntimeError("没有识别到语音，请确认麦克风权限和 Windows 语音识别语言已启用。")
    finally:
        if grammar is not None:
            try:
                grammar.DictationSetState(0)
            except Exception:
                pass
        pythoncom.CoUninitialize()


def _recognize_speech_once(timeout_sec: float = 7.0, phrase_time_limit: float = 8.0) -> str:
    errors: list[str] = []
    backends = _voice_input_backends()

    def run_speech_recognition_backends(sr_backends: tuple[str, ...]) -> str | None:
        try:
            return _recognize_with_speech_recognition(timeout_sec, phrase_time_limit, sr_backends)
        except Exception as exc:
            errors.append(str(exc))
            return None

    pending_sr_backends: list[str] = []
    for backend in backends:
        if backend in _VOICE_INPUT_SR_BACKENDS:
            pending_sr_backends.append(backend)
            continue

        if backend == "sapi":
            if pending_sr_backends:
                text = run_speech_recognition_backends(tuple(pending_sr_backends))
                pending_sr_backends.clear()
                if text:
                    return text
            try:
                return _recognize_with_windows_sapi(max(timeout_sec, phrase_time_limit))
            except Exception as exc:
                errors.append(str(exc))

    if pending_sr_backends:
        text = run_speech_recognition_backends(tuple(pending_sr_backends))
        if text:
            return text

    detail = "；".join(error for error in errors if error)
    raise RuntimeError(detail or "语音识别不可用。")


class InputBox(QFrame, ScalableOverlay):
    _BASE_WIDTH = 260
    _BASE_HEIGHT = 46
    _BASE_RADIUS = 24
    WIDTH = 260
    HEIGHT = 46
    RADIUS = 24

    submitted = Signal(str)
    _voice_text_ready = Signal(str)
    _voice_error = Signal(str)
    _voice_done = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("glass")
        self.setStyleSheet(_glass_style(self.RADIUS))
        self.setFixedSize(self.WIDTH, self.HEIGHT)
        self.visible = False
        self.focused = False
        self.text = ""
        self._voice_thread: threading.Thread | None = None
        self._voice_listening = False
        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(6, 4, 8, 4)
        self._lay.setSpacing(4)
        self._voice_btn = QPushButton()
        self._voice_btn.setFixedSize(28, 28)
        self._voice_btn.setIcon(_make_mic_icon())
        self._voice_btn.setIconSize(QSize(20, 20))
        self._voice_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._voice_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._voice_btn.setAccessibleName("语音输入")
        self._voice_btn.setToolTip("语音输入")
        self._voice_btn.setStyleSheet(BTN_ICON)
        self._voice_btn.clicked.connect(self.start_voice_input)
        self._field = QLineEdit()
        self._field.setPlaceholderText("输入消息…")
        self._field.setFrame(False)
        self._field.setFont(_app_font(15))
        self._apply_field_style()
        self._field.returnPressed.connect(self._submit)
        self._btn = QPushButton("发送")
        self._btn.setStyleSheet(BTN_PRIMARY)
        self._btn.clicked.connect(self._submit)
        self._lay.addWidget(self._voice_btn)
        self._lay.addWidget(self._field, 1)
        self._lay.addWidget(self._btn)
        self._voice_text_ready.connect(self._apply_voice_text)
        self._voice_error.connect(self._show_voice_error)
        self._voice_done.connect(self._finish_voice_input)
        self.hide()

    def apply_ui_scale(self, scale: float) -> None:
        super().apply_ui_scale(scale)
        self.WIDTH = _scaled_int(self._BASE_WIDTH, self._ui_scale, 150)
        self.HEIGHT = _scaled_int(self._BASE_HEIGHT, self._ui_scale, 34)
        self.RADIUS = _scaled_int(self._BASE_RADIUS, self._ui_scale, 14)
        self.setFixedSize(self.WIDTH, self.HEIGHT)
        self._lay.setContentsMargins(
            _scaled_int(6, self._ui_scale, 4),
            _scaled_int(4, self._ui_scale, 2),
            _scaled_int(8, self._ui_scale, 4),
            _scaled_int(4, self._ui_scale, 2),
        )
<<<<<<< HEAD
        font_px = _scaled_int(15, self._ui_scale, 10)
        btn_px = max(9, font_px - 1)
        self._field.setFont(_app_font(font_px))
        self._field.setStyleSheet(
            f"QLineEdit {{ font-size: {font_px}px; background: transparent; border: none; color: #23232d; }}"
            f"QLineEdit::placeholder {{ color: #94a3b8; font-size: {font_px}px; }}"
        )
        self._btn.setFont(_app_font(btn_px))
        pad_v = _scaled_int(8, self._ui_scale, 4)
        pad_h = _scaled_int(14, self._ui_scale, 8)
        self._btn.setStyleSheet(
            f"QPushButton {{ background-color: #1e293b; color: white; border: none;"
            f" border-radius: {_scaled_int(12, self._ui_scale, 8)}px;"
            f" padding: {pad_v}px {pad_h}px; font-size: {btn_px}px; }}"
            f"QPushButton:hover {{ background-color: #334155; }}"
        )
=======
        self._lay.setSpacing(_scaled_int(4, self._ui_scale, 2))
        button_size = _scaled_int(28, self._ui_scale, 22)
        icon_size = _scaled_int(20, self._ui_scale, 16)
        self._voice_btn.setFixedSize(button_size, button_size)
        self._voice_btn.setIconSize(QSize(icon_size, icon_size))
        self._field.setFont(_app_font(_scaled_int(15, self._ui_scale, 10)))
        self._apply_field_style()
>>>>>>> 1360d08d5d0fccda2d7e04fc098499a58aacf455
        self.setStyleSheet(_glass_style(self.RADIUS))

    def _apply_field_style(self) -> None:
        min_height = _scaled_int(28, self._ui_scale, 22)
        pad_x = _scaled_int(6, self._ui_scale, 4)
        self._field.setMinimumHeight(min_height)
        self._field.setStyleSheet(
            f"""
            QLineEdit {{
                background: transparent;
                border: none;
                border-radius: 0px;
                padding: 0px {pad_x}px;
            }}
            """
        )

    @property
    def rect(self) -> QRect:
        return self.geometry()

    def show(self, x: int, y: int) -> None:
        self.move(x, y)
        self.visible = True
        self.focused = True
        super().show()
        self.raise_()
        self._field.setFocus()

    def hide(self) -> None:
        self.visible = False
        super().hide()

    def set_text(self, text: str) -> None:
        self.text = text
        self._field.setText(text)

    def get_text(self) -> str:
        return self._field.text().strip()

    def _submit(self) -> None:
        t = self.get_text()
        if t:
            self.submitted.emit(t)

    def start_voice_input(self) -> None:
        if self._voice_listening:
            return
        _VOICE_LOGGER.info("开始语音输入")
        self._voice_listening = True
        self._voice_btn.setIcon(_make_mic_icon("#ef476f"))
        self._voice_btn.setToolTip("正在听，请说话…")
        if not self._field.text().strip():
            self._field.setPlaceholderText("正在听，请说话…")
        self._voice_thread = threading.Thread(target=self._run_voice_input, daemon=True)
        self._voice_thread.start()

    def _run_voice_input(self) -> None:
        try:
            text = _recognize_speech_once()
            _VOICE_LOGGER.info("语音识别成功，文本长度=%s", len(text))
            self._voice_text_ready.emit(text)
        except Exception as exc:
            _VOICE_LOGGER.warning("语音识别失败: %s", exc)
            self._voice_error.emit(str(exc))
        finally:
            self._voice_done.emit()

    def _apply_voice_text(self, text: str) -> None:
        text = _clean_voice_text(text)
        if not text:
            return
        current = self._field.text()
        cursor_pos = self._field.cursorPosition()
        prefix = current[:cursor_pos]
        suffix = current[cursor_pos:]
        spacer = ""
        if prefix and not prefix.endswith((" ", "\n")) and text[:1] not in "，。！？,.!?":
            spacer = "" if re.search(r"[\u4e00-\u9fff]$", prefix) else " "
        merged = f"{prefix}{spacer}{text}{suffix}"
        self.set_text(merged)
        self._field.setFocus()
        self._field.setCursorPosition(len(prefix) + len(spacer) + len(text))

    def _show_voice_error(self, message: str) -> None:
        message = message.strip() or "语音识别失败，请再试一次。"
        summary = _voice_error_summary(message)
        self._field.setPlaceholderText(summary)
        self._voice_btn.setToolTip(message)
        QToolTip.showText(
            self._voice_btn.mapToGlobal(QPoint(0, self._voice_btn.height())),
            message,
            self._voice_btn,
            self._voice_btn.rect(),
            7000,
        )
        QTimer.singleShot(7000, self._restore_voice_hint)

    def _finish_voice_input(self) -> None:
        self._voice_listening = False
        self._voice_btn.setIcon(_make_mic_icon())
        if self._voice_btn.toolTip().startswith("正在听"):
            self._voice_btn.setToolTip("语音输入")
        if self._field.placeholderText().startswith("正在听"):
            self._field.setPlaceholderText("输入消息…")

    def _restore_voice_hint(self) -> None:
        if self._voice_listening:
            return
        self._voice_btn.setToolTip("语音输入")
        self._field.setPlaceholderText("输入消息…")

    def is_voice_click(self, mouse_pos: tuple[int, int]) -> bool:
        return self._voice_btn.geometry().contains(self.mapFromGlobal(QPoint(*mouse_pos)))

    def is_send_click(self, mouse_pos: tuple[int, int]) -> bool:
        return self._btn.geometry().contains(self.mapFromGlobal(QPoint(*mouse_pos)))

    def handle_event(self, _event) -> bool:
        return False

    def is_enter_submit(self, _event) -> bool:
        return False


# ---------------------------------------------------------------------------
# 控制台
# ---------------------------------------------------------------------------


class _PetCellButton(QFrame):
    """角色卡片：图片在上、名称在下；单击详情，双击切换；右键管理。"""

    single_clicked_pet = Signal(dict)
    double_clicked_pet = Signal(dict)
    pet_context_action = Signal(str, dict)

    def __init__(self, pet: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pet = pet
        self.setFixedSize(128, 150)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(BTN_GLASS)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 4)
        lay.setSpacing(4)
        self._pic = QLabel()
        self._pic.setFixedSize(116, 108)
        self._pic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pic.setStyleSheet(
            "background: rgba(255,255,255,0.55); border-radius: 10px;"
        )
        self._pic.setPixmap(_load_pixmap(pet.get("thumb", ""), QSize(100, 100)))
        self._name_lbl = QLabel(pet.get("name", ""))
        self._name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name_lbl.setFont(_app_font(12))
        self._name_lbl.setWordWrap(True)
        lay.addWidget(self._pic)
        lay.addWidget(self._name_lbl, 0, Qt.AlignmentFlag.AlignHCenter)
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.setInterval(220)
        self._click_timer.timeout.connect(self._emit_single_click)

    def _on_context_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)
        for label, action in (
            ("设置动作映射", "action_map"),
            ("管理动作", "actions"),
            ("编辑性格简介", "personality"),
            ("重命名角色", "rename"),
            ("删除角色", "delete"),
        ):
            menu.addAction(label, lambda _=False, a=action: self.pet_context_action.emit(a, self._pet))
        menu.exec(self.mapToGlobal(pos))

    def update_pet(self, pet: dict) -> None:
        self._pet = pet
        self._name_lbl.setText(pet.get("name", ""))
        self._pic.setPixmap(_load_pixmap(pet.get("thumb", ""), QSize(100, 100)))

    def _emit_single_click(self) -> None:
        self.single_clicked_pet.emit(self._pet)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        self._click_timer.stop()
        self.double_clicked_pet.emit(self._pet)
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._click_timer.start()
        super().mousePressEvent(event)


# ---------------------------------------------------------------------------
# 聊天记录 / 上传 / Live2D 预览
# ---------------------------------------------------------------------------


class ChatHistoryStore:
    """按角色名持久化聊天记录到 assets/chat_history/角色名.json"""

    def __init__(self, project_root: str) -> None:
        self._dir = os.path.join(project_root, "assets", "chat_history")
        os.makedirs(self._dir, exist_ok=True)

    @staticmethod
    def _safe_name(name: str) -> str:
        return re.sub(r'[\\/:*?"<>|]', "_", name.strip()) or "未命名"

    def path_for(self, name: str) -> str:
        return os.path.join(self._dir, f"{self._safe_name(name)}.json")

    def load(self, name: str) -> list[tuple[str, str]]:
        path = self.path_for(name)
        if not os.path.isfile(path):
            return []
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            msgs = data.get("msgs", data if isinstance(data, list) else [])
            out: list[tuple[str, str]] = []
            for item in msgs:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    out.append((str(item[0]), str(item[1])))
            return out
        except (OSError, json.JSONDecodeError):
            return []

    def save(self, name: str, msgs: list[tuple[str, str]]) -> None:
        path = self.path_for(name)
        payload = {"name": name, "msgs": [[r, t] for r, t in msgs]}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def list_characters(self) -> list[str]:
        names: list[str] = []
        if not os.path.isdir(self._dir):
            return names
        for fname in os.listdir(self._dir):
            if fname.endswith(".json"):
                names.append(os.path.splitext(fname)[0])
        return sorted(names)


def scan_voice_packs(project_root: str) -> list[dict]:
    """扫描 assets/voice_packs 下的 TTS 音色包清单。"""
    packs: list[dict] = []
    base_dir = os.path.join(project_root, "assets", "voice_packs")
    if not os.path.isdir(base_dir):
        return packs

    for dirname in sorted(os.listdir(base_dir)):
        pack_dir = os.path.join(base_dir, dirname)
        manifest_path = os.path.join(pack_dir, "voice_pack.json")
        if not os.path.isdir(pack_dir) or not os.path.isfile(manifest_path):
            continue
        try:
            with open(manifest_path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        pack_id = str(data.get("id") or dirname).strip() or dirname
        name = str(data.get("display_name") or data.get("name") or pack_id).strip() or pack_id
        noise_reduction = data.get("noise_reduction") if isinstance(data.get("noise_reduction"), dict) else {}
        conversions = data.get("conversions") if isinstance(data.get("conversions"), list) else []
        analysis = data.get("analysis") if isinstance(data.get("analysis"), dict) else {}
        features = analysis.get("voice_features") if isinstance(analysis.get("voice_features"), dict) else {}
        voice_profiles = data.get("voice_profiles") if isinstance(data.get("voice_profiles"), dict) else {}
        default_profile = voice_profiles.get("default") if isinstance(voice_profiles.get("default"), dict) else {}
        profile_edge_voice = str(default_profile.get("edge_voice") or "").strip()
        clone_backend = data.get("clone_backend") if isinstance(data.get("clone_backend"), dict) else {}
        backend_provider = str(
            clone_backend.get("provider") or default_profile.get("provider") or ""
        ).strip()
        profile_language = language_from_edge_voice(profile_edge_voice)
        language = data.get("language") if isinstance(data.get("language"), dict) else {}
        if profile_language and not language:
            language = {"id": profile_language, "label": language_label(profile_language)}
        packs.append(
            {
                "kind": "local_voice_pack",
                "id": pack_id,
                "name": name,
                "display_name": name,
                "icon": str(data.get("icon") or "🎙️"),
                "description": str(data.get("description") or "TTS 音色参数包。"),
                "sample_text": str(data.get("sample_text") or "你好呀，今天也一起加油。"),
                "language": language,
                "edge_voice": profile_edge_voice,
                "voice_features": features,
                "fit_source": str(default_profile.get("fit_source") or ""),
                "fit_confidence": str(default_profile.get("fit_confidence") or ""),
                "is_custom": bool(data.get("is_custom", False)),
                "sample_count": int(analysis.get("sample_count") or 0)
                if analysis
                else len(data.get("samples") or []) if isinstance(data.get("samples"), list) else 0,
                "denoised_count": int(noise_reduction.get("processed_count") or 0),
                "converted_count": len(conversions),
                "backend_provider": backend_provider,
                "clone_status": str(clone_backend.get("status") or ""),
                "clone_mode": str(clone_backend.get("mode") or ""),
            }
        )
    return packs


def tts_voice_preset_choices(current_edge_voice: str = "") -> list[dict]:
    """把固定 Edge 音色也作为语音包列表里的同级选项。"""
    preset_values = {voice_id for _label, voice_id in TTS_VOICE_PRESETS if voice_id}
    choices: list[dict] = []
    for label, voice_id in TTS_VOICE_PRESETS:
        voice_id = str(voice_id or "").strip()
        if not voice_id:
            continue
        choices.append(
            {
                "id": "",
                "name": label,
                "display_name": label,
                "icon": "🔊",
                "description": f"固定 Edge TTS 音色：{voice_id}。选择后会覆盖语音包内置音色。",
                "sample_text": "你好呀，今天也一起加油。",
                "kind": "edge_voice",
                "edge_voice": voice_id,
                "language": (
                    {"id": language_from_edge_voice(voice_id), "label": language_label(language_from_edge_voice(voice_id))}
                    if language_from_edge_voice(voice_id)
                    else {}
                ),
            }
        )
    current_edge_voice = str(current_edge_voice or "").strip()
    if current_edge_voice and current_edge_voice not in preset_values:
        choices.append(
            {
                "id": "",
                "name": current_edge_voice,
                "display_name": current_edge_voice,
                "icon": "🔊",
                "description": "当前自定义 Edge TTS 音色。",
                "sample_text": "你好呀，今天也一起加油。",
                "kind": "edge_voice",
                "edge_voice": current_edge_voice,
                "language": (
                    {
                        "id": language_from_edge_voice(current_edge_voice),
                        "label": language_label(language_from_edge_voice(current_edge_voice)),
                    }
                    if language_from_edge_voice(current_edge_voice)
                    else {}
                ),
            }
        )
    return choices


def openvoice_install_ready(project_root: str) -> bool:
    root = os.path.abspath(project_root)
    python_exe = os.path.join(root, ".openvoice", "Scripts", "python.exe")
    repo_api = os.path.join(root, "third_party", "OpenVoice", "openvoice", "api.py")
    converter_ckpt = os.path.join(
        root,
        "third_party",
        "OpenVoice",
        "checkpoints_v2",
        "converter",
        "checkpoint.pth",
    )
    converter_config = os.path.join(
        root,
        "third_party",
        "OpenVoice",
        "checkpoints_v2",
        "converter",
        "config.json",
    )
    return all(os.path.isfile(path) for path in (python_exe, repo_api, converter_ckpt, converter_config))


class VoicePackImportDialog(QDialog):
    def __init__(self, project_root: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project_root = project_root
        self._files: list[str] = []
        self._result_pack: dict[str, Any] | None = None

        self.setWindowTitle("导入语音包")
        self.resize(520, 480)
        lay = QVBoxLayout(self)

        lay.addWidget(QLabel("语音包名称"))
        self._name = QLineEdit()
        self._name.setPlaceholderText("例如：我的音色")
        lay.addWidget(self._name)

        lay.addWidget(QLabel("样本语言"))
        self._language = QComboBox()
        for preset in VOICE_PACK_LANGUAGE_PRESETS:
            self._language.addItem(str(preset["label"]), str(preset["id"]))
        lay.addWidget(self._language)

        self._clone_with_gpt = QCheckBox("生成 GPT-SoVITS 专属克隆语音包")
        self._clone_with_gpt.setChecked(True)
        lay.addWidget(self._clone_with_gpt)

        lay.addWidget(QLabel("GPT-SoVITS API 地址"))
        self._gpt_sovits_url = QLineEdit()
        self._gpt_sovits_url.setPlaceholderText("http://127.0.0.1:9880")
        self._gpt_sovits_url.setText(str(config.get("GPT_SOVITS_API_URL", "http://127.0.0.1:9880") or ""))
        lay.addWidget(self._gpt_sovits_url)

        lay.addWidget(QLabel("参考音频台词（可选，越准确越像）"))
        self._prompt_text = QLineEdit()
        self._prompt_text.setPlaceholderText("例如：你好呀，我是你的桌面伙伴。")
        lay.addWidget(self._prompt_text)

        row = QHBoxLayout()
        file_btn = QPushButton("选择音频或 MP4")
        file_btn.setStyleSheet(BTN_GLASS)
        file_btn.clicked.connect(self._choose_files)
        folder_btn = QPushButton("导入文件夹")
        folder_btn.setStyleSheet(BTN_GLASS)
        folder_btn.clicked.connect(self._choose_folder)
        row.addWidget(file_btn)
        row.addWidget(folder_btn)
        lay.addLayout(row)

        self._file_summary = QLabel("尚未选择音频或 MP4 样本，可一次选择一个或多个文件")
        self._file_summary.setWordWrap(True)
        self._file_summary.setStyleSheet("color:#64748b;font-size:12px;")
        lay.addWidget(self._file_summary, 1)

        hint = QLabel("导入后会保存到 assets/voice_packs；样本语言只用于分析，AI 回复语言可以在语言页单独选择。MP4 会先抽取音轨转成 MP3，原始文件不覆盖、不改写。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#94a3b8;font-size:12px;")
        lay.addWidget(hint)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._accept_import)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def result_pack(self) -> dict[str, Any] | None:
        return self._result_pack

    def _choose_files(self) -> None:
        exts = " ".join(f"*{ext}" for ext in IMPORT_SAMPLE_EXTENSIONS)
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "选择语音样本",
            self._project_root,
            f"音频/视频文件 ({exts});;音频文件 ({' '.join(f'*{ext}' for ext in AUDIO_SAMPLE_EXTENSIONS)});;MP4 视频 (*.mp4);;所有文件 (*.*)",
        )
        self._add_files(paths)

    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择语音包文件夹", self._project_root)
        if not folder:
            return
        found: list[str] = []
        for root, _dirs, files in os.walk(folder):
            for fname in files:
                if os.path.splitext(fname)[1].lower() in IMPORT_SAMPLE_EXTENSIONS:
                    found.append(os.path.join(root, fname))
        if not found:
            QMessageBox.warning(self, "未找到音频", "这个文件夹里没有可导入的音频或 MP4 文件。")
            return
        self._add_files(found)

    def _add_files(self, paths: list[str]) -> None:
        seen = {os.path.normcase(os.path.abspath(path)) for path in self._files}
        for path in paths or []:
            if not os.path.isfile(path):
                continue
            if os.path.splitext(path)[1].lower() not in IMPORT_SAMPLE_EXTENSIONS:
                continue
            key = os.path.normcase(os.path.abspath(path))
            if key in seen:
                continue
            seen.add(key)
            self._files.append(path)
        self._refresh_file_summary()

    def _refresh_file_summary(self) -> None:
        if not self._files:
            self._file_summary.setText("尚未选择音频或 MP4 样本")
            return
        names = [os.path.basename(path) for path in self._files[:6]]
        more = len(self._files) - len(names)
        text = f"已选择 {len(self._files)} 个音频样本\n" + "\n".join(names)
        if more > 0:
            text += f"\n... 还有 {more} 个"
        self._file_summary.setText(text)

    def _accept_import(self) -> None:
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "缺少名称", "请填写语音包名称。")
            return
        if not self._files:
            QMessageBox.warning(self, "缺少音频", "请至少选择一个本地音频或 MP4 样本，也可以一次选择多个。")
            return
        base_dir = os.path.join(self._project_root, "assets", "voice_packs")
        try:
            self._result_pack = create_imported_voice_pack(
                display_name=name,
                language_id=str(self._language.currentData() or "zh-CN"),
                sample_paths=self._files,
                base_dir=base_dir,
                clone_backend="gpt-sovits" if self._clone_with_gpt.isChecked() else "",
                prompt_text=self._prompt_text.text().strip(),
                gpt_sovits_api_url=self._gpt_sovits_url.text().strip(),
            )
        except Exception as exc:
            QMessageBox.critical(self, "导入失败", f"语音包导入失败：{exc}")
            return
        self.accept()


def _stem_no_ext(path: str) -> str:
    base = os.path.basename(path)
    if base.lower().endswith(".motion3.json"):
        return base[: -len(".motion3.json")]
    return os.path.splitext(base)[0]


MAO_PRO_ZH_DISPLAY = "小魔女"


def is_mao_pro_zh_model(model_path: str) -> bool:
    return "mao_pro_zh" in model_path.replace("\\", "/").lower()


def motion_label_from_filename(filename: str) -> str:
    """从文件名提取 anim_ 后面的动作名，如 这狗_anim_爱你.gif → 爱你。"""
    base = os.path.splitext(os.path.basename(filename))[0]
    m = re.search(r"anim_(.+)$", base, re.IGNORECASE)
    if m:
        name = m.group(1)
        if re.search(r"_\d{3}$", name):
            name = re.sub(r"_\d{3}$", "", name)
        return name
    return base


def motion_display_name_from_file(filename: str) -> str:
    """动作映射/展示用显示名（anim_ 后文字或用户动作名）。"""
    return motion_label_from_filename(filename)


def resolve_mao_pro_motion_preview(model_path: str) -> str:
    """mao_pro_zh：优先使用 runtime 下缓存的首帧预览图。"""
    if not model_path or not os.path.isfile(model_path):
        return ""
    runtime = os.path.dirname(os.path.abspath(model_path))
    cache = os.path.join(runtime, "_preview_first_motion.png")
    if os.path.isfile(cache):
        return cache
    motions_dir = os.path.join(runtime, "motions")
    if os.path.isdir(motions_dir):
        for fname in sorted(os.listdir(motions_dir)):
            if fname.lower().endswith(".motion3.json"):
                stem = _stem_no_ext(fname)
                for png in sorted(os.listdir(motions_dir)):
                    if png.lower().startswith(stem.lower()) and png.lower().endswith(".png"):
                        return os.path.join(motions_dir, png)
                break
    return resolve_live2d_thumb(model_path)


def build_mao_pro_pet_record(model_path: str, available_motions: list[str]) -> dict:
    preview = resolve_mao_pro_motion_preview(model_path)
    motions = [
        {"id": m, "label": m, "gif": "", "frames": []}
        for m in available_motions
    ] or [{"id": "mtn_01", "label": "mtn_01", "gif": "", "frames": []}]
    return {
        "id": "mao_pro_zh",
        "name": MAO_PRO_ZH_DISPLAY,
        "thumb": preview,
        "personality": "活泼可爱的小魔女，喜欢陪伴你学习与工作。",
        "motions": motions,
        "model_path": model_path,
        "is_flat": False,
    }


def custom_pets_json_path(project_root: str) -> str:
    return os.path.join(project_root, "assets", "custom_pets.json")


def load_custom_pet_ids(project_root: str) -> list[str]:
    path = custom_pets_json_path(project_root)
    if not os.path.isfile(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return [str(x) for x in data.get("ids", [])]
        if isinstance(data, list):
            return [str(x) for x in data]
    except (OSError, json.JSONDecodeError):
        pass
    return []


def save_custom_pet_ids(project_root: str, ids: list[str]) -> None:
    path = custom_pets_json_path(project_root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"ids": list(dict.fromkeys(ids))}, f, ensure_ascii=False, indent=2)


def _gif_first_frame_to_png(gif_path: str, png_path: str) -> bool:
    try:
        from PIL import Image as PILImage
        with PILImage.open(gif_path) as img:
            img.convert("RGBA").save(png_path, "PNG")
        return os.path.isfile(png_path)
    except Exception as exc:
        print(f"[FlatUpload] 提取 GIF 首帧失败: {exc}")
        return False


def find_flat_idle_gif(project_root: str, pet_id: str) -> str:
    """查找 idle GIF；若无 idle 则返回该角色第一个 GIF。"""
    idle_path = ""
    first_path = ""
    scan: list[tuple[str, str]] = []
    sub = os.path.join(project_root, "assets", "animations", pet_id)
    root = os.path.join(project_root, "assets", "animations")
    if os.path.isdir(sub):
        scan.append((sub, ""))
    if os.path.isdir(root):
        scan.append((root, f"{pet_id}_"))
    for folder, prefix in scan:
        try:
            files = sorted(os.listdir(folder))
        except OSError:
            continue
        for fname in files:
            if not fname.lower().endswith(".gif"):
                continue
            if prefix and not fname.startswith(prefix):
                continue
            path = os.path.normpath(os.path.join(folder, fname))
            if not first_path:
                first_path = path
            if "idle" in fname.lower():
                idle_path = path
                break
        if idle_path:
            break
    return idle_path or first_path


def apply_zhegou_idle_thumb(project_root: str, pet: dict) -> dict:
    """这狗：贴图使用 idle 动作首帧，无 idle 则用第一个动作首帧。"""
    if pet.get("id") != "这狗":
        return pet
    pet = dict(pet)
    gif = pet.get("idle_gif") or ""
    if not gif or not os.path.isfile(gif):
        gif = find_flat_idle_gif(project_root, "这狗")
    if not gif or not os.path.isfile(gif):
        return pet
    images_dir = os.path.join(project_root, "assets", "images")
    os.makedirs(images_dir, exist_ok=True)
    out = os.path.join(images_dir, "这狗_idle_frame.png")
    portrait = os.path.join(images_dir, "这狗_image.png")
    if _gif_first_frame_to_png(gif, out):
        pet["idle_image"] = out
        pet["idle_gif"] = gif
    if os.path.isfile(portrait):
        pet["thumb"] = portrait
    elif os.path.isfile(out):
        pet["thumb"] = out
    return pet


def scan_flat_pets(project_root: str, *, include_custom: bool = False) -> list[dict]:
    """扫描 assets 下 GIF/PNG 与静态图；默认排除自定义上传角色。"""
    assets_dir = os.path.join(project_root, "assets")
    images_dir = os.path.join(assets_dir, "images")
    anims_dir = os.path.join(assets_dir, "animations")
    portrait_exact_re = re.compile(r"^(.+)_image\.png$", re.IGNORECASE)
    portrait_loose_re = re.compile(r"^(.+)_image_.+\.png$", re.IGNORECASE)
    anim_gif_re = re.compile(r"^(.+)_anim_(.+)\.gif$", re.IGNORECASE)
    anim_png_re = re.compile(r"^(.+)_anim_(.+)_(\d+)\.png$", re.IGNORECASE)

    def _clean_fname(fname: str) -> str:
        return re.sub(r"\s+\.", ".", fname.strip())

    def _abspath(base: str, fname: str) -> str:
        return os.path.normpath(os.path.join(base, fname.strip()))

    portrait_by_pet: dict[str, str] = {}
    portrait_rank: dict[str, int] = {}
    gifs_by_pet: dict[str, dict[str, str]] = defaultdict(dict)
    png_by_pet: dict[str, dict[str, list[tuple[int, str]]]] = defaultdict(lambda: defaultdict(list))
    pet_ids: set[str] = set()

    if os.path.isdir(images_dir):
        for raw_fname in os.listdir(images_dir):
            fname = _clean_fname(raw_fname)
            pet_id = None
            rank = 99
            exact = portrait_exact_re.match(fname)
            loose = portrait_loose_re.match(fname)
            if exact:
                pet_id, rank = exact.group(1), 0
            elif loose:
                pet_id, rank = loose.group(1), 1
            if pet_id is None:
                continue
            pet_ids.add(pet_id)
            if pet_id not in portrait_rank or rank < portrait_rank[pet_id]:
                portrait_by_pet[pet_id] = _abspath(images_dir, raw_fname)
                portrait_rank[pet_id] = rank

    if os.path.isdir(anims_dir):
        for raw_fname in os.listdir(anims_dir):
            name = _clean_fname(raw_fname)
            gif_match = anim_gif_re.match(name)
            if gif_match:
                pet_id, action = gif_match.group(1), gif_match.group(2)
                pet_ids.add(pet_id)
                gifs_by_pet[pet_id][action] = _abspath(anims_dir, raw_fname)
                continue
            png_match = anim_png_re.match(name)
            if png_match:
                pet_id, action, seq = png_match.group(1), png_match.group(2), int(png_match.group(3))
                pet_ids.add(pet_id)
                png_by_pet[pet_id][action].append((seq, _abspath(anims_dir, raw_fname)))

    def _pick_idle_gif(pet_id: str) -> str:
        gifs = gifs_by_pet.get(pet_id, {})
        if gifs.get("idle") and os.path.isfile(gifs["idle"]):
            return gifs["idle"]
        explicit = _abspath(anims_dir, f"{pet_id}_anim_idle.gif")
        if os.path.isfile(explicit):
            return explicit
        for action in sorted(gifs.keys()):
            path = gifs[action]
            if path and os.path.isfile(path):
                return path
        return ""

    custom_ids = set(load_custom_pet_ids(project_root))

    pets: list[dict] = []
    for pet_id in sorted(pet_ids):
        if not include_custom and pet_id in custom_ids:
            continue
        gifs = gifs_by_pet.get(pet_id, {})
        png_actions = png_by_pet.get(pet_id, {})
        # 平面素材库：仅收录 assets/animations 中确有动作文件的角色
        if not gifs and not png_actions:
            if not (include_custom and pet_id in custom_ids):
                continue
        thumb = portrait_by_pet.get(pet_id, "")
        idle_gif = _pick_idle_gif(pet_id)
        all_actions = sorted(set(gifs.keys()) | set(png_actions.keys()))
        motions: list[dict] = []
        for action in all_actions:
            if action.lower() == "idle":
                continue
            gif_path = gifs.get(action, "")
            frames = [path for _seq, path in sorted(png_actions.get(action, []), key=lambda x: x[0])]
            if gif_path and not os.path.isfile(gif_path):
                gif_path = ""
            if not gif_path and not frames:
                continue
            label = motion_label_from_filename(f"{pet_id}_anim_{action}.gif")
            motions.append(
                {
                    "id": action,
                    "label": label,
                    "gif": gif_path,
                    "frames": frames,
                }
            )
        pets.append(
            {
                "id": pet_id,
                "name": pet_id,
                "thumb": thumb,
                "idle_image": thumb,
                "idle_gif": idle_gif,
                "personality": f"平面素材角色 · {pet_id}",
                "motions": motions,
                "is_flat": True,
            }
        )
    return pets


def action_mapping_path(project_root: str) -> str:
    return os.path.join(project_root, "assets", "action_mapping.json")


def load_action_mapping_json(project_root: str) -> dict:
    path = action_mapping_path(project_root)
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def load_pet_action_mapping(project_root: str, pet_id: str) -> dict[str, list[str]]:
    data = load_action_mapping_json(project_root)
    pet_map = data.get(pet_id, {})
    if not isinstance(pet_map, dict):
        return {}
    return {
        str(k): [str(x) for x in v]
        for k, v in pet_map.items()
        if isinstance(v, list)
    }


def save_pet_action_mapping(
    project_root: str, pet_id: str, mapping: dict[str, list[str]]
) -> None:
    path = action_mapping_path(project_root)
    data = load_action_mapping_json(project_root)
    data[pet_id] = {k: list(v) for k, v in mapping.items()}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def remove_pet_from_action_mapping(project_root: str, pet_id: str) -> None:
    path = action_mapping_path(project_root)
    if not os.path.isfile(path):
        return
    try:
        data = load_action_mapping_json(project_root)
        if pet_id in data:
            del data[pet_id]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def rename_pet_in_action_mapping(project_root: str, old_id: str, new_id: str) -> None:
    if not old_id or old_id == new_id:
        return
    path = action_mapping_path(project_root)
    if not os.path.isfile(path):
        return
    try:
        data = load_action_mapping_json(project_root)
        if old_id in data:
            data[new_id] = data.pop(old_id)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


class ManageActionsDialog(QDialog):
    """管理角色动作：查看 / 添加 / 删除 / 重新映射。"""

    def __init__(self, pet: dict, project_root: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pet = pet
        self._root = project_root
        self.setWindowTitle(f"管理动作 - {pet.get('name', '')}")
        self.resize(520, 460)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"<h3>{pet.get('name', '')} 的动作列表</h3>"))
        self._list = QListWidget()
        lay.addWidget(self._list, 1)
        row = QHBoxLayout()
        add_btn = QPushButton("添加动作")
        del_btn = QPushButton("删除选中")
        map_btn = QPushButton("重新映射")
        add_btn.clicked.connect(self._add_action)
        del_btn.clicked.connect(self._delete_action)
        map_btn.clicked.connect(self._remap_actions)
        row.addWidget(add_btn)
        row.addWidget(del_btn)
        row.addWidget(map_btn)
        lay.addLayout(row)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        lay.addWidget(close_btn)
        self._refresh_list()

    def _anim_dir(self) -> str:
        pet_id = self._pet.get("id", "")
        d = os.path.join(self._root, "assets", "animations", pet_id)
        if os.path.isdir(d):
            return d
        return os.path.join(self._root, "assets", "animations")

    def _refresh_list(self) -> None:
        self._list.clear()
        pet_id = self._pet.get("id", "")
        prefix = f"{pet_id}_"
        folder = self._anim_dir()
        if os.path.isdir(folder):
            for fname in sorted(os.listdir(folder)):
                if fname.lower().endswith((".gif", ".png")):
                    self._list.addItem(fname)

    def _add_action(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "添加动作", self._root, "动画 (*.gif *.png)"
        )
        if not path:
            return
        os.makedirs(self._anim_dir(), exist_ok=True)
        shutil.copy2(path, os.path.join(self._anim_dir(), os.path.basename(path)))
        self._refresh_list()

    def _delete_action(self) -> None:
        item = self._list.currentItem()
        if not item:
            return
        fp = os.path.join(self._anim_dir(), item.text())
        if os.path.isfile(fp) and QMessageBox.question(self, "确认", f"删除 {item.text()}？") == QMessageBox.StandardButton.Yes:
            os.remove(fp)
            self._refresh_list()

    def _remap_actions(self) -> None:
        files = [self._list.item(i).text() for i in range(self._list.count())]
        dlg = ActionMappingDialog(
            self._pet.get("name", ""),
            files,
            self,
            initial=load_pet_action_mapping(self._root, self._pet.get("id", "")),
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            save_pet_action_mapping(self._root, self._pet.get("id", ""), dlg.mapping())


class PetCharacterOps:
    """角色卡片右键：删除 / 重命名 / 改简介。"""

    @staticmethod
    def delete_pet(console: "ControlConsole", pet: dict) -> None:
        name = pet.get("name", pet.get("id", ""))
        if QMessageBox.question(
            console, "删除角色", f"确定删除「{name}」及其所有素材与配置？"
        ) != QMessageBox.StandardButton.Yes:
            return
        root = console._project_root
        pet_id = pet.get("id", "")
        if pet.get("is_flat"):
            anim_dir = os.path.join(root, "assets", "animations", pet_id)
            if os.path.isdir(anim_dir):
                shutil.rmtree(anim_dir, ignore_errors=True)
            for fname in os.listdir(os.path.join(root, "assets", "animations")) if os.path.isdir(os.path.join(root, "assets", "animations")) else []:
                if fname.startswith(f"{pet_id}_"):
                    try:
                        os.remove(os.path.join(root, "assets", "animations", fname))
                    except OSError:
                        pass
            img = os.path.join(root, "assets", "images", f"{pet_id}_image.png")
            if os.path.isfile(img):
                os.remove(img)
            ids = [i for i in load_custom_pet_ids(root) if i != pet_id]
            save_custom_pet_ids(root, ids)
        else:
            model_dir = os.path.join(root, "assets", "models", pet_id)
            if os.path.isdir(model_dir):
                shutil.rmtree(model_dir, ignore_errors=True)
            console._live2d = [p for p in console._live2d if p.get("id") != pet_id]
        remove_pet_from_action_mapping(root, pet_id)
        console._rescan_flat_pets()
        console._custom_ids = load_custom_pet_ids(root)
        console._reload_character_tabs()
        console._show_toast(f"已删除角色: {name}")

    @staticmethod
    def rename_pet(console: "ControlConsole", pet: dict) -> None:
        old_name = pet.get("name", pet.get("id", ""))
        new_name, ok = QInputDialog.getText(console, "重命名角色", "新名称：", text=old_name)
        if not ok or not new_name.strip() or new_name.strip() == old_name:
            return
        new_name = new_name.strip()
        root = console._project_root
        pet_id = pet.get("id", "")
        new_id = re.sub(r"\s+", "_", new_name)
        if pet.get("is_flat"):
            old_dir = os.path.join(root, "assets", "animations", pet_id)
            new_dir = os.path.join(root, "assets", "animations", new_id)
            if os.path.isdir(old_dir) and old_dir != new_dir:
                if os.path.isdir(new_dir):
                    shutil.rmtree(new_dir, ignore_errors=True)
                shutil.move(old_dir, new_dir)
            old_img = os.path.join(root, "assets", "images", f"{pet_id}_image.png")
            new_img = os.path.join(root, "assets", "images", f"{new_id}_image.png")
            if os.path.isfile(old_img):
                shutil.move(old_img, new_img)
            ids = load_custom_pet_ids(root)
            if pet_id in ids:
                ids = [new_id if i == pet_id else i for i in ids]
                save_custom_pet_ids(root, ids)
        rename_pet_in_action_mapping(root, pet_id, new_id)
        pet["id"] = new_id
        pet["name"] = new_name
        console._rescan_flat_pets()
        console._custom_ids = load_custom_pet_ids(root)
        console._reload_character_tabs()
        console._show_toast(f"已重命名为: {new_name}")

    @staticmethod
    def edit_personality(console: "ControlConsole", pet: dict) -> None:
        text, ok = QInputDialog.getMultiLineText(
            console, "编辑性格简介", "性格描述：", pet.get("personality", "")
        )
        if ok:
            pet["personality"] = text.strip()
            console._show_toast("性格简介已更新")

    @staticmethod
    def manage_actions(console: "ControlConsole", pet: dict) -> None:
        dlg = ManageActionsDialog(pet, console._project_root, console)
        dlg.exec()
        console._rescan_flat_pets()
        console._reload_character_tabs()

    @staticmethod
    def setup_action_mapping(console: "ControlConsole", pet: dict) -> None:
        pet_id = pet.get("id", "")
        files = PetCharacterOps._list_motion_files(console._project_root, pet)
        dlg = ActionMappingDialog(
            pet.get("name", pet_id),
            files,
            console,
            initial=load_pet_action_mapping(console._project_root, pet_id),
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        save_pet_action_mapping(console._project_root, pet_id, dlg.mapping())
        console._rescan_flat_pets()
        console._reload_character_tabs()
        desk = getattr(console, "_desk", None)
        if desk is not None:
            desk.reload_action_mapping()
            desk.refresh_pet_motions_after_mapping_change()
        console._show_toast("动作映射已保存")

    @staticmethod
    def _list_motion_files(project_root: str, pet: dict) -> list[str]:
        pet_id = pet.get("id", "")
        names: list[str] = []
        anim_dir = os.path.join(project_root, "assets", "animations", pet_id)
        if os.path.isdir(anim_dir):
            for fname in sorted(os.listdir(anim_dir)):
                if fname.lower().endswith((".gif", ".png")):
                    names.append(fname)
        flat_dir = os.path.join(project_root, "assets", "animations")
        prefix = f"{pet_id}_"
        if os.path.isdir(flat_dir):
            for fname in sorted(os.listdir(flat_dir)):
                if fname.startswith(prefix) and fname.lower().endswith((".gif", ".png")):
                    names.append(fname)
        model_path = pet.get("model_path") or ""
        if model_path and os.path.isfile(model_path):
            runtime = os.path.dirname(os.path.abspath(model_path))
            motions_dir = os.path.join(runtime, "motions")
            if os.path.isdir(motions_dir):
                for fname in sorted(os.listdir(motions_dir)):
                    if fname.lower().endswith(".motion3.json"):
                        names.append(fname[: -len(".motion3.json")])
        return list(dict.fromkeys(names))


def resolve_live2d_thumb(model_path: str) -> str:
    """解析 Live2D 预览图；无 textures 时尝试 motions 目录或模型目录内 PNG。"""
    if not model_path or not os.path.isfile(model_path):
        return ""
    runtime = os.path.dirname(os.path.abspath(model_path))
    for tex_dir_name in ("mao_pro.4096", "textures", "texture"):
        tex_dir = os.path.join(runtime, tex_dir_name)
        if os.path.isdir(tex_dir):
            for fname in sorted(os.listdir(tex_dir)):
                if fname.lower().endswith(".png"):
                    return os.path.join(tex_dir, fname)
    motions_dir = os.path.join(runtime, "motions")
    if os.path.isdir(motions_dir):
        for fname in sorted(os.listdir(motions_dir)):
            if fname.lower().endswith(".png"):
                return os.path.join(motions_dir, fname)
    for dirpath, _dn, files in os.walk(runtime):
        for fname in sorted(files):
            if fname.lower().endswith(".png"):
                return os.path.join(dirpath, fname)
    return ""


def list_live2d_motion_stems(model_path: str) -> list[str]:
    if not model_path or not os.path.isfile(model_path):
        return []
    runtime = os.path.dirname(os.path.abspath(model_path))
    stems: list[str] = []
    seen: set[str] = set()
    for dirpath, _dn, files in os.walk(runtime):
        for fname in sorted(files):
            if not fname.lower().endswith(".motion3.json"):
                continue
            stem = _stem_no_ext(fname)
            if stem not in seen:
                seen.add(stem)
                stems.append(stem)
    return stems


def validate_live2d_model(model_path: str) -> tuple[bool, str]:
    if not model_path or not os.path.isfile(model_path):
        return False, "请选择有效的 .model3.json 文件"
    runtime = os.path.dirname(model_path)
    try:
        with open(model_path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"无法读取模型 JSON: {exc}"
    refs = data.get("FileReferences", {})
    moc = refs.get("Moc") or ""
    moc_path = os.path.join(runtime, moc) if moc else ""
    if not moc_path or not os.path.isfile(moc_path):
        return False, "缺少 .moc3 文件"
    textures = refs.get("Textures") or []
    has_tex = any(os.path.isfile(os.path.join(runtime, t)) for t in textures)
    if not has_tex:
        preview = resolve_live2d_thumb(model_path)
        if not preview:
            return False, "缺少贴图文件夹，且无法找到备用预览图"
    return True, "验证通过"


class ActionMappingDialog(QDialog):
    """为 D 动作类型选择对应素材（下拉显示动作名，保存文件名）。"""

    def __init__(
        self,
        pet_name: str,
        motion_files: list[str],
        parent: QWidget | None = None,
        *,
        initial: dict[str, list[str]] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"动作映射 - {pet_name}")
        self.resize(560, 480)
        self._mapping: dict[str, list[str]] = {}
        initial = initial or {}
        outer = QVBoxLayout(self)
        outer.addWidget(QLabel(f"<h3>为「{pet_name}」配置动作映射</h3>"))
        outer.addWidget(QLabel("为 happy / sad / hungry / angry / idle 选择动作；下拉显示动作名。"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        self._combos: dict[str, QComboBox] = {}
        for code in D_ACTION_CODES:
            row = QHBoxLayout()
            row.addWidget(QLabel(f"<b>{D_ACTION_LABELS.get(code, code)}</b>"))
            combo = QComboBox()
            combo.addItem("（不映射）", "")
            for fname in motion_files:
                combo.addItem(motion_display_name_from_file(fname), fname)
            pick = (initial.get(code) or [""])[0] if initial.get(code) else ""
            if pick:
                idx = combo.findData(pick)
                if idx < 0:
                    idx = combo.findText(pick)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            self._combos[code] = combo
            row.addWidget(combo, 1)
            lay.addLayout(row)
        lay.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        outer.addWidget(btns)

    def mapping(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for code, combo in self._combos.items():
            fname = combo.currentData()
            if fname:
                out[code] = [str(fname)]
        return out


class Live2dUploadDialog(QDialog):
    def __init__(self, project_root: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._root = project_root
        self._model_path = ""
        self.setWindowTitle("上传 Live2D 模型")
        self.resize(480, 320)
        lay = QVBoxLayout(self)
        self._name = QLineEdit()
        self._name.setPlaceholderText("角色姓名（必填）")
        lay.addWidget(QLabel("角色姓名"))
        lay.addWidget(self._name)
        self._personality = QLineEdit()
        self._personality.setPlaceholderText("性格描述（可选）")
        lay.addWidget(QLabel("性格描述"))
        lay.addWidget(self._personality)
        pick_row = QHBoxLayout()
        self._path_lbl = QLabel("未选择文件")
        pick_btn = QPushButton("选择 .model3.json")
        pick_btn.clicked.connect(self._pick_model)
        pick_row.addWidget(self._path_lbl, 1)
        pick_row.addWidget(pick_btn)
        lay.addLayout(pick_row)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)
        self._result_pet: dict | None = None

    def _pick_model(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择模型", self._root, "Live2D Model (*.model3.json)")
        if path:
            self._model_path = path
            self._path_lbl.setText(os.path.basename(path))

    def _on_ok(self) -> None:
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请填写角色姓名")
            return
        ok, msg = validate_live2d_model(self._model_path)
        if not ok:
            QMessageBox.warning(self, "验证失败", msg)
            return
        pet_id = re.sub(r"\s+", "_", name)
        dest_root = os.path.join(self._root, "assets", "models", pet_id)
        src_dir = os.path.dirname(self._model_path)
        os.makedirs(dest_root, exist_ok=True)
        for item in os.listdir(src_dir):
            s = os.path.join(src_dir, item)
            d = os.path.join(dest_root, item)
            if os.path.isdir(s):
                if os.path.exists(d):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copytree(s, d)
            else:
                shutil.copy2(s, d)
        dest_model = os.path.join(dest_root, os.path.basename(self._model_path))
        if not os.path.isfile(dest_model):
            shutil.copy2(self._model_path, dest_model)
        stems = list_live2d_motion_stems(dest_model)
        map_dlg = ActionMappingDialog(name, stems, self)
        if map_dlg.exec() != QDialog.DialogCode.Accepted:
            return
        save_pet_action_mapping(self._root, pet_id, map_dlg.mapping())
        thumb = resolve_live2d_thumb(dest_model)
        self._result_pet = {
            "id": pet_id,
            "name": name,
            "personality": self._personality.text().strip(),
            "thumb": thumb,
            "model_path": dest_model,
            "is_flat": False,
            "motions": [{"id": s, "label": s, "gif": "", "frames": []} for s in stems],
        }
        self.accept()

    def result_pet(self) -> dict | None:
        return self._result_pet


class Live2dModelingDialog(QDialog):
    """Live2D 白膜参数建模入口。"""

    def __init__(self, project_root: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._root = project_root
        self._template_root = os.path.join(
            project_root,
            "assets",
            "live2d_modeling",
            "base_front_template",
        )
        self._schema = self._load_json("rig_parameters.json")
        self._presets = self._load_json("parameter_presets.json").get("presets", {})
        self._defaults = self._default_params()
        self._params = dict(self._defaults)
        self._sliders: dict[str, QSlider] = {}
        self._value_labels: dict[str, QLabel] = {}
        self._param_units: dict[str, str] = {}

        self.setWindowTitle("Live2D 白膜建模")
        self.resize(960, 680)
        self.setMinimumSize(820, 560)

        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.timeout.connect(self._render_preview)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 18)
        root.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("<h2>Live2D 白膜建模</h2>")
        header.addWidget(title)
        header.addStretch()
        self._status = QLabel("")
        self._status.setStyleSheet("color:#64748b;")
        header.addWidget(self._status)
        root.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(14)
        body.addWidget(self._build_preview_panel(), 0)
        body.addWidget(self._build_controls_panel(), 1)
        root.addLayout(body, 1)

        self._apply_preset("default")

    def _load_json(self, filename: str) -> dict:
        path = os.path.join(self._template_root, filename)
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError) as exc:
            QMessageBox.warning(self, "白膜资源不可用", f"无法读取 {filename}: {exc}")
            return {}

    def _default_params(self) -> dict[str, float]:
        defaults: dict[str, float] = {}
        for group in self._schema.get("groups", []):
            for param in group.get("parameters", []):
                key = str(param.get("key") or "")
                if key:
                    defaults[key] = float(param.get("default", 0))
        return defaults

    def _preset_items(self) -> list[tuple[str, str]]:
        items: list[tuple[str, str]] = []
        for key, data in self._presets.items():
            if isinstance(data, dict):
                items.append((str(key), str(data.get("label") or key)))
        return items or [("default", "默认白膜")]

    def _build_preview_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("glass")
        panel.setStyleSheet(_glass_style(16))
        panel.setFixedWidth(340)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(16, 14, 16, 16)
        lay.setSpacing(10)

        self._preview = QLabel()
        self._preview.setFixedSize(300, 450)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setStyleSheet(
            "background: #eef2f7; border: 1px solid #ffd1dc; border-radius: 14px;"
        )
        lay.addWidget(self._preview, alignment=Qt.AlignmentFlag.AlignCenter)

        lay.addWidget(QLabel("白膜名称"))
        self._name_input = QLineEdit("我的Live2D白膜")
        self._name_input.setPlaceholderText("用于导出文件夹和 PNG 名称")
        lay.addWidget(self._name_input)

        export_btn = QPushButton("导出当前白膜")
        export_btn.setStyleSheet(BTN_PRIMARY)
        export_btn.clicked.connect(self._export_current)
        lay.addWidget(export_btn)

        reset_btn = QPushButton("恢复默认")
        reset_btn.setStyleSheet(BTN_GLASS)
        reset_btn.clicked.connect(lambda: self._apply_preset("default"))
        lay.addWidget(reset_btn)
        lay.addStretch()
        return panel

    def _build_controls_panel(self) -> QWidget:
        wrap = QWidget()
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("<b>预设</b>"))
        self._preset_combo = QComboBox()
        for key, label in self._preset_items():
            self._preset_combo.addItem(label, key)
        self._preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        preset_row.addWidget(self._preset_combo, 1)
        lay.addLayout(preset_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        inner_lay = QVBoxLayout(inner)
        inner_lay.setContentsMargins(0, 0, 8, 0)
        inner_lay.setSpacing(10)
        for group in self._schema.get("groups", []):
            inner_lay.addWidget(self._build_param_group(group))
        inner_lay.addStretch()
        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)
        return wrap

    def _build_param_group(self, group: dict) -> QFrame:
        frame = QFrame()
        frame.setObjectName("glass")
        frame.setStyleSheet(_glass_style(14))
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(14, 10, 14, 12)
        lay.setSpacing(8)
        lay.addWidget(QLabel(f"<b>{group.get('label', '')}</b>"))

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(1, 1)
        for row, param in enumerate(group.get("parameters", [])):
            key = str(param.get("key") or "")
            if not key:
                continue
            label = QLabel(str(param.get("label") or key))
            label.setMinimumWidth(92)
            label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(int(param.get("min", 0)), int(param.get("max", 100)))
            slider.setSingleStep(int(param.get("step", 1)))
            slider.setValue(int(self._defaults.get(key, param.get("default", 0))))
            value = QLabel()
            value.setMinimumWidth(54)
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._sliders[key] = slider
            self._value_labels[key] = value
            self._param_units[key] = str(param.get("unit") or "")
            self._set_value_label(key, slider.value())
            slider.valueChanged.connect(lambda v, name=key: self._on_param_changed(name, v))
            grid.addWidget(label, row, 0)
            grid.addWidget(slider, row, 1)
            grid.addWidget(value, row, 2)
        lay.addLayout(grid)
        return frame

    def _set_value_label(self, key: str, value: int | float) -> None:
        label = self._value_labels.get(key)
        if label is not None:
            label.setText(f"{int(value)}{self._param_units.get(key, '')}")

    def _on_param_changed(self, key: str, value: int) -> None:
        self._params[key] = float(value)
        self._set_value_label(key, value)
        self._schedule_render()

    def _on_preset_changed(self, *_args: Any) -> None:
        self._apply_preset(str(self._preset_combo.currentData() or "default"))

    def _apply_preset(self, preset_key: str) -> None:
        self._params = dict(self._defaults)
        preset = self._presets.get(preset_key, {})
        if isinstance(preset, dict):
            self._params.update(
                {str(k): float(v) for k, v in preset.get("params", {}).items()}
            )
        idx = self._preset_combo.findData(preset_key) if hasattr(self, "_preset_combo") else -1
        if idx >= 0 and self._preset_combo.currentIndex() != idx:
            self._preset_combo.blockSignals(True)
            self._preset_combo.setCurrentIndex(idx)
            self._preset_combo.blockSignals(False)
        for key, slider in self._sliders.items():
            value = int(round(self._params.get(key, self._defaults.get(key, 0))))
            slider.blockSignals(True)
            slider.setValue(value)
            slider.blockSignals(False)
            self._set_value_label(key, value)
        self._schedule_render(delay_ms=10)

    def _schedule_render(self, delay_ms: int = 140) -> None:
        self._status.setText("正在生成预览...")
        self._render_timer.start(delay_ms)

    def _renderer(self):
        from pathlib import Path

        if self._root and self._root not in sys.path:
            sys.path.insert(0, self._root)
        from tools import render_parametric_live2d_base as renderer

        template_root = Path(self._template_root)
        renderer.ROOT = template_root
        renderer.PARAM_FILE = template_root / "rig_parameters.json"
        renderer.PRESET_FILE = template_root / "parameter_presets.json"
        renderer.LAYER_DIR = template_root / "ai_cut_layers"
        renderer.OUT_DIR = template_root / "parametric"
        return renderer

    def _render_to(self, out_dir: str, name: str) -> dict[str, str]:
        from pathlib import Path

        renderer = self._renderer()
        return renderer.render(dict(self._params), Path(out_dir), name)

    def _render_preview(self) -> None:
        try:
            out_dir = os.path.join(self._template_root, "ui_preview")
            result = self._render_to(out_dir, "live2d_base_editor")
            preview = result.get("preview", "")
            self._preview.setPixmap(_load_pixmap(preview, self._preview.size()))
            self._status.setText("预览已更新")
        except Exception as exc:
            self._status.setText("预览生成失败")
            QMessageBox.warning(self, "预览生成失败", str(exc))

    def _safe_export_name(self) -> str:
        name = self._name_input.text().strip() or "live2d_base"
        name = re.sub(r"[\\/:*?\"<>|]+", "_", name)
        name = re.sub(r"\s+", "_", name).strip("._")
        return name or "live2d_base"

    def _export_current(self) -> None:
        try:
            name = self._safe_export_name()
            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            out_dir = os.path.join(
                self._root,
                "assets",
                "live2d_modeling",
                "custom_bases",
                f"{name}_{stamp}",
            )
            result = self._render_to(out_dir, name)
            manifest = {
                "name": name,
                "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
                "params": dict(self._params),
                "files": result,
            }
            with open(os.path.join(out_dir, "modeling_manifest.json"), "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)
            self._status.setText(f"已导出: {out_dir}")
            QMessageBox.information(self, "导出完成", f"白膜文件已导出到：\n{out_dir}")
        except Exception as exc:
            QMessageBox.warning(self, "导出失败", str(exc))


class FlatUploadDialog(QDialog):
    def __init__(self, project_root: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._root = project_root
        self._uploaded_files: list[str] = []
        self.setWindowTitle("上传平面素材")
        self.resize(480, 280)
        lay = QVBoxLayout(self)
        self._name = QLineEdit()
        lay.addWidget(QLabel("角色姓名（必填）"))
        lay.addWidget(self._name)
        self._personality = QLineEdit()
        lay.addWidget(QLabel("性格描述（可选）"))
        lay.addWidget(self._personality)
        self._thumb_path = ""
        thumb_row = QHBoxLayout()
        self._thumb_lbl = QLabel("未上传贴图（将用首帧自动生成）")
        thumb_btn = QPushButton("上传平面贴图（可选）")
        thumb_btn.clicked.connect(self._pick_thumb)
        thumb_row.addWidget(self._thumb_lbl, 1)
        thumb_row.addWidget(thumb_btn)
        lay.addLayout(thumb_row)
        self._hint = QLabel("")
        lay.addWidget(self._hint)
        upload_btn = QPushButton("上传当前动作")
        upload_btn.clicked.connect(self._upload_one)
        lay.addWidget(upload_btn)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._finish)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)
        self._action_index = 1
        self._result_pet: dict | None = None
        self._refresh_upload_hint()

    def _refresh_upload_hint(self) -> None:
        self._hint.setText(f"这是动作{self._action_index}，请选择 GIF 或多张 PNG 序列帧")

    def _pick_thumb(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择平面贴图", self._root, "图片 (*.png *.jpg *.jpeg *.webp)"
        )
        if path:
            self._thumb_path = path
            self._thumb_lbl.setText(os.path.basename(path))

    def _upload_one(self) -> None:
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请先填写角色姓名")
            return
        self._refresh_upload_hint()
        pet_id = re.sub(r"\s+", "_", name)
        action_name, ok = QInputDialog.getText(
            self, "动作名称", f"为动作{self._action_index}命名（如：爱你、开心）："
        )
        if not ok or not action_name.strip():
            return
        action_name = re.sub(r"\s+", "_", action_name.strip())
        dest_dir = os.path.join(self._root, "assets", "animations")
        os.makedirs(dest_dir, exist_ok=True)

        paths, _ = QFileDialog.getOpenFileNames(
            self,
            f"动作{self._action_index} - 选择 GIF 或 PNG 序列（PNG 可多选）",
            self._root,
            "动画 (*.gif *.png);;GIF (*.gif);;PNG (*.png)",
        )
        if not paths:
            return
        paths = sorted(paths, key=lambda p: (os.path.dirname(p), p.lower()))
        gifs = [p for p in paths if p.lower().endswith(".gif")]
        pngs = [p for p in paths if p.lower().endswith(".png")]
        if gifs and pngs:
            QMessageBox.warning(self, "提示", "请勿同时选择 GIF 与 PNG，请分开上传。")
            return
        if len(gifs) == 1:
            dest = os.path.join(dest_dir, f"{pet_id}_anim_{action_name}.gif")
            shutil.copy2(gifs[0], dest)
            self._uploaded_files.append(os.path.basename(dest))
        elif len(gifs) > 1:
            QMessageBox.warning(self, "提示", "一次只能上传一个 GIF 文件。")
            return
        elif pngs:
            for i, src in enumerate(pngs, 1):
                dest = os.path.join(dest_dir, f"{pet_id}_anim_{action_name}_{i:03d}.png")
                shutil.copy2(src, dest)
                self._uploaded_files.append(os.path.basename(dest))
        else:
            QMessageBox.warning(self, "提示", "请选择 GIF 或 PNG 文件。")
            return
        self._action_index += 1
        self._refresh_upload_hint()
        cont = QMessageBox.question(
            self, "继续", "是否继续添加动作？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if cont == QMessageBox.StandardButton.No:
            self._finish()

    def _finish(self) -> None:
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请填写角色姓名")
            return
        if not self._uploaded_files:
            QMessageBox.warning(self, "提示", "请至少上传一个动作")
            return
        pet_id = re.sub(r"\s+", "_", name)
        map_dlg = ActionMappingDialog(name, self._uploaded_files, self)
        if map_dlg.exec() != QDialog.DialogCode.Accepted:
            return
        save_pet_action_mapping(self._root, pet_id, map_dlg.mapping())
        ids = load_custom_pet_ids(self._root)
        if pet_id not in ids:
            ids.append(pet_id)
            save_custom_pet_ids(self._root, ids)
        images_dir = os.path.join(self._root, "assets", "images")
        os.makedirs(images_dir, exist_ok=True)
        thumb = os.path.join(images_dir, f"{pet_id}_image.png")
        anims_dir = os.path.join(self._root, "assets", "animations")
        if self._thumb_path and os.path.isfile(self._thumb_path):
            shutil.copy2(self._thumb_path, thumb)
        elif os.path.isdir(anims_dir):
            for fname in sorted(os.listdir(anims_dir)):
                if not fname.startswith(f"{pet_id}_anim_"):
                    continue
                full = os.path.join(anims_dir, fname)
                if fname.lower().endswith(".gif"):
                    if _gif_first_frame_to_png(full, thumb):
                        break
                elif fname.lower().endswith(".png") and fname.endswith("_001.png"):
                    shutil.copy2(full, thumb)
                    break
        self._result_pet = {
            "id": pet_id,
            "name": name,
            "personality": self._personality.text().strip(),
            "thumb": thumb if os.path.isfile(thumb) else "",
            "idle_image": thumb if os.path.isfile(thumb) else "",
            "is_flat": True,
            "is_custom": True,
            "motions": [],
            "anim_dir": anims_dir,
        }
        self.accept()

    def result_pet(self) -> dict | None:
        return self._result_pet


class ControlConsole(QMainWindow):
    def __init__(
        self,
        project_root: str,
        model_path: str,
        available_motions: list[str],
        motion_name_map: dict[str, str],
        on_play_motion: Callable[[str], bool] | None = None,
        on_pet_changed: Callable[[dict], None] | None = None,
        on_voice_pack_changed: Callable[[dict], None] | None = None,
        current_voice_pack_id: str = "",
        on_tts_settings_changed: Callable[[dict], None] | None = None,
        current_tts_settings: dict[str, Any] | None = None,
        on_read_text: Callable[..., None] | None = None,
        on_stop_read_text: Callable[[], None] | None = None,
        on_pet_settings_changed: Callable[[dict[str, dict[str, Any]]], None] | None = None,
    ) -> None:
        super().__init__()
        self._project_root = project_root
        self.model_path = model_path
        self.available_motions = available_motions
        self.motion_name_map = motion_name_map
        self.on_play_motion = on_play_motion
        self.on_pet_changed = on_pet_changed
        self.on_voice_pack_changed = on_voice_pack_changed
        self.on_tts_settings_changed = on_tts_settings_changed
        self.on_read_text = on_read_text
        self.on_stop_read_text = on_stop_read_text
        self.on_pet_settings_changed = on_pet_settings_changed
        self.stats = {"mood": 85, "energy": 72, "affection": 90}
        self._page = "dashboard"
        self._pet_main_id: str | None = None
        self._sel_pet: str | None = None
        self._voice_pack_id = (current_voice_pack_id or "").strip()
        self._voice_packs: list[dict] = []
        self._read_documents: list[BookDocument] = []
        self._tts_settings = normalize_tts_settings(current_tts_settings)
        self._tts_control_syncing = False
        self._pet_settings_path = os.path.join(
            self._project_root,
            "data",
            "pet_personalization_settings.json",
        )
        self._pet_settings = self._load_pet_personalization_settings()
        self._pet_setting_controls: dict[tuple[str, str], QWidget] = {}
        self._char_tab = 0
        self._ai_i = -1
        self._detail_pic: QLabel | None = None
        self._anim_frames: list[str] = []
        self._anim_index = 0
        self._anim_idle_path = ""
        self._anim_pic_size = QSize(260, 170)
        self._anim_movie: QMovie | None = None
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._on_anim_frame)
        self._toast: QLabel | None = None
        self._chat_store = ChatHistoryStore(project_root)
        self._custom_ids = load_custom_pet_ids(project_root)
        # 自动扫描 assets/models/ 下所有 Live2D 模型
        from app.live2d_scanner import scan_live2d_models
        models_dir = os.path.join(project_root, "assets", "models")
        scanned = scan_live2d_models(models_dir)
        if scanned:
            self._live2d = scanned
            # 修正 mao_pro_zh 的显示名和缩略图
            for i, pet in enumerate(self._live2d):
                if pet["id"] == "mao_pro_zh" and is_mao_pro_zh_model(model_path):
                    self._live2d[i] = build_mao_pro_pet_record(model_path, available_motions)
                    break
        elif is_mao_pro_zh_model(model_path):
            self._live2d = [build_mao_pro_pet_record(model_path, available_motions)]
        else:
            tex = resolve_live2d_thumb(model_path) or ""
            motions = [
                {"id": m, "label": m, "gif": "", "frames": []}
                for m in available_motions
            ] or [{"id": "mtn_01", "label": "mtn_01", "gif": "", "frames": []}]
            self._live2d = [
                {
                    "id": "mao",
                    "name": "小黑",
                    "thumb": tex,
                    "personality": "活泼可爱的 AI 桌宠，喜欢陪伴你学习与工作。",
                    "motions": motions,
                    "model_path": model_path,
                    "is_flat": False,
                },
            ]
        self._flat = [
            apply_zhegou_idle_thumb(project_root, p)
            for p in scan_flat_pets(project_root, include_custom=False)
        ]
        self._custom_pets = self._build_custom_pet_list()
        self._current_pet_id = self._live2d[0]["id"] if self._live2d else (self._flat[0]["id"] if self._flat else "")
        self._chats: list[dict] = []
        self._load_chat_histories()
        self._build_ui()
        self._console_scale_widgets: list[tuple[QWidget, int]] = []
        self._collect_console_scale_targets()
        QTimer.singleShot(0, self._apply_console_ui_scale)

    def _collect_console_scale_targets(self) -> None:
        self._console_scale_widgets = []
        for lbl in self.findChildren(QLabel):
            px = lbl.font().pointSize()
            if px > 0:
                self._console_scale_widgets.append((lbl, px))
        for btn in self.findChildren(QPushButton):
            px = btn.font().pointSize()
            if px > 0:
                self._console_scale_widgets.append((btn, px))
        for tab in self.findChildren(QTabWidget):
            px = tab.font().pointSize()
            if px > 0:
                self._console_scale_widgets.append((tab, px))
        for combo in self.findChildren(QComboBox):
            px = combo.font().pointSize()
            if px > 0:
                self._console_scale_widgets.append((combo, px))

    def _console_ui_scale(self) -> float:
        return max(0.82, min(1.2, self.width() / 800))

    def _apply_console_ui_scale(self) -> None:
        scale = self._console_ui_scale()
        for widget, base_px in self._console_scale_widgets:
            px = max(9, int(round(base_px * scale)))
            f = widget.font()
            f.setPointSize(px)
            widget.setFont(f)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_console_ui_scale()

    def closeEvent(self, event) -> None:
        event.ignore()
        self.hide()

    def _rescan_flat_pets(self) -> None:
        self._flat = [
            apply_zhegou_idle_thumb(self._project_root, p)
            for p in scan_flat_pets(self._project_root, include_custom=False)
        ]

    def _build_custom_pet_list(self) -> list[dict]:
        all_by_id = {p["id"]: p for p in scan_flat_pets(self._project_root, include_custom=True)}
        pets: list[dict] = []
        for cid in self._custom_ids:
            raw = all_by_id.get(cid)
            if not raw:
                continue
            p = self._enrich_pet_motions(dict(raw))
            p["is_custom"] = True
            pets.append(apply_zhegou_idle_thumb(self._project_root, p))
        return pets

    def _flat_library_pets(self) -> list[dict]:
        """平面素材库：不含自定义标签页上传的角色。"""
        return [p for p in self._flat if p.get("id") not in self._custom_ids]

    def _enrich_pet_motions(self, pet: dict) -> dict:
        pet = dict(pet)
        if pet.get("is_flat"):
            pet_id = pet.get("id", "")
            motions: list[dict] = []
            anim_dir = os.path.join(self._project_root, "assets", "animations", pet_id)
            scan_dirs = [anim_dir] if os.path.isdir(anim_dir) else []
            root_anim = os.path.join(self._project_root, "assets", "animations")
            if os.path.isdir(root_anim):
                scan_dirs.append(root_anim)
            seen: set[str] = set()
            for folder in scan_dirs:
                in_sub = folder.endswith(pet_id)
                for fname in sorted(os.listdir(folder)):
                    if not fname.lower().endswith(".gif"):
                        continue
                    if not in_sub and not fname.startswith(f"{pet_id}_"):
                        continue
                    path = os.path.normpath(os.path.join(folder, fname))
                    if path in seen:
                        continue
                    seen.add(path)
                    motions.append(
                        {
                            "id": f"file:{fname}",
                            "label": motion_label_from_filename(fname),
                            "gif": path,
                            "frames": [],
                        }
                    )
            if motions:
                pet["motions"] = motions
        return apply_zhegou_idle_thumb(self._project_root, pet)

    def _log(self, msg: str) -> None:
        print(f"[ControlConsole] {msg}")

    def _load_chat_histories(self) -> None:
        self._chats = []
        for name in self._chat_store.list_characters():
            msgs = self._chat_store.load(name)
            if msgs:
                self._chats.append({"name": name, "color": "#ec4899", "msgs": msgs})
        if not self._chats:
            self._chats.append({"name": "默认", "color": "#3b82f6", "msgs": []})

    def _save_current_chat(self) -> None:
        if self._ai_i < 0 or self._ai_i >= len(self._chats):
            return
        chat = self._chats[self._ai_i]
        self._chat_store.save(chat["name"], chat["msgs"])

    def bring_to_front(self) -> None:
        """显示并置顶设置面板（重复打开时仍到最前）。"""
        state = self.windowState() & ~Qt.WindowState.WindowMinimized
        self.setWindowState(state)
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _build_ui(self) -> None:
        self.setWindowTitle("桌面宠物控制台")
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.Window
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.resize(800, 600)
        self.setMinimumSize(720, 540)
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self._drag_bar = ConsoleDragBar(self, "桌面宠物控制台")
        outer.addWidget(self._drag_bar)

        root = QHBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QFrame()
        sidebar.setFixedWidth(260)
        sidebar.setStyleSheet("background: rgba(255,255,255,220);")
        sb_lay = QVBoxLayout(sidebar)
        sb_lay.setContentsMargins(16, 24, 16, 16)
        title = QLabel("Pet Console")
        title.setFont(_app_font(20, True))
        sb_lay.addWidget(title)
        sb_lay.addWidget(QLabel("桌面宠物"))
        self._menu_btns: dict[str, QPushButton] = {}
        for pid, icon, label in (
            ("pet_settings", "⚙️", "桌宠设置"),
            ("dashboard", "📊", "仪表盘"),
            ("characters", "👤", "角色选择"),
            ("ai_settings", "💬", "AI对话"),
            ("permissions", "🔒", "权限设置"),
            ("theme", "🎨", "主题"),
            ("exit", "🚪", "退出"),
        ):
            btn = QPushButton(f"{icon}  {label}")
            btn.setStyleSheet(BTN_GLASS)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _=False, p=pid: self._nav(p))
            sb_lay.addWidget(btn)
            self._menu_btns[pid] = btn
        sb_lay.addStretch()
        root.addWidget(sidebar)

        right = QVBoxLayout()
        self._stack = QStackedWidget()
        self._stack.addWidget(self._page_pet_settings())
        self._stack.addWidget(self._page_dashboard())
        self._stack.addWidget(self._page_characters())
        self._stack.addWidget(self._page_ai())
        self._stack.addWidget(self._page_placeholder("权限设置"))
        self._stack.addWidget(self._page_placeholder("主题"))
        self._stack.addWidget(self._page_pet_main())
        right.addWidget(self._stack, 1)
        root.addLayout(right, 1)
        outer.addLayout(root, 1)
        self._nav("dashboard")

    def _toggle_max(self) -> None:
        self.showNormal() if self.isMaximized() else self.showMaximized()

    def _nav(self, page: str) -> None:
        if page == "exit":
            self.close()
            return
        self._page = page
        idx = {
            "pet_settings": 0,
            "dashboard": 1,
            "characters": 2,
            "ai_settings": 3,
            "permissions": 4,
            "theme": 5,
            "pet_main": 6,
        }.get(page, 0)
        self._stack.setCurrentIndex(idx)
        for pid, btn in self._menu_btns.items():
            btn.setChecked(pid == page or (page == "pet_main" and pid == "characters"))
        if page == "pet_main":
            self._refresh_pet_main()
        if page == "dashboard":
            self._refresh_dashboard()
        self._log(f"切换: {page}")

    def _get_pet(self, pet_id: str | None) -> dict | None:
        if not pet_id:
            return None
        for pet in self._live2d + self._flat:
            if pet["id"] == pet_id:
                return pet
        return None

    def _pet_idle_path(self, pet: dict) -> str:
        return pet.get("idle_image") or pet.get("thumb", "")

    def _motion_playable(self, motion: dict) -> bool:
        gif = motion.get("gif") or ""
        frames = motion.get("frames") or []
        return bool(gif and os.path.isfile(gif)) or bool(frames)

    def _stop_animation(self) -> None:
        if self._anim_timer.isActive():
            self._anim_timer.stop()
        if self._anim_movie is not None:
            self._anim_movie.stop()
            try:
                self._anim_movie.finished.disconnect(self._on_gif_finished)
            except (RuntimeError, TypeError):
                pass
            if self._detail_pic is not None:
                self._detail_pic.setMovie(None)
            self._anim_movie = None
        self._anim_frames = []
        self._anim_index = 0

    def _restore_idle_pic(self) -> None:
        if self._detail_pic is None or not self._anim_idle_path:
            return
        self._detail_pic.setMovie(None)
        self._detail_pic.setPixmap(_load_pixmap(self._anim_idle_path, self._anim_pic_size))

    def _play_motion(self, motion: dict, pic_label: QLabel, idle_path: str, size: QSize) -> None:
        gif = motion.get("gif") or ""
        frames = motion.get("frames") or []
        if not self._motion_playable(motion):
            if motion.get("id") and self.on_play_motion:
                self.on_play_motion(motion["id"])
            return
        self._stop_animation()
        self._detail_pic = pic_label
        self._anim_idle_path = idle_path
        self._anim_pic_size = size
        if gif and os.path.isfile(gif):
            self._anim_movie = QMovie(gif)
            self._anim_movie.setScaledSize(size)
            pic_label.setMovie(self._anim_movie)
            self._anim_movie.setLoopCount(1)
            self._anim_movie.finished.connect(self._on_gif_finished)
            self._anim_movie.start()
            return
        self._anim_frames = frames
        self._anim_index = 0
        self._on_anim_frame()
        self._anim_timer.start(100)

    def _on_gif_finished(self) -> None:
        self._restore_idle_pic()
        if self._anim_movie is not None:
            try:
                self._anim_movie.finished.disconnect(self._on_gif_finished)
            except (RuntimeError, TypeError):
                pass
            self._anim_movie = None

    def _on_anim_frame(self) -> None:
        if not self._anim_frames or self._detail_pic is None:
            self._stop_animation()
            return
        path = self._anim_frames[self._anim_index]
        self._detail_pic.setPixmap(_load_pixmap(path, self._anim_pic_size))
        self._anim_index += 1
        if self._anim_index >= len(self._anim_frames):
            self._anim_timer.stop()
            self._restore_idle_pic()
            self._anim_frames = []
            self._anim_index = 0

    def _current_pet(self) -> dict | None:
        return self._get_pet(self._current_pet_id)

    def _refresh_dashboard(self) -> None:
        pet = self._current_pet()
        if not pet or not hasattr(self, "_dash_pet_pic"):
            return
        desk = getattr(self, "_desk", None)
        if pet.get("is_flat") and desk is not None:
            pet = desk.build_pet_record(pet.get("id", "")) or pet
        thumb = pet.get("thumb") or self._pet_idle_path(pet)
        self._dash_pet_pic.setPixmap(_load_pixmap(thumb, QSize(100, 100)))
        self._dash_pet_name.setText(f"<b>{pet['name']}</b>")
        self._dash_pet_personality.setText(pet.get("personality", ""))

    def _switch_current_pet(self, pet: dict) -> None:
        self._apply_pet_switch(pet)

    def _open_pet_main(self, pet: dict) -> None:
        self._pet_main_id = pet["id"]
        self._nav("pet_main")
        self._log(f"查看角色: {pet['name']}")

    def _apply_pet_switch(self, pet: dict) -> None:
        self._rescan_flat_pets()
        pet = self._get_pet(pet["id"]) or pet
        self._current_pet_id = pet["id"]
        self._sel_pet = pet["id"]
        self._pet_main_id = pet["id"]
        self._stop_animation()
        self._show_toast(f"已切换到 {pet['name']}")
        self._nav("dashboard")
        self._log(f"切换角色: {pet['name']} ({pet['id']})")
        if self.on_pet_changed:
            self.on_pet_changed(pet)

    def _show_toast(self, message: str) -> None:
        if self._toast is None:
            self._toast = QLabel(self)
            self._toast.setStyleSheet(
                "background-color: rgba(30, 41, 59, 220); color: white;"
                "border-radius: 10px; padding: 10px 18px; font-size: 14px;"
            )
            self._toast.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._toast.setText(message)
        self._toast.adjustSize()
        x = (self.width() - self._toast.width()) // 2
        y = self.height() - self._toast.height() - 36
        self._toast.move(max(16, x), max(16, y))
        self._toast.raise_()
        self._toast.show()
        QTimer.singleShot(2200, self._toast.hide)

    @staticmethod
    def _default_pet_personalization_settings() -> dict[str, dict[str, Any]]:
        return json.loads(json.dumps(DEFAULT_PET_PERSONALIZATION_SETTINGS))

    @staticmethod
    def _setting_bool(value: Any) -> bool:
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y", "on", "开启", "允许", "记住"}
        return bool(value)

    def _load_pet_personalization_settings(self) -> dict[str, dict[str, Any]]:
        data = self._default_pet_personalization_settings()
        if not os.path.isfile(self._pet_settings_path):
            return data
        try:
            with open(self._pet_settings_path, encoding="utf-8") as f:
                loaded = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            self._log(f"读取桌宠设置失败，使用默认值: {exc}")
            return data
        if not isinstance(loaded, dict):
            return data
        for section in PET_PERSONALIZATION_SECTIONS:
            section_key = str(section["key"])
            incoming = loaded.get(section_key)
            if not isinstance(incoming, dict):
                continue
            for field in section["fields"]:
                field_key = str(field["key"])
                if field_key in incoming:
                    data[section_key][field_key] = incoming[field_key]
        return data

    def _save_pet_personalization_settings(self) -> bool:
        try:
            os.makedirs(os.path.dirname(self._pet_settings_path), exist_ok=True)
            with open(self._pet_settings_path, "w", encoding="utf-8") as f:
                json.dump(self._pet_settings, f, ensure_ascii=False, indent=2)
            return True
        except OSError as exc:
            QMessageBox.warning(self, "保存失败", f"无法保存桌宠设置：{exc}")
            return False

    def _pet_setting_value(self, section_key: str, field_key: str) -> Any:
        section = self._pet_settings.get(section_key, {})
        if field_key in section:
            return section[field_key]
        return DEFAULT_PET_PERSONALIZATION_SETTINGS.get(section_key, {}).get(field_key, "")

    def _set_combo_text(self, combo: QComboBox, value: Any) -> None:
        text = str(value or "")
        idx = combo.findText(text)
        if idx < 0 and text:
            combo.addItem(text)
            idx = combo.findText(text)
        combo.setCurrentIndex(max(0, idx))

    def _create_pet_setting_control(self, field: dict[str, Any], value: Any) -> tuple[QWidget, QWidget]:
        control_type = str(field.get("type") or "line")
        if control_type == "combo":
            combo = QComboBox()
            for option in field.get("options", ()):
                combo.addItem(str(option))
            combo.setMinimumWidth(220)
            self._set_combo_text(combo, value)
            return combo, combo
        if control_type == "check":
            check = QCheckBox(str(field.get("text") or "开启"))
            check.setChecked(self._setting_bool(value))
            return check, check
        if control_type == "slider":
            wrap = QWidget()
            row = QHBoxLayout(wrap)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(10)
            slider = QSlider(Qt.Orientation.Horizontal)
            minimum = int(field.get("min", 0))
            maximum = int(field.get("max", 100))
            slider.setRange(minimum, maximum)
            try:
                current = int(value)
            except (TypeError, ValueError):
                current = minimum
            slider.setValue(max(minimum, min(maximum, current)))
            value_label = QLabel()
            value_label.setMinimumWidth(48)
            value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            suffix = str(field.get("suffix") or "")

            def _update_slider_label(v: int, label: QLabel = value_label, unit: str = suffix) -> None:
                label.setText(f"{v}{unit}")

            slider.valueChanged.connect(_update_slider_label)
            _update_slider_label(slider.value())
            row.addWidget(slider, 1)
            row.addWidget(value_label)
            return wrap, slider
        line = QLineEdit()
        line.setText(str(value or ""))
        line.setPlaceholderText(str(field.get("placeholder") or ""))
        return line, line

    def _read_pet_setting_control(self, control: QWidget) -> Any:
        if isinstance(control, QComboBox):
            return control.currentText()
        if isinstance(control, QCheckBox):
            return control.isChecked()
        if isinstance(control, QSlider):
            return control.value()
        if isinstance(control, QLineEdit):
            return control.text().strip()
        return ""

    def _set_pet_setting_control_value(self, control: QWidget, value: Any) -> None:
        if isinstance(control, QComboBox):
            self._set_combo_text(control, value)
        elif isinstance(control, QCheckBox):
            control.setChecked(self._setting_bool(value))
        elif isinstance(control, QSlider):
            try:
                control.setValue(int(value))
            except (TypeError, ValueError):
                pass
        elif isinstance(control, QLineEdit):
            control.setText(str(value or ""))

    def _apply_pet_personalization_controls(self) -> None:
        for section in PET_PERSONALIZATION_SECTIONS:
            section_key = str(section["key"])
            for field in section["fields"]:
                field_key = str(field["key"])
                control = self._pet_setting_controls.get((section_key, field_key))
                if control is not None:
                    self._set_pet_setting_control_value(
                        control,
                        self._pet_setting_value(section_key, field_key),
                    )

    def _collect_pet_personalization_controls(self) -> dict[str, dict[str, Any]]:
        data = self._default_pet_personalization_settings()
        for section in PET_PERSONALIZATION_SECTIONS:
            section_key = str(section["key"])
            for field in section["fields"]:
                field_key = str(field["key"])
                control = self._pet_setting_controls.get((section_key, field_key))
                if control is not None:
                    data[section_key][field_key] = self._read_pet_setting_control(control)
        return data

    def _save_pet_personalization_from_controls(self) -> None:
        self._pet_settings = self._collect_pet_personalization_controls()
        if self._save_pet_personalization_settings():
            if self.on_pet_settings_changed:
                self.on_pet_settings_changed(dict(self._pet_settings))
            if hasattr(self, "_pet_settings_status"):
                self._pet_settings_status.setText("已保存")
            self._show_toast("桌宠设置已保存")
            self._log("桌宠设置已保存")

    def _reset_pet_personalization_settings(self) -> None:
        self._pet_settings = self._default_pet_personalization_settings()
        self._apply_pet_personalization_controls()
        if self._save_pet_personalization_settings():
            if self.on_pet_settings_changed:
                self.on_pet_settings_changed(dict(self._pet_settings))
            if hasattr(self, "_pet_settings_status"):
                self._pet_settings_status.setText("已恢复默认")
            self._show_toast("桌宠设置已恢复默认")
            self._log("桌宠设置已恢复默认")

    def _build_pet_setting_section(self, index: int, section: dict[str, Any]) -> QFrame:
        section_key = str(section["key"])
        frame = QFrame()
        frame.setObjectName("glass")
        frame.setStyleSheet(_glass_style(14))
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(16, 12, 16, 14)
        lay.setSpacing(8)

        title = QLabel(f"<b>{index}. {section.get('icon', '')} {section.get('title', '')}</b>")
        title.setWordWrap(True)
        lay.addWidget(title)
        summary = QLabel(str(section.get("summary") or ""))
        summary.setWordWrap(True)
        summary.setStyleSheet("color:#64748b;")
        lay.addWidget(summary)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(1, 1)
        for row, field in enumerate(section["fields"]):
            field_key = str(field["key"])
            label = QLabel(str(field.get("label") or field_key))
            label.setMinimumWidth(96)
            label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            widget, control = self._create_pet_setting_control(
                field,
                self._pet_setting_value(section_key, field_key),
            )
            self._pet_setting_controls[(section_key, field_key)] = control
            grid.addWidget(label, row, 0)
            grid.addWidget(widget, row, 1)
        lay.addLayout(grid)
        return frame

    def _page_pet_settings(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(24, 16, 24, 24)
        lay.setSpacing(12)

        header = QHBoxLayout()
        header.addWidget(QLabel("<h2>桌宠设置</h2>"))
        header.addStretch()
        self._pet_settings_status = QLabel("")
        self._pet_settings_status.setStyleSheet("color:#64748b;")
        header.addWidget(self._pet_settings_status)
        reset_btn = QPushButton("恢复默认")
        reset_btn.setStyleSheet(BTN_GLASS)
        reset_btn.clicked.connect(self._reset_pet_personalization_settings)
        save_btn = QPushButton("保存设置")
        save_btn.setStyleSheet(BTN_PRIMARY)
        save_btn.clicked.connect(self._save_pet_personalization_from_controls)
        header.addWidget(reset_btn)
        header.addWidget(save_btn)
        lay.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        inner_lay = QVBoxLayout(inner)
        inner_lay.setContentsMargins(0, 0, 8, 0)
        inner_lay.setSpacing(12)
        self._pet_setting_controls.clear()
        for index, section in enumerate(PET_PERSONALIZATION_SECTIONS, start=1):
            inner_lay.addWidget(self._build_pet_setting_section(index, section))
        inner_lay.addStretch()
        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)
        return w

    def _on_pet_main_switch(self) -> None:
        pet = self._get_pet(self._pet_main_id)
        if pet:
            self._apply_pet_switch(pet)

    def _stat_card(self, icon: str, title: str, val: int, color: str) -> QFrame:
        f = QFrame()
        f.setStyleSheet(_glass_style(14))
        lay = QVBoxLayout(f)
        row = QHBoxLayout()
        row.addWidget(QLabel(icon))
        row.addWidget(QLabel(title))
        row.addStretch()
        row.addWidget(QLabel(str(val)))
        lay.addLayout(row)
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(val)
        bar.setTextVisible(False)
        bar.setStyleSheet(f"QProgressBar {{ background:#e2e8f0; border-radius:4px; height:8px; }} QProgressBar::chunk {{ background:{color}; border-radius:4px; }}")
        lay.addWidget(bar)
        return f

    def _page_dashboard(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(24, 16, 24, 24)
        now = datetime.datetime.now()
        wd = "一二三四五六日"[now.weekday()]
        lay.addWidget(QLabel(f"<h2>欢迎回来，用户</h2><p>{now.year}年{now.month}月{now.day}日 星期{wd}</p>"))
        cards = QHBoxLayout()
        for icon, title, key, col in (("🐾", "宠物心情", "mood", "#3b82f6"), ("🔥", "能量值", "energy", "#fb923c"), ("❤️", "好感度", "affection", "#ec4899")):
            cards.addWidget(self._stat_card(icon, title, self.stats[key], col))
        lay.addLayout(cards)
        lay.addWidget(QLabel("<h3>当前宠物简介</h3>"))
        intro = QFrame()
        intro.setStyleSheet(_glass_style(14))
        il = QHBoxLayout(intro)
        self._dash_pet_pic = QLabel()
        self._dash_pet_pic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        il.addWidget(self._dash_pet_pic)
        tx = QVBoxLayout()
        self._dash_pet_name = QLabel()
        self._dash_pet_personality = QLabel()
        self._dash_pet_personality.setWordWrap(True)
        tx.addWidget(self._dash_pet_name)
        tx.addWidget(self._dash_pet_personality)
        il.addLayout(tx, 1)
        lay.addWidget(intro)
        lay.addStretch()
        return w

    def _page_synonyms_placeholder(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("<h2>同义词管理</h2>"))
        ph = QLabel("请从桌宠设置面板打开以管理同义词。")
        ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph.setStyleSheet("color:#94a3b8;font-size:16px;")
        lay.addWidget(ph, 1)
        return w

    def _live2d_library_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        entry = QFrame()
        entry.setObjectName("glass")
        entry.setStyleSheet(_glass_style(16))
        entry_lay = QHBoxLayout(entry)
        entry_lay.setContentsMargins(16, 12, 16, 12)
        title = QLabel("<b>Live2D 白膜建模</b>")
        title.setFont(_app_font(14, True))
        entry_lay.addWidget(title)
        entry_lay.addStretch()
        open_btn = QPushButton("Live2D建模")
        open_btn.setStyleSheet(BTN_PRIMARY)
        open_btn.clicked.connect(self._open_live2d_modeling)
        entry_lay.addWidget(open_btn)
        lay.addWidget(entry)
        lay.addWidget(self._char_grid(self._live2d, add_plus=True, on_plus=self._upload_live2d), 1)
        return w

    def _page_characters(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(24, 16, 24, 24)
        lay.addWidget(QLabel("<h2>角色选择</h2>"))
        outer = QHBoxLayout()
        self._tabs = QTabWidget()
        self._tabs.addTab(self._live2d_library_tab(), "Live2D库")
        self._tabs.addTab(self._char_grid(self._flat_library_pets(), add_plus=False), "平面素材库")
        custom_wrap = QWidget()
        custom_lay = QVBoxLayout(custom_wrap)
        custom_lay.addWidget(
            self._char_grid(self._custom_pets, add_plus=False, empty_hint="暂无自定义素材"),
            1,
        )
        up_row = QHBoxLayout()
        up_row.addStretch()
        up = QPushButton("上传平面素材")
        up.setStyleSheet(BTN_PRIMARY)
        up.clicked.connect(self._upload_flat)
        up_row.addWidget(up)
        up_row.addStretch()
        custom_lay.addLayout(up_row)
        self._tabs.addTab(custom_wrap, "自定义")
        outer.addWidget(self._tabs, 1)
        self._detail = QFrame()
        self._detail.setFixedWidth(300)
        self._detail.setStyleSheet(_glass_style(16))
        self._detail_lay = QVBoxLayout(self._detail)
        self._detail.hide()
        outer.addWidget(self._detail)
        lay.addLayout(outer, 1)
        return w

    def _char_grid(
        self,
        pets: list[dict],
        add_plus: bool = False,
        on_plus: Callable[[], None] | None = None,
        *,
        empty_hint: str | None = None,
    ) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        grid = QGridLayout(inner)
        if not pets and not add_plus:
            hint_text = empty_hint or (
                "暂无平面素材\n请将 {pet_id}_image.png 放入 assets/images/\n"
                "动图放入 assets/animations/"
            )
            hint = QLabel(hint_text)
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hint.setStyleSheet("color:#94a3b8;padding:32px;font-size:13px;")
            grid.addWidget(hint, 0, 0, 1, 4)
        for i, pet in enumerate(pets):
            cell = self._pet_cell(pet)
            grid.addWidget(cell, i // 4, i % 4)
        if add_plus:
            plus = QPushButton("+")
            plus.setFixedSize(128, 128)
            plus.clicked.connect(on_plus or (lambda: self._log("上传")))
            grid.addWidget(plus, len(pets) // 4, len(pets) % 4)
        scroll.setWidget(inner)
        return scroll

    def _open_live2d_modeling(self) -> None:
        dlg = Live2dModelingDialog(self._project_root, self)
        dlg.exec()

    def _upload_live2d(self) -> None:
        dlg = Live2dUploadDialog(self._project_root, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            pet = dlg.result_pet()
            if pet:
                self._live2d.append(pet)
                self._reload_character_tabs()
                self._show_toast(f"已添加 Live2D 角色: {pet['name']}")

    def _upload_flat(self) -> None:
        dlg = FlatUploadDialog(self._project_root, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            pet = dlg.result_pet()
            if pet:
                pet_id = pet.get("id", "")
                ids = load_custom_pet_ids(self._project_root)
                if pet_id not in ids:
                    ids.append(pet_id)
                save_custom_pet_ids(self._project_root, ids)
                self._custom_ids = ids
                self._rescan_flat_pets()
                self._custom_pets = self._build_custom_pet_list()
                self._reload_character_tabs()
                self._tabs.setCurrentIndex(2)
                self._show_toast(f"已添加自定义角色: {pet['name']}")

    def _on_pet_context_action(self, action: str, pet: dict) -> None:
        if action == "delete":
            PetCharacterOps.delete_pet(self, pet)
        elif action == "rename":
            PetCharacterOps.rename_pet(self, pet)
        elif action == "personality":
            PetCharacterOps.edit_personality(self, pet)
        elif action == "actions":
            PetCharacterOps.manage_actions(self, pet)
        elif action == "action_map":
            PetCharacterOps.setup_action_mapping(self, pet)

    def _reload_character_tabs(self) -> None:
        if not hasattr(self, "_tabs"):
            return
        idx = self._tabs.currentIndex()
        self._custom_pets = self._build_custom_pet_list()
        while self._tabs.count():
            self._tabs.removeTab(0)
        self._tabs.addTab(
            self._live2d_library_tab(),
            "Live2D库",
        )
        self._tabs.addTab(self._char_grid(self._flat_library_pets(), add_plus=False), "平面素材库")
        custom_wrap = QWidget()
        custom_lay = QVBoxLayout(custom_wrap)
        custom_lay.addWidget(
            self._char_grid(self._custom_pets, add_plus=False, empty_hint="暂无自定义素材"),
            1,
        )
        up_row = QHBoxLayout()
        up_row.addStretch()
        up = QPushButton("上传平面素材")
        up.setStyleSheet(BTN_PRIMARY)
        up.clicked.connect(self._upload_flat)
        up_row.addWidget(up)
        up_row.addStretch()
        custom_lay.addLayout(up_row)
        self._tabs.addTab(custom_wrap, "自定义")
        self._tabs.setCurrentIndex(min(idx, self._tabs.count() - 1))

    def _pet_cell(self, pet: dict) -> _PetCellButton:
        btn = _PetCellButton(pet)
        btn.single_clicked_pet.connect(self._select_pet)
        btn.double_clicked_pet.connect(self._open_pet_main)
        btn.pet_context_action.connect(self._on_pet_context_action)
        return btn

    def _select_pet(self, pet: dict) -> None:
        if pet.get("is_flat"):
            pet = self._enrich_pet_motions(pet)
        self._sel_pet = pet["id"]
        self._show_detail(pet)
        self._log(f"选中: {pet['name']}")

    def _open_pet_main(self, pet: dict) -> None:
        if pet.get("is_flat") or pet.get("is_custom"):
            pet = self._enrich_pet_motions(pet)
            self._apply_pet_switch(pet)
            return
        self._pet_main_id = pet["id"]
        self._nav("pet_main")
        self._log(f"查看角色: {pet['name']}")

    def _show_detail(self, pet: dict) -> None:
        self._stop_animation()
        while self._detail_lay.count():
            w = self._detail_lay.takeAt(0).widget()
            if w:
                w.deleteLater()
        idle_path = self._pet_idle_path(pet)
        pic = QLabel()
        pic.setPixmap(_load_pixmap(idle_path, QSize(260, 170)))
        pic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._detail_pic = pic
        self._detail_lay.addWidget(pic)
        self._detail_lay.addWidget(QLabel(f"<b>{pet['name']}</b>"))
        self._detail_lay.addWidget(QLabel(pet.get("personality", "")))
        self._detail.show()

    def _page_pet_main(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(24, 16, 24, 24)
        top = QHBoxLayout()
        back = QPushButton("← 返回")
        back.clicked.connect(lambda: self._nav("dashboard"))
        top.addStretch()
        top.addWidget(back)
        lay.addLayout(top)
        body = QHBoxLayout()
        left = QFrame()
        left.setStyleSheet(_glass_style(16))
        ll = QVBoxLayout(left)
        self._pet_main_name = QLabel()
        ll.addWidget(self._pet_main_name)
        self._pet_main_switch_btn = QPushButton("切换该角色")
        self._pet_main_switch_btn.setObjectName("switchPetBtn")
        self._pet_main_switch_btn.setStyleSheet(BTN_SWITCH)
        self._pet_main_switch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pet_main_switch_btn.clicked.connect(self._on_pet_main_switch)
        ll.addWidget(self._pet_main_switch_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        row = QHBoxLayout()
        self._pet_main_pic = QLabel()
        self._pet_main_pic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self._pet_main_pic)
        tx = QVBoxLayout()
        self._pet_main_desc = QLabel("AI小助手·你的桌面陪伴")
        tx.addWidget(self._pet_main_desc)
        for ln in ("轻量陪伴", "贴心助手", "治愈每一天"):
            tx.addWidget(QLabel(ln))
        row.addLayout(tx)
        ll.addLayout(row)
        body.addWidget(left, 1)
        lay.addLayout(body)
        lay.addWidget(QLabel("<h3>宠物状态</h3>"))
        stats = QHBoxLayout()
        for icon, title, key, col in (("😊", "心情", "mood", "#3b82f6"), ("⚡", "能量", "energy", "#fb923c"), ("❤️", "好感度", "affection", "#ec4899")):
            stats.addWidget(self._stat_card(icon, title, self.stats[key], col))
        lay.addLayout(stats)
        lay.addStretch()
        return w

    def _refresh_pet_main(self) -> None:
        pet = self._get_pet(self._pet_main_id)
        if not pet or not hasattr(self, "_pet_main_pic"):
            return
        idle_path = self._pet_idle_path(pet)
        self._pet_main_name.setText(f"<h2>{pet['name']}</h2>")
        self._pet_main_desc.setText(pet.get("personality", ""))
        self._pet_main_pic.setPixmap(_load_pixmap(idle_path, QSize(120, 120)))

    def _page_ai(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(24, 16, 24, 24)
        lay.setSpacing(16)

        menu_panel = QFrame()
        menu_panel.setFixedWidth(190)
        menu_panel.setStyleSheet(_glass_style(14))
        menu_lay = QVBoxLayout(menu_panel)
        menu_lay.addWidget(QLabel("<b>AI 对话</b>"))
        self._ai_tool_btns: dict[str, QPushButton] = {}
        for key, icon, label in (
            ("voice_pack", "🎙️", "语音包"),
            ("language", "🌐", "语言"),
            ("text_reader", "📖", "文本朗读"),
            ("history", "💬", "聊天记录"),
            ("voice_settings", "🔊", "语音设置"),
        ):
            btn = QPushButton(f"{icon}  {label}")
            btn.setCheckable(True)
            btn.setStyleSheet(BTN_GLASS)
            btn.clicked.connect(lambda _=False, k=key: self._switch_ai_tool(k))
            menu_lay.addWidget(btn)
            self._ai_tool_btns[key] = btn
        menu_lay.addStretch()
        lay.addWidget(menu_panel)

        self._ai_tool_stack = QStackedWidget()
        self._ai_tool_stack.addWidget(self._ai_voice_pack_page())
        self._ai_tool_stack.addWidget(self._ai_language_page())
        self._ai_tool_stack.addWidget(self._ai_text_reader_page())
        self._ai_tool_stack.addWidget(self._ai_history_page())
        self._ai_tool_stack.addWidget(self._ai_voice_settings_page())
        lay.addWidget(self._ai_tool_stack, 1)

        if self._chats:
            self._pick_chat(0)
        self._apply_tts_controls_from_settings()
        self._refresh_voice_pack_list()
        self._switch_ai_tool("voice_pack")
        return w

    def _ai_voice_pack_page(self) -> QWidget:
        page = QFrame()
        page.setStyleSheet(_glass_style(14))
        lay = QVBoxLayout(page)
        header = QHBoxLayout()
        header.addWidget(QLabel("<b>语音包</b>"))
        header.addStretch()
        import_btn = QPushButton("导入语音包")
        import_btn.setStyleSheet(BTN_PRIMARY)
        import_btn.clicked.connect(self._import_voice_pack)
        header.addWidget(import_btn)
        lay.addLayout(header)
        self._voice_pack_list = QListWidget()
        self._voice_pack_list.itemClicked.connect(self._pick_voice_pack_by_item)
        lay.addWidget(self._voice_pack_list, 1)
        self._voice_pack_detail = QLabel()
        self._voice_pack_detail.setWordWrap(True)
        self._voice_pack_detail.setStyleSheet("color:#64748b;font-size:12px;")
        lay.addWidget(self._voice_pack_detail)
        return page

    def _ai_language_page(self) -> QWidget:
        page = QFrame()
        page.setStyleSheet(_glass_style(14))
        lay = QVBoxLayout(page)
        lay.addWidget(QLabel("<b>语言</b>"))

        row = QHBoxLayout()
        row.addWidget(QLabel("AI 回复语言"))
        self._reply_language_combo = QComboBox()
        for preset in VOICE_PACK_LANGUAGE_PRESETS:
            self._reply_language_combo.addItem(str(preset["label"]), str(preset["id"]))
        self._reply_language_combo.currentIndexChanged.connect(self._on_reply_language_changed)
        row.addWidget(self._reply_language_combo, 1)
        lay.addLayout(row)

        self._reply_language_detail = QLabel()
        self._reply_language_detail.setWordWrap(True)
        self._reply_language_detail.setStyleSheet("color:#64748b;font-size:12px;")
        lay.addWidget(self._reply_language_detail)
        lay.addStretch()

        self._apply_reply_language_control_from_settings()
        return page

    def _import_voice_pack(self) -> None:
        dlg = VoicePackImportDialog(self._project_root, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        pack = dlg.result_pack()
        if not pack:
            return
        pack_id = str(pack.get("id") or "").strip()
        self._refresh_voice_pack_list()
        selected = next(
            (p for p in self._voice_packs if str(p.get("id", "")).strip() == pack_id),
            pack,
        )
        self._select_voice_pack(selected, toast_prefix="已导入并切换语音包")

    def _ai_text_reader_page(self) -> QWidget:
        page = QFrame()
        page.setStyleSheet(_glass_style(14))
        lay = QVBoxLayout(page)

        header = QHBoxLayout()
        header.addWidget(QLabel("<b>文本朗读</b>"))
        header.addStretch()
        import_btn = QPushButton("导入文本")
        import_btn.setStyleSheet(BTN_GLASS)
        import_btn.clicked.connect(self._import_text_for_reading)
        header.addWidget(import_btn)
        lay.addLayout(header)

        self._read_text_edit = QTextEdit()
        self._read_text_edit.setAcceptRichText(False)
        self._read_text_edit.setPlaceholderText("在这里粘贴或导入要朗读的文本…")
        self._read_text_edit.textChanged.connect(self._update_text_reader_state)
        lay.addWidget(self._read_text_edit, 1)

        self._read_text_hint = QLabel("导入或输入文本后会按当前音色朗读；语言不会限制朗读。")
        self._read_text_hint.setWordWrap(True)
        self._read_text_hint.setStyleSheet("color:#64748b;font-size:12px;")
        lay.addWidget(self._read_text_hint)

        bottom = QHBoxLayout()
        bottom.addStretch()
        self._stop_read_text_btn = QPushButton("停止")
        self._stop_read_text_btn.setStyleSheet(BTN_GLASS)
        self._stop_read_text_btn.clicked.connect(self._stop_text_reading)
        bottom.addWidget(self._stop_read_text_btn)
        self._read_text_btn = QPushButton("朗读")
        self._read_text_btn.setStyleSheet(BTN_PRIMARY)
        self._read_text_btn.clicked.connect(self._read_text_aloud)
        bottom.addWidget(self._read_text_btn)
        lay.addLayout(bottom)

        self._update_text_reader_state()
        return page

    def _import_text_for_reading(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "导入文本",
            self._project_root,
            BOOK_FILE_DIALOG_FILTER,
        )
        if not paths:
            return
        try:
            documents = read_book_files(paths)
            text = combine_documents(documents)
        except Exception as exc:
            QMessageBox.warning(self, "导入失败", f"文本导入失败：{exc}")
            return
        self._read_documents = documents
        self._read_text_edit.setPlainText(text)
        names = "、".join(doc.title for doc in documents[:3])
        more = len(documents) - min(3, len(documents))
        if more > 0:
            names += f" 等 {len(documents)} 本"
        self._show_toast(f"已导入：{names}")

    def _read_text_aloud(self) -> None:
        if not hasattr(self, "_read_text_edit"):
            return
        text = self._read_text_edit.toPlainText().strip()
        if not text:
            return
        if not self._text_reader_can_read(text):
            self._update_text_reader_state()
            return
        if not self.on_read_text:
            self._show_toast("朗读功能未连接桌宠")
            return
        title = self._current_read_text_title()
        try:
            self.on_read_text(text, title=title)
        except Exception as exc:
            self._show_toast(f"朗读失败：{exc}")
            return
        self._show_toast("已开始朗读文本")

    def _stop_text_reading(self) -> None:
        if not self.on_stop_read_text:
            return
        try:
            self.on_stop_read_text()
        except Exception as exc:
            self._show_toast(f"停止失败：{exc}")
            return
        self._show_toast("已请求停止朗读")

    def _current_read_text_title(self) -> str:
        docs = list(getattr(self, "_read_documents", []) or [])
        if not docs:
            return "文本"
        if len(docs) == 1:
            return docs[0].title
        return f"{docs[0].title} 等 {len(docs)} 本"

    def _update_text_reader_state(self) -> None:
        if not hasattr(self, "_read_text_hint") or not hasattr(self, "_read_text_btn"):
            return
        text = self._read_text_edit.toPlainText().strip() if hasattr(self, "_read_text_edit") else ""
        settings = normalize_tts_settings(self._tts_settings)
        if not text:
            self._set_text_reader_hint("导入或输入文本后会按当前音色朗读；语言不会限制朗读。", enabled=False)
            return
        if not settings.get("enabled"):
            self._set_text_reader_hint("语音已关闭，启用语音后才能朗读。", enabled=False)
            return
        detected = detect_text_language(text)
        self._set_text_reader_hint(
            f"准备按当前音色朗读。检测语言：{language_label(detected) if detected else '未识别'}。",
            enabled=True,
            ok=True,
        )

    def _set_text_reader_hint(self, message: str, enabled: bool, ok: bool | None = None) -> None:
        color = "#64748b"
        if ok is True:
            color = "#0f766e"
        elif ok is False:
            color = "#dc2626"
        self._read_text_hint.setText(message)
        self._read_text_hint.setStyleSheet(f"color:{color};font-size:12px;")
        self._read_text_btn.setEnabled(enabled)

    def _text_reader_can_read(self, text: str) -> bool:
        settings = normalize_tts_settings(self._tts_settings)
        return bool(text.strip() and settings.get("enabled"))

    def _current_response_language(self) -> str:
        settings = normalize_tts_settings(self._tts_settings)
        language = normalize_language_id(settings.get("response_language"))
        if language:
            return language
        language = language_from_edge_voice(settings.get("edge_voice"))
        if language:
            return language
        return self._fallback_response_language() or "zh-CN"

    def _current_voice_language(self) -> str:
        return self._current_response_language()

    def _fallback_response_language(self) -> str:
        return language_from_edge_voice(config.EDGE_TTS_VOICE)

    def _current_voice_pack(self) -> dict | None:
        if not getattr(self, "_voice_packs", None):
            return None
        current = self._current_voice_choice_key()
        return next((p for p in self._voice_packs if self._voice_choice_key(p) == current), None)

    def _ai_history_page(self) -> QWidget:
        page = QFrame()
        page.setStyleSheet(_glass_style(14))
        lay = QVBoxLayout(page)
        top = QHBoxLayout()
        top.addWidget(QLabel("<b>聊天记录</b>"))
        self._chat_search = QLineEdit()
        self._chat_search.setPlaceholderText("搜索聊天内容…")
        self._chat_search.textChanged.connect(self._filter_chat_view)
        top.addWidget(self._chat_search, 1)
        lay.addLayout(top)
        self._chat_view = QTextEdit()
        self._chat_view.setReadOnly(True)
        self._chat_empty = QLabel("暂无聊天记录")
        self._chat_empty.setStyleSheet("color:#94a3b8;")
        self._chat_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._chat_empty, 1)
        lay.addWidget(self._chat_view, 1)
        self._chat_view.hide()
        bottom = QHBoxLayout()
        self._ai_in = QLineEdit()
        self._ai_in.setPlaceholderText("输入消息…")
        send = QPushButton("发送")
        send.setStyleSheet(BTN_PRIMARY)
        send.clicked.connect(self._send_chat)
        bottom.addWidget(self._ai_in, 1)
        bottom.addWidget(send)
        lay.addLayout(bottom)
        return page

    def _ai_voice_settings_page(self) -> QWidget:
        page = QFrame()
        page.setStyleSheet(_glass_style(14))
        lay = QVBoxLayout(page)
        lay.addWidget(QLabel("<b>语音设置</b>"))
        self._tts_enabled_check = QCheckBox("启用语音")
        self._tts_enabled_check.stateChanged.connect(self._on_tts_controls_changed)
        lay.addWidget(self._tts_enabled_check)
        lay.addWidget(QLabel("合成模式"))
        self._tts_quality_combo = QComboBox()
        for preset in TTS_QUALITY_PRESETS:
            self._tts_quality_combo.addItem(str(preset["label"]), str(preset["id"]))
        self._tts_quality_combo.currentIndexChanged.connect(self._on_tts_controls_changed)
        lay.addWidget(self._tts_quality_combo)
        self._tts_openvoice_check = QCheckBox("启用 OpenVoice 声纹转换")
        self._tts_openvoice_check.stateChanged.connect(self._on_tts_controls_changed)
        lay.addWidget(self._tts_openvoice_check)
        lay.addWidget(QLabel("情感 / 风格"))
        self._tts_style_combo = QComboBox()
        for preset in TTS_STYLE_PRESETS:
            self._tts_style_combo.addItem(str(preset["label"]), str(preset["id"]))
        self._tts_style_combo.currentIndexChanged.connect(self._on_tts_controls_changed)
        lay.addWidget(self._tts_style_combo)
        lay.addWidget(QLabel("精细参数"))
        controls = QGridLayout()
        self._tts_edge_rate_slider, self._tts_edge_rate_value = self._add_tts_slider(
            controls, 0, "神经语速", -50, 50
        )
        self._tts_edge_pitch_slider, self._tts_edge_pitch_value = self._add_tts_slider(
            controls, 1, "神经音调", -50, 50
        )
        self._tts_edge_volume_slider, self._tts_edge_volume_value = self._add_tts_slider(
            controls, 2, "神经音量", -50, 50
        )
        self._tts_rate_slider, self._tts_rate_value = self._add_tts_slider(
            controls, 3, "离线语速", 80, 260
        )
        self._tts_volume_slider, self._tts_volume_value = self._add_tts_slider(
            controls, 4, "离线音量", 0, 100
        )
        lay.addLayout(controls)
        self._tts_detail = QLabel()
        self._tts_detail.setWordWrap(True)
        self._tts_detail.setStyleSheet("color:#64748b;font-size:12px;")
        lay.addWidget(self._tts_detail)
        lay.addStretch()
        return page

    def _switch_ai_tool(self, key: str) -> None:
        idx = {
            "voice_pack": 0,
            "language": 1,
            "text_reader": 2,
            "history": 3,
            "voice_settings": 4,
        }.get(key, 0)
        if hasattr(self, "_ai_tool_stack"):
            self._ai_tool_stack.setCurrentIndex(idx)
        for btn_key, btn in getattr(self, "_ai_tool_btns", {}).items():
            btn.setChecked(btn_key == key)

    @staticmethod
    def _set_combo_current_data(combo: QComboBox, data: str) -> None:
        target = str(data or "")
        for i in range(combo.count()):
            if str(combo.itemData(i) or "") == target:
                combo.setCurrentIndex(i)
                return
        combo.setCurrentIndex(0)

    def _on_reply_language_changed(self, *_args: Any) -> None:
        if getattr(self, "_tts_control_syncing", False) or not hasattr(self, "_reply_language_combo"):
            return
        language = normalize_language_id(self._reply_language_combo.currentData()) or "zh-CN"
        settings = dict(self._tts_settings)
        settings["response_language"] = language
        self._tts_settings = normalize_tts_settings(settings)
        self._render_reply_language_detail()
        self._render_tts_detail()
        self._render_current_voice_pack_detail()
        self._update_text_reader_state()
        if self.on_tts_settings_changed:
            self.on_tts_settings_changed(dict(self._tts_settings))
        self._show_toast(f"AI 回复语言: {language_label(language)}")

    def _apply_reply_language_control_from_settings(self) -> None:
        if not hasattr(self, "_reply_language_combo"):
            return
        self._tts_control_syncing = True
        self._set_combo_current_data(self._reply_language_combo, self._current_response_language())
        self._tts_control_syncing = False
        self._render_reply_language_detail()

    def _render_reply_language_detail(self) -> None:
        if not hasattr(self, "_reply_language_detail"):
            return
        settings = normalize_tts_settings(self._tts_settings)
        language = self._current_response_language()
        lines = [
            f"当前语言: {language_label(language)}",
            "语言只决定 AI 回复和朗读内容；语音包只决定说话风格。",
        ]
        if settings.get("voice_style_pack_enabled"):
            pack = voice_style_pack_by_id(settings.get("voice_style_pack"))
            style_settings = resolve_voice_style_pack_settings(settings.get("voice_style_pack"), language)
            lines.append(f"当前语音包: {pack.get('name', '风格音色')}")
            lines.append(f"合成音色: {style_settings.get('edge_voice')}")
        elif self._voice_pack_id:
            pack = self._current_voice_pack()
            if pack:
                lines.append(f"当前语音包: {pack.get('name') or pack.get('display_name') or self._voice_pack_id}")
        else:
            lines.append(f"合成音色: {settings.get('edge_voice') or config.EDGE_TTS_VOICE}")
        self._reply_language_detail.setText("\n".join(lines))

    def _add_tts_slider(
        self,
        layout: QGridLayout,
        row: int,
        label: str,
        minimum: int,
        maximum: int,
    ) -> tuple[QSlider, QLabel]:
        title = QLabel(label)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setSingleStep(1)
        slider.setPageStep(5)
        value_label = QLabel("")
        value_label.setMinimumWidth(58)
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        slider.valueChanged.connect(self._update_tts_slider_labels)
        slider.valueChanged.connect(self._on_tts_controls_changed)
        layout.addWidget(title, row, 0)
        layout.addWidget(slider, row, 1)
        layout.addWidget(value_label, row, 2)
        return slider, value_label

    def _set_tts_slider_values_from_settings(self) -> None:
        if not hasattr(self, "_tts_edge_rate_slider"):
            return
        settings = normalize_tts_settings(self._tts_settings)
        self._tts_edge_rate_slider.setValue(
            _parse_signed_int_setting(settings.get("edge_rate"), os.getenv("EDGE_TTS_RATE", "+8%"))
        )
        self._tts_edge_pitch_slider.setValue(
            _parse_signed_int_setting(settings.get("edge_pitch"), os.getenv("EDGE_TTS_PITCH", "+12Hz"))
        )
        self._tts_edge_volume_slider.setValue(
            _parse_signed_int_setting(settings.get("edge_volume"), os.getenv("EDGE_TTS_VOLUME", "+8%"))
        )
        self._tts_rate_slider.setValue(_parse_tts_rate_setting(settings.get("tts_rate")))
        self._tts_volume_slider.setValue(_parse_tts_volume_setting(settings.get("tts_volume")))
        self._update_tts_slider_labels()

    def _update_tts_slider_labels(self, *_args: Any) -> None:
        if not hasattr(self, "_tts_edge_rate_value"):
            return
        self._tts_edge_rate_value.setText(_signed_percent(self._tts_edge_rate_slider.value()))
        self._tts_edge_pitch_value.setText(_signed_hz(self._tts_edge_pitch_slider.value()))
        self._tts_edge_volume_value.setText(_signed_percent(self._tts_edge_volume_slider.value()))
        self._tts_rate_value.setText(str(self._tts_rate_slider.value()))
        self._tts_volume_value.setText(f"{self._tts_volume_slider.value()}%")

    def _apply_tts_controls_from_settings(self) -> None:
        self._tts_settings = normalize_tts_settings(self._tts_settings)
        self._apply_reply_language_control_from_settings()
        if not hasattr(self, "_tts_quality_combo"):
            return
        self._tts_control_syncing = True
        self._tts_enabled_check.setChecked(bool(self._tts_settings.get("enabled", True)))
        self._set_combo_current_data(self._tts_quality_combo, str(self._tts_settings.get("quality") or "basic"))
        if hasattr(self, "_tts_openvoice_check"):
            self._tts_openvoice_check.setChecked(bool(self._tts_settings.get("openvoice_enabled", False)))
        self._set_combo_current_data(self._tts_style_combo, str(self._tts_settings.get("emotion_style") or "auto"))
        self._set_tts_slider_values_from_settings()
        self._tts_control_syncing = False
        self._render_tts_detail()
        self._render_reply_language_detail()
        self._render_current_voice_pack_detail()
        self._update_text_reader_state()

    def _on_tts_controls_changed(self, *_args: Any) -> None:
        if self._tts_control_syncing or not hasattr(self, "_tts_quality_combo"):
            return

        quality_id = str(self._tts_quality_combo.currentData() or "basic")
        preset = next((p for p in TTS_QUALITY_PRESETS if str(p.get("id")) == quality_id), TTS_QUALITY_PRESETS[0])
        style_id = str(self._tts_style_combo.currentData() or "default")
        style = next((p for p in TTS_STYLE_PRESETS if str(p.get("id")) == style_id), TTS_STYLE_PRESETS[0])

        settings = dict(self._tts_settings)
        settings.update(
            {
                "quality": quality_id,
                "provider": str(preset.get("provider") or "auto"),
                "enabled": bool(self._tts_enabled_check.isChecked()) and bool(preset.get("enabled", True)),
                "emotion_style": style_id,
                "voice_profile": str(style.get("voice_profile") or "default"),
                "cute_style": bool(style.get("cute_style", False)),
            }
        )
        if hasattr(self, "_tts_edge_rate_slider"):
            settings.update(
                {
                    "edge_rate": _signed_percent(self._tts_edge_rate_slider.value()),
                    "edge_pitch": _signed_hz(self._tts_edge_pitch_slider.value()),
                    "edge_volume": _signed_percent(self._tts_edge_volume_slider.value()),
                    "tts_rate": str(self._tts_rate_slider.value()),
                    "tts_volume": f"{self._tts_volume_slider.value() / 100:.2f}",
                }
            )
        self._tts_settings = normalize_tts_settings(settings)
        self._render_tts_detail()
        self._render_reply_language_detail()
        self._render_current_voice_pack_detail()
        self._update_text_reader_state()
        if self.on_tts_settings_changed:
            self.on_tts_settings_changed(dict(self._tts_settings))

    def _render_tts_detail(self) -> None:
        if not hasattr(self, "_tts_detail"):
            return
        settings = normalize_tts_settings(self._tts_settings)
        mode = next(
            (str(p["label"]) for p in TTS_QUALITY_PRESETS if str(p["id"]) == settings.get("quality")),
            "基础语音合成",
        )
        style = next(
            (str(p["label"]) for p in TTS_STYLE_PRESETS if str(p["id"]) == settings.get("emotion_style")),
            "自动跟随情绪",
        )
        enabled = "已启用" if settings.get("enabled") else "已关闭"
        edge_rate = settings.get("edge_rate") or os.getenv("EDGE_TTS_RATE", "+8%")
        edge_pitch = settings.get("edge_pitch") or os.getenv("EDGE_TTS_PITCH", "+12Hz")
        edge_volume = settings.get("edge_volume") or os.getenv("EDGE_TTS_VOLUME", "+8%")
        tts_rate = settings.get("tts_rate") or os.getenv("TTS_RATE", "168")
        tts_volume = settings.get("tts_volume") or os.getenv("TTS_VOLUME", "0.95")
        openvoice_status = "已启用" if settings.get("openvoice_enabled") else "未启用"
        self._tts_detail.setText(
            f"{enabled} · {mode}\n"
            f"AI 回复语言: {language_label(self._current_response_language())}\n"
            f"情感 / 风格: {style}\n"
            f"OpenVoice 声纹转换: {openvoice_status}\n"
            f"神经语音: 语速 {edge_rate}，音调 {edge_pitch}，音量 {edge_volume}\n"
            f"离线回退: 语速 {tts_rate}，音量 {tts_volume}"
        )

    def _current_tts_voice_label(self) -> str:
        settings = normalize_tts_settings(self._tts_settings)
        if self._voice_pack_id:
            pack = self._current_voice_pack()
            if pack:
                return str(pack.get("name") or pack.get("display_name") or self._voice_pack_id)
        if settings.get("voice_style_pack_enabled") and not self._voice_pack_id:
            pack = voice_style_pack_by_id(settings.get("voice_style_pack"))
            style_settings = resolve_voice_style_pack_settings(
                settings.get("voice_style_pack"),
                self._current_response_language(),
            )
            return f"{pack.get('name', '风格音色')} / {style_settings.get('edge_voice')}"
        return next(
            (label for label, value in TTS_VOICE_PRESETS if value == settings.get("edge_voice")),
            str(settings.get("edge_voice") or "默认音色"),
        )

    def _refresh_voice_pack_list(self) -> None:
        if not hasattr(self, "_voice_pack_list"):
            return
        self._voice_packs = voice_style_pack_choices() + scan_voice_packs(self._project_root)
        self._voice_pack_list.clear()
        current = self._current_voice_choice_key()
        selected_row = 0
        found_current = False
        for i, pack in enumerate(self._voice_packs):
            item = QListWidgetItem(f"{pack.get('icon', '🎙️')}  {pack.get('name', pack.get('id', ''))}")
            item.setData(Qt.ItemDataRole.UserRole, self._voice_choice_key(pack))
            item.setToolTip(str(pack.get("description", "")))
            self._voice_pack_list.addItem(item)
            if self._voice_choice_key(pack) == current:
                selected_row = i
                found_current = True
        if found_current and self._voice_packs:
            selected_pack = self._voice_packs[selected_row]
            if str(selected_pack.get("kind") or "") != "voice_style_pack" and self._voice_pack_id:
                settings = dict(self._tts_settings)
                if settings.get("voice_style_pack_enabled"):
                    settings["voice_style_pack_enabled"] = False
                    settings["voice_pack_mode"] = "prefer"
                    settings["edge_voice"] = ""
                    self._tts_settings = normalize_tts_settings(settings)
                    if self.on_tts_settings_changed:
                        self.on_tts_settings_changed(dict(self._tts_settings))
        if not found_current and self._voice_packs:
            self._voice_pack_id = ""
            selected_row = 0
            selected_pack = self._voice_packs[selected_row]
            if str(selected_pack.get("kind") or "") == "voice_style_pack":
                settings = dict(self._tts_settings)
                settings["response_language"] = self._current_response_language()
                settings["voice_style_pack"] = normalize_voice_style_pack_id(selected_pack.get("id"))
                settings["voice_style_pack_enabled"] = True
                settings["edge_voice"] = ""
                settings["voice_pack_mode"] = "off"
                self._tts_settings = normalize_tts_settings(settings)
                if self.on_tts_settings_changed:
                    self.on_tts_settings_changed(dict(self._tts_settings))
        self._voice_pack_list.setCurrentRow(selected_row)
        if self._voice_packs:
            self._render_voice_pack_detail(self._voice_packs[selected_row])
        self._render_reply_language_detail()
        self._update_text_reader_state()

    @staticmethod
    def _voice_choice_key(pack: dict) -> str:
        if str(pack.get("kind") or "") == "voice_style_pack":
            return f"voice_style_pack:{normalize_voice_style_pack_id(pack.get('id'))}"
        if str(pack.get("kind") or "") == "edge_voice":
            return f"edge_voice:{str(pack.get('edge_voice') or '').strip()}"
        return f"voice_pack:{str(pack.get('id') or '').strip()}"

    def _current_voice_choice_key(self) -> str:
        settings = normalize_tts_settings(self._tts_settings)
        if self._voice_pack_id:
            return f"voice_pack:{(self._voice_pack_id or '').strip()}"
        if settings.get("voice_style_pack_enabled"):
            return f"voice_style_pack:{normalize_voice_style_pack_id(settings.get('voice_style_pack'))}"
        edge_voice = str(settings.get("edge_voice") or "").strip()
        if edge_voice:
            return f"edge_voice:{edge_voice}"
        return f"voice_pack:{(self._voice_pack_id or '').strip()}"

    def _render_current_voice_pack_detail(self) -> None:
        if not hasattr(self, "_voice_pack_list") or not self._voice_packs:
            return
        row = self._voice_pack_list.currentRow()
        if row < 0 or row >= len(self._voice_packs):
            row = 0
        self._render_voice_pack_detail(self._voice_packs[row])

    def _set_current_voice_choice_row(self) -> None:
        if not hasattr(self, "_voice_pack_list") or not self._voice_packs:
            return
        current = self._current_voice_choice_key()
        for i, pack in enumerate(self._voice_packs):
            if self._voice_choice_key(pack) == current:
                self._voice_pack_list.setCurrentRow(i)
                return

    def _pick_voice_pack_by_item(self, item: QListWidgetItem) -> None:
        choice_key = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
        pack = next((p for p in self._voice_packs if self._voice_choice_key(p) == choice_key), None)
        if pack is None:
            return
        self._select_voice_pack(pack, toast_prefix="已切换语音包")

    def _select_voice_pack(self, pack: dict, toast_prefix: str = "已切换语音包") -> None:
        if str(pack.get("kind") or "") == "voice_style_pack":
            style_pack_id = normalize_voice_style_pack_id(pack.get("id"))
            self._voice_pack_id = ""
            settings = dict(self._tts_settings)
            response_language = self._current_response_language()
            style_settings = resolve_voice_style_pack_settings(style_pack_id, response_language)
            settings.update(style_settings)
            settings["response_language"] = response_language
            settings["voice_style_pack"] = style_pack_id
            settings["voice_style_pack_enabled"] = True
            settings["edge_voice"] = ""
            settings["voice_pack_mode"] = "off"
            self._tts_settings = normalize_tts_settings(settings)
            if self.on_voice_pack_changed:
                self.on_voice_pack_changed({"id": "", "name": pack.get("name") or "风格音色"})
            if self.on_tts_settings_changed:
                self.on_tts_settings_changed(dict(self._tts_settings))
            self._apply_tts_controls_from_settings()
            self._set_current_voice_choice_row()
            self._render_voice_pack_detail(pack)
            self._update_text_reader_state()
            self._show_toast(f"{toast_prefix}: {pack.get('name') or pack.get('display_name') or '风格音色'}")
            return

        if str(pack.get("kind") or "") == "edge_voice":
            voice_id = str(pack.get("edge_voice") or "").strip()
            self._voice_pack_id = ""
            settings = dict(self._tts_settings)
            settings["voice_style_pack_enabled"] = False
            settings["edge_voice"] = voice_id
            edge_language = language_from_edge_voice(voice_id)
            if edge_language:
                settings["response_language"] = edge_language
            self._tts_settings = normalize_tts_settings(settings)
            if self.on_voice_pack_changed:
                self.on_voice_pack_changed({"id": "", "name": pack.get("name") or "默认"})
            if self.on_tts_settings_changed:
                self.on_tts_settings_changed(dict(self._tts_settings))
            self._render_tts_detail()
            self._render_reply_language_detail()
            self._set_current_voice_choice_row()
            self._render_voice_pack_detail(pack)
            self._update_text_reader_state()
            self._show_toast(f"{toast_prefix}: {pack.get('name') or pack.get('display_name') or '默认'}")
            return

        pack_id = str(pack.get("id", "")).strip()
        self._voice_pack_id = pack_id
        settings = dict(self._tts_settings)
        settings_changed = False
        if settings.get("voice_style_pack_enabled"):
            settings["voice_style_pack_enabled"] = False
            settings["voice_pack_mode"] = "prefer"
            settings_changed = True
        if str(self._tts_settings.get("edge_voice") or "").strip():
            settings["edge_voice"] = ""
            settings_changed = True
        backend_provider = str(pack.get("backend_provider") or "").strip().lower()
        if backend_provider == "gpt-sovits":
            settings["quality"] = "gpt_sovits"
            settings["provider"] = "gpt-sovits"
            settings["openvoice_enabled"] = False
            settings_changed = True
        if pack.get("is_custom") and backend_provider != "gpt-sovits" and openvoice_install_ready(self._project_root):
            if str(settings.get("quality") or "").strip().lower() != "openvoice":
                settings["quality"] = "openvoice"
                settings["provider"] = "edge"
                settings_changed = True
            if not settings.get("openvoice_enabled"):
                settings["openvoice_enabled"] = True
                settings_changed = True
        if settings_changed:
            self._tts_settings = normalize_tts_settings(settings)
            self._apply_tts_controls_from_settings()
            if self.on_tts_settings_changed:
                self.on_tts_settings_changed(dict(self._tts_settings))
        self._set_current_voice_choice_row()
        self._render_voice_pack_detail(pack)
        self._render_reply_language_detail()
        self._update_text_reader_state()
        if self.on_voice_pack_changed:
            self.on_voice_pack_changed(pack)
        self._show_toast(f"{toast_prefix}: {pack.get('name') or pack.get('display_name') or '默认'}")

    def _render_voice_pack_detail(self, pack: dict) -> None:
        if not hasattr(self, "_voice_pack_detail"):
            return
        desc = str(pack.get("description") or "")
        sample = str(pack.get("sample_text") or "")
        lines = [desc] if desc else []
        if str(pack.get("kind") or "") == "voice_style_pack":
            response_language = self._current_response_language()
            style_settings = resolve_voice_style_pack_settings(pack.get("id"), response_language)
            lines.append(f"当前语言: {language_label(response_language)}")
            lines.append(f"合成音色: {style_settings.get('edge_voice')}")
            lines.append(
                "风格参数: "
                f"语速 {style_settings.get('edge_rate')}，"
                f"音调 {style_settings.get('edge_pitch')}，"
                f"音量 {style_settings.get('edge_volume')}"
            )
        language = pack.get("language")
        if isinstance(language, dict) and language.get("label"):
            label = "样本语言" if str(pack.get("kind") or "") != "voice_style_pack" else "语言"
            lines.append(f"{label}: {language.get('label')}")
        if pack.get("is_custom"):
            sample_count = int(pack.get("sample_count") or 0)
            lines.append(f"本地样本: {sample_count} 个")
            converted_count = int(pack.get("converted_count") or 0)
            if converted_count:
                lines.append(f"MP4 转 MP3: {converted_count} 个")
            denoised_count = int(pack.get("denoised_count") or 0)
            lines.append(f"轻度降噪副本: {denoised_count} 个，原始音频已保留")
            features = pack.get("voice_features") if isinstance(pack.get("voice_features"), dict) else {}
            pitch = features.get("estimated_pitch_hz")
            if pitch:
                lines.append(f"样本音高估计: {pitch} Hz")
            if pack.get("fit_source"):
                confidence = str(pack.get("fit_confidence") or "low")
                lines.append(f"拟合方式: 样本特征微调（{confidence}）")
            if str(pack.get("backend_provider") or "").strip().lower() == "gpt-sovits":
                lines.append("克隆后端: GPT-SoVITS（需本机 api_v2.py 服务运行）")
            if str(pack.get("backend_provider") or "").strip().lower() != "gpt-sovits" and openvoice_install_ready(self._project_root):
                lines.append("OpenVoice: 已就绪，选择此包后自动启用声纹增强")
        lines.append(f"当前音色: {self._current_tts_voice_label()}")
        if sample:
            lines.append(f"试听: {sample}")
        self._voice_pack_detail.setText("\n".join(lines))

    def _pick_chat(self, idx: int) -> None:
        self._ai_i = idx
        self._chat_empty.hide()
        self._chat_view.show()
        self._render_chat_view()

    def _render_chat_view(self) -> None:
        if self._ai_i < 0 or self._ai_i >= len(self._chats):
            return
        query = (self._chat_search.text() if hasattr(self, "_chat_search") else "").strip().lower()
        self._chat_view.clear()
        for role, txt in self._chats[self._ai_i]["msgs"]:
            if query and query not in txt.lower():
                continue
            align = "right" if role == "user" else "left"
            color = "#3b82f6" if role == "user" else "#64748b"
            self._chat_view.append(f'<p style="text-align:{align};color:{color};">{txt}</p>')

    def _filter_chat_view(self) -> None:
        if self._ai_i >= 0:
            self._render_chat_view()

    def append_chat_message(self, character_name: str, role: str, text: str) -> None:
        idx = next((i for i, c in enumerate(self._chats) if c["name"] == character_name), -1)
        if idx < 0:
            self._chats.append({"name": character_name, "color": "#ec4899", "msgs": []})
            idx = len(self._chats) - 1
        self._chats[idx]["msgs"].append((role, text))
        self._chat_store.save(character_name, self._chats[idx]["msgs"])
        if self._ai_i == idx and hasattr(self, "_chat_view"):
            self._render_chat_view()

    def _send_chat(self) -> None:
        t = self._ai_in.text().strip()
        if not t or self._ai_i < 0:
            return
        name = self._chats[self._ai_i]["name"]
        self.append_chat_message(name, "user", t)
        self.append_chat_message(name, "ai", f"收到：{t}")
        self._ai_in.clear()

    def _page_placeholder(self, title: str) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel(f"<h2>{title}</h2>"))
        ph = QLabel("功能开发中...")
        ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph.setStyleSheet("color:#94a3b8;font-size:18px;")
        lay.addWidget(ph, 1)
        return w

    def run(self) -> None:
        from PySide6.QtCore import QEventLoop

        self.show()
        loop = QEventLoop()
        self.destroyed.connect(loop.quit)
        loop.exec()
