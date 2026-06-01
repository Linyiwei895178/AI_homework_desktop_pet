"""
Vision-side proactive event helpers.
"""

from __future__ import annotations

from typing import Any

from models.nlp.proactive_event_builder import (
    build_cloud_pet_event,
    build_gesture_event,
    build_screen_time_event,
)
from models.vision.computer_activity_detector import build_companion_event as build_computer_activity_event


def build_companion_event(state: dict[str, Any]) -> dict[str, Any]:
    """Compatibility wrapper for computer activity companion comments."""
    return build_computer_activity_event(state)


__all__ = [
    "build_companion_event",
    "build_computer_activity_event",
    "build_screen_time_event",
    "build_cloud_pet_event",
    "build_gesture_event",
]
