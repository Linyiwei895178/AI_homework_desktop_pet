"""
Read-only helpers for UI personalization settings.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
UI_SETTINGS_PATH = DATA_DIR / "pet_ui_settings.json"
PERSONALIZATION_SETTINGS_PATH = DATA_DIR / "pet_personalization_settings.json"


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
    "companion_mode": {
        "mode": "学习陪伴",
        "auto_switch": True,
        "focus_silence": True,
    },
    "boundaries": {
        "no_disturb_when_fullscreen": True,
    },
}


def load_ui_settings(project_root: str | Path | None = None) -> dict[str, Any]:
    """
    Load UI settings and personalization settings without importing Qt widgets.
    """
    root = Path(project_root) if project_root else PROJECT_ROOT
    data_dir = root / "data"
    ui_settings = _read_json(data_dir / "pet_ui_settings.json")
    personalization = _merge_personalization(
        _read_json(data_dir / "pet_personalization_settings.json")
    )
    return {
        "ui_settings": ui_settings,
        "personalization_settings": personalization,
        "tts_settings": ui_settings.get("tts_settings", {}) if isinstance(ui_settings, dict) else {},
        "voice_pack_id": ui_settings.get("voice_pack_id", "") if isinstance(ui_settings, dict) else "",
    }


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
