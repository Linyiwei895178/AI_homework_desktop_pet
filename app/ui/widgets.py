"""
PySide6 UI 鎺т欢锛氬彸閿彍鍗曘€佸姬褰㈠姩浣滆彍鍗曘€佹皵娉°€佽緭鍏ユ銆佹帶鍒跺彴绛夈€?
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
    languages_match,
    normalize_language_id,
)
from utils.config import config
from utils.logger import get_logger

# ---------------------------------------------------------------------------
# 鏍峰紡甯搁噺
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
    "happy": "寮€蹇?,
    "sad": "浼ゅ績",
    "hungry": "鍚冮キ",
    "angry": "鐢熸皵",
    "idle": "寰呮満",
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
    "voice_profile": "default",
    "emotion_style": "auto",
    "cute_style": True,
    "voice_pack_mode": "prefer",
    "edge_rate": "",
    "edge_pitch": "",
    "edge_volume": "",
    "tts_rate": "",
    "tts_volume": "",
}

DEFAULT_PET_PERSONALIZATION_SETTINGS: dict[str, dict[str, Any]] = {
    "speech_style": {
        "tone": "鏈嬪弸鎰?,
        "nickname": "鐢ㄦ埛",
        "catchphrase": "鎴戝湪鍛?,
        "use_emoji": True,
    },
    "interaction_frequency": {
        "proactive_level": 45,
        "quiet_when_busy": True,
        "quiet_hours": "23:00-08:00",
    },
    "appearance_actions": {
        "theme_color": "妯辫姳绮?,
        "idle_action": "杞昏交鏅冨姩",
        "transparency": 92,
    },
    "companion_mode": {
        "mode": "瀛︿範闄即",
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
        "style": "娓╂煍鎻愰啋",
    },
    "memory_relationship": {
        "relationship": "鏈嬪弸",
        "remember_preferences": True,
        "remember_projects": True,
        "user_title": "鐢ㄦ埛",
    },
    "voice_expression": {
        "voice_enabled": True,
        "voice_style": "鑷劧鍙埍",
        "speech_rate": 55,
        "bubble_density": 50,
    },
    "desktop_behavior": {
        "activity_range": "灞忓箷杈圭紭鍜岀┖鐧藉",
        "avoid_windows": True,
        "follow_mouse": False,
        "multi_screen": True,
    },
    "boundaries": {
        "no_disturb_when_fullscreen": True,
        "safe_topics": "涓嶈繃搴︿翰瀵嗐€佷笉璁ㄨ闅愮",
        "comfort_level": "杞诲害瀹夋叞",
        "allow_close_expression": False,
    },
}

PET_PERSONALIZATION_SECTIONS: tuple[dict[str, Any], ...] = (
    {
        "key": "speech_style",
        "icon": "馃挰",
        "title": "璇磋瘽椋庢牸",
        "summary": "绉板懠銆佸彛澶寸銆佽姘斿拰琛ㄦ儏浣跨敤銆?,
        "fields": (
            {"key": "tone", "label": "璇皵妯℃澘", "type": "combo", "options": ("鏈嬪弸鎰?, "娓╂煍鎾掑▏", "鐢靛瓙绠″", "姣掕垖鍚愭Ы", "鎭嬩汉闄即")},
            {"key": "nickname", "label": "鎬庝箞绉板懠浣?, "type": "line", "placeholder": "鐢ㄦ埛 / 涓讳汉 / 鍚屽"},
            {"key": "catchphrase", "label": "鍙ｅご绂?, "type": "line", "placeholder": "鎴戝湪鍛?},
            {"key": "use_emoji", "label": "琛ㄦ儏绗﹀彿", "type": "check", "text": "鍏佽浣跨敤"},
        ),
    },
    {
        "key": "interaction_frequency",
        "icon": "鈴憋笍",
        "title": "浜掑姩棰戠巼",
        "summary": "涓诲姩鎵撴嫑鍛笺€佸畨闈欐椂娈靛拰蹇欑鏃剁殑鎵撴壈绋嬪害銆?,
        "fields": (
            {"key": "proactive_level", "label": "涓诲姩绋嬪害", "type": "slider", "min": 0, "max": 100, "suffix": "%"},
            {"key": "quiet_when_busy", "label": "蹇欑璇嗗埆", "type": "check", "text": "妫€娴嬪埌蹇欑鏃跺皯鎵撴壈"},
            {"key": "quiet_hours", "label": "瀹夐潤鏃舵", "type": "combo", "options": ("鏃?, "22:00-07:00", "23:00-08:00", "00:00-09:00")},
        ),
    },
    {
        "key": "appearance_actions",
        "icon": "馃巰",
        "title": "澶栬涓庡姩浣?,
        "summary": "棰滆壊涓婚銆侀€忔槑搴︺€佸緟鏈哄姩浣滃拰琚偣鍑绘椂鐨勮〃鐜般€?,
        "fields": (
            {"key": "theme_color", "label": "棰滆壊涓婚", "type": "combo", "options": ("妯辫姳绮?, "钖勮嵎缁?, "澶╃┖钃?, "鏆栭槼姗?, "鏋佺畝鐏?)},
            {"key": "idle_action", "label": "寰呮満鍔ㄤ綔", "type": "combo", "options": ("杞昏交鏅冨姩", "鍘熷湴鐪ㄧ溂", "灏忔璧板姩", "璐磋竟浼戞伅", "瀹夐潤绔欑珛")},
            {"key": "transparency", "label": "涓嶉€忔槑搴?, "type": "slider", "min": 30, "max": 100, "suffix": "%"},
        ),
    },
    {
        "key": "companion_mode",
        "icon": "馃Л",
        "title": "闄即妯″紡",
        "summary": "宸ヤ綔銆佸涔犮€佹懜楸笺€佺潯鍓嶅拰娓告垙闄即鐨勮涓烘ā寮忋€?,
        "fields": (
            {"key": "mode", "label": "榛樿妯″紡", "type": "combo", "options": ("宸ヤ綔闄即", "瀛︿範闄即", "鎽搁奔鎼瓙", "鐫″墠闄即", "娓告垙闄即")},
            {"key": "auto_switch", "label": "妯″紡鍒囨崲", "type": "check", "text": "鍏佽鑷姩鍒囨崲"},
            {"key": "focus_silence", "label": "涓撴敞淇濇姢", "type": "check", "text": "涓撴敞鏃跺噺灏戞皵娉?},
        ),
    },
    {
        "key": "emotion_system",
        "icon": "馃挆",
        "title": "鎯呯华绯荤粺",
        "summary": "蹇冩儏銆佺簿鍔涖€佷翰瀵嗗害鐨勫搷搴斿己搴︺€?,
        "fields": (
            {"key": "enable_emotion", "label": "鎯呯华鐘舵€?, "type": "check", "text": "鍚敤"},
            {"key": "mood_sensitivity", "label": "蹇冩儏鏁忔劅搴?, "type": "slider", "min": 0, "max": 100, "suffix": "%"},
            {"key": "intimacy_growth", "label": "浜插瘑搴︽垚闀?, "type": "slider", "min": 0, "max": 100, "suffix": "%"},
        ),
    },
    {
        "key": "reminders",
        "icon": "馃敂",
        "title": "鎻愰啋鍋忓ソ",
        "summary": "鍠濇按銆佷紤鎭€佺暘鑼勯挓銆佸悆楗拰鐫¤鎻愰啋銆?,
        "fields": (
            {"key": "water", "label": "鍠濇按", "type": "check", "text": "寮€鍚?},
            {"key": "rest", "label": "浼戞伅", "type": "check", "text": "寮€鍚?},
            {"key": "pomodoro", "label": "鐣寗閽?, "type": "check", "text": "寮€鍚?},
            {"key": "meal", "label": "鍚冮キ", "type": "check", "text": "寮€鍚?},
            {"key": "sleep", "label": "鐫¤", "type": "check", "text": "寮€鍚?},
            {"key": "style", "label": "鎻愰啋璇皵", "type": "combo", "options": ("娓╂煍鎻愰啋", "涓ユ牸鐫ｄ績", "鎼炵瑧鍚愭Ы", "瀹夐潤寮圭獥")},
        ),
    },
    {
        "key": "memory_relationship",
        "icon": "馃",
        "title": "璁板繂涓庡叧绯?,
        "summary": "鍏崇郴瀹氫綅銆佺О鍛笺€佸亸濂藉拰椤圭洰璁板繂銆?,
        "fields": (
            {"key": "relationship", "label": "鍏崇郴瀹氫綅", "type": "combo", "options": ("鏈嬪弸", "鎼。", "绠″", "濮愬鎰?, "濡瑰鎰?, "鎹熷弸")},
            {"key": "user_title", "label": "鐢ㄦ埛绉板懠", "type": "line", "placeholder": "鐢ㄦ埛"},
            {"key": "remember_preferences", "label": "鍋忓ソ璁板繂", "type": "check", "text": "璁颁綇"},
            {"key": "remember_projects", "label": "椤圭洰璁板繂", "type": "check", "text": "璁颁綇"},
        ),
    },
    {
        "key": "voice_expression",
        "icon": "馃帣锔?,
        "title": "澹伴煶涓庤〃杈?,
        "summary": "璇煶寮€鍏炽€侀煶鑹查鏍笺€佽閫熷拰姘旀场瀵嗗害銆?,
        "fields": (
            {"key": "voice_enabled", "label": "璇煶鎾姤", "type": "check", "text": "寮€鍚?},
            {"key": "voice_style", "label": "澹伴煶椋庢牸", "type": "combo", "options": ("鑷劧鍙埍", "娓╂煍瀹夐潤", "鍏冩皵娲绘臣", "鍐烽潤鍙潬", "杞诲井姣掕垖")},
            {"key": "speech_rate", "label": "璇€?, "type": "slider", "min": 0, "max": 100, "suffix": "%"},
            {"key": "bubble_density", "label": "姘旀场瀵嗗害", "type": "slider", "min": 0, "max": 100, "suffix": "%"},
        ),
    },
    {
        "key": "desktop_behavior",
        "icon": "馃枼锔?,
        "title": "妗岄潰琛屼负",
        "summary": "娲诲姩鑼冨洿銆侀伩璁╃獥鍙ｃ€佽窡闅忛紶鏍囧拰澶氬睆绉诲姩銆?,
        "fields": (
            {"key": "activity_range", "label": "娲诲姩鑼冨洿", "type": "combo", "options": ("灞忓箷杈圭紭鍜岀┖鐧藉", "鍙湪褰撳墠灞忓箷", "鍥哄畾鍦ㄨ钀?, "璺熼殢娲昏穬绐楀彛")},
            {"key": "avoid_windows", "label": "绐楀彛閬胯", "type": "check", "text": "寮€鍚?},
            {"key": "follow_mouse", "label": "璺熼殢榧犳爣", "type": "check", "text": "寮€鍚?},
            {"key": "multi_screen", "label": "澶氬睆绉诲姩", "type": "check", "text": "鍏佽"},
        ),
    },
    {
        "key": "boundaries",
        "icon": "馃洝锔?,
        "title": "杈圭晫璁剧疆",
        "summary": "涓嶆墦鎵般€佽瘽棰樿竟鐣屻€佸畨鎱板昂搴﹀拰浜插瘑琛ㄨ揪銆?,
        "fields": (
            {"key": "no_disturb_when_fullscreen", "label": "鍏ㄥ睆涓嶆墦鎵?, "type": "check", "text": "寮€鍚?},
            {"key": "safe_topics", "label": "璇濋杈圭晫", "type": "line", "placeholder": "涓嶈繃搴︿翰瀵嗐€佷笉璁ㄨ闅愮"},
            {"key": "comfort_level", "label": "瀹夋叞灏哄害", "type": "combo", "options": ("鍙粰寤鸿", "杞诲害瀹夋叞", "鏄庢樉鍏冲績", "楂樹翰瀵嗛櫔浼?)},
            {"key": "allow_close_expression", "label": "浜插瘑琛ㄨ揪", "type": "check", "text": "鍏佽鏇翠翰杩戠殑琛ㄨ揪"},
        ),
    },
)

TTS_QUALITY_PRESETS: tuple[dict[str, Any], ...] = (
    {
        "id": "basic",
        "label": "鍩虹璇煶鍚堟垚",
        "provider": "auto",
        "enabled": True,
    },
    {
        "id": "neural",
        "label": "楂樻嫙鐪熺缁忚闊?,
        "provider": "edge",
        "enabled": True,
    },
    {
        "id": "offline",
        "label": "绂荤嚎璇煶",
        "provider": "pyttsx3",
        "enabled": True,
    },
    {
        "id": "off",
        "label": "鍏抽棴璇煶",
        "provider": "off",
        "enabled": False,
    },
)

TTS_VOICE_PRESETS: tuple[tuple[str, str], ...] = (
    ("璺熼殢璇煶鍖?/ 榛樿", ""),
    ("涓枃濂冲０ Xiaoyi", "zh-CN-XiaoyiNeural"),
    ("涓枃濂冲０ Xiaoxiao", "zh-CN-XiaoxiaoNeural"),
    ("涓枃濂冲０ Xiaomo", "zh-CN-XiaomoNeural"),
    ("涓枃鐢峰０ Yunxi", "zh-CN-YunxiNeural"),
    ("绮よ濂冲０ HiuGaai", "zh-HK-HiuGaaiNeural"),
    ("鑻辫濂冲０ Jenny锛堢編闊筹級", "en-US-JennyNeural"),
    ("鑻辫鐢峰０ Guy锛堢編闊筹級", "en-US-GuyNeural"),
    ("鑻辫濂冲０ Sonia锛堣嫳闊筹級", "en-GB-SoniaNeural"),
    ("鑻辫鐢峰０ Ryan锛堣嫳闊筹級", "en-GB-RyanNeural"),
    ("娉曡濂冲０ Denise", "fr-FR-DeniseNeural"),
    ("娉曡鐢峰０ Henri", "fr-FR-HenriNeural"),
    ("寰疯濂冲０ Katja", "de-DE-KatjaNeural"),
    ("寰疯鐢峰０ Conrad", "de-DE-ConradNeural"),
    ("瑗跨彮鐗欒濂冲０ Elvira", "es-ES-ElviraNeural"),
    ("瑗跨彮鐗欒鐢峰０ Alvaro", "es-ES-AlvaroNeural"),
    ("澧ㄨタ鍝ヨタ璇コ澹?Dalia", "es-MX-DaliaNeural"),
    ("鎰忓ぇ鍒╄濂冲０ Elsa", "it-IT-ElsaNeural"),
    ("钁¤悇鐗欒濂冲０ Francisca", "pt-BR-FranciscaNeural"),
    ("淇勮濂冲０ Svetlana", "ru-RU-SvetlanaNeural"),
    ("鑽峰叞璇コ澹?Colette", "nl-NL-ColetteNeural"),
    ("鍗板湴璇コ澹?Swara", "hi-IN-SwaraNeural"),
    ("闃挎媺浼濂冲０ Salma", "ar-EG-SalmaNeural"),
    ("鏃ユ枃濂冲０ Nanami", "ja-JP-NanamiNeural"),
    ("闊╂枃濂冲０ SunHi", "ko-KR-SunHiNeural"),
)

TTS_STYLE_PRESETS: tuple[dict[str, Any], ...] = (
    {"id": "auto", "label": "鑷姩璺熼殢鎯呯华", "voice_profile": "default", "cute_style": True},
    {"id": "neutral", "label": "鑷劧", "voice_profile": "default", "cute_style": False},
    {"id": "cheerful", "label": "寮€蹇冩椿娉?, "voice_profile": "cute", "cute_style": True},
    {"id": "comfort", "label": "娓╂煍瀹夋姎", "voice_profile": "calm", "cute_style": False},
    {"id": "serious", "label": "涓ヨ們涓撲笟", "voice_profile": "default", "cute_style": False},
    {"id": "story", "label": "鏁呬簨鏃佺櫧", "voice_profile": "default", "cute_style": False},
    {"id": "news", "label": "鏂伴椈鎾姤", "voice_profile": "default", "cute_style": False},
)


def normalize_tts_settings(settings: dict[str, Any] | None) -> dict[str, Any]:
    data = dict(DEFAULT_TTS_UI_SETTINGS)
    if isinstance(settings, dict):
        for key in data:
            if key in settings:
                data[key] = settings[key]

    data["enabled"] = bool(data.get("enabled", True))
    data["provider"] = str(data.get("provider") or "auto").strip().lower().replace("_", "-")
    if data["provider"] in {"disabled", "none", "false"}:
        data["provider"] = "off"
    data["quality"] = str(data.get("quality") or "").strip().lower()
    if data["provider"] == "off":
        data["quality"] = "off"
        data["enabled"] = False
    if data["quality"] not in {str(p["id"]) for p in TTS_QUALITY_PRESETS}:
        if data["provider"] in {"edge", "edge-tts", "neural", "edge-neural", "high-realism"}:
            data["quality"] = "neural"
        elif data["provider"] in {"pyttsx3", "offline", "local"}:
            data["quality"] = "offline"
        else:
            data["quality"] = "basic"
    data["edge_voice"] = str(data.get("edge_voice") or "").strip()
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
    data["voice_pack_mode"] = str(data.get("voice_pack_mode") or "prefer").strip().lower() or "prefer"
    for key in ("edge_rate", "edge_pitch", "edge_volume", "tts_rate", "tts_volume"):
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
    """妗屽疇绐楀彛缂╁皬鏃讹紝overlay 鎺т欢鎸夋瘮渚嬬缉鏀俱€?""

    _ui_scale: float = 1.0

    def apply_ui_scale(self, scale: float) -> None:
        self._ui_scale = max(0.35, min(1.25, scale))


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
# 鍙抽敭鑿滃崟 & 浜岀骇鑿滃崟锛堣嚜缁?overlay锛?
# ---------------------------------------------------------------------------


class RightClickMenu(QFrame, ScalableOverlay):
    ITEMS = (
        "鐘舵€佹爮",
        "AI瀵硅瘽",
        "璁剧疆闈㈡澘",
        "鍔ㄤ綔灞曠ず",
        "寰呮満",
        "缃《璁剧疆",
        "鎮仠娣″嚭",
        "閫€鍑?,
        "鍏抽棴",
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
        self.setMouseTracking(True)
        self.hide()

    def apply_ui_scale(self, scale: float) -> None:
        super().apply_ui_scale(scale)
        self.WIDTH = _scaled_int(self._BASE_WIDTH, self._ui_scale, 120)
        self.ITEM_HEIGHT = _scaled_int(self._BASE_ITEM_HEIGHT, self._ui_scale, 28)
        self.PADDING = _scaled_int(self._BASE_PADDING, self._ui_scale, 4)
        self._font = _app_font(_scaled_int(16, self._ui_scale, 11))
        radius = _scaled_int(16, self._ui_scale, 10)
        self.setStyleSheet(_glass_style(radius))

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
        bg.addRoundedRect(QRectF(0, 0, self.width(), self.height()), 16, 16)
        p.fillPath(bg, QColor(255, 255, 255, 248))
        p.setPen(QPen(QColor(226, 232, 240, 220), 1))
        p.drawPath(bg)
        for i, label in enumerate(self.ITEMS):
            item_r = QRect(0, self.PADDING + i * self.ITEM_HEIGHT, self.WIDTH, self.ITEM_HEIGHT)
            if i == self.hover_index:
                path = QPainterPath()
                path.addRoundedRect(QRectF(item_r.adjusted(4, 2, -4, -2)), 8, 8)
                p.fillPath(path, QColor(220, 235, 255, 230))
            p.setPen(QColor(35, 35, 45))
            p.drawText(item_r.adjusted(16, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, label)
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
        items: tuple[str, ...] = ("寮€濮嬬疆椤?, "鍏抽棴缃《"),
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
        self.setMouseTracking(True)
        self.hide()

    def apply_ui_scale(self, scale: float) -> None:
        super().apply_ui_scale(scale)
        self.WIDTH = _scaled_int(self._BASE_WIDTH, self._ui_scale, 100)
        self.ITEM_HEIGHT = _scaled_int(self._BASE_ITEM_HEIGHT, self._ui_scale, 26)
        self.PADDING = _scaled_int(self._BASE_PADDING, self._ui_scale, 4)
        self._font = _app_font(_scaled_int(15, self._ui_scale, 10))
        self.setStyleSheet(_glass_style(_scaled_int(12, self._ui_scale, 8)))

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
        bg.addRoundedRect(QRectF(0, 0, self.width(), self.height()), 12, 12)
        p.fillPath(bg, QColor(255, 255, 255, 248))
        p.setPen(QPen(QColor(226, 232, 240, 220), 1))
        p.drawPath(bg)
        for i, label in enumerate(self.ITEMS):
            item_r = QRect(0, self.PADDING + i * self.ITEM_HEIGHT, self.WIDTH, self.ITEM_HEIGHT)
            color = QColor(150, 150, 160) if i == self.active_index else QColor(35, 35, 45)
            if i == self.hover_index and i != self.active_index:
                path = QPainterPath()
                path.addRoundedRect(QRectF(item_r.adjusted(4, 2, -4, -2)), 8, 8)
                p.fillPath(path, QColor(220, 235, 255, 230))
            p.setPen(color)
            p.drawText(item_r.adjusted(12, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, label)
        p.end()


# ---------------------------------------------------------------------------
# 寮у舰鍔ㄤ綔鑿滃崟
# ---------------------------------------------------------------------------


def _ease_out_back(t: float) -> float:
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    c1, c3 = 1.70158, 2.70158
    return 1.0 + c3 * (t - 1.0) ** 3 + c1 * (t - 1.0) ** 2


class ArcMotionMenu(QWidget, ScalableOverlay):
    _BASE_RADIUS = 120
    _BASE_BUTTON_SIZE = 48
    RADIUS = 120
    BUTTON_SIZE = 48
    HOVER_SCALE = 1.1
    ANIM_DURATION = 0.42
    STAGGER = 0.055

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
        self._font = _app_font(_scaled_int(12, self._ui_scale, 9))

    def show_menu(self, center_x: int, center_y: int, items: list[dict[str, Any]]) -> None:
        self.center_x, self.center_y = center_x, center_y
        self.items = list(items)
        self.visible = True
        self.hover_index = -1
        self._elapsed = 0.0
        pad = self.RADIUS + self.BUTTON_SIZE + 20
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

    def _angle_deg(self, index: int) -> float:
        n = len(self.items)
        if n <= 1:
            return 0.0
        return -90.0 + 180.0 * index / (n - 1)

    def _btn_center(self, index: int) -> tuple[int, int]:
        deg = math.radians(self._angle_deg(index))
        x = self.center_x + int(self.RADIUS * math.sin(deg))
        y = self.center_y - int(self.RADIUS * math.cos(deg))
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
        pad = self.RADIUS + self.BUTTON_SIZE
        return QRect(min(xs) - pad, min(ys) - pad, max(xs) - min(xs) + pad * 2, max(ys) - min(ys) + pad * 2)

    def hover_at(self, mouse_pos: tuple[int, int] | None = None) -> None:
        if not self.visible:
            self.hover_index = -1
            return
        lp = self.mapFromGlobal(QPoint(*mouse_pos)) if mouse_pos else None
        self.hover_index = -1
        if lp:
            for i in range(len(self.items)):
                if self._pop_scale(i) > 0.2 and self.button_rect(i).contains(lp):
                    self.hover_index = i
                    break
        QWidget.update(self)

    def update(self, mouse_pos: tuple[int, int] | None = None) -> None:
        self.hover_at(mouse_pos)

    def handle_click(self, mouse_pos: tuple[int, int]) -> Optional[dict[str, Any]]:
        lp = self.mapFromGlobal(QPoint(*mouse_pos))
        self.hover_index = -1
        for i in range(len(self.items)):
            if self.button_rect(i).contains(lp):
                self._selected = self.items[i]
                return self._selected
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
                label = label[:4] + "鈥?
            p.setPen(QColor(30, 30, 40))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, label)
        p.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        for i in range(len(self.items)):
            if self.button_rect(i).contains(event.pos()):
                self._selected = self.items[i]
                self.picked.emit(self._selected)
                return
        self.hide()


RadialMenu = ArcMotionMenu


# ---------------------------------------------------------------------------
# 姘旀场 & 杈撳叆妗?
# ---------------------------------------------------------------------------


class InfoBubble(QFrame, ScalableOverlay):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("glass")
        self.setAutoFillBackground(True)
        self.setStyleSheet(_glass_style(14))
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.visible = False
        self.mood, self.affection, self.energy = 85, 72, 90
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(12, 12, 12, 12)
        self._lbl = QLabel()
        self._lbl.setFont(_app_font(15))
        self._lay.addWidget(self._lbl)
        self.hide()

    def apply_ui_scale(self, scale: float) -> None:
        super().apply_ui_scale(scale)
        m = _scaled_int(12, self._ui_scale, 6)
        self._lay.setContentsMargins(m, m, m, m)
        self._lbl.setFont(_app_font(_scaled_int(15, self._ui_scale, 10)))
        self.setStyleSheet(_glass_style(_scaled_int(14, self._ui_scale, 8)))

    @property
    def rect(self) -> QRect:
        return self.geometry()

    def show(self, x: int, y: int) -> None:
        self._lbl.setText(
            f"蹇冩儏鉂わ笍{self.mood}\n濂芥劅搴︹瓙{self.affection}\n鑳介噺鈿self.energy}"
        )
        self.adjustSize()
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
        self.setFixedWidth(self.WIDTH)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.visible = False
        self.text = ""
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(14, 14, 14, 14)
        self._lbl = QLabel()
        self._lbl.setFont(_app_font(15))
        self._lbl.setWordWrap(True)
        self._lay.addWidget(self._lbl)
        self.hide()

    def apply_ui_scale(self, scale: float) -> None:
        super().apply_ui_scale(scale)
        self.WIDTH = _scaled_int(self._BASE_WIDTH, self._ui_scale, 160)
        self.RADIUS = _scaled_int(self._BASE_RADIUS, self._ui_scale, 12)
        self.setFixedWidth(self.WIDTH)
        m = _scaled_int(14, self._ui_scale, 8)
        self._lay.setContentsMargins(m, m, m, m)
        self._lbl.setFont(_app_font(_scaled_int(15, self._ui_scale, 10)))
        self.setStyleSheet(_glass_style(self.RADIUS))

    @property
    def rect(self) -> QRect:
        return self.geometry()

    def set_text(self, text: str) -> None:
        self.text = text
        self._lbl.setText(text)

    def show(self, x: int, y: int, text: str) -> None:
        self.set_text(text)
        self.adjustSize()
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


def _voice_error_summary(message: str) -> str:
    if any(keyword in message for keyword in ("SpeechRecognition", "speech_recognition", "PyAudio", "pyaudio")):
        return "璇煶杈撳叆缂哄皯渚濊禆锛岃瀹夎 SpeechRecognition 鍜?PyAudio 鍚庨噸鍚€?
    if any(keyword in message for keyword in ("楹﹀厠椋?, "Microphone", "Input Device", "杈撳叆璁惧")):
        return "鏃犳硶鎵撳紑楹﹀厠椋庯紝璇锋鏌ョ郴缁熸潈闄愬拰榛樿杈撳叆璁惧銆?
    if "鍦ㄧ嚎璇煶璇嗗埆涓嶅彲鐢? in message:
        return "鍦ㄧ嚎璇煶璇嗗埆涓嶅彲鐢紝璇锋鏌ョ綉缁滄垨绋嶅悗鍐嶈瘯銆?
    if "娌℃湁璇嗗埆" in message or "娌℃湁鍚竻" in message:
        return "娌℃湁璇嗗埆鍒拌闊筹紝璇峰啀璇曚竴娆°€?
    return message or "璇煶璇嗗埆澶辫触锛岃鍐嶈瘯涓€娆°€?


def _recognize_with_speech_recognition(timeout_sec: float, phrase_time_limit: float) -> str:
    try:
        import speech_recognition as sr  # type: ignore
    except ImportError as exc:
        missing = getattr(exc, "name", "") or str(exc)
        if missing and missing != "speech_recognition":
            raise RuntimeError(f"SpeechRecognition 渚濊禆缂哄け锛歿missing}銆傝閲嶆柊瀹夎璇煶杈撳叆渚濊禆銆?) from exc
        raise RuntimeError("鏈畨瑁?SpeechRecognition锛屾棤娉曞惎鐢ㄨ闊宠緭鍏ャ€?) from exc

    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.4)
            audio = recognizer.listen(
                source,
                timeout=timeout_sec,
                phrase_time_limit=phrase_time_limit,
            )
    except AttributeError as exc:
        if "PyAudio" in str(exc):
            raise RuntimeError("鏈畨瑁?PyAudio锛屾棤娉曡鍙栭害鍏嬮闊抽銆?) from exc
        raise
    except OSError as exc:
        raise RuntimeError(f"鏃犳硶鎵撳紑楹﹀厠椋庤澶囷細{exc}") from exc
    try:
        text = recognizer.recognize_google(audio, language="zh-CN")
    except sr.UnknownValueError as exc:
        raise RuntimeError("娌℃湁鍚竻锛岃鍐嶈瘯涓€娆°€?) from exc
    except sr.RequestError as exc:
        raise RuntimeError(f"鍦ㄧ嚎璇煶璇嗗埆涓嶅彲鐢細{exc}") from exc
    cleaned = _clean_voice_text(text)
    if not cleaned:
        raise RuntimeError("娌℃湁璇嗗埆鍒版枃瀛楋紝璇峰啀璇曚竴娆°€?)
    return cleaned


def _recognize_with_windows_sapi(timeout_sec: float) -> str:
    if sys.platform != "win32":
        raise RuntimeError("褰撳墠绯荤粺娌℃湁鍙敤鐨勬湰鍦拌闊宠瘑鍒悗绔€?)

    try:
        import pythoncom  # type: ignore
        import win32com.client  # type: ignore
    except ImportError as exc:
        raise RuntimeError("缂哄皯 pywin32锛屾棤娉曡皟鐢?Windows 璇煶璇嗗埆銆?) from exc

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
        recognizer = win32com.client.Dispatch("SAPI.SpInprocRecognizer")
        recognizer.AudioInput = win32com.client.Dispatch("SAPI.SpMMAudioIn")
        context = win32com.client.DispatchWithEvents(
            recognizer.CreateRecoContext(),
            _SapiEvents,
        )
        try:
            context.EventInterests = 16  # SPEI_RECOGNITION
        except Exception:
            pass
        grammar = context.CreateGrammar()
        grammar.DictationSetState(1)

        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline and not done.is_set():
            pythoncom.PumpWaitingMessages()
            time.sleep(0.05)

        text = _clean_voice_text(result["text"])
        if text:
            return text
        raise RuntimeError("娌℃湁璇嗗埆鍒拌闊筹紝璇风‘璁ら害鍏嬮鏉冮檺鍜?Windows 璇煶璇嗗埆璇█宸插惎鐢ㄣ€?)
    finally:
        if grammar is not None:
            try:
                grammar.DictationSetState(0)
            except Exception:
                pass
        pythoncom.CoUninitialize()


def _recognize_speech_once(timeout_sec: float = 7.0, phrase_time_limit: float = 8.0) -> str:
    errors: list[str] = []
    try:
        return _recognize_with_speech_recognition(timeout_sec, phrase_time_limit)
    except ImportError:
        errors.append("鏈畨瑁?speech_recognition/pyaudio")
    except Exception as exc:
        errors.append(str(exc))

    try:
        return _recognize_with_windows_sapi(timeout_sec)
    except Exception as exc:
        errors.append(str(exc))

    detail = "锛?.join(error for error in errors if error)
    raise RuntimeError(detail or "璇煶璇嗗埆涓嶅彲鐢ㄣ€?)


class InputBox(QFrame, ScalableOverlay):
    _BASE_WIDTH = 260
    _BASE_HEIGHT = 40
    _BASE_RADIUS = 24
    WIDTH = 260
    HEIGHT = 40
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
        self._voice_btn.setAccessibleName("璇煶杈撳叆")
        self._voice_btn.setToolTip("璇煶杈撳叆")
        self._voice_btn.setStyleSheet(BTN_ICON)
        self._voice_btn.clicked.connect(self.start_voice_input)
        self._field = QLineEdit()
        self._field.setPlaceholderText("杈撳叆娑堟伅鈥?)
        self._field.setFrame(False)
        self._field.setFont(_app_font(15))
        self._field.returnPressed.connect(self._submit)
        self._btn = QPushButton("鍙戦€?)
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
        self.HEIGHT = _scaled_int(self._BASE_HEIGHT, self._ui_scale, 28)
        self.RADIUS = _scaled_int(self._BASE_RADIUS, self._ui_scale, 14)
        self.setFixedSize(self.WIDTH, self.HEIGHT)
        self._lay.setContentsMargins(
            _scaled_int(6, self._ui_scale, 4),
            _scaled_int(4, self._ui_scale, 2),
            _scaled_int(8, self._ui_scale, 4),
            _scaled_int(4, self._ui_scale, 2),
        )
        self._lay.setSpacing(_scaled_int(4, self._ui_scale, 2))
        button_size = _scaled_int(28, self._ui_scale, 22)
        icon_size = _scaled_int(20, self._ui_scale, 16)
        self._voice_btn.setFixedSize(button_size, button_size)
        self._voice_btn.setIconSize(QSize(icon_size, icon_size))
        self._field.setFont(_app_font(_scaled_int(15, self._ui_scale, 10)))
        self.setStyleSheet(_glass_style(self.RADIUS))

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
        _VOICE_LOGGER.info("寮€濮嬭闊宠緭鍏?)
        self._voice_listening = True
        self._voice_btn.setIcon(_make_mic_icon("#ef476f"))
        self._voice_btn.setToolTip("姝ｅ湪鍚紝璇疯璇濃€?)
        if not self._field.text().strip():
            self._field.setPlaceholderText("姝ｅ湪鍚紝璇疯璇濃€?)
        self._voice_thread = threading.Thread(target=self._run_voice_input, daemon=True)
        self._voice_thread.start()

    def _run_voice_input(self) -> None:
        try:
            text = _recognize_speech_once()
            _VOICE_LOGGER.info("璇煶璇嗗埆鎴愬姛锛屾枃鏈暱搴?%s", len(text))
            self._voice_text_ready.emit(text)
        except Exception as exc:
            _VOICE_LOGGER.warning("璇煶璇嗗埆澶辫触: %s", exc)
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
        if prefix and not prefix.endswith((" ", "\n")) and text[:1] not in "锛屻€傦紒锛?.!?":
            spacer = "" if re.search(r"[\u4e00-\u9fff]$", prefix) else " "
        merged = f"{prefix}{spacer}{text}{suffix}"
        self.set_text(merged)
        self._field.setFocus()
        self._field.setCursorPosition(len(prefix) + len(spacer) + len(text))

    def _show_voice_error(self, message: str) -> None:
        message = message.strip() or "璇煶璇嗗埆澶辫触锛岃鍐嶈瘯涓€娆°€?
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
        if self._voice_btn.toolTip().startswith("姝ｅ湪鍚?):
            self._voice_btn.setToolTip("璇煶杈撳叆")
        if self._field.placeholderText().startswith("姝ｅ湪鍚?):
            self._field.setPlaceholderText("杈撳叆娑堟伅鈥?)

    def _restore_voice_hint(self) -> None:
        if self._voice_listening:
            return
        self._voice_btn.setToolTip("璇煶杈撳叆")
        self._field.setPlaceholderText("杈撳叆娑堟伅鈥?)

    def is_voice_click(self, mouse_pos: tuple[int, int]) -> bool:
        return self._voice_btn.geometry().contains(self.mapFromGlobal(QPoint(*mouse_pos)))

    def is_send_click(self, mouse_pos: tuple[int, int]) -> bool:
        return self._btn.geometry().contains(self.mapFromGlobal(QPoint(*mouse_pos)))

    def handle_event(self, _event) -> bool:
        return False

    def is_enter_submit(self, _event) -> bool:
        return False


# ---------------------------------------------------------------------------
# 鎺у埗鍙?
# ---------------------------------------------------------------------------


class _PetCellButton(QFrame):
    """瑙掕壊鍗＄墖锛氬浘鐗囧湪涓娿€佸悕绉板湪涓嬶紱鍗曞嚮璇︽儏锛屽弻鍑诲垏鎹紱鍙抽敭绠＄悊銆?""

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
            ("璁剧疆鍔ㄤ綔鏄犲皠", "action_map"),
            ("绠＄悊鍔ㄤ綔", "actions"),
            ("缂栬緫鎬ф牸绠€浠?, "personality"),
            ("閲嶅懡鍚嶈鑹?, "rename"),
            ("鍒犻櫎瑙掕壊", "delete"),
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
# 鑱婂ぉ璁板綍 / 涓婁紶 / Live2D 棰勮
# ---------------------------------------------------------------------------


class ChatHistoryStore:
    """鎸夎鑹插悕鎸佷箙鍖栬亰澶╄褰曞埌 assets/chat_history/瑙掕壊鍚?json"""

    def __init__(self, project_root: str) -> None:
        self._dir = os.path.join(project_root, "assets", "chat_history")
        os.makedirs(self._dir, exist_ok=True)

    @staticmethod
    def _safe_name(name: str) -> str:
        return re.sub(r'[\\/:*?"<>|]', "_", name.strip()) or "鏈懡鍚?

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
    """鎵弿 assets/voice_packs 涓嬬殑 TTS 闊宠壊鍖呮竻鍗曘€?""
    default_language = language_from_edge_voice(config.EDGE_TTS_VOICE)
    packs: list[dict] = [
        {
            "id": "",
            "name": "璺熼殢璇煶鍖?/ 榛樿",
            "display_name": "榛樿",
            "icon": "馃帣锔?,
            "description": "璺熼殢褰撳墠瑙掕壊鎴?.env 榛樿闊宠壊銆?,
            "sample_text": "浣犲ソ鍛€锛屼粖澶╀篃涓€璧峰姞娌广€?,
            "edge_voice": config.EDGE_TTS_VOICE,
            "language": (
                {"id": default_language, "label": language_label(default_language)}
                if default_language
                else {}
            ),
        }
    ]
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
        voice_profiles = data.get("voice_profiles") if isinstance(data.get("voice_profiles"), dict) else {}
        default_profile = voice_profiles.get("default") if isinstance(voice_profiles.get("default"), dict) else {}
        profile_edge_voice = str(default_profile.get("edge_voice") or "").strip()
        profile_language = language_from_edge_voice(profile_edge_voice)
        language = data.get("language") if isinstance(data.get("language"), dict) else {}
        if profile_language and not language:
            language = {"id": profile_language, "label": language_label(profile_language)}
        packs.append(
            {
                "id": pack_id,
                "name": name,
                "display_name": name,
                "icon": str(data.get("icon") or "馃帣锔?),
                "description": str(data.get("description") or "TTS 闊宠壊鍙傛暟鍖呫€?),
                "sample_text": str(data.get("sample_text") or "浣犲ソ鍛€锛屼粖澶╀篃涓€璧峰姞娌广€?),
                "language": language,
                "edge_voice": profile_edge_voice,
                "is_custom": bool(data.get("is_custom", False)),
                "sample_count": int((data.get("analysis") or {}).get("sample_count") or 0)
                if isinstance(data.get("analysis"), dict)
                else len(data.get("samples") or []) if isinstance(data.get("samples"), list) else 0,
                "denoised_count": int(noise_reduction.get("processed_count") or 0),
                "converted_count": len(conversions),
            }
        )
    return packs


def tts_voice_preset_choices(current_edge_voice: str = "") -> list[dict]:
    """鎶婂浐瀹?Edge 闊宠壊涔熶綔涓鸿闊冲寘鍒楄〃閲岀殑鍚岀骇閫夐」銆?""
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
                "icon": "馃攰",
                "description": f"鍥哄畾 Edge TTS 闊宠壊锛歿voice_id}銆傞€夋嫨鍚庝細瑕嗙洊璇煶鍖呭唴缃煶鑹层€?,
                "sample_text": "浣犲ソ鍛€锛屼粖澶╀篃涓€璧峰姞娌广€?,
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
                "icon": "馃攰",
                "description": "褰撳墠鑷畾涔?Edge TTS 闊宠壊銆?,
                "sample_text": "浣犲ソ鍛€锛屼粖澶╀篃涓€璧峰姞娌广€?,
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


class VoicePackImportDialog(QDialog):
    def __init__(self, project_root: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project_root = project_root
        self._files: list[str] = []
        self._result_pack: dict[str, Any] | None = None

        self.setWindowTitle("瀵煎叆璇煶鍖?)
        self.resize(460, 360)
        lay = QVBoxLayout(self)

        lay.addWidget(QLabel("璇煶鍖呭悕绉?))
        self._name = QLineEdit()
        self._name.setPlaceholderText("渚嬪锛氭垜鐨勪腑鏂囪闊?)
        lay.addWidget(self._name)

        lay.addWidget(QLabel("璇█"))
        self._language = QComboBox()
        for preset in VOICE_PACK_LANGUAGE_PRESETS:
            self._language.addItem(str(preset["label"]), str(preset["id"]))
        lay.addWidget(self._language)

        row = QHBoxLayout()
        file_btn = QPushButton("閫夋嫨闊抽鎴?MP4")
        file_btn.setStyleSheet(BTN_GLASS)
        file_btn.clicked.connect(self._choose_files)
        folder_btn = QPushButton("瀵煎叆鏂囦欢澶?)
        folder_btn.setStyleSheet(BTN_GLASS)
        folder_btn.clicked.connect(self._choose_folder)
        row.addWidget(file_btn)
        row.addWidget(folder_btn)
        lay.addLayout(row)

        self._file_summary = QLabel("灏氭湭閫夋嫨闊抽鎴?MP4 鏍锋湰锛屽彲涓€娆￠€夋嫨涓€涓垨澶氫釜鏂囦欢")
        self._file_summary.setWordWrap(True)
        self._file_summary.setStyleSheet("color:#64748b;font-size:12px;")
        lay.addWidget(self._file_summary, 1)

        hint = QLabel("瀵煎叆鍚庝細淇濆瓨鍒?assets/voice_packs锛汳P4 浼氬厛鎶藉彇闊宠建杞垚 MP3銆俉AV 鏍锋湰浼氱敓鎴愯交搴﹂檷鍣壇鏈紝鍘熷鏂囦欢涓嶈鐩栥€佷笉鏀瑰啓銆?)
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
            "閫夋嫨璇煶鏍锋湰",
            self._project_root,
            f"闊抽/瑙嗛鏂囦欢 ({exts});;闊抽鏂囦欢 ({' '.join(f'*{ext}' for ext in AUDIO_SAMPLE_EXTENSIONS)});;MP4 瑙嗛 (*.mp4);;鎵€鏈夋枃浠?(*.*)",
        )
        self._add_files(paths)

    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "閫夋嫨璇煶鍖呮枃浠跺す", self._project_root)
        if not folder:
            return
        found: list[str] = []
        for root, _dirs, files in os.walk(folder):
            for fname in files:
                if os.path.splitext(fname)[1].lower() in IMPORT_SAMPLE_EXTENSIONS:
                    found.append(os.path.join(root, fname))
        if not found:
            QMessageBox.warning(self, "鏈壘鍒伴煶棰?, "杩欎釜鏂囦欢澶归噷娌℃湁鍙鍏ョ殑闊抽鎴?MP4 鏂囦欢銆?)
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
            self._file_summary.setText("灏氭湭閫夋嫨闊抽鎴?MP4 鏍锋湰")
            return
        names = [os.path.basename(path) for path in self._files[:6]]
        more = len(self._files) - len(names)
        text = f"宸查€夋嫨 {len(self._files)} 涓煶棰戞牱鏈琝n" + "\n".join(names)
        if more > 0:
            text += f"\n... 杩樻湁 {more} 涓?
        self._file_summary.setText(text)

    def _accept_import(self) -> None:
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "缂哄皯鍚嶇О", "璇峰～鍐欒闊冲寘鍚嶇О銆?)
            return
        if not self._files:
            QMessageBox.warning(self, "缂哄皯闊抽", "璇疯嚦灏戦€夋嫨涓€涓湰鍦伴煶棰戞垨 MP4 鏍锋湰锛屼篃鍙互涓€娆￠€夋嫨澶氫釜銆?)
            return
        base_dir = os.path.join(self._project_root, "assets", "voice_packs")
        try:
            self._result_pack = create_imported_voice_pack(
                display_name=name,
                language_id=str(self._language.currentData() or "zh-CN"),
                sample_paths=self._files,
                base_dir=base_dir,
            )
        except Exception as exc:
            QMessageBox.critical(self, "瀵煎叆澶辫触", f"璇煶鍖呭鍏ュけ璐ワ細{exc}")
            return
        self.accept()


def _stem_no_ext(path: str) -> str:
    base = os.path.basename(path)
    if base.lower().endswith(".motion3.json"):
        return base[: -len(".motion3.json")]
    return os.path.splitext(base)[0]


MAO_PRO_ZH_DISPLAY = "灏忛瓟濂?


def is_mao_pro_zh_model(model_path: str) -> bool:
    return "mao_pro_zh" in model_path.replace("\\", "/").lower()


def motion_label_from_filename(filename: str) -> str:
    """浠庢枃浠跺悕鎻愬彇 anim_ 鍚庨潰鐨勫姩浣滃悕锛屽 杩欑嫍_anim_鐖变綘.gif 鈫?鐖变綘銆?""
    base = os.path.splitext(os.path.basename(filename))[0]
    m = re.search(r"anim_(.+)$", base, re.IGNORECASE)
    if m:
        return m.group(1)
    return base


def resolve_mao_pro_motion_preview(model_path: str) -> str:
    """mao_pro_zh锛氫紭鍏堜娇鐢?runtime 涓嬬紦瀛樼殑棣栧抚棰勮鍥俱€?""
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
        "personality": "娲绘臣鍙埍鐨勫皬榄斿コ锛屽枩娆㈤櫔浼翠綘瀛︿範涓庡伐浣溿€?,
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
        print(f"[FlatUpload] 鎻愬彇 GIF 棣栧抚澶辫触: {exc}")
        return False


def find_flat_idle_gif(project_root: str, pet_id: str) -> str:
    """鏌ユ壘 idle GIF锛涜嫢鏃?idle 鍒欒繑鍥炶瑙掕壊绗竴涓?GIF銆?""
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
    """杩欑嫍锛氳创鍥句娇鐢?idle 鍔ㄤ綔棣栧抚锛屾棤 idle 鍒欑敤绗竴涓姩浣滈甯с€?""
    if pet.get("id") != "杩欑嫍":
        return pet
    pet = dict(pet)
    gif = pet.get("idle_gif") or ""
    if not gif or not os.path.isfile(gif):
        gif = find_flat_idle_gif(project_root, "杩欑嫍")
    if not gif or not os.path.isfile(gif):
        return pet
    images_dir = os.path.join(project_root, "assets", "images")
    os.makedirs(images_dir, exist_ok=True)
    out = os.path.join(images_dir, "杩欑嫍_idle_frame.png")
    if _gif_first_frame_to_png(gif, out):
        pet["thumb"] = out
        pet["idle_image"] = out
        pet["idle_gif"] = gif
    return pet


def scan_flat_pets(project_root: str) -> list[dict]:
    """鎵弿 assets 涓?GIF/PNG 涓庨潤鎬佸浘锛岀敓鎴愬钩闈㈣鑹插垪琛ㄣ€?""
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

    pets: list[dict] = []
    for pet_id in sorted(pet_ids):
        thumb = portrait_by_pet.get(pet_id, "")
        idle_gif = _pick_idle_gif(pet_id)
        gifs = gifs_by_pet.get(pet_id, {})
        png_actions = png_by_pet.get(pet_id, {})
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
                "personality": f"骞抽潰绱犳潗瑙掕壊 路 {pet_id}",
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
    """绠＄悊瑙掕壊鍔ㄤ綔锛氭煡鐪?/ 娣诲姞 / 鍒犻櫎 / 閲嶆柊鏄犲皠銆?""

    def __init__(self, pet: dict, project_root: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pet = pet
        self._root = project_root
        self.setWindowTitle(f"绠＄悊鍔ㄤ綔 - {pet.get('name', '')}")
        self.resize(520, 460)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"<h3>{pet.get('name', '')} 鐨勫姩浣滃垪琛?/h3>"))
        self._list = QListWidget()
        lay.addWidget(self._list, 1)
        row = QHBoxLayout()
        add_btn = QPushButton("娣诲姞鍔ㄤ綔")
        del_btn = QPushButton("鍒犻櫎閫変腑")
        map_btn = QPushButton("閲嶆柊鏄犲皠")
        add_btn.clicked.connect(self._add_action)
        del_btn.clicked.connect(self._delete_action)
        map_btn.clicked.connect(self._remap_actions)
        row.addWidget(add_btn)
        row.addWidget(del_btn)
        row.addWidget(map_btn)
        lay.addLayout(row)
        close_btn = QPushButton("鍏抽棴")
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
            self, "娣诲姞鍔ㄤ綔", self._root, "鍔ㄧ敾 (*.gif *.png)"
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
        if os.path.isfile(fp) and QMessageBox.question(self, "纭", f"鍒犻櫎 {item.text()}锛?) == QMessageBox.StandardButton.Yes:
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
    """瑙掕壊鍗＄墖鍙抽敭锛氬垹闄?/ 閲嶅懡鍚?/ 鏀圭畝浠嬨€?""

    @staticmethod
    def delete_pet(console: "ControlConsole", pet: dict) -> None:
        name = pet.get("name", pet.get("id", ""))
        if QMessageBox.question(
            console, "鍒犻櫎瑙掕壊", f"纭畾鍒犻櫎銆寋name}銆嶅強鍏舵墍鏈夌礌鏉愪笌閰嶇疆锛?
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
        console._show_toast(f"宸插垹闄よ鑹? {name}")

    @staticmethod
    def rename_pet(console: "ControlConsole", pet: dict) -> None:
        old_name = pet.get("name", pet.get("id", ""))
        new_name, ok = QInputDialog.getText(console, "閲嶅懡鍚嶈鑹?, "鏂板悕绉帮細", text=old_name)
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
        console._show_toast(f"宸查噸鍛藉悕涓? {new_name}")

    @staticmethod
    def edit_personality(console: "ControlConsole", pet: dict) -> None:
        text, ok = QInputDialog.getMultiLineText(
            console, "缂栬緫鎬ф牸绠€浠?, "鎬ф牸鎻忚堪锛?, pet.get("personality", "")
        )
        if ok:
            pet["personality"] = text.strip()
            console._show_toast("鎬ф牸绠€浠嬪凡鏇存柊")

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
        console._show_toast("鍔ㄤ綔鏄犲皠宸蹭繚瀛?)

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
    """瑙ｆ瀽 Live2D 棰勮鍥撅紱鏃?textures 鏃跺皾璇?motions 鐩綍鎴栨ā鍨嬬洰褰曞唴 PNG銆?""
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
        return False, "璇烽€夋嫨鏈夋晥鐨?.model3.json 鏂囦欢"
    runtime = os.path.dirname(model_path)
    try:
        with open(model_path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"鏃犳硶璇诲彇妯″瀷 JSON: {exc}"
    refs = data.get("FileReferences", {})
    moc = refs.get("Moc") or ""
    moc_path = os.path.join(runtime, moc) if moc else ""
    if not moc_path or not os.path.isfile(moc_path):
        return False, "缂哄皯 .moc3 鏂囦欢"
    textures = refs.get("Textures") or []
    has_tex = any(os.path.isfile(os.path.join(runtime, t)) for t in textures)
    if not has_tex:
        preview = resolve_live2d_thumb(model_path)
        if not preview:
            return False, "缂哄皯璐村浘鏂囦欢澶癸紝涓旀棤娉曟壘鍒板鐢ㄩ瑙堝浘"
    return True, "楠岃瘉閫氳繃"


class ActionMappingDialog(QDialog):
    """涓?D 鍔ㄤ綔绫诲瀷閫夋嫨瀵瑰簲绱犳潗鏂囦欢锛堟敮鎸佸閫夛級銆?""

    def __init__(
        self,
        pet_name: str,
        motion_files: list[str],
        parent: QWidget | None = None,
        *,
        initial: dict[str, list[str]] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"鍔ㄤ綔鏄犲皠 - {pet_name}")
        self.resize(560, 480)
        self._mapping: dict[str, list[str]] = {}
        initial = initial or {}
        outer = QVBoxLayout(self)
        outer.addWidget(QLabel(f"<h3>涓恒€寋pet_name}銆嶉厤缃姩浣滄槧灏?/h3>"))
        outer.addWidget(QLabel("涓?happy / sad / hungry / angry / idle 閫夋嫨鍔ㄤ綔鏂囦欢锛涙湭鏄犲皠灏嗘挱鏀惧緟鏈恒€?))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        self._lists: dict[str, QListWidget] = {}
        for code in D_ACTION_CODES:
            row = QVBoxLayout()
            row.addWidget(QLabel(f"<b>{D_ACTION_LABELS.get(code, code)}</b> ({code})"))
            lw = QListWidget()
            lw.setMinimumHeight(72)
            lw.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
            for fname in motion_files:
                lw.addItem(fname)
            selected = set(initial.get(code, []))
            for i in range(lw.count()):
                item = lw.item(i)
                if item and item.text() in selected:
                    item.setSelected(True)
            self._lists[code] = lw
            row.addWidget(lw)
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
        for code, lw in self._lists.items():
            selected = [item.text() for item in lw.selectedItems()]
            if selected:
                out[code] = selected
        return out


class Live2dUploadDialog(QDialog):
    def __init__(self, project_root: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._root = project_root
        self._model_path = ""
        self.setWindowTitle("涓婁紶 Live2D 妯″瀷")
        self.resize(480, 320)
        lay = QVBoxLayout(self)
        self._name = QLineEdit()
        self._name.setPlaceholderText("瑙掕壊濮撳悕锛堝繀濉級")
        lay.addWidget(QLabel("瑙掕壊濮撳悕"))
        lay.addWidget(self._name)
        self._personality = QLineEdit()
        self._personality.setPlaceholderText("鎬ф牸鎻忚堪锛堝彲閫夛級")
        lay.addWidget(QLabel("鎬ф牸鎻忚堪"))
        lay.addWidget(self._personality)
        pick_row = QHBoxLayout()
        self._path_lbl = QLabel("鏈€夋嫨鏂囦欢")
        pick_btn = QPushButton("閫夋嫨 .model3.json")
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
        path, _ = QFileDialog.getOpenFileName(self, "閫夋嫨妯″瀷", self._root, "Live2D Model (*.model3.json)")
        if path:
            self._model_path = path
            self._path_lbl.setText(os.path.basename(path))

    def _on_ok(self) -> None:
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "鎻愮ず", "璇峰～鍐欒鑹插鍚?)
            return
        ok, msg = validate_live2d_model(self._model_path)
        if not ok:
            QMessageBox.warning(self, "楠岃瘉澶辫触", msg)
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


class FlatUploadDialog(QDialog):
    def __init__(self, project_root: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._root = project_root
        self._uploaded_files: list[str] = []
        self.setWindowTitle("涓婁紶骞抽潰绱犳潗")
        self.resize(480, 280)
        lay = QVBoxLayout(self)
        self._name = QLineEdit()
        lay.addWidget(QLabel("瑙掕壊濮撳悕锛堝繀濉級"))
        lay.addWidget(self._name)
        self._personality = QLineEdit()
        lay.addWidget(QLabel("鎬ф牸鎻忚堪锛堝彲閫夛級"))
        lay.addWidget(self._personality)
        self._hint = QLabel("鍑嗗涓婁紶鍔ㄤ綔鈥?)
        lay.addWidget(self._hint)
        upload_btn = QPushButton("涓婁紶褰撳墠鍔ㄤ綔")
        upload_btn.clicked.connect(self._upload_one)
        lay.addWidget(upload_btn)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._finish)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)
        self._action_index = 1
        self._result_pet: dict | None = None

    def _upload_one(self) -> None:
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "鎻愮ず", "璇峰厛濉啓瑙掕壊濮撳悕")
            return
        self._hint.setText(f"杩欐槸鍔ㄤ綔{self._action_index}锛岃閫夋嫨 GIF 鎴栧寮?PNG 搴忓垪甯?)
        gif_path, _ = QFileDialog.getOpenFileName(self, "閫夋嫨 GIF", self._root, "GIF (*.gif)")
        dest_dir = os.path.join(self._root, "assets", "animations", name)
        os.makedirs(dest_dir, exist_ok=True)
        if gif_path:
            dest = os.path.join(dest_dir, os.path.basename(gif_path))
            shutil.copy2(gif_path, dest)
            self._uploaded_files.append(os.path.basename(dest))
            self._action_index += 1
            cont = QMessageBox.question(self, "缁х画", "鏄惁缁х画娣诲姞鍔ㄤ綔锛?, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if cont == QMessageBox.StandardButton.No:
                self._finish()
            return
        png_paths, _ = QFileDialog.getOpenFileNames(self, "閫夋嫨 PNG 搴忓垪甯?, self._root, "PNG (*.png)")
        if not png_paths:
            return
        png_paths.sort()
        prefix = _stem_no_ext(png_paths[0])
        for i, src in enumerate(png_paths, 1):
            dest = os.path.join(dest_dir, f"{prefix}_{i:03d}.png")
            shutil.copy2(src, dest)
            self._uploaded_files.append(os.path.basename(dest))
        self._action_index += 1
        cont = QMessageBox.question(self, "缁х画", "鏄惁缁х画娣诲姞鍔ㄤ綔锛?, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if cont == QMessageBox.StandardButton.No:
            self._finish()

    def _finish(self) -> None:
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "鎻愮ず", "璇峰～鍐欒鑹插鍚?)
            return
        if not self._uploaded_files:
            QMessageBox.warning(self, "鎻愮ず", "璇疯嚦灏戜笂浼犱竴涓姩浣?)
            return
        pet_id = re.sub(r"\s+", "_", name)
        map_dlg = ActionMappingDialog(name, self._uploaded_files, self)
        if map_dlg.exec() != QDialog.DialogCode.Accepted:
            return
        save_pet_action_mapping(self._root, pet_id, map_dlg.mapping())
        images_dir = os.path.join(self._root, "assets", "images")
        os.makedirs(images_dir, exist_ok=True)
        thumb = os.path.join(images_dir, f"{name}_image.png")
        dest_dir = os.path.join(self._root, "assets", "animations", name)
        if os.path.isdir(dest_dir):
            for fname in sorted(os.listdir(dest_dir)):
                if fname.lower().endswith(".gif"):
                    _gif_first_frame_to_png(os.path.join(dest_dir, fname), thumb)
                    break
        self._result_pet = {
            "id": name,
            "name": name,
            "personality": self._personality.text().strip(),
            "thumb": thumb if os.path.isfile(thumb) else "",
            "idle_image": thumb if os.path.isfile(thumb) else "",
            "is_flat": True,
            "is_custom": True,
            "motions": [],
            "anim_dir": dest_dir,
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
        # 鑷姩鎵弿 assets/models/ 涓嬫墍鏈?Live2D 妯″瀷
        from app.live2d_scanner import scan_live2d_models
        models_dir = os.path.join(project_root, "assets", "models")
        scanned = scan_live2d_models(models_dir)
        if scanned:
            self._live2d = scanned
            # 淇 mao_pro_zh 鐨勬樉绀哄悕鍜岀缉鐣ュ浘
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
                    "name": "灏忛粦",
                    "thumb": tex,
                    "personality": "娲绘臣鍙埍鐨?AI 妗屽疇锛屽枩娆㈤櫔浼翠綘瀛︿範涓庡伐浣溿€?,
                    "motions": motions,
                    "model_path": model_path,
                    "is_flat": False,
                },
            ]
        self._flat = [
            apply_zhegou_idle_thumb(project_root, p)
            for p in scan_flat_pets(project_root)
        ]
        self._custom_pets = self._build_custom_pet_list()
        self._current_pet_id = self._live2d[0]["id"] if self._live2d else (self._flat[0]["id"] if self._flat else "")
        self._chats: list[dict] = []
        self._load_chat_histories()
        self._build_ui()

    def _rescan_flat_pets(self) -> None:
        self._flat = [
            apply_zhegou_idle_thumb(self._project_root, p)
            for p in scan_flat_pets(self._project_root)
        ]

    def _build_custom_pet_list(self) -> list[dict]:
        pets: list[dict] = []
        for p in self._flat:
            if p.get("id") in self._custom_ids:
                p = self._enrich_pet_motions(dict(p))
                p["is_custom"] = True
                pets.append(p)
        return pets

    def _flat_library_pets(self) -> list[dict]:
        """骞抽潰绱犳潗搴擄細涓嶅惈鑷畾涔夋爣绛鹃〉涓婁紶鐨勮鑹层€?""
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
            self._chats.append({"name": "榛樿", "color": "#3b82f6", "msgs": []})

    def _save_current_chat(self) -> None:
        if self._ai_i < 0 or self._ai_i >= len(self._chats):
            return
        chat = self._chats[self._ai_i]
        self._chat_store.save(chat["name"], chat["msgs"])

    def _build_ui(self) -> None:
        self.setWindowTitle("妗岄潰瀹犵墿鎺у埗鍙?)
        self.resize(800, 600)
        self.setMinimumSize(720, 540)
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
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
        sb_lay.addWidget(QLabel("妗岄潰瀹犵墿"))
        self._menu_btns: dict[str, QPushButton] = {}
        for pid, icon, label in (
            ("pet_settings", "鈿欙笍", "妗屽疇璁剧疆"),
            ("dashboard", "馃搳", "浠〃鐩?),
            ("characters", "馃懁", "瑙掕壊閫夋嫨"),
            ("ai_settings", "馃挰", "AI瀵硅瘽"),
            ("permissions", "馃敀", "鏉冮檺璁剧疆"),
            ("theme", "馃帹", "涓婚"),
            ("exit", "馃毆", "閫€鍑?),
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
        chrome = QHBoxLayout()
        chrome.addStretch()
        for label, slot in (("鈥?, self.showMinimized), ("鈻?, self._toggle_max), ("脳", self.close)):
            b = QPushButton(label)
            b.setFixedSize(28, 28)
            b.clicked.connect(slot)
            chrome.addWidget(b)
        right.addLayout(chrome)
        self._stack = QStackedWidget()
        self._stack.addWidget(self._page_pet_settings())
        self._stack.addWidget(self._page_dashboard())
        self._stack.addWidget(self._page_characters())
        self._stack.addWidget(self._page_ai())
        self._stack.addWidget(self._page_placeholder("鏉冮檺璁剧疆"))
        self._stack.addWidget(self._page_placeholder("涓婚"))
        self._stack.addWidget(self._page_pet_main())
        right.addWidget(self._stack, 1)
        root.addLayout(right, 1)
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
        self._log(f"鍒囨崲: {page}")

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
        thumb = pet.get("thumb") or self._pet_idle_path(pet)
        self._dash_pet_pic.setPixmap(_load_pixmap(thumb, QSize(100, 100)))
        self._dash_pet_name.setText(f"<b>{pet['name']}</b>")
        self._dash_pet_personality.setText(pet.get("personality", ""))

    def _switch_current_pet(self, pet: dict) -> None:
        self._apply_pet_switch(pet)

    def _open_pet_main(self, pet: dict) -> None:
        self._pet_main_id = pet["id"]
        self._nav("pet_main")
        self._log(f"鏌ョ湅瑙掕壊: {pet['name']}")

    def _apply_pet_switch(self, pet: dict) -> None:
        self._rescan_flat_pets()
        pet = self._get_pet(pet["id"]) or pet
        self._current_pet_id = pet["id"]
        self._sel_pet = pet["id"]
        self._pet_main_id = pet["id"]
        self._stop_animation()
        self._show_toast(f"宸插垏鎹㈠埌 {pet['name']}")
        self._nav("dashboard")
        self._log(f"鍒囨崲瑙掕壊: {pet['name']} ({pet['id']})")
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
            return value.strip().lower() in {"1", "true", "yes", "y", "on", "寮€鍚?, "鍏佽", "璁颁綇"}
        return bool(value)

    def _load_pet_personalization_settings(self) -> dict[str, dict[str, Any]]:
        data = self._default_pet_personalization_settings()
        if not os.path.isfile(self._pet_settings_path):
            return data
        try:
            with open(self._pet_settings_path, encoding="utf-8") as f:
                loaded = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            self._log(f"璇诲彇妗屽疇璁剧疆澶辫触锛屼娇鐢ㄩ粯璁ゅ€? {exc}")
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
            QMessageBox.warning(self, "淇濆瓨澶辫触", f"鏃犳硶淇濆瓨妗屽疇璁剧疆锛歿exc}")
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
            check = QCheckBox(str(field.get("text") or "寮€鍚?))
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
            if hasattr(self, "_pet_settings_status"):
                self._pet_settings_status.setText("宸蹭繚瀛?)
            self._show_toast("妗屽疇璁剧疆宸蹭繚瀛?)
            self._log("妗屽疇璁剧疆宸蹭繚瀛?)

    def _reset_pet_personalization_settings(self) -> None:
        self._pet_settings = self._default_pet_personalization_settings()
        self._apply_pet_personalization_controls()
        if self._save_pet_personalization_settings():
            if hasattr(self, "_pet_settings_status"):
                self._pet_settings_status.setText("宸叉仮澶嶉粯璁?)
            self._show_toast("妗屽疇璁剧疆宸叉仮澶嶉粯璁?)
            self._log("妗屽疇璁剧疆宸叉仮澶嶉粯璁?)

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
        header.addWidget(QLabel("<h2>妗屽疇璁剧疆</h2>"))
        header.addStretch()
        self._pet_settings_status = QLabel("")
        self._pet_settings_status.setStyleSheet("color:#64748b;")
        header.addWidget(self._pet_settings_status)
        reset_btn = QPushButton("鎭㈠榛樿")
        reset_btn.setStyleSheet(BTN_GLASS)
        reset_btn.clicked.connect(self._reset_pet_personalization_settings)
        save_btn = QPushButton("淇濆瓨璁剧疆")
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
        wd = "涓€浜屼笁鍥涗簲鍏棩"[now.weekday()]
        lay.addWidget(QLabel(f"<h2>娆㈣繋鍥炴潵锛岀敤鎴?/h2><p>{now.year}骞磠now.month}鏈坽now.day}鏃?鏄熸湡{wd}</p>"))
        cards = QHBoxLayout()
        for icon, title, key, col in (("馃惥", "瀹犵墿蹇冩儏", "mood", "#3b82f6"), ("馃敟", "鑳介噺鍊?, "energy", "#fb923c"), ("鉂わ笍", "濂芥劅搴?, "affection", "#ec4899")):
            cards.addWidget(self._stat_card(icon, title, self.stats[key], col))
        lay.addLayout(cards)
        lay.addWidget(QLabel("<h3>褰撳墠瀹犵墿绠€浠?/h3>"))
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
        lay.addWidget(QLabel("<h2>鍚屼箟璇嶇鐞?/h2>"))
        ph = QLabel("璇蜂粠妗屽疇璁剧疆闈㈡澘鎵撳紑浠ョ鐞嗗悓涔夎瘝銆?)
        ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph.setStyleSheet("color:#94a3b8;font-size:16px;")
        lay.addWidget(ph, 1)
        return w

    def _page_characters(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(24, 16, 24, 24)
        lay.addWidget(QLabel("<h2>瑙掕壊閫夋嫨</h2>"))
        outer = QHBoxLayout()
        self._tabs = QTabWidget()
        self._tabs.addTab(self._char_grid(self._live2d, add_plus=True, on_plus=self._upload_live2d), "Live2D搴?)
        self._tabs.addTab(self._char_grid(self._flat_library_pets(), add_plus=False), "骞抽潰绱犳潗搴?)
        custom_wrap = QWidget()
        custom_lay = QVBoxLayout(custom_wrap)
        custom_lay.addWidget(self._char_grid(self._custom_pets, add_plus=False), 1)
        up_row = QHBoxLayout()
        up_row.addStretch()
        up = QPushButton("涓婁紶骞抽潰绱犳潗")
        up.setStyleSheet(BTN_PRIMARY)
        up.clicked.connect(self._upload_flat)
        up_row.addWidget(up)
        up_row.addStretch()
        custom_lay.addLayout(up_row)
        self._tabs.addTab(custom_wrap, "鑷畾涔?)
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
    ) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        grid = QGridLayout(inner)
        if not pets and not add_plus:
            hint = QLabel("鏆傛棤骞抽潰绱犳潗\n璇峰皢 {pet_id}_image.png 鏀惧叆 assets/images/\n鍔ㄥ浘鏀惧叆 assets/animations/")
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hint.setStyleSheet("color:#94a3b8;padding:32px;")
            grid.addWidget(hint, 0, 0, 1, 4)
        for i, pet in enumerate(pets):
            cell = self._pet_cell(pet)
            grid.addWidget(cell, i // 4, i % 4)
        if add_plus:
            plus = QPushButton("+")
            plus.setFixedSize(128, 128)
            plus.clicked.connect(on_plus or (lambda: self._log("涓婁紶")))
            grid.addWidget(plus, len(pets) // 4, len(pets) % 4)
        scroll.setWidget(inner)
        return scroll

    def _upload_live2d(self) -> None:
        dlg = Live2dUploadDialog(self._project_root, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            pet = dlg.result_pet()
            if pet:
                self._live2d.append(pet)
                self._reload_character_tabs()
                self._show_toast(f"宸叉坊鍔?Live2D 瑙掕壊: {pet['name']}")

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
                self._show_toast(f"宸叉坊鍔犺嚜瀹氫箟瑙掕壊: {pet['name']}")

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
            self._char_grid(self._live2d, add_plus=True, on_plus=self._upload_live2d),
            "Live2D搴?,
        )
        self._tabs.addTab(self._char_grid(self._flat_library_pets(), add_plus=False), "骞抽潰绱犳潗搴?)
        custom_wrap = QWidget()
        custom_lay = QVBoxLayout(custom_wrap)
        custom_lay.addWidget(self._char_grid(self._custom_pets, add_plus=False), 1)
        up_row = QHBoxLayout()
        up_row.addStretch()
        up = QPushButton("涓婁紶骞抽潰绱犳潗")
        up.setStyleSheet(BTN_PRIMARY)
        up.clicked.connect(self._upload_flat)
        up_row.addWidget(up)
        up_row.addStretch()
        custom_lay.addLayout(up_row)
        self._tabs.addTab(custom_wrap, "鑷畾涔?)
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
        self._log(f"閫変腑: {pet['name']}")

    def _open_pet_main(self, pet: dict) -> None:
        if pet.get("is_flat") or pet.get("is_custom"):
            pet = self._enrich_pet_motions(pet)
            self._apply_pet_switch(pet)
            return
        self._pet_main_id = pet["id"]
        self._nav("pet_main")
        self._log(f"鏌ョ湅瑙掕壊: {pet['name']}")

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
        self._detail_lay.addWidget(QLabel(pet["personality"]))
        self._detail_lay.addWidget(QLabel("鍔ㄤ綔灞曠ず"))
        row = QHBoxLayout()
        motions = [m for m in pet.get("motions", []) if self._motion_playable(m) or not pet.get("is_flat")]
        if not motions:
            b = QPushButton("鏆傛棤鍔ㄤ綔")
            b.setEnabled(False)
            b.setStyleSheet(BTN_GLASS)
            row.addWidget(b)
        else:
            for m in motions:
                b = QPushButton(m["label"][:8])
                b.setStyleSheet(BTN_GLASS)
                if self._motion_playable(m):
                    b.clicked.connect(
                        lambda _=False, motion=m, p=pet, label=pic: self._play_motion(
                            motion, label, self._pet_idle_path(p), QSize(260, 170)
                        )
                    )
                elif self.on_play_motion:
                    b.clicked.connect(lambda _=False, mid=m["id"]: self.on_play_motion(mid))
                row.addWidget(b)
        row.addStretch()
        self._detail_lay.addLayout(row)
        self._detail.show()

    def _page_pet_main(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(24, 16, 24, 24)
        top = QHBoxLayout()
        back = QPushButton("鈫?杩斿洖")
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
        self._pet_main_switch_btn = QPushButton("鍒囨崲璇ヨ鑹?)
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
        self._pet_main_desc = QLabel("AI灏忓姪鎵嬄蜂綘鐨勬闈㈤櫔浼?)
        tx.addWidget(self._pet_main_desc)
        for ln in ("杞婚噺闄即", "璐村績鍔╂墜", "娌绘剤姣忎竴澶?):
            tx.addWidget(QLabel(ln))
        row.addLayout(tx)
        ll.addLayout(row)
        body.addWidget(left, 1)
        right = QVBoxLayout()
        right.addWidget(QLabel("<h3>鍔ㄤ綔灞曠ず</h3>"))
        self._pet_main_motions_widget = QWidget()
        self._pet_main_motions_lay = QVBoxLayout(self._pet_main_motions_widget)
        self._pet_main_motions_lay.setContentsMargins(0, 0, 0, 0)
        right.addWidget(self._pet_main_motions_widget)
        right.addStretch()
        body.addLayout(right, 1)
        lay.addLayout(body)
        lay.addWidget(QLabel("<h3>瀹犵墿鐘舵€?/h3>"))
        stats = QHBoxLayout()
        for icon, title, key, col in (("馃槉", "蹇冩儏", "mood", "#3b82f6"), ("鈿?, "鑳介噺", "energy", "#fb923c"), ("鉂わ笍", "濂芥劅搴?, "affection", "#ec4899")):
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
        while self._pet_main_motions_lay.count():
            item = self._pet_main_motions_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        motions = [m for m in pet.get("motions", []) if self._motion_playable(m) or not pet.get("is_flat")]
        if not motions:
            b = QPushButton("鏆傛棤鍔ㄤ綔")
            b.setEnabled(False)
            b.setStyleSheet(BTN_GLASS)
            self._pet_main_motions_lay.addWidget(b)
        else:
            for m in motions:
                b = QPushButton(m["label"])
                b.setStyleSheet(BTN_GLASS)
                if self._motion_playable(m):
                    b.clicked.connect(
                        lambda _=False, motion=m, p=pet: self._play_motion(
                            motion, self._pet_main_pic, self._pet_idle_path(p), QSize(120, 120)
                        )
                    )
                elif self.on_play_motion:
                    b.clicked.connect(lambda _=False, mid=m["id"]: self.on_play_motion(mid))
                self._pet_main_motions_lay.addWidget(b)

    def _page_ai(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(24, 16, 24, 24)
        lay.setSpacing(16)

        menu_panel = QFrame()
        menu_panel.setFixedWidth(190)
        menu_panel.setStyleSheet(_glass_style(14))
        menu_lay = QVBoxLayout(menu_panel)
        menu_lay.addWidget(QLabel("<b>AI 瀵硅瘽</b>"))
        self._ai_tool_btns: dict[str, QPushButton] = {}
        for key, icon, label in (
            ("voice_pack", "馃帣锔?, "璇煶鍖呴€夋嫨"),
            ("text_reader", "馃摉", "鏂囨湰鏈楄"),
            ("history", "馃挰", "鑱婂ぉ璁板綍"),
            ("voice_settings", "馃攰", "璇煶璁剧疆"),
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
        header.addWidget(QLabel("<b>璇煶鍖呴€夋嫨</b>"))
        header.addStretch()
        import_btn = QPushButton("瀵煎叆璇煶鍖?)
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

    def _import_voice_pack(self) -> None:
        dlg = VoicePackImportDialog(self._project_root, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        pack = dlg.result_pack()
        if not pack:
            return
        self._voice_pack_id = str(pack.get("id") or "").strip()
        self._refresh_voice_pack_list()
        selected = next(
            (p for p in self._voice_packs if str(p.get("id", "")).strip() == self._voice_pack_id),
            pack,
        )
        self._select_voice_pack(selected, toast_prefix="宸插鍏ュ苟鍒囨崲璇煶鍖?)

    def _ai_text_reader_page(self) -> QWidget:
        page = QFrame()
        page.setStyleSheet(_glass_style(14))
        lay = QVBoxLayout(page)

        header = QHBoxLayout()
        header.addWidget(QLabel("<b>鏂囨湰鏈楄</b>"))
        header.addStretch()
        import_btn = QPushButton("瀵煎叆鏂囨湰")
        import_btn.setStyleSheet(BTN_GLASS)
        import_btn.clicked.connect(self._import_text_for_reading)
        header.addWidget(import_btn)
        lay.addLayout(header)

        self._read_text_edit = QTextEdit()
        self._read_text_edit.setAcceptRichText(False)
        self._read_text_edit.setPlaceholderText("鍦ㄨ繖閲岀矘璐存垨瀵煎叆瑕佹湕璇荤殑鏂囨湰鈥?)
        self._read_text_edit.textChanged.connect(self._update_text_reader_state)
        lay.addWidget(self._read_text_edit, 1)

        self._read_text_hint = QLabel("瀵煎叆鎴栬緭鍏ユ枃鏈悗浼氭寜褰撳墠璇煶闊宠壊鏈楄銆?)
        self._read_text_hint.setWordWrap(True)
        self._read_text_hint.setStyleSheet("color:#64748b;font-size:12px;")
        lay.addWidget(self._read_text_hint)

        bottom = QHBoxLayout()
        bottom.addStretch()
        self._stop_read_text_btn = QPushButton("鍋滄")
        self._stop_read_text_btn.setStyleSheet(BTN_GLASS)
        self._stop_read_text_btn.clicked.connect(self._stop_text_reading)
        bottom.addWidget(self._stop_read_text_btn)
        self._read_text_btn = QPushButton("鏈楄")
        self._read_text_btn.setStyleSheet(BTN_PRIMARY)
        self._read_text_btn.clicked.connect(self._read_text_aloud)
        bottom.addWidget(self._read_text_btn)
        lay.addLayout(bottom)

        self._update_text_reader_state()
        return page

    def _import_text_for_reading(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "瀵煎叆鏂囨湰",
            self._project_root,
            BOOK_FILE_DIALOG_FILTER,
        )
        if not paths:
            return
        try:
            documents = read_book_files(paths)
            text = combine_documents(documents)
        except Exception as exc:
            QMessageBox.warning(self, "瀵煎叆澶辫触", f"鏂囨湰瀵煎叆澶辫触锛歿exc}")
            return
        self._read_documents = documents
        self._read_text_edit.setPlainText(text)
        names = "銆?.join(doc.title for doc in documents[:3])
        more = len(documents) - min(3, len(documents))
        if more > 0:
            names += f" 绛?{len(documents)} 鏈?
        self._show_toast(f"宸插鍏ワ細{names}")

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
            self._show_toast("鏈楄鍔熻兘鏈繛鎺ユ瀹?)
            return
        title = self._current_read_text_title()
        try:
            self.on_read_text(text, title=title)
        except Exception as exc:
            self._show_toast(f"鏈楄澶辫触锛歿exc}")
            return
        self._show_toast("宸插紑濮嬫湕璇绘枃鏈?)

    def _stop_text_reading(self) -> None:
        if not self.on_stop_read_text:
            return
        try:
            self.on_stop_read_text()
        except Exception as exc:
            self._show_toast(f"鍋滄澶辫触锛歿exc}")
            return
        self._show_toast("宸茶姹傚仠姝㈡湕璇?)

    def _current_read_text_title(self) -> str:
        docs = list(getattr(self, "_read_documents", []) or [])
        if not docs:
            return "鏂囨湰"
        if len(docs) == 1:
            return docs[0].title
        return f"{docs[0].title} 绛?{len(docs)} 鏈?

    def _update_text_reader_state(self) -> None:
        if not hasattr(self, "_read_text_hint") or not hasattr(self, "_read_text_btn"):
            return
        text = self._read_text_edit.toPlainText().strip() if hasattr(self, "_read_text_edit") else ""
        settings = normalize_tts_settings(self._tts_settings)
        if not text:
            self._set_text_reader_hint("瀵煎叆鎴栬緭鍏ユ枃鏈悗浼氭寜褰撳墠璇煶闊宠壊鏈楄銆?, enabled=False)
            return
        if not settings.get("enabled"):
            self._set_text_reader_hint("璇煶宸插叧闂紝鍚敤璇煶鍚庢墠鑳芥湕璇汇€?, enabled=False)
            return
        expected = self._current_voice_language()
        detected = detect_text_language(text)
        if not expected:
            self._set_text_reader_hint("褰撳墠闊宠壊璇█鏈煡锛屾棤娉曟牎楠屾湕璇昏瑷€銆?, enabled=False)
            return
        if not detected:
            self._set_text_reader_hint("鏃犳硶璇嗗埆杈撳叆璇█锛屾棤娉曟湕璇汇€?, enabled=False)
            return
        if languages_match(expected, detected):
            self._set_text_reader_hint(
                f"璇█鍖归厤锛氬綋鍓嶉煶鑹?{language_label(expected)}锛岃緭鍏?{language_label(detected)}銆?,
                enabled=True,
                ok=True,
            )
            return
        self._set_text_reader_hint(
            f"璇█涓嶅尮閰嶆棤娉曟湕璇伙紙褰撳墠闊宠壊锛歿language_label(expected)}锛岃緭鍏ワ細{language_label(detected)}锛夈€?,
            enabled=False,
            ok=False,
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
        if not text.strip() or not settings.get("enabled"):
            return False
        expected = self._current_voice_language()
        detected = detect_text_language(text)
        return languages_match(expected, detected)

    def _current_voice_language(self) -> str:
        settings = normalize_tts_settings(self._tts_settings)
        language = language_from_edge_voice(settings.get("edge_voice"))
        if language:
            return language

        pack = self._current_voice_pack()
        if pack:
            raw_language = pack.get("language")
            if isinstance(raw_language, dict):
                language = normalize_language_id(raw_language.get("id") or raw_language.get("label"))
                if language:
                    return language
            language = language_from_edge_voice(pack.get("edge_voice"))
            if language:
                return language
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
        top.addWidget(QLabel("<b>鑱婂ぉ璁板綍</b>"))
        self._chat_search = QLineEdit()
        self._chat_search.setPlaceholderText("鎼滅储鑱婂ぉ鍐呭鈥?)
        self._chat_search.textChanged.connect(self._filter_chat_view)
        top.addWidget(self._chat_search, 1)
        lay.addLayout(top)
        self._chat_view = QTextEdit()
        self._chat_view.setReadOnly(True)
        self._chat_empty = QLabel("鏆傛棤鑱婂ぉ璁板綍")
        self._chat_empty.setStyleSheet("color:#94a3b8;")
        self._chat_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._chat_empty, 1)
        lay.addWidget(self._chat_view, 1)
        self._chat_view.hide()
        bottom = QHBoxLayout()
        self._ai_in = QLineEdit()
        self._ai_in.setPlaceholderText("杈撳叆娑堟伅鈥?)
        send = QPushButton("鍙戦€?)
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
        lay.addWidget(QLabel("<b>璇煶璁剧疆</b>"))
        self._tts_enabled_check = QCheckBox("鍚敤璇煶")
        self._tts_enabled_check.stateChanged.connect(self._on_tts_controls_changed)
        lay.addWidget(self._tts_enabled_check)
        lay.addWidget(QLabel("鍚堟垚妯″紡"))
        self._tts_quality_combo = QComboBox()
        for preset in TTS_QUALITY_PRESETS:
            self._tts_quality_combo.addItem(str(preset["label"]), str(preset["id"]))
        self._tts_quality_combo.currentIndexChanged.connect(self._on_tts_controls_changed)
        lay.addWidget(self._tts_quality_combo)
        lay.addWidget(QLabel("鎯呮劅 / 椋庢牸"))
        self._tts_style_combo = QComboBox()
        for preset in TTS_STYLE_PRESETS:
            self._tts_style_combo.addItem(str(preset["label"]), str(preset["id"]))
        self._tts_style_combo.currentIndexChanged.connect(self._on_tts_controls_changed)
        lay.addWidget(self._tts_style_combo)
        lay.addWidget(QLabel("绮剧粏鍙傛暟"))
        controls = QGridLayout()
        self._tts_edge_rate_slider, self._tts_edge_rate_value = self._add_tts_slider(
            controls, 0, "绁炵粡璇€?, -50, 50
        )
        self._tts_edge_pitch_slider, self._tts_edge_pitch_value = self._add_tts_slider(
            controls, 1, "绁炵粡闊宠皟", -50, 50
        )
        self._tts_edge_volume_slider, self._tts_edge_volume_value = self._add_tts_slider(
            controls, 2, "绁炵粡闊抽噺", -50, 50
        )
        self._tts_rate_slider, self._tts_rate_value = self._add_tts_slider(
            controls, 3, "绂荤嚎璇€?, 80, 260
        )
        self._tts_volume_slider, self._tts_volume_value = self._add_tts_slider(
            controls, 4, "绂荤嚎闊抽噺", 0, 100
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
            "text_reader": 1,
            "history": 2,
            "voice_settings": 3,
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
        if not hasattr(self, "_tts_quality_combo"):
            return
        self._tts_settings = normalize_tts_settings(self._tts_settings)
        self._tts_control_syncing = True
        self._tts_enabled_check.setChecked(bool(self._tts_settings.get("enabled", True)))
        self._set_combo_current_data(self._tts_quality_combo, str(self._tts_settings.get("quality") or "basic"))
        self._set_combo_current_data(self._tts_style_combo, str(self._tts_settings.get("emotion_style") or "auto"))
        self._set_tts_slider_values_from_settings()
        self._tts_control_syncing = False
        self._render_tts_detail()
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
            "鍩虹璇煶鍚堟垚",
        )
        style = next(
            (str(p["label"]) for p in TTS_STYLE_PRESETS if str(p["id"]) == settings.get("emotion_style")),
            "鑷姩璺熼殢鎯呯华",
        )
        enabled = "宸插惎鐢? if settings.get("enabled") else "宸插叧闂?
        edge_rate = settings.get("edge_rate") or os.getenv("EDGE_TTS_RATE", "+8%")
        edge_pitch = settings.get("edge_pitch") or os.getenv("EDGE_TTS_PITCH", "+12Hz")
        edge_volume = settings.get("edge_volume") or os.getenv("EDGE_TTS_VOLUME", "+8%")
        tts_rate = settings.get("tts_rate") or os.getenv("TTS_RATE", "168")
        tts_volume = settings.get("tts_volume") or os.getenv("TTS_VOLUME", "0.95")
        self._tts_detail.setText(
            f"{enabled} 路 {mode}\n"
            f"鎯呮劅 / 椋庢牸: {style}\n"
            f"绁炵粡璇煶: 璇€?{edge_rate}锛岄煶璋?{edge_pitch}锛岄煶閲?{edge_volume}\n"
            f"绂荤嚎鍥為€€: 璇€?{tts_rate}锛岄煶閲?{tts_volume}"
        )

    def _current_tts_voice_label(self) -> str:
        settings = normalize_tts_settings(self._tts_settings)
        return next(
            (label for label, value in TTS_VOICE_PRESETS if value == settings.get("edge_voice")),
            str(settings.get("edge_voice") or "璺熼殢璇煶鍖?/ 榛樿"),
        )

    def _refresh_voice_pack_list(self) -> None:
        if not hasattr(self, "_voice_pack_list"):
            return
        current_voice = str(normalize_tts_settings(self._tts_settings).get("edge_voice") or "").strip()
        self._voice_packs = scan_voice_packs(self._project_root) + tts_voice_preset_choices(current_voice)
        self._voice_pack_list.clear()
        current = self._current_voice_choice_key()
        selected_row = 0
        found_current = False
        for i, pack in enumerate(self._voice_packs):
            item = QListWidgetItem(f"{pack.get('icon', '馃帣锔?)}  {pack.get('name', pack.get('id', ''))}")
            item.setData(Qt.ItemDataRole.UserRole, self._voice_choice_key(pack))
            item.setToolTip(str(pack.get("description", "")))
            self._voice_pack_list.addItem(item)
            if self._voice_choice_key(pack) == current:
                selected_row = i
                found_current = True
        if not found_current:
            self._voice_pack_id = ""
            selected_row = 0
        self._voice_pack_list.setCurrentRow(selected_row)
        if self._voice_packs:
            self._render_voice_pack_detail(self._voice_packs[selected_row])
        self._update_text_reader_state()

    @staticmethod
    def _voice_choice_key(pack: dict) -> str:
        if str(pack.get("kind") or "") == "edge_voice":
            return f"edge_voice:{str(pack.get('edge_voice') or '').strip()}"
        return f"voice_pack:{str(pack.get('id') or '').strip()}"

    def _current_voice_choice_key(self) -> str:
        edge_voice = str(normalize_tts_settings(self._tts_settings).get("edge_voice") or "").strip()
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
        self._select_voice_pack(pack, toast_prefix="宸插垏鎹㈣闊冲寘")

    def _select_voice_pack(self, pack: dict, toast_prefix: str = "宸插垏鎹㈣闊冲寘") -> None:
        if str(pack.get("kind") or "") == "edge_voice":
            voice_id = str(pack.get("edge_voice") or "").strip()
            self._voice_pack_id = ""
            settings = dict(self._tts_settings)
            settings["edge_voice"] = voice_id
            self._tts_settings = normalize_tts_settings(settings)
            if self.on_voice_pack_changed:
                self.on_voice_pack_changed({"id": "", "name": pack.get("name") or "榛樿"})
            if self.on_tts_settings_changed:
                self.on_tts_settings_changed(dict(self._tts_settings))
            self._render_tts_detail()
            self._set_current_voice_choice_row()
            self._render_voice_pack_detail(pack)
            self._update_text_reader_state()
            self._show_toast(f"{toast_prefix}: {pack.get('name') or pack.get('display_name') or '榛樿'}")
            return

        pack_id = str(pack.get("id", "")).strip()
        self._voice_pack_id = pack_id
        if str(self._tts_settings.get("edge_voice") or "").strip():
            settings = dict(self._tts_settings)
            settings["edge_voice"] = ""
            self._tts_settings = normalize_tts_settings(settings)
            self._apply_tts_controls_from_settings()
            if self.on_tts_settings_changed:
                self.on_tts_settings_changed(dict(self._tts_settings))
        self._set_current_voice_choice_row()
        self._render_voice_pack_detail(pack)
        self._update_text_reader_state()
        if self.on_voice_pack_changed:
            self.on_voice_pack_changed(pack)
        self._show_toast(f"{toast_prefix}: {pack.get('name') or pack.get('display_name') or '榛樿'}")

    def _render_voice_pack_detail(self, pack: dict) -> None:
        if not hasattr(self, "_voice_pack_detail"):
            return
        desc = str(pack.get("description") or "")
        sample = str(pack.get("sample_text") or "")
        lines = [desc] if desc else []
        language = pack.get("language")
        if isinstance(language, dict) and language.get("label"):
            lines.append(f"璇█: {language.get('label')}")
        if pack.get("is_custom"):
            sample_count = int(pack.get("sample_count") or 0)
            lines.append(f"鏈湴鏍锋湰: {sample_count} 涓?)
            converted_count = int(pack.get("converted_count") or 0)
            if converted_count:
                lines.append(f"MP4 杞?MP3: {converted_count} 涓?)
            denoised_count = int(pack.get("denoised_count") or 0)
            lines.append(f"杞诲害闄嶅櫔鍓湰: {denoised_count} 涓紝鍘熷闊抽宸蹭繚鐣?)
        lines.append(f"闊宠壊: {self._current_tts_voice_label()}")
        if sample:
            lines.append(f"璇曞惉: {sample}")
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
        self.append_chat_message(name, "ai", f"鏀跺埌锛歿t}")
        self._ai_in.clear()

    def _page_placeholder(self, title: str) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel(f"<h2>{title}</h2>"))
        ph = QLabel("鍔熻兘寮€鍙戜腑...")
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


