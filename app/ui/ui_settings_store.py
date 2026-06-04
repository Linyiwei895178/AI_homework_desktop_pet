"""
UI settings load/save helpers (pet_ui_settings.json + personalization).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
UI_SETTINGS_PATH = DATA_DIR / "pet_ui_settings.json"
PERSONALIZATION_SETTINGS_PATH = DATA_DIR / "pet_personalization_settings.json"

DEFAULT_DESKTOP_BEHAVIOR: dict[str, Any] = {
    "auto_walk": False,
    "follow_mouse_mode": 0,
}

DEFAULT_UI_SETTINGS: dict[str, Any] = {
    "pin_top": True,
    "hover_fade": False,
    "status_bar": False,
    "chat_open": False,
    "voice_pack_id": "",
    "desktop_behavior": dict(DEFAULT_DESKTOP_BEHAVIOR),
}

DEFAULT_PERSONALIZATION_SETTINGS: dict[str, dict[str, Any]] = {
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


def normalize_follow_mouse_mode(behavior: dict[str, Any] | None) -> int:
    """0=关闭，1=轻微，2=紧密；兼容旧版 follow_mouse 布尔值。"""
    if not isinstance(behavior, dict):
        return 0
    if "follow_mouse_mode" in behavior:
        try:
            return max(0, min(2, int(behavior["follow_mouse_mode"])))
        except (TypeError, ValueError):
            return 0
    if behavior.get("follow_mouse") in (True, "true", "1", 1):
        return 1
    return 0


def desktop_behavior_from_settings(settings: dict[str, Any] | None) -> dict[str, Any]:
    """解析 desktop_behavior 段，缺失字段用默认值。"""
    merged = dict(DEFAULT_DESKTOP_BEHAVIOR)
    if not isinstance(settings, dict):
        return merged
    raw = settings.get("desktop_behavior")
    if isinstance(raw, dict):
        if "auto_walk" in raw:
            merged["auto_walk"] = bool(raw["auto_walk"])
        merged["follow_mouse_mode"] = normalize_follow_mouse_mode(raw)
    return merged


def merge_ui_settings(raw: dict[str, Any] | None) -> dict[str, Any]:
    """合并磁盘设置与默认 UI 设置。"""
    merged = json.loads(json.dumps(DEFAULT_UI_SETTINGS))
    if isinstance(raw, dict):
        for key, value in raw.items():
            if key == "personalization_settings":
                continue
            if key == "desktop_behavior" and isinstance(value, dict):
                behavior = dict(merged.get("desktop_behavior", DEFAULT_DESKTOP_BEHAVIOR))
                behavior.update(value)
                merged["desktop_behavior"] = behavior
            else:
                merged[key] = value
    merged["desktop_behavior"] = desktop_behavior_from_settings(merged)
    return merged


def load_ui_settings(project_root: str | Path | None = None) -> dict[str, Any]:
    """
    加载 pet_ui_settings.json 与个性化配置（优先 ui 文件内 personalization_settings）。
    """
    root = Path(project_root) if project_root else PROJECT_ROOT
    data_dir = root / "data"
    ui_raw = _read_json(data_dir / "pet_ui_settings.json")
    ui_settings = merge_ui_settings(ui_raw)
    embedded = ui_raw.get("personalization_settings") if isinstance(ui_raw, dict) else None
    if isinstance(embedded, dict):
        personalization = _merge_personalization(embedded)
    else:
        personalization = _merge_personalization(_read_json(data_dir / "pet_personalization_settings.json"))
    return {
        "ui_settings": ui_settings,
        "personalization_settings": personalization,
        "personalization": personalization,
        "tts_settings": ui_settings.get("tts_settings", {}) if isinstance(ui_settings, dict) else {},
        "voice_pack_id": ui_settings.get("voice_pack_id", "") if isinstance(ui_settings, dict) else "",
        "desktop_behavior": ui_settings.get("desktop_behavior", dict(DEFAULT_DESKTOP_BEHAVIOR)),
    }


def save_ui_settings(settings: dict[str, Any], project_root: str | Path | None = None) -> bool:
    """
    保存到 data/pet_ui_settings.json（合并已有内容，不整文件覆盖无关字段）。
    """
    root = Path(project_root) if project_root else PROJECT_ROOT
    path = root / "data" / "pet_ui_settings.json"
    merged = merge_ui_settings(_read_json(path))
    if isinstance(settings, dict):
        if isinstance(settings.get("personalization_settings"), dict):
            merged["personalization_settings"] = _merge_personalization(settings["personalization_settings"])
        ui_patch = settings.get("ui_settings")
        if isinstance(ui_patch, dict):
            settings = {**settings, **ui_patch}
        for key in (
            "pin_top",
            "hover_fade",
            "status_bar",
            "chat_open",
            "voice_pack_id",
            "tts_settings",
            "desktop_behavior",
        ):
            if key not in settings:
                continue
            if key == "desktop_behavior" and isinstance(settings[key], dict):
                behavior = dict(merged.get("desktop_behavior", DEFAULT_DESKTOP_BEHAVIOR))
                behavior.update(settings[key])
                merged["desktop_behavior"] = desktop_behavior_from_settings({"desktop_behavior": behavior})
            else:
                merged[key] = settings[key]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except OSError:
        return False


def merge_personalization_into_state(current_state: dict[str, Any] | None) -> dict[str, Any]:
    """从 pet_ui_settings.json 读取个性化并写入 current_state。"""
    state = dict(current_state) if isinstance(current_state, dict) else {}
    bundle = load_ui_settings()
    personalization = bundle.get("personalization_settings")
    if not isinstance(personalization, dict):
        personalization = _merge_personalization({})
    state["personalization_settings"] = personalization
    state["personalization"] = personalization
    return state


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def _merge_personalization(raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {
        key: dict(value)
        for key, value in DEFAULT_PERSONALIZATION_SETTINGS.items()
    }
    if not isinstance(raw, dict):
        return merged
    for section, values in raw.items():
        if not isinstance(values, dict):
            continue
        target = merged.setdefault(str(section), {})
        target.update(values)
    return merged
