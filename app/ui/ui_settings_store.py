"""
UI settings persistence for pet personalization.

Reads/writes data/pet_ui_settings.json with safe JSON helpers.
"""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any, Dict, Optional

from utils.safe_json import safe_read_json, safe_write_json


# Default personalization settings (deep-copied when read fails)
DEFAULT_PET_PERSONALIZATION_SETTINGS: Dict[str, Any] = {
    "theme": "default",
    "scale": 1.0,
    "opacity": 1.0,
    "pin_to_top": True,
    "auto_hide": False,
    "mouse_follow": False,
    "free_roam": True,
    "show_status_bar": True,
    "show_chat_bubble": True,
    "show_cloud_panel": False,
    "response_language": "zh-CN",
    "voice_pack_id": "",
    "tts_rate": "+8%",
    "tts_pitch": "+12Hz",
    "tts_volume": "+8%",
    "chat_role": "可爱女孩",
    "animation_enabled": True,
    "motion_speed": "normal",
    "interaction_sound": True,
    "auto_feedback": True,
}


_SETTINGS_PATH = Path(__file__).resolve().parents[2] / "data" / "pet_ui_settings.json"


def load_ui_settings() -> Dict[str, Any]:
    """
    Load UI personalization settings from data/pet_ui_settings.json.

    If the file is missing or corrupt, returns a deep copy of DEFAULT_PET_PERSONALIZATION_SETTINGS.

    :returns: dict of settings
    """
    data = safe_read_json(_SETTINGS_PATH, default=None)
    if data is None or not isinstance(data, dict):
        return copy.deepcopy(DEFAULT_PET_PERSONALIZATION_SETTINGS)
    merged = copy.deepcopy(DEFAULT_PET_PERSONALIZATION_SETTINGS)
    merged.update(data)
    return merged


def save_ui_settings(settings: Dict[str, Any]) -> bool:
    """
    Save UI personalization settings to data/pet_ui_settings.json.

    :param settings: dict of settings (only known keys are saved)
    :returns: True on success
    """
    existing = load_ui_settings()
    existing.update(settings)
    # Only keep keys that are in the default dict
    clean = {k: v for k, v in existing.items() if k in DEFAULT_PET_PERSONALIZATION_SETTINGS}
    return safe_write_json(str(_SETTINGS_PATH), clean)


def reset_ui_settings() -> Dict[str, Any]:
    """
    Reset settings to defaults and persist.

    :returns: default settings dict
    """
    defaults = copy.deepcopy(DEFAULT_PET_PERSONALIZATION_SETTINGS)
    safe_write_json(str(_SETTINGS_PATH), defaults)
    return defaults
